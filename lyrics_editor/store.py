"""Review drafts. The input ASR document is NEVER opened for writing.

One authoritative, atomic snapshot contains rows and its schema-2 reviewed view.
Immutable pre-save revisions and optimistic revision checks prevent silent loss.
Only a separate explicit confirm action can construct confirmed occurrences.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid
import wave

from .timebase import validate_interval, frame_interval, frames_to_seconds, seconds_to_frame


class Conflict(ValueError):
    pass


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def atomic_write(path, payload):
    """Same-filesystem replace, after complete serialization and flush; retain old on failure."""
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('xb') as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, data, state_dir, title=None):
        self.data_path = Path(data).resolve(strict=True)
        self.base_hash = digest(self.data_path)
        self.base = json.loads(self.data_path.read_text(encoding='utf-8'))
        if self.base.get('schema_version') != '2.0':
            raise ValueError('Der Editor benötigt Lyrics-Schema 2.0.')
        from lyrics_sync import validate
        validate(self.base)
        audio_path = Path(self.base['audio']['path'])
        if not audio_path.is_absolute():
            audio_path = self.data_path.parent / audio_path
        self.audio = audio_path.resolve(strict=True)
        self.title = title or self.audio.stem
        if digest(self.audio) != self.base['audio']['sha256']:
            raise ValueError('Die Audiodatei passt nicht zum gespeicherten SHA-256.')
        self.audio_stat = (self.audio.stat().st_size, self.audio.stat().st_mtime_ns)
        self.duration = self.base['audio']['duration_seconds']
        self.fps = self.base['fps']
        with wave.open(str(self.audio), 'rb') as audio:
            if abs(audio.getnframes() / audio.getframerate() - self.duration) > 1 / audio.getframerate():
                raise ValueError('WAV-Dauer und Lyrics-Metadaten stimmen nicht überein.')
        self.directory = Path(state_dir).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'lyrics_editor_draft.json'
        if self.path == self.data_path or self.directory == self.audio:
            raise ValueError('Entwurf und Quelldaten müssen getrennt bleiben.')
        self.history = self.directory / 'revisions'
        self.history.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.undo_stack, self.redo_stack = [], []
        self.disk_hash = digest(self.path) if self.path.exists() else None
        if self.path.exists():
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            if saved['source_sha256'] != self.base_hash:
                raise Conflict('Der Entwurf gehört zu einem anderen Stand der Lyrics-Quelle. Nichts wurde überschrieben.')
            self.rows = saved['rows']
            self.revision = saved['revision']
            self._validate_rows(self.rows)
            if saved['reviewed_document'] != self.document():
                raise ValueError('Entwurf und bestätigte Ansicht sind widersprüchlich.')
            self.saved_revision = self.revision
        else:
            self.rows = []
            for index, item in enumerate(self.base['recognized_occurrences']):
                timing = item['asr_segment_timing']
                self.rows.append(dict(id='LYR-' + item['id'], source_ids=[item['id']], text=item['text'],
                    start=timing['start_time'], end=timing['end_time'], status='unreviewed', deleted=False,
                    repeat_of=None, order=index, confirmation=None, suggestion=dict(text=item['text'],
                    start=timing['start_time'], end=timing['end_time']), review_reasons=item['review_reasons']))
            # Also supports a source that already contains reviewed passages.
            for item in self.base['confirmed_occurrences']:
                for row in self.rows:
                    if row['status'] != 'confirmed' and set(row['source_ids']) & set(item['source_occurrence_ids']):
                        row['deleted'] = True
                entry = dict(id=item['id'], source_ids=item['source_occurrence_ids'], text=item['text'],
                    start=item['timing']['start_time'], end=item['timing']['end_time'], status='confirmed',
                    deleted=False, repeat_of=item['repeat_of'], order=len(self.rows), suggestion=None,
                    review_reasons=[], confirmation=dict(reviewer=item['manual_evidence']['reviewer'],
                    at=item['manual_evidence'].get('reviewed_at', now()), allow_overlap=True))
                existing = next((r for r in self.rows if r['id'] == entry['id']), None)
                if existing is not None:
                    existing.update(entry)
                else:
                    self.rows.append(entry)
            self.revision = uuid.uuid4().hex
            self.saved_revision = self.revision
            self._validate_rows(self.rows)

    def _source_guard(self):
        if digest(self.data_path) != self.base_hash:
            raise Conflict('Die Lyrics-Quelldatei wurde außerhalb des Editors geändert. Bitte nicht überschreiben.')
        stat = (self.audio.stat().st_size, self.audio.stat().st_mtime_ns)
        if stat != self.audio_stat:
            raise Conflict('Die Audiodatei wurde geändert. Sitzung zum Schutz der Zeiten angehalten.')

    def _check(self, revision):
        if revision != self.revision:
            raise Conflict('Ein anderer Tab hat den Stand geändert. Bitte neu laden; lokale Eingaben bleiben sichtbar.')
        self._source_guard()

    def _validate_rows(self, rows):
        identities = {r['id'] for r in rows}
        if len(identities) != len(rows):
            raise ValueError('Doppelte Lyrics-ID.')
        source_ids = {r['id'] for r in self.base['recognized_occurrences']}
        for row in rows:
            if row['status'] not in ('unreviewed', 'editing', 'confirmed') or not isinstance(row['deleted'], bool):
                raise ValueError('Ungültiger Bearbeitungsstatus.')
            if not isinstance(row['text'], str) or not row['text'].strip() or len(row['text']) > 4000:
                raise ValueError('Bitte einen Text mit 1 bis 4000 Zeichen eingeben.')
            if not set(row['source_ids']) <= source_ids:
                raise ValueError('Unbekannte ASR-Referenz.')
            validate_interval(row['start'], row['end'], self.duration, self.fps)
            if row['status'] == 'confirmed' and not row['confirmation']:
                raise ValueError('Bestätigung ohne manuelle Prüfaktion.')
            if row['status'] != 'confirmed' and row['confirmation'] is not None:
                raise ValueError('Ungeprüfte Zeile darf keine Bestätigung tragen.')
            visited, cursor = {row['id']}, row.get('repeat_of')
            while cursor:
                if cursor not in identities or cursor in visited:
                    raise ValueError('Ungültige oder zyklische Wiederholungsreferenz.')
                visited.add(cursor)
                cursor = next(r for r in rows if r['id'] == cursor).get('repeat_of')

    def document(self):
        doc = copy.deepcopy(self.base)
        doc['workflow_status'] = 'needs_review'
        doc['confirmed_occurrences'] = []
        confirmed = sorted((r for r in self.rows if not r['deleted'] and r['status'] == 'confirmed'),
                           key=lambda r: (r['start'], r['order']))
        ids = {r['id'] for r in confirmed}
        for index, row in enumerate(confirmed, 1):
            start_frame, end_frame = frame_interval(row['start'], row['end'], self.fps)
            doc['confirmed_occurrences'].append(dict(id=row['id'], sequence_index=index, text=row['text'],
                source_occurrence_ids=row['source_ids'], manual_text_confirmation=True,
                manual_evidence=dict(reviewer=row['confirmation']['reviewer'],
                    source='Local lyrics editor: explicit original-audio text and timing confirmation',
                    reviewed_at=row['confirmation']['at'], audio_sha256=self.base['audio']['sha256'],
                    allow_overlap=row['confirmation'].get('allow_overlap', False)),
                timing=dict(status='manual_confirmed', start_time=row['start'], end_time=row['end'],
                    start_frame=start_frame, end_frame=end_frame, method='manual_editor_review',
                    manual_confirmation=True, display_enabled=True),
                repeat_of=row['repeat_of'] if row['repeat_of'] in ids else None))
        doc['interval_convention'] = 'Half-open [start,end); outward coverage at 24 FPS; integer-frame representation tolerance 1e-7 frames.'
        doc['editor_review'] = dict(source_sha256=self.base_hash, revision=self.revision,
                                   timebase='outward-with-integer-tolerance-v1')
        from lyrics_sync import validate
        validate(doc)
        return doc

    def state(self):
        return dict(revision=self.revision, saved_revision=self.saved_revision,
            dirty=self.revision != self.saved_revision, has_saved_draft=self.path.exists(), rows=copy.deepcopy(self.rows),
            title=self.title, duration=self.duration, fps=self.fps, audio_name=self.audio.name,
            can_undo=bool(self.undo_stack), can_redo=bool(self.redo_stack),
            source_count=len(self.base['recognized_occurrences']), state_file=str(self.path),
            confirmed_count=sum(r['status'] == 'confirmed' and not r['deleted'] for r in self.rows))

    def act(self, payload):
        with self.lock:
            self._check(payload['revision'])
            action = payload['action']
            before = copy.deepcopy(self.rows)
            old_revision = self.revision
            old_undo, old_redo = copy.deepcopy(self.undo_stack), copy.deepcopy(self.redo_stack)
            try:
                if action in ('undo', 'redo'):
                    stack, target = (self.undo_stack, self.redo_stack) if action == 'undo' else (self.redo_stack, self.undo_stack)
                    if not stack:
                        return self.state()
                    target.append(before)
                    self.rows = stack.pop()
                else:
                    row = next((r for r in self.rows if r['id'] == payload.get('id')), None)
                    if action not in ('insert',) and row is None:
                        raise ValueError('Zeile nicht gefunden.')
                    if row is not None and row['deleted'] and action != 'restore':
                        raise ValueError('Entfernte Zeile zuerst wiederherstellen.')
                    if action == 'update':
                        start, end, _ = validate_interval(payload['start'], payload['end'], self.duration, self.fps)
                        text = payload['text'].strip()
                        if (text, start, end) == (row['text'], row['start'], row['end']):
                            return self.state()
                        row.update(text=text, start=start, end=end, status='editing', confirmation=None)
                    elif action in ('insert', 'duplicate'):
                        base = row if action == 'duplicate' else None
                        start = base['start'] if base else float(payload.get('start', 0))
                        end = base['end'] if base else min(self.duration, start + 3)
                        self.rows.append(dict(id='LYR-' + uuid.uuid4().hex, source_ids=base['source_ids'][:] if base else [],
                            text=base['text'] if base else 'Neue Textzeile', start=start, end=end, status='editing',
                            deleted=False, repeat_of=base['id'] if base else None, order=len(self.rows),
                            confirmation=None, suggestion=None, review_reasons=[]))
                    elif action == 'delete':
                        row.update(deleted=True, status='editing', confirmation=None)
                    elif action == 'restore':
                        row.update(deleted=False, status='editing', confirmation=None)
                    elif action == 'unconfirm':
                        row.update(status='editing', confirmation=None)
                    elif action == 'snap':
                        a = frames_to_seconds(seconds_to_frame(row['start'], self.fps, 'nearest'), self.fps)
                        b = min(self.duration, frames_to_seconds(seconds_to_frame(row['end'], self.fps, 'nearest'), self.fps))
                        validate_interval(a, b, self.duration, self.fps)
                        row.update(start=a, end=b, status='editing', confirmation=None)
                    elif action == 'confirm':
                        reviewer = payload.get('reviewer', '').strip()
                        if payload.get('acknowledge') is not True or not reviewer or len(reviewer) > 120:
                            raise ValueError('Bitte die Hörprüfung ausdrücklich bestätigen und einen Namen angeben.')
                        a, b = frame_interval(row['start'], row['end'], self.fps)
                        overlap = any(not other['deleted'] and other['id'] != row['id'] and other['status'] == 'confirmed'
                            and a < frame_interval(other['start'], other['end'], self.fps)[1]
                            and b > frame_interval(other['start'], other['end'], self.fps)[0] for other in self.rows)
                        if overlap and payload.get('allow_overlap') is not True:
                            raise ValueError('Überlappende Framebereiche: gemeinsame Framegrenze korrigieren oder Überlappung bewusst erlauben.')
                        row.update(status='confirmed', confirmation=dict(reviewer=reviewer, at=now(),
                                   allow_overlap=payload.get('allow_overlap') is True))
                    else:
                        raise ValueError('Unbekannte Aktion.')
                    self._validate_rows(self.rows)
                    self.undo_stack.append(before)
                    self.redo_stack.clear()
                self.revision = uuid.uuid4().hex
                self._validate_rows(self.rows)
                self.document()
                if action == 'confirm':
                    self._save()
            except Exception:
                self.rows, self.revision = before, old_revision
                self.undo_stack, self.redo_stack = old_undo, old_redo
                raise
            return self.state()

    def _save(self):
        self._source_guard()
        actual = digest(self.path) if self.path.exists() else None
        if actual != self.disk_hash:
            raise Conflict('Der gespeicherte Entwurf wurde extern geändert. Keine Datei überschrieben.')
        self._validate_rows(self.rows)
        doc = self.document()
        snapshot = dict(editor_schema_version='1.0', source_sha256=self.base_hash, revision=self.revision,
                        saved_at=now(), rows=self.rows, reviewed_document=doc)
        payload = encoded(snapshot)
        if self.path.exists():
            backup = self.history / (now().replace(':', '-') + '-' + uuid.uuid4().hex + '.json')
            with backup.open('xb') as output:
                output.write(self.path.read_bytes())
                output.flush()
                os.fsync(output.fileno())
        atomic_write(self.path, payload)
        self.disk_hash = digest(self.path)
        self.saved_revision = self.revision

    def save(self, revision):
        with self.lock:
            self._check(revision)
            self._save()
            return self.state()

    def reload(self, revision):
        with self.lock:
            self._check(revision)
            if not self.path.exists():
                raise ValueError('Noch kein gespeicherter Entwurf vorhanden.')
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            if saved['source_sha256'] != self.base_hash:
                raise Conflict('Gespeicherter Entwurf passt nicht zur Quelle.')
            self._validate_rows(saved['rows'])
            old_rows, old_revision = self.rows, self.revision
            try:
                self.rows, self.revision = saved['rows'], saved['revision']
                if saved['reviewed_document'] != self.document():
                    raise ValueError('Entwurf und bestätigte Ansicht sind widersprüchlich.')
            except Exception:
                self.rows, self.revision = old_rows, old_revision
                raise
            self.saved_revision = self.revision
            self.disk_hash = digest(self.path)
            self.undo_stack.clear()
            self.redo_stack.clear()
            return self.state()

    def export(self, revision):
        with self.lock:
            self._check(revision)
            self._save()
            doc = self.document()
            # Export is outside the source directory; keep its audio reference usable.
            doc['audio']['path'] = str(self.audio)
            path = self.directory / ('lyrics_reviewed-' + self.revision + '.json')
            payload = encoded(doc)
            if path.exists():
                if path.read_bytes() != payload:
                    raise Conflict('Exportdatei existiert mit anderem Inhalt.')
            else:
                with path.open('xb') as output:
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
            return dict(path=str(path), confirmed_count=len(doc['confirmed_occurrences']), state=self.state())
