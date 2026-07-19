# reports/

Artefactos generados por el pipeline (gitignored, salvo este README y `.gitkeep`).

| Carpeta | Contenido |
|---------|-----------|
| `eda/` | EDA de accidentes (`eda_*.png`, `eda_*.csv`) |
| `modelo/` | Métricas, evaluation, classification reports, curvas PR, baseline vs visitas |
| `ranking/` | `ranking_maestro_*`, `ranking_contract.json`, `scored_panel_holdout_*`, `top_k_*`, `top_riesgo.csv` |
| `shap/` | Explicabilidad SHAP (`shap_*.png`, `shap_report.json`) |
| `dataset/contexto_2022_2025/` | Descripción completa del problema, calidad y anomalías; 2025 parcial |
| `dataset/entrenamiento_2022_2023/` | Variables y targets que realmente ajustan el modelo |
| `dataset/desempeno_holdout_2025/` | Precisión fuera de muestra, condiciones, calibración y baselines |
| `dataset/data_quality_audit.json` | Auditoría automática del panel y fuentes |
| `legacy/` | Aliases viejos, holdout 2024, logs de pipeline, dumps CSV grandes |

Split oficial: train 2022–2023 · calibración 2024 · holdout **2025**. Horizontes: `1m` y `3m`.

Rutas centralizadas en `src/pfi_prediccion/config.py` (`REPORTS_*_DIR`).

Regla de lectura:

- contexto: 2022–2025;
- entrenamiento: solo 2022–2023;
- calibración: 2024, sin presentarla como resultado final;
- desempeño: solo holdout 2025.

Detalle de cada gráfico: [`dataset/README.md`](dataset/README.md).
