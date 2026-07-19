/*
  Migración: auditoría append-only de agenda + contribuciones SHAP por RankingItem.
*/

SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE [PfiPrevencion];
GO

IF OBJECT_ID(N'app.AgendaEventos', N'U') IS NULL
CREATE TABLE app.AgendaEventos (
    Id                  BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_AgendaEventos PRIMARY KEY,
    AgendaItemId        INT NOT NULL,
    SnapshotItemId      BIGINT NULL,
    IdEstablecimiento   CHAR(64) NOT NULL,
    Tipo                NVARCHAR(30) NOT NULL,  -- programada | reprogramada | realizada | cancelada
    ActorUsuarioId      INT NULL,
    ActorNombre         NVARCHAR(200) NULL,
    ActorEmail          NVARCHAR(256) NULL,
    ActorRol            NVARCHAR(40) NULL,
    OcurridoEn          DATETIME2(3) NOT NULL CONSTRAINT DF_AgendaEventos_OcurridoEn DEFAULT (SYSUTCDATETIME()),
    EstadoAnterior      NVARCHAR(30) NULL,
    EstadoNuevo         NVARCHAR(30) NULL,
    Datos               NVARCHAR(MAX) NULL,
    OperacionId         UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_AgendaEventos_OperacionId DEFAULT (NEWID()),
    CONSTRAINT FK_AgendaEventos_Agenda FOREIGN KEY (AgendaItemId) REFERENCES app.AgendaItems (Id),
    CONSTRAINT FK_AgendaEventos_Actor FOREIGN KEY (ActorUsuarioId) REFERENCES app.Usuarios (Id),
    CONSTRAINT CK_AgendaEventos_Tipo CHECK (
        Tipo IN (N'programada', N'reprogramada', N'realizada', N'cancelada')
    ),
    CONSTRAINT CK_AgendaEventos_DatosJson CHECK (Datos IS NULL OR ISJSON(Datos) = 1),
    CONSTRAINT UQ_AgendaEventos_OperacionId UNIQUE (OperacionId)
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_AgendaEventos_Agenda_Ocurrido' AND object_id = OBJECT_ID(N'app.AgendaEventos')
)
CREATE INDEX IX_AgendaEventos_Agenda_Ocurrido
    ON app.AgendaEventos (AgendaItemId, OcurridoEn DESC, Id DESC);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_AgendaEventos_Establecimiento_Ocurrido' AND object_id = OBJECT_ID(N'app.AgendaEventos')
)
CREATE INDEX IX_AgendaEventos_Establecimiento_Ocurrido
    ON app.AgendaEventos (IdEstablecimiento, OcurridoEn DESC, Id DESC);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_AgendaEventos_Tipo_Ocurrido' AND object_id = OBJECT_ID(N'app.AgendaEventos')
)
CREATE INDEX IX_AgendaEventos_Tipo_Ocurrido
    ON app.AgendaEventos (Tipo, OcurridoEn DESC);
GO

IF OBJECT_ID(N'app.RankingItemContribuciones', N'U') IS NULL
CREATE TABLE app.RankingItemContribuciones (
    Id                  BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RankingItemContribuciones PRIMARY KEY,
    RankingItemId       BIGINT NOT NULL,
    Orden               TINYINT NOT NULL,
    Feature             NVARCHAR(120) NOT NULL,
    Tema                NVARCHAR(80) NULL,
    Etiqueta            NVARCHAR(200) NOT NULL,
    ValorObservado      NVARCHAR(200) NULL,
    ShapValue           FLOAT NOT NULL,
    Direccion           NVARCHAR(20) NOT NULL, -- aumenta | reduce
    Descripcion         NVARCHAR(500) NULL,
    CONSTRAINT FK_RankingItemContribuciones_Item FOREIGN KEY (RankingItemId)
        REFERENCES app.RankingItems (Id) ON DELETE CASCADE,
    CONSTRAINT CK_RankingItemContribuciones_Direccion CHECK (Direccion IN (N'aumenta', N'reduce')),
    CONSTRAINT UQ_RankingItemContribuciones_ItemOrden UNIQUE (RankingItemId, Orden)
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_RankingItemContribuciones_Item' AND object_id = OBJECT_ID(N'app.RankingItemContribuciones')
)
CREATE INDEX IX_RankingItemContribuciones_Item
    ON app.RankingItemContribuciones (RankingItemId, Orden);
GO

PRINT 'Migración agenda eventos + SHAP aplicada.';
GO
