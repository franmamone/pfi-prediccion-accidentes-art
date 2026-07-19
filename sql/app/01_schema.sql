/*
  Schema operativo de la app PFI Prevención.
  Separado del core ART: solo rankings importados, agenda, visitas y usuarios.
*/

SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE [PfiPrevencion];
GO

IF SCHEMA_ID(N'app') IS NULL
    EXEC(N'CREATE SCHEMA app');
GO

/* ---------- Catálogo / auth ---------- */

IF OBJECT_ID(N'app.Zonas', N'U') IS NULL
CREATE TABLE app.Zonas (
    Id          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Zonas PRIMARY KEY,
    Nombre      NVARCHAR(120) NOT NULL,
    Activa      BIT NOT NULL CONSTRAINT DF_Zonas_Activa DEFAULT (1),
    CONSTRAINT UQ_Zonas_Nombre UNIQUE (Nombre)
);
GO

IF OBJECT_ID(N'app.Usuarios', N'U') IS NULL
CREATE TABLE app.Usuarios (
    Id              INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Usuarios PRIMARY KEY,
    Email           NVARCHAR(256) NOT NULL,
    Nombre          NVARCHAR(200) NOT NULL,
    PasswordHash    NVARCHAR(500) NOT NULL,
    Rol             NVARCHAR(40) NOT NULL,  -- Prevencionista | Coordinador | Analista | Admin
    ZonaId          INT NULL,
    Activo          BIT NOT NULL CONSTRAINT DF_Usuarios_Activo DEFAULT (1),
    CreadoEn        DATETIME2(0) NOT NULL CONSTRAINT DF_Usuarios_CreadoEn DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT UQ_Usuarios_Email UNIQUE (Email),
    CONSTRAINT FK_Usuarios_Zonas FOREIGN KEY (ZonaId) REFERENCES app.Zonas (Id),
    CONSTRAINT CK_Usuarios_Rol CHECK (Rol IN (N'Prevencionista', N'Coordinador', N'Analista', N'Admin'))
);
GO

/* ---------- Ranking importado del pipeline ---------- */

IF OBJECT_ID(N'app.RankingSnapshots', N'U') IS NULL
CREATE TABLE app.RankingSnapshots (
    Id              INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RankingSnapshots PRIMARY KEY,
    Periodo         CHAR(7) NOT NULL,           -- YYYY-MM
    Horizonte       VARCHAR(2) NOT NULL,        -- 1m | 3m
    GeneradoEn      DATETIME2(0) NOT NULL CONSTRAINT DF_RankingSnapshots_GeneradoEn DEFAULT (SYSUTCDATETIME()),
    ArchivoOrigen   NVARCHAR(400) NULL,
    Filas           INT NOT NULL CONSTRAINT DF_RankingSnapshots_Filas DEFAULT (0),
    Criticos        INT NOT NULL CONSTRAINT DF_RankingSnapshots_Criticos DEFAULT (0),
    Altos           INT NOT NULL CONSTRAINT DF_RankingSnapshots_Altos DEFAULT (0),
    EsVigente       BIT NOT NULL CONSTRAINT DF_RankingSnapshots_EsVigente DEFAULT (1),
    ModeloVersion   NVARCHAR(80) NULL,
    ArtifactHash    CHAR(64) NULL,
    DatosHasta      CHAR(7) NULL,
    ImportadoEn     DATETIME2(0) NULL,
    ActivadoEn      DATETIME2(0) NULL,
    UniversoFilas   INT NULL,
    ItemsImportados INT NULL,
    CONSTRAINT CK_RankingSnapshots_Horizonte CHECK (Horizonte IN ('1m', '3m'))
);
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

