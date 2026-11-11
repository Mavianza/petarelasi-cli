-- Contoh sintetis SQL Server, dengan batch GO dan clustered primary key.
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[anggota] (
    [kode] nvarchar(20) NOT NULL,
    [unit] nvarchar(20) NOT NULL,
    [nama] nvarchar(100) NULL,
    CONSTRAINT [PK_anggota] PRIMARY KEY CLUSTERED ([unit] ASC, [kode] ASC)
)
GO
CREATE TABLE [dbo].[buku] (
    [id] int IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [judul] nvarchar(200) NOT NULL,
    [buku_induk] int NULL
)
GO
CREATE TABLE [dbo].[pinjam] (
    [id] int IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [unit_anggota] nvarchar(20) NOT NULL,
    [kode_anggota] nvarchar(20) NOT NULL,
    [buku_id] int NOT NULL
)
GO
ALTER TABLE [dbo].[buku] WITH CHECK ADD CONSTRAINT [buku_induk_fk] FOREIGN KEY ([buku_induk]) REFERENCES [dbo].[buku] ([id])
GO
ALTER TABLE [dbo].[pinjam] WITH CHECK ADD CONSTRAINT [anggota_fk] FOREIGN KEY ([unit_anggota], [kode_anggota]) REFERENCES [dbo].[anggota] ([unit], [kode])
GO
ALTER TABLE [dbo].[pinjam] WITH CHECK ADD CONSTRAINT [buku_fk] FOREIGN KEY ([buku_id]) REFERENCES [dbo].[buku] ([id])
GO
ALTER TABLE [dbo].[pinjam] CHECK CONSTRAINT [buku_fk]
GO
