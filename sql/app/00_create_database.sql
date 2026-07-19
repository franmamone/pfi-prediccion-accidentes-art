/*
  BD operativa de la app de prevención (NO es el core ART/ART).

  Instancia: localhost (SQL Server 2025 Developer)
  Base:      PfiPrevencion

  Aplicar:
    sqlcmd -S localhost -E -i sql/app/00_create_database.sql
    sqlcmd -S localhost -E -i sql/app/01_schema.sql
*/

IF DB_ID(N'PfiPrevencion') IS NULL
BEGIN
    CREATE DATABASE [PfiPrevencion];
    PRINT 'Base PfiPrevencion creada.';
END
ELSE
    PRINT 'Base PfiPrevencion ya existe.';
GO
