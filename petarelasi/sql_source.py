"""Extract declared tables and relationships from SQL exports without executing SQL."""

from contextlib import contextmanager
from dataclasses import dataclass, field
import logging
from pathlib import Path
import re

from .schema import ASCII_FOLD, SchemaError, validate


DIALECTS = ("postgres", "mysql", "tsql", "sqlite")
MAX_SQL_BYTES = 8 * 1024 * 1024


def qualified_name(parts) -> str:
    return ".".join(part if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part)
                    else '"' + part.replace('"', '""') + '"' for part in parts if part)


@contextmanager
def quiet_parser():
    logger = logging.getLogger("sqlglot")
    blocker = lambda record: False
    logger.addFilter(blocker)
    try:
        yield
    finally:
        logger.removeFilter(blocker)


def preprocess(sql, dialect, module):
    """Remove recognized client delimiters using token positions, preserving literals."""
    tokenizer = module.Dialect.get_or_raise(dialect).tokenizer_class
    if dialect == "tsql":
        keywords = tokenizer.KEYWORDS | {"GO": module.TokenType.VAR}
        tokenizer = type("BatchTokenizer", (tokenizer,), {"KEYWORDS": keywords})
    tokens = tokenizer().tokenize(sql)
    edits = []
    for token in tokens:
        if (dialect == "tsql" and token.token_type == module.TokenType.VAR
                and token.text.upper() == "GO"):
            start = sql.rfind("\n", 0, token.start) + 1
            stop = sql.find("\n", token.end + 1)
            stop = len(sql) if stop == -1 else stop
            line = sql[start:stop]
            if re.fullmatch(r"\s*GO\s*(?:--[^\r\n]*)?", line, re.IGNORECASE):
                edits.append((start, stop, ";\n"))
            elif re.fullmatch(r"\s*GO\s+[0-9]+\s*(?:--[^\r\n]*)?", line, re.IGNORECASE):
                raise SchemaError("GO dengan hitungan pengulangan tidak didukung. Ekspor skema tanpa pengulangan batch.")
        elif dialect == "postgres" and token.token_type == module.TokenType.BACKSLASH:
            start = sql.rfind("\n", 0, token.start) + 1
            stop = sql.find("\n", token.end + 1)
            stop = len(sql) if stop == -1 else stop
            line = sql[start:stop]
            if re.fullmatch(r"\\(?:un)?restrict\s+[A-Za-z0-9_]+\s*", line):
                edits.append((start, stop, ""))
            elif sql[start:token.start].strip() == "":
                raise SchemaError("Perintah klien psql tidak didukung. Gunakan pg_dump --schema-only.")
    for start, stop, replacement in sorted(set(edits), reverse=True):
        sql = sql[:start] + replacement + sql[stop:]
    return sql


@dataclass
class Definition:
    key: tuple[str, str, str]
    columns: list[dict] = field(default_factory=list)
    primary: list[str] | None = None


