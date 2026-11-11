# PetaRelasi 1.2 · Studio & CLI

PetaRelasi Studio adalah aplikasi desktop untuk mengubah struktur database menjadi diagram interaktif dan ERD Draw.io. Buka file atau tempel SQL, jelajahi diagram, lalu klik tabel/kolom/garis untuk memahami primary key dan foreign key. Gunakan ekspor Draw.io untuk menyunting diagram lebih lanjut.

![Antarmuka aktual PetaRelasi Studio, dengan contoh sintetis FK gabungan](docs/studio.png)

## Jalankan aplikasi

**Windows:** siapkan Python 3.10–3.14 64-bit, ekstrak proyek, lalu klik dua kali **`Mulai_Studio.cmd`**. Peluncur membuat lingkungan `.venv` dan memasang dependensi saat pertama digunakan. Proses pertama membutuhkan internet. Pada pembukaan berikutnya, pemasangan dilewati jika versi aplikasi dan dependensi sudah tersedia.

Alternatif dari terminal di folder proyek, juga untuk Linux/macOS:

```powershell
python -m pip install ".[app]"
python -m petarelasi app
```

Perintah `petarelasi-studio` juga tersedia setelah instalasi. Aplikasi berjalan sebagai jendela desktop Qt; tidak membutuhkan server web, akun, atau koneksi internet setelah dependensi terpasang. Mode CLI SQLite/JSON tetap dapat dijalankan tanpa extra aplikasi.

Ini adalah distribusi source dengan peluncur Windows, belum berupa installer `.exe`. Sistem operasi perlu mendukung Qt 6.10. Linux memerlukan lingkungan desktop dan library platform Qt yang sesuai; tes otomatis di sini memakai plugin offscreen. Peluncur `.cmd` belum dijalankan pada Windows nyata.

## Alur penggunaan Studio

1. **Mulai dari contoh.** Saat dibuka, contoh perpustakaan sintetis langsung tampil. Pilih contoh toko untuk melihat alur pelanggan → pesanan → detail pesanan → produk. SQL contoh bisa diedit untuk belajar.
2. **Buka sumber sendiri.** Pada tab **Buka file**, pilih SQLite, ekspor `.sql` UTF-8, atau snapshot `.json`, lalu klik **Buat diagram**. Untuk SQL, pilih dialek dan schema bawaan bila perlu. Tab **Tempel SQL** menerima definisi tabel lengkap. File juga bisa diseret ke area diagram; file SQL menunggu pilihan dialek dan tombol Buat diagram.
3. **Jelajahi.** Cari tabel dari daftar kiri. Gulir mouse untuk zoom, seret area kosong untuk bergeser, dan klik **Pas layar** untuk melihat seluruh diagram. Pilihan **Fokus** dan **Radius** membatasi diagram pada tetangga tabel yang dipilih.
4. **Pelajari.** Klik judul tabel untuk ringkasan. Klik baris kolom untuk tipe, posisi PK, serta referensi masuk/keluar. Klik garis untuk melihat seluruh pasangan kolom dari satu FK; FK gabungan dijelaskan sebagai satu grup. Tombol **Panduan PK & FK** mengembalikan penjelasan dasar.
5. **Ekspor tampilan.** Pilih Draw.io, SVG, atau snapshot JSON di kanan atas. Semua format mengikuti tabel dan relasi dalam fokus saat ini. Untuk mengekspor seluruh skema, pilih **Semua tabel** terlebih dahulu. Zoom dan sorotan belajar hanya berlaku di pratinjau. File yang sudah ada dilindungi dari penimpaan.

Shortcut: **Ctrl+O** memilih file, **Ctrl+Enter** membuat diagram, **Ctrl+S** membuka dialog ekspor. Untuk membuka hasil Draw.io, gunakan **File → Open From → Device** di diagrams.net atau Draw.io Desktop.

## Belajar dari skema yang nyata

