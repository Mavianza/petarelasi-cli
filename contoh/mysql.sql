-- Contoh sintetis MySQL/MariaDB. Mendukung pola ALTER pada ekspor phpMyAdmin.
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
USE `perpustakaan`;
CREATE TABLE `anggota` (
    `kode` varchar(20) NOT NULL,
    `unit` varchar(20) NOT NULL,
    `nama` varchar(100)
) ENGINE=InnoDB;
CREATE TABLE `buku` (
    `id` int NOT NULL,
    `judul` varchar(200) NOT NULL,
    `buku_induk` int DEFAULT NULL
) ENGINE=InnoDB;
CREATE TABLE `pinjam` (
    `id` int NOT NULL,
    `unit_anggota` varchar(20) NOT NULL,
    `kode_anggota` varchar(20) NOT NULL,
    `buku_id` int NOT NULL
) ENGINE=InnoDB;
ALTER TABLE `anggota` ADD PRIMARY KEY (`unit`, `kode`);
ALTER TABLE `buku` ADD PRIMARY KEY (`id`), ADD KEY `induk` (`buku_induk`);
ALTER TABLE `pinjam` ADD PRIMARY KEY (`id`);
ALTER TABLE `buku` MODIFY `id` int NOT NULL AUTO_INCREMENT;
ALTER TABLE `buku` ADD CONSTRAINT `buku_induk_fk` FOREIGN KEY (`buku_induk`) REFERENCES `buku` (`id`);
ALTER TABLE `pinjam` ADD CONSTRAINT `anggota_fk` FOREIGN KEY (`unit_anggota`,`kode_anggota`) REFERENCES `anggota` (`unit`,`kode`);
ALTER TABLE `pinjam` ADD CONSTRAINT `buku_fk` FOREIGN KEY (`buku_id`) REFERENCES `buku` (`id`);
COMMIT;
