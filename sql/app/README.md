# SQL Server — BD operativa de la app

Base **PfiPrevencion** en `localhost` (instancia default).  
No es el core ART (`ART_CORE`); solo rankings importados, agenda, visitas y usuarios.

## Requisitos

- SQL Server 2025 Developer (o Express) en localhost
- Autenticación Windows (`-E`) o SQL auth en connection string
- `sqlcmd` en el PATH

## Crear / actualizar

```powershell
sqlcmd -S localhost -E -i sql/app/00_create_database.sql
sqlcmd -S localhost -E -i sql/app/01_schema.sql
# Si la BD ya existía con el schema anterior de agenda:
sqlcmd -S localhost -E -i sql/app/02_migrate_agenda_visitas.sql
# Auditoría append-only + contribuciones SHAP:
sqlcmd -S localhost -E -i sql/app/03_add_agenda_eventos_y_shap.sql
# Analítica histórica (snapshots versionados, SHAP agregado, outcomes, cobertura):
sqlcmd -S localhost -E -i sql/app/04_add_analitica_historica.sql
```

Flujo de visitas: `programada` → `realizada` | `cancelada` (tablas `app.AgendaItems` + `app.VisitasApp`).  
Auditoría: `app.AgendaEventos` (append-only; actor = usuario autenticado).  
SHAP por ítem: `app.RankingItemContribuciones` (top factores del ranking importado).  
SHAP agregado: `app.SnapshotShapAgregados` (matriz completa, top 50 / top 225).  
Outcomes / precisión: `app.RankingItemOutcomes`, `app.SnapshotMetricasObservadas` (estados `pendiente|parcial|maduro`).  
Cobertura por cohorte: `app.SnapshotCoberturas` (anclada a `ActivadoEn`, no al mes del ranking).  
Snapshots: versionados por `ArtifactHash`; un vigente por horizonte (`EsVigente`).

**Importante:** no reejecutar `02_migrate_agenda_visitas.sql` sobre una BD ya migrada (hace drop/recreate de agenda).  
`04_add_analitica_historica.sql` es idempotente (IF COL_LENGTH / IF OBJECT_ID).

## Connection string (API)

```
Server=localhost;Database=PfiPrevencion;Trusted_Connection=True;TrustServerCertificate=True;Encrypt=True
```

## Regenerar ranking con SHAP e importar

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe scripts\export_ranking_shap.py --periodo 2025-11
.\.venv\Scripts\python.exe scripts\import_ranking_to_app.py --periodo 2025-11
# Mismo hash → noop; hash nuevo → nueva versión sin borrar la anterior.
```

## Actualizar precisión observada y cobertura

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe scripts\update_observed_metrics.py --fuente-completa-hasta 2025-10
```

`--fuente-completa-hasta` es obligatorio: solo marca `maduro` las ventanas totalmente cubiertas.  
La cobertura operativa se refresca mientras la ventana está abierta y se congela al cerrarla.

## Usuarios

- Reales: crear por invitación / ABM en la app (no hay seed de admin genérico).
- Demo cercanía CABA (API al arrancar): `prev.palermo@prevex.local` … `prev.caballito@prevex.local` / `Prev123!`
