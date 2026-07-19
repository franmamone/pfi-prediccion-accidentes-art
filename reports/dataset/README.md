# Reportes del dataset y desempeño

Los gráficos se separan por propósito para no mezclar datos conocidos por el modelo con resultados fuera de muestra.

## `contexto_2022_2025/`

Describe el problema y la cartera completa:

- evolución de accidentes;
- formas, gravedad, edad y dotación;
- provincia de ocurrencia;
- divisiones CIIU Rev. 3;
- concentración por empleador;
- prevención y anomalías de carga.

El período llega hasta noviembre de 2025 para accidentes. Los gráficos indican que 2025 es parcial.

## `entrenamiento_2022_2023/`

Muestra exclusivamente las filas que ajustan los parámetros del modelo:

- targets de 1 y 3 meses;
- tasa positiva;
- dotación nominal positiva;
- prevención;
- tasas descriptivas por cápitas.

`entrenamiento_resumen.json` registra filas, establecimientos, meses y positivos.

## `desempeno_holdout_2025/`

Evalúa el modelo fuera de muestra:

- precisión mensual top-50 y top-225;
- cortes trimestrales top-150 y top-675 para 3m;
- precisión por historial, nómina, cápitas y actividad;
- distribución y calibración del score;
- comparación con historial, visitas registradas y azar.

Los gráficos de precisión usan únicamente 2025. El score se interpreta como prioridad, no como probabilidad calibrada.

## Advertencias de lectura

- Cantidad de accidentes no equivale a tasa de riesgo.
- `dotacion_establecimiento = 0` puede incluir fallas de cruce.
- La exportación vigente de prevención agrupa realizadas por fecha planificada.
- Enero de 2024 y enero de 2025 son cargas atípicas.

Regeneración:

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe scripts\run_dataset_reports.py
```
