from collections import defaultdict, deque
from contextlib import closing
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    pk: int


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class Reference:
    table: str
    columns: tuple[str, ...]
    references: str
    ref_columns: tuple[str, ...]


@dataclass(frozen=True)
class Schema:
    tables: tuple[Table, ...]
    foreign_keys: tuple[Reference, ...]

    def snapshot(self) -> dict:
        return {"version": 1, **asdict(self)}

    def focus(self, name: str, radius: int) -> "Schema":
        if name not in {table.name for table in self.tables}:
            raise SchemaError(f"Tabel {name!r} tidak ditemukan.")
        neighbors: dict[str, set[str]] = defaultdict(set)
        for edge in self.foreign_keys:
            neighbors[edge.table].add(edge.references)
            neighbors[edge.references].add(edge.table)
        visible = {name}
        pending = deque([(name, 0)])
        while pending:
            current, distance = pending.popleft()
            if distance == radius:
                continue
            for other in sorted(neighbors[current] - visible):
                visible.add(other)
                pending.append((other, distance + 1))
        return Schema(tuple(t for t in self.tables if t.name in visible),
                      tuple(e for e in self.foreign_keys if e.table in visible and e.references in visible))


def clean(value, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 120 or (not empty and not value):
        raise SchemaError(f"{label} harus berupa teks dengan panjang maksimal 120 karakter.")
    if value and not value.isprintable():
        raise SchemaError(f"{label} memuat karakter yang tidak dapat dicetak.")
    return value


def sequence(value, label: str, limit: int, *, empty: bool = False) -> list:
    if not isinstance(value, list) or len(value) > limit or (not empty and not value):
        raise SchemaError(f"{label} harus berupa daftar dengan maksimal {limit} item.")
    return value


def validate(data) -> Schema:
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise SchemaError("Snapshot harus berupa objek dengan version 1.")
    tables = {}
    column_names = {}
    total_columns = 0
    for raw in sequence(data.get("tables"), "tables", 48):
        if not isinstance(raw, dict):
            raise SchemaError("Entri tabel harus berupa objek.")
        name = clean(raw.get("name"), "Nama tabel")
        if name in tables:
            raise SchemaError(f"Tabel berulang: {name}.")
        columns = []
        seen = set()
        for item in sequence(raw.get("columns"), f"Kolom {name}", 120):
            if not isinstance(item, dict):
                raise SchemaError("Entri kolom harus berupa objek.")
            column = clean(item.get("name"), "Nama kolom")
            if column in seen:
                raise SchemaError(f"Kolom berulang: {name}.{column}.")
            seen.add(column)
            kind = clean(item.get("type"), "Tipe kolom", empty=True)
            pk = item.get("pk")
            if type(pk) is not int or not 0 <= pk <= 120:
                raise SchemaError(f"Urutan primary key tidak valid pada {name}.{column}.")
            columns.append(Column(column, kind, pk))
        numbers = sorted(c.pk for c in columns if c.pk)
        if numbers != list(range(1, len(numbers) + 1)):
            raise SchemaError(f"Urutan primary key {name} harus berurutan mulai dari 1.")
        total_columns += len(columns)
        if total_columns > 600:
            raise SchemaError("Maksimal 600 kolom dalam satu snapshot.")
        tables[name] = Table(name, tuple(columns))
        column_names[name] = seen

    refs = []
    pairs = 0
    for raw in sequence(data.get("foreign_keys"), "foreign_keys", 100, empty=True):
        if not isinstance(raw, dict):
            raise SchemaError("Entri foreign key harus berupa objek.")
        table = clean(raw.get("table"), "Tabel asal")
        target = clean(raw.get("references"), "Tabel tujuan")
        if table not in tables or target not in tables:
            raise SchemaError(f"Tabel pada relasi {table} → {target} tidak ditemukan.")
        columns = tuple(clean(c, "Kolom asal") for c in sequence(raw.get("columns"), "columns", 120))
        target_columns = tuple(clean(c, "Kolom tujuan") for c in sequence(raw.get("ref_columns"), "ref_columns", 120))
        if len(columns) != len(target_columns):
            raise SchemaError(f"Jumlah kolom tidak cocok pada relasi {table} → {target}.")
        for owner, names in [(table, columns), (target, target_columns)]:
            for name in names:
                if name not in column_names[owner]:
                    raise SchemaError(f"Kolom relasi tidak ditemukan: {owner}.{name}.")
        pairs += len(columns)
        if pairs > 120:
            raise SchemaError("Maksimal 120 pasangan kolom relasi.")
        refs.append(Reference(table, columns, target, target_columns))
    return Schema(tuple(tables[name] for name in sorted(tables)),
                  tuple(sorted(refs, key=lambda r: (r.table, r.columns, r.references, r.ref_columns))))


ASCII_FOLD = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def sqlite_snapshot(path: Path) -> Schema:
    if not path.is_file():
        raise SchemaError("Berkas database SQLite tidak ditemukan.")
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, isolation_level=None, timeout=5)) as db:
        db.execute("PRAGMA query_only = ON")
        db.execute("BEGIN")
        names = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND substr(name,1,7)<>'sqlite_' ORDER BY name LIMIT 49"
        )]
        sequence(names, "Tabel SQLite", 48)
        lookup = {name.translate(ASCII_FOLD): name for name in names}
        tables = {}
        for name in names:
            columns = [{"name": col, "type": kind or "", "pk": pk} for col, kind, pk in db.execute(
                "SELECT name, type, pk FROM pragma_table_xinfo(?, 'main') ORDER BY cid LIMIT 121", (name,),
            )]
            tables[name] = columns
        refs = []
        for name in names:
            groups = defaultdict(list)
            for key, _, target, local, remote in db.execute(
                """SELECT id, seq, "table", "from", "to"
                   FROM pragma_foreign_key_list(?, 'main') ORDER BY id, seq LIMIT 121""", (name,),
            ):
                groups[key].append((target, local, remote))
            for group in groups.values():
                target = lookup.get(group[0][0].translate(ASCII_FOLD), group[0][0])
                if target not in tables:
                    raise SchemaError(f"Tabel tujuan tidak ditemukan: {name} → {target}.")
                local_lookup = {c["name"].translate(ASCII_FOLD): c["name"] for c in tables[name]}
                remote_lookup = {c["name"].translate(ASCII_FOLD): c["name"] for c in tables[target]}
                local_columns = [local_lookup.get(row[1].translate(ASCII_FOLD), row[1]) for row in group]
                if any(row[2] is None for row in group):
                    if not all(row[2] is None for row in group):
                        raise SchemaError(f"Relasi implisit tidak konsisten pada {name} → {target}.")
                    primary = sorted((c for c in tables[target] if c["pk"]), key=lambda c: c["pk"])
                    if len(primary) != len(group):
                        raise SchemaError(f"Primary key tujuan tidak cocok pada relasi implisit {name} → {target}.")
                    remote_columns = [c["name"] for c in primary]
                else:
                    remote_columns = [remote_lookup.get(row[2].translate(ASCII_FOLD), row[2]) for row in group]
                refs.append({"table": name, "columns": local_columns, "references": target,
                             "ref_columns": remote_columns})
        return validate({"version": 1, "tables": [{"name": n, "columns": c} for n, c in tables.items()],
                         "foreign_keys": refs})


def read_snapshot(path: Path) -> Schema:
    if not path.is_file():
        raise SchemaError("Berkas snapshot JSON tidak ditemukan.")
    with path.open("rb") as handle:
        data = handle.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise SchemaError("Snapshot melebihi 1 MiB.")
    return validate(json.loads(data.decode("utf-8-sig")))
