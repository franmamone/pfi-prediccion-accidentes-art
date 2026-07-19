# Pipeline ML — Python

Exportación, EDA, panel **establecimiento × mes**, modelos XGBoost (1m / 3m) y ranking de riesgo.

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
$env:PYTHONPATH="src"
```

Notebooks (opcional): `pip install -r requirements.txt`

## Pipeline completo

```powershell
$env:PYTHONPATH="src"
python scripts/run_pipeline.py --horizon both
```

Pasos que ejecuta:

1. Export SQL → `data/raw/*.parquet` (o CSV manual + conversiones)
2. EDA → `reports/eda/`
3. Panel → `data/processed/panel_establecimiento_mes.parquet`
4. Entrenamiento → `models/model_pipeline_{1m,3m}.joblib`
5. Evaluación → `reports/modelo/`, scored panels → `reports/ranking/`
6. Ranking maestro → `reports/ranking/`
7. SHAP → `reports/shap/` (omitible con `--skip-shap`)
8. Reportes dataset → `reports/dataset/`

### Flags útiles

| Flag | Uso |
|------|-----|
| `--skip-export` | Usar parquet ya exportado |
| `--skip-panel` | Reentrenar sin reconstruir el panel |
| `--horizon 1m\|3m\|both` | Horizonte(s) a entrenar/evaluar |
| `--skip-shap` | Omitir SHAP |
| `--skip-ranking` | Omitir ranking maestro |
| `--ablations` | Comparar aportes de features |

### Universo de establecimientos

1. En SSMS: `SELECT * FROM ml.vw_establecimientos_universo_ml` → `data/raw/establecimientos_universo.csv`
2. `python scripts/universe_csv_to_parquet.py`
3. `python scripts/run_pipeline.py --skip-export`

## Export manual desde SSMS

Si Python no conecta por SSPI o el `SELECT *` da timeout, exportá por año (ver `docs/export-datos-2025.md`) y luego:

```powershell
python scripts/csv_to_parquet.py --input data/raw
python scripts/run_pipeline.py --skip-export --horizon both
```

## Scripts por paso

| Script | Salida principal |
|--------|------------------|
| `export_accidents.py` | `data/raw/accidentes_ml.parquet` |
| `csv_to_parquet.py` | `data/raw/accidentes_ml.parquet` |
| `universe_csv_to_parquet.py` | `data/raw/establecimientos_universo.parquet` |
| `run_eda.py` | `reports/eda/` |
| `build_panel.py` | `data/processed/panel_establecimiento_mes.parquet` |
| `train_baseline.py` | `models/model_pipeline_*.joblib` + `reports/modelo/` |
| `export_top_riesgo.py` | `reports/ranking/top_riesgo.csv` |
| `audit_data_quality.py` | `reports/dataset/data_quality_audit.json` |
| `parquet_to_csv.py` | dumps en `reports/legacy/` |

Ver `reports/README.md` para la organización de artefactos.

## Grano del panel

| Vista SQL | Panel |
|-----------|-------|
| 1 fila = 1 accidente | 1 fila = 1 establecimiento × mes |
| Accidentes hasta 2025-11 | ~1,67M filas con universo completo |

**Targets**

- `target_accidente_mes_siguiente` (1m) — ≥1 accidente en T+1
- `target_accidente_3m` (3m) — ≥1 accidente en T+1..T+3

**Features:** solo información disponible antes del mes objetivo. Columnas post-accidente excluidas (`LEAKAGE_COLUMNS` en `config.py`).

## Split temporal y métricas

| Rol | Año |
|-----|-----|
| Train | 2022–2023 |
| Calibración (umbral F2) | 2024 |
| Holdout / test oficial | **2025** |

Métricas principales: PR-AUC, recall, **precision@top-K** (50 / 225) y lift vs visitas reales / historial / azar.

## Artefactos del modelo

| Archivo | Rol |
|---------|-----|
| `models/model_pipeline_1m.joblib` | Pipeline horizonte mensual |
| `models/model_pipeline_3m.joblib` | Pipeline horizonte trimestral |
| `reports/modelo/evaluation_metrics_{1m,3m}.json` | Métricas holdout + top-K |
| `reports/modelo/baseline_comparison_{1m,3m}.json` | Modelo vs visitas/historial/azar |
| `reports/ranking/ranking_maestro_*.csv` | Lista operativa |
| `reports/ranking/ranking_contract.json` | Contrato API / React |

## Notebook

`notebooks/01_eda_accidentes.ipynb` — exploración interactiva sobre el parquet.