- **PK1, PK2, ...** menunjukkan urutan kolom dalam primary key, termasuk jika urutannya berbeda dari urutan kolom tabel.
- **FK** menandai kolom sumber referensi. Panah bergerak dari kolom FK menuju kolom yang dirujuk. Label F1.1/F1.2 menandai pasangan dalam FK gabungan yang sama.
- Panel penjelasan memakai nama dan relasi yang benar-benar ada dalam skema. Nama kolom seperti `user_id` saja tidak dianggap sebagai FK.
- Aplikasi membahas struktur. Isi record, validitas data, kardinalitas wajib/opsional, dan aturan bisnis tidak disimpulkan dari nama kolom.

**Jaminan impor:** hanya hasil pembacaan yang berhasil yang menggantikan dokumen. SQL rusak, target FK hilang, atau file tidak bisa dibaca mempertahankan skema, fokus, dan diagram terakhir yang berhasil. Error terlihat di panel sumber, dan diagram sebelumnya masih bisa diekspor. Pekerjaan impor berjalan di worker agar jendela tetap responsif; penutupan saat impor menunggu worker selesai.

Perubahan pada editor SQL ditandai sampai tombol Buat diagram berhasil dijalankan lagi. Isi SQL/tempelan dan file sumber tidak disimpan sebagai riwayat aplikasi. Preferensi yang disimpan hanya ukuran jendela serta direktori buka/ekspor terakhir. Tempelan SQL diparse melalui file sementara yang dihapus setelah pembacaan. UI tidak menjalankan SQL, tidak mengubah database sumber, dan tidak mengirim file ke server.

Studio saat ini memakai sumber file dan tempelan SQL. Adapter koneksi PostgreSQL/MySQL langsung tetap tersedia melalui CLI dengan status eksperimental seperti dijelaskan di bawah.

## Pilih sumber database

| Sumber | Cara memakai | Status pemeriksaan versi ini |
| --- | --- | --- |
| File SQLite `.sqlite` / `.db` | Langsung berikan path | Tes integrasi dengan database SQLite nyata |
| Ekspor PostgreSQL `.sql` | `--dialect postgres` | Fixture DDL bergaya pg_dump, termasuk PK/FK lewat ALTER |
| Ekspor MySQL / MariaDB `.sql` | `--dialect mysql` | Fixture DDL dengan USE, index, dan ALTER bergaya phpMyAdmin |
| Ekspor SQL Server `.sql` | `--dialect tsql` | Fixture DDL dengan batch GO dan named clustered PK |
| Ekspor SQLite `.sql` | `--dialect sqlite` | Fixture DDL dengan FK gabungan implisit |
| Snapshot `.json` | Langsung berikan path | Tes validasi dan hasil diagram deterministik |
| Koneksi PostgreSQL / MySQL / MariaDB | `env:DATABASE_URL` | **Eksperimental**; belum diuji ke server nyata |
| Koneksi SQLite melalui URL | `env:DATABASE_URL` | Tes integrasi metadata SQLAlchemy dengan file SQLite nyata |

## Instalasi dan percobaan tercepat

Gunakan Python 3.10 atau lebih baru. Unduh proyek, ekstrak, dan buka terminal di folder yang berisi `pyproject.toml`.

```powershell
python -m pip install ".[all]"
python -m petarelasi render contoh/mysql.sql hasil.drawio --dialect mysql
```

```text
3 tabel, 4 sambungan kolom. Hasil di hasil.drawio.
```

Buka `hasil.drawio` melalui **File → Open From → Device** di diagrams.net atau Draw.io Desktop. Tabel, kolom, dan konektornya bisa disunting. Gunakan nama keluaran baru setiap kali; program melindungi file yang sudah ada.

File `contoh/mysql.drawio` juga sudah disertakan dan bisa langsung dibuka untuk melihat hasilnya.

Jika hanya memerlukan file SQL, cukup pasang `python -m pip install ".[sql]"`. Penggunaan file SQLite dan snapshot JSON bisa langsung dijalankan dari folder proyek tanpa dependensi tambahan.

## Dari database sendiri ke Draw.io

### File ekspor SQL

Ekspor **struktur/schema saja** ke satu file `.sql` UTF-8 yang menyertakan tabel induk dan foreign key. Tidak perlu mengekspor isi record. Perintah di bawah membaca file itu secara lokal; SQL tidak dijalankan.

