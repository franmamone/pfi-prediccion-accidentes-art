-- Hora planificada de visita (además de la fecha).
IF COL_LENGTH(N'app.AgendaItems', N'HoraPlanificada') IS NULL
BEGIN
    ALTER TABLE app.AgendaItems
        ADD HoraPlanificada time NOT NULL
            CONSTRAINT DF_AgendaItems_HoraPlanificada DEFAULT ('09:00:00');
END
GO
