using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using PfiPrevencion.Api.Data;
using PfiPrevencion.Api.Services;

namespace PfiPrevencion.Api;

public static class AuthUsersEndpoints
{
    public static void MapAuthUsersAndGeo(this WebApplication app, string jwtKey, string jwtIssuer)
    {
        app.MapPost("/api/auth/forgot-password", async (
            ForgotPasswordRequest req, AppDbContext db, AuthTokenService tokens, IEmailSender email) =>
        {
            var mail = (req.Email ?? "").Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(mail)) return Results.Ok(new { ok = true });
            var user = await db.Usuarios.FirstOrDefaultAsync(u => u.Email == mail && u.Activo);
            if (user is not null && email.IsConfigured)
            {
                try { await tokens.SendResetAsync(user); }
                catch { /* no filtrar existencia */ }
            }
            return Results.Ok(new { ok = true });
        });

        app.MapPost("/api/auth/reset-password", async (
            ResetPasswordRequest req, AppDbContext db, AuthTokenService tokens) =>
        {
            if (string.IsNullOrWhiteSpace(req.Token) || string.IsNullOrWhiteSpace(req.Nueva) || req.Nueva.Length < 8)
                return Results.BadRequest(new { error = "Token y contraseña (mín. 8) son obligatorios." });
            var row = await tokens.FindValidAsync(req.Token, "reset");
            if (row?.Usuario is null)
                return Results.BadRequest(new { error = "El enlace no es válido o expiró." });
            row.Usuario.PasswordHash = BCrypt.Net.BCrypt.HashPassword(req.Nueva);
            row.Usuario.DebeCambiarPassword = false;
            row.UsadoEn = DateTime.UtcNow;
            await db.SaveChangesAsync();
            return Results.Ok(new { ok = true });
        });

        app.MapPost("/api/auth/aceptar-invitacion", async (
            AcceptInviteRequest req, AppDbContext db, AuthTokenService tokens) =>
        {
            if (string.IsNullOrWhiteSpace(req.Token) || string.IsNullOrWhiteSpace(req.Nueva) || req.Nueva.Length < 8)
                return Results.BadRequest(new { error = "Token y contraseña (mín. 8) son obligatorios." });
            var row = await tokens.FindValidAsync(req.Token, "invite");
            if (row?.Usuario is null)
                return Results.BadRequest(new { error = "El enlace no es válido o expiró." });
            row.Usuario.PasswordHash = BCrypt.Net.BCrypt.HashPassword(req.Nueva);
            row.Usuario.DebeCambiarPassword = false;
            row.Usuario.Activo = true;
            row.UsadoEn = DateTime.UtcNow;
            await db.SaveChangesAsync();
            return Results.Ok(new { ok = true, email = row.Usuario.Email });
        });

        app.MapPost("/api/auth/mfa", async (MfaLoginRequest req, AppDbContext db) =>
        {
            if (string.IsNullOrWhiteSpace(req.MfaToken) || string.IsNullOrWhiteSpace(req.Code))
                return Results.BadRequest(new { error = "Falta el código MFA." });
            var principal = ValidateMfaPendingToken(req.MfaToken, jwtKey, jwtIssuer);
            if (principal is null)
                return Results.Json(new { error = "El paso MFA expiró. Volvé a iniciar sesión." }, statusCode: StatusCodes.Status401Unauthorized);
            var sub = principal.FindFirstValue(JwtRegisteredClaimNames.Sub)
                ?? principal.FindFirstValue(ClaimTypes.NameIdentifier);
            if (!int.TryParse(sub, out var userId))
                return Results.Json(new { error = "El paso MFA expiró. Volvé a iniciar sesión." }, statusCode: StatusCodes.Status401Unauthorized);
            var user = await db.Usuarios.FirstOrDefaultAsync(u => u.Id == userId && u.Activo);
            if (user is null || !user.MfaEnabled || string.IsNullOrWhiteSpace(user.MfaSecret))
                return Results.Json(new { error = "No se pudo verificar MFA para este usuario." }, statusCode: StatusCodes.Status401Unauthorized);

            var ok = MfaService.VerifyCode(user.MfaSecret, req.Code);
            if (!ok && MfaService.TryConsumeRecovery(user.MfaRecoveryHashes, req.Code, out var updated))
            {
                user.MfaRecoveryHashes = updated;
                ok = true;
                await db.SaveChangesAsync();
            }
            if (!ok)
                return Results.Json(new { error = "Código MFA incorrecto." }, statusCode: StatusCodes.Status401Unauthorized);

            var token = CreateSessionToken(user, jwtKey, jwtIssuer);
            return Results.Ok(new { access_token = token, token_type = "Bearer", user = ToUserDtoExt(user) });
        });

        app.MapPost("/api/me/mfa/setup", async (ClaimsPrincipal principal, AppDbContext db) =>
        {
            var user = await GetUser(principal, db);
            if (user is null) return Results.Unauthorized();
            if (!user.MfaRequired)
                return Results.BadRequest(new { error = "MFA no fue habilitado por un administrador." });
            if (user.MfaEnabled)
                return Results.BadRequest(new { error = "MFA ya está activo." });
            var secret = MfaService.GenerateSecret();
            user.MfaSecret = secret;
            await db.SaveChangesAsync();
            return Results.Ok(new
            {
                secret,
                otpauthUrl = MfaService.BuildOtpAuthUrl(user.Email, secret),
            });
        }).RequireAuthorization();

