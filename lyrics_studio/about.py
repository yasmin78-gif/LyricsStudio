"""Application information in the desktop's existing visual style."""
import platform
import struct
import sys

import PySide6
from PySide6.QtCore import Qt, QSysInfo, QUrl, qVersion
from PySide6.QtGui import QDesktopServices, QFontDatabase
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from . import __version__
from .branding import application_icon
from .legal_info import show_legal


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Info über Lyrics Studio')
        self.setWindowIcon(application_icon())
        self.resize(560, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(application_icon().pixmap(76, 76))
        icon.setFixedSize(84, 84)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.addWidget(icon)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel('Lyrics Studio')
        title.setStyleSheet('font-size: 27px; font-weight: 700;')
        title_box.addWidget(title)
        title_box.addWidget(QLabel(f'Version {__version__}'))
        heading.addLayout(title_box, 1)
        layout.addLayout(heading)
        description = QLabel('Songtexte hören, korrigieren und mit präzisem Timing exportieren.\nDeine Songs. Dein Timing. Dein Projekt.')
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addSpacing(8)
        copyright_box = QVBoxLayout()
        copyright_box.setSpacing(4)
        copyright_box.addWidget(QLabel('Copyright © 2026 Yasmin Mahr'))
        copyright_box.addWidget(QLabel('Eigener Quellcode: MIT-Lizenz'))
        layout.addLayout(copyright_box)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet('color: #36425a;')
        layout.addWidget(separator)
        caption = QLabel('Technische Informationen')
        caption.setStyleSheet('font-weight: 700;')
        layout.addWidget(caption)
        operating_system = QSysInfo.prettyProductName()
        if sys.platform == 'win32':
            operating_system += f' (Build {sys.getwindowsversion().build})'
        details = QLabel('\n'.join([
            f'Python:         {platform.python_version()}',
            f'Qt / PySide6:   {qVersion()} / {PySide6.__version__}',
            f'Betriebssystem: {operating_system}',
            f'Architektur:    {QSysInfo.currentCpuArchitecture()}',
            f'Prozess:        {struct.calcsize("P") * 8}-Bit',
            f'Ausführung:     {"Desktop-Paket" if getattr(sys, "frozen", False) else "Aus Quellcode"}',
        ]))
        details.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details.setWordWrap(True)
        layout.addWidget(details)
        layout.addStretch()
        links = QHBoxLayout()
        project = QPushButton('Projekt auf GitHub ↗')
        project.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://github.com/yasmin78-gif/LyricsStudio')))
        links.addWidget(project)
        licenses = QPushButton('Lizenzen und Datenschutz')
        licenses.clicked.connect(lambda: show_legal(self))
        links.addWidget(licenses)
        layout.addLayout(links)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        controls.button(QDialogButtonBox.StandardButton.Close).setText('Schließen')
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
