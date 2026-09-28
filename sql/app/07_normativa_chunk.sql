/*
  Corpus normativo para copiloto RAG (Prevex).
  Idempotente. Ejecutar sobre PfiPrevencion (localhost).
*/

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'app')
    EXEC(N'CREATE SCHEMA app');
GO

IF OBJECT_ID(N'app.NormativaChunk', N'U') IS NULL
BEGIN
    CREATE TABLE app.NormativaChunk
    (
        Id          int IDENTITY(1,1) NOT NULL PRIMARY KEY,
        SourceId    nvarchar(32)  NOT NULL,
        Titulo      nvarchar(200) NOT NULL,
        Texto       nvarchar(max) NOT NULL,
        Tema        nvarchar(64)  NOT NULL,
        Actividad   nvarchar(16)  NULL,
        NormaRef    nvarchar(120) NULL,
        Orden       int           NOT NULL CONSTRAINT DF_NormativaChunk_Orden DEFAULT 0,
        Activo      bit           NOT NULL CONSTRAINT DF_NormativaChunk_Activo DEFAULT 1,
        CreadoEn    datetime2     NOT NULL CONSTRAINT DF_NormativaChunk_CreadoEn DEFAULT SYSUTCDATETIME()
    );

    CREATE INDEX IX_NormativaChunk_Tema_Actividad
        ON app.NormativaChunk (Tema, Actividad)
        INCLUDE (SourceId, Orden);

    CREATE INDEX IX_NormativaChunk_Source_Orden
        ON app.NormativaChunk (SourceId, Orden);
END;
GO
