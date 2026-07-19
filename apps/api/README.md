# API PFI Prevención

ASP.NET Core 10 · SQL Server local `PfiPrevencion`.

## Requisitos

- SQL Server en `localhost` con la base creada (`sql/app/`)
- Rankings importados (`scripts/import_ranking_to_app.py`)
- .NET SDK 10

## Arranque

```powershell
cd apps/api
dotnet run --urls http://localhost:5080
```

## Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/health` | No | Ping + conteo de snapshots |
| POST | `/api/auth/login` | No | `{ "email", "password" }` → JWT |
| GET | `/api/resumen?horizonte=1m\|3m` | Sí | KPIs del ranking vigente |
| GET | `/api/riesgo?horizonte=&banda=&sector=&q=&top=` | Sí | Lista de priorización |
| GET | `/api/establecimientos/{id}?horizonte=` | Sí | Ficha en ranking vigente |

## Usuario demo

- `admin@pfi.local` / `Admin123!`

## Connection string

```
Server=localhost;Database=PfiPrevencion;Trusted_Connection=True;TrustServerCertificate=True;Encrypt=True
```
