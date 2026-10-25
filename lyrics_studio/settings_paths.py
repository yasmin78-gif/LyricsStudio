"""Local file discovery only; never downloads models or runs selected programs."""
import os
from pathlib import Path
import shutil
import sys


def existing_file(value, executable=False):
    value = os.path.expandvars(str(value or '').strip())
    if not value:
        return None
    if executable:
        found = shutil.which(value)
        if found:
            return Path(found).resolve()
    path = Path(value).expanduser()
    # Relative paths must not depend on the application that launched us.
    return path.resolve() if path.is_absolute() and path.is_file() else None


def model_candidates(current='', extra=()):
    roots = [Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share')) / 'LyricsStudio/models',
             Path(sys.executable).parent / 'models', Path(__file__).resolve().parents[1] / 'models']
    roots += [Path.home() / 'Downloads', Path.home() / 'models', Path.home() / 'AI/Models',
              Path.home() / 'AI/Models/whisper.cpp']
    # Common shared model locations, on the application's drive and the user's drive.
    for anchor in {Path(sys.executable).anchor, Path(__file__).resolve().anchor, Path.home().anchor}:
        if anchor:
            roots += [Path(anchor) / 'AI/Models/whisper.cpp', Path(anchor) / 'AI/Models/whisper',
                      Path(anchor) / 'AI/Models']
    result = []
    for value in [current, os.environ.get('LYRICS_STUDIO_MODEL', ''), *extra]:
        path = existing_file(value)
        if path and path.suffix.lower() == '.bin' and path not in result:
            result.append(path)
            roots.append(path.parent)
    for root in roots:
        if root.is_dir():
            for path in sorted(root.glob('ggml*.bin'))[:100]:
                if path.is_file() and path.resolve() not in result:
                    result.append(path.resolve())
    return result


def ffmpeg_candidates(current='', extra=()):
    """Find distinct installed FFmpeg executables without a whole-drive search."""
    result = []
    def add(value):
        path = existing_file(value, executable=True)
        if path and path not in result:
            result.append(path)
    add(current)
    for value in extra:
        add(value)
    add('ffmpeg')
    for directory in os.get_exec_path():
        found = shutil.which('ffmpeg', path=directory)
        if found:
            add(found)
    name = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
    for root in [Path(sys.executable).parent, Path(__file__).resolve().parents[1],
                 Path.home() / 'ffmpeg', Path.home() / '.local/bin']:
        for relative in [name, 'bin/' + name, 'tools/' + name, 'ffmpeg/bin/' + name]:
            candidate = root / relative
            if candidate.is_file():
                add(candidate)
    if sys.platform == 'win32':
        local = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
        packages = local / 'Microsoft/WinGet/Packages'
        for pattern in ('*FFmpeg*/ffmpeg*/bin/ffmpeg.exe', '*FFmpeg*/bin/ffmpeg.exe'):
            for candidate in packages.glob(pattern):
                add(candidate)
        for base in [Path(os.environ.get('ProgramFiles', 'C:/Program Files')), local / 'Programs']:
            candidate = base / 'ffmpeg/bin/ffmpeg.exe'
            if candidate.is_file():
                add(candidate)
    return result


def resource_name(path, model=False):
    path = Path(path)
    if model:
        name = path.stem.removeprefix('ggml-').replace('-', ' ')
        size = path.stat().st_size / 1024 ** 3
        return f'Whisper {name.title()} · {size:.1f} GB'.replace('.', ',')
    import re
    version = re.search(r'ffmpeg[-_ ]?(\d+(?:\.\d+){0,2})', str(path), re.IGNORECASE)
    return 'FFmpeg ' + version.group(1) if version else 'FFmpeg'


def chooser_start(value, executable=False, fallback=None):
    found = existing_file(value, executable)
    if found:
        return str(found)
    expanded = Path(os.path.expandvars(str(value or ''))).expanduser()
    if expanded.is_absolute():
        if expanded.is_dir():
            return str(expanded)
        if expanded.parent.is_dir():
            return str(expanded.parent)
    for candidate in (fallback, Path.home() / 'Downloads', Path.home()):
        if candidate and Path(candidate).is_dir():
            return str(Path(candidate))
    return str(Path.home())