IF OBJECT_ID(N'app.RankingItems', N'U') IS NULL
CREATE TABLE app.RankingItems (
    Id                      BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RankingItems PRIMARY KEY,
    SnapshotId              INT NOT NULL,
    IdEstablecimiento       CHAR(64) NOT NULL,
    IdEmpleador             CHAR(64) NULL,
    Ranking                 INT NOT NULL,
    ScoreRiesgo             FLOAT NOT NULL,
    Banda                   VARCHAR(20) NOT NULL,   -- critico | alto | medio
    Motivo                  NVARCHAR(80) NULL,
    ObligacionPrs           BIT NOT NULL CONSTRAINT DF_RankingItems_ObligacionPrs DEFAULT (0),
    EnCooldown              BIT NOT NULL CONSTRAINT DF_RankingItems_EnCooldown DEFAULT (0),
    UltimaVisitaHaceMeses   FLOAT NULL,
    Sector                  NVARCHAR(120) NULL,
    CiiuDivision            NVARCHAR(10) NULL,
    CantidadCapitas         FLOAT NULL,
    DotacionNominaMes       FLOAT NULL,
    AlertaUmbral            BIT NOT NULL CONSTRAINT DF_RankingItems_AlertaUmbral DEFAULT (0),
    MotivoPrincipalTexto    NVARCHAR(500) NULL,
    CONSTRAINT FK_RankingItems_Snapshots FOREIGN KEY (SnapshotId)
        REFERENCES app.RankingSnapshots (Id) ON DELETE CASCADE,
    CONSTRAINT CK_RankingItems_Banda CHECK (Banda IN ('critico', 'alto', 'medio'))
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_RankingItems_Snapshot_Ranking'
      AND object_id = OBJECT_ID(N'app.RankingItems')
)
CREATE INDEX IX_RankingItems_Snapshot_Ranking
    ON app.RankingItems (SnapshotId, Ranking);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_RankingItems_Snapshot_Banda'
      AND object_id = OBJECT_ID(N'app.RankingItems')
)
CREATE INDEX IX_RankingItems_Snapshot_Banda
    ON app.RankingItems (SnapshotId, Banda);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_RankingItems_Establecimiento'
      AND object_id = OBJECT_ID(N'app.RankingItems')
)
CREATE INDEX IX_RankingItems_Establecimiento
    ON app.RankingItems (IdEstablecimiento);
GO

/* ---------- Operación ---------- */

IF OBJECT_ID(N'app.AgendaItems', N'U') IS NULL
CREATE TABLE app.AgendaItems (
    Id                  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_AgendaItems PRIMARY KEY,
    UsuarioId           INT NOT NULL,                 -- responsable asignado
    IdEstablecimiento   CHAR(64) NOT NULL,
    Periodo             CHAR(7) NOT NULL,
    Horizonte           VARCHAR(2) NOT NULL CONSTRAINT DF_AgendaItems_Horizonte DEFAULT ('1m'),
    FechaPlanificada    DATE NOT NULL,
    MotivoVisita        NVARCHAR(40) NOT NULL,        -- predictivo | prs | seguimiento | extraordinaria
    Estado              NVARCHAR(30) NOT NULL,        -- programada | realizada | cancelada
    SnapshotId          INT NULL,                    -- cohorte de ranking de origen (estable)
    SnapshotItemId      BIGINT NULL,                 -- vínculo opcional al ítem (SET NULL si se pierde)
    RankingOrigen       INT NULL,                    -- contexto histórico al programar
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
    CONSTRAINT FK_AgendaItems_Snapshots FOREIGN KEY (SnapshotId)
        REFERENCES app.RankingSnapshots (Id),
    CONSTRAINT FK_AgendaItems_RankingItems FOREIGN KEY (SnapshotItemId)
        REFERENCES app.RankingItems (Id) ON DELETE SET NULL,
    CONSTRAINT CK_AgendaItems_Estado CHECK (Estado IN (N'programada', N'realizada', N'cancelada')),
    CONSTRAINT CK_AgendaItems_Horizonte CHECK (Horizonte IN ('1m', '3m'))
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_AgendaItems_Estado_Fecha' AND object_id = OBJECT_ID(N'app.AgendaItems')
)
CREATE INDEX IX_AgendaItems_Estado_Fecha
    ON app.AgendaItems (Estado, FechaPlanificada);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_AgendaItems_Usuario_Estado' AND object_id = OBJECT_ID(N'app.AgendaItems')
)
CREATE INDEX IX_AgendaItems_Usuario_Estado
    ON app.AgendaItems (UsuarioId, Estado);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_AgendaItems_Establecimiento' AND object_id = OBJECT_ID(N'app.AgendaItems')
)
CREATE INDEX IX_AgendaItems_Establecimiento
    ON app.AgendaItems (IdEstablecimiento);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UQ_AgendaItems_Programada_Establecimiento' AND object_id = OBJECT_ID(N'app.AgendaItems')
)
CREATE UNIQUE INDEX UQ_AgendaItems_Programada_Establecimiento
    ON app.AgendaItems (IdEstablecimiento)
    WHERE Estado = N'programada';
