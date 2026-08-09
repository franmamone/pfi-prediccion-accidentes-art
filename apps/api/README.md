# API + SPA — Prevex

ASP.NET Core 10 · SQL Server local `PfiPrevencion` · React (Vite) en el **mismo origen**.

Patrón igual al de `Testing`: un solo puerto. Las rutas `/api/*` las atiende .NET; el resto es la SPA.

## Requisitos

- SQL Server en `localhost` con la base creada (`sql/app/`)
- Rankings importados (`scripts/import_ranking_to_app.py`)
- .NET SDK 10
- Node.js (para el frontend en desarrollo / publish)

## Arranque unificado (recomendado)

Desde la raíz del repo o desde `apps/api`:

```powershell
cd apps/api
dotnet run --launch-profile http
```

Eso:

1. Levanta la API en `http://localhost:5011`
2. Arranca Vite (`npm run dev`) vía **SpaProxy** en `http://localhost:5173`
3. Al abrir `http://localhost:5011`, SpaProxy **redirige** al front en `:5173` (igual que en Testing). Vite proxifica `/api` → `:5011`, así que el navegador habla con un solo origen de UI y las llamadas van a `/api/...` sin CORS.

Abrí **`http://localhost:5011`** (te lleva al front).  
Login: `admin@pfi.local` / `Admin123!` · Preventor: `prevencionista@pfi.local` / `Prev123!`

En **producción** (`dotnet publish`) no hay redirect: UI y `/api` viven en el mismo host/puerto (`wwwroot` + Kestrel).

### Solo API (sin SpaProxy)

```powershell
dotnet run --launch-profile api-only
```

Útil si ya tenés Vite corriendo aparte (`cd apps/web; npm run dev`).

## Publish (producción / AWS)

```powershell
cd apps/web
npm install
npm run build   # opcional: el publish lo corre si falta dist
cd ..\api
dotnet publish -c Release -o ..\..\publish\api
```

El target `IncludeSpaInPublish` copia `apps/web/dist/**` a `wwwroot/` del publish.  
En el servidor: `dotnet PfiPrevencion.Api.dll` sirve **UI + API** en el mismo proceso/puerto.

## Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/health` | No | Ping + conteo de snapshots |
| POST | `/api/auth/login` | No | `{ "email", "password" }` → JWT |
| GET | `/api/resumen?horizonte=1m\|3m` | Sí | KPIs del ranking vigente |
| GET | `/api/riesgo?horizonte=&banda=&sector=&q=&top=` | Sí | Lista de priorización |
| GET | `/api/establecimientos/{id}?horizonte=` | Sí | Ficha en ranking vigente |

## Connection string

```
Server=localhost;Database=PfiPrevencion;Trusted_Connection=True;TrustServerCertificate=True;Encrypt=True
```
