-- Respuestas del copiloto que el preventor guarda para preparar la visita.
IF OBJECT_ID(N'app.CopilotoGuardado', N'U') IS NULL
BEGIN
    CREATE TABLE app.CopilotoGuardado
    (
        Id                 int IDENTITY(1,1) NOT NULL PRIMARY KEY,
        UsuarioId          int            NOT NULL,
        IdEstablecimiento  varchar(64)    NOT NULL,
        Pregunta           nvarchar(800)  NOT NULL,
        Respuesta          nvarchar(max)  NOT NULL,
        Tema               nvarchar(64)   NULL,
        Seccion            nvarchar(80)   NULL,
        Modelo             nvarchar(80)   NULL,
        GuardadoEn         datetime2      NOT NULL CONSTRAINT DF_CopilotoGuardado_GuardadoEn DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_CopilotoGuardado_Usuario FOREIGN KEY (UsuarioId) REFERENCES app.Usuarios (Id)
    );

    CREATE INDEX IX_CopilotoGuardado_User_Est
        ON app.CopilotoGuardado (UsuarioId, IdEstablecimiento, GuardadoEn DESC);
END
GO
