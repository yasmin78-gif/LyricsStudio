"""Cancellable FFmpeg conversion and local Whisper inference."""
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import wave

from lyrics_editor.store import atomic_write, encoded
from lyrics_editor.timebase import frame_interval
from lyrics_sync import reference, validate
from .projects import project_lock


class Cancelled(Exception):
    pass


def tool_path(value='ffmpeg'):
    found = shutil.which(str(value))
    if not found:
        raise ValueError('FFmpeg wurde nicht gefunden. Bitte unter Einstellungen auswählen.')
    return str(Path(found).resolve())


def filter_value(value):
    """Escape both FFmpeg filter option and filtergraph parsing levels."""
    value = str(value).replace('\\', '/')
    first = ''.join('\\' + c if c in "\\':" else c for c in value)
    return ''.join('\\' + c if c in "\\'[],;" else c for c in first)


def parse_srt(text, duration):
    result = []
    text = text.lstrip('\ufeff').replace('\r\n', '\n').strip()
    if not text:
        return result
    pattern = re.compile(r'(\d+):(\d{2}):(\d{2})[,.](\d{3})')
    for block in re.split(r'\n\s*\n', text):
        lines = block.strip().splitlines()
        if lines and lines[0].strip().isdigit():
            lines.pop(0)
        if not lines or '-->' not in lines[0]:
            raise ValueError('Whisper hat ungültige Untertiteldaten erzeugt.')
        parts = lines.pop(0).split('-->')
        stamps = [pattern.fullmatch(p.strip()) for p in parts]
        if len(stamps) != 2 or not all(stamps):
            raise ValueError('Ungültige Zeitangaben in der Whisper-Ausgabe.')
        times = []
        for stamp in stamps:
            h, m, s, ms = map(int, stamp.groups())
            if m > 59 or s > 59:
                raise ValueError('Ungültige Zeitangaben in der Whisper-Ausgabe.')
            times.append(h * 3600 + m * 60 + s + ms / 1000)
        start, end = times
        wording = '\n'.join(lines).strip()
        if not wording or len(wording) > 4000 or start >= duration or end <= start:
            raise ValueError('Eine erkannte Passage hat ungültigen Text oder ungültige Zeiten.')
        if end > duration + 0.1:
            raise ValueError('Eine erkannte Passage liegt hinter dem Audioende.')
        result.append((start, min(end, duration), wording))
    return result


def make_document(audio, segments, reference_text=''):
    audio = Path(audio).resolve()
    with wave.open(str(audio), 'rb') as stream:
        duration = stream.getnframes() / stream.getframerate()
    with audio.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    recognized = []
    for index, (start, end, text) in enumerate(segments, 1):
        a, b = frame_interval(start, end, 24)
        unresolved = dict(status='unresolved', start_time=None, end_time=None,
            start_frame=None, end_frame=None, method=None,
            manual_confirmation=False, display_enabled=False)
        recognized.append(dict(id=f'ASR-{index:04}', sequence_index=index, text=text,
            manual_text_confirmation=False, wording_status='unresolved', reference_ids=[],
            hypothesis_repeat_of=None, alignment_status='not_run', timing=unresolved,
            asr_segment_timing=dict(start_time=start, end_time=end, start_frame=a, end_frame=b),
            review_reasons=['Automatisch erkannt: Wortlaut und Zeitgrenzen am Audio prüfen.']))
    doc = dict(schema_version='2.0', workflow_status='needs_review', fps=24,
        audio=dict(path=str(audio), sha256=digest, duration_seconds=duration),
        original_lyrics=dict(evidence_role='reference_only_never_assumed_transcript',
                             reference_lines=reference(reference_text)),
        recognized_occurrences=recognized, confirmed_occurrences=[], alignment_attempts=[])
    validate(doc)
    return doc


def run_process(command, cwd, cancel, report, label, duration=None):
    log_path = Path(cwd) / 'processing.log'
    progress_path = Path(cwd) / 'progress.txt'
    # File-backed output avoids blocked pipes and allows prompt cancellation even during model loading.
    with log_path.open('ab') as log:
        with subprocess.Popen(command, cwd=cwd, stdout=log, stderr=log,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                              start_new_session=os.name != 'nt') as process:
            try:
                while process.poll() is None:
                    if cancel.is_set():
                        raise Cancelled('Verarbeitung abgebrochen.')
                    percent = -1
                    if duration and progress_path.exists():
                        content = progress_path.read_text(encoding='utf-8', errors='replace')[-12000:]
                        matches = re.findall(r'out_time_us=(\d+)', content)
                        if matches:
                            percent = min(99, int(int(matches[-1]) / 1_000_000 / duration * 100))
                    report(label, percent)
                    time.sleep(0.15)
            finally:
                if process.poll() is None:
                    if os.name == 'nt':
                        # Includes child processes started by Windows Python launchers.
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    else:
                        os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        if os.name == 'nt':
                            process.kill()
                        else:
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
            if cancel.is_set():
                raise Cancelled('Verarbeitung abgebrochen.')
            if process.returncode:
                tail = log_path.read_text(encoding='utf-8', errors='replace')[-2500:]
                raise ValueError(f'{label} fehlgeschlagen.\n{tail}')


