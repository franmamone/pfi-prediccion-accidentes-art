/*
  Migración: analítica histórica — snapshots versionados, SHAP agregado,
  outcomes observados y cobertura por cohorte operativa.
*/

SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE [PfiPrevencion];
GO

/* ---------- RankingSnapshots: versionado inmutable ---------- */

IF COL_LENGTH(N'app.RankingSnapshots', N'ModeloVersion') IS NULL
    ALTER TABLE app.RankingSnapshots ADD ModeloVersion NVARCHAR(80) NULL;
GO
IF COL_LENGTH(N'app.RankingSnapshots', N'ArtifactHash') IS NULL
    ALTER TABLE app.RankingSnapshots ADD ArtifactHash CHAR(64) NULL;
GO
IF COL_LENGTH(N'app.RankingSnapshots', N'DatosHasta') IS NULL
    ALTER TABLE app.RankingSnapshots ADD DatosHasta CHAR(7) NULL;
GO
IF COL_LENGTH(N'app.RankingSnapshots', N'ImportadoEn') IS NULL
    ALTER TABLE app.RankingSnapshots ADD ImportadoEn DATETIME2(0) NULL;
GO
IF COL_LENGTH(N'app.RankingSnapshots', N'ActivadoEn') IS NULL
    ALTER TABLE app.RankingSnapshots ADD ActivadoEn DATETIME2(0) NULL;
GO
IF COL_LENGTH(N'app.RankingSnapshots', N'UniversoFilas') IS NULL
    ALTER TABLE app.RankingSnapshots ADD UniversoFilas INT NULL;
GO
IF COL_LENGTH(N'app.RankingSnapshots', N'ItemsImportados') IS NULL
    ALTER TABLE app.RankingSnapshots ADD ItemsImportados INT NULL;
GO

UPDATE app.RankingSnapshots
SET ImportadoEn = COALESCE(ImportadoEn, GeneradoEn),
    ActivadoEn = COALESCE(ActivadoEn, GeneradoEn),
    UniversoFilas = COALESCE(UniversoFilas, Filas),
    ItemsImportados = COALESCE(ItemsImportados, Criticos + Altos)
WHERE ImportadoEn IS NULL OR ActivadoEn IS NULL OR UniversoFilas IS NULL OR ItemsImportados IS NULL;
GO

-- Reemplazar unicidad Periodo+Horizonte por Periodo+Horizonte+ArtifactHash (permite versiones).
IF EXISTS (
    SELECT 1 FROM sys.key_constraints
    WHERE name = N'UQ_RankingSnapshots_PeriodoHorizonte'
      AND parent_object_id = OBJECT_ID(N'app.RankingSnapshots')
)
ALTER TABLE app.RankingSnapshots DROP CONSTRAINT UQ_RankingSnapshots_PeriodoHorizonte;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UQ_RankingSnapshots_PeriodoHorizonteHash'
      AND object_id = OBJECT_ID(N'app.RankingSnapshots')
)
CREATE UNIQUE INDEX UQ_RankingSnapshots_PeriodoHorizonteHash
    ON app.RankingSnapshots (Periodo, Horizonte, ArtifactHash)
    WHERE ArtifactHash IS NOT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_RankingSnapshots_Horizonte_Vigente'
      AND object_id = OBJECT_ID(N'app.RankingSnapshots')
)
CREATE INDEX IX_RankingSnapshots_Horizonte_Vigente
    ON app.RankingSnapshots (Horizonte, EsVigente, Periodo DESC);
GO

/* Unicidad de ítems dentro del snapshot */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UQ_RankingItems_Snapshot_Establecimiento'
      AND object_id = OBJECT_ID(N'app.RankingItems')
)
CREATE UNIQUE INDEX UQ_RankingItems_Snapshot_Establecimiento
    ON app.RankingItems (SnapshotId, IdEstablecimiento);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UQ_RankingItems_Snapshot_Ranking'
      AND object_id = OBJECT_ID(N'app.RankingItems')
)
CREATE UNIQUE INDEX UQ_RankingItems_Snapshot_Ranking
    ON app.RankingItems (SnapshotId, Ranking);
