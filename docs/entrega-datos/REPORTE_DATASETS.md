# Reporte de datasets regenerados (Prevex / PFI)

**Fecha:** 2026-11-18  
**Alcance:** regeneración offline de CSV/parquet/panel + export del ranking ya vigente en la app.  
**Importante:** este trabajo **no modifica** la app local ni la demo AWS (no hay reimport ni redeploy).

Inventario máquina-legible: `docs/entrega-datos/inventario_datasets.json`

---

## 1. Mapa de carpetas

```
data/
  raw/                         # Fuentes exportadas (anonimizadas): csv + parquet
    accidentes_ml.csv|.parquet
    establecimientos_universo.csv|.parquet   # activas: FechaBaja IS NULL
    prevencion_establecimiento_mes.csv|.parquet
    nomina_establecimiento_mes.csv|.parquet
    encuesta/                  # respuestas de encuesta (csv/xlsx)
  processed/
    panel_establecimiento_mes.parquet        # panel ML establecimiento × mes
  normativa/
    chunks.jsonl                             # corpus RGRL (ya existía)

reports/
  ranking/                     # Copia del ranking vigente de la app (sin reentrenar)
    ranking_maestro_{1m|3m}_2025-11.json|.csv
    shap_contribuciones_{1m|3m}_2025-11.json
  dataset/
    data_quality_audit.json

docs/entrega-datos/
  REPORTE_DATASETS.md          # este archivo
  inventario_datasets.json
```

---

## 2. Volúmenes

| Artefacto | Filas | Columnas | Peso aprox. |
|-----------|------:|---------:|------------:|
| `accidentes_ml` | 25.897 | 66 | CSV 19,5 MB / parquet 4,3 MB |
| `establecimientos_universo` | **35.869** | 22 | CSV 14,2 MB / parquet 4,4 MB |
| `prevencion_establecimiento_mes` | 30.780 | 6 | CSV 2,5 MB / parquet 0,7 MB |
| `nomina_establecimiento_mes` | 510.281 | 12 | CSV 56,9 MB / parquet 5,5 MB |
| `panel_establecimiento_mes` | **1.685.843** | 67 | parquet 11,1 MB |

**Panel (resumen):**

- Establecimientos: **35.869**
- Período features: **2022-01 … 2025-11**
- Target 1m evaluable: 1.649.974 filas; tasa positiva ≈ **0,97 %**
- Target 3m evaluable: 1.578.236 filas; tasa positiva ≈ **2,15 %**

**Universo vs histórico:** el ranking/app usó **35.505** (jul-2026). Con el criterio documentado (`FechaBaja IS NULL`), el export vigente tiene **35.869** (cartera creció ~364).

---

## 3. Columnas por dataset

### 3.1 Accidentes (`accidentes_ml`)

IDs anonimizados (hash), calendario del siniestro, perfil del trabajador, empleador/establecimiento (CIIU, cápitas, geo), tipificación del accidente, historial de visitas/siniestros previos y flag PESE.

Ver lista completa en `inventario_datasets.json` → `accidentes.columnas`.

### 3.2 Universo (`establecimientos_universo`)

`id_establecimiento`, `id_empleador`, cápitas, CIIU (empleador/establecimiento/rev4), grupo, frecuencia visita CIIU, tipo, flags, antigüedad, provincia/CP, coordenadas, riesgo higiénico.

Filtro SQL: **`FechaBaja IS NULL`**.

### 3.3 Prevención (`prevencion_establecimiento_mes`)

Establecimiento × mes con visitas planificadas/realizadas (y columnas asociadas del export).

### 3.4 Nómina (`nomina_establecimiento_mes`)

`id_establecimiento`, `periodo`, `anio`, `mes`, `dotacion_nomina_mes`, `edad_promedio`, `pct_mayores_50`, `pct_mujeres`, `antiguedad_promedio_meses`, `pct_antiguedad_menor_6m`, `tareas_distintas`, `pct_en_tarea_principal`.

### 3.5 Panel ML (`panel_establecimiento_mes`)

Une universo + historial de accidentes + prevención + nómina + features derivadas (`tendencia_accidentes_3m`, ratios de visitas, tasas, estacionalidad `mes_sin`/`mes_cos`, targets `target_accidente_mes_siguiente` y `target_accidente_3m`, etc.).

Lista completa: `inventario_datasets.json` → `panel.columnas` (67 campos).

---

## 4. Resultado del modelo (el de la app, sin reentrenar)

Se exportó el **ranking ya vigente** en SQL local `PfiPrevencion` (el mismo que alimentó la demo), período **2025-11**, top **1000**.

| Horizonte | Archivo | Ítems |
|-----------|---------|------:|
| 1m | `reports/ranking/ranking_maestro_1m_2025-11.json` | 1.000 |
| 3m | `reports/ranking/ranking_maestro_3m_2025-11.json` | 1.000 |

SHAP por ítem: `shap_contribuciones_{1m|3m}_2025-11.json` (5.000 contribuciones c/u).

**Acierto histórico holdout 2025 (trimestral, hardcode operativo de la app):**

| Top-K | Precisión |
|------:|----------:|
| 50 | 93,5 % |
| 100 | 88,1 % |
| 200 | 80,7 % |
| 225 | 79,0 % |
| 500 | 63,7 % |
| 1000 | 49,5 % |

Interpretación: efectividad histórica del tramo en 2025 (precision@K), **no** probabilidad futura calibrada por establecimiento.

Snapshot app: `UniversoFilas = 35.505` (referencia del entrenamiento/export original).

---

## 5. Origen de los datasets

Los CSV/parquet de `data/raw/` se generaron offline desde vistas de extracción sobre el core de la ART (IDs hasheados, sin PII).  
Los scripts SQL de esas vistas **no forman parte del repositorio de entrega** (resguardo fuera de Git).

Pipeline local a partir de los archivos ya exportados: parquet → `scripts/build_panel.py` → `scripts/audit_data_quality.py`.

---

## 6. Qué no se hizo (a propósito)

- No se reentrenó XGBoost en este paso.
- No se reimportó ranking a la app.
- No se sincronizó ni redeployó AWS.
- No se actualizó la bitácora (pedido explícito).
