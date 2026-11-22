# reports/

Salidas del pipeline ML. En la entrega quedan versionados el **ranking** y la auditoría de calidad; el resto suele generarse en local.

| Carpeta | Contenido | En Git (entrega) |
|---------|-----------|------------------|
| `ranking/` | `ranking_maestro_*`, contribuciones SHAP | Sí |
| `dataset/` | `data_quality_audit.json` (+ README) | Parcial |
| `eda/`, `modelo/`, `shap/`, `legacy/` | Exploración / métricas / dumps | No (gitignore) |

Split oficial: train 2022–2023 · calibración 2024 · holdout **2025**. Horizontes: `1m` y `3m`.

Detalle de datasets: [`../docs/entrega-datos/REPORTE_DATASETS.md`](../docs/entrega-datos/REPORTE_DATASETS.md).  
Gráficos de dataset (si se regeneran): [`dataset/README.md`](dataset/README.md).
