"""Create a portable, offline Resolve import package from confirmed passages."""
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import threading
import uuid
import zlib

from lyrics_editor.timebase import frame_interval
from lyrics_sync import validate
from . import __version__
from .processing import Cancelled


def lua_string(value):
    result = []
    for char in str(value):
        if char in ('\\', '"'):
            result.append('\\' + char)
        elif ord(char) < 32:
            result.append('\\' + str(ord(char)).zfill(3))
        else:
            result.append(char)
    return '"' + ''.join(result) + '"'


def lua_value(value):
    if value is None:
        return 'nil'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return lua_string(value)
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError('Nicht endlicher Zahlenwert im Export.')
        return str(value)
    if isinstance(value, list):
        return '{' + ',\n'.join(lua_value(item) for item in value) + '}'
    if isinstance(value, dict):
        return '{' + ',\n'.join('[' + lua_string(key) + ']=' + lua_value(item) for key, item in value.items()) + '}'
    raise TypeError('Unbekannter Exportwert.')


def title_plan(document, name, fps=24, offset=0, width=1920, height=1080, include_audio=True):
    validate(document)
    if fps not in (24, 25, 30, 50, 60) or isinstance(fps, bool):
        raise ValueError('Bitte 24, 25, 30, 50 oder 60 FPS auswählen.')
    if not math.isfinite(offset) or not 0 <= offset <= 86400:
        raise ValueError('Ungültiger Song-Startversatz.')
    if (width, height) not in ((1920, 1080), (3840, 2160)):
        raise ValueError('Bitte Full HD oder UHD auswählen.')
    rows, ends = [], []
    for item in sorted(document['confirmed_occurrences'], key=lambda r: (r['timing']['start_time'], r['sequence_index'])):
        timing = item['timing']
        if not item['manual_text_confirmation'] or not timing['manual_confirmation'] or not timing['display_enabled']:
            raise ValueError('Nur ausdrücklich bestätigte, aktive Passagen dürfen exportiert werden.')
        start, end = frame_interval(timing['start_time'] + offset, timing['end_time'] + offset, fps)
        lane = next((index for index, boundary in enumerate(ends) if boundary <= start), len(ends))
        if lane == len(ends):
            ends.append(end)
        else:
            ends[lane] = end
        rows.append(dict(id=item['id'], text=item['text'], start_frame=start, end_frame=end,
                         track=lane + 1, source_start=timing['start_time'], source_end=timing['end_time']))
    if not rows:
        raise ValueError('Noch keine bestätigten Textpassagen vorhanden.')
    identity = uuid.uuid4().hex[:12]
    return dict(export_version=1, app_version=__version__, export_id=identity,
                name=name[:80] + ' - Lyrics ' + identity, fps=fps, width=width, height=height,
                offset_seconds=offset, audio_start_frame=frame_interval(offset, offset + 1, fps)[0],
                audio='song.wav' if include_audio else None, audio_sha256=document['audio']['sha256'],
                carrier_frames=max(row['end_frame']-row['start_frame'] for row in rows) + 1,
                tracks=len(ends), rows=rows)


def transparent_png(width, height):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    pixels = (b'\0' + b'\0' * (width * 4)) * height
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(pixels, 9)) + chunk(b'IEND', b''))


