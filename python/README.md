# Pipeline ML — Python

Exportación, EDA, panel **establecimiento × mes**, modelo XGBoost y ranking de riesgo.

## Requisitos

- Python 3.12+
- ODBC Driver 17/18 for SQL Server (solo si exportás desde Python; el flujo habitual es SSMS)
- Acceso a `ART_CORE` en la misma red que SSMS

## Setup

```powershell
cd <ruta-del-repo>
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-core.txt
# opcional: pip install -e .
copy .env.example .env
```

Notebooks (opcional): `pip install -r requirements.txt`

## Pipeline completo

```powershell
python scripts/run_pipeline.py
```

Pasos que ejecuta:

1. Export SQL → `data/raw/accidentes_ml.parquet` (o CSV manual + `csv_to_parquet.py`)
2. EDA → `reports/eda_*`
3. Panel → `data/processed/panel_establecimiento_mes.parquet`
4. Entrenamiento → `models/model_pipeline.joblib`
5. Evaluación → `reports/evaluation_metrics.json`, `reports/model_evaluation.png`

### Flags útiles

| Flag | Uso |
|------|-----|
| `--skip-export` | Usar parquet de accidentes ya exportado |
| `--skip-panel` | Reentrenar sin reconstruir el panel (~3 min menos) |

### Universo de establecimientos

Para incluir todos los empleadores (no solo los que tuvieron accidentes):

1. En SSMS: `SELECT * FROM ml.vw_establecimientos_universo_ml` → `data/raw/establecimientos_universo.csv`
2. `python scripts/universe_csv_to_parquet.py`
3. `python scripts/run_pipeline.py --skip-export`

Si existe `data/raw/establecimientos_universo.parquet`, el pipeline lo carga automáticamente.

## Export manual desde SSMS

Si Python no conecta por SSPI o el `SELECT *` da timeout (error 10053), exportá por año con `sql/ml/04_export_por_anio.sql` y luego:

```powershell
python scripts/csv_to_parquet.py --input data/raw
python scripts/run_pipeline.py --skip-export
```

## Scripts por paso

| Script | Salida principal |
|--------|------------------|
| `export_accidents.py` | `data/raw/accidentes_ml.parquet` |
| `csv_to_parquet.py` | `data/raw/accidentes_ml.parquet` |
| `universe_csv_to_parquet.py` | `data/raw/establecimientos_universo.parquet` |
| `run_eda.py` | `reports/eda_*` |
| `build_panel.py` | `data/processed/panel_establecimiento_mes.parquet` |
| `train_baseline.py` | `models/model_pipeline.joblib` + métricas |
| `export_top_riesgo.py` | `reports/top_riesgo.csv` |
| `parquet_to_csv.py` | utilidad para abrir en Excel |

## Grano del panel

| Vista SQL | Panel |
|-----------|-------|
| 1 fila = 1 accidente | 1 fila = 1 establecimiento × mes |
| ~18,5k filas (2022–2024) | ~1,2M filas con universo completo |

**Target:** `target_accidente_mes_siguiente` — 1 si hay ≥1 accidente en T+1.

**Features:** solo información disponible antes del mes objetivo. Columnas post-accidente excluidas (`LEAKAGE_COLUMNS` en `config.py`).

## Split temporal y métricas

- **Train:** 2022–2023
- **Validación (umbral F2):** 2023
- **Test:** 2024
- **Holdout futuro:** 2025 (no incluido en la vista)

Métricas principales: PR-AUC, recall, **precision@top-K** y lift (las dos últimas son las operativas para priorizar visitas).

## Artefactos del modelo

| Archivo | Rol |
|---------|-----|
| `models/model_pipeline.joblib` | Pipeline sklearn + umbral (inferencia) |
| `models/xgboost_model.json` | Booster XGBoost suelto |
| `reports/model_metrics.json` | Métricas de test |
| `reports/evaluation_metrics.json` | Recall@top-K |
| `reports/top_riesgo.csv` | Ranking mensual exportable |

`baseline_*.json` se generan como alias de compatibilidad con corridas anteriores.

## Notebook

`notebooks/01_eda_accidentes.ipynb` — exploración interactiva sobre el parquet.
