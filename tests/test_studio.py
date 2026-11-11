"""Exercise real widgets offscreen, imports in QThread and exported artifacts."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from petarelasi.schema import validate
from petarelasi.studio.model import EXAMPLES, Session, read_sql_text, relation_notes, table_notes

HAS_SQL = importlib.util.find_spec('sqlglot') is not None
HAS_QT = importlib.util.find_spec('PySide6') is not None
PROJECT = Path(__file__).resolve().parents[1]


class StudioCompatibilityTests(unittest.TestCase):
    def test_app_command_has_actionable_error_without_extra(self):
        result = subprocess.run([sys.executable, '-S', '-m', 'petarelasi', 'app'], cwd=PROJECT,
                                capture_output=True, encoding='utf-8', timeout=10,
                                env=os.environ | {'PYTHONIOENCODING': 'utf-8'})
        self.assertEqual(result.returncode, 2)
        self.assertIn('pip install ".[app]"', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_learning_notes_escape_user_identifiers(self):
        schema = validate({'version': 1, 'tables': [{'name': '<img src=x>', 'columns': [
            {'name': '<script>', 'type': 'INT', 'pk': 1}]}], 'foreign_keys': []})
        notes = table_notes(schema, '<img src=x>', '<script>')
        self.assertNotIn('<img src=x>', notes)
        self.assertNotIn('<script>', notes)
        self.assertIn('&lt;script&gt;', notes)


@unittest.skipUnless(HAS_SQL, 'Pasang extra sql/app untuk tes sesi Studio.')
class StudioSessionTests(unittest.TestCase):
    def test_sql_to_learning_to_focused_export_complete_flow(self):
        schema = read_sql_text(next(iter(EXAMPLES.values())), 'sqlite')
        session = Session()
        session.replace(schema, 'contoh')
        ref = next(item for item in schema.foreign_keys if len(item.columns) == 2)
        self.assertIn('Satu FK gabungan', relation_notes(ref))
        self.assertIn('PK2', table_notes(schema, 'anggota', 'kode'))
        session.set_focus('anggota', 1)
        with TemporaryDirectory() as temp:
            output = Path(temp) / 'focus.drawio'
            session.export(output)
            cells = ET.parse(output).findall('.//mxCell[@parent="1"][@vertex="1"]')
            self.assertEqual([item.get('value') for item in cells], ['anggota', 'pinjam'])
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                session.export(output)
            self.assertEqual(output.read_bytes(), before)


if HAS_QT and HAS_SQL:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import QPointF, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton
    from petarelasi.layout import HEADER, ROW, WIDTH
    from petarelasi.studio.window import StudioWindow


@unittest.skipUnless(HAS_QT and HAS_SQL, 'Pasang extra app untuk tes GUI Qt.')
class StudioGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        settings = QSettings(str(self.root / 'preferences.ini'), QSettings.Format.IniFormat)
        self.window = StudioWindow(settings)
        self.window.resize(1400, 850)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.wait_until(lambda: not self.window.busy)
        self.window.close()
        self.app.processEvents()
        self.temporary.cleanup()

    def wait_until(self, predicate, timeout=8):
        deadline = monotonic() + timeout
        while not predicate():
            if monotonic() > deadline:
                self.fail('Operasi GUI tidak selesai dalam batas waktu.')
            QTest.qWait(10)
        self.app.processEvents()

    def import_sql(self, text, dialect='sqlite'):
        self.window.input_tabs.setCurrentIndex(1)
        self.window.sql_editor.setPlainText(text)
        self.window.dialect.setCurrentIndex(self.window.dialect.findData(dialect))
        QTest.mouseClick(self.window.build_button, Qt.MouseButton.LeftButton)
        self.assertTrue(self.window.busy)
        self.wait_until(lambda: not self.window.busy)

    def test_click_actual_column_displays_pk_order_and_highlight(self):
        item = self.window.view.tables['anggota']
        position = self.window.view.mapFromScene(item.pos() + QPointF(WIDTH / 2, HEADER + ROW / 2))
        QTest.mouseClick(self.window.view.viewport(), Qt.MouseButton.LeftButton, pos=position)
        self.assertEqual(self.window.selected_table, 'anggota')
        self.assertIn('PK2', self.window.notes.toPlainText())
        self.assertEqual(item.active_column, 'kode')

    def test_click_composite_wire_shows_all_column_pairs(self):
        edge = next(item for item in self.window.view.edges if len(item[4].columns) == 2)
        wire = edge[3]
        x = (wire.points[2][0] + wire.points[3][0]) / 2
        y = wire.points[2][1]
        position = self.window.view.mapFromScene(QPointF(x, y))
        QTest.mouseClick(self.window.view.viewport(), Qt.MouseButton.LeftButton, pos=position)
        text = self.window.notes.toPlainText()
        self.assertIn('Satu FK gabungan, 2 pasangan', text)
        self.assertIn('unit_anggota', text)
        self.assertIn('kode_anggota', text)

    def test_file_dialog_import_and_export_button_produce_real_drawio(self):
        source = PROJECT / 'contoh' / 'mysql.sql'
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(source), '')):
            QTest.mouseClick(self.window.open_button, Qt.MouseButton.LeftButton)
        self.window.dialect.setCurrentIndex(self.window.dialect.findData('mysql'))
        QTest.mouseClick(self.window.build_button, Qt.MouseButton.LeftButton)
        self.wait_until(lambda: not self.window.busy)
        self.assertEqual(len(self.window.session.schema.tables), 3)
        self.assertEqual(self.window.session.label, 'mysql.sql')
        output = self.root / 'from-ui.drawio'
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(output), '')):
            QTest.mouseClick(self.window.export_button, Qt.MouseButton.LeftButton)
        self.assertTrue(output.is_file())
        self.assertEqual(len(ET.parse(output).findall('.//mxCell[@edge="1"]')), 4)
        self.assertFalse(self.window.error_label.isVisible())

    def test_sqlite_file_and_exported_json_can_both_be_reopened(self):
        import sqlite3
        from contextlib import closing
        source = self.root / 'kampus.sqlite'
        with closing(sqlite3.connect(source)) as db:
            db.executescript('CREATE TABLE p(id INTEGER PRIMARY KEY); CREATE TABLE c(p INT REFERENCES p(id));')
        before = source.read_bytes()
        self.window.prepare_file(source)
        QTest.mouseClick(self.window.build_button, Qt.MouseButton.LeftButton)
        self.wait_until(lambda: not self.window.busy)
        self.assertEqual(len(self.window.view.tables), 2)
        self.assertEqual(len(self.window.view.edges), 1)
        self.assertEqual(source.read_bytes(), before)
        snapshot = self.root / 'reopen.json'
        self.assertTrue(self.window.export_to(snapshot))
        self.window.prepare_file(snapshot)
        QTest.mouseClick(self.window.build_button, Qt.MouseButton.LeftButton)
        self.wait_until(lambda: not self.window.busy)
        self.assertEqual(len(self.window.view.edges), 1)
        self.assertFalse(self.window.sql_options.isVisible())

    def test_failed_import_preserves_schema_scene_focus_and_export(self):
        focus = self.window.focus_combo.findData('anggota')
        self.window.focus_combo.setCurrentIndex(focus)
        before = self.window.session.schema
        visible = self.window.session.visible
        diagram = self.window.view.diagram
        self.import_sql('CREATE TABLE salah (id INT REFERENCES hilang(id));', 'postgres')
        self.assertIs(self.window.session.schema, before)
        self.assertIs(self.window.session.visible, visible)
        self.assertEqual(self.window.view.diagram, diagram)
        self.assertEqual(self.window.session.focus, 'anggota')
        self.assertTrue(self.window.error_label.isVisible())
        self.assertIn('sebelumnya tetap', self.window.error_label.text())
        self.assertTrue(self.window.export_button.isEnabled())
        self.assertTrue(self.window.export_to(self.root / 'preserved.drawio'))
        self.assertEqual(len(ET.parse(self.root / 'preserved.drawio').findall('.//mxCell[@edge="1"]')), 2)

    def test_pasted_sql_loads_then_can_recover_after_parse_failure(self):
        self.import_sql('CREATE TABLE x(id INT PRIMARY KEY);', 'postgres')
        self.assertEqual(self.window.session.schema.tables[0].name, 'public.x')
        self.import_sql('CREATE TABLE broken(', 'postgres')
        self.assertEqual(self.window.session.schema.tables[0].name, 'public.x')
        self.import_sql('CREATE TABLE baru(id INT PRIMARY KEY);', 'mysql')
        self.assertEqual(self.window.session.schema.tables[0].name, 'baru')
        self.assertFalse(self.window.error_label.isVisible())

    def test_focus_search_and_all_export_formats_follow_visible_tables(self):
        self.window.search.setText('buku')
        visible_list = [self.window.table_list.item(i).data(Qt.ItemDataRole.UserRole)
                        for i in range(self.window.table_list.count()) if not self.window.table_list.item(i).isHidden()]
        self.assertEqual(visible_list, ['buku'])
        self.window.focus_combo.setCurrentIndex(self.window.focus_combo.findData('buku'))
        self.window.radius.setValue(0)
        self.assertEqual(list(self.window.view.tables), ['buku'])
        self.assertEqual(len(self.window.view.edges), 1)
        for extension in ['.drawio', '.svg', '.json']:
            output = self.root / ('focused' + extension)
            self.assertTrue(self.window.export_to(output))
        import json
        data = json.loads((self.root / 'focused.json').read_text())
        self.assertEqual([t['name'] for t in data['tables']], ['buku'])
        self.assertEqual(len(data['foreign_keys']), 1)
        self.window.focus_combo.setCurrentIndex(0)
        self.assertEqual(len(self.window.view.tables), 4)

    def test_existing_output_protection_is_reported_in_interface(self):
        output = self.root / 'protected.drawio'
        output.write_bytes(b'keep me')
        self.assertFalse(self.window.export_to(output))
        self.assertEqual(output.read_bytes(), b'keep me')
        self.assertIn('Ekspor gagal', self.window.error_label.text())

    def test_sql_changes_are_marked_until_next_successful_import(self):
        self.window.sql_editor.appendPlainText('-- Catatan belajar')
        self.assertTrue(self.window.draft_note.isVisible())
        self.import_sql('CREATE TABLE x(id INT PRIMARY KEY);')
        self.assertFalse(self.window.draft_note.isVisible())

    def test_zoom_buttons_fit_and_small_window_remain_usable(self):
        self.window.resize(1200, 720)
        self.app.processEvents()
        before = self.window.view.transform().m11()
        plus = next(b for b in self.window.findChildren(QPushButton) if b.text() == '+')
        QTest.mouseClick(plus, Qt.MouseButton.LeftButton)
        self.assertGreater(self.window.view.transform().m11(), before)
        fit = next(b for b in self.window.findChildren(QPushButton) if b.text() == 'Pas layar')
        QTest.mouseClick(fit, Qt.MouseButton.LeftButton)
        self.assertLessEqual(self.window.view.transform().m11(), 1.15)
        self.assertTrue(self.window.build_button.isVisible())
        self.assertTrue(self.window.export_button.isVisible())
        self.assertGreaterEqual(self.window.view.viewport().width(), 400)

    def test_closing_during_import_waits_for_worker_instead_of_terminating_it(self):
        from threading import Event
        release = Event()
        original = read_sql_text

        def delayed(*args):
            release.wait(4)
            return original(*args)

        with patch('petarelasi.studio.window.read_sql_text', side_effect=delayed):
            self.window.import_source()
            self.assertTrue(self.window.busy)
            self.window.close()
            self.assertTrue(self.window.isVisible())
            self.assertTrue(self.window.pending_close)
            release.set()
            self.wait_until(lambda: not self.window.busy)
            self.assertFalse(self.window.isVisible())