GO

IF OBJECT_ID(N'app.VisitasApp', N'U') IS NULL
CREATE TABLE app.VisitasApp (
    Id                  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_VisitasApp PRIMARY KEY,
    IdEstablecimiento   CHAR(64) NOT NULL,
    UsuarioId           INT NOT NULL,
    AgendaItemId        INT NULL,
    FechaHoraReal       DATETIME2(0) NOT NULL,
    Tipo                NVARCHAR(40) NOT NULL,  -- predictiva | regulatoria | seguimiento | extraordinaria
    Resultado           NVARCHAR(30) NOT NULL,  -- realizada | no_realizada
    MotivoNoRealizada   NVARCHAR(200) NULL,
    Hallazgos           NVARCHAR(MAX) NULL,
    Acciones            NVARCHAR(MAX) NULL,
    CreadoEn            DATETIME2(0) NOT NULL CONSTRAINT DF_VisitasApp_CreadoEn DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_VisitasApp_Usuarios FOREIGN KEY (UsuarioId) REFERENCES app.Usuarios (Id),
    CONSTRAINT FK_VisitasApp_Agenda FOREIGN KEY (AgendaItemId) REFERENCES app.AgendaItems (Id),
    CONSTRAINT CK_VisitasApp_Resultado CHECK (Resultado IN (N'realizada', N'no_realizada'))
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UQ_VisitasApp_AgendaItem' AND object_id = OBJECT_ID(N'app.VisitasApp')
)
CREATE UNIQUE INDEX UQ_VisitasApp_AgendaItem
    ON app.VisitasApp (AgendaItemId)
    WHERE AgendaItemId IS NOT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_VisitasApp_Establecimiento_Fecha' AND object_id = OBJECT_ID(N'app.VisitasApp')
)
CREATE INDEX IX_VisitasApp_Establecimiento_Fecha
    ON app.VisitasApp (IdEstablecimiento, FechaHoraReal DESC);
GO

/* ---------- Auditoría agenda ---------- */

IF OBJECT_ID(N'app.AgendaEventos', N'U') IS NULL
CREATE TABLE app.AgendaEventos (
    Id                  BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_AgendaEventos PRIMARY KEY,
    AgendaItemId        INT NOT NULL,
    SnapshotItemId      BIGINT NULL,
    IdEstablecimiento   CHAR(64) NOT NULL,
    Tipo                NVARCHAR(30) NOT NULL,
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

/* ---------- SHAP por ítem de ranking ---------- */

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
    Direccion           NVARCHAR(20) NOT NULL,
    Descripcion         NVARCHAR(500) NULL,
    CONSTRAINT FK_RankingItemContribuciones_Item FOREIGN KEY (RankingItemId)
        REFERENCES app.RankingItems (Id) ON DELETE CASCADE,
    CONSTRAINT CK_RankingItemContribuciones_Direccion CHECK (Direccion IN (N'aumenta', N'reduce')),
    CONSTRAINT UQ_RankingItemContribuciones_ItemOrden UNIQUE (RankingItemId, Orden)
);
GO

/* ---------- Config ---------- */

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

