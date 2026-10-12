# Web — Prevex

React + Vite + TypeScript. Tema claro/oscuro.

Consume la API por rutas relativas **`/api/...`** (mismo origen). No hardcodea host ni puerto.

## Arranque unificado (recomendado)

Ver [`../api/README.md`](../api/README.md): un solo `dotnet run` levanta API + Vite vía SpaProxy.

Abrí `http://localhost:5011`.

## Arranque solo frontend

Si la API ya corre en `5011`:

```powershell
cd apps/web
npm install
npm run dev
```

Vite en `http://localhost:5173` proxifica `/api` → `http://localhost:5011`.

Login: usuarios reales (invitar desde Usuarios).  
Demo cercanía CABA: `prev.palermo@pfi.local` … `prev.caballito@pfi.local` / `Prev123!`

## Build

```powershell
npm run build
```

Salida en `dist/`. En publish, la API la incluye en `wwwroot`.

## Pantallas

- Login · Priorización · Agenda (calendario) · Estadísticas · Detalle · Perfil
- Responsive: drawer móvil para preventor/admin desde el celular

## Nota corporativa

Si `npm install` falla por certificado SSL, el proyecto incluye `.npmrc` con `strict-ssl=false` (solo local).
