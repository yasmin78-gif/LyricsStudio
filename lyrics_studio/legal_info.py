"""Visible notices and upstream download links; no external tools are bundled."""
from pathlib import Path
import sys
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QTextBrowser, QVBoxLayout

FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/'
MODEL_URL = 'https://huggingface.co/ggerganov/whisper.cpp/tree/main'


def legal_directory():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'legal'


def show_legal(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle('Lyrics Studio · Lizenzen und Datenschutz')
    dialog.resize(840, 640)
    layout = QVBoxLayout(dialog)
    tabs = QTabWidget()
    pending = {}
    for title, filename in [('Hinweise', 'THIRD_PARTY.md'), ('Datenschutz', 'PRIVACY.md'),
                            ('LGPLv3', 'LGPL-3.0.txt'), ('GPLv3', 'GPL-3.0.txt'),
                            ('Chromium', 'chromium-credits.html')]:
        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.anchorClicked.connect(lambda url: QDesktopServices.openUrl(url) if url.scheme() == 'https' else None)
        path = legal_directory() / filename
        pending[tabs.addTab(view, title)] = (view, path)
    def load_tab(index):
        item = pending.pop(index, None)
        if item is None:
            return
        view, path = item
        if not path.exists():
            view.setPlainText('Die Lizenzdatei fehlt in dieser Installation: ' + path.name)
            return
        text = path.read_text(encoding='utf-8', errors='replace')
        if path.suffix == '.md':
            view.setMarkdown(text)
        elif path.suffix == '.html':
            view.setHtml(text)
        else:
            view.setPlainText(text)
    tabs.currentChanged.connect(load_tab)
    load_tab(0)
    layout.addWidget(tabs)
    controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    controls.rejected.connect(dialog.reject)
    layout.addWidget(controls)
    dialog.exec()
