"""Keep the Widgets/WebEngine runtime and its PE dependency closure, not all QML plugins."""
from pathlib import Path
import json
import pefile


def release_binaries(entries):
    plugins = {'qwindows.dll', 'qoffscreen.dll', 'qmodernwindowsstyle.dll', 'qgif.dll', 'qico.dll',
               'qjpeg.dll', 'qsvg.dll', 'qsvgicon.dll', 'qschannelbackend.dll',
               'qopensslbackend.dll', 'qcertonlybackend.dll', 'qnetworklistmanager.dll'}
    roots = []
    by_name = {}
    for entry in entries:
        dest, source, _ = entry
        # Never satisfy Windows ICU/API dependencies with an unrelated tool's DLL.
        if 'poppler' in [part.lower() for part in Path(source).parts]:
            continue
        path = dest.replace('\\', '/').lower()
        name = Path(dest).name.lower()
        by_name.setdefault(name, []).append(entry)
        if '/qml/' in path:
            continue
        if '/plugins/' in path:
            if name in plugins:
                roots.append(entry)
        elif not path.startswith('pyside6/') or name.endswith('.pyd') or name == 'qtwebengineprocess.exe':
            if not ('icu' in name and 'poppler' in source.lower()):
                roots.append(entry)
    selected = {entry[0]: entry for entry in roots}
    queue = list(roots)
    while queue:
        _, source, _ = queue.pop()
        pe = pefile.PE(source, fast_load=True)
        pe.parse_data_directories(directories=[1,13])
        for table in ('DIRECTORY_ENTRY_IMPORT', 'DIRECTORY_ENTRY_DELAY_IMPORT'):
            for dependency in getattr(pe, table, []):
                for entry in by_name.get(dependency.dll.decode().lower(), []):
                    if entry[0] not in selected:
                        selected[entry[0]] = entry
                        queue.append(entry)
        pe.close()
    forbidden = ('Qt6Charts', 'Qt6DataVisualization', 'Qt6Graphs', 'Qt6VirtualKeyboard', 'Qt6Quick3D')
    assert not any(Path(e[0]).name.startswith(forbidden) for e in selected.values()), 'Unexpected GPL-only Qt module'
    Path('build').mkdir(exist_ok=True)
    Path('build/runtime-binaries.json').write_text(json.dumps(sorted(selected), indent=2), encoding='utf-8')
    return list(selected.values())


def release_data(entries):
    result = []
    for entry in entries:
        path = entry[0].replace('\\','/').lower()
        if '/qml/' in path or '.debug.' in path:
            continue
        result.append(entry)
    return result
