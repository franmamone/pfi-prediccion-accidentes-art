# API + SPA — Prevex

ASP.NET Core 10 · SQL Server local `PfiPrevencion` · React (Vite) en el **mismo origen**.

Patrón igual al de `Testing`: un solo puerto. Las rutas `/api/*` las atiende .NET; el resto es la SPA.

## Requisitos

- SQL Server en `localhost` con la base creada (`sql/app/`)
- Rankings importados (`scripts/import_ranking_to_app.py`)
- .NET SDK 10
- Node.js (para el frontend en desarrollo / publish)

## Arranque desde Visual Studio

1. Abrí `PfiPrevencion.slnx` (o el `.csproj` de la API).
2. Marcá **PfiPrevencion.Api** como proyecto de inicio (ya viene como `DefaultStartup`).
3. Perfil de depuración: **http** (SpaProxy; el recomendado). No uses un perfil `https` local: el certificado de desarrollo suele fallar (`ERR_CERT_AUTHORITY_INVALID`) y VS abre `:7235`.
4. **F5** / **Ctrl+F5** inicia la API y, con el perfil `http`, SpaProxy levanta Vite (`npm run dev`).
5. El navegador abre `http://localhost:5011` → redirige al front en `:5173`.
6. **Shift+F5** (Detener depuración) corta la API; Vite suele cerrarse con ella.

Si al cerrar el navegador se corta la depuración: en VS → **Herramientas → Opciones → Proyectos y soluciones → Proyectos web** y desmarcá *“Detener el depurador al cerrar la ventana del explorador”* (o similar).

Requisito: Node.js en el PATH (para que SpaProxy pueda ejecutar `npm run dev`).

## Arranque unificado por CLI (recomendado también)

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
Login: usuarios reales (invitar desde Usuarios). Demo cercanía CABA: `prev.palermo@pfi.local` … `prev.caballito@pfi.local` / `Prev123!`

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
| GET | `/api/resumen` | Sí | KPIs del ranking trimestral vigente |
| GET | `/api/riesgo?banda=&sector=&q=&top=` | Sí | Lista de priorización (horizonte trimestral) |
| GET | `/api/establecimientos/{id}` | Sí | Ficha en el ranking trimestral vigente |

## Connection string

```
Server=localhost;Database=PfiPrevencion;Trusted_Connection=True;TrustServerCertificate=True;Encrypt=True
```

## Secrets y config (local + AWS)

Ningún secret en Git. Placeholders en `appsettings.json`; valores reales por **User Secrets** (dev) o **variables de entorno** (AWS).

### Local (User Secrets)

Desde `apps/api`:

```powershell
dotnet user-secrets init
dotnet user-secrets set "Smtp:Host" "smtp.gmail.com"
dotnet user-secrets set "Smtp:Port" "587"
dotnet user-secrets set "Smtp:User" "tu@gmail.com"
dotnet user-secrets set "Smtp:Password" "<app-password-de-gmail>"
dotnet user-secrets set "Smtp:From" "Prevex <tu@gmail.com>"
dotnet user-secrets set "App:PublicBaseUrl" "http://localhost:5173"
dotnet user-secrets set "Jwt:Key" "<clave-larga-min-32-chars>"
```

Sin SMTP configurado, el alta de usuarios falla con error explícito (no se silencia).

### AWS (cuando desplieguen)

| Clave env | Uso |
|-----------|-----|
| `Smtp__Host` / `Smtp__Port` / `Smtp__User` / `Smtp__Password` / `Smtp__From` | MailKit (Gmail o Amazon SES) |
| `App__PublicBaseUrl` | URL HTTPS del front (links de invite/reset) |
| `Jwt__Key` | Firma JWT (rotar; ≥32 chars) |
| `ConnectionStrings__PfiPrevencion` | RDS SQL Server |

MFA TOTP no depende de AWS (secreto en SQL). Lo exige un Admin al crear/editar usuario; el QR se completa en el primer login. Al programar/reprogramar una visita a un Preventor se envía mail con link a `/agenda?visita={id}` (requiere SMTP + `App:PublicBaseUrl`). Leaflet/OSM no necesita API key.
