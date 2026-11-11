"""Reflect existing database metadata through optional SQLAlchemy drivers."""

import os
import re

from .schema import SchemaError, clean, validate
from .sql_source import qualified_name


MAX_TABLES = 48


def reflect_schema(inspector, dialect: str, schema: str | None = None):
    namespace = schema or inspector.default_schema_name
    if not namespace:
        raise SchemaError("Schema/database bawaan tidak diketahui. Tambahkan --schema NAMA.")
    clean(namespace, "Nama schema")
    names = inspector.get_table_names(schema=namespace)
    if len(names) > MAX_TABLES:
        raise SchemaError("Schema memuat lebih dari 48 tabel.")
    pending = [(namespace, name) for name in sorted(names)]
    tables = {}
    references = []
    position = 0
    columns_seen = 0
    while position < len(pending):
        owner, name = pending[position]
        position += 1
        key = (owner, name)
        if key in tables:
            continue
        if len(tables) >= MAX_TABLES:
            raise SchemaError("Tabel beserta induk lintas schema melebihi batas 48.")
        primary = inspector.get_pk_constraint(name, schema=owner).get("constrained_columns") or []
        columns = []
        for column in inspector.get_columns(name, schema=owner):
            kind = column["type"]
            kind_text = kind.compile(dialect=inspector.bind.dialect)
            columns.append({"name": column["name"], "type": kind_text,
                            "pk": primary.index(column["name"]) + 1 if column["name"] in primary else 0})
        columns_seen += len(columns)
        if columns_seen > 600:
            raise SchemaError("Maksimal 600 kolom.")
        tables[key] = {"name": qualified_name((owner, name)), "columns": columns}
        options = {"postgresql_ignore_search_path": True} if dialect == "postgresql" else {}
        for relation in inspector.get_foreign_keys(name, schema=owner, **options):
            target_schema = relation.get("referred_schema") or owner
            target_table = relation.get("referred_table")
            local = relation.get("constrained_columns")
            remote = relation.get("referred_columns")
            if not target_table or not local or not remote or any(value is None for value in remote):
                raise SchemaError("Metadata foreign key belum lengkap. Coba ekspor SQL struktur.")
            references.append({"table": qualified_name((owner, name)), "columns": list(local),
                               "references": qualified_name((target_schema, target_table)),
                               "ref_columns": list(remote)})
            if len(references) > 100:
                raise SchemaError("Maksimal 100 foreign key.")
            target = (target_schema, target_table)
            if target not in tables and target not in pending[position:]:
                pending.append(target)
    return validate({"version": 1, "tables": list(tables.values()), "foreign_keys": references})


def live_snapshot(variable: str, schema: str | None = None):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable):
        raise SchemaError("Sumber env: harus diikuti nama environment variable yang valid.")
    raw_url = os.environ.get(variable)
    if not raw_url:
        raise SchemaError(f"Environment variable {variable} belum diisi.")
    try:
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.engine import make_url
        from sqlalchemy.pool import NullPool
    except ImportError as exc:
        raise SchemaError('Dukungan koneksi belum dipasang. Jalankan python -m pip install ".[postgres]" atau ".[mysql]".') from exc

    engine = None
    try:
        url = make_url(raw_url)
        backend = url.get_backend_name()
        if backend in {"postgres", "postgresql"}:
            url = url.set(drivername="postgresql+psycopg")
            connect_args = {"connect_timeout": 5}
        elif backend in {"mysql", "mariadb"}:
            url = url.set(drivername=backend + "+pymysql")
            connect_args = {"connect_timeout": 5, "read_timeout": 15, "write_timeout": 15}
        elif backend == "sqlite":
            # Useful for local metadata reflection and automated integration checks.
            if not url.database or url.database == ":memory:":
                raise SchemaError("URL SQLite perlu merujuk database file yang sudah ada.")
            from pathlib import Path
            if not Path(url.database).is_file():
                raise SchemaError("Database SQLite pada environment variable tidak ditemukan.")
            url = url.set(drivername="sqlite+pysqlite")
            connect_args = {"timeout": 5}
        else:
            raise SchemaError("Koneksi langsung mendukung PostgreSQL, MySQL/MariaDB, dan SQLite.")
        engine = create_engine(url, connect_args=connect_args, poolclass=NullPool, hide_parameters=True)
        with engine.connect() as connection:
            if backend in {"postgres", "postgresql"}:
                connection = connection.execution_options(isolation_level="REPEATABLE READ",
                                                          postgresql_readonly=True)
            elif backend in {"mysql", "mariadb"}:
                connection = connection.execution_options(isolation_level="REPEATABLE READ")
            with connection.begin():
                return reflect_schema(inspect(connection), engine.dialect.name, schema)
    except SchemaError:
        raise
    except (ImportError, ModuleNotFoundError) as exc:
        raise SchemaError('Driver belum tersedia. Pasang extra "postgres" atau "mysql" yang sesuai.') from exc
    except Exception as exc:
        # Driver diagnostics may contain connection URLs or passwords.
        raise SchemaError("Koneksi atau pembacaan metadata gagal. Periksa URL, schema, driver, dan izin baca metadata.") from exc
    finally:
        if engine is not None:
            engine.dispose()
