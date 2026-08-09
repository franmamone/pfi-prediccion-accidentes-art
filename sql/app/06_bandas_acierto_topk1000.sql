/*
  Migración idempotente: bandas por acierto histórico + métricas top-1000.

  - RankingItems.Banda: agrega 'bajo' (antes solo critico/alto/medio).
  - SnapshotShapAgregados / SnapshotMetricasObservadas / SnapshotCoberturas:
    permiten TopK = 1000 (antes solo 50/225) para llevar la analítica al top-1000.

  Se puede correr múltiples veces (drop + recreate de los CHECK).
*/

SET NOCOUNT ON;

/* ---- RankingItems.Banda: + 'bajo' ---- */
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_RankingItems_Banda')
    ALTER TABLE app.RankingItems DROP CONSTRAINT CK_RankingItems_Banda;
GO
ALTER TABLE app.RankingItems WITH NOCHECK
    ADD CONSTRAINT CK_RankingItems_Banda CHECK (Banda IN ('critico', 'alto', 'medio', 'bajo'));
GO

/* ---- SnapshotShapAgregados.TopK: + 1000 ---- */
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_SnapshotShapAgregados_TopK')
    ALTER TABLE app.SnapshotShapAgregados DROP CONSTRAINT CK_SnapshotShapAgregados_TopK;
GO
ALTER TABLE app.SnapshotShapAgregados WITH NOCHECK
    ADD CONSTRAINT CK_SnapshotShapAgregados_TopK CHECK (TopK IN (50, 225, 1000));
GO

/* ---- SnapshotMetricasObservadas.TopK: + 1000 ---- */
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_SnapshotMetricasObservadas_TopK')
    ALTER TABLE app.SnapshotMetricasObservadas DROP CONSTRAINT CK_SnapshotMetricasObservadas_TopK;
GO
ALTER TABLE app.SnapshotMetricasObservadas WITH NOCHECK
    ADD CONSTRAINT CK_SnapshotMetricasObservadas_TopK CHECK (TopK IN (50, 225, 1000));
GO

/* ---- SnapshotCoberturas.TopK: + 1000 ---- */
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_SnapshotCoberturas_TopK')
    ALTER TABLE app.SnapshotCoberturas DROP CONSTRAINT CK_SnapshotCoberturas_TopK;
GO
ALTER TABLE app.SnapshotCoberturas WITH NOCHECK
    ADD CONSTRAINT CK_SnapshotCoberturas_TopK CHECK (TopK IN (50, 225, 1000));
GO
