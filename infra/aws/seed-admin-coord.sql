-- Admin y Coordinador para ver priorización (/riesgo). Password: Prev123!
-- Hash BCrypt generado con python bcrypt (compatible con BCrypt.Net).

IF NOT EXISTS (SELECT 1 FROM app.Usuarios WHERE Email = N'admin@pfi.local')
BEGIN
  INSERT INTO app.Usuarios (Email, Nombre, PasswordHash, Rol, ZonaId, Activo, DebeCambiarPassword, CreadoEn)
  VALUES (
    N'admin@pfi.local',
    N'Admin Demo',
    N'$2b$11$64ZRg0AFy3kxpAUff1c1fuouLZYu3yorLN/L.UXd1vYMmxCwRcYMm',
    N'Admin',
    (SELECT TOP 1 Id FROM app.Zonas),
    1,
    0,
    SYSUTCDATETIME()
  );
END;

IF NOT EXISTS (SELECT 1 FROM app.Usuarios WHERE Email = N'coord@pfi.local')
BEGIN
  INSERT INTO app.Usuarios (Email, Nombre, PasswordHash, Rol, ZonaId, Activo, DebeCambiarPassword, CreadoEn)
  VALUES (
    N'coord@pfi.local',
    N'Coordinador Demo',
    N'$2b$11$64ZRg0AFy3kxpAUff1c1fuouLZYu3yorLN/L.UXd1vYMmxCwRcYMm',
    N'Coordinador',
    (SELECT TOP 1 Id FROM app.Zonas),
    1,
    0,
    SYSUTCDATETIME()
  );
END;

SELECT Id, Rol, Email, Activo FROM app.Usuarios ORDER BY Rol, Email;