        app.MapPost("/api/me/mfa/confirm", async (
            MfaConfirmRequest req, ClaimsPrincipal principal, AppDbContext db) =>
        {
            var user = await GetUser(principal, db);
            if (user is null) return Results.Unauthorized();
            if (!user.MfaRequired)
                return Results.BadRequest(new { error = "MFA no fue habilitado por un administrador." });
            if (string.IsNullOrWhiteSpace(user.MfaSecret))
                return Results.BadRequest(new { error = "Primero iniciá el setup MFA." });
            if (!MfaService.VerifyCode(user.MfaSecret, req.Code ?? ""))
                return Results.BadRequest(new { error = "Código inválido." });
            user.MfaEnabled = true;
            user.MfaConfirmedEn = DateTime.UtcNow;
            user.MfaRecoveryHashes = null;
            await db.SaveChangesAsync();
            return Results.Ok(new { ok = true });
        }).RequireAuthorization();

        app.MapGet("/api/usuarios", async (
            ClaimsPrincipal principal, AppDbContext db, string? rol, bool? activo) =>
        {
            var me = await GetUser(principal, db);
            if (me is null) return Results.Unauthorized();
            if (!CanAdmin(me)) return Results.Json(new { error = "Sin permiso." }, statusCode: 403);

            var q = db.Usuarios.AsNoTracking()
                .Include(u => u.Disponibilidades)
                .AsQueryable();
            if (!string.IsNullOrWhiteSpace(rol))
                q = q.Where(u => u.Rol == rol.Trim());
            if (activo is not null)
                q = q.Where(u => u.Activo == activo);

            var rows = await q.OrderBy(u => u.Nombre).Take(500).ToListAsync();
            return Results.Ok(new { total = rows.Count, items = rows.Select(ToUsuarioAdminDto) });
        }).RequireAuthorization();

        app.MapPost("/api/usuarios", async (
            CreateUsuarioRequest req,
            ClaimsPrincipal principal,
            AppDbContext db,
            AuthTokenService tokens,
            IEmailSender email) =>
        {
            var me = await GetUser(principal, db);
            if (me is null) return Results.Unauthorized();
            if (!CanAdmin(me)) return Results.Json(new { error = "Sin permiso." }, statusCode: 403);
            if (!email.IsConfigured)
                return Results.BadRequest(new { error = "SMTP no configurado. No se puede enviar la invitación." });

            var mailAddr = (req.Email ?? "").Trim().ToLowerInvariant();
            var nombre = (req.Nombre ?? "").Trim();
            var rol = (req.Rol ?? "").Trim();
            if (mailAddr.Length < 5 || nombre.Length < 2)
                return Results.BadRequest(new { error = "Email y nombre son obligatorios." });
            if (rol is not ("Admin" or "Coordinador" or "Preventor"))
                return Results.BadRequest(new { error = "Rol inválido." });
            if (await db.Usuarios.AnyAsync(u => u.Email == mailAddr))
                return Results.Conflict(new { error = "Ya existe un usuario con ese email." });

            if (rol == "Preventor")
            {
                if (req.Latitud is null || req.Longitud is null)
                    return Results.BadRequest(new { error = "El preventor necesita latitud/longitud (CABA)." });
                if (req.Disponibilidad is null || req.Disponibilidad.Count == 0)
                    return Results.BadRequest(new { error = "Configurá al menos un día de disponibilidad." });
            }

            var (lat, lon) = (req.Latitud, req.Longitud);
            if (rol == "Preventor" && (lat is null || lon is null))
            {
                var r = GeoHelper.RandomCaba(Random.Shared);
                lat = r.Lat; lon = r.Lon;
            }

            var user = new Usuario
            {
                Email = mailAddr,
                Nombre = nombre,
                PasswordHash = BCrypt.Net.BCrypt.HashPassword(Guid.NewGuid().ToString("N")),
                Rol = rol,
                ZonaId = req.ZonaId,
                Activo = true,
                DebeCambiarPassword = true,
                MfaRequired = req.MfaRequired == true,
                Latitud = lat,
                Longitud = lon,
                CreadoEn = DateTime.UtcNow,
            };
            db.Usuarios.Add(user);
            await db.SaveChangesAsync();

            if (rol == "Preventor" && req.Disponibilidad is { Count: > 0 })
            {
                foreach (var d in req.Disponibilidad)
                {
                    if (d.DiaSemana is < 1 or > 7) continue;
                    if (!TimeOnly.TryParse(d.HoraDesde, out var desde) || !TimeOnly.TryParse(d.HoraHasta, out var hasta))
                        continue;
                    if (hasta <= desde) continue;
                    db.UsuarioDisponibilidades.Add(new UsuarioDisponibilidad
                    {
                        UsuarioId = user.Id,
                        DiaSemana = (byte)d.DiaSemana,
                        HoraDesde = desde,
                        HoraHasta = hasta,
                    });
                }
                await db.SaveChangesAsync();
            }

            await tokens.SendInviteAsync(user);
            await db.Entry(user).Collection(u => u.Disponibilidades).LoadAsync();
            return Results.Ok(ToUsuarioAdminDto(user));
        }).RequireAuthorization();

