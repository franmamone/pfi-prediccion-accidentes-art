# PFI — Predicción de accidentes ART

Proyecto Final de Ingeniería (UADE): sistema predictivo de accidentabilidad laboral para aseguradoras de riesgo del trabajo.

## Estructura

```
docs/           Informe LaTeX + bitácora
sql/ml/         Vistas SQL Server (accidentes, universo, prevención, nómina)
src/            Paquete Python `pfi_prediccion`
scripts/        CLIs del pipeline
notebooks/      EDA interactiva
data/           Parquets locales (gitignored)
reports/        Artefactos por subcarpeta (eda, modelo, ranking, shap, dataset, legacy)
models/         Modelos entrenados (gitignored)
tests/          Tests unitarios (targets, splits)
```

## Flujo de datos

1. **SQL** — Vistas en `ART_CORE` (`sql/ml/`), datos hasta 2025-12
2. **Export** — Parquet en `data/raw/`
3. **Panel** — Agregación establecimiento × mes con targets 1m y 3m
4. **Modelo** — XGBoost dual (horizontes `1m` / `3m`)
5. **Ranking** — Lista maestra de establecimientos en riesgo para Preventores

Split oficial: **train 2022–2023 · calibración 2024 · holdout 2025**.

Guía de setup y comandos: [`python/README.md`](python/README.md)

Bitácora de decisiones: [`docs/bitacora/bitacora.md`](docs/bitacora/bitacora.md)

Organización de reportes: [`reports/README.md`](reports/README.md)

## Resultado vigente (holdout 2025)

| Métrica | 1m | 3m |
|---------|----|----|
| PR-AUC | 0,366 | 0,515 |
| Precision @ top-50 / mes | 76,4% | 93,5% |
| Precision @ top-225 / mes | 51,5% | 79,0% |
| Visitas reales @ mismo volumen | 10,3% | 17,8% |

Panel ~1,67M filas · ~35.500 establecimientos. Detalle en bitácora §17.
