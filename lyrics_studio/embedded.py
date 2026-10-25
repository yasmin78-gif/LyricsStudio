"""Retained local editor views, with an asynchronous save bridge to the existing web UI."""
import json
import time
import uuid

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


class LocalEditorPage(QWebEnginePage):
    def __init__(self, origin, parent):
        super().__init__(parent)
        self.origin = QUrl(origin)

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        return (url.scheme() == self.origin.scheme() and url.host() == self.origin.host()
                and url.port() == self.origin.port())

    def createWindow(self, window_type):
        return None


class EditorView(QWebEngineView):
    def __init__(self, server, parent=None):
        super().__init__(parent)
        self.loaded = False
        self.pending = False
        self.origin = f'http://127.0.0.1:{server.server_port}'
        self.setPage(LocalEditorPage(self.origin, self))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setAcceptDrops(False)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        self.loadFinished.connect(self._loaded)
        self.load(QUrl(self.origin))

    def _loaded(self, success):
        self.loaded = success

    def pause(self):
        self.page().runJavaScript('window.lyricsDesktop?.pause();')

    def flush(self, save, callback):
        """Apply typed fields before saving; callback returns a structured success/error."""
        if not self.loaded:
            callback({'ok': False, 'error': 'Der Editor lädt noch. Bitte kurz warten.'})
            return
        if self.pending:
            callback({'ok': False, 'error': 'Der Editor speichert bereits. Bitte kurz warten.'})
            return
        self.pending = True
        request = uuid.uuid4().hex
        key = json.dumps(request)
        self.page().runJavaScript(
            f'window.__desktopResult=null;'
            f'if(window.lyricsDesktop){{window.lyricsDesktop.flush({str(save).lower()})'
            f'.then(result=>{{window.__desktopResult={{id:{key},...result}};}})'
            f'.catch(()=>{{window.__desktopResult={{id:{key},ok:false,error:"Speichern fehlgeschlagen."}};}});}}'
            f'else{{window.__desktopResult={{id:{key},ok:false,error:"Der Editor ist noch nicht bereit."}};}}')
        deadline = time.monotonic() + 15
        timer = QTimer(self)
        timer.setInterval(80)
        polling = False
        done = False

        def finish(result):
            nonlocal done
            if done:
                return
            done = True
            self.pending = False
            timer.stop()
            timer.deleteLater()
            callback(result)

        def received(raw):
            nonlocal polling
            if done:
                return
            polling = False
            result = json.loads(raw) if raw else None
            if result and result.get('id') == request:
                finish(result)
            elif time.monotonic() >= deadline:
                finish({'ok': False, 'error': 'Der Editor antwortet nicht. Deine Eingaben bleiben geöffnet.'})

        def poll():
            nonlocal polling
            if time.monotonic() >= deadline:
                finish({'ok': False, 'error': 'Der Editor antwortet nicht. Deine Eingaben bleiben geöffnet.'})
                return
            if not polling:
                polling = True
                self.page().runJavaScript('JSON.stringify(window.__desktopResult || null)', received)

        timer.timeout.connect(poll)
        timer.start()