        app.MapPut("/api/usuarios/{id:int}", async (
            int id, UpdateUsuarioRequest req, ClaimsPrincipal principal, AppDbContext db) =>
        {
            var me = await GetUser(principal, db);
            if (me is null) return Results.Unauthorized();
            if (!CanAdmin(me)) return Results.Json(new { error = "Sin permiso." }, statusCode: 403);

            var user = await db.Usuarios.Include(u => u.Disponibilidades).FirstOrDefaultAsync(u => u.Id == id);
            if (user is null) return Results.NotFound();

            if (!string.IsNullOrWhiteSpace(req.Nombre))
                user.Nombre = req.Nombre.Trim();
            if (!string.IsNullOrWhiteSpace(req.Rol) && req.Rol is "Admin" or "Coordinador" or "Preventor")
                user.Rol = req.Rol;
            // Baja lógica: Activo=false (no se borra la fila ni el historial de agenda/auditoría).
            if (req.Activo is not null) user.Activo = req.Activo.Value;
            if (req.ZonaId is not null) user.ZonaId = req.ZonaId;
            if (req.Latitud is not null) user.Latitud = req.Latitud;
            if (req.Longitud is not null) user.Longitud = req.Longitud;

            if (req.MfaRequired is not null)
            {
                user.MfaRequired = req.MfaRequired.Value;
                if (!user.MfaRequired)
                {
                    user.MfaEnabled = false;
                    user.MfaSecret = null;
                    user.MfaConfirmedEn = null;
                    user.MfaRecoveryHashes = null;
                }
                else if (req.ResetMfa == true)
                {
                    user.MfaEnabled = false;
                    user.MfaSecret = null;
                    user.MfaConfirmedEn = null;
                    user.MfaRecoveryHashes = null;
                }
            }
            else if (req.ResetMfa == true && user.MfaRequired)
            {
                user.MfaEnabled = false;
                user.MfaSecret = null;
                user.MfaConfirmedEn = null;
                user.MfaRecoveryHashes = null;
            }

            if (req.Disponibilidad is not null)
            {
                db.UsuarioDisponibilidades.RemoveRange(user.Disponibilidades);
                foreach (var d in req.Disponibilidad)
                {
                    if (d.DiaSemana is < 1 or > 7) continue;
                    if (!TimeOnly.TryParse(d.HoraDesde, out var desde) || !TimeOnly.TryParse(d.HoraHasta, out var hasta))
                        continue;
                    if (hasta <= desde) continue;
                    db.UsuarioDisponibilidades.Add(new UsuarioDisponibilidad
                    {
                        UsuarioId = user.Id,
                        DiaSemana = (byte)d.DiaSemana,
                        HoraDesde = desde,
                        HoraHasta = hasta,
                    });
                }
            }

            await db.SaveChangesAsync();
            await db.Entry(user).Collection(u => u.Disponibilidades).LoadAsync();
            return Results.Ok(ToUsuarioAdminDto(user));
        }).RequireAuthorization();

        app.MapPost("/api/usuarios/{id:int}/reenviar-invitacion", async (
            int id, ClaimsPrincipal principal, AppDbContext db, AuthTokenService tokens, IEmailSender email) =>
        {
            var me = await GetUser(principal, db);
            if (me is null) return Results.Unauthorized();
            if (!CanAdmin(me)) return Results.Json(new { error = "Sin permiso." }, statusCode: 403);
            if (!email.IsConfigured)
                return Results.BadRequest(new { error = "SMTP no configurado." });
            var user = await db.Usuarios.FirstOrDefaultAsync(u => u.Id == id);
            if (user is null) return Results.NotFound();
            user.DebeCambiarPassword = true;
            await db.SaveChangesAsync();
            await tokens.SendInviteAsync(user);
            return Results.Ok(new { ok = true });
        }).RequireAuthorization();

