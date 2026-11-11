"""PetaRelasi Studio: local file import, interactive ERD and learning inspector."""
from pathlib import Path
import sqlite3
import sys

from PySide6.QtCore import QSettings, QSignalBlocker, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from .. import __version__
from .canvas import DiagramView
from .model import EXAMPLES, Session, intro_notes, read_file, read_sql_text, relation_notes, table_notes
from .style import NOTES_STYLE, STYLE


DIALECT_LABELS = [('SQLite', 'sqlite'), ('MySQL / MariaDB', 'mysql'),
                  ('PostgreSQL', 'postgres'), ('SQL Server', 'tsql')]


def label(text, name='', wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, callback, name=''):
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    widget.clicked.connect(callback)
    return widget


def panel(name, margins=(20, 20, 20, 20)):
    widget = QWidget()
    widget.setObjectName(name)
    body = QVBoxLayout(widget)
    body.setContentsMargins(*margins)
    body.setSpacing(12)
    return widget, body


class SqlHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        for expression, color, bold in [
            (r'\b(CREATE|TABLE|PRIMARY|FOREIGN|KEY|REFERENCES|ALTER|ADD|CONSTRAINT|NOT|NULL|DEFAULT|UNIQUE|USE|GO)\b', '#087d72', True),
            (r'\b(INTEGER|INT|BIGINT|TEXT|VARCHAR|NVARCHAR|SERIAL|BOOLEAN|DATE|TIMESTAMP|DECIMAL)\b', '#966424', False),
            (r"'(?:[^']|'')*'", '#8d586d', False),
            (r'--[^\n]*', '#8c998b', False),
        ]:
            regex = QRegularExpression(expression, QRegularExpression.PatternOption.CaseInsensitiveOption)
            matches = regex.globalMatch(text)
            style = QTextCharFormat()
            style.setForeground(QColor(color))
            if bold:
                style.setFontWeight(QFont.Weight.Bold)
            while matches.hasNext():
                match = matches.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), style)


class ImportJob(QThread):
    ready = Signal(object, str)
    failed = Signal(str)

    def __init__(self, operation, title, parent):
        super().__init__(parent)
        self.operation, self.title = operation, title

    def run(self):
        try:
            schema = self.operation()
        except (ValueError, OSError, sqlite3.Error) as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit('Skema tidak dapat dibaca. Periksa format file dan pilihan dialek SQL.')
        else:
            self.ready.emit(schema, self.title)


