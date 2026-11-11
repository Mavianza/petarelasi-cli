"""Input integrations use synthetic schemas only; SQL is never executed."""
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from petarelasi.schema import SchemaError
from petarelasi.sources import load_source

PROJECT = Path(__file__).resolve().parents[1]
HAS_SQL = importlib.util.find_spec('sqlglot') is not None
HAS_LIVE = importlib.util.find_spec('sqlalchemy') is not None


class CliCase(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def cli(self, *args, expected=0, env=None, no_site=False):
        result = subprocess.run(
            [sys.executable, *(['-S'] if no_site else []), '-m', 'petarelasi', *map(str, args)],
            cwd=PROJECT, capture_output=True, encoding='utf-8', timeout=20,
            env=os.environ | {'PYTHONIOENCODING': 'utf-8'} | (env or {}),
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return result

    def sql(self, text):
        path = self.root / 'skema.sql'
        path.write_text(text, encoding='utf-8')
        return path

    def read_sql(self, text, dialect='postgres', **options):
        return load_source(self.sql(text), dialect=dialect, **options)


@unittest.skipUnless(HAS_SQL, 'Pasang extra sql untuk tes input SQL.')
class SqlSourceTests(CliCase):
    def test_four_dialects_generate_connected_drawio_and_snapshot(self):
        for filename, dialect, prefix in [('postgres.sql', 'postgres', 'public.'),
                                          ('mysql.sql', 'mysql', 'perpustakaan.'),
                                          ('sqlserver.sql', 'tsql', 'dbo.'),
                                          ('sqlite.sql', 'sqlite', '')]:
            with self.subTest(dialect=dialect):
                source = PROJECT / 'contoh' / filename
                output = self.root / f'{dialect}.drawio'
                snapshot = self.root / f'{dialect}.json'
                self.cli('render', source, output, '--dialect', dialect)
                self.cli('snapshot', source, snapshot, '--dialect', dialect)
                data = json.loads(snapshot.read_text(encoding='utf-8'))
                self.assertEqual(len(data['tables']), 3)
                self.assertEqual(len(data['foreign_keys']), 3)
                pair = next(item for item in data['foreign_keys'] if item['references'] == prefix + 'anggota')
                self.assertEqual(pair['columns'], ['unit_anggota', 'kode_anggota'])
                self.assertEqual(pair['ref_columns'], ['unit', 'kode'])
                self.assertEqual(len(ET.parse(output).findall('.//mxCell[@edge="1"]')), 4)
                roundtrip = self.root / f'{dialect}-roundtrip.drawio'
                self.cli('render', snapshot, roundtrip)
                self.assertEqual(output.read_bytes(), roundtrip.read_bytes())

    def test_qualified_and_quoted_identifiers_preserve_separate_tables(self):
        schema = self.read_sql('''CREATE TABLE public.Thing (ID int PRIMARY KEY);
            CREATE TABLE archive.thing (id int PRIMARY KEY);
            CREATE TABLE public."A&B" ("Key<1>" int PRIMARY KEY, p int REFERENCES public.Thing(ID));
            CREATE TABLE public.link (p int REFERENCES public."A&B"("Key<1>"));''')
        self.assertEqual([item.name for item in schema.tables],
                         ['archive.thing', 'public."A&B"', 'public.link', 'public.thing'])
        self.assertEqual(schema.foreign_keys[-1].ref_columns, ('Key<1>',))
        output = self.root / 'quoted.drawio'
        self.cli('render', self.root / 'skema.sql', output, '--dialect', 'postgres')
        self.assertIsNotNone(ET.parse(output).find('.//mxCell[@value=\'public."A&B"\']'))

    def test_postgres_forward_reference_and_alter_primary_key_resolve_at_end(self):
        schema = self.read_sql('''CREATE TABLE child (x text, y text, FOREIGN KEY(x,y) REFERENCES parent);
            CREATE TABLE parent (a text,b text); ALTER TABLE parent ADD PRIMARY KEY(b,a);''')
        self.assertEqual(schema.foreign_keys[0].ref_columns, ('b', 'a'))

    def test_sql_declaration_order_produces_identical_diagram_bytes(self):
        declarations = ['CREATE TABLE p (a int PRIMARY KEY);',
                        'CREATE TABLE c (p int REFERENCES p(a));']
        outputs = []
        for index, order in enumerate([declarations, declarations[::-1]]):
            output = self.root / f'order-{index}.drawio'
            self.cli('render', self.sql(' '.join(order)), output, '--dialect', 'postgres')
            outputs.append(output.read_bytes())
        self.assertEqual(outputs[0], outputs[1])

    def test_sqlserver_go_inside_default_literal_is_not_a_delimiter(self):
        schema = self.read_sql("CREATE TABLE [dbo].[x] ([id] int PRIMARY KEY, [v] nvarchar(20) DEFAULT 'a\nGO\nb')\nGO\nCREATE TABLE [dbo].[y] (p int REFERENCES [dbo].[x](id))\nGO -- batch\n", 'tsql')
        self.assertEqual(len(schema.tables), 2)
        self.assertEqual(len(schema.foreign_keys), 1)

    def test_sqlserver_use_preserves_catalog_and_default_dbo(self):
        schema = self.read_sql('''USE [kampus]; CREATE TABLE parent(id int PRIMARY KEY);
            CREATE TABLE dbo.child(p int REFERENCES [kampus].[dbo].[parent](id));''', 'tsql')
        self.assertEqual([t.name for t in schema.tables], ['kampus.dbo.child', 'kampus.dbo.parent'])
        self.assertEqual(schema.foreign_keys[0].references, 'kampus.dbo.parent')

    def test_mysql_use_and_phpmyadmin_modify_keep_key_order(self):
        schema = self.read_sql('''USE `db`; CREATE TABLE p (a int,b int);
            ALTER TABLE p ADD PRIMARY KEY (b,a); ALTER TABLE p MODIFY a bigint NOT NULL AUTO_INCREMENT;
            CREATE TABLE c (a int,b int, FOREIGN KEY(a,b) REFERENCES p(b,a));''', 'mysql')
        parent = next(item for item in schema.tables if item.name == 'db.p')
        self.assertEqual([(item.name, item.pk) for item in parent.columns], [('a', 2), ('b', 1)])
        self.assertEqual(parent.columns[0].type, 'BIGINT')

    def test_custom_search_path_requires_explicit_schema(self):
        for setting in ['SET search_path = other;', 'SET search_path TO other;',
                        "SELECT pg_catalog.set_config('search_path', 'other', false);"]:
            with self.subTest(setting=setting):
                source = setting + ' CREATE TABLE x (id int PRIMARY KEY);'
                with self.assertRaisesRegex(SchemaError, '--schema'):
                    self.read_sql(source)
                self.assertEqual(self.read_sql(source, schema='other').tables[0].name, 'other.x')

    def test_missing_parent_and_wrong_arity_do_not_create_output(self):
        for sql in ['CREATE TABLE c (p int REFERENCES missing(id));',
                    'CREATE TABLE p(a int,b int,PRIMARY KEY(a,b)); CREATE TABLE c(p int REFERENCES p);']:
            with self.subTest(sql=sql):
                output = self.root / 'bad.drawio'
                self.cli('render', self.sql(sql), output, '--dialect', 'postgres', expected=2)
                self.assertFalse(output.exists())

    def test_unsupported_structural_changes_and_batch_repeat_fail(self):
        cases = [('postgres', 'CREATE TABLE p(id int); ALTER TABLE p ADD COLUMN x int;'),
                 ('postgres', 'CREATE TABLE p(id int); DROP TABLE p;'),
                 ('postgres', 'CREATE TABLE p AS SELECT 1 AS id;'),
                 ('postgres', 'CREATE TABLE p(id int); CREATE TABLE c(x int) INHERITS(p);'),
                 ('mysql', 'CREATE TABLE p(id int); ALTER TABLE p RENAME COLUMN id TO k;'),
                 ('mysql', 'CREATE TABLE p(id int,x int); ALTER TABLE p MODIFY x int FIRST;'),
                 ('tsql', 'CREATE TABLE p(id int)\nGO 2\n')]
        for dialect, sql in cases:
            with self.subTest(dialect=dialect, sql=sql):
                output = self.root / 'bad.svg'
                self.cli('render', self.sql(sql), output, '--dialect', dialect, expected=2)
                self.assertFalse(output.exists())

    def test_data_statements_are_not_executed_and_do_not_enter_snapshot(self):
        path = self.sql('CREATE TABLE p (id int PRIMARY KEY); INSERT INTO p VALUES (987654321); DELETE FROM p; UPDATE p SET id=1;')
        before = path.read_bytes()
        snapshot = self.root / 'safe.json'
        self.cli('snapshot', path, snapshot, '--dialect', 'postgres')
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn('987654321', snapshot.read_text())
        self.assertEqual(sorted(item.name for item in self.root.iterdir()), ['safe.json', 'skema.sql'])

    def test_parse_error_does_not_echo_sql_values(self):
        secret = 'PRIVATE_SENTINEL_DO_NOT_PRINT'
        output = self.root / 'bad.svg'
        result = self.cli('render', self.sql("CREATE TABLE x (id int DEFAULT '" + secret), output,
                          '--dialect', 'postgres', expected=2)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertFalse(output.exists())

    def test_sql_dialect_and_utf8_and_size_validation(self):
        source = self.sql('CREATE TABLE p(id int);')
        output = self.root / 'bad.svg'
        self.assertIn('--dialect', self.cli('render', source, output, expected=2).stderr)
        source.write_bytes(b'\xff\xfe')
        self.cli('render', source, output, '--dialect', 'postgres', expected=2)
        source.write_bytes(b' ' * (8 * 1024 * 1024 + 1))
        self.assertIn('8 MiB', self.cli('render', source, output, '--dialect', 'postgres', expected=2).stderr)
        self.assertFalse(output.exists())

    def test_qualified_focus_and_existing_output_protection(self):
        source = PROJECT / 'contoh' / 'postgres.sql'
        output = self.root / 'focus.drawio'
        result = self.cli('render', source, output, '--dialect', 'postgres', '--focus', 'public.anggota')
        self.assertIn('2 tabel, 2 sambungan', result.stdout)
        before = output.read_bytes()
        self.cli('render', source, output, '--dialect', 'postgres', expected=2)
        self.assertEqual(output.read_bytes(), before)


class DependencyTests(CliCase):
    def test_native_demo_still_works_without_optional_packages(self):
        self.cli('demo', self.root / 'demo', no_site=True)
        result = self.cli('render', self.sql('CREATE TABLE x(id int);'), self.root / 'x.svg',
                          '--dialect', 'postgres', no_site=True, expected=2)
        self.assertIn('Dukungan SQL belum dipasang', result.stderr)
        self.assertIn('pip install', result.stderr)

    def test_source_options_are_validated_before_loading(self):
        with self.assertRaisesRegex(SchemaError, '--dialect'):
            load_source('env:MY_DATABASE', dialect='mysql')
        with self.assertRaisesRegex(SchemaError, '--schema'):
            load_source('schema.json', schema='other')


@unittest.skipUnless(HAS_LIVE, 'Pasang extra postgres/mysql untuk tes koneksi.')
class LiveSourceTests(CliCase):
    def test_real_sqlite_metadata_connection_through_cli(self):
        path = self.root / 'database.sqlite'
        with closing(sqlite3.connect(path)) as db:
            db.executescript('CREATE TABLE p(a int,b int,PRIMARY KEY(b,a)); CREATE TABLE c(x int,y int,FOREIGN KEY(x,y) REFERENCES p(b,a));')
        before = path.read_bytes()
        output = self.root / 'live.drawio'
        env = {'PETARELASI_TEST_URL': 'sqlite:///' + path.as_posix()}
        self.cli('render', 'env:PETARELASI_TEST_URL', output, env=env)
        self.assertEqual(len(ET.parse(output).findall('.//mxCell[@edge="1"]')), 2)
        self.assertEqual(path.read_bytes(), before)
        snapshot = self.root / 'live.json'
        self.cli('snapshot', 'env:PETARELASI_TEST_URL', snapshot, env=env)
        data = json.loads(snapshot.read_text())
        self.assertEqual(data['foreign_keys'][0]['ref_columns'], ['b', 'a'])

    def test_environment_errors_and_connection_failures_hide_credentials(self):
        for variable, value in [('BAD-ENV', ''), ('PETARELASI_TEST_URL', ''),
                                ('PETARELASI_TEST_URL', 'not_a_url:PRIVATE_SENTINEL'),
                                ('PETARELASI_TEST_URL', 'postgresql://user:PRIVATE_SENTINEL@127.0.0.1:1/db')]:
            with self.subTest(variable=variable, value=value):
                output = self.root / 'bad.svg'
                result = self.cli('render', 'env:' + variable, output, env={variable: value}, expected=2)
                self.assertNotIn('PRIVATE_SENTINEL', result.stdout + result.stderr)
                self.assertFalse(output.exists())

    def test_missing_sqlite_url_does_not_create_a_database(self):
        missing = self.root / 'missing.sqlite'
        self.cli('render', 'env:PETARELASI_TEST_URL', self.root / 'bad.svg',
                 env={'PETARELASI_TEST_URL': 'sqlite:///' + missing.as_posix()}, expected=2)
        self.assertFalse(missing.exists())

    def test_cross_schema_parent_is_included_and_schema_name_is_preserved(self):
        from sqlalchemy import Integer
        from sqlalchemy.dialects.sqlite import dialect
        from types import SimpleNamespace
        from petarelasi.live_source import reflect_schema

        class Inspector:
            default_schema_name = 'kampus'
            bind = SimpleNamespace(dialect=dialect())

            def get_table_names(self, schema):
                return ['pinjam']

            def get_pk_constraint(self, table, schema):
                return {'constrained_columns': ['id']}

            def get_columns(self, table, schema):
                return [{'name': 'id', 'type': Integer()}]

            def get_foreign_keys(self, table, schema, **kwargs):
                if table == 'pinjam':
                    return [{'constrained_columns': ['id'], 'referred_schema': 'arsip',
                             'referred_table': 'anggota', 'referred_columns': ['id']}]
                return []

        schema = reflect_schema(Inspector(), 'postgresql')
        self.assertEqual([t.name for t in schema.tables], ['arsip.anggota', 'kampus.pinjam'])
        self.assertEqual(schema.foreign_keys[0].references, 'arsip.anggota')

    def test_incomplete_live_metadata_fails_instead_of_dropping_foreign_key(self):
        from petarelasi.live_source import reflect_schema
        from types import SimpleNamespace
        from sqlalchemy import Integer
        from sqlalchemy.dialects.sqlite import dialect
        inspector = SimpleNamespace(
            default_schema_name='main', bind=SimpleNamespace(dialect=dialect()),
            get_table_names=lambda **kw: ['x'], get_pk_constraint=lambda *a, **kw: {},
            get_columns=lambda *a, **kw: [{'name': 'id', 'type': Integer()}],
            get_foreign_keys=lambda *a, **kw: [{'constrained_columns': ['id'], 'referred_table': 'p', 'referred_columns': [None]}],
        )
        with self.assertRaisesRegex(SchemaError, 'belum lengkap'):
            reflect_schema(inspector, 'sqlite')