        app.MapGet("/api/agenda/candidatos", async (
            ClaimsPrincipal principal,
            AppDbContext db,
            DateOnly fecha,
            string hora,
            string idEstablecimiento) =>
        {
            var me = await GetUser(principal, db);
            if (me is null) return Results.Unauthorized();
            if (!CanManage(me)) return Results.Json(new { error = "Sin permiso." }, statusCode: 403);
            if (!TimeOnly.TryParse(hora, out var horaT))
                return Results.BadRequest(new { error = "Hora inválida." });

            var estId = idEstablecimiento.Trim();
            var ubic = await db.EstablecimientoUbicaciones.AsNoTracking()
                .FirstOrDefaultAsync(e => e.IdEstablecimiento == estId);
            if (ubic is null)
            {
                ubic = await EnsureEstablecimientoUbicacionAsync(db, estId);
            }

            var dia = GeoHelper.ToIsoDiaSemana(fecha);
            var preventores = await db.Usuarios.AsNoTracking()
                .Include(u => u.Disponibilidades)
                .Where(u => u.Activo && u.Rol == "Preventor"
                    && u.Latitud != null && u.Longitud != null)
                .ToListAsync();

            var agendaDia = await db.AgendaItems.AsNoTracking()
                .Where(a => a.FechaPlanificada == fecha
                    && (a.Estado == "programada" || a.Estado == "realizada"))
                .Select(a => new { a.UsuarioId, a.HoraPlanificada, a.IdEstablecimiento })
                .ToListAsync();

            var estIdsAgenda = agendaDia.Select(a => a.IdEstablecimiento).Distinct().ToList();
            Dictionary<string, (double Lat, double Lon)> ubicAgenda;
            if (estIdsAgenda.Count == 0)
            {
                ubicAgenda = new Dictionary<string, (double Lat, double Lon)>(StringComparer.OrdinalIgnoreCase);
            }
            else
            {
                var ubicRows = await db.EstablecimientoUbicaciones.AsNoTracking()
                    .Where(e => estIdsAgenda.Contains(e.IdEstablecimiento))
                    .Select(e => new { e.IdEstablecimiento, e.Latitud, e.Longitud })
                    .ToListAsync();
                ubicAgenda = ubicRows.ToDictionary(
                    e => e.IdEstablecimiento,
                    e => (e.Latitud, e.Longitud),
                    StringComparer.OrdinalIgnoreCase);
            }

            var capitasByEst = await LoadCapitasByEstAsync(db, estIdsAgenda.Append(estId).Distinct().ToList());
            var duracionCandidata = GeoHelper.DuracionEstimadaHoras(
                capitasByEst.GetValueOrDefault(estId));
            var tamanoCandidata = GeoHelper.TamanoEtiqueta(capitasByEst.GetValueOrDefault(estId));

            var list = new List<CandidatoDto>();
            foreach (var p in preventores)
            {
                var franjas = p.Disponibilidades
                    .Where(d => d.DiaSemana == dia)
                    .Select(d => (d.HoraDesde, d.HoraHasta))
                    .ToList();
                if (franjas.Count == 0) continue;

                var delPreventor = agendaDia.Where(a => a.UsuarioId == p.Id).ToList();
                var slots = delPreventor
                    .Select(a => new GeoHelper.SlotOcupado(
                        a.HoraPlanificada,
                        GeoHelper.DuracionEstimadaHoras(capitasByEst.GetValueOrDefault(a.IdEstablecimiento))))
                    .OrderBy(s => s.Hora)
                    .ToList();

                var huecos = GeoHelper.CalcularHuecos(franjas, slots, duracionCandidata);
                if (huecos.Count == 0) continue;

                var enFranja = GeoHelper.HoraEnFranjas(horaT, franjas);
                var libreGap = GeoHelper.RespetaGap(horaT, duracionCandidata, slots);
                var disponibleEnHora = enFranja && libreGap && slots.All(s => s.Hora != horaT);

                var visitasDia = delPreventor
                    .Where(a => ubicAgenda.ContainsKey(a.IdEstablecimiento))
                    .Select(a =>
                    {
                        var u = ubicAgenda[a.IdEstablecimiento];
                        return new GeoHelper.VisitaDia(a.HoraPlanificada, u.Lat, u.Lon);
                    })
                    .ToList();

                var (anclaLat, anclaLon, anclaOrigen) = GeoHelper.ResolverAncla(
                    p.Latitud!.Value, p.Longitud!.Value, horaT, visitasDia);
                var dist = GeoHelper.HaversineKm(anclaLat, anclaLon, ubic.Latitud, ubic.Longitud);
                var horasCarga = Math.Round(slots.Sum(s => s.DuracionHoras), 1);
                var score = GeoHelper.Score(dist, horasCarga);

                list.Add(new CandidatoDto(
                    p.Id, p.Email, p.Nombre, p.Latitud.Value, p.Longitud.Value,
                    slots.Count, horasCarga, Math.Round(dist, 2), Math.Round(score, 2),
                    anclaOrigen, disponibleEnHora,
                    slots.Select(s => s.Hora.ToString("HH\\:mm")).ToList(),
                    huecos.Select(t => t.ToString("HH\\:mm")).ToList()));
            }

            var ordenados = list
                .OrderByDescending(x => x.DisponibleEnHora)
                .ThenBy(x => x.Score)
                .ThenBy(x => x.HorasCargaDia)
                .ThenBy(x => x.DistanciaKm)
                .ToList();

            var recomendado = ordenados.FirstOrDefault(c => c.DisponibleEnHora) ?? ordenados.FirstOrDefault();

            return Results.Ok(new
            {
                establecimiento = new
                {
                    idEstablecimiento = estId,
                    latitud = ubic.Latitud,
                    longitud = ubic.Longitud,
                    duracionEstimadaHoras = duracionCandidata,
                    tamano = tamanoCandidata,
                    cantidadCapitas = capitasByEst.GetValueOrDefault(estId),
                },
                gapHoras = duracionCandidata,
                duracionDefaultHoras = GeoHelper.DuracionDefaultHoras,
                pasoMinutos = (int)GeoHelper.PasoHueco.TotalMinutes,
                recomendadoId = recomendado?.Id,
                candidatos = ordenados.Select(c => new
                {
                    id = c.Id,
                    email = c.Email,
                    nombre = c.Nombre,
                    latitud = c.Latitud,
                    longitud = c.Longitud,
                    visitasDelDia = c.VisitasDelDia,
                    horasCargaDia = c.HorasCargaDia,
                    distanciaKm = c.DistanciaKm,
                    anclaOrigen = c.AnclaOrigen,
                    disponibleEnHora = c.DisponibleEnHora,
                    horasOcupadas = c.HorasOcupadas,
                    huecosDisponibles = c.HuecosDisponibles,
                }),
            });
        }).RequireAuthorization();

