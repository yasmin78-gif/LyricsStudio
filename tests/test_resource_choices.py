import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QComboBox, QDialog
from lyrics_studio.app import SettingsDialog, Window
from lyrics_studio.settings_paths import ffmpeg_candidates, model_candidates, resource_name


class ResourceChoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.settings = QSettings(str(self.root / 'settings.ini'), QSettings.Format.IniFormat)
        self.ffmpeg = self.root / 'ffmpeg-9.0.2' / 'bin' / 'ffmpeg.exe'
        self.ffmpeg.parent.mkdir(parents=True)
        self.ffmpeg.write_bytes(b'synthetic executable')
        self.model = self.root / 'ggml-large-v3.bin'
        self.model.write_bytes(b'synthetic model')

    def dialog(self, ffmpeg=None, models=None):
        with patch('lyrics_studio.app.ffmpeg_candidates', return_value=ffmpeg if ffmpeg is not None else [self.ffmpeg]), \
             patch('lyrics_studio.app.model_candidates', return_value=models if models is not None else [self.model]):
            dialog = SettingsDialog(self.settings, None)
        self.addCleanup(dialog.close)
        return dialog

    def test_lists_preselect_available_resources_without_paths(self):
        dialog = self.dialog()
        for combo, path in [(dialog.ffmpeg, self.ffmpeg), (dialog.model, self.model)]:
            self.assertIsInstance(combo, QComboBox)
            self.assertFalse(combo.isEditable())
            self.assertEqual(combo.currentData(), str(path))
            self.assertNotIn(str(self.root), combo.currentText())
            self.assertEqual(combo.toolTip(), str(path))
        self.assertTrue(dialog.save_control.isEnabled())
        self.assertFalse(dialog.advanced.isChecked())
        dialog.accept_selection()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_saved_selection_is_preserved_among_multiple_choices(self):
        second = self.root / 'ggml-small.bin'
        second.write_bytes(b'synthetic')
        self.settings.setValue('model', str(second))
        dialog = self.dialog(models=[self.model, second])
        self.assertEqual(dialog.model.currentData(), str(second))
        dialog.model.setCurrentIndex(0)
        with patch('lyrics_studio.app.ffmpeg_candidates', return_value=[self.ffmpeg]), \
             patch('lyrics_studio.app.model_candidates', return_value=[self.model, second]):
            dialog.refresh_choices()
        self.assertEqual(dialog.model.currentData(), str(self.model))

    def test_missing_resources_are_explicit_and_cannot_be_saved(self):
        dialog = self.dialog(ffmpeg=[], models=[])
        self.assertFalse(dialog.ffmpeg.isEnabled())
        self.assertFalse(dialog.model.isEnabled())
        self.assertFalse(dialog.save_control.isEnabled())
        self.assertIn('Kein', dialog.availability.text())
        self.assertFalse(dialog.ffmpeg.currentData())
        dialog.accept_selection()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_disappearing_selected_file_does_not_save_stale_path(self):
        dialog = self.dialog()
        self.model.unlink()
        dialog.accept_selection()
        self.assertFalse(dialog.save_control.isEnabled())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_manual_add_becomes_selected_and_remembered(self):
        second = self.root / 'ggml-small.bin'
        second.write_bytes(b'synthetic')
        dialog = self.dialog()
        with patch('lyrics_studio.app.QFileDialog.getOpenFileName', return_value=(str(second), '')), \
             patch('lyrics_studio.app.model_candidates', return_value=[second, self.model]):
            dialog.add_resource(True)
        self.assertEqual(dialog.model.currentData(), str(second))
        self.assertIn(str(second), dialog.known_models)

    def test_window_saves_selected_paths_in_existing_settings_keys(self):
        dialog = self.dialog()
        dialog.known_models = [str(self.model)]
        window = Window(self.root / 'projects', self.settings)
        self.addCleanup(window.close)
        with patch('lyrics_studio.app.SettingsDialog', return_value=dialog), \
             patch.object(dialog, 'exec', return_value=QDialog.DialogCode.Accepted):
            window.configure()
        self.assertEqual(self.settings.value('ffmpeg'), str(self.ffmpeg))
        self.assertEqual(self.settings.value('model'), str(self.model))
        self.assertEqual(self.settings.value('model_locations', [], type=list), [str(self.model)])

    def test_discovery_keeps_saved_and_extra_locations_and_deduplicates(self):
        with patch('lyrics_studio.settings_paths.shutil.which', return_value=str(self.ffmpeg)), \
             patch('lyrics_studio.settings_paths.os.get_exec_path', return_value=[]):
            choices = ffmpeg_candidates(str(self.ffmpeg), [str(self.ffmpeg)])
        self.assertEqual(choices, [self.ffmpeg])
        self.assertIn(self.model, model_candidates('', [str(self.model)]))
        self.assertEqual(resource_name(self.ffmpeg), 'FFmpeg 9.0.2')
        self.assertIn('Large V3', resource_name(self.model, model=True))


if __name__ == '__main__':
    unittest.main()
