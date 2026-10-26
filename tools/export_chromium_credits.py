"""Retain Chromium's upstream notices, including a source superset of Windows use."""
import html
import posixpath
import re
from pathlib import Path
import tarfile

source = Path('dist/upstream-sources/qtwebengine-everywhere-src-6.140.0.tar.xz')
target = Path('legal/chromium-credits.html')
count = 0
referenced = set()
with tarfile.open(source,mode='r|xz') as archive:
    for member in archive:
        if member.isfile() and member.name.endswith('README.chromium'):
            data = archive.extractfile(member).read().decode('utf-8',errors='replace')
            for value in re.findall(r'^License File:\s*(.+)$',data,re.M):
                for filename in value.split(','):
                    filename = filename.strip()
                    if filename.startswith('//'):
                        referenced.add('src/3rdparty/chromium/'+filename[2:])
                    else:
                        referenced.add(posixpath.normpath(posixpath.join(posixpath.dirname(member.name),filename)))
with target.open('w',encoding='utf-8') as output:
    output.write('<!doctype html><html><head><meta charset="utf-8"><title>Qt WebEngine / Chromium notices</title></head><body>')
    output.write('<h1>Qt WebEngine 6.140.0 / Chromium notices</h1><p>Full license, copyright and notice files retained from the unmodified corresponding upstream source archive. This intentionally includes a superset of components in the Windows binary; inclusion here does not assert that every listed component is linked or shipped. Qt-specific parts are used under LGPLv3.</p>')
    with tarfile.open(source,mode='r|xz') as archive:
        for member in archive:
            if not member.isfile() or member.size > 2_000_000:
                continue
            name = Path(member.name).name.lower()
            if member.name not in referenced and not name.startswith(('license','licence','copying','copyright','notice')):
                continue
            if name.endswith(('.py','.cc','.h','.js','.ts','.png','.svg','.gn','.gni','.json')):
                continue
            data = archive.extractfile(member).read()
            if b'\0' in data:
                continue
            output.write('<h2>'+html.escape(member.name)+'</h2><pre>'+html.escape(data.decode('utf-8',errors='replace'))+'</pre>')
            count += 1
    output.write('</body></html>')
assert count > 100, 'Incomplete source notices'
print('Retained WebEngine/Chromium notices:',count,'files;',target.stat().st_size,'bytes')
