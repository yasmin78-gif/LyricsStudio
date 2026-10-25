# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


a = Analysis(
    ['lyrics_studio/launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[('lyrics_editor/static', 'lyrics_editor/static'), ('lyrics_studio/assets', 'lyrics_studio/assets')],
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
a.binaries = [entry for entry in a.binaries
              if not (Path(entry[0]).name.lower().startswith(('icuuc', 'icudt'))
                      and 'poppler' in [part.lower() for part in Path(entry[1]).parts])]
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
    upx=True,
    console=False,
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
    upx=True,
    upx_exclude=[],
    name='LyricsStudio',
)
