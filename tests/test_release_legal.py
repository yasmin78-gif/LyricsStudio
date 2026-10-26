import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QTabWidget
from lyrics_studio.app import SettingsDialog
from lyrics_studio.legal_info import legal_directory, show_legal, FFMPEG_URL, MODEL_URL


class ReleaseLegalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_license_view_opens_without_network_and_retains_source_information(self):
        notices = legal_directory() / 'THIRD_PARTY.md'
        self.assertIn('LGPL',notices.read_text(encoding='utf-8'))
        records = json.loads((legal_directory()/'SOURCES.json').read_text(encoding='utf-8'))
        self.assertEqual(len(records),9)
        self.assertTrue(all(len(record['sha256'])==64 for record in records))
        with patch('lyrics_studio.legal_info.QDesktopServices.openUrl') as external:
            def close():
                dialog = QApplication.activeModalWidget()
                self.assertIsInstance(dialog,QDialog)
                self.assertEqual(dialog.findChild(QTabWidget).count(),5)
                dialog.reject()
            QTimer.singleShot(20,close)
            show_legal(None)
            external.assert_not_called()

    def test_download_buttons_open_provider_pages_only_on_click(self):
        with patch('lyrics_studio.app.ffmpeg_candidates',return_value=[]), patch('lyrics_studio.app.model_candidates',return_value=[]), patch('lyrics_studio.app.QDesktopServices.openUrl') as external:
            dialog = SettingsDialog(QSettings('LyricsStudio-QA','Downloads'),None)
            external.assert_not_called()
            buttons = {button.text():button for button in dialog.findChildren(QPushButton)}
            buttons['FFmpeg herunterladen ↗'].click()
            buttons['Whisper-Modell herunterladen ↗'].click()
            self.assertEqual([call.args[0].toString() for call in external.call_args_list],[FFMPEG_URL,MODEL_URL])
            dialog.close()


if __name__=='__main__':
    unittest.main()