GO

/* ---------- Agenda: vínculo estable al snapshot ---------- */

IF COL_LENGTH(N'app.AgendaItems', N'SnapshotId') IS NULL
    ALTER TABLE app.AgendaItems ADD SnapshotId INT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = N'FK_AgendaItems_Snapshots' AND parent_object_id = OBJECT_ID(N'app.AgendaItems')
)
ALTER TABLE app.AgendaItems WITH NOCHECK
ADD CONSTRAINT FK_AgendaItems_Snapshots FOREIGN KEY (SnapshotId)
    REFERENCES app.RankingSnapshots (Id);
GO

-- Backfill SnapshotId desde SnapshotItemId cuando exista.
UPDATE a
SET a.SnapshotId = i.SnapshotId
FROM app.AgendaItems a
INNER JOIN app.RankingItems i ON i.Id = a.SnapshotItemId
WHERE a.SnapshotId IS NULL AND a.SnapshotItemId IS NOT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_AgendaItems_Snapshot' AND object_id = OBJECT_ID(N'app.AgendaItems')
)
CREATE INDEX IX_AgendaItems_Snapshot ON app.AgendaItems (SnapshotId, Estado);
GO

/* ---------- SHAP agregado por snapshot ---------- */

IF OBJECT_ID(N'app.SnapshotShapAgregados', N'U') IS NULL
CREATE TABLE app.SnapshotShapAgregados (
    Id                  BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_SnapshotShapAgregados PRIMARY KEY,
    SnapshotId          INT NOT NULL,
    TopK                INT NOT NULL,
    Feature             NVARCHAR(120) NOT NULL,
    Tema                NVARCHAR(80) NULL,
    Etiqueta            NVARCHAR(200) NOT NULL,
    OrdenImportancia    INT NOT NULL,
    ItemsCohorte        INT NOT NULL,
    MeanAbsShap         FLOAT NOT NULL,
    MeanShap            FLOAT NOT NULL,
    P50AbsShap          FLOAT NULL,
    P90AbsShap          FLOAT NULL,
    PctAumenta          FLOAT NOT NULL,
    Metodo              NVARCHAR(60) NOT NULL CONSTRAINT DF_SnapshotShapAgregados_Metodo DEFAULT (N'matriz_completa'),
    GeneradoEn          DATETIME2(0) NOT NULL CONSTRAINT DF_SnapshotShapAgregados_GeneradoEn DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_SnapshotShapAgregados_Snapshot FOREIGN KEY (SnapshotId)
        REFERENCES app.RankingSnapshots (Id) ON DELETE CASCADE,
    CONSTRAINT CK_SnapshotShapAgregados_TopK CHECK (TopK IN (50, 225)),
    CONSTRAINT UQ_SnapshotShapAgregados_Key UNIQUE (SnapshotId, TopK, Feature)
);
GO

/* ---------- Outcomes por ítem ---------- */