class Builder:
    def __init__(self, dialect, schema, exp):
        self.dialect = dialect
        self.namespace = schema if schema is not None else {"postgres": "public", "tsql": "dbo"}.get(dialect, "")
        self.explicit_schema = schema is not None
        self.search_path_unknown = False
        self.catalog = ""
        self.exp = exp
        self.tables = {}
        self.references = []

    def key(self, table):
        if not isinstance(table, self.exp.Table):
            raise SchemaError("Definisi tabel SQL tidak didukung.")
        if not table.db and self.search_path_unknown and not self.explicit_schema:
            raise SchemaError("Tabel tanpa schema memakai search_path khusus. Tambahkan --schema NAMA.")
        return table.catalog or self.catalog, table.db or self.namespace, table.name

    def column_name(self, expression):
        exp = self.exp
        if isinstance(expression, exp.Ordered):
            expression = expression.this
        if isinstance(expression, exp.Column) and not expression.table:
            expression = expression.this
        if not isinstance(expression, exp.Identifier):
            raise SchemaError("Primary/foreign key harus merujuk kolom biasa.")
        return expression.name

    def primary(self, definition, expressions):
        columns = [self.column_name(node) for node in expressions]
        if not columns or definition.primary is not None:
            raise SchemaError("Primary key kosong atau dideklarasikan lebih dari sekali.")
        definition.primary = columns

    def reference(self, definition, columns, reference):
        target = reference.this
        if isinstance(target, self.exp.Schema):
            remote = [self.column_name(node) for node in target.expressions]
            target = target.this
        else:
            remote = None
        self.references.append((definition.key, columns, self.key(target), remote))
        if len(self.references) > 100:
            raise SchemaError("Maksimal 100 foreign key.")

    def constraint(self, definition, node):
        exp = self.exp
        if isinstance(node, exp.Constraint):
            values = node.expressions
            # SQL Server represents PRIMARY KEY CLUSTERED as two sibling nodes.
            if any(isinstance(value, exp.PrimaryKeyColumnConstraint) for value in values):
                index = next((value for value in values if isinstance(
                    value, (exp.ClusteredColumnConstraint, exp.NonClusteredColumnConstraint))), None)
                if index is None:
                    raise SchemaError("Kolom primary key SQL Server tidak dapat dibaca.")
                self.primary(definition, index.this)
                return
            for value in values:
                self.constraint(definition, value)
        elif isinstance(node, exp.PrimaryKey):
            self.primary(definition, node.expressions)
        elif isinstance(node, exp.ForeignKey):
            self.reference(definition, [self.column_name(value) for value in node.expressions],
                           node.args["reference"])
        elif isinstance(node, (exp.CheckColumnConstraint, exp.UniqueColumnConstraint, exp.IndexColumnConstraint)):
            return
        else:
            raise SchemaError("Constraint tabel SQL belum didukung. Ekspor definisi tabel dengan primary/foreign key biasa.")

    def column(self, definition, node):
        exp = self.exp
        if not isinstance(node.this, exp.Identifier) or node.args.get("kind") is None:
            raise SchemaError("Kolom SQL harus memiliki nama dan tipe yang eksplisit.")
        name = node.name
        definition.columns.append({"name": name, "type": node.args["kind"].sql(dialect=self.dialect), "pk": 0})
        for constraint in node.constraints:
            kind = constraint.args.get("kind")
            if isinstance(kind, exp.PrimaryKeyColumnConstraint):
                self.primary(definition, [node.this])
            elif isinstance(kind, exp.Reference):
                self.reference(definition, [name], kind)

    def resolve(self, key):
        if key in self.tables:
            return key
        if self.dialect == "postgres":
            raise SchemaError("Tabel relasi tidak ditemukan dalam ekspor: " + qualified_name(key) + ".")
        folded = tuple(part.translate(ASCII_FOLD) for part in key)
        matches = [item for item in self.tables
                   if tuple(part.translate(ASCII_FOLD) for part in item) == folded]
        if len(matches) != 1:
            raise SchemaError("Tabel relasi hilang atau ambigu: " + qualified_name(key) + ".")
        return matches[0]

    def resolve_columns(self, definition, names):
        available = [column["name"] for column in definition.columns]
        result = []
        for name in names:
            if name in available:
                result.append(name)
                continue
            matches = ([] if self.dialect == "postgres" else
                       [candidate for candidate in available
                        if candidate.translate(ASCII_FOLD) == name.translate(ASCII_FOLD)])
            if len(matches) != 1:
                raise SchemaError("Kolom relasi tidak ditemukan atau ambigu: "
                                  + qualified_name(definition.key) + "." + name + ".")
            result.append(matches[0])
        return result

    def statement(self, node):
        exp = self.exp
        if isinstance(node, exp.Create) and str(node.args.get("kind", "")).upper() == "TABLE":
            if (not isinstance(node.this, exp.Schema) or node.args.get("expression") is not None
                    or node.args.get("replace")):
                raise SchemaError("CREATE TABLE perlu daftar kolom eksplisit. CREATE AS/LIKE atau REPLACE tidak didukung.")
            if node.find(exp.InheritsProperty, exp.PartitionedByProperty) is not None:
                raise SchemaError("Tabel inheritance/partisi belum didukung. Gunakan introspeksi database atau snapshot JSON lengkap.")
            key = self.key(node.this.this)
            if key in self.tables:
                raise SchemaError("CREATE TABLE berulang: " + qualified_name(key) + ".")
            definition = Definition(key)
            self.tables[key] = definition
            if len(self.tables) > 48:
                raise SchemaError("Maksimal 48 tabel.")
            for entry in node.this.expressions:
                if isinstance(entry, exp.ColumnDef):
                    self.column(definition, entry)
                else:
                    self.constraint(definition, entry)
        elif isinstance(node, exp.Alter) and str(node.args.get("kind", "")).upper() == "TABLE":
            definition = self.tables[self.resolve(self.key(node.this))]
            for action in node.args.get("actions") or []:
                if isinstance(action, exp.AddConstraint):
                    for constraint in action.expressions:
                        self.constraint(definition, constraint)
                elif isinstance(action, exp.AlterColumn) and action.args.get("dtype") is None:
                    # Defaults/nullability do not change the diagram's displayed fields.
                    continue
                elif self.dialect == "mysql" and isinstance(action, exp.ModifyColumn):
                    # phpMyAdmin commonly adds AUTO_INCREMENT with MODIFY after keys.
                    column = action.this
                    if (not isinstance(column, exp.ColumnDef) or column.args.get("position")
                            or any(isinstance(item.args.get("kind"),
                                              (exp.PrimaryKeyColumnConstraint, exp.Reference))
                                   for item in column.constraints)):
                        raise SchemaError("MODIFY dengan perubahan posisi atau relasi belum didukung.")
                    name = self.resolve_columns(definition, [column.name])[0]
                    if column.args.get("kind") is None:
                        raise SchemaError("MODIFY membutuhkan tipe kolom eksplisit.")
                    next(item for item in definition.columns if item["name"] == name)["type"] = column.args["kind"].sql(dialect=self.dialect)
                else:
                    raise SchemaError("ALTER TABLE ini mengubah struktur kolom. Gunakan ekspor skema akhir, bukan skrip migrasi.")
        elif isinstance(node, exp.Use):
            if self.dialect == "tsql":
                self.catalog = node.this.name
            elif self.dialect == "mysql":
                self.namespace = node.this.name
            else:
                raise SchemaError("USE hanya didukung untuk MySQL/MariaDB dan SQL Server.")
        elif isinstance(node, exp.Set):
            if self.dialect == "postgres" and re.search(r"\bsearch_path\b", node.sql(), re.IGNORECASE):
                self.search_path_unknown = True
        elif isinstance(node, exp.Select):
            if self.dialect == "postgres" and re.search(r"\bset_config\s*\(\s*'search_path'", node.sql(), re.IGNORECASE):
                self.search_path_unknown = True
        elif isinstance(node, exp.Drop) and str(node.args.get("kind", "")).upper() == "TABLE":
            if self.key(node.this) in self.tables:
                raise SchemaError("DROP setelah CREATE TABLE tidak didukung. Gunakan ekspor skema akhir.")
        elif isinstance(node, exp.Command):
            command = str(node.this).upper()
            text = str(node.args.get("expression") or "")
            if command == "SET":
                if re.search(r"\bsearch_path\b", text, re.IGNORECASE):
                    self.search_path_unknown = True
            elif command == "ALTER" and (
                re.search(r"\bOWNER\s+TO\b", text, re.IGNORECASE)
                or (self.dialect == "tsql" and re.search(r"\bCHECK\s+CONSTRAINT\b", text, re.IGNORECASE))
            ):
                return
            elif command not in {"COMMENT", "GRANT", "REVOKE"}:
                raise SchemaError("Ada sintaks SQL yang belum dapat dibaca. Gunakan ekspor skema-only dengan dialek yang sesuai.")
        elif isinstance(node, (exp.Set, exp.Select, exp.Insert, exp.Update, exp.Delete,
                               exp.Merge, exp.Create, exp.Alter, exp.Drop, exp.Comment,
                               exp.Grant, exp.Revoke, exp.Transaction, exp.Commit, exp.Rollback,
                               exp.Semicolon)):
            return
        else:
            raise SchemaError("Pernyataan SQL di luar cakupan ekspor skema.")

    def finish(self):
        if not self.tables:
            raise SchemaError("Ekspor tidak memuat CREATE TABLE yang didukung.")
        for definition in self.tables.values():
            names = [column["name"] for column in definition.columns]
            if len(names) != len(set(names)):
                raise SchemaError("Kolom berulang pada " + qualified_name(definition.key) + ".")
            primary = self.resolve_columns(definition, definition.primary or [])
            for index, name in enumerate(primary, 1):
                definition.columns[names.index(name)]["pk"] = index
            definition.primary = primary
        references = []
        for source, local, target, remote in self.references:
            left = self.tables[source]
            target = self.resolve(target)
            right = self.tables[target]
            if remote is None:
                remote = right.primary
                if not remote:
                    raise SchemaError("REFERENCES implisit membutuhkan primary key tujuan.")
            references.append({"table": qualified_name(source),
                               "columns": self.resolve_columns(left, local),
                               "references": qualified_name(target),
                               "ref_columns": self.resolve_columns(right, remote)})
        return validate({"version": 1,
                         "tables": [{"name": qualified_name(key), "columns": table.columns}
                                    for key, table in self.tables.items()],
                         "foreign_keys": references})


