import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import struct
import tempfile
import unittest

from PySide6.QtCore import QSettings
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from lyrics_studio.app import Window
from lyrics_studio.branding import ASSETS, application_icon


class BrandingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_icon_has_small_and_large_windows_resolutions(self):
        data = (ASSETS / 'icon.ico').read_bytes()
        reserved, kind, count = struct.unpack_from('<HHH', data)
        self.assertEqual((reserved, kind, count), (0, 1, 7))
        sizes = []
        for index in range(count):
            width, height, _, _, _, depth, length, offset = struct.unpack_from('<BBBBHHII', data, 6 + index*16)
            sizes.append(width or 256)
            self.assertEqual(width, height)
            self.assertEqual(depth, 32)
            self.assertFalse(QImage.fromData(data[offset:offset+length]).isNull())
        self.assertEqual(sizes, [16, 24, 32, 48, 64, 128, 256])
        self.assertFalse(application_icon().isNull())

    def test_project_window_receives_app_icon(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory)/'settings.ini'), QSettings.Format.IniFormat)
            window = Window(Path(directory)/'projects', settings)
            self.assertFalse(window.windowIcon().isNull())
            window.close()


if __name__ == '__main__':
    unittest.main()
