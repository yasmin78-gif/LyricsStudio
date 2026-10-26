"""Release gate: inventories the actual bundle and checks distribution policy."""
import hashlib
import json
from pathlib import Path
import sys


def inspect(root):
    root = Path(root)
    required = ('LICENSE','README.md','legal/THIRD_PARTY.md','legal/PRIVACY.md',
                'legal/LGPL-3.0.txt','legal/GPL-3.0.txt','legal/LGPL-2.1.txt',
                'legal/Python.txt','legal/SOURCES.json','legal/chromium-credits.html')
    internal = root / '_internal'
    assert all((internal / name).is_file() for name in required), 'Missing license or source notice'
    assert (internal/'legal/chromium-credits.html').stat().st_size > 100000, 'Incomplete Chromium notices'
    forbidden = ('qt6charts','qt6datavisualization','qt6graphs','qt6virtualkeyboard','qt6quick3d',
                 'qt6multimedia','qt6pdf','opengl32sw','icuuc.dll','icudt78.dll','ffmpeg.exe','ffprobe.exe')
    files = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        assert not path.name.lower().startswith(forbidden), f'Unexpected runtime: {path.name}'
        assert path.suffix.lower() not in ('.wav','.mp3','.flac','.m4a','.srt'), 'User media in release'
        files.append({'path':path.relative_to(root).as_posix(), 'bytes':path.stat().st_size,
                      'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest()})
    return {'format':1, 'app_version':'0.6.0', 'platform':'Windows x64',
            'python':'3.13.15', 'pyside':'6.12.0', 'qt':'6.12.0',
            'webengine':'6.140.0', 'chromium':'140.0.7339.225',
            'external_ffmpeg_bundled':False,'whisper_models_bundled':False,'files':files}


if __name__=='__main__':
    data = inspect(sys.argv[1])
    target = Path(sys.argv[2])
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('Bundle audit passed:',len(data['files']),'files;',round(sum(f['bytes'] for f in data['files'])/1048576),'MiB')
