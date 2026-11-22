# Pipeline ML — Python

Panel **establecimiento × mes**, modelos XGBoost (1m / 3m) y ranking de riesgo a partir de los datasets anonimizados en `data/raw/`.

## Requisitos

- Python 3.12+
- Datasets en `data/raw/` (csv/parquet de entrega) y/o panel en `data/processed/`

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

Con los parquet ya presentes en el repo:

```powershell
$env:PYTHONPATH="src"
python scripts/run_pipeline.py --skip-export --horizon both
```

Pasos habituales:

1. Fuentes → `data/raw/*.parquet` (ya versionados en la entrega)
2. Panel → `data/processed/panel_establecimiento_mes.parquet`
3. Entrenamiento → `models/model_pipeline_{1m,3m}.joblib` (local; no versionado)
4. Evaluación → `reports/modelo/` (local)
5. Ranking / SHAP → `reports/ranking/` (hay copia de entrega versionada)

### Flags útiles

| Flag | Uso |
|------|-----|
| `--skip-export` | Usar parquet ya exportado (recomendado en entrega) |
| `--skip-panel` | Reentrenar sin reconstruir el panel |
| `--horizon 1m\|3m\|both` | Horizonte(s) a entrenar/evaluar |
| `--skip-shap` | Omitir SHAP |
| `--skip-ranking` | Omitir ranking maestro |

## Scripts por paso

| Script | Salida principal |
|--------|------------------|
| `csv_to_parquet.py` | `data/raw/*.parquet` desde CSV |
| `universe_csv_to_parquet.py` | `data/raw/establecimientos_universo.parquet` |
| `build_panel.py` | `data/processed/panel_establecimiento_mes.parquet` |
| `run_pipeline.py` | Orquesta panel + train + ranking |
| `audit_data_quality.py` | `reports/dataset/data_quality_audit.json` |

Ver `reports/README.md` y `docs/entrega-datos/REPORTE_DATASETS.md`.

## Grano del panel

| Fuente | Panel |
|--------|-------|
| 1 fila = 1 accidente (export) | 1 fila = 1 establecimiento × mes |
| Accidentes hasta 2025-11 | ~1,67M filas con universo completo |

**Targets**

- `target_accidente_mes_siguiente` (1m) — ≥1 accidente en T+1
- `target_accidente_3m` (3m) — ≥1 accidente en T+1..T+3

**Features:** solo información disponible antes del mes objetivo.

## Split temporal y métricas

| Rol | Año |
|-----|-----|
| Train | 2022–2023 |
| Calibración (umbral F2) | 2024 |
| Holdout / test oficial | **2025** |

Métricas principales: PR-AUC, recall, **precision@top-K** (50 / 225) y lift vs visitas reales / historial / azar.

## Artefactos

| Archivo | Rol |
|---------|-----|
| `data/raw/*.parquet` | Fuentes anonimizadas de entrega |
| `data/processed/panel_establecimiento_mes.parquet` | Panel ML |
| `reports/ranking/ranking_maestro_*` | Lista operativa (entrega) |
| `models/model_pipeline_*.joblib` | Modelos entrenados (local) |

## Notebook

`notebooks/01_eda_accidentes.ipynb` — exploración interactiva sobre el parquet.
