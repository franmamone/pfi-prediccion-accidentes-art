/*
  Seguimiento de reagenda: el preventor indica plazo máx. (meses) al cerrar;
  el coordinador ve estado "reagendar" en Priorización y agenda antes del límite.
*/
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE [PfiPrevencion];
GO

IF OBJECT_ID(N'app.EstablecimientoReagenda', N'U') IS NULL
CREATE TABLE app.EstablecimientoReagenda (
    Id                  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_EstablecimientoReagenda PRIMARY KEY,
    IdEstablecimiento   NVARCHAR(64) NOT NULL,
    LimiteEn            DATE NOT NULL,
    MesesPlazo          TINYINT NOT NULL,
    VisitaOrigenId      INT NULL,
    AgendaCubiertaId    INT NULL,
    Estado              NVARCHAR(20) NOT NULL CONSTRAINT DF_EstablecimientoReagenda_Estado DEFAULT (N'pendiente'),
    CreadoEn            DATETIME2(0) NOT NULL CONSTRAINT DF_EstablecimientoReagenda_CreadoEn DEFAULT (SYSUTCDATETIME()),
    CubiertoEn          DATETIME2(0) NULL,
    CreadoPorUsuarioId  INT NULL,
    CONSTRAINT CK_EstablecimientoReagenda_Estado CHECK (Estado IN (N'pendiente', N'cubierta', N'cancelada')),
    CONSTRAINT CK_EstablecimientoReagenda_Meses CHECK (MesesPlazo IN (1, 2, 3, 6)),
    CONSTRAINT FK_EstablecimientoReagenda_Visita FOREIGN KEY (VisitaOrigenId) REFERENCES app.VisitasApp (Id),
    CONSTRAINT FK_EstablecimientoReagenda_Agenda FOREIGN KEY (AgendaCubiertaId) REFERENCES app.AgendaItems (Id)
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_EstablecimientoReagenda_Est_Estado'
      AND object_id = OBJECT_ID(N'app.EstablecimientoReagenda')
)
CREATE INDEX IX_EstablecimientoReagenda_Est_Estado
    ON app.EstablecimientoReagenda (IdEstablecimiento, Estado)
    INCLUDE (LimiteEn, MesesPlazo);
GO