IF OBJECT_ID(N'app.RankingItemOutcomes', N'U') IS NULL
CREATE TABLE app.RankingItemOutcomes (
    Id                  BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RankingItemOutcomes PRIMARY KEY,
    RankingItemId       BIGINT NOT NULL,
    SnapshotId          INT NOT NULL,
    PeriodoDecision     CHAR(7) NOT NULL,
    Horizonte           VARCHAR(2) NOT NULL,
    VentanaInicio       CHAR(7) NOT NULL,
    VentanaFin          CHAR(7) NOT NULL,
    Estado              NVARCHAR(20) NOT NULL,  -- pendiente | parcial | maduro
    CantidadAccidentes  INT NULL,
    OutcomeBinario      BIT NULL,
    FuenteCompletaHasta CHAR(7) NULL,
    EvaluadoEn          DATETIME2(0) NULL,
    CONSTRAINT FK_RankingItemOutcomes_Item FOREIGN KEY (RankingItemId)
        REFERENCES app.RankingItems (Id) ON DELETE CASCADE,
    CONSTRAINT FK_RankingItemOutcomes_Snapshot FOREIGN KEY (SnapshotId)
        REFERENCES app.RankingSnapshots (Id),
    CONSTRAINT CK_RankingItemOutcomes_Estado CHECK (Estado IN (N'pendiente', N'parcial', N'maduro')),
    CONSTRAINT CK_RankingItemOutcomes_Horizonte CHECK (Horizonte IN ('1m', '3m')),
    CONSTRAINT UQ_RankingItemOutcomes_Item UNIQUE (RankingItemId)
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_RankingItemOutcomes_Snapshot_Estado'
      AND object_id = OBJECT_ID(N'app.RankingItemOutcomes')
)
CREATE INDEX IX_RankingItemOutcomes_Snapshot_Estado
    ON app.RankingItemOutcomes (SnapshotId, Estado);
GO

/* ---------- Métricas observadas por snapshot ---------- */

IF OBJECT_ID(N'app.SnapshotMetricasObservadas', N'U') IS NULL
CREATE TABLE app.SnapshotMetricasObservadas (
    Id                  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_SnapshotMetricasObservadas PRIMARY KEY,
    SnapshotId          INT NOT NULL,
    TopK                INT NOT NULL,
    Estado              NVARCHAR(20) NOT NULL,
    Denominador         INT NOT NULL,
    Positivos           INT NULL,
    Precision           FLOAT NULL,
    VentanaInicio       CHAR(7) NOT NULL,
    VentanaFin          CHAR(7) NOT NULL,
    FuenteCompletaHasta CHAR(7) NULL,
    CalculadoEn         DATETIME2(0) NOT NULL CONSTRAINT DF_SnapshotMetricasObservadas_CalculadoEn DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_SnapshotMetricasObservadas_Snapshot FOREIGN KEY (SnapshotId)
        REFERENCES app.RankingSnapshots (Id) ON DELETE CASCADE,
    CONSTRAINT CK_SnapshotMetricasObservadas_TopK CHECK (TopK IN (50, 225)),
    CONSTRAINT CK_SnapshotMetricasObservadas_Estado CHECK (Estado IN (N'pendiente', N'parcial', N'maduro')),
    CONSTRAINT UQ_SnapshotMetricasObservadas_Key UNIQUE (SnapshotId, TopK)
);
GO

/* ---------- Cobertura operativa por cohorte ---------- */

IF OBJECT_ID(N'app.SnapshotCoberturas', N'U') IS NULL
CREATE TABLE app.SnapshotCoberturas (
    Id                  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_SnapshotCoberturas PRIMARY KEY,
    SnapshotId          INT NOT NULL,
    TopK                INT NOT NULL,
    VentanaInicio       DATE NOT NULL,
    VentanaFin          DATE NOT NULL,
    Denominador         INT NOT NULL,
    Programados         INT NOT NULL,
    Realizados          INT NOT NULL,
    Cubiertos           INT NOT NULL,
    Porcentaje          FLOAT NOT NULL,
    Estado              NVARCHAR(20) NOT NULL,  -- abierta | cerrada
    CorteEn             DATETIME2(0) NULL,
    CalculadoEn         DATETIME2(0) NOT NULL CONSTRAINT DF_SnapshotCoberturas_CalculadoEn DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_SnapshotCoberturas_Snapshot FOREIGN KEY (SnapshotId)
        REFERENCES app.RankingSnapshots (Id) ON DELETE CASCADE,
    CONSTRAINT CK_SnapshotCoberturas_TopK CHECK (TopK IN (50, 225)),
    CONSTRAINT CK_SnapshotCoberturas_Estado CHECK (Estado IN (N'abierta', N'cerrada')),
    CONSTRAINT UQ_SnapshotCoberturas_Key UNIQUE (SnapshotId, TopK)
);
GO

PRINT 'Migración analítica histórica aplicada.';
GO
