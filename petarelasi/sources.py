from pathlib import Path

from .schema import SchemaError, clean, read_snapshot, sqlite_snapshot
from .sql_source import DIALECTS, sql_snapshot


def load_source(source, *, dialect: str | None = None, schema: str | None = None):
    text = str(source)
    if schema is not None:
        clean(schema, "Nama schema")
    if text.startswith("env:"):
        if dialect is not None:
            raise SchemaError("--dialect hanya dipakai untuk berkas SQL.")
        from .live_source import live_snapshot
        return live_snapshot(text[4:], schema)
    path = Path(source)
    if path.suffix.lower() == ".sql":
        return sql_snapshot(path, dialect, schema)
    if dialect is not None or schema is not None:
        raise SchemaError("--dialect dan --schema dipakai untuk SQL; --schema juga tersedia pada sumber env:NAMA.")
    return read_snapshot(path) if path.suffix.lower() == ".json" else sqlite_snapshot(path)