```powershell
python -m petarelasi render skema.sql hasil.drawio --dialect mysql
python -m petarelasi render skema-postgres.sql hasil-pg.drawio --dialect postgres
python -m petarelasi render skema-sqlserver.sql hasil-mssql.drawio --dialect tsql
python -m petarelasi render skema-sqlite.sql hasil-sqlite.drawio --dialect sqlite
```

Untuk PostgreSQL, contoh ekspor melalui CLI resminya:

```powershell
pg_dump --schema-only --no-owner --no-privileges --file=skema-postgres.sql nama_database
```

Untuk MySQL, contoh ekspor struktur tabel:

```powershell
mysqldump --user=nama_user --password --no-data --skip-triggers --no-tablespaces --result-file=skema.sql nama_database
```

Di phpMyAdmin, pilih ekspor **Custom → SQL → Structure** dan sertakan constraint. Di SSMS, gunakan **Tasks → Generate Scripts**, pilih tabel beserta tabel induknya, lalu **Advanced → Types of data to script → Schema only**. Simpan sebagai UTF-8. Pilih objek tabel; routine, trigger, dan fitur skema khusus berada di luar cakupan pembacaan ini.

Nama schema dipertahankan, misalnya `public.anggota` atau `dbo.anggota`. PostgreSQL tanpa prefix memakai `public`, SQL Server memakai `dbo`, dan MySQL mengikuti `USE` bila ada. Untuk ekspor tanpa prefix dengan schema lain, tambahkan `--schema nama_schema`. `--schema` pada input SQL menentukan prefix bawaan, bukan menyaring tabel yang sudah memiliki prefix. `USE` pada SQL Server dipertahankan sebagai nama catalog/database.

```powershell
python -m petarelasi render skema.sql bagian.drawio --dialect postgres --schema akademik
```

### Koneksi langsung, tanpa ekspor

Adapter ini membaca katalog metadata melalui SQLAlchemy. Pasang `.[postgres]` atau `.[mysql]` jika sebelumnya hanya memasang extra SQL. `.[all]` sudah mencakup keduanya.

Contoh PowerShell dengan URL contoh; isi sesuai database sendiri:

```powershell
$env:DATABASE_URL = "postgresql://nama_user:password@localhost:5432/kampus"
python -m petarelasi render env:DATABASE_URL hasil.drawio --schema public
```

Untuk MySQL atau MariaDB, gunakan URL berikut lalu jalankan perintah render yang sama tanpa `--schema public`:

```powershell
$env:DATABASE_URL = "mysql://nama_user:password@localhost:3306/kampus"
python -m petarelasi render env:DATABASE_URL hasil-mysql.drawio
```

Pada Bash, bentuk pengisiannya `export DATABASE_URL='postgresql://nama_user:password@localhost:5432/kampus'`. Karakter khusus dalam username/password perlu di-URL-encode. Sumber CLI hanya memuat **nama** environment variable; pesan kegagalan koneksi tidak mencetak URL atau diagnostik driver yang mungkin berisi kredensial.

Program mengambil semua tabel di schema awal dan secara rekursif menyertakan tabel induk lintas schema yang dirujuk FK. Gunakan akun dengan izin membaca metadata semua tabel tersebut. Query introspeksi tidak membaca record aplikasi atau menjalankan DDL. PostgreSQL menggunakan transaksi `REPEATABLE READ` dengan `READ ONLY`; MySQL/MariaDB menggunakan `REPEATABLE READ` dan query metadata. Perubahan DDL bersamaan pada MySQL tidak dijamin menghasilkan snapshot lintas tabel yang konsisten.

**Batas verifikasi:** adapter PostgreSQL dan MySQL/MariaDB telah diimplementasikan, tetapi belum diuji ke server nyata. Lingkungan pengembangan tidak mengizinkan server database sementara membuka socket. Jalur koneksi SQLite, pengikutsertaan induk lintas schema dengan metadata sintetis, dan penanganan metadata tidak lengkap sudah diuji. Gunakan ekspor SQL sebagai jalur yang telah diuji untuk keempat dialek tersebut.

### SQLite dan JSON

```powershell
python -m petarelasi render database.sqlite hasil.drawio
python -m petarelasi snapshot database.sqlite skema.json
python -m petarelasi render skema.json hasil.svg
```