def prepare_project(project, settings, cancel=None, report=lambda label, percent: None):
    cancel = cancel or threading.Event()
    with project_lock(project.directory):
        project.reload()
        if project.ready or project.data.exists() or project.state_dir.exists():
            raise ValueError('Dieses Projekt hat bereits Editor-Daten. Bitte ein neues Projekt anlegen.')
        project.update(status='processing', error=None)
        try:
            ffmpeg = tool_path(settings.get('ffmpeg') or 'ffmpeg')
            model = Path(settings.get('model', '')).expanduser()
            if not settings.get('model') or not model.is_file():
                raise ValueError('Bitte unter Einstellungen ein vorhandenes Whisper-Modell (.bin) auswählen.')
            model = model.resolve()
            capability = subprocess.run([ffmpeg, '-hide_banner', '-h', 'filter=whisper'],
                capture_output=True, text=True, errors='replace', timeout=15,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if 'Transcribe audio' not in capability.stdout + capability.stderr:
                raise ValueError('Diese FFmpeg-Version enthält keinen Whisper-Filter. Bitte eine Version mit Whisper-Unterstützung auswählen.')
            source = Path(project.info['source_path'])
            if not source.is_file():
                raise ValueError('Die ausgewählte Quelldatei ist nicht mehr vorhanden. Bitte den Song erneut importieren.')
            with tempfile.TemporaryDirectory(prefix='.import-', dir=project.directory) as temporary:
                stage = Path(temporary)
                audio = stage / 'audio.wav'
                common = [ffmpeg, '-hide_banner', '-nostdin', '-y', '-loglevel', 'info',
                          '-nostats', '-progress', 'progress.txt']
                report('Audio wird vorbereitet …', -1)
                run_process(common + ['-i', str(source), '-map', '0:a:0', '-vn', '-ac', '2',
                    '-ar', '44100', '-c:a', 'pcm_s16le', str(audio)], stage, cancel, report,
                    'Audio wird vorbereitet …')
                with wave.open(str(audio), 'rb') as stream:
                    duration = stream.getnframes() / stream.getframerate()
                if not math.isfinite(duration) or duration <= 0:
                    raise ValueError('Die Audiodatei enthält kein abspielbares Audio.')
                (stage / 'progress.txt').unlink(missing_ok=True)
                try:
                    model_arg = Path(os.path.relpath(model, stage)).as_posix()
                except ValueError:  # Windows: model on a different drive
                    model_arg = model.as_posix()
                audio_filter = (f'whisper=model={filter_value(model_arg)}:language={project.info["language"]}'
                    f':translate=false:queue=20:use_gpu={str(bool(settings.get("gpu", True))).lower()}'
                    ':destination=transcript.srt:format=srt:max_len=120')
                run_process(common + ['-i', str(audio), '-vn', '-af', audio_filter, '-f', 'null', '-'],
                    stage, cancel, report, 'Whisper erkennt Textpassagen …', duration)
                transcript = stage / 'transcript.srt'
                if not transcript.is_file():
                    raise ValueError('Whisper hat keine Textpassagen gefunden. Bitte Aufnahme und Sprache prüfen.')
                segments = parse_srt(transcript.read_text(encoding='utf-8-sig'), duration)
                if not segments:
                    raise ValueError('Whisper hat keine Textpassagen gefunden. Bitte Aufnahme und Sprache prüfen.')
                reference_path = project.path('reference.txt')
                reference_text = reference_path.read_text(encoding='utf-8') if reference_path.exists() else ''
                doc = make_document(audio, segments, reference_text)
                if cancel.is_set():
                    raise Cancelled('Verarbeitung abgebrochen.')
                final_audio = project.path('audio.wav')
                os.replace(audio, final_audio)
                doc['audio']['path'] = 'audio.wav'
                atomic_write(project.data, encoded(doc))
                shutil.copyfile(transcript, project.path('whisper.srt'))
                shutil.copyfile(stage / 'processing.log', project.path('processing.log'))
                project.update(status='ready', error=None, duration_seconds=duration,
                               source_count=len(segments))
                report('Bereit für die Bearbeitung', 100)
        except Exception as exc:
            project.update(status='cancelled' if isinstance(exc, Cancelled) else 'error', error=str(exc))
            raise
