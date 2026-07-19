/*
  Migración: flujo simple de visitas (programada → realizada | cancelada).
  Idempotente para PfiPrevencion local.
*/

SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE [PfiPrevencion];
GO

/* Recrear tablas operativas (aún no usadas por la API; esquema v1 incompleto). */

IF OBJECT_ID(N'app.VisitasApp', N'U') IS NOT NULL
    DROP TABLE app.VisitasApp;
GO

IF OBJECT_ID(N'app.AgendaItems', N'U') IS NOT NULL
    DROP TABLE app.AgendaItems;
GO

CREATE TABLE app.AgendaItems (
    Id                  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_AgendaItems PRIMARY KEY,
    UsuarioId           INT NOT NULL,
    IdEstablecimiento   CHAR(64) NOT NULL,
    Periodo             CHAR(7) NOT NULL,
    Horizonte           VARCHAR(2) NOT NULL CONSTRAINT DF_AgendaItems_Horizonte DEFAULT ('1m'),
    FechaPlanificada    DATE NOT NULL,
    MotivoVisita        NVARCHAR(40) NOT NULL,
    Estado              NVARCHAR(30) NOT NULL,
    SnapshotItemId      BIGINT NULL,
    RankingOrigen       INT NULL,
    ScoreOrigen         FLOAT NULL,
    BandaOrigen         VARCHAR(20) NULL,
    MotivoOrigen        NVARCHAR(80) NULL,
    Notas               NVARCHAR(1000) NULL,
    CreadoEn            DATETIME2(0) NOT NULL CONSTRAINT DF_AgendaItems_CreadoEn DEFAULT (SYSUTCDATETIME()),
    ActualizadoEn       DATETIME2(0) NOT NULL CONSTRAINT DF_AgendaItems_ActualizadoEn DEFAULT (SYSUTCDATETIME()),
    CanceladaEn         DATETIME2(0) NULL,
    MotivoCancelacion   NVARCHAR(400) NULL,
    RowVersion          ROWVERSION NOT NULL,
    CONSTRAINT FK_AgendaItems_Usuarios FOREIGN KEY (UsuarioId) REFERENCES app.Usuarios (Id),
    CONSTRAINT FK_AgendaItems_RankingItems FOREIGN KEY (SnapshotItemId)
        REFERENCES app.RankingItems (Id) ON DELETE SET NULL,
    CONSTRAINT CK_AgendaItems_Estado CHECK (Estado IN (N'programada', N'realizada', N'cancelada')),
    CONSTRAINT CK_AgendaItems_Horizonte CHECK (Horizonte IN ('1m', '3m'))
);
GO

CREATE INDEX IX_AgendaItems_Estado_Fecha
    ON app.AgendaItems (Estado, FechaPlanificada);
GO

CREATE INDEX IX_AgendaItems_Usuario_Estado
    ON app.AgendaItems (UsuarioId, Estado);
GO

CREATE INDEX IX_AgendaItems_Establecimiento
    ON app.AgendaItems (IdEstablecimiento);
GO

/* Una sola visita programada activa por establecimiento. */
CREATE UNIQUE INDEX UQ_AgendaItems_Programada_Establecimiento
    ON app.AgendaItems (IdEstablecimiento)
    WHERE Estado = N'programada';
GO

CREATE TABLE app.VisitasApp (
    Id                  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_VisitasApp PRIMARY KEY,
    IdEstablecimiento   CHAR(64) NOT NULL,
    UsuarioId           INT NOT NULL,
    AgendaItemId        INT NULL,
    FechaHoraReal       DATETIME2(0) NOT NULL,
    Tipo                NVARCHAR(40) NOT NULL,
    Resultado           NVARCHAR(30) NOT NULL,
    MotivoNoRealizada   NVARCHAR(200) NULL,
    Hallazgos           NVARCHAR(MAX) NULL,
    Acciones            NVARCHAR(MAX) NULL,
    CreadoEn            DATETIME2(0) NOT NULL CONSTRAINT DF_VisitasApp_CreadoEn DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_VisitasApp_Usuarios FOREIGN KEY (UsuarioId) REFERENCES app.Usuarios (Id),
    CONSTRAINT FK_VisitasApp_Agenda FOREIGN KEY (AgendaItemId) REFERENCES app.AgendaItems (Id),
    CONSTRAINT CK_VisitasApp_Resultado CHECK (Resultado IN (N'realizada', N'no_realizada'))
);
GO

CREATE UNIQUE INDEX UQ_VisitasApp_AgendaItem
    ON app.VisitasApp (AgendaItemId)
    WHERE AgendaItemId IS NOT NULL;
GO

CREATE INDEX IX_VisitasApp_Establecimiento_Fecha
    ON app.VisitasApp (IdEstablecimiento, FechaHoraReal DESC);
GO

PRINT 'Migración agenda/visitas aplicada.';
GO
