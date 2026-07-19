# Web — Predictia

React + Vite + TypeScript. Tema claro/oscuro. Consume la API en `http://localhost:5080`.

## Arranque

Terminal 1 — API:

```powershell
cd apps/api
dotnet run --urls http://localhost:5080
```

Terminal 2 — Web:

```powershell
cd apps/web
npm install
npm run dev
```

Abrir `http://localhost:5173`  
Login: `admin@pfi.local` / `Admin123!`  
Prevencionista demo: `prevencionista@pfi.local` / `Prev123!`

El proxy de Vite reenvía `/api` → `localhost:5080`.

## Pantallas

- Login (ojito de contraseña + tema)
- Resumen (estados operativos exclusivos + cobertura top 50/225)
- Priorización (filtros, tooltips, acción **Programar visita**)
- Agenda (bandejas Programadas / Realizadas / Canceladas + cronología de auditoría)
- Auditoría (bitácora append-only del ciclo de visitas)
- Estadísticas (KPIs, cobertura/precisión históricas, SHAP agregado top 50/225, distribuciones del ranking vigente)
- Detalle (contexto operativo + factores SHAP individuales + programar visita)
- Exportaciones CSV
- Perfil (nombre y cambio de contraseña)

### Nota SHAP

Las contribuciones SHAP del detalle son aportes en la escala interna del modelo (margen).  
No se muestran como probabilidad, causalidad ni “porcentaje del puntaje”.  
En Estadísticas, el SHAP **agregado** promedia la matriz completa de la cohorte (top 50 / top 225), no los cinco factores truncados del detalle.

### Nota metodológica (Estadísticas)

- **Cobertura:** cohorte desde la activación del snapshot en la app (ventana 1m/3m operativa). El mes del ranking de datos no es el mes de cobertura.
- **Precisión observada:** solo con outcome `maduro` (fuente completa hasta el fin de la ventana). Pendientes se muestran como “—” / estado pendiente, nunca como 0%.
- Holdout de referencia y operación real se etiquetan por separado.

## Nota corporativa

Si `npm install` falla por certificado SSL, el proyecto incluye `.npmrc` con `strict-ssl=false` (solo local).
