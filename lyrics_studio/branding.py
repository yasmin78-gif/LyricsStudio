"""Shared application icon and Windows taskbar identity."""
from pathlib import Path
import sys

from PySide6.QtGui import QIcon

ASSETS = Path(__file__).parent / 'assets'


def application_icon():
    icon = QIcon(str(ASSETS / ('icon.ico' if sys.platform == 'win32' else 'icon.png')))
    return icon if not icon.isNull() else QIcon(str(ASSETS / 'icon.png'))


def set_taskbar_identity():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('LyricsStudio.Desktop')