class StudioWindow(QMainWindow):
    document_loaded = Signal()
    import_failed = Signal(str)

    def __init__(self, settings=None, *, load_example=True):
        super().__init__()
        self.settings = settings if settings is not None else QSettings('Mavianza', 'PetaRelasiStudio')
        self.session = Session()
        self.worker = None
        self.busy = False
        self.pending_close = False
        self.file_path = None
        self.selected_table = ''
        self.setWindowTitle('PetaRelasi Studio · Jelajahi struktur database')
        self.resize(1480, 900)
        self.setMinimumSize(1060, 680)
        self.setStyleSheet(STYLE)
        self._build()
        self._shortcuts()
        geometry = self.settings.value('geometry')
        if geometry is not None:
            self.restoreGeometry(geometry)
        if load_example:
            self.load_example()

    def _build(self):
        root = QWidget()
        body = QVBoxLayout(root)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.setCentralWidget(root)
        header, header_body = panel('header', (24, 17, 24, 17))
        top = QHBoxLayout()
        identity = QVBoxLayout()
        identity.setSpacing(1)
        identity.addWidget(label('PetaRelasi', 'brand'))
        identity.addWidget(label('STUDIO  /  JELAJAHI & PAHAMI', 'eyebrow'))
        top.addLayout(identity)
        top.addSpacing(24)
        self.tagline = label('Dari struktur database ke diagram yang bisa dipelajari.', 'subtitle')
        top.addWidget(self.tagline)
        top.addStretch()
        top.addWidget(label('Lokal · ' + __version__, 'pill'))
        self.export_format = QComboBox()
        for title, extension in [('Draw.io', '.drawio'), ('SVG', '.svg'), ('Snapshot JSON', '.json')]:
            self.export_format.addItem(title, extension)
        top.addWidget(self.export_format)
        self.export_button = button('Ekspor tampilan', self.choose_export, 'primary')
        self.export_button.setEnabled(False)
        top.addWidget(self.export_button)
        header_body.addLayout(top)
        body.addWidget(header)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        body.addWidget(self.progress)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        body.addWidget(self.splitter, 1)
        self._build_input()
        self._build_diagram()
        self._build_notes()
        self.splitter.setSizes([320, 820, 320])
        self.splitter.setStretchFactor(1, 1)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().showMessage('File dibaca di komputer ini. SQL tidak dieksekusi.')

    def _build_input(self):
        left, body = panel('inputPanel')
        left.setMinimumWidth(280)
        left.setMaximumWidth(400)
        body.addWidget(label('01  SUMBER SKEMA', 'eyebrow'))
        heading = QHBoxLayout()
        heading.addWidget(label('Mulai dari database', 'section'))
        heading.addStretch()
        body.addLayout(heading)
        self.examples = QComboBox()
        self.examples.addItems(EXAMPLES)
        examples = QHBoxLayout()
        examples.addWidget(self.examples, 1)
        self.example_button = button('Coba', self.load_example)
        examples.addWidget(self.example_button)
        body.addLayout(examples)
        self.input_tabs = QTabWidget()
        self.input_tabs.setObjectName('inputTabs')
        file_tab, file_body = panel('fileTab', (0, 14, 0, 0))
        self.open_button = button('Pilih file database / SQL', self.choose_file)
        file_body.addWidget(self.open_button)
        self.file_label = label('Belum ada file dipilih.', 'muted', True)
        file_body.addWidget(self.file_label)
        file_body.addWidget(label('SQLite (.db / .sqlite), ekspor .sql, atau snapshot .json. File juga bisa diseret ke diagram.', 'muted', True))
        file_body.addStretch()
        self.input_tabs.addTab(file_tab, 'Buka file')
        sql_tab, sql_body = panel('sqlTab', (0, 12, 0, 0))
        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setObjectName('sqlEditor')
        self.sql_editor.setPlaceholderText('CREATE TABLE anggota (\n  id INTEGER PRIMARY KEY\n);')
        self.sql_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.sql_editor.setTabStopDistance(24)
        self.sql_editor.setMinimumHeight(165)
        self.highlighter = SqlHighlighter(self.sql_editor.document())
        sql_body.addWidget(self.sql_editor)
        self.draft_note = label('Perubahan SQL belum diterapkan.', 'muted')
        self.draft_note.hide()
        sql_body.addWidget(self.draft_note)
        self.input_tabs.addTab(sql_tab, 'Tempel SQL')
        body.addWidget(self.input_tabs, 2)
        self.sql_options = QWidget()
        options = QVBoxLayout(self.sql_options)
        options.setContentsMargins(0, 0, 0, 0)
        options.setSpacing(6)
        options.addWidget(label('Jenis SQL', 'muted'))
        self.dialect = QComboBox()
        for title, value in DIALECT_LABELS:
            self.dialect.addItem(title, value)
        options.addWidget(self.dialect)
        self.namespace = QLineEdit()
        self.namespace.setPlaceholderText('Schema bawaan · opsional')
        self.namespace.setToolTip('Untuk nama tabel SQL yang tidak menyebut schema. Contoh: public atau dbo.')
        options.addWidget(self.namespace)
        body.addWidget(self.sql_options)
        self.build_button = button('Buat diagram', self.import_source, 'primary')
        self.build_button.setObjectName('buildButton')
        self.build_button.setStyleSheet('QPushButton { background:#087d72; color:white; border-color:#087d72; padding:11px; }')
        body.addWidget(self.build_button)
        self.error_label = label('', wrap=True)
        self.error_label.setObjectName('errorLabel')
        self.error_label.setStyleSheet('color:#a5433e; background:#fff0e8; padding:10px; border-radius:6px; font-size:12px;')
        self.error_label.hide()
        body.addWidget(self.error_label)
        body.addSpacing(8)
        body.addWidget(label('TABEL DALAM SKEMA', 'eyebrow'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Cari nama tabel…')
        self.search.setClearButtonEnabled(True)
        body.addWidget(self.search)
        self.table_list = QListWidget()
        self.table_list.setMinimumHeight(100)
        body.addWidget(self.table_list, 1)
        self.table_list.currentItemChanged.connect(self._table_chosen)
        self.search.textChanged.connect(self.filter_tables)
        self.input_tabs.currentChanged.connect(self._source_options)
        scroll = QScrollArea()
        scroll.setObjectName('inputScroll')
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(280)
        scroll.setMaximumWidth(400)
        scroll.setWidget(left)
        self.splitter.addWidget(scroll)
        self.input_panel = left
        self.sql_editor.textChanged.connect(self._mark_draft)
        self.dialect.currentIndexChanged.connect(self._mark_draft)
        self.namespace.textChanged.connect(self._mark_draft)
        self._source_options()

    def _build_diagram(self):
        middle, body = panel('canvasPanel', (0, 0, 0, 0))
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(20, 16, 20, 12)
        title = QVBoxLayout()
        title.setSpacing(3)
        title.addWidget(label('02  JELAJAHI DIAGRAM', 'eyebrow'))
        self.source_title = label('Belum ada diagram', 'section')
        title.addWidget(self.source_title)
        self.count_label = label('Buka file atau gunakan contoh untuk mulai.', 'counter')
        title.addWidget(self.count_label)
        toolbar.addLayout(title, 1)
        self.zoom_label = label('100%', 'muted')
        toolbar.addWidget(button('−', lambda: self.view.zoom(1 / 1.2)))
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(button('+', lambda: self.view.zoom(1.2)))
        toolbar.addWidget(button('Pas layar', lambda: self.view.fit_diagram()))
        body.addLayout(toolbar)
        filters = QHBoxLayout()
        filters.setContentsMargins(20, 0, 20, 12)
        filters.addWidget(label('Fokus', 'muted'))
        self.focus_combo = QComboBox()
        self.focus_combo.addItem('Semua tabel', None)
        self.focus_combo.setMinimumContentsLength(15)
        filters.addWidget(self.focus_combo, 1)
        filters.addWidget(label('Radius', 'muted'))
        self.radius = QSpinBox()
        self.radius.setRange(0, 5)
        self.radius.setValue(1)
        self.radius.setFixedWidth(57)
        self.radius.setEnabled(False)
        filters.addWidget(self.radius)
        body.addLayout(filters)
        self.focus_combo.currentIndexChanged.connect(self.change_focus)
        self.radius.valueChanged.connect(self.change_focus)
        self.view = DiagramView()
        self.view.setMinimumWidth(430)
        self.view.table_selected.connect(self.select_table)
        self.view.relation_selected.connect(self.select_relation)
        self.view.zoom_changed.connect(lambda percent: self.zoom_label.setText(str(percent) + '%'))
        self.view.file_dropped.connect(self.drop_file)
        body.addWidget(self.view, 1)
        guide = label('Gulir untuk zoom  ·  Seret area kosong untuk bergeser  ·  Klik tabel, kolom, atau garis', 'muted')
        guide.setWordWrap(True)
        guide.setContentsMargins(20, 11, 20, 11)
        body.addWidget(guide)
        self.splitter.addWidget(middle)

    def _build_notes(self):
        right, body = panel('notesPanel')
        right.setMinimumWidth(260)
        right.setMaximumWidth(390)
        heading = QHBoxLayout()
        heading.addWidget(label('03  PAHAMI RELASINYA', 'eyebrow'))
        heading.addStretch()
        body.addLayout(heading)
        body.addWidget(button('Panduan PK & FK', self.show_intro, 'quiet'))
        self.notes = QTextBrowser()
        self.notes.setObjectName('learningNotes')
        self.notes.setOpenExternalLinks(False)
        self.notes.document().setDefaultStyleSheet(NOTES_STYLE)
        self.notes.setHtml(intro_notes())
        body.addWidget(self.notes, 1)
        body.addWidget(label('PK  Identitas baris     FK  Referensi', 'muted', True))
        body.addWidget(label('Yang diekspor adalah tabel dan relasi dalam tampilan saat ini.', 'muted', True))
        self.splitter.addWidget(right)

    def _shortcuts(self):
        self.open_shortcut = QShortcut(QKeySequence.StandardKey.Open, self)
        self.open_shortcut.activated.connect(self.choose_file)
        self.save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        self.save_shortcut.activated.connect(self.choose_export)
        self.build_shortcut = QShortcut(QKeySequence('Ctrl+Return'), self)
        self.build_shortcut.activated.connect(self.import_source)

    def _source_options(self):
        is_sql = self.input_tabs.currentIndex() == 1 or (self.file_path is not None and self.file_path.suffix.lower() == '.sql')
        self.sql_options.setVisible(is_sql)

    def _mark_draft(self, *args):
        if self.input_tabs.currentIndex() == 1 and self.session.schema is not None:
            self.draft_note.show()

    def choose_file(self):
        if self.busy:
            return
        filename, _ = QFileDialog.getOpenFileName(self, 'Buka skema database', self.settings.value('last_directory', ''),
                                                 'Database dan skema (*.sqlite *.sqlite3 *.db *.sql *.json);;Semua file (*)')
        if filename:
            self.prepare_file(filename)

    def prepare_file(self, filename):
        self.file_path = Path(filename)
        self.file_label.setText(self.file_path.name + '\nKlik Buat diagram untuk membaca file.')
        self.file_label.setToolTip(str(self.file_path))
        self.input_tabs.setCurrentIndex(0)
        self._source_options()
        self.settings.setValue('last_directory', str(self.file_path.parent))

    def drop_file(self, filename):
        if not self.busy:
            self.prepare_file(filename)
            if self.file_path.suffix.lower() == '.sql':
                self.statusBar().showMessage('File SQL dipilih. Sesuaikan jenis SQL, lalu klik Buat diagram.')
            else:
                self.import_source()

    def load_example(self):
        if self.busy:
            return
        title = self.examples.currentText()
        text = EXAMPLES[title]
        self.sql_editor.setPlainText(text)
        self.dialect.setCurrentIndex(self.dialect.findData('sqlite'))
        self.namespace.clear()
        self.input_tabs.setCurrentIndex(1)
        # Tiny bundled example is loaded before the event loop at first launch.
        try:
            schema = read_sql_text(text, 'sqlite')
        except (ValueError, OSError) as exc:
            self.show_error(str(exc))
        else:
            self.accept_schema(schema, 'Contoh ' + title.split(' · ')[0].lower())

    def import_source(self):
        if self.busy:
            return
        dialect = self.dialect.currentData()
        namespace = self.namespace.text().strip() or None
        if self.input_tabs.currentIndex() == 1:
            text = self.sql_editor.toPlainText()
            operation = lambda: read_sql_text(text, dialect, namespace)
            title = 'SQL ' + self.dialect.currentText()
        else:
            path = self.file_path
            if path is None:
                self.show_error('Pilih file terlebih dahulu atau gunakan tab Tempel SQL.')
                return
            operation = lambda: read_file(path, dialect, namespace)
            title = path.name
        self.set_busy(True)
        self.worker = ImportJob(operation, title, self)
        self.worker.ready.connect(self.accept_schema)
        self.worker.failed.connect(self._import_error)
        self.worker.finished.connect(self._import_finished)
        self.worker.start()

    def set_busy(self, busy):
        self.busy = busy
        self.input_panel.setEnabled(not busy)
        self.export_button.setEnabled(not busy and self.session.visible is not None)
        self.progress.setVisible(busy)
        self.build_button.setText('Membaca skema…' if busy else 'Buat diagram')
        if busy:
            self.error_label.hide()
            self.statusBar().showMessage('Membaca struktur. Diagram sebelumnya tetap tersedia sampai impor berhasil.')

    def accept_schema(self, schema, title):
        self.session.replace(schema, title)
        self.selected_table = ''
        self.error_label.hide()
        self.draft_note.hide()
        self.source_title.setText(title if len(title) < 66 else title[:42] + '…' + title[-20:])
        self.source_title.setToolTip(title)
        self.table_list.clear()
        self.search.clear()
        with QSignalBlocker(self.focus_combo):
            self.focus_combo.clear()
            self.focus_combo.addItem('Semua tabel', None)
            for table in schema.tables:
                self.focus_combo.addItem(table.name, table.name)
                item = QListWidgetItem(f'{table.name}\n{len(table.columns)} kolom')
                item.setData(Qt.ItemDataRole.UserRole, table.name)
                item.setToolTip(table.name)
                self.table_list.addItem(item)
        self.radius.setEnabled(False)
        with QSignalBlocker(self.radius):
            self.radius.setValue(1)
        self.draw_visible()
        self.show_intro()
        self.export_button.setEnabled(not self.busy)
        self.statusBar().showMessage('Skema siap. Klik tabel atau garis untuk memahami relasinya. Ekspor mengikuti tampilan saat ini.')
        self.document_loaded.emit()
        QTimer.singleShot(0, self.view.fit_diagram)

    def _import_error(self, message):
        self.show_error(message + ('\nDiagram sebelumnya tetap ditampilkan.' if self.session.schema else ''))
        self.import_failed.emit(message)

    def _import_finished(self):
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        self.set_busy(False)
        if self.pending_close:
            self.close()

    def show_error(self, message):
        self.error_label.setText(message)
        self.error_label.show()
        self.statusBar().showMessage('Proses gagal. ' + message.split('\n')[0])

    def filter_tables(self, text):
        for index in range(self.table_list.count()):
            item = self.table_list.item(index)
            item.setHidden(text.casefold() not in item.data(Qt.ItemDataRole.UserRole).casefold())

    def _table_chosen(self, current, previous):
        if current is not None:
            self.select_table(current.data(Qt.ItemDataRole.UserRole), '')

    def select_table(self, name, column=''):
        if self.session.schema is None:
            return
        self.selected_table = name
        self.view.select(name, column)
        self.notes.setHtml(table_notes(self.session.schema, name, column))
        for index in range(self.table_list.count()):
            item = self.table_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == name:
                with QSignalBlocker(self.table_list):
                    self.table_list.setCurrentItem(item)
                break
        if name not in self.view.tables:
            self.statusBar().showMessage('Tabel ada di skema lengkap dan berada di luar fokus diagram. Pilih Semua tabel untuk melihatnya.')
        else:
            self.statusBar().showMessage(name + ('.' + column if column else '') + ' · Penjelasan tersedia di panel kanan.')

    def select_relation(self, ref):
        self.view.select(reference=ref)
        self.notes.setHtml(relation_notes(ref))
        self.statusBar().showMessage(f'{ref.table} → {ref.references} · {len(ref.columns)} pasangan dalam satu foreign key.')

    def show_intro(self):
        self.view.select()
        self.notes.setHtml(intro_notes())
        self.table_list.clearSelection()
        self.table_list.setCurrentRow(-1)

    def change_focus(self, *args):
        if self.session.schema is None:
            return
        name = self.focus_combo.currentData()
        self.session.set_focus(name, self.radius.value())
        self.radius.setEnabled(name is not None)
        self.draw_visible()
        self.show_intro()
        self.statusBar().showMessage('Tampilan fokus aktif. Semua format ekspor mengikuti tabel yang terlihat.' if name else 'Semua tabel ditampilkan.')

    def draw_visible(self):
        visible = self.session.visible
        self.view.show_schema(visible)
        total = len(self.session.schema.tables)
        pairs = sum(len(ref.columns) for ref in visible.foreign_keys)
        self.count_label.setText(f'{len(visible.tables)} dari {total} tabel · {len(visible.foreign_keys)} FK · {pairs} sambungan kolom')

    def choose_export(self):
        if self.busy or self.session.visible is None:
            return
        extension = self.export_format.currentData()
        path, _ = QFileDialog.getSaveFileName(self, 'Ekspor diagram yang sedang terlihat',
                                             str(Path(self.settings.value('last_directory', '') or '.') / ('PetaRelasi' + extension)),
                                             f'{self.export_format.currentText()} (*{extension})',
                                             options=QFileDialog.Option.DontConfirmOverwrite)
        if path:
            if not Path(path).suffix:
                path += extension
            self.export_to(path)

    def export_to(self, path):
        try:
            self.session.export(path)
        except (ValueError, OSError) as exc:
            self.show_error('Ekspor gagal. ' + str(exc))
            return False
        self.error_label.hide()
        self.settings.setValue('last_directory', str(Path(path).parent))
        self.statusBar().showMessage('Tersimpan: ' + str(path) + ' · ' + str(len(self.session.visible.tables)) + ' tabel dalam tampilan.')
        return True

    def closeEvent(self, event):
        if self.busy:
            self.pending_close = True
            self.statusBar().showMessage('Menunggu pembacaan skema selesai sebelum menutup aplikasi…')
            event.ignore()
            return
        self.settings.setValue('geometry', self.saveGeometry())
        super().closeEvent(event)

    def resizeEvent(self, event):
        if hasattr(self, 'tagline'):
            self.tagline.setVisible(self.width() >= 1380)
        super().resizeEvent(event)


def launch():
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName('PetaRelasi Studio')
    app.setOrganizationName('Mavianza')
    app.setStyle('Fusion')
    window = StudioWindow()
    screen = app.primaryScreen()
    if screen is not None and window.settings.value('geometry') is None:
        available = screen.availableGeometry()
        window.resize(max(1060, min(1480, available.width() - 70)),
                      max(680, min(900, available.height() - 70)))
    window.show()
    return app.exec()