Perintah `snapshot` juga menerima `.sql` dengan `--dialect`, serta `env:NAMA_VARIABEL`. JSON berisi struktur saja dan dapat dipakai untuk membuat ulang diagram tanpa koneksi database.

## Fokus pada sebagian relasi

```powershell
python -m petarelasi render contoh/postgres.sql fokus.drawio --dialect postgres --focus public.anggota --radius 1
```

Gunakan nama tabel lengkap sesuai snapshot, termasuk schema/catalog dan tanda kutip jika ada. Radius 0–5 memiliki bawaan 1. Radius 0 menyisakan tabel pusat dan relasi ke dirinya sendiri. Radius 1 menyertakan tetangga langsung dari kedua arah. Hanya relasi dengan kedua tabel dalam tampilan yang digambar.

## Cakupan dan jaminan

- **Panah mengikuti FK yang dideklarasikan.** FK gabungan dipasangkan menurut urutan kolom constraint. Referensi implisit ke primary key memakai urutan PK, bukan urutan kolom tabel. Penamaan `user_id` saja tidak dianggap sebagai relasi tanpa constraint FK. Jika database belum mendefinisikan FK, diagram tetap menampilkan tabel dan kolomnya.
- **Validasi mendahului penulisan.** Target tabel/kolom hilang, pasangan FK tidak cocok, atau metadata tidak lengkap membuat proses gagal sebelum file diagram baru dibuat. File keluaran yang sudah ada tidak ditimpa.
- **File SQL hanya diparse.** Tidak ada koneksi database pada jalur ini. Pernyataan data yang dikenali diabaikan; ekspor schema-only tetap dianjurkan. Blok `COPY` data dan perintah klien selain pembatas pg_dump yang dikenal ditolak.
- **Hasil deterministik untuk snapshot ekuivalen.** Urutan tabel dan FK dinormalisasi; urutan kolom dan pasangan FK dipertahankan. Tipe dari SQL/live dapat dinormalisasi oleh parser/driver, sehingga label tipe tidak harus sama persis dengan ejaan ekspor asli.

Parser mendukung `CREATE TABLE` berkolom eksplisit, PK/FK inline dan tingkat tabel, `ALTER TABLE ADD` constraint PK/FK, nama berpetik, relasi mandiri, dan beberapa schema. MySQL juga mendukung `MODIFY` tipe kolom yang sudah ada tanpa memindahkan atau mengganti namanya, untuk pola ekspor AUTO_INCREMENT. Batch SQL Server `GO` tanpa hitungan dan pembatas `\restrict`/`\unrestrict` pg_dump ditangani. Indeks/unique/check/default yang dikenali tidak ditampilkan dalam ERD.

Alat ini membaca ekspor struktur akhir. Skrip migrasi dengan ADD/DROP/RENAME kolom, CREATE TABLE AS/LIKE, tabel partisi/inheritance, stored procedure, serta sintaks khusus vendor yang tidak didukung dapat ditolak. Oracle, MongoDB, file backup biner `.dump`/`.bak`, dan koneksi SQL Server langsung belum tersedia. Koneksi langsung hanya dapat menampilkan metadata yang terlihat oleh akun database tersebut.

Batas per diagram adalah **48 tabel, 600 kolom, 100 foreign key, dan 120 pasangan kolom**. File SQL maksimal 8 MiB; JSON maksimal 1 MiB. Diagram padat dapat memiliki garis bersilangan. Jalur SVG tidak melewati bagian dalam kotak tabel; Draw.io dapat menghitung ulang jalur setelah elemen dipindahkan. Exit code 0 berarti berhasil, 2 berarti input/keluaran gagal diproses.

## Struktur dan keputusan teknis

