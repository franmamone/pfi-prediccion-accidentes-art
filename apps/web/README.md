# Web — PFI Prevención

React + Vite + TypeScript. Tema azul/negro. Consume la API en `http://localhost:5080`.

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

El proxy de Vite reenvía `/api` → `localhost:5080`.

## Pantallas MVP

- Login
- Resumen (1m / 3m)
- Priorización + filtros
- Por actividad
- Detalle establecimiento
- Export CSV

## Nota corporativa

Si `npm install` falla por certificado SSL, el proyecto incluye `.npmrc` con `strict-ssl=false` (solo local).
