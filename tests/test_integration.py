from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from petarelasi.layout import HEADER, ROW, WIDTH, layout
from petarelasi.schema import sqlite_snapshot, validate


PROJECT = Path(__file__).resolve().parents[1]
NS = {"svg": "http://www.w3.org/2000/svg"}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.demo = self.root / "demo"
        self.cli("demo", self.demo)
        self.db = self.demo / "perpustakaan.sqlite"
        self.snapshot = self.demo / "skema.json"

    def cli(self, *args, expected=0):
        result = subprocess.run(
            [sys.executable, "-m", "petarelasi", *map(str, args)], cwd=PROJECT,
            capture_output=True, encoding="utf-8", timeout=15,
            env=os.environ | {"PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result.stdout if expected == 0 else result.stderr

    def schema(self):
        return json.loads(self.snapshot.read_text(encoding="utf-8"))

    def write_json(self, schema):
        path = self.root / "custom.json"
        path.write_text(json.dumps(schema), encoding="utf-8")
        return path

    def test_demo_complete_and_input_database_is_read_only(self):
        before = sha256(self.db.read_bytes()).hexdigest()
        exported = self.root / "inspect.json"
        self.assertIn("4 tabel, 4 foreign key", self.cli("snapshot", self.db, exported))
        self.assertEqual(exported.read_bytes(), self.snapshot.read_bytes())
        self.assertEqual(sha256(self.db.read_bytes()).hexdigest(), before)
        self.assertEqual(len(ET.parse(self.demo / "erd.drawio").findall(".//mxCell[@edge='1']")), 5)
        self.assertEqual(len(ET.parse(self.demo / "erd.svg").findall(".//svg:polygon", NS)), 5)

    def test_implicit_composite_fk_uses_pk_order_not_column_position(self):
        relation = next(r for r in self.schema()["foreign_keys"] if r["references"] == "anggota")
        self.assertEqual(relation["columns"], ["unit_anggota", "kode_anggota"])
        self.assertEqual(relation["ref_columns"], ["unit", "kode"])

    def test_drawio_links_real_column_vertices(self):
        cells = {c.get("id"): c for c in ET.parse(self.demo / "erd.drawio").findall(".//mxCell")}
        actual = {}
        for edge in (c for c in cells.values() if c.get("edge") == "1"):
            left, right = cells[edge.get("source")], cells[edge.get("target")]
            self.assertEqual(left.get("vertex"), "1")
            self.assertEqual(right.get("vertex"), "1")
            self.assertIsNotNone(edge.find("mxGeometry/Array[@as='points']"))
            actual[cells[left.get("parent")].get("value"), left.get("value")] = (
                cells[right.get("parent")].get("value"), right.get("value"),
            )
        self.assertEqual(actual["pinjam", "[FK] unit_anggota  ·  TEXT"], ("anggota", "[PK1] unit  ·  TEXT"))
        self.assertEqual(actual["pinjam", "[FK] kode_anggota  ·  TEXT"], ("anggota", "[PK2] kode  ·  TEXT"))
        self.assertEqual(actual["buku", "[FK] buku_induk  ·  INTEGER"], ("buku", "[PK1] id  ·  INTEGER"))

    def test_layout_polyline_does_not_enter_any_box_interior(self):
        diagram = layout(sqlite_snapshot(self.db))
        for wire in diagram.wires:
            self.assertEqual(wire.points[0], wire.source.port(wire.source_row, wire.source_side, target=False))
            self.assertEqual(wire.points[-1], wire.target.port(wire.target_row, wire.target_side, target=True))
            for (x1, y1), (x2, y2) in zip(wire.points, wire.points[1:]):
                self.assertTrue(x1 == x2 or y1 == y2)
                for box in diagram.boxes:
                    left, top, right, bottom = box.x, box.y, box.x + WIDTH, box.y + box.height
                    if x1 == x2:
                        crossed = left < x1 < right and max(min(y1, y2), top) < min(max(y1, y2), bottom)
                    else:
                        crossed = top < y1 < bottom and max(min(x1, x2), left) < min(max(x1, x2), right)
                    self.assertFalse(crossed, (wire.key, box.key))

    def test_svg_endpoints_align_with_row_geometry(self):
        svg = ET.parse(self.demo / "erd.svg")
        rows = {n.get("id"): n for n in svg.findall(".//svg:text", NS) if n.get("id")}
        for line in svg.findall(".//svg:polyline", NS):
            pts = [tuple(map(int, point.split(","))) for point in line.get("points").split()]
            for attr, position, offset in [("data-source", 0, -8), ("data-target", -1, 0)]:
                row = rows[line.get(attr)]
                self.assertEqual(pts[position][1], int(row.get("y")) + offset)

    def test_sqlite_and_shuffled_json_produce_identical_files(self):
        data = self.schema()
        data["tables"].reverse()
        data["foreign_keys"].reverse()
        source = self.write_json(data)
        for extension in ("drawio", "svg"):
            with self.subTest(extension=extension):
                a = self.root / ("a." + extension)
                b = self.root / ("b." + extension)
                self.cli("render", self.db, a)
                self.cli("render", source, b)
                self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_focus_radius_zero_keeps_self_reference(self):
        out = self.root / "buku.drawio"
        self.assertIn("1 tabel, 1 sambungan kolom", self.cli("render", self.snapshot, out, "--focus", "buku", "--radius", 0))
        self.assertEqual(len(ET.parse(out).findall(".//mxCell[@edge='1']")), 1)

    def test_focus_radius_one_keeps_only_incident_tables_and_composite(self):
        out = self.root / "fokus.drawio"
        self.assertIn("2 tabel, 2 sambungan kolom", self.cli("render", self.snapshot, out, "--focus", "anggota"))
        names = [c.get("value") for c in ET.parse(out).findall(".//mxCell[@parent='1'][@vertex='1']")]
        self.assertEqual(names, ["anggota", "pinjam"])

    def test_invalid_json_reference_leaves_no_output(self):
        schema = self.schema()
        schema["foreign_keys"][0]["ref_columns"][0] = "kolom_hilang"
        out = self.root / "invalid.svg"
        self.assertIn("Kolom relasi tidak ditemukan", self.cli("render", self.write_json(schema), out, expected=2))
        self.assertFalse(out.exists())

    def test_broken_sqlite_parent_and_implicit_arity_are_reported(self):
        for script, message in [
            ("CREATE TABLE salah (kode REFERENCES hilang);", "Tabel tujuan tidak ditemukan"),
            ("CREATE TABLE induk (a,b,PRIMARY KEY(a,b)); CREATE TABLE salah (a REFERENCES induk);",
             "Primary key tujuan tidak cocok"),
        ]:
            with self.subTest(script=script):
                path = self.root / "rusak.sqlite"
                with closing(sqlite3.connect(path)) as db:
                    db.executescript(script)
                out = self.root / "gagal.drawio"
                self.assertIn(message, self.cli("render", path, out, expected=2))
                self.assertFalse(out.exists())
                path.unlink()

    def test_quoted_identifiers_and_ascii_case_match_are_preserved(self):
        path = self.root / "db khusus ?.sqlite"
        if os.name == "nt":
            path = self.root / "db khusus #.sqlite"
        with closing(sqlite3.connect(path)) as db:
            db.executescript('CREATE TABLE "A&B" ("K<e>y" INTEGER PRIMARY KEY);'
                             'CREATE TABLE "X "" Y" ("Kolom" INTEGER REFERENCES "a&b"("k<e>y"));')
        output = self.root / "khusus.drawio"
        self.cli("render", path, output)
        content = ET.parse(output)
        self.assertIsNotNone(content.find(".//mxCell[@value='A&B']"))
        self.assertIsNotNone(content.find(".//mxCell[@value='[PK1] K<e>y  ·  INTEGER']"))
        self.assertEqual(len(content.findall(".//mxCell[@edge='1']")), 1)

    def test_existing_output_is_protected_and_missing_db_not_created(self):
        existing = self.demo / "erd.svg"
        before = existing.read_bytes()
        self.cli("render", self.db, existing, expected=2)
        self.assertEqual(existing.read_bytes(), before)
        missing = self.root / "missing.sqlite"
        self.cli("snapshot", missing, self.root / "empty.json", expected=2)
        self.assertFalse(missing.exists())

    def test_unknown_focus_and_radius_without_focus_are_rejected(self):
        out = self.root / "gagal.svg"
        self.assertIn("tidak ditemukan", self.cli("render", self.db, out, "--focus", "asing", expected=2))
        self.assertIn("memerlukan --focus", self.cli("render", self.db, out, "--radius", 2, expected=2))
        self.assertFalse(out.exists())

    def test_mutual_relations_and_rows_in_same_column_use_distinct_tracks(self):
        tables = [{"name": name, "columns": [{"name": "id", "type": "INT", "pk": 1}]}
                  for name in ("a", "b", "c", "d", "e")]
        references = [{"table": left, "columns": ["id"], "references": right, "ref_columns": ["id"]}
                      for left, right in [("a", "d"), ("d", "a"), ("d", "d"), ("e", "a")]]
        diagram = layout(validate({"version": 1, "tables": tables, "foreign_keys": references}))
        self.assertEqual(len(diagram.wires), 4)
        self.assertEqual(len({w.points[2][1] for w in diagram.wires}), 4)
        self.assertEqual(len({x for wire in diagram.wires for x in (wire.points[1][0], wire.points[4][0])}), 8)
        for box in diagram.boxes:
            self.assertEqual(box.height, HEADER + ROW)


if __name__ == "__main__":
    unittest.main()