IF OBJECT_ID(N'app.RankingItemOutcomes', N'U') IS NULL
CREATE TABLE app.RankingItemOutcomes (
    Id                  BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RankingItemOutcomes PRIMARY KEY,
    RankingItemId       BIGINT NOT NULL,
    SnapshotId          INT NOT NULL,
    PeriodoDecision     CHAR(7) NOT NULL,
    Horizonte           VARCHAR(2) NOT NULL,
    VentanaInicio       CHAR(7) NOT NULL,
    VentanaFin          CHAR(7) NOT NULL,
    Estado              NVARCHAR(20) NOT NULL,
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
    Estado              NVARCHAR(20) NOT NULL,
    CorteEn             DATETIME2(0) NULL,
    CalculadoEn         DATETIME2(0) NOT NULL CONSTRAINT DF_SnapshotCoberturas_CalculadoEn DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_SnapshotCoberturas_Snapshot FOREIGN KEY (SnapshotId)
        REFERENCES app.RankingSnapshots (Id) ON DELETE CASCADE,
    CONSTRAINT CK_SnapshotCoberturas_TopK CHECK (TopK IN (50, 225)),
    CONSTRAINT CK_SnapshotCoberturas_Estado CHECK (Estado IN (N'abierta', N'cerrada')),
    CONSTRAINT UQ_SnapshotCoberturas_Key UNIQUE (SnapshotId, TopK)
);
GO

IF OBJECT_ID(N'app.AppConfig', N'U') IS NULL
CREATE TABLE app.AppConfig (
    Clave       NVARCHAR(80) NOT NULL CONSTRAINT PK_AppConfig PRIMARY KEY,
    Valor       NVARCHAR(400) NOT NULL,
    Actualizado DATETIME2(0) NOT NULL CONSTRAINT DF_AppConfig_Actualizado DEFAULT (SYSUTCDATETIME())
);
GO

/* ---------- Seeds ---------- */

IF NOT EXISTS (SELECT 1 FROM app.Zonas WHERE Nombre = N'Zona Centro')
    INSERT INTO app.Zonas (Nombre) VALUES (N'Zona Centro');

IF NOT EXISTS (SELECT 1 FROM app.Zonas WHERE Nombre = N'Zona Norte')
    INSERT INTO app.Zonas (Nombre) VALUES (N'Zona Norte');

IF NOT EXISTS (SELECT 1 FROM app.Zonas WHERE Nombre = N'Zona Sur')
    INSERT INTO app.Zonas (Nombre) VALUES (N'Zona Sur');
GO

MERGE app.AppConfig AS t
USING (VALUES
    (N'capacidad_criticos', N'50'),
    (N'capacidad_mensual', N'225'),
    (N'capacidad_trimestral', N'675'),
    (N'cooldown_meses', N'3'),
    (N'horizonte_default', N'1m'),
    (N'periodo_vigente_1m', N'2025-10'),
    (N'periodo_vigente_3m', N'2025-08')
) AS s (Clave, Valor)
ON t.Clave = s.Clave
WHEN MATCHED THEN UPDATE SET Valor = s.Valor, Actualizado = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (Clave, Valor) VALUES (s.Clave, s.Valor);
GO

/* Usuario demo: admin@pfi.local / Admin123!
   Hash PBKDF2 generado por la API al primer arranque si no existe;
   placeholder marcado para que el seeder .NET lo reemplace. */
IF NOT EXISTS (SELECT 1 FROM app.Usuarios WHERE Email = N'admin@pfi.local')
BEGIN
    DECLARE @zona INT = (SELECT TOP (1) Id FROM app.Zonas ORDER BY Id);
    INSERT INTO app.Usuarios (Email, Nombre, PasswordHash, Rol, ZonaId, Activo)
    VALUES (
        N'admin@pfi.local',
        N'Administrador PFI',
        N'PENDING_SEED',
        N'Admin',
        @zona,
        1
    );
END
GO

PRINT 'Schema app aplicado en PfiPrevencion.';
GO
