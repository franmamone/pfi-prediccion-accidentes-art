/*
  Contexto del preventor: dossier histórico por establecimiento + caché de
  resúmenes generados por IA (Gemini/Gemma).

  Idempotente. Ejecutar sobre PfiPrevencion (localhost).
  Origen del dossier: data/processed/dossier_preventor.json
  (accidentes y visitas previas de ART_CORE, anonimizados por hash).
*/

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'app')
    EXEC(N'CREATE SCHEMA app');
GO

IF OBJECT_ID(N'app.EstablecimientoDossier', N'U') IS NULL
BEGIN
    CREATE TABLE app.EstablecimientoDossier
    (
        IdEstablecimiento   varchar(64)   NOT NULL PRIMARY KEY,
        Referencia          varchar(10)   NULL,
        Fuente              nvarchar(200) NULL,
        AccidentesTotal     int           NULL,
        AccidentesUlt12m    int           NULL,
        VisitasTotal        int           NULL,
        DossierJson         nvarchar(max) NOT NULL,
        GeneradoEn          datetime2     NOT NULL CONSTRAINT DF_EstDossier_GeneradoEn DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID(N'app.ResumenIaEstablecimiento', N'U') IS NULL
BEGIN
    CREATE TABLE app.ResumenIaEstablecimiento
    (
        Id                 int IDENTITY(1,1) NOT NULL PRIMARY KEY,
        IdEstablecimiento  varchar(64)   NOT NULL,
        Horizonte          varchar(2)    NOT NULL CONSTRAINT DF_ResumenIa_Horizonte DEFAULT '1m',
        Modelo             nvarchar(80)  NOT NULL,
        PromptHash         varchar(64)   NULL,
        Resumen            nvarchar(max) NOT NULL,
        TokensPrompt       int           NULL,
        TokensSalida       int           NULL,
        GeneradoEn         datetime2     NOT NULL CONSTRAINT DF_ResumenIa_GeneradoEn DEFAULT SYSUTCDATETIME()
    );

    CREATE UNIQUE INDEX UX_ResumenIa_Est_Horizonte
        ON app.ResumenIaEstablecimiento (IdEstablecimiento, Horizonte);
END;
GO