        app.MapGet("/api/agenda/capacidad", async (ClaimsPrincipal principal, AppDbContext db) =>
        {
            var me = await GetUser(principal, db);
            if (me is null) return Results.Unauthorized();
            if (!CanManage(me)) return Results.Json(new { error = "Sin permiso." }, statusCode: 403);

            var nPrev = await db.Usuarios.CountAsync(u => u.Activo && u.Rol == "Preventor");
            var hoy = DateOnly.FromDateTime(DateTime.Today);
            var hasta = hoy.AddDays(6);
            var porDia = await db.AgendaItems.AsNoTracking()
                .Where(a => a.FechaPlanificada >= hoy && a.FechaPlanificada <= hasta
                    && (a.Estado == "programada" || a.Estado == "realizada"))
                .GroupBy(a => a.FechaPlanificada)
                .Select(g => new { fecha = g.Key, visitas = g.Count() })
                .ToListAsync();

            return Results.Ok(new
            {
                preventoresActivos = nPrev,
                nota = "Asignación: distancia al ancla del día (visita anterior si hay; si no, base) + horas estimadas por cápitas (1/2/3 h). Sin tope duro de visitas.",
                semana = porDia.OrderBy(x => x.fecha),
            });
        }).RequireAuthorization();
    }

    public static object? TryLoginWithMfa(
        Usuario user, string jwtKey, string jwtIssuer, out bool mfaRequired, out string? mfaToken, out string? accessToken)
    {
        mfaRequired = false;
        mfaToken = null;
        accessToken = null;
        if (user.DebeCambiarPassword && (user.PasswordHash.Length < 10 || user.PasswordHash.StartsWith("INVITE", StringComparison.Ordinal)))
        {
            return Results.BadRequest(new { error = "Debés aceptar la invitación y crear tu contraseña antes de ingresar." });
        }
        if (user.MfaEnabled && !string.IsNullOrWhiteSpace(user.MfaSecret))
        {
            mfaRequired = true;
            mfaToken = CreateMfaPendingToken(user, jwtKey, jwtIssuer);
            return null;
        }
        accessToken = CreateSessionToken(user, jwtKey, jwtIssuer);
        return null;
    }

    public static async Task EnsureAuthGeoTablesAsync(AppDbContext db)
    {
        await db.Database.ExecuteSqlRawAsync("""
            IF COL_LENGTH(N'app.Usuarios', N'Latitud') IS NULL ALTER TABLE app.Usuarios ADD Latitud FLOAT NULL;
            IF COL_LENGTH(N'app.Usuarios', N'Longitud') IS NULL ALTER TABLE app.Usuarios ADD Longitud FLOAT NULL;
            IF COL_LENGTH(N'app.Usuarios', N'MfaRequired') IS NULL
                ALTER TABLE app.Usuarios ADD MfaRequired BIT NOT NULL CONSTRAINT DF_Usuarios_MfaRequired DEFAULT (0);
            IF COL_LENGTH(N'app.Usuarios', N'MfaEnabled') IS NULL
                ALTER TABLE app.Usuarios ADD MfaEnabled BIT NOT NULL CONSTRAINT DF_Usuarios_MfaEnabled DEFAULT (0);
            IF COL_LENGTH(N'app.Usuarios', N'MfaSecret') IS NULL ALTER TABLE app.Usuarios ADD MfaSecret NVARCHAR(200) NULL;
            IF COL_LENGTH(N'app.Usuarios', N'MfaConfirmedEn') IS NULL ALTER TABLE app.Usuarios ADD MfaConfirmedEn DATETIME2(0) NULL;
            IF COL_LENGTH(N'app.Usuarios', N'DebeCambiarPassword') IS NULL
                ALTER TABLE app.Usuarios ADD DebeCambiarPassword BIT NOT NULL CONSTRAINT DF_Usuarios_DebeCambiarPassword DEFAULT (0);
            IF COL_LENGTH(N'app.Usuarios', N'MfaRecoveryHashes') IS NULL ALTER TABLE app.Usuarios ADD MfaRecoveryHashes NVARCHAR(MAX) NULL;
            """);

        // Separado del ALTER para que SQL Server vea la columna nueva.
        await db.Database.ExecuteSqlRawAsync("""
            IF COL_LENGTH(N'app.Usuarios', N'MfaRequired') IS NOT NULL
                UPDATE app.Usuarios SET MfaRequired = 1 WHERE MfaEnabled = 1 AND MfaRequired = 0;
            """);

        await db.Database.ExecuteSqlRawAsync("""
            IF OBJECT_ID(N'app.UsuarioDisponibilidad', N'U') IS NULL
            CREATE TABLE app.UsuarioDisponibilidad (
                Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                UsuarioId INT NOT NULL,
                DiaSemana TINYINT NOT NULL,
                HoraDesde TIME(0) NOT NULL,
                HoraHasta TIME(0) NOT NULL,
                CONSTRAINT FK_UsuarioDisponibilidad_Usuarios FOREIGN KEY (UsuarioId) REFERENCES app.Usuarios (Id) ON DELETE CASCADE
            );
            """);

        await db.Database.ExecuteSqlRawAsync("""
            IF OBJECT_ID(N'app.AuthToken', N'U') IS NULL
            CREATE TABLE app.AuthToken (
                Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                UsuarioId INT NOT NULL,
                Tipo NVARCHAR(20) NOT NULL,
                TokenHash CHAR(64) NOT NULL,
                ExpiraEn DATETIME2(0) NOT NULL,
                UsadoEn DATETIME2(0) NULL,
                CreadoEn DATETIME2(0) NOT NULL DEFAULT (SYSUTCDATETIME()),
                CONSTRAINT FK_AuthToken_Usuarios FOREIGN KEY (UsuarioId) REFERENCES app.Usuarios (Id) ON DELETE CASCADE
            );
            """);

        await db.Database.ExecuteSqlRawAsync("""
            IF OBJECT_ID(N'app.EstablecimientoUbicacion', N'U') IS NULL
            CREATE TABLE app.EstablecimientoUbicacion (
                IdEstablecimiento NVARCHAR(64) NOT NULL PRIMARY KEY,
                Latitud FLOAT NOT NULL,
                Longitud FLOAT NOT NULL,
                Barrio NVARCHAR(80) NULL,
                ActualizadoEn DATETIME2(0) NOT NULL DEFAULT (SYSUTCDATETIME())
            );
            """);

        await SeedCabaUbicacionesAsync(db);
    }

    public static async Task<string?> ValidateAssigneeForSlotAsync(
        AppDbContext db, Usuario assignee, DateOnly fecha, TimeOnly hora, string idEstablecimiento)
    {
        if (assignee.Rol != "Preventor")
            return null; // gestores pueden autoasignarse sin franja

        var dias = await db.UsuarioDisponibilidades.AsNoTracking()
            .Where(d => d.UsuarioId == assignee.Id)
            .ToListAsync();
        var iso = GeoHelper.ToIsoDiaSemana(fecha);
        var franjas = dias.Where(d => d.DiaSemana == iso)
            .Select(d => (d.HoraDesde, d.HoraHasta))
            .ToList();
        if (franjas.Count > 0 && !GeoHelper.HoraEnFranjas(hora, franjas))
            return "El preventor no tiene disponibilidad en ese día/hora.";

        var agenda = await db.AgendaItems.AsNoTracking()
            .Where(a => a.UsuarioId == assignee.Id
                && a.FechaPlanificada == fecha
                && (a.Estado == "programada" || a.Estado == "realizada"))
            .Select(a => new { a.HoraPlanificada, a.IdEstablecimiento })
            .ToListAsync();
        if (agenda.Any(a => a.HoraPlanificada == hora))
            return "El preventor ya tiene una visita a esa hora.";

        var estIds = agenda.Select(a => a.IdEstablecimiento).Append(idEstablecimiento).Distinct().ToList();
        var capitas = await LoadCapitasByEstAsync(db, estIds);
        var duracionCandidata = GeoHelper.DuracionEstimadaHoras(capitas.GetValueOrDefault(idEstablecimiento));
        var slots = agenda
            .Select(a => new GeoHelper.SlotOcupado(
                a.HoraPlanificada,
                GeoHelper.DuracionEstimadaHoras(capitas.GetValueOrDefault(a.IdEstablecimiento))))
            .ToList();
        if (!GeoHelper.RespetaGap(hora, duracionCandidata, slots))
            return $"El turno se solapa con otra visita (duración estimada {duracionCandidata:0} h según tamaño/cápitas).";

        return null;
    }

    static async Task<Dictionary<string, double?>> LoadCapitasByEstAsync(AppDbContext db, List<string> ids)
    {
        var dict = new Dictionary<string, double?>(StringComparer.OrdinalIgnoreCase);
        if (ids.Count == 0) return dict;
        var snapId = await db.RankingSnapshots.AsNoTracking()
            .Where(s => s.EsVigente)
            .OrderByDescending(s => s.Id)
            .Select(s => (int?)s.Id)
            .FirstOrDefaultAsync();
        if (snapId is null) return dict;
        var rows = await db.RankingItems.AsNoTracking()
            .Where(i => i.SnapshotId == snapId.Value && ids.Contains(i.IdEstablecimiento))
            .Select(i => new { i.IdEstablecimiento, i.CantidadCapitas })
            .ToListAsync();
        foreach (var r in rows)
            dict[r.IdEstablecimiento] = r.CantidadCapitas;
        return dict;
    }

    static async Task SeedCabaUbicacionesAsync(AppDbContext db)
    {
        var vigentes = await db.RankingSnapshots.AsNoTracking()
            .Where(s => s.EsVigente)
            .Select(s => s.Id)
            .ToListAsync();
        var rng = new Random(42);

        if (vigentes.Count > 0)
        {
            var ids = await db.RankingItems.AsNoTracking()
                .Where(i => vigentes.Contains(i.SnapshotId))
                .Select(i => i.IdEstablecimiento)
                .Distinct()
                .Take(2000)
                .ToListAsync();
            var existing = await db.EstablecimientoUbicaciones.AsNoTracking()
                .Select(e => e.IdEstablecimiento)
                .ToListAsync();
            var existingSet = existing.ToHashSet(StringComparer.OrdinalIgnoreCase);
            var missing = ids.Where(id => !existingSet.Contains(id)).ToList();
            foreach (var id in missing)
            {
                var (lat, lon) = GeoHelper.RandomCaba(rng);
                db.EstablecimientoUbicaciones.Add(new EstablecimientoUbicacion
                {
                    IdEstablecimiento = id,
                    Latitud = lat,
                    Longitud = lon,
                    ActualizadoEn = DateTime.UtcNow,
                });
            }
            if (missing.Count > 0) await db.SaveChangesAsync();
        }

        await SeedPreventoresDemoCabaAsync(db);

        // Preventores demo sin coords
        var prevs = await db.Usuarios
            .Where(u => u.Rol == "Preventor" && (u.Latitud == null || u.Longitud == null))
            .ToListAsync();
        foreach (var p in prevs)
        {
            var (lat, lon) = GeoHelper.RandomCaba(rng);
            p.Latitud = lat;
            p.Longitud = lon;
        }
        if (prevs.Count > 0) await db.SaveChangesAsync();

        // Disponibilidad default Lun-Vie 9-17 para preventores sin franjas
        var prevIds = await db.Usuarios.Where(u => u.Rol == "Preventor" && u.Activo)
            .Select(u => u.Id).ToListAsync();
        var conDisp = await db.UsuarioDisponibilidades.Select(d => d.UsuarioId).Distinct().ToListAsync();
        var sin = prevIds.Except(conDisp).ToList();
        foreach (var uid in sin)
        {
            for (byte d = 1; d <= 5; d++)
            {
                db.UsuarioDisponibilidades.Add(new UsuarioDisponibilidad
                {
                    UsuarioId = uid,
                    DiaSemana = d,
                    HoraDesde = new TimeOnly(9, 0),
                    HoraHasta = new TimeOnly(17, 0),
                });
            }
        }
        if (sin.Count > 0) await db.SaveChangesAsync();
    }

    /// <summary>Preventores de prueba en barrios distintos (pass Prev123!) para demo de cercanía.</summary>
    static async Task SeedPreventoresDemoCabaAsync(AppDbContext db)
    {
        var zonaId = await db.Zonas.Select(z => (int?)z.Id).FirstOrDefaultAsync();
        var demos = new (string Email, string Nombre, double Lat, double Lon, string Barrio)[]
        {
            ("prev.palermo@pfi.local", "Ana Palermo", -34.5875, -58.4250, "Palermo"),
            ("prev.belgrano@pfi.local", "Bruno Belgrano", -34.5620, -58.4550, "Belgrano"),
            ("prev.flores@pfi.local", "Carla Flores", -34.6280, -58.4630, "Flores"),
            ("prev.boca@pfi.local", "Diego La Boca", -34.6345, -58.3630, "La Boca"),
            ("prev.recoleta@pfi.local", "Elena Recoleta", -34.5870, -58.3925, "Recoleta"),
            ("prev.caballito@pfi.local", "Facundo Caballito", -34.6200, -58.4400, "Caballito"),
        };

        var emails = demos.Select(d => d.Email).ToList();
        var existingEmails = await db.Usuarios.AsNoTracking()
            .Where(u => emails.Contains(u.Email))
            .Select(u => u.Email)
            .ToListAsync();
        var existingSet = existingEmails.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var hash = BCrypt.Net.BCrypt.HashPassword("Prev123!");
        var created = false;
        foreach (var d in demos)
        {
            if (existingSet.Contains(d.Email)) continue;
            db.Usuarios.Add(new Usuario
            {
                Email = d.Email,
                Nombre = d.Nombre,
                PasswordHash = hash,
                Rol = "Preventor",
                ZonaId = zonaId,
                Activo = true,
                DebeCambiarPassword = false,
                Latitud = d.Lat,
                Longitud = d.Lon,
                CreadoEn = DateTime.UtcNow,
            });
            created = true;
        }

        if (created) await db.SaveChangesAsync();
    }

    static async Task<EstablecimientoUbicacion> EnsureEstablecimientoUbicacionAsync(AppDbContext db, string id)
    {
        var (lat, lon) = GeoHelper.RandomCaba(Random.Shared);
        var row = new EstablecimientoUbicacion
        {
            IdEstablecimiento = id,
            Latitud = lat,
            Longitud = lon,
            ActualizadoEn = DateTime.UtcNow,
        };
        db.EstablecimientoUbicaciones.Add(row);
        await db.SaveChangesAsync();
        return row;
    }

    static async Task<Usuario?> GetUser(ClaimsPrincipal principal, AppDbContext db)
    {
        var sub = principal.FindFirstValue(JwtRegisteredClaimNames.Sub)
            ?? principal.FindFirstValue(ClaimTypes.NameIdentifier);
        if (!int.TryParse(sub, out var id)) return null;
        return await db.Usuarios.FirstOrDefaultAsync(u => u.Id == id && u.Activo);
    }

    static bool CanManage(Usuario u) => u.Rol is "Admin" or "Coordinador";
    static bool CanAdmin(Usuario u) => u.Rol is "Admin";

    public static object ToUserDtoExt(Usuario user) => new
    {
        user.Id,
        user.Email,
        user.Nombre,
        user.Rol,
        user.ZonaId,
        mfaRequired = user.MfaRequired,
        mfaEnabled = user.MfaEnabled,
        mfaSetupRequired = user.MfaRequired && !user.MfaEnabled,
        debeCambiarPassword = user.DebeCambiarPassword,
        latitud = user.Latitud,
        longitud = user.Longitud,
    };

    static object ToUsuarioAdminDto(Usuario user) => new
    {
        user.Id,
        user.Email,
        user.Nombre,
        user.Rol,
        user.ZonaId,
        user.Activo,
        mfaRequired = user.MfaRequired,
        mfaEnabled = user.MfaEnabled,
        mfaSetupRequired = user.MfaRequired && !user.MfaEnabled,
        debeCambiarPassword = user.DebeCambiarPassword,
        latitud = user.Latitud,
        longitud = user.Longitud,
        creadoEn = user.CreadoEn,
        disponibilidad = user.Disponibilidades
            .OrderBy(d => d.DiaSemana)
            .Select(d => new
            {
                diaSemana = d.DiaSemana,
                horaDesde = d.HoraDesde.ToString("HH:mm"),
                horaHasta = d.HoraHasta.ToString("HH:mm"),
            }),
    };

    static string CreateSessionToken(Usuario user, string key, string issuer)
    {
        var claims = new[]
        {
            new Claim(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
            new Claim(JwtRegisteredClaimNames.Email, user.Email),
            new Claim(ClaimTypes.Role, user.Rol),
            new Claim("name", user.Nombre),
        };
        var creds = new SigningCredentials(
            new SymmetricSecurityKey(Encoding.UTF8.GetBytes(key)),
            SecurityAlgorithms.HmacSha256);
        var token = new JwtSecurityToken(
            issuer: issuer,
            audience: issuer,
            claims: claims,
            expires: DateTime.UtcNow.AddHours(12),
            signingCredentials: creds);
        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    static string CreateMfaPendingToken(Usuario user, string key, string issuer)
    {
        var claims = new[]
        {
            new Claim(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
            new Claim("mfa", "pending"),
        };
        var creds = new SigningCredentials(
            new SymmetricSecurityKey(Encoding.UTF8.GetBytes(key)),
            SecurityAlgorithms.HmacSha256);
        var token = new JwtSecurityToken(
            issuer: issuer,
            audience: issuer,
            claims: claims,
            expires: DateTime.UtcNow.AddMinutes(5),
            signingCredentials: creds);
        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    static ClaimsPrincipal? ValidateMfaPendingToken(string token, string key, string issuer)
    {
        try
        {
            var handler = new JwtSecurityTokenHandler();
            var principal = handler.ValidateToken(token, new TokenValidationParameters
            {
                ValidateIssuer = true,
                ValidateAudience = true,
                ValidateLifetime = true,
                ValidateIssuerSigningKey = true,
                ValidIssuer = issuer,
                ValidAudience = issuer,
                IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(key)),
            }, out _);
            if (principal.FindFirstValue("mfa") != "pending") return null;
            return principal;
        }
        catch
        {
            return null;
        }
    }

    public record ForgotPasswordRequest(string? Email);
    public record ResetPasswordRequest(string? Token, string? Nueva);
    public record AcceptInviteRequest(string? Token, string? Nueva);
    public record MfaLoginRequest(string? MfaToken, string? Code);
    public record MfaConfirmRequest(string? Code);
    public record DisponibilidadDto(int DiaSemana, string? HoraDesde, string? HoraHasta);
    public record CreateUsuarioRequest(
        string? Email, string? Nombre, string? Rol, int? ZonaId,
        double? Latitud, double? Longitud, bool? MfaRequired, List<DisponibilidadDto>? Disponibilidad);
    public record UpdateUsuarioRequest(
        string? Nombre, string? Rol, bool? Activo, int? ZonaId,
        double? Latitud, double? Longitud, bool? MfaRequired, bool? ResetMfa,
        List<DisponibilidadDto>? Disponibilidad);

    sealed record CandidatoDto(
        int Id, string Email, string Nombre, double Latitud, double Longitud,
        int VisitasDelDia, double HorasCargaDia, double DistanciaKm, double Score,
        string AnclaOrigen, bool DisponibleEnHora,
        List<string> HorasOcupadas, List<string> HuecosDisponibles);
}
