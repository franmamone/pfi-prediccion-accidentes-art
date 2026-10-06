-- Acta estructurada al cerrar una visita (S4 MVP).
IF OBJECT_ID(N'app.VisitaActa', N'U') IS NULL
BEGIN
    CREATE TABLE app.VisitaActa
    (
        Id                   int IDENTITY(1,1) NOT NULL PRIMARY KEY,
        VisitaAppId          int            NOT NULL,
        AgendaItemId         int            NULL,
        ResultadoGlobal      nvarchar(20)   NOT NULL,
        Revisita             bit            NOT NULL CONSTRAINT DF_VisitaActa_Revisita DEFAULT 0,
        PlazoRevisitaDias    int            NULL,
        Notas                nvarchar(max)  NULL,
        ChecklistJson        nvarchar(max)  NULL,
        CreadoEn             datetime2      NOT NULL CONSTRAINT DF_VisitaActa_CreadoEn DEFAULT SYSUTCDATETIME(),
        CreadoPorUsuarioId   int            NULL,
        CONSTRAINT UQ_VisitaActa_VisitaAppId UNIQUE (VisitaAppId),
        CONSTRAINT FK_VisitaActa_VisitaApp FOREIGN KEY (VisitaAppId) REFERENCES app.VisitasApp (Id),
        CONSTRAINT CK_VisitaActa_Resultado CHECK (ResultadoGlobal IN (N'ok', N'observacion', N'critico'))
    );
    CREATE INDEX IX_VisitaActa_Agenda ON app.VisitaActa (AgendaItemId);
END
GO

IF OBJECT_ID(N'app.VisitaHallazgo', N'U') IS NULL
BEGIN
    CREATE TABLE app.VisitaHallazgo
    (
        Id                   int IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ActaId               int            NOT NULL,
        IdEstablecimiento    varchar(64)    NOT NULL,
        Severidad            nvarchar(16)   NOT NULL,
        Hallazgo             nvarchar(max)  NOT NULL,
        Recomendacion        nvarchar(max)  NULL,
        PlazoDias            int            NULL,
        NormaRef             nvarchar(200)  NULL,
        ItemRgrl             nvarchar(120)  NULL,
        Estado               nvarchar(16)   NOT NULL CONSTRAINT DF_VisitaHallazgo_Estado DEFAULT N'abierto',
        Origen               nvarchar(32)   NOT NULL CONSTRAINT DF_VisitaHallazgo_Origen DEFAULT N'manual',
        CreadoEn             datetime2      NOT NULL CONSTRAINT DF_VisitaHallazgo_CreadoEn DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_VisitaHallazgo_Acta FOREIGN KEY (ActaId) REFERENCES app.VisitaActa (Id) ON DELETE CASCADE,
        CONSTRAINT CK_VisitaHallazgo_Severidad CHECK (Severidad IN (N'baja', N'media', N'alta')),
        CONSTRAINT CK_VisitaHallazgo_Estado CHECK (Estado IN (N'abierto', N'cerrado')),
        CONSTRAINT CK_VisitaHallazgo_Origen CHECK (Origen IN (N'manual', N'sugerido_aceptado'))
    );
    CREATE INDEX IX_VisitaHallazgo_Est_Estado
        ON app.VisitaHallazgo (IdEstablecimiento, Estado, CreadoEn DESC);
END
GO
