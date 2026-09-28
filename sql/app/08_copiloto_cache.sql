/*
  Caché de respuestas del copiloto normativo por establecimiento + sección.
  Idempotente. Ejecutar sobre PfiPrevencion (localhost).
*/

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'app')
    EXEC(N'CREATE SCHEMA app');
GO

IF OBJECT_ID(N'app.CopilotoRespuestaCache', N'U') IS NULL
BEGIN
    CREATE TABLE app.CopilotoRespuestaCache
    (
        Id                 int IDENTITY(1,1) NOT NULL PRIMARY KEY,
        IdEstablecimiento  varchar(64)    NOT NULL,
        Seccion            nvarchar(80)   NOT NULL,
        Pregunta           nvarchar(800)  NOT NULL,
        Tema               nvarchar(64)   NOT NULL,
        Actividad          nvarchar(16)   NULL,
        Respuesta          nvarchar(max)  NOT NULL,
        Modelo             nvarchar(80)   NOT NULL,
        SinFundamento      bit            NOT NULL CONSTRAINT DF_CopilotoCache_SinFundamento DEFAULT 0,
        GeneradoEn         datetime2      NOT NULL CONSTRAINT DF_CopilotoCache_GeneradoEn DEFAULT SYSUTCDATETIME()
    );

    CREATE UNIQUE INDEX UX_CopilotoCache_Est_Seccion
        ON app.CopilotoRespuestaCache (IdEstablecimiento, Seccion);
END;
GO
