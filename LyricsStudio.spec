# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
exec(Path('tools/bundle_policy.py').read_text(encoding='utf-8'))


a = Analysis(
    ['lyrics_studio/launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[('lyrics_editor/static', 'lyrics_editor/static'), ('lyrics_studio/assets', 'lyrics_studio/assets'),
           ('legal', 'legal'), ('LICENSE', '.'), ('README.md', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Do not bundle Poppler's versioned ICU under the Windows system ICU name.
# An unrelated Poppler directory on PATH can otherwise break Qt at startup.
a.binaries = release_binaries(a.binaries)
a.datas = release_data(a.datas)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LyricsStudio',
    icon='lyrics_studio/assets/icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=os.environ.get('LYRICS_STUDIO_BUILD_CONSOLE') == '1',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LyricsStudio',
)
