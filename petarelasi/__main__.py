import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

from .layout import layout
from .render import drawio, svg
from .schema import read_snapshot, sqlite_snapshot


DEMO = """
CREATE TABLE anggota (
    kode TEXT NOT NULL,
    unit TEXT NOT NULL,
    nama TEXT,
    PRIMARY KEY (unit, kode)
);
CREATE TABLE buku (
    id INTEGER PRIMARY KEY,
    judul TEXT NOT NULL,
    buku_induk INTEGER REFERENCES buku(id)
);
CREATE TABLE pinjam (
    id INTEGER PRIMARY KEY,
    unit_anggota TEXT NOT NULL,
    kode_anggota TEXT NOT NULL,
    buku_id INTEGER NOT NULL REFERENCES buku(id),
    FOREIGN KEY (unit_anggota, kode_anggota) REFERENCES anggota
);
CREATE TABLE pengembalian (
    id INTEGER PRIMARY KEY,
    pinjam_id INTEGER REFERENCES pinjam(id),
    dicatat TEXT
);
"""


def write_new(path: Path, data: bytes) -> None:
    handle = path.open("xb")
    try:
        with handle:
            handle.write(data)
    except (OSError, KeyboardInterrupt):
        path.unlink(missing_ok=True)
        raise


def snapshot_bytes(schema) -> bytes:
    return (json.dumps(schema.snapshot(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PetaRelasi, pembuat ERD dari SQLite atau snapshot JSON.")
    sub = parser.add_subparsers(dest="action", required=True)
    demo = sub.add_parser("demo", help="Buat SQLite, JSON, Draw.io dan SVG contoh.")
    demo.add_argument("directory", type=Path)
    inspect = sub.add_parser("snapshot", help="Simpan struktur SQLite dalam JSON.")
    inspect.add_argument("database", type=Path)
    inspect.add_argument("output", type=Path)
    render = sub.add_parser("render", help="Buat diagram dari SQLite atau snapshot .json.")
    render.add_argument("source", type=Path)
    render.add_argument("output", type=Path, help="Berkas baru .drawio atau .svg.")
    render.add_argument("--focus", help="Nama tabel pusat.")
    render.add_argument("--radius", type=int, choices=range(6), help="Jarak relasi 0–5 dari tabel pusat. Bawaan 1.")
    return parser


def demo(directory: Path) -> None:
    directory.mkdir()
    with closing(sqlite3.connect(directory / "perpustakaan.sqlite")) as db:
        db.executescript(DEMO)
    schema = sqlite_snapshot(directory / "perpustakaan.sqlite")
    diagram = layout(schema)
    write_new(directory / "skema.json", snapshot_bytes(schema))
    write_new(directory / "erd.drawio", drawio(diagram))
    write_new(directory / "erd.svg", svg(diagram))
    print(f"{len(diagram.boxes)} tabel, {len(diagram.wires)} sambungan kolom. Hasil di {directory}.")


def main(argv=None) -> int:
    parser = cli_parser()
    args = parser.parse_args(argv)
    try:
        if args.action == "demo":
            demo(args.directory)
        elif args.action == "snapshot":
            schema = sqlite_snapshot(args.database)
            write_new(args.output, snapshot_bytes(schema))
            print(f"{len(schema.tables)} tabel, {len(schema.foreign_keys)} foreign key. Hasil di {args.output}.")
        else:
            extension = args.output.suffix.lower()
            if extension not in {".drawio", ".svg"}:
                raise ValueError("Keluaran harus berakhiran .drawio atau .svg.")
            if args.radius is not None and args.focus is None:
                raise ValueError("--radius memerlukan --focus.")
            schema = (read_snapshot(args.source) if args.source.suffix.lower() == ".json"
                      else sqlite_snapshot(args.source))
            if args.focus is not None:
                schema = schema.focus(args.focus, args.radius if args.radius is not None else 1)
            diagram = layout(schema)
            write_new(args.output, drawio(diagram) if extension == ".drawio" else svg(diagram))
            print(f"{len(diagram.boxes)} tabel, {len(diagram.wires)} sambungan kolom. Hasil di {args.output}.")
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"Gagal. {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
