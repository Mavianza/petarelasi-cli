-- Contoh sintetis bergaya pg_dump --schema-only, bukan data pengguna.
\restrict ContohPetaRelasi
SET statement_timeout = 0;
SELECT pg_catalog.set_config('search_path', '', false);
CREATE TABLE public.anggota (
    kode text NOT NULL,
    unit text NOT NULL,
    nama text
);
CREATE TABLE public.buku (
    id integer NOT NULL,
    judul text NOT NULL,
    buku_induk integer
);
CREATE TABLE public.pinjam (
    id integer NOT NULL,
    unit_anggota text NOT NULL,
    kode_anggota text NOT NULL,
    buku_id integer NOT NULL
);
ALTER TABLE ONLY public.anggota ADD CONSTRAINT anggota_pkey PRIMARY KEY (unit, kode);
ALTER TABLE ONLY public.buku ADD CONSTRAINT buku_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.pinjam ADD CONSTRAINT pinjam_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.buku ADD CONSTRAINT buku_induk_fk FOREIGN KEY (buku_induk) REFERENCES public.buku(id);
ALTER TABLE ONLY public.pinjam ADD CONSTRAINT pinjam_anggota_fk FOREIGN KEY (unit_anggota, kode_anggota) REFERENCES public.anggota(unit, kode);
ALTER TABLE ONLY public.pinjam ADD CONSTRAINT pinjam_buku_fk FOREIGN KEY (buku_id) REFERENCES public.buku(id);
\unrestrict ContohPetaRelasi
