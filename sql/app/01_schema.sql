/*
  Schema operativo de la app PFI Prevención.
  Separado del core ART: solo rankings importados, agenda, visitas y usuarios.
*/

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
    CONSTRAINT UQ_RankingSnapshots_PeriodoHorizonte UNIQUE (Periodo, Horizonte),
    CONSTRAINT CK_RankingSnapshots_Horizonte CHECK (Horizonte IN ('1m', '3m'))
);
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
    UsuarioId           INT NOT NULL,
    IdEstablecimiento   CHAR(64) NOT NULL,
    Periodo             CHAR(7) NOT NULL,
    FechaPlanificada    DATE NOT NULL,
    MotivoVisita        NVARCHAR(40) NOT NULL,  -- predictivo | prs | seguimiento | extraordinaria
    Estado              NVARCHAR(30) NOT NULL,  -- por_agendar | confirmada | en_curso | realizada | no_realizada
    SnapshotItemId      BIGINT NULL,
    Notas               NVARCHAR(1000) NULL,
    CreadoEn            DATETIME2(0) NOT NULL CONSTRAINT DF_AgendaItems_CreadoEn DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_AgendaItems_Usuarios FOREIGN KEY (UsuarioId) REFERENCES app.Usuarios (Id),
    CONSTRAINT FK_AgendaItems_RankingItems FOREIGN KEY (SnapshotItemId) REFERENCES app.RankingItems (Id),
    CONSTRAINT CK_AgendaItems_Estado CHECK (
        Estado IN (N'por_agendar', N'confirmada', N'en_curso', N'realizada', N'no_realizada')
    )
);
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

/* ---------- Config ---------- */

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
