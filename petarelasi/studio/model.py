"""Document state and learning notes shared by the desktop UI and its tests."""
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory

from ..__main__ import DEMO, snapshot_bytes, write_new
from ..layout import layout
from ..render import drawio, svg
from ..schema import Reference, Schema, SchemaError
from ..sources import load_source
from ..sql_source import MAX_SQL_BYTES


EXAMPLES = {
    'Perpustakaan · FK gabungan': DEMO,
    'Toko · alur pesanan': '''CREATE TABLE pelanggan (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL
);
CREATE TABLE produk (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL,
    harga INTEGER NOT NULL
);
CREATE TABLE pesanan (
    id INTEGER PRIMARY KEY,
    pelanggan_id INTEGER NOT NULL REFERENCES pelanggan(id),
    dibuat TEXT NOT NULL
);
CREATE TABLE detail_pesanan (
    pesanan_id INTEGER REFERENCES pesanan(id),
    produk_id INTEGER REFERENCES produk(id),
    jumlah INTEGER NOT NULL,
    PRIMARY KEY (pesanan_id, produk_id)
);
''',
}


def read_sql_text(text: str, dialect: str, namespace: str | None = None) -> Schema:
    if not text.strip():
        raise SchemaError('Tempel atau tulis definisi CREATE TABLE terlebih dahulu.')
    raw = text.encode('utf-8')
    if len(raw) > MAX_SQL_BYTES:
        raise SchemaError('Teks SQL melebihi 8 MiB. Gunakan ekspor struktur tanpa data.')
    with TemporaryDirectory(prefix='petarelasi-sql-') as temporary:
        path = Path(temporary) / 'skema.sql'
        path.write_bytes(raw)
        return load_source(path, dialect=dialect, schema=namespace)


def read_file(path, dialect: str, namespace: str | None = None) -> Schema:
    path = Path(path)
    if not path.is_file():
        raise SchemaError('Pilih file SQLite, SQL atau snapshot JSON yang sudah ada.')
    options = {'dialect': dialect, 'schema': namespace} if path.suffix.lower() == '.sql' else {}
    return load_source(path, **options)


class Session:
    """Only a fully parsed schema replaces the previous successful document."""
    def __init__(self):
        self.schema: Schema | None = None
        self.visible: Schema | None = None
        self.label = ''
        self.focus: str | None = None
        self.radius = 1

    def replace(self, schema: Schema, label: str):
        self.schema = self.visible = schema
        self.label = label
        self.focus = None
        self.radius = 1

    def set_focus(self, name: str | None, radius: int):
        if self.schema is None:
            raise SchemaError('Buka skema terlebih dahulu.')
        if not 0 <= radius <= 5:
            raise SchemaError('Radius relasi harus antara 0 dan 5.')
        visible = self.schema.focus(name, radius) if name else self.schema
        self.visible, self.focus, self.radius = visible, name, radius

    def export(self, path):
        if self.visible is None:
            raise SchemaError('Belum ada diagram untuk diekspor.')
        path = Path(path)
        if path.suffix.lower() == '.json':
            payload = snapshot_bytes(self.visible)
        elif path.suffix.lower() in {'.drawio', '.svg'}:
            diagram = layout(self.visible)
            payload = drawio(diagram) if path.suffix.lower() == '.drawio' else svg(diagram)
        else:
            raise SchemaError('Pilih format .drawio, .svg atau .json.')
        write_new(path, payload)


def code(value) -> str:
    return '<code>' + escape(str(value)) + '</code>'


def paragraph(text) -> str:
    return '<p>' + text + '</p>'