| Berkas | Tanggung jawab |
| --- | --- |
| `petarelasi/sources.py` | Memilih sumber berdasarkan file atau `env:`. |
| `petarelasi/sql_source.py` | AST SQLGlot, pembatas client, penyelesaian PK/FK setelah seluruh DDL terbaca. |
| `petarelasi/live_source.py` | Introspeksi SQLAlchemy dan pengambilan induk lintas schema. |
| `petarelasi/schema.py` | Model bersama, validasi, SQLite baca-saja, dan pencarian tetangga. |
| `petarelasi/layout.py` | Port tiap kolom dan jalur siku deterministik. |
| `petarelasi/render.py` | Serialisasi Draw.io XML dan SVG. |
| `petarelasi/__main__.py` | CLI dan perlindungan file keluaran. |
| `petarelasi/studio/model.py` | Sesi dokumen, input tempelan SQL, dan penjelasan PK/FK. |
| `petarelasi/studio/canvas.py` | Pratinjau Qt interaktif dengan geometri dari mesin ekspor. |
| `petarelasi/studio/window.py` | Antarmuka, worker impor, fokus, inspector, dan dialog ekspor. |
| `studio_setup.py`, `Mulai_Studio.cmd` | Persiapan lingkungan lokal dan peluncur desktop. |
| `tests/` | Tes integrasi input, renderer, kegagalan, dan kompatibilitas versi lama. |

Semua adapter masuk ke model skema dan validator yang sama. Foreign key diselesaikan setelah definisi SQL terkumpul agar urutan deklarasi pg_dump dan referensi ke tabel yang baru muncul belakangan tetap benar. Dependensi baru dimuat hanya saat sumbernya dipilih, sehingga mode SQLite/JSON tetap ringan.

Format JSON minimal tetap kompatibel dengan versi 1.0:

```json
{
  "version": 1,
  "tables": [
    {"name": "anggota", "columns": [{"name": "id", "type": "INTEGER", "pk": 1}]},
    {"name": "pinjam", "columns": [{"name": "anggota_id", "type": "INTEGER", "pk": 0}]}
  ],
  "foreign_keys": [
    {"table": "pinjam", "columns": ["anggota_id"], "references": "anggota", "ref_columns": ["id"]}
  ]
}
```

`pk` bernilai 0 untuk kolom biasa dan 1, 2, ... untuk posisi primary key. Posisi `columns` pada FK dipasangkan dengan posisi yang sama di `ref_columns`.

## Tes

```powershell
python -m pip install ".[all]"
python -m unittest discover -s tests -v
```

Suite menguji CLI nyata, empat fixture dialek SQL, round-trip SQL → JSON → Draw.io, FK gabungan, nama berpetik, GO dalam string, custom search_path, penggunaan catalog SQL Server, perlindungan keluaran, metadata SQLite nyata, sanitasi error, dan regresi geometri/renderer. Tes lintas schema memakai inspector sintetis; tes ini tidak menggantikan uji server PostgreSQL/MySQL. Tes tanpa extra dapat dijalankan; bagian yang memerlukan extra akan ditandai skipped.

Untuk Studio, tes menekan widget Qt dengan QTest, mengeklik kolom dan garis di canvas, mengimpor melalui dialog file, membuka ulang SQLite/JSON, serta memeriksa hasil ekspor nyata. Tes kegagalan memeriksa bahwa skema/fokus/diagram lama tetap tersedia setelah impor rusak. Penutupan jendela saat worker aktif juga diuji.

Hasil pemeriksaan versi 1.2.0: **49/49 tes lulus** dengan dependensi lengkap pada Python 3.12 dan Qt 6.10.2 menggunakan offscreen di Linux. Tanpa extra: **18 lulus, 31 skipped**. Screenshot di atas adalah render antarmuka aktual dengan data contoh sintetis. Pengoperasian native dan peluncur `.cmd` pada Windows belum diuji di lingkungan ini.

Untuk demo SQLite tanpa dependensi:

```powershell
python -m petarelasi demo contoh-baru
python -m petarelasi --version
```

Rujukan: [Qt Graphics View](https://doc.qt.io/qtforpython-6/overviews/qtwidgets-graphicsview.html), [pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html), [mysqldump](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html), [SSMS Generate Scripts](https://learn.microsoft.com/sql/ssms/scripting/generate-and-publish-scripts-wizard), [SQLGlot](https://sqlglot.com/sqlglot.html), [SQLAlchemy reflection](https://docs.sqlalchemy.org/en/20/core/reflection.html), dan [Draw.io generation](https://www.drawio.com/docs/reference/diagram-generation/).
