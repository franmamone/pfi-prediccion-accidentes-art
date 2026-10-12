/*
  Usuarios: MFA, coords, disponibilidad semanal.
  AuthToken: invite / reset.
  EstablecimientoUbicacion: coords demo CABA.
*/
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE [PfiPrevencion];
GO

IF COL_LENGTH(N'app.Usuarios', N'Latitud') IS NULL
    ALTER TABLE app.Usuarios ADD Latitud FLOAT NULL;
GO
IF COL_LENGTH(N'app.Usuarios', N'Longitud') IS NULL
    ALTER TABLE app.Usuarios ADD Longitud FLOAT NULL;
GO
IF COL_LENGTH(N'app.Usuarios', N'MfaRequired') IS NULL
    ALTER TABLE app.Usuarios ADD MfaRequired BIT NOT NULL
        CONSTRAINT DF_Usuarios_MfaRequired DEFAULT (0);
GO
IF COL_LENGTH(N'app.Usuarios', N'MfaEnabled') IS NULL
    ALTER TABLE app.Usuarios ADD MfaEnabled BIT NOT NULL
        CONSTRAINT DF_Usuarios_MfaEnabled DEFAULT (0);
GO
IF COL_LENGTH(N'app.Usuarios', N'MfaSecret') IS NULL
    ALTER TABLE app.Usuarios ADD MfaSecret NVARCHAR(200) NULL;
GO
IF COL_LENGTH(N'app.Usuarios', N'MfaConfirmedEn') IS NULL
    ALTER TABLE app.Usuarios ADD MfaConfirmedEn DATETIME2(0) NULL;
GO
IF COL_LENGTH(N'app.Usuarios', N'DebeCambiarPassword') IS NULL
    ALTER TABLE app.Usuarios ADD DebeCambiarPassword BIT NOT NULL
        CONSTRAINT DF_Usuarios_DebeCambiarPassword DEFAULT (0);
GO
IF COL_LENGTH(N'app.Usuarios', N'MfaRecoveryHashes') IS NULL
    ALTER TABLE app.Usuarios ADD MfaRecoveryHashes NVARCHAR(MAX) NULL;
GO

IF COL_LENGTH(N'app.Usuarios', N'MfaRequired') IS NOT NULL
    UPDATE app.Usuarios SET MfaRequired = 1 WHERE MfaEnabled = 1 AND MfaRequired = 0;
GO

IF OBJECT_ID(N'app.UsuarioDisponibilidad', N'U') IS NULL
CREATE TABLE app.UsuarioDisponibilidad (
    Id          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_UsuarioDisponibilidad PRIMARY KEY,
    UsuarioId   INT NOT NULL,
    DiaSemana   TINYINT NOT NULL,  -- 1=Lun .. 7=Dom (ISO)
    HoraDesde   TIME(0) NOT NULL,
    HoraHasta   TIME(0) NOT NULL,
    CONSTRAINT FK_UsuarioDisponibilidad_Usuarios FOREIGN KEY (UsuarioId) REFERENCES app.Usuarios (Id) ON DELETE CASCADE,
    CONSTRAINT CK_UsuarioDisponibilidad_Dia CHECK (DiaSemana BETWEEN 1 AND 7),
    CONSTRAINT CK_UsuarioDisponibilidad_Rango CHECK (HoraHasta > HoraDesde)
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_UsuarioDisponibilidad_Usuario_Dia'
      AND object_id = OBJECT_ID(N'app.UsuarioDisponibilidad')
)
CREATE INDEX IX_UsuarioDisponibilidad_Usuario_Dia
    ON app.UsuarioDisponibilidad (UsuarioId, DiaSemana);
GO

IF OBJECT_ID(N'app.AuthToken', N'U') IS NULL
CREATE TABLE app.AuthToken (
    Id          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_AuthToken PRIMARY KEY,
    UsuarioId   INT NOT NULL,
    Tipo        NVARCHAR(20) NOT NULL,  -- invite | reset
    TokenHash   CHAR(64) NOT NULL,
    ExpiraEn    DATETIME2(0) NOT NULL,
    UsadoEn     DATETIME2(0) NULL,
    CreadoEn    DATETIME2(0) NOT NULL CONSTRAINT DF_AuthToken_CreadoEn DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_AuthToken_Usuarios FOREIGN KEY (UsuarioId) REFERENCES app.Usuarios (Id) ON DELETE CASCADE,
    CONSTRAINT CK_AuthToken_Tipo CHECK (Tipo IN (N'invite', N'reset'))
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_AuthToken_Hash'
      AND object_id = OBJECT_ID(N'app.AuthToken')
)
CREATE UNIQUE INDEX IX_AuthToken_Hash ON app.AuthToken (TokenHash);
GO

IF OBJECT_ID(N'app.EstablecimientoUbicacion', N'U') IS NULL
CREATE TABLE app.EstablecimientoUbicacion (
    IdEstablecimiento NVARCHAR(64) NOT NULL CONSTRAINT PK_EstablecimientoUbicacion PRIMARY KEY,
    Latitud           FLOAT NOT NULL,
    Longitud          FLOAT NOT NULL,
    Barrio            NVARCHAR(80) NULL,
    ActualizadoEn     DATETIME2(0) NOT NULL CONSTRAINT DF_EstUbic_ActualizadoEn DEFAULT (SYSUTCDATETIME())
);
GO