def export_package(document, name, audio_path, parent, *, fps=24, offset=0, width=1920, height=1080,
                   include_audio=True, cancel=None, report=lambda *_: None):
    cancel = cancel or threading.Event()
    plan = title_plan(document, name, fps, offset, width, height, include_audio)
    parent = Path(parent).resolve(strict=True)
    if not parent.is_dir():
        raise ValueError('Bitte einen vorhandenen Exportordner auswählen.')
    safe_name = re.sub(r'[^\w -]', '_', name, flags=re.UNICODE).strip(' .')[:60] or 'Lyrics'
    target = parent / (safe_name + '-DaVinci-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + plan['export_id'])
    def check_cancel():
        if cancel.is_set():
            raise Cancelled('DaVinci-Export abgebrochen.')
    with tempfile.TemporaryDirectory(prefix='.lyrics-export-', dir=parent) as temporary:
        root = Path(temporary).resolve()
        if not root.is_relative_to(parent):
            raise ValueError('Ungültiger temporärer Exportpfad.')
        carrier = root / 'carrier'
        carrier.mkdir()
        (root / 'comps').mkdir()
        (root / '.gitignore').write_text('# Private Lyrics Studio export\n*\n', encoding='utf-8')
        report('Transparente Titelmedien werden vorbereitet …', 0)
        pixels = transparent_png(width, height)
        anchor = None
        for index in range(plan['carrier_frames']):
            check_cancel()
            frame = carrier / f'Carrier_{index:06}.png'
            if index % 900 == 0:
                frame.write_bytes(pixels)
                anchor = frame
            else:
                try:
                    os.link(anchor, frame)
                except OSError:
                    shutil.copyfile(anchor, frame)
            if index % 50 == 0:
                report('Transparente Titelmedien werden vorbereitet …', int(index / plan['carrier_frames'] * 60))
        if include_audio:
            digest = hashlib.sha256()
            with Path(audio_path).open('rb') as source, (root / 'song.wav').open('xb') as output:
                while block := source.read(4 * 1024 * 1024):
                    check_cancel()
                    digest.update(block)
                    output.write(block)
            if digest.hexdigest() != plan['audio_sha256']:
                raise ValueError('Die Audiodatei wurde geändert. Export zum Schutz der Zeitangaben abgebrochen.')
        check_cancel()
        (root / 'manifest.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
        (root / 'Titel_Daten.lua').write_text('return ' + lua_value(plan) + '\n', encoding='utf-8')
        template = Path(__file__).parent / 'assets/resolve_import.lua'
        shutil.copyfile(template, root / 'Import_in_DaVinci.lua')
        for source, destination in [('resolve_styles.lua', 'Lyrics_Stile.lua'),
                                    ('resolve_style_picker.lua', 'Titelstil_in_Resolve.lua'),
                                    ('ghostly_mist.setting', 'Ghostly Mist Dissolve.setting')]:
            shutil.copyfile(template.parent / source, root / destination)
        command = 'dofile(' + lua_string((target / 'Import_in_DaVinci.lua').as_posix()) + ')'
        style_command = 'dofile(' + lua_string((target / 'Titelstil_in_Resolve.lua').as_posix()) + ')'
        (root / 'IMPORT-ANLEITUNG.txt').write_text(
            'Lyrics Studio - Bearbeitbare DaVinci-Titel\n\n'
            f'{len(plan["rows"])} bestätigte Passagen, {fps} FPS, {width} x {height}.\n\n'
            '1. In DaVinci Resolve das gewünschte Projekt öffnen.\n'
            '2. Workspace/Arbeitsbereich > Console/Konsole öffnen und Lua auswählen.\n'
            '3. Folgenden Befehl einfügen und Enter drücken:\n\n' + command + '\n\n'
            'Der Import legt eine neue Timeline und einen eigenen Medienordner an. Bestehende Timelines werden nicht überschrieben.\n'
            'Die Texte sind Fusion-Text+-Kompositionen: Clip auswählen, Fusion öffnen und den Knoten Lyrics_Text bearbeiten.\n'
            'Die Clips können in andere Timelines mit gleicher Bildrate kopiert und dort weiter animiert werden.\n'
            'Beabsichtigte Überlappungen liegen auf getrennten Videospuren. Anschließend das Resolve-Projekt speichern.\n'
            'Den gesamten Exportordner behalten: Die Titel referenzieren die transparente Bildsequenz und ihre Kompositionen.\n'
            'Bei verschobenem Exportordner den Pfad im dofile-Befehl anpassen. Keine einzelne Datei aus dem Paket verschieben.\n',
            encoding='utf-8')
        with (root / 'IMPORT-ANLEITUNG.txt').open('a', encoding='utf-8') as guide:
            guide.write('\nAnimationen nachträglich in Resolve wählen\n\n'
                        'In der Edit-Timeline einen oder mehrere Lyrics-Clips markieren. In der Lua-Konsole ausführen:\n\n'
                        + style_command + '\n\n'
                        'Im Dialog Standard Text+, Sanftes Ein-/Ausblenden oder Ghostly Mist Dissolve wählen.\n'
                        'Für weitere Passagen mit einem anderen Stil wiederholen. Text und Clipzeiten bleiben erhalten.\n'
                        'Die Vorlage wird mitgeliefert; eine separate Installation ist nicht nötig.\n'
                        'Die vorherige Fusion-Komposition bleibt im Clip erhalten. Jeder Wechsel legt eine neue Komposition an.\n'
                        'Schrift, Größe, Farbe und Position werden übernommen; eigene Keyframe-Animationen werden nicht in den neuen Stil übertragen.\n'
                        'Voraussetzung: Resolve mit Timeline:GetSelectedClips() (getestet mit Studio 21.1.1).\n')
        report('DaVinci-Export wird abgeschlossen …', 95)
        check_cancel()
        root.rename(target)
    report('DaVinci-Titelpaket erstellt', 100)
    return target