def sql_snapshot(path: Path, dialect: str, schema: str | None = None):
    if dialect not in DIALECTS:
        raise SchemaError("Input SQL memerlukan --dialect postgres, mysql, tsql, atau sqlite.")
    try:
        import sqlglot
        from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
    except ImportError as exc:
        raise SchemaError('Dukungan SQL belum dipasang. Jalankan python -m pip install ".[sql]".') from exc
    if not path.is_file():
        raise SchemaError("Berkas SQL tidak ditemukan.")
    with path.open("rb") as handle:
        raw = handle.read(MAX_SQL_BYTES + 1)
    if len(raw) > MAX_SQL_BYTES:
        raise SchemaError("Berkas SQL melebihi 8 MiB. Gunakan ekspor struktur tanpa data.")
    try:
        text = raw.decode("utf-8-sig")
        with quiet_parser():
            text = preprocess(text, dialect, sqlglot)
            nodes = sqlglot.parse(text, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)
    except SchemaError:
        raise
    except (UnicodeError, sqlglot.errors.SqlglotError, RecursionError) as exc:
        raise SchemaError("SQL tidak dapat diparse. Periksa dialek dan gunakan ekspor struktur UTF-8 tanpa blok COPY data.") from exc
    if len(nodes) > 3000:
        raise SchemaError("Ekspor maksimal 3.000 pernyataan.")
    builder = Builder(dialect, schema, sqlglot.exp)
    for index, node in enumerate(nodes, 1):
        if node is None:
            continue
        if dialect == "postgres":
            node = normalize_identifiers(node, dialect=dialect)
        try:
            builder.statement(node)
        except SchemaError as exc:
            raise SchemaError(f"Pernyataan {index}. {exc}") from exc
    return builder.finish()
