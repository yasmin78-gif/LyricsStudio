"""Portable projects. No user media or application settings live in the repository."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid

from lyrics_editor.store import atomic_write, encoded

AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.aif', '.aiff', '.wma'}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def default_library():
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    return base / 'LyricsStudio' / 'projects'


@contextmanager
def project_lock(directory):
    """OS lock is released on process exit, including after a crash."""
    lease = (Path(directory) / '.project.lock').open('a+b')
    try:
        if lease.tell() == 0:
            lease.write(b'0')
            lease.flush()
        lease.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('Dieses Projekt wird bereits in einer anderen Anwendung verarbeitet.') from exc
        yield
    finally:
        lease.close()


class Project:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.file = self.directory / 'project.json'
        self.reload()

    def reload(self):
        self.info = json.loads(self.file.read_text(encoding='utf-8'))
        if self.info.get('project_version') != 1:
            raise ValueError('Diese Projektversion wird nicht unterstützt.')
        if not isinstance(self.info.get('name'), str) or not self.info['name'].strip():
            raise ValueError('Das Projekt hat keinen gültigen Namen.')
        uuid.UUID(self.info['id'])
        return self

    def path(self, relative):
        path = (self.directory / relative).resolve()
        if not path.is_relative_to(self.directory) or path == self.directory:
            raise ValueError('Ein Projektpfad liegt außerhalb des Projektordners.')
        return path

    @property
    def data(self):
        return self.path('lyrics_timing.json')

    @property
    def state_dir(self):
        return self.path('editor-state')

    @property
    def ready(self):
        return self.info.get('status') == 'ready' and self.data.is_file()

    def update(self, **values):
        self.info.update(values, updated_at=timestamp())
        atomic_write(self.file, encoded(self.info))


class Library:
    def __init__(self, root=None):
        self.root = Path(root or default_library()).expanduser().resolve()
        if any((parent / '.git').exists() for parent in (self.root, *self.root.parents)):
            raise ValueError('Bitte die persönliche Projektbibliothek außerhalb eines Git-Repositorys anlegen.')
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self):
        projects, errors = [], []
        for file in self.root.glob('*/project.json'):
            try:
                projects.append(Project(file.parent))
            except (ValueError, KeyError, OSError, TypeError) as exc:
                errors.append(f'{file.parent.name}: {exc}')
        projects.sort(key=lambda p: p.info.get('updated_at', ''), reverse=True)
        return projects, errors

    def create(self, name, audio, reference_text='', language='auto'):
        name = name.strip()
        source = Path(audio).expanduser().resolve(strict=True)
        if not name or len(name) > 120:
            raise ValueError('Bitte einen Projektnamen mit 1 bis 120 Zeichen eingeben.')
        if not source.is_file() or source.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError('Bitte eine unterstützte Audiodatei auswählen.')
        if language not in ('auto', 'de', 'en', 'fr', 'es', 'it', 'pt', 'nl', 'pl'):
            raise ValueError('Nicht unterstützte Sprache.')
        identity = str(uuid.uuid4())
        directory = self.root / identity
        directory.mkdir()
        info = dict(project_version=1, id=identity, name=name, created_at=timestamp(),
                    updated_at=timestamp(), status='new', source_path=str(source),
                    source_name=source.name, language=language, fps=24, error=None)
        atomic_write(directory / 'project.json', encoded(info))
        if reference_text.strip():
            atomic_write(directory / 'reference.txt', reference_text.encode('utf-8'))
        return Project(directory)