def intro_notes() -> str:
    return '''<h2>Mulai dari satu sambungan.</h2>
<p>Klik tabel, baris kolom, atau garis pada diagram. Penjelasan di sini mengikuti skema yang sedang dibuka.</p>
<h3>PK · Primary key</h3><p>Identitas unik baris dalam tabel. PK1, PK2 menunjukkan urutan kolom ketika primary key terdiri dari beberapa kolom.</p>
<h3>FK · Foreign key</h3><p>Kolom yang merujuk kolom pada tabel lain, atau pada tabelnya sendiri. Panah bergerak dari kolom FK menuju kolom yang dirujuk.</p>
<h3>FK gabungan</h3><p>Beberapa kolom membentuk satu referensi. F1.1 dan F1.2 adalah pasangan dari grup FK yang sama, bukan dua relasi terpisah.</p>
<p><b>Coba:</b> pilih contoh Perpustakaan, lalu klik garis antara pinjam dan anggota.</p>
<p>Garis hanya berasal dari FK yang dideklarasikan. Nama kolom seperti user_id saja belum membuktikan adanya relasi.</p>'''


def table_notes(schema: Schema, name: str, column: str = '') -> str:
    table = next(item for item in schema.tables if item.name == name)
    primary = sorted((item for item in table.columns if item.pk), key=lambda item: item.pk)
    outgoing = [ref for ref in schema.foreign_keys if ref.table == name]
    incoming = [ref for ref in schema.foreign_keys if ref.references == name]
    text = '<h2>' + escape(name) + '</h2>'
    text += paragraph(f'{len(table.columns)} kolom · {len(outgoing)} FK keluar · {len(incoming)} FK masuk')
    if column:
        selected = next(item for item in table.columns if item.name == column)
        text += '<h3>' + escape(column) + '</h3>' + paragraph('Tipe data ' + code(selected.type or '(tidak disebutkan)'))
        if selected.pk:
            text += paragraph(f'<b>PK{selected.pk}</b> · bagian ke-{selected.pk} dari primary key ' +
                              ', '.join(code(item.name) for item in primary) + '.')
        else:
            text += paragraph('Kolom ini bukan bagian primary key.')
        matches = [ref for ref in outgoing if column in ref.columns]
        for ref in matches:
            text += relation_notes(ref, heading=False)
        targets = [ref for ref in incoming if column in ref.ref_columns]
        for ref in targets:
            text += paragraph('Dirujuk oleh ' + code(ref.table) + ' melalui ' + ', '.join(code(c) for c in ref.columns) + '.')
        if not matches and not targets:
            text += paragraph('Tidak ada sambungan foreign key pada kolom ini dalam skema.')
    else:
        text += '<h3>Identitas tabel</h3>'
        text += paragraph('Primary key: ' + (', '.join(code(item.name) for item in primary) if primary else 'tidak dideklarasikan') + '.')
        text += paragraph('Klik satu baris kolom untuk melihat perannya dan semua referensi yang melibatkan kolom itu.')
        if not outgoing and not incoming:
            text += paragraph('Tabel ini tidak memiliki FK yang dideklarasikan. PetaRelasi tidak menebak relasi dari nama kolom.')
    return text


def relation_notes(ref: Reference, *, heading=True) -> str:
    text = '<h2>Ikuti referensinya</h2>' if heading else '<h3>Referensi keluar</h3>'
    text += paragraph(code(ref.table) + ' → ' + code(ref.references))
    text += '<table cellspacing="6"><tr><th align="left">Kolom FK</th><th align="left">Kolom tujuan</th></tr>'
    for left, right in zip(ref.columns, ref.ref_columns):
        text += '<tr><td>' + code(left) + '</td><td>→ ' + code(right) + '</td></tr>'
    text += '</table>'
    if len(ref.columns) > 1:
        text += paragraph(f'<b>Satu FK gabungan, {len(ref.columns)} pasangan.</b> Kolom-kolom tersebut membentuk satu referensi bersama. Urutan pasangan mengikuti deklarasi constraint.')
    elif ref.table == ref.references:
        text += paragraph('<b>Relasi mandiri.</b> Tabel ini merujuk kolom pada tabelnya sendiri.')
    else:
        text += paragraph('Panah dimulai dari kolom FK dan berakhir pada kolom yang dirujuk.')
    text += paragraph('Diagram ini menjelaskan struktur. Isi record dan validitas data di dalam tabel tidak diperiksa.')
    return text
