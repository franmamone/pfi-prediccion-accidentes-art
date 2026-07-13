# PFI — Predicción de accidentes ART

Proyecto Final de Ingeniería (UADE): sistema predictivo de accidentabilidad laboral para aseguradoras de riesgo del trabajo.

## Estructura

```
docs/           Informe LaTeX + bitácora
sql/ml/         Vistas SQL Server (accidentes + universo de establecimientos)
src/            Paquete Python `pfi_prediccion`
scripts/        CLIs del pipeline
notebooks/      EDA interactiva
data/           Parquets locales (gitignored)
reports/        EDA, métricas, rankings
models/         Modelos entrenados (gitignored)
```

## Flujo de datos

1. **SQL** — Vistas en `ART_CORE` (`sql/ml/`)
2. **Export** — Parquet en `data/raw/`
3. **Panel** — Agregación establecimiento × mes con target T+1
4. **Modelo** — XGBoost con split temporal (train 2022–2023, test 2024)
5. **Ranking** — Top-N establecimientos en mayor riesgo para prevencionistas

Guía de setup y comandos: [`python/README.md`](python/README.md)

Bitácora de decisiones: [`docs/bitacora/bitacora.md`](docs/bitacora/bitacora.md)

## Resultado actual (panel universo)

- ~35.500 establecimientos, ~1,2M filas-mes
- Precision @ top-50 en test 2024: **~88%**
- Ver métricas completas en `reports/evaluation_metrics.json`
