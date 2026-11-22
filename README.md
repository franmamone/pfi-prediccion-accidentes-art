# PFI — Predicción de accidentes ART

Proyecto Final de Ingeniería (UADE): sistema predictivo de accidentabilidad laboral para aseguradoras de riesgo del trabajo (**Prevex**).

## Estructura

```
apps/           API .NET + frontend React (Vite)
docs/           Informe LaTeX UADE + figuras/tablas
sql/app/        Esquema SQL de la aplicación Prevex
src/            Paquete Python `pfi_prediccion`
scripts/        CLIs del pipeline (panel, train, ranking, import)
data/raw/       Datasets anonimizados (csv/parquet) + encuesta
data/processed/ Panel establecimiento × mes
reports/        Ranking / SHAP de entrega
infra/aws/      Scripts de despliegue demo
tests/          Tests unitarios Python
```

## Flujo de datos

1. **Export** — Datos anonimizados en `data/raw/` (csv/parquet), período hasta 2025-12  
2. **Panel** — Agregación establecimiento × mes con targets 1m y 3m  
3. **Modelo** — XGBoost dual (horizontes `1m` / `3m`)  
4. **Ranking** — Lista maestra de establecimientos en riesgo para Preventores  
5. **App** — API + UI sobre ranking importado (`sql/app/`)

Split oficial: **train 2022–2023 · calibración 2024 · holdout 2025**.

Guía Python: [`python/README.md`](python/README.md)  
Datasets de entrega: [`docs/entrega-datos/REPORTE_DATASETS.md`](docs/entrega-datos/REPORTE_DATASETS.md)  
API / SPA: [`apps/api/README.md`](apps/api/README.md)

## Resultado vigente (holdout 2025)

| Métrica | 1m | 3m |
|---------|----|----|
| PR-AUC | 0,366 | 0,515 |
| Precision @ top-50 / mes | 76,4% | 93,5% |
| Precision @ top-225 / mes | 51,5% | 79,0% |
| Visitas reales @ mismo volumen | 10,3% | 17,8% |

## Secrets

No hay API keys en el repositorio. En local: `dotnet user-secrets` / variables de entorno. En AWS: `prevex.env` (`Gemini__ApiKey`, SMTP, JWT, connection string).
