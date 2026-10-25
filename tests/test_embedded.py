import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu --log-level=3')
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from PySide6.QtCore import QEvent, QCoreApplication, QEventLoop, QSettings, QTimer, QUrl, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from lyrics_editor.store import encoded
from lyrics_studio.app import Window
from lyrics_studio.processing import make_document
from lyrics_studio.projects import Library


def javascript(page, expression):
    result = []
    loop = QEventLoop()
    page.runJavaScript(expression, lambda value: (result.append(value), loop.quit()))
    QTimer.singleShot(4000, loop.quit)
    loop.exec()
    if not result:
        raise AssertionError('JavaScript antwortet nicht.')
    return result[0]


def wait_for(condition):
    for _ in range(100):
        if condition():
            return
        QTest.qWait(50)
    raise AssertionError('Editor wurde nicht rechtzeitig bereit.')


class EmbeddedEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        audio = self.root / 'synthetic.wav'
        with wave.open(str(audio), 'wb') as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b'\0' * 64000 * 3)
        library = Library(self.root / 'projects')
        self.projects = []
        for name in ('Projekt A', 'Projekt B'):
            project = library.create(name, audio)
            target = project.path('audio.wav')
            target.write_bytes(audio.read_bytes())
            doc = make_document(target, [(0.2, 1.8, 'Synthetische Passage')])
            doc['audio']['path'] = 'audio.wav'
            project.data.write_bytes(encoded(doc))
            project.update(status='ready')
            self.projects.append(project)
        settings = QSettings(str(self.root / 'settings.ini'), QSettings.Format.IniFormat)
        self.window = Window(library.root, settings)
        self.window.show()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.window.dispose_editors()
        self.window.sessions.close()
        self.window.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.temp.cleanup()

    def open_project(self, index=0):
        project = self.projects[index]
        for row in range(self.window.table.rowCount()):
            if self.window.table.item(row, 0).data(Qt.ItemDataRole.UserRole).info['id'] == project.info['id']:
                self.window.table.selectRow(row)
                break
        self.window.open_editor()
        view = self.window.editor_views[str(project.directory)]
        wait_for(lambda: view.loaded and javascript(view.page(), "!!document.querySelector('.lyric-row')"))
        return view

    def type_text(self, view, text):
        javascript(view.page(), f"document.getElementById('text').value={json.dumps(text)};document.getElementById('text').dispatchEvent(new Event('input',{{bubbles:true}}));")

    def test_opens_inside_window_without_external_browser(self):
        with patch('lyrics_studio.app.QDesktopServices.openUrl') as external:
            view = self.open_project()
            external.assert_not_called()
        self.assertIs(self.window.pages.currentWidget(), self.window.editor_page)
        self.assertFalse(view.page().acceptNavigationRequest(QUrl('https://example.com'), 0, True))
        self.assertEqual(javascript(view.page(), "document.getElementById('songTitle').textContent"), 'Projekt A')
        for control in ('save', 'export', 'statePath'):
            self.assertEqual(javascript(view.page(), f"getComputedStyle(document.getElementById('{control}')).display"), 'none')
        self.assertEqual(javascript(view.page(), "document.getElementById('reload').textContent"), 'Änderungen verwerfen')

    def test_project_switch_preserves_unsubmitted_text_and_view(self):
        first = self.open_project()
        self.type_text(first, 'Noch nicht übernommen')
        self.window.show_overview()
        second = self.open_project(1)
        self.assertIsNot(first, second)
        self.window.show_overview()
        self.assertIs(self.open_project(), first)
        self.assertEqual(javascript(first.page(), "document.getElementById('text').value"), 'Noch nicht übernommen')

    def test_desktop_save_applies_pending_form_fields(self):
        view = self.open_project()
        self.type_text(view, 'Vom Desktop gespeichert')
        self.window.save_active_editor()
        wait_for(lambda: not self.window.editor_operation)
        draft = json.loads(self.projects[0].path('editor-state/lyrics_editor_draft.json').read_text(encoding='utf-8'))
        self.assertEqual(draft['rows'][0]['text'], 'Vom Desktop gespeichert')
        self.assertEqual(draft['rows'][0]['status'], 'editing')

    def test_invalid_input_is_preserved_and_blocks_save(self):
        view = self.open_project()
        javascript(view.page(), "document.getElementById('start').value='2';document.getElementById('start').dispatchEvent(new Event('input',{bubbles:true}));")
        results = []
        view.flush(True, results.append)
        wait_for(lambda: bool(results))
        self.assertFalse(results[0]['ok'])
        self.assertEqual(javascript(view.page(), "document.getElementById('start').value"), '2')
        self.assertFalse(self.projects[0].path('editor-state/lyrics_editor_draft.json').exists())

    def test_discard_requires_confirmation_and_restores_saved_fields(self):
        view = self.open_project()
        self.type_text(view, 'Gespeicherter Text')
        self.window.save_active_editor()
        wait_for(lambda: not self.window.editor_operation)
        self.type_text(view, 'Nicht gespeicherter Text')
        javascript(view.page(), "window.confirm=()=>false;document.getElementById('reload').click();")
        QTest.qWait(150)
        self.assertEqual(javascript(view.page(), "document.getElementById('text').value"), 'Nicht gespeicherter Text')
        javascript(view.page(), "window.confirm=()=>true;document.getElementById('reload').click();")
        wait_for(lambda: javascript(view.page(), "document.getElementById('text').value") == 'Gespeicherter Text')
        self.assertTrue(javascript(view.page(), "document.getElementById('reload').disabled"))

    def test_export_first_saves_typed_editor_changes(self):
        view = self.open_project()
        self.type_text(view, 'Vor Export übernommen')
        with patch.object(self.window, '_export_srt') as export:
            self.window.export_srt()
            wait_for(lambda: not self.window.editor_operation)
            export.assert_called_once()
        server, _ = self.window.sessions.servers[str(self.projects[0].directory)]
        self.assertEqual(server.store.rows[0]['text'], 'Vor Export übernommen')

    def test_close_saves_pending_inputs_from_all_open_projects(self):
        for index in range(2):
            view = self.open_project(index)
            self.type_text(view, f'Gespeichertes Projekt {index}')
            self.window.show_overview()
        with patch('lyrics_studio.app.QMessageBox.question', return_value=QMessageBox.StandardButton.Save):
            self.window.close()
            wait_for(lambda: not self.window.isVisible())
        for index, project in enumerate(self.projects):
            draft = json.loads(project.path('editor-state/lyrics_editor_draft.json').read_text(encoding='utf-8'))
            self.assertEqual(draft['rows'][0]['text'], f'Gespeichertes Projekt {index}')


if __name__ == '__main__':
    unittest.main()
