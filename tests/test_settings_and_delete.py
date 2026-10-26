import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox, QLineEdit
from lyrics_studio.app import SettingsDialog, Window, choose_file
from lyrics_studio.projects import Library
from lyrics_studio.settings_paths import chooser_start, existing_file, model_candidates


class SettingsAndDeleteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.audio = self.root / 'original.wav'
        self.audio.write_bytes(b'synthetic test audio')
        self.library = Library(self.root / 'library')
        self.settings = QSettings(str(self.root / 'settings.ini'), QSettings.Format.IniFormat)

    def tearDown(self):
        self.temp.cleanup()

    def test_executable_uses_resolved_path_not_launch_directory(self):
        exe = self.root / 'ffmpeg.exe'
        exe.write_bytes(b'synthetic')
        with patch('lyrics_studio.settings_paths.shutil.which', return_value=str(exe)):
            self.assertEqual(existing_file('ffmpeg', True), exe)
            self.assertEqual(chooser_start('ffmpeg', True), str(exe))
            dialog = SettingsDialog(self.settings, None)
            self.assertEqual(dialog.ffmpeg.currentData(), str(exe))
            with patch('lyrics_studio.app.QFileDialog.getOpenFileName', return_value=('', '')) as picker:
                choose_file(dialog, QLineEdit(str(exe)), 'Select', '*.exe', True)
                self.assertEqual(picker.call_args.args[2], str(exe))
            dialog.close()

    def test_missing_file_uses_parent_or_explicit_fallback(self):
        self.assertEqual(chooser_start(str(self.root / 'missing.bin')), str(self.root))
        self.assertEqual(chooser_start('', fallback=self.root), str(self.root))
        self.assertIsNone(existing_file('relative.bin'))

    def test_model_discovery_and_selection(self):
        model = self.root / 'ggml-small.bin'
        model.write_bytes(b'synthetic')
        with patch.dict(os.environ, {'LYRICS_STUDIO_MODEL': str(model)}):
            self.assertIn(model, model_candidates())
            dialog = SettingsDialog(self.settings, None)
            self.assertEqual(dialog.model.currentData(), str(model))
            dialog.close()

    def test_project_delete_moves_only_project_and_preserves_original(self):
        project = self.library.create('Delete me', self.audio)
        other = self.library.create('Keep me', self.audio)
        trash = self.root / 'trash'
        def move(directory):
            shutil.move(directory, trash)
            return True, str(trash)
        self.library.delete(project, move)
        self.assertFalse(project.directory.exists())
        self.assertTrue((trash / 'project.json').is_file())
        self.assertTrue(other.directory.exists())
        self.assertEqual(self.audio.read_bytes(), b'synthetic test audio')

    def test_boolean_trash_result_and_ui_refresh(self):
        first = self.library.create('Remove', self.audio)
        second = self.library.create('Keep', self.audio)
        window = Window(library=self.library.root, settings=self.settings)
        for row in range(window.table.rowCount()):
            if window.table.item(row, 0).text() == 'Remove':
                window.table.selectRow(row)
        trash = self.root / 'trash'
        def move(directory):
            shutil.move(directory, trash)
            return True
        with patch('lyrics_studio.app.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes), patch('lyrics_studio.app.QFile.moveToTrash', side_effect=move):
            window.delete_project()
        self.assertEqual(window.table.rowCount(), 1)
        self.assertEqual(window.selected().info['id'], second.info['id'])
        self.assertFalse(first.directory.exists())
        self.assertTrue(self.audio.exists())
        window.close()

    def test_success_without_move_does_not_report_deleted(self):
        project = self.library.create('Keep', self.audio)
        with self.assertRaises(OSError):
            self.library.delete(project, lambda _: True)
        self.assertTrue(project.directory.exists())

    def test_failed_trash_never_falls_back_to_permanent_deletion(self):
        project = self.library.create('Keep', self.audio)
        with self.assertRaises(OSError):
            self.library.delete(project, lambda _: (False, ''))
        self.assertTrue(project.file.exists())

    def test_delete_rejects_outside_library_and_internal_original(self):
        outside = Library(self.root / 'other').create('Other', self.audio)
        with self.assertRaises(ValueError):
            self.library.delete(outside, lambda _: self.fail('must not delete'))
        project = self.library.create('Inside', self.audio)
        original = project.directory / 'original.wav'
        original.write_bytes(b'original')
        project.update(source_path=str(original))
        with self.assertRaises(ValueError):
            self.library.delete(project, lambda _: self.fail('must not delete'))

    def test_delete_cancel_then_confirm(self):
        project = self.library.create('Project', self.audio)
        window = Window(library=self.library.root, settings=self.settings)
        with patch('lyrics_studio.app.QMessageBox.question', return_value=QMessageBox.StandardButton.Cancel), patch.object(window.library, 'delete') as delete:
            window.delete_project()
            delete.assert_not_called()
        with patch('lyrics_studio.app.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes), patch.object(window.library, 'delete') as delete, patch.object(window.sessions, 'close_project') as close:
            window.delete_project()
            delete.assert_called_once()
            self.assertEqual(delete.call_args.args[0].info['id'], project.info['id'])
            close.assert_called_once()
        window.close()


if __name__ == '__main__':
    unittest.main()
