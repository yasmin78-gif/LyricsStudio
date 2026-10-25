import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import wave

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication
from lyrics_editor.store import Store, encoded
from lyrics_studio.app import NewProjectDialog, STYLE, Window
from lyrics_studio.exports import srt_document, srt_timestamp
from lyrics_studio.processing import Cancelled, make_document, parse_srt, prepare_project, run_process
from lyrics_studio.projects import Library, Project, project_lock
from lyrics_studio.sessions import Sessions


def synthetic_audio(path, duration=3):
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b'\0' * 64000 * duration)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audio = self.root / 'Song with spaces.wav'
        synthetic_audio(self.audio)
        self.library = Library(self.root / 'library')

    def ready_project(self):
        project = self.library.create('Synthetic project', self.audio, 'Example text')
        audio = project.path('audio.wav')
        shutil.copyfile(self.audio, audio)
        document = make_document(audio, [(0.2, 1.8, 'Synthetic passage')], 'Example text')
        document['audio']['path'] = 'audio.wav'
        project.data.write_bytes(encoded(document))
        project.update(status='ready', duration_seconds=3, source_count=1)
        return project

    def test_projects_reopen_separately_and_reject_path_escape(self):
        first = self.library.create('First', self.audio)
        second = self.library.create('Second', self.audio)
        self.assertNotEqual(first.directory, second.directory)
        self.assertEqual(len(self.library.list()[0]), 2)
        self.assertEqual(Project(first.directory).info['name'], 'First')
        with self.assertRaises(ValueError):
            first.path('../outside.json')

    def test_corrupt_project_does_not_hide_valid_projects(self):
        valid = self.library.create('Valid', self.audio)
        bad = self.library.root / 'broken'
        bad.mkdir()
        (bad / 'project.json').write_text('{}')
        projects, errors = self.library.list()
        self.assertEqual(projects[0].info['id'], valid.info['id'])
        self.assertEqual(len(errors), 1)

    def test_library_stays_outside_git(self):
        source = self.root / 'source'
        source.mkdir()
        (source / '.git').mkdir()
        with self.assertRaises(ValueError):
            Library(source / 'personal-projects')

    def test_portable_project_and_relative_audio_export(self):
        project = self.ready_project()
        store = Store(project.data, project.state_dir)
        store.act(dict(action='confirm', revision=store.revision, id=store.rows[0]['id'],
                       reviewer='Synthetic test', acknowledge=True))
        result = store.export(store.revision)
        self.assertEqual(len(Store(result['path'], project.path('reimport')).rows), 1)
        moved = self.root / 'moved-project'
        shutil.move(project.directory, moved)
        reopened = Store(moved / 'lyrics_timing.json', moved / 'editor-state')
        self.assertEqual(reopened.audio, moved / 'audio.wav')
        self.assertEqual(reopened.document()['confirmed_occurrences'][0]['text'], 'Synthetic passage')

    def test_session_switch_preserves_work_and_restart_restores_saved_draft(self):
        project = self.ready_project()
        sessions = Sessions()
        self.addCleanup(sessions.close)
        first = sessions.open(project)
        first.store.act(dict(action='update', revision=first.store.revision, id=first.store.rows[0]['id'],
                             text='Edited synthetic text', start=0.3, end=1.7))
        self.assertIs(sessions.open(project), first)
        self.assertEqual(len(sessions.dirty()), 1)
        conn = http.client.HTTPConnection('127.0.0.1', first.server_port, timeout=3)
        conn.request('GET', '/api/state')
        state = json.loads(conn.getresponse().read())
        conn.close()
        self.assertEqual(state['rows'][0]['text'], 'Edited synthetic text')
        sessions.save_all()
        sessions.close()
        self.assertEqual(sessions.open(project).store.rows[0]['text'], 'Edited synthetic text')

    def test_project_lock_and_failed_processing_preserve_original(self):
        project = self.library.create('Failure', self.audio)
        before = self.audio.read_bytes()
        with project_lock(project.directory):
            with self.assertRaises(ValueError):
                with project_lock(project.directory):
                    pass
        with self.assertRaises(ValueError):
            prepare_project(project, {'ffmpeg': 'missing-lyrics-studio-ffmpeg'})
        self.assertEqual(Project(project.directory).info['status'], 'error')
        self.assertEqual(self.audio.read_bytes(), before)
        self.assertFalse(project.data.exists())

    def test_cancel_terminates_child_process(self):
        cancel = threading.Event()
        timer = threading.Timer(0.25, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        with self.assertRaises(Cancelled):
            run_process([sys.executable, '-c', 'import time; time.sleep(30)'],
                        self.root, cancel, lambda *_: None, 'Test')
        self.assertLess(time.monotonic() - started, 5)

    def test_srt_uses_only_confirmed_rows_and_applies_offset(self):
        project = self.ready_project()
        store = Store(project.data, project.state_dir)
        with self.assertRaises(ValueError):
            srt_document(store.document())
        store.act(dict(action='confirm', revision=store.revision, id=store.rows[0]['id'],
                       reviewer='Synthetic test', acknowledge=True))
        text = srt_document(store.document(), 10)
        self.assertIn('00:00:10,200 --> 00:00:11,800', text)
        self.assertIn('Synthetic passage', text)
        self.assertEqual(srt_timestamp(59.9996), '00:01:00,000')
        with self.assertRaises(ValueError):
            srt_document(store.document(), float('nan'))

    def test_srt_parser_rejects_invalid_timing(self):
        self.assertEqual(parse_srt('1\n00:00:00,200 --> 00:00:01,800\nTest\n', 3), [(0.2, 1.8, 'Test')])
        for text in ['1\n00:00:02,000 --> 00:00:01,000\nText', 'bad output', '1\n00:99:00,000 --> 01:00:00,000\nText']:
            with self.assertRaises(ValueError):
                parse_srt(text, 3)


class DesktopTests(unittest.TestCase):
    setUp = ProjectTests.setUp
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.app.setStyleSheet(STYLE)

    def test_window_drop_routes_local_audio_to_project_dialog(self):
        settings = QSettings(str(self.root / 'settings.ini'), QSettings.Format.IniFormat)
        window = Window(self.library.root, settings)
        window.show()
        self.addCleanup(window.close)
        self.app.processEvents()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.audio))])
        drag = QDragEnterEvent(QPoint(50, 100), Qt.DropAction.CopyAction, mime,
                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.dragEnterEvent(drag)
        self.assertTrue(drag.isAccepted())
        with patch.object(window, 'new_project') as create:
            drop = QDropEvent(QPointF(50, 100), Qt.DropAction.CopyAction, mime,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            window.dropEvent(drop)
            self.app.processEvents()
            create.assert_called_once_with(audio=self.audio)
        mime.setUrls([QUrl('https://example.com/song.mp3')])
        self.assertIsNone(window.drop_audio(mime))
        mime.setUrls([QUrl.fromLocalFile(str(self.audio)), QUrl.fromLocalFile(str(self.audio))])
        self.assertIsNone(window.drop_audio(mime))

    def test_new_dialog_prefills_dropped_song(self):
        dialog = NewProjectDialog(None, self.audio)
        self.assertEqual(dialog.name.text(), 'Song with spaces')
        self.assertEqual(dialog.audio.text(), str(self.audio))
        dialog.validate_input()
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)


if __name__ == '__main__':
    unittest.main()
