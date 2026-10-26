"""Download matching, unmodified upstream sources and retain license notices."""
import concurrent.futures
import hashlib
import importlib.metadata
import json
import posixpath
from pathlib import Path
import shutil
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LEGAL = ROOT / 'legal'
CACHE = ROOT / 'dist/upstream-sources'
QT = '6.12.0'
MODULES = ('qtbase', 'qtdeclarative', 'qtpositioning', 'qtwebchannel', 'qtsvg', 'qtshadertools', 'qttranslations')
URLS = {f'{module}-everywhere-src-{QT}.tar.xz':
        f'https://download.qt.io/official_releases/qt/6.12/{QT}/submodules/{module}-everywhere-src-{QT}.tar.xz'
        for module in MODULES}
URLS[f'pyside-setup-everywhere-src-{QT}.tar.xz'] = f'https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-{QT}-src/pyside-setup-everywhere-src-{QT}.tar.xz'
URLS['qtwebengine-everywhere-src-6.140.0.tar.xz'] = ('https://download.qt.io/online/qtsdkrepository/all_os/extensions/qtwebengine/6120/61400/src_doc_examples/'
    'extensions.qtwebengine.6120.61400.src/6.12.0-0-202609281005qtwebengine-everywhere-src-6.140.0.tar.xz')


def download(item):
    name, url = item
    target = CACHE / name
    if not target.exists():
        temporary = target.with_suffix('.download')
        urllib.request.urlretrieve(url, temporary)
        temporary.rename(target)
    digest = hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()
    print(f'Source ready: {name} ({target.stat().st_size // 1048576} MiB)', flush=True)
    return {'file': name, 'upstream': url, 'sha256': digest, 'size': target.stat().st_size,
            'release': f'https://github.com/yasmin78-gif/LyricsStudio/releases/download/v0.6.0/{name}',
            'modifications': 'None; unmodified upstream archive'}


def notices(record):
    module = record['file'].split('-everywhere')[0]
    if module == 'qtwebengine':
        return  # Chromium's exact generated credits are exported separately.
    target = LEGAL / 'upstream-notices' / module
    target.mkdir(parents=True, exist_ok=True)
    old_index = target / 'INDEX.json'
    if old_index.exists():
        for name in json.loads(old_index.read_text(encoding='utf-8')):
            owned = (target / name).resolve()
            assert owned.is_relative_to(target.resolve())
            owned.unlink(missing_ok=True)
    index = {}
    with tarfile.open(CACHE / record['file']) as archive:
        referenced = set()
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith('qt_attribution.json') and '/tests/' not in member.name and '/examples/' not in member.name:
                entries = json.loads(archive.extractfile(member).read(), strict=False)
                for entry in entries if isinstance(entries,list) else [entries]:
                    names = entry.get('LicenseFile',[])
                    if isinstance(names,str):
                        names = names.split(',')
                    for name in names:
                        referenced.add(posixpath.normpath(posixpath.join(posixpath.dirname(member.name),name.strip())))
                referenced.add(member.name)
        for member in archive:
            if not member.isfile() or member.size > 2_000_000:
                continue
            path = Path(member.name)
            lower = path.name.lower()
            if member.name not in referenced and not lower.startswith(('license','licence','copying','copyright','notice')):
                continue
            if member.name not in referenced and path.suffix.lower() in ('.png','.svg','.py','.cmake','.json','.yaml','.cc','.h'):
                continue
            # Qt library notices, not example/test project licenses.
            if '/tests/' in member.name or '/examples/' in member.name:
                continue
            filename = hashlib.sha256(member.name.encode()).hexdigest()[:16] + '.txt'
            (target / filename).write_bytes(archive.extractfile(member).read())
            index[filename] = member.name
    (target / 'INDEX.json').write_text(json.dumps(index, indent=2), encoding='utf-8')
    return len(index)


if __name__ == '__main__':
    LEGAL.mkdir(exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        records = list(pool.map(download, URLS.items()))
    (LEGAL / 'SOURCES.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    for record in records:
        print('Retained licenses:',record['file'],notices(record),flush=True)
    shutil.copyfile(Path(sys.base_prefix) / 'LICENSE.txt', LEGAL / 'Python.txt')
    for name in ('pyinstaller', 'shiboken6', 'PySide6', 'PySide6_Essentials', 'PySide6_Addons', 'PySide6_WebEngine'):
        distribution = importlib.metadata.distribution(name)
        for file in distribution.files:
            if '/licenses/' in str(file).replace('\\','/') or Path(str(file)).name in ('COPYING.txt','LICENSE.txt'):
                target = LEGAL / 'wheel-licenses' / name / Path(str(file)).name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(distribution.locate_file(file),target)
    licenses = {
        'LGPL-3.0.txt': 'https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/LGPL-3.0-only.txt',
        'GPL-3.0.txt': 'https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/GPL-3.0-only.txt',
        'LGPL-2.1.txt': 'https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt',
        'OpenSSL.txt': 'https://raw.githubusercontent.com/openssl/openssl/openssl-3.0.19/LICENSE.txt',
        'libffi.txt': 'https://raw.githubusercontent.com/libffi/libffi/v3.4.6/LICENSE',
        'InnoSetup.txt': 'https://jrsoftware.org/files/is/license.txt',
    }
    for name,url in licenses.items():
        if not (LEGAL / name).is_file():
            urllib.request.urlretrieve(url, LEGAL / name)
    print('Legal source preparation complete.',flush=True)
