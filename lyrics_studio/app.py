"""Native desktop shell. The existing editor stays in the user's browser."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import threading

from PySide6.QtCore import QFile, QSettings, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    QAbstractItemView, QHeaderView, QLayout, QGroupBox, QStackedWidget,
)

from lyrics_editor.store import atomic_write
from .exports import srt_document
from .processing import Cancelled, prepare_project
from .projects import AUDIO_EXTENSIONS, Library, Project, default_library
from .sessions import Sessions
from . import __version__
from .updates import check_for_updates
from .branding import application_icon, set_taskbar_identity
from .embedded import EditorView
from .resolve_export import export_package, lua_string
from .legal_info import FFMPEG_URL, MODEL_URL
from .about import AboutDialog
from .settings_paths import chooser_start, existing_file, model_candidates, ffmpeg_candidates, resource_name

STATUS = {'new': 'Neu', 'processing': 'Verarbeitung unterbrochen', 'ready': 'Bereit zur Bearbeitung',
          'error': 'Vorbereitung fehlgeschlagen', 'cancelled': 'Abgebrochen'}
LANGUAGES = [('Automatisch erkennen', 'auto'), ('Deutsch', 'de'), ('Englisch', 'en'),
             ('Französisch', 'fr'), ('Spanisch', 'es'), ('Italienisch', 'it'),
             ('Portugiesisch', 'pt'), ('Niederländisch', 'nl'), ('Polnisch', 'pl')]
AUDIO_FILTER = 'Audiodateien (' + ' '.join('*' + ext for ext in sorted(AUDIO_EXTENSIONS)) + ')'

STYLE = '''
QWidget { font-family: "Segoe UI", "Arial"; font-size: 14px; color: #e5e9f2; }
QMainWindow, QDialog { background: #10141e; }
QLabel#brand { font-size: 27px; font-weight: 700; }
QLabel#eyebrow { color: #81d8c6; font-size: 11px; font-weight: 700; }
QLabel#muted { color: #a0aabd; }
QLabel#heading { font-size: 23px; font-weight: 600; }
QFrame#panel { background: #191f2d; border: 1px solid #2b3447; border-radius: 12px; }
QPushButton { background: #252e40; border: 1px solid #3a465e; border-radius: 7px; padding: 10px 15px; }
QPushButton:hover { background: #32405a; border-color: #74cbbb; }
QPushButton:disabled { color: #768196; background: #1a2130; border-color: #293247; }
QPushButton#primary { color: #0b2521; background: #87decb; border-color: #87decb; font-weight: 700; }
QPushButton#primary:hover { background: #a1ecdd; }
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDoubleSpinBox {
 background: #101622; border: 1px solid #36425a; border-radius: 6px; padding: 8px; selection-background-color: #386b69;
}
QComboBox QAbstractItemView { background: #202a3d; selection-background-color: #386b69; }
QTableWidget { background: #191f2d; alternate-background-color: #1d2534; border: 0; gridline-color: #2b3447; }
QTableWidget::item { padding: 9px; }
QTableWidget::item:selected { background: #294d4c; color: #edfff8; }
QHeaderView::section { background: #202839; color: #aeb9cd; padding: 12px; border: 0; }
QProgressBar { border: 1px solid #36425a; border-radius: 6px; background: #101622; text-align: center; min-height: 18px; }
QProgressBar::chunk { background: #72cbb8; border-radius: 5px; }
QSplitter::handle { background: #10141e; width: 14px; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: #191f2d; }
QCheckBox { spacing: 9px; }
'''


def label(text, name=None):
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        item.setObjectName(name)
    item.setWordWrap(True)
    return item


def button(text, callback=None, primary=False):
    item = QPushButton(text)
    item.setMinimumHeight(40)
    if callback:
        item.clicked.connect(callback)
    if primary:
        item.setObjectName('primary')
    return item


def choose_file(parent, field, title, file_filter, executable=False):
    models = model_candidates(field.text()) if not executable else []
    fallback = models[0].parent if models else None
    start = chooser_start(field.text(), executable=executable, fallback=fallback)
    path, _ = QFileDialog.getOpenFileName(parent, title, start, file_filter)
    if path:
        field.setText(path)


def file_row(parent, field, title, file_filter, executable=False):
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(field, 1)
    layout.addWidget(button('Auswählen …', lambda: choose_file(parent, field, title, file_filter, executable)))
    return row


class SettingsDialog(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle('Lyrics Studio · Einstellungen')
        self.resize(680, 440)
        layout = QVBoxLayout(self)
        layout.addWidget(label('Lokale Spracherkennung', 'heading'))
        layout.addWidget(label('Wähle aus, welche lokale Audio-Verarbeitung und welches Whisper-Modell du verwenden möchtest.', 'muted'))
        form = QFormLayout()
        self.ffmpeg = QComboBox()
        self.model = QComboBox()
        self.ffmpeg.setMinimumWidth(320)
        self.model.setMinimumWidth(320)
        self.preferred_ffmpeg = settings.value('ffmpeg', 'ffmpeg')
        self.preferred_model = settings.value('model', os.environ.get('LYRICS_STUDIO_MODEL', ''))
        self.known_ffmpeg = settings.value('ffmpeg_locations', [], type=list)
        self.known_models = settings.value('model_locations', [], type=list)
        self.gpu = QCheckBox('Grafikkarte verwenden')
        self.gpu.setChecked(settings.value('gpu', True, type=bool))
        self.startup_updates = QCheckBox('Beim Programmstart nach Updates suchen')
        self.startup_updates.setChecked(settings.value('check_updates_startup', True, type=bool))
        form.addRow('Audio-Verarbeitung', self.ffmpeg)
        form.addRow('Whisper-Modell', self.model)
        form.addRow('', self.gpu)
        layout.addLayout(form)
        self.availability = label('', 'muted')
        layout.addWidget(self.availability)
        layout.addWidget(button('Erneut nach verfügbaren Einträgen suchen', self.refresh_choices))
        downloads = QHBoxLayout()
        downloads.addWidget(button('FFmpeg herunterladen ↗', lambda: QDesktopServices.openUrl(QUrl(FFMPEG_URL))))
        downloads.addWidget(button('Whisper-Modell herunterladen ↗', lambda: QDesktopServices.openUrl(QUrl(MODEL_URL))))
        layout.addLayout(downloads)
        layout.addWidget(label('Externe Downloads: FFmpeg mit Whisper-Filter (Windows: Full Build) und ein GGML-Modell als .bin wählen. Heruntergeladene Archive entpacken, dann erneut suchen oder die Dateien hinzufügen. Diese Komponenten werden nicht mitgeliefert.', 'muted'))
        self.advanced = QGroupBox('Weitere Installation hinzufügen')
        self.advanced.setCheckable(True)
        advanced_layout = QVBoxLayout(self.advanced)
        self.advanced_content = QWidget()
        additions = QVBoxLayout(self.advanced_content)
        additions.setContentsMargins(0, 0, 0, 0)
        additions.addWidget(label('Falls eine Installation an einem anderen Ort liegt, kannst du sie einmalig zur Auswahl hinzufügen.', 'muted'))
        additions.addWidget(button('FFmpeg-Version hinzufügen …', lambda: self.add_resource(False)))
        additions.addWidget(button('Whisper-Modell hinzufügen …', lambda: self.add_resource(True)))
        advanced_layout.addWidget(self.advanced_content)
        self.advanced.toggled.connect(self.advanced_content.setVisible)
        self.advanced.setChecked(False)
        layout.addWidget(self.advanced)
        layout.addWidget(label('Die Auswahl gilt für alle Projekte. Deine Songs bleiben auf diesem Rechner.', 'muted'))
        layout.addWidget(self.startup_updates)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Save).setText('Speichern')
        controls.button(QDialogButtonBox.StandardButton.Cancel).setText('Abbrechen')
        self.save_control = controls.button(QDialogButtonBox.StandardButton.Save)
        controls.accepted.connect(self.accept_selection)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
        self.ffmpeg.currentIndexChanged.connect(self.update_availability)
        self.model.currentIndexChanged.connect(self.update_availability)
        self.refresh_choices()

    def populate_choice(self, combo, paths, preferred, model=False):
        combo.blockSignals(True)
        combo.clear()
        resolved = existing_file(preferred, executable=not model)
        names = [resource_name(path, model) for path in paths]
        for number, (path, name) in enumerate(zip(paths, names), 1):
            if names.count(name) > 1:
                name += f' · Installation {number}'
            combo.addItem(name, str(path))
            combo.setItemData(combo.count() - 1, str(path), Qt.ItemDataRole.ToolTipRole)
        if not paths:
            combo.addItem('Kein Whisper-Modell gefunden' if model else 'Kein FFmpeg gefunden', '')
        selected = combo.findData(str(resolved)) if resolved else -1
        combo.setCurrentIndex(selected if selected >= 0 else 0)
        combo.setEnabled(bool(paths))
        combo.blockSignals(False)

    def refresh_choices(self):
        ffmpeg = self.ffmpeg.currentData() or self.preferred_ffmpeg
        model = self.model.currentData() or self.preferred_model
        self.populate_choice(self.ffmpeg, ffmpeg_candidates(ffmpeg, self.known_ffmpeg), ffmpeg)
        self.populate_choice(self.model, model_candidates(model, self.known_models), model, model=True)
        self.update_availability()

    def update_availability(self, *_):
        missing = []
        if not self.ffmpeg.currentData():
            missing.append('Keine lokale Audio-Verarbeitung gefunden.')
        if not self.model.currentData():
            missing.append('Noch kein Whisper-Modell gefunden.')
        self.availability.setText(' '.join(missing) + ' Füge eine vorhandene Installation hinzu.' if missing
                                  else 'Vorhandene Einträge sind ausgewählt. Du kannst die Auswahl direkt speichern.')
        self.save_control.setEnabled(not missing)
        for combo in (self.ffmpeg, self.model):
            combo.setToolTip(combo.currentData() or '')

    def add_resource(self, model):
        combo = self.model if model else self.ffmpeg
        start = chooser_start(combo.currentData(), executable=not model)
        title = 'Whisper-Modell hinzufügen' if model else 'FFmpeg-Version hinzufügen'
        file_filter = 'Whisper-Modelle (*.bin)' if model else 'FFmpeg (ffmpeg.exe ffmpeg);;Programme (*)'
        path, _ = QFileDialog.getOpenFileName(self, title, start, file_filter)
        if not path:
            return
        found = existing_file(path, executable=not model)
        if not found or model and found.suffix.lower() != '.bin':
            self.availability.setText('Diese Datei ist nicht verfügbar. Bitte eine vorhandene Installation auswählen.')
            return
        if model:
            self.preferred_model = str(found)
            self.known_models.append(str(found))
        else:
            self.preferred_ffmpeg = str(found)
            self.known_ffmpeg.append(str(found))
        # Use the newly added file even when another entry was selected before.
        paths = model_candidates(str(found), self.known_models) if model else ffmpeg_candidates(str(found), self.known_ffmpeg)
        self.populate_choice(combo, paths, str(found), model=model)
        self.update_availability()

    def accept_selection(self):
        if not existing_file(self.ffmpeg.currentData(), executable=True) or not existing_file(self.model.currentData()):
            self.availability.setText('Ein ausgewählter Eintrag ist nicht mehr vorhanden. Bitte erneut suchen.')
            self.save_control.setEnabled(False)
            return
        self.accept()


class NewProjectDialog(QDialog):
    def __init__(self, parent, audio=None):
        super().__init__(parent)
        self.setWindowTitle('Neues Lyrics-Projekt')
        self.resize(700, 530)
        layout = QVBoxLayout(self)
        layout.addWidget(label('Ein neuer Song. Ein neues Projekt.', 'heading'))
        layout.addWidget(label('Der Song wird als eigene Arbeitskopie vorbereitet. Deine Originaldatei bleibt erhalten.', 'muted'))
        form = QFormLayout()
        self.name = QLineEdit(Path(audio).stem if audio else '')
        self.name.setMaxLength(120)
        self.name.setPlaceholderText('Projektname')
        self.audio = QLineEdit(str(audio) if audio else '')
        self.audio.setPlaceholderText('WAV, MP3, FLAC oder andere Audiodatei')
        self.audio.textChanged.connect(self.suggest_name)
        self.language = QComboBox()
        for text, code in LANGUAGES:
            self.language.addItem(text, code)
        form.addRow('Projektname', self.name)
        form.addRow('Song', file_row(self, self.audio, 'Song auswählen', AUDIO_FILTER))
        form.addRow('Sprache', self.language)
        layout.addLayout(form)
        layout.addWidget(label('Vorhandener Liedtext · optional'))
        self.reference = QPlainTextEdit()
        self.reference.setPlaceholderText('Liedtext hier einfügen. Er bleibt als Referenz erhalten; Whisper erkennt den tatsächlichen Gesang unabhängig davon.')
        layout.addWidget(self.reference, 1)
        layout.addWidget(button('Liedtext aus TXT laden …', self.load_reference))
        self.error = label('', 'muted')
        layout.addWidget(self.error)
        controls = QDialogButtonBox()
        controls.addButton('Abbrechen', QDialogButtonBox.ButtonRole.RejectRole)
        controls.addButton('Projekt anlegen', QDialogButtonBox.ButtonRole.AcceptRole).setObjectName('primary')
        controls.accepted.connect(self.validate_input)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

    def suggest_name(self):
        if not self.name.text().strip() and self.audio.text():
            self.name.setText(Path(self.audio.text()).stem)

    def load_reference(self):
        file, _ = QFileDialog.getOpenFileName(self, 'Liedtext laden', '', 'Textdateien (*.txt)')
        if file:
            try:
                self.reference.setPlainText(Path(file).read_text(encoding='utf-8-sig'))
            except (OSError, UnicodeError) as exc:
                self.error.setText(f'Der Liedtext konnte nicht geladen werden: {exc}')

    def validate_input(self):
        source = Path(self.audio.text())
        if not self.name.text().strip():
            self.error.setText('Bitte einen Projektnamen eingeben.')
        elif not source.is_file() or source.suffix.lower() not in AUDIO_EXTENSIONS:
            self.error.setText('Bitte eine unterstützte Audiodatei auswählen.')
        else:
            self.accept()


class ImportWorker(QThread):
    progress = Signal(str, int)
    completed = Signal(str, bool)

    def __init__(self, project, settings, parent):
        super().__init__(parent)
        self.project = project
        self.settings = settings
        self.cancel = threading.Event()

    def run(self):
        try:
            prepare_project(self.project, self.settings, self.cancel, self.progress.emit)
            self.completed.emit('Der Song ist vorbereitet. Öffne Lyrics Studio, um Text und Zeiten zu prüfen.', True)
        except Cancelled:
            self.completed.emit('Die Verarbeitung wurde abgebrochen. Du kannst sie später erneut starten.', False)
        except Exception as exc:
            self.completed.emit(str(exc), False)


class UpdateWorker(QThread):
    completed = Signal(object)

    def run(self):
        self.completed.emit(check_for_updates())


class TitleExportWorker(QThread):
    progress = Signal(str, int)
    completed = Signal(str, bool)

    def __init__(self, project, document, audio, parent_directory, options, parent):
        super().__init__(parent)
        self.project = project
        self.document = document
        self.audio = audio
        self.parent_directory = parent_directory
        self.options = options
        self.cancel = threading.Event()
        self.output = None

    def run(self):
        try:
            self.output = export_package(self.document, self.project.info['name'], self.audio,
                self.parent_directory, cancel=self.cancel, report=self.progress.emit, **self.options)
            self.completed.emit('DaVinci-Titelpaket erstellt: ' + str(self.output), True)
        except Cancelled:
            self.completed.emit('DaVinci-Export abgebrochen.', False)
        except Exception as exc:
            self.completed.emit(str(exc), False)


class Window(QMainWindow):
    def __init__(self, library=None, settings=None, start_updates=False):
        super().__init__()
        self.settings = settings if settings is not None else QSettings('LyricsStudio', 'Desktop')
        self.library = Library(library or self.settings.value('library', str(default_library())))
        self.sessions = Sessions()
        self.worker = None
        self.processing_id = None
        self.update_worker = None
        self.update_url = ''
        self.close_after_update = False
        self.editor_views = {}
        self.active_editor_key = None
        self.editor_operation = False
        self.close_after_save = False
        self.projects = []
        self.setWindowTitle(f'Lyrics Studio {__version__} · Projekte')
        self.setWindowIcon(application_icon())
        self.resize(1180, 780)
        self.setMinimumSize(900, 640)
        self.setAcceptDrops(True)
        root = QWidget()
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self.overview = root
        self.pages.addWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(30, 26, 30, 20)
        layout.setSpacing(20)
        header = QHBoxLayout()
        brand = QVBoxLayout()
        brand_heading = QHBoxLayout()
        brand_heading.addWidget(label('≋  Lyrics Studio', 'brand'))
        brand_heading.addWidget(label(f'v{__version__}', 'muted'))
        brand_heading.addStretch()
        brand.addLayout(brand_heading)
        brand.addWidget(label('Deine Songs. Dein Timing. Dein Projekt.', 'muted'))
        header.addLayout(brand, 1)
        local_badge = label('●  Lokal auf deinem Rechner', 'muted')
        local_badge.setMinimumWidth(200)
        header.addWidget(local_badge)
        header.addWidget(button('Einstellungen', self.configure))
        header.addWidget(button('Über Lyrics Studio', lambda: AboutDialog(self).exec()))
        layout.addLayout(header)
        toolbar = QHBoxLayout()
        toolbar.addWidget(label('PROJEKTBIBLIOTHEK', 'eyebrow'))
        toolbar.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Projekte suchen …')
        self.search.setMaximumWidth(250)
        self.search.textChanged.connect(self.refresh)
        toolbar.addWidget(self.search)
        toolbar.addWidget(button('Projektordner …', self.change_library))
        self.new_button = button('+ Neues Projekt', self.new_project, True)
        toolbar.addWidget(self.new_button)
        layout.addLayout(toolbar)
        splitter = QSplitter()
        left = QFrame()
        left.setObjectName('panel')
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(1, 1, 1, 14)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Projekt / Song', 'Status', 'Zuletzt bearbeitet'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setAcceptDrops(False)
        self.table.viewport().setAcceptDrops(False)
        self.table.itemSelectionChanged.connect(self.show_project)
        self.table.doubleClicked.connect(lambda _: self.open_editor())
        left_layout.addWidget(self.table, 1)
        self.drop_hint = label('↓  Song hierher ziehen oder „Neues Projekt“ wählen\nWAV · MP3 · FLAC · M4A · OGG', 'muted')
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setMargin(20)
        left_layout.addWidget(self.drop_hint)
        splitter.addWidget(left)
        right = QFrame()
        right.setObjectName('panel')
        right.setMinimumWidth(320)
        right.setMaximumWidth(380)
        right_outer = QVBoxLayout(right)
        right_outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        detail = QVBoxLayout(content)
        detail.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        scroll.setWidget(content)
        right_outer.addWidget(scroll)
        detail.setContentsMargins(24, 25, 24, 24)
        detail.setSpacing(15)
        detail.addWidget(label('DEIN ARBEITSPLATZ', 'eyebrow'))
        self.title = label('Bereit für deinen nächsten Song?', 'heading')
        detail.addWidget(self.title)
        self.description = label('Lege ein Projekt an. Lyrics Studio bereitet deinen Song vor und bewahrt deine Bearbeitung für später auf.', 'muted')
        detail.addWidget(self.description)
        self.reference_note = label('', 'muted')
        detail.addWidget(self.reference_note)
        self.prepare_button = button('Song vorbereiten', self.prepare)
        self.open_button = button('Lyrics bearbeiten', self.open_editor, True)
        self.save_button = button('Editor-Entwurf speichern', self.save_project)
        detail.addWidget(self.prepare_button)
        detail.addWidget(self.open_button)
        detail.addWidget(self.save_button)
        detail.addSpacing(8)
        detail.addWidget(label('EXPORT', 'eyebrow'))
        self.export_button = button('Untertitel exportieren · SRT', self.export_srt)
        detail.addWidget(self.export_button)
        self.title_export = button('Bearbeitbare Titel · DaVinci', self.export_resolve)
        self.title_export.setEnabled(False)
        detail.addWidget(self.title_export)
        detail.addWidget(label('Exportiert bestätigte Passagen: als Untertitel oder als einzeln bearbeitbare Text+-Kompositionen für DaVinci Resolve.', 'muted'))
        self.folder_button = button('Projektdateien öffnen  ↗', self.open_folder)
        detail.addStretch()
        detail.addWidget(self.folder_button)
        self.delete_button = button('Projekt löschen …', self.delete_project)
        detail.addWidget(self.delete_button)
        splitter.addWidget(right)
        splitter.setSizes([720, 360])
        layout.addWidget(splitter, 1)
        work = QFrame()
        work.setObjectName('panel')
        work_layout = QVBoxLayout(work)
        self.message = label('Ziehe eine Audiodatei ins Fenster, um loszulegen.', 'muted')
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        work_layout.addWidget(self.message)
        progress_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.hide()
        self.cancel_button = button('Abbrechen', self.cancel_processing)
        self.cancel_button.hide()
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.cancel_button)
        work_layout.addLayout(progress_row)
        layout.addWidget(work)
        self.library_label = label('', 'muted')
        self.library_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.library_label)
        update_row = QHBoxLayout()
        self.update_status = label('Updateprüfung bereit.', 'muted')
        update_row.addWidget(self.update_status, 1)
        self.update_check = button('Nach Updates suchen', self.check_updates)
        self.update_open = button('Update öffnen ↗', self.open_update)
        self.update_open.hide()
        update_row.addWidget(self.update_check)
        update_row.addWidget(self.update_open)
        layout.addLayout(update_row)
        self.editor_page = QWidget()
        editor_layout = QVBoxLayout(self.editor_page)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_toolbar = QHBoxLayout()
        editor_toolbar.setContentsMargins(14, 8, 14, 8)
        editor_toolbar.addWidget(button('← Projekte', self.show_overview))
        self.editor_title = label('', 'muted')
        editor_toolbar.addWidget(self.editor_title, 1)
        editor_toolbar.addWidget(button('Projektinformationen', self.project_information))
        editor_toolbar.addWidget(button('Entwurf speichern', self.save_active_editor))
        editor_layout.addLayout(editor_toolbar)
        self.editor_stack = QStackedWidget()
        editor_layout.addWidget(self.editor_stack, 1)
        self.pages.addWidget(self.editor_page)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_live_status)
        self.timer.start(2000)
        self.refresh()
        if start_updates and self.settings.value('check_updates_startup', True, type=bool):
            QTimer.singleShot(300, self.check_updates)
        elif start_updates:
            self.update_status.setText('Automatische Updateprüfung deaktiviert.')

    def check_updates(self):
        if self.update_worker and self.update_worker.isRunning():
            return
        self.update_status.setText('Suche nach einer neueren Version …')
        self.update_check.setEnabled(False)
        self.update_open.hide()
        self.update_worker = UpdateWorker(self)
        self.update_worker.completed.connect(self.show_update_result)
        self.update_worker.finished.connect(self.update_finished)
        self.update_worker.start()

    def show_update_result(self, result):
        self.update_status.setText(result.message)
        self.update_url = result.url if result.status == 'available' else ''
        self.update_open.setVisible(bool(self.update_url))

    def update_finished(self):
        self.update_check.setEnabled(True)
        if self.close_after_update:
            self.close_after_update = False
            QTimer.singleShot(0, self.close)

    def open_update(self):
        if self.update_url:
            QDesktopServices.openUrl(QUrl(self.update_url))

    def selected(self):
        row = self.table.currentRow()
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) if row >= 0 else None

    def refresh(self, *_):
        current = self.selected()
        identity = current.info['id'] if current else None
        self.projects, errors = self.library.list()
        query = self.search.text().casefold()
        shown = [p for p in self.projects if query in (p.info['name'] + ' ' + p.info['source_name']).casefold()]
        self.table.blockSignals(True)
        self.table.setRowCount(len(shown))
        selected_row = 0
        for row, project in enumerate(shown):
            name = QTableWidgetItem(project.info['name'])
            name.setToolTip(project.info['source_name'])
            name.setData(Qt.ItemDataRole.UserRole, project)
            self.table.setItem(row, 0, name)
            status = 'Wird vorbereitet …' if project.info['id'] == self.processing_id else STATUS.get(project.info['status'], 'Unbekannt')
            self.table.setItem(row, 1, QTableWidgetItem(status))
            date = project.info.get('updated_at', '')
            try:
                date = datetime.fromisoformat(date).astimezone().strftime('%d.%m.%Y · %H:%M')
            except ValueError:
                pass
            self.table.setItem(row, 2, QTableWidgetItem(date))
            self.table.setRowHeight(row, 56)
            if project.info['id'] == identity:
                selected_row = row
        if shown:
            self.table.selectRow(selected_row)
        self.table.blockSignals(False)
        self.library_label.setText(f'{len(self.projects)} Projekte  ·  {self.library.root}')
        if errors:
            self.message.setText('Einige Projekte konnten nicht geladen werden: ' + '; '.join(errors))
        self.show_project()

    def show_project(self):
        project = self.selected()
        ready = bool(project and project.ready)
        busy = bool(self.worker and self.worker.isRunning())
        self.prepare_button.setEnabled(bool(project and not ready and not busy))
        self.open_button.setEnabled(ready)
        self.save_button.setEnabled(ready)
        self.export_button.setEnabled(ready)
        self.title_export.setEnabled(ready and not busy)
        self.folder_button.setEnabled(project is not None)
        self.delete_button.setEnabled(project is not None and not busy)
        if project:
            self.title.setText(project.info['name'])
            self.title.setTextFormat(Qt.TextFormat.PlainText)
            self.description.setTextFormat(Qt.TextFormat.PlainText)
            if ready:
                duration = project.info.get('duration_seconds', 0)
                text = f'{project.info["source_name"]}\n{int(duration)//60}:{int(duration)%60:02} Minuten · {project.info.get("source_count", 0)} Textvorschläge'
            else:
                text = project.info.get('error') or 'Bereite den Song vor. Danach kannst du Text und Zeiten im Browser prüfen und korrigieren.'
            self.description.setText(text[:1200])
            self.reference_note.setText('Liedtext als Referenz hinterlegt' if project.path('reference.txt').exists() else 'Kein Referenztext hinterlegt')
        else:
            self.title.setText('Bereit für deinen nächsten Song?')
            self.description.setText('Ziehe einen Song ins Fenster oder lege ein neues Projekt an.')
            self.reference_note.clear()

    def update_live_status(self):
        project = self.selected()
        if project and str(project.directory) in self.sessions.servers:
            server, _ = self.sessions.servers[str(project.directory)]
            with server.store.lock:
                state = server.store.state()
            self.reference_note.setText(f'{state["confirmed_count"]} bestätigte Passagen · ' + ('ungespeicherte Änderungen' if state['dirty'] else 'Stand gespeichert'))

    def notify_error(self, exc):
        self.message.setText(str(exc)[:1600])
        QMessageBox.warning(self, 'Lyrics Studio', str(exc)[:2500])

    def configure(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.setValue('ffmpeg', dialog.ffmpeg.currentData())
            self.settings.setValue('model', dialog.model.currentData())
            self.settings.setValue('ffmpeg_locations', dialog.known_ffmpeg)
            self.settings.setValue('model_locations', dialog.known_models)
            self.settings.setValue('gpu', dialog.gpu.isChecked())
            self.settings.setValue('check_updates_startup', dialog.startup_updates.isChecked())
            self.settings.sync()

    def change_library(self):
        path = QFileDialog.getExistingDirectory(self, 'Projektbibliothek auswählen', str(self.library.root))
        if path:
            try:
                self.library = Library(path)
                self.settings.setValue('library', str(self.library.root))
                self.refresh()
            except (OSError, ValueError) as exc:
                self.notify_error(exc)

    def new_project(self, checked=False, audio=None):
        dialog = NewProjectDialog(self, audio)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            project = self.library.create(dialog.name.text(), dialog.audio.text(),
                dialog.reference.toPlainText(), dialog.language.currentData())
            self.search.clear()
            self.refresh()
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole).info['id'] == project.info['id']:
                    self.table.selectRow(row)
                    break
            if self.worker and self.worker.isRunning():
                self.message.setText('Projekt angelegt. Starte die Vorbereitung, sobald die laufende Verarbeitung abgeschlossen ist.')
            else:
                self.prepare()
        except (ValueError, OSError) as exc:
            self.notify_error(exc)

    def prepare(self):
        project = self.selected()
        if not project or project.ready or (self.worker and self.worker.isRunning()):
            return
        if not self.settings.value('model', os.environ.get('LYRICS_STUDIO_MODEL', '')):
            self.configure()
            if not self.settings.value('model', os.environ.get('LYRICS_STUDIO_MODEL', '')):
                self.message.setText('Projekt angelegt. Wähle in den Einstellungen das Whisper-Modell und starte dann „Song vorbereiten“.')
                return
        options = {key: self.settings.value(key, default, type=bool) if key == 'gpu' else self.settings.value(key, default)
                   for key, default in [('ffmpeg', 'ffmpeg'), ('model', os.environ.get('LYRICS_STUDIO_MODEL', '')), ('gpu', True)]}
        self.worker = ImportWorker(project, options, self)
        self.processing_id = project.info['id']
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.import_result)
        self.worker.finished.connect(self.import_finished)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.worker.start()
        self.refresh()

    def on_progress(self, text, percent):
        self.message.setText(text)
        self.progress.setRange(0, 0 if percent < 0 else 100)
        if percent >= 0:
            self.progress.setValue(percent)

    def import_result(self, message, success):
        self.message.setText(message[:1600])

    def import_finished(self):
        self.processing_id = None
        self.progress.hide()
        self.cancel_button.hide()
        self.refresh()

    def cancel_processing(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self.message.setText('Verarbeitung wird beendet …')

    def open_editor(self):
        project = self.selected()
        if not project or not project.ready:
            return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            server = self.sessions.open(project)
            project.update()
            key = str(project.directory)
            if self.active_editor_key and self.active_editor_key != key:
                self.editor_views[self.active_editor_key].pause()
            if key not in self.editor_views:
                view = EditorView(server, self.editor_stack)
                self.editor_views[key] = view
                self.editor_stack.addWidget(view)
            self.active_editor_key = key
            self.editor_stack.setCurrentWidget(self.editor_views[key])
            self.editor_title.setText(f'{project.info["name"]} · Lyrics Studio {__version__}')
            self.pages.setCurrentWidget(self.editor_page)
            self.setWindowTitle(f'Lyrics Studio {__version__} · {project.info["name"]}')
        except (ValueError, OSError) as exc:
            self.notify_error(exc)
        finally:
            QApplication.restoreOverrideCursor()

    def show_overview(self):
        if self.active_editor_key:
            self.editor_views[self.active_editor_key].pause()
        self.pages.setCurrentWidget(self.overview)
        self.setWindowTitle(f'Lyrics Studio {__version__} · Projekte')
        self.refresh()

    def save_active_editor(self):
        if self.active_editor_key:
            key = self.active_editor_key
            self.flush_editor(key, lambda: self.editor_title.setText(self.sessions.servers[key][0].store.title + ' · Entwurf gespeichert'))

    def project_information(self):
        project = Project(self.active_editor_key) if self.active_editor_key else self.selected()
        if not project:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Projektinformationen')
        dialog.resize(650, 250)
        form = QFormLayout(dialog)
        for caption, value in [('Projekt', project.info['name']), ('Songdatei', project.info['source_name']),
                               ('Projektordner', str(project.directory)),
                               ('Gespeicherter Entwurf', str(project.state_dir / 'lyrics_editor_draft.json'))]:
            info = label(value, 'muted')
            info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(caption, info)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        controls.button(QDialogButtonBox.StandardButton.Close).setText('Schließen')
        controls.rejected.connect(dialog.reject)
        form.addRow(controls)
        dialog.exec()

    def flush_editor(self, key, success):
        if self.editor_operation:
            return
        view = self.editor_views.get(key)
        if view is None:
            success()
            return
        self.editor_operation = True
        def completed(result):
            self.editor_operation = False
            if result.get('ok'):
                success()
            else:
                self.notify_error(ValueError(result.get('error', 'Speichern fehlgeschlagen.')))
        view.flush(True, completed)

    def save_project(self):
        project = self.selected()
        if project and str(project.directory) in self.editor_views:
            self.flush_editor(str(project.directory), lambda: self.message.setText('Der Editor-Entwurf wurde gespeichert.'))
            return
        if project and project.ready:
            try:
                server = self.sessions.open(project)
                with server.store.lock:
                    server.store.save(server.store.revision)
                project.update()
                self.message.setText('Der Editor-Entwurf wurde gespeichert.')
                self.refresh()
            except (ValueError, OSError) as exc:
                self.notify_error(exc)

    def export_srt(self):
        project = self.selected()
        if not project or not project.ready:
            return
        self.flush_editor(str(project.directory), lambda: self._export_srt(project))

    def _export_srt(self, project):
        dialog = QDialog(self)
        dialog.setWindowTitle('Untertitel exportieren')
        form = QFormLayout(dialog)
        form.addRow(label('Exportiert werden die ausdrücklich bestätigten Passagen.'))
        offset = QDoubleSpinBox()
        offset.setRange(0, 86400)
        offset.setDecimals(3)
        offset.setSuffix(' s')
        form.addRow('Song beginnt in der Timeline bei', offset)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Ok).setText('Weiter …')
        controls.button(QDialogButtonBox.StandardButton.Cancel).setText('Abbrechen')
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        form.addRow(controls)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            server = self.sessions.open(project)
            with server.store.lock:
                server.store.save(server.store.revision)
                payload = srt_document(server.store.document(), offset.value())
            path, _ = QFileDialog.getSaveFileName(self, 'SRT speichern', str(project.path('exports') / 'lyrics.srt'), 'Untertitel (*.srt)')
            if path:
                target = Path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(target, payload.encode('utf-8'))
                self.message.setText(f'Untertitel exportiert: {target}')
                project.update()
        except (ValueError, OSError) as exc:
            self.notify_error(exc)

    def export_resolve(self):
        project = self.selected()
        if not project or not project.ready or self.worker and self.worker.isRunning():
            return
        self.flush_editor(str(project.directory), lambda: self._export_resolve(project))

    def _export_resolve(self, project):
        try:
            server = self.sessions.open(project)
            with server.store.lock:
                server.store.save(server.store.revision)
                document = server.store.document()
                audio = server.store.audio
            if not document['confirmed_occurrences']:
                raise ValueError('Bitte zuerst Textpassagen prüfen und bestätigen.')
        except (ValueError, OSError) as exc:
            self.notify_error(exc)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Bearbeitbare DaVinci-Titel exportieren')
        dialog.resize(610, 330)
        form = QFormLayout(dialog)
        form.addRow(label(f'Bestätigte Passagen: {len(document["confirmed_occurrences"])} · Export als Text+-Kompositionen.'))
        form.addRow(label('Der Import erstellt eine neue Timeline. Wähle die Bildrate deiner gewünschten Ziel-Timeline.', 'muted'))
        fps = QComboBox()
        for value in (24, 25, 30, 50, 60):
            fps.addItem(f'{value} FPS', value)
        resolution = QComboBox()
        resolution.addItem('Full HD · 1920 × 1080', (1920, 1080))
        resolution.addItem('UHD · 3840 × 2160', (3840, 2160))
        offset = QDoubleSpinBox()
        offset.setRange(0, 86400)
        offset.setDecimals(3)
        offset.setSuffix(' s')
        include_audio = QCheckBox('Song als Audiospur mitnehmen')
        include_audio.setChecked(True)
        form.addRow('Bildrate', fps)
        form.addRow('Auflösung', resolution)
        form.addRow('Song beginnt bei', offset)
        form.addRow('', include_audio)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Ok).setText('Exportordner wählen …')
        controls.button(QDialogButtonBox.StandardButton.Cancel).setText('Abbrechen')
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        form.addRow(controls)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        parent = QFileDialog.getExistingDirectory(self, 'DaVinci-Export ablegen', str(project.directory))
        if not parent:
            return
        width, height = resolution.currentData()
        options = dict(fps=fps.currentData(), offset=offset.value(), width=width, height=height,
                       include_audio=include_audio.isChecked())
        self.worker = TitleExportWorker(project, document, audio, parent, options, self)
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.resolve_export_result)
        self.worker.finished.connect(self.import_finished)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.show()
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.worker.start()
        self.show_project()

    def resolve_export_result(self, message, success):
        self.message.setText(message[:1600])
        if not success:
            return
        output = self.worker.output
        command = 'dofile(' + lua_string((output / 'Import_in_DaVinci.lua').as_posix()) + ')'
        dialog = QDialog(self)
        dialog.setWindowTitle('DaVinci-Titelpaket ist fertig')
        dialog.resize(720, 370)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('In DaVinci Resolve importieren', 'heading'))
        layout.addWidget(label('Öffne dein Resolve-Projekt und danach Arbeitsbereich / Workspace → Konsole / Console. Wähle dort Lua, füge diesen Befehl ein und drücke Enter.'))
        field = QPlainTextEdit(command)
        field.setReadOnly(True)
        field.setMaximumHeight(95)
        layout.addWidget(field)
        layout.addWidget(button('Importbefehl kopieren', lambda: QApplication.clipboard().setText(command)))
        style_command = 'dofile(' + lua_string((output / 'Titelstil_in_Resolve.lua').as_posix()) + ')'
        layout.addWidget(label('Nach dem Import: Lyrics-Clips in Resolve markieren und mit dem Stilbefehl eine Animation wählen. Für andere Passagen wiederholen.', 'muted'))
        layout.addWidget(button('Befehl zur Stilwahl kopieren', lambda: QApplication.clipboard().setText(style_command)))
        layout.addWidget(button('Exportordner öffnen ↗', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))))
        layout.addWidget(label('Die neue Timeline enthält einzelne Text+-Kompositionen. Zum Bearbeiten einen Clip auswählen und in Fusion den Knoten Lyrics_Text öffnen. Den gesamten Exportordner behalten.', 'muted'))
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText('Schließen')
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()

    def delete_project(self):
        project = self.selected()
        if not project or self.editor_operation or self.worker and self.worker.isRunning():
            return
        answer = QMessageBox.question(self, 'Projekt löschen',
            f'„{project.info["name"]}“ mit allen Projektdateien und Entwürfen in den Papierkorb verschieben?\n\n'
            'Die ursprüngliche Songdatei bleibt erhalten. Offene Browser-Editoren dieses Projekts werden beendet; ungespeicherte Eingaben gehen verloren.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.library.validate_delete(project)
            view = self.editor_views.pop(str(project.directory), None)
            if view:
                view.pause()
                self.editor_stack.removeWidget(view)
                view.deleteLater()
                if self.active_editor_key == str(project.directory):
                    self.active_editor_key = None
                    self.pages.setCurrentWidget(self.overview)
            self.sessions.close_project(project)
            self.library.delete(project, QFile.moveToTrash)
            self.message.setText('Projekt in den Papierkorb verschoben. Die ursprüngliche Songdatei wurde nicht verändert.')
            self.refresh()
        except (ValueError, OSError) as exc:
            self.notify_error(exc)

    def open_folder(self):
        project = self.selected()
        if project:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(project.directory)))

    def drop_audio(self, mime):
        if not mime.hasUrls() or len(mime.urls()) != 1:
            return None
        url = mime.urls()[0]
        path = Path(url.toLocalFile()) if url.isLocalFile() else None
        return path if path and path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS else None

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self.drop_audio(event.mimeData()):
            event.acceptProposedAction()
            self.drop_hint.setText('↓  Loslassen, um ein neues Song-Projekt anzulegen')
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_hint.setText('↓  Song hierher ziehen oder „Neues Projekt“ wählen\nWAV · MP3 · FLAC · M4A · OGG')
        event.accept()

    def dropEvent(self, event: QDropEvent):
        audio = self.drop_audio(event.mimeData())
        self.drop_hint.setText('↓  Song hierher ziehen oder „Neues Projekt“ wählen\nWAV · MP3 · FLAC · M4A · OGG')
        if audio:
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda: self.new_project(audio=audio))
        else:
            event.ignore()

    def closeEvent(self, event):
        if self.editor_operation:
            event.ignore()
            return
        if self.close_after_save:
            self.dispose_editors()
            self.sessions.close()
            event.accept()
            return
        if self.update_worker and self.update_worker.isRunning():
            self.close_after_update = True
            event.ignore()
            return
        if self.worker and self.worker.isRunning():
            self.message.setText('Bitte die Verarbeitung abschließen lassen oder zuerst „Abbrechen“ wählen.')
            event.ignore()
            return
        if self.sessions.servers:
            choice = QMessageBox.question(self, 'Ungespeicherte Änderungen',
                'Vor dem Beenden alle geöffneten Projekte speichern? Auch Eingaben im Editor werden übernommen.',
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
            if choice == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if choice == QMessageBox.StandardButton.Save:
                if self.editor_views:
                    event.ignore()
                    self.save_editors_before_close(list(self.editor_views))
                    return
                try:
                    self.sessions.save_all()
                except (ValueError, OSError) as exc:
                    self.notify_error(exc)
                    event.ignore()
                    return
        self.dispose_editors()
        self.sessions.close()
        event.accept()

    def save_editors_before_close(self, keys):
        if keys:
            key, *remaining = keys
            self.flush_editor(key, lambda: self.save_editors_before_close(remaining))
            return
        try:
            self.sessions.save_all()
            self.close_after_save = True
            self.close()
        except (ValueError, OSError) as exc:
            self.notify_error(exc)

    def dispose_editors(self):
        for view in self.editor_views.values():
            view.pause()
            self.editor_stack.removeWidget(view)
            view.deleteLater()
        self.editor_views.clear()
        self.active_editor_key = None


def main():
    parser = argparse.ArgumentParser(description='Lyrics Studio Desktop')
    parser.add_argument('--library', type=Path, help='Ordner für persönliche Projekte')
    parser.add_argument('--check', action='store_true', help='Oberfläche und gebündelte Dateien prüfen, dann beenden')
    parser.add_argument('--check-editor', action='store_true', help='Eingebetteten Editor mit einem vorbereiteten Testprojekt prüfen')
    args = parser.parse_args()
    set_taskbar_identity()
    application = QApplication(sys.argv[:1])
    application.setApplicationName('Lyrics Studio')
    application.setApplicationVersion(__version__)
    application.setWindowIcon(application_icon())
    application.setStyle('Fusion')
    application.setStyleSheet(STYLE)
    window = Window(args.library, start_updates=not (args.check or args.check_editor))
    window.show()
    if args.check_editor:
        finished = False
        def finish_editor_check(success):
            nonlocal finished
            if finished:
                return
            finished = True
            window.dispose_editors()
            window.sessions.close()
            window.close()
            application.exit(0 if success else 1)
        def start_editor_check():
            for row in range(window.table.rowCount()):
                if window.table.item(row, 0).data(Qt.ItemDataRole.UserRole).ready:
                    window.table.selectRow(row)
                    window.open_editor()
                    break
            if not window.editor_views:
                finish_editor_check(False)
                return
            view = window.editor_views[window.active_editor_key]
            timer = QTimer(window)
            def inspect():
                if view.loaded:
                    view.page().runJavaScript("!!window.lyricsDesktop && !!document.querySelector('.lyric-row')", result)
            def result(ready):
                if ready:
                    timer.stop()
                    finish_editor_check(True)
            timer.timeout.connect(inspect)
            timer.start(150)
            QTimer.singleShot(20000, lambda: finish_editor_check(False))
        QTimer.singleShot(150, start_editor_check)
    elif args.check:
        from lyrics_editor.server import ASSETS
        def check():
            valid = all((ASSETS / name).is_file() for name in ('index.html', 'app.js', 'style.css'))
            valid = valid and window.open_button.height() >= 40 and not window.windowIcon().isNull()
            window.close()
            application.exit(0 if valid else 1)
        QTimer.singleShot(150, check)
    sys.exit(application.exec())
