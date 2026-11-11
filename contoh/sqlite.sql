-- Contoh sintetis SQLite. Urutan primary key berbeda dari urutan kolom.
CREATE TABLE anggota (kode TEXT, unit TEXT, nama TEXT, PRIMARY KEY (unit, kode));
CREATE TABLE buku (id INTEGER PRIMARY KEY, judul TEXT, buku_induk INTEGER REFERENCES buku(id));
CREATE TABLE pinjam (
    id INTEGER PRIMARY KEY,
    unit_anggota TEXT,
    kode_anggota TEXT,
    buku_id INTEGER REFERENCES buku(id),
    FOREIGN KEY (unit_anggota, kode_anggota) REFERENCES anggota
);
