using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using PfiPrevencion.Api;
using PfiPrevencion.Api.Data;
using PfiPrevencion.Api.Services;

var builder = WebApplication.CreateBuilder(args);

var connectionString = builder.Configuration.GetConnectionString("PfiPrevencion")
    ?? "Server=localhost;Database=PfiPrevencion;Trusted_Connection=True;TrustServerCertificate=True;Encrypt=True";

var jwtKey = builder.Configuration["Jwt:Key"] ?? "PfiPrevencionDevKey_ChangeMe_32chars!!";
var jwtIssuer = builder.Configuration["Jwt:Issuer"] ?? "PfiPrevencion";

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(connectionString));

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = jwtIssuer,
            ValidAudience = jwtIssuer,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey)),
        };
    });
builder.Services.AddAuthorization();
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
        policy.AllowAnyHeader().AllowAnyMethod().AllowAnyOrigin());
});
builder.Services.AddOpenApi();
builder.Services.AddHttpClient<GeminiClient>(c =>
{
    var timeoutSeconds = builder.Configuration.GetValue<int?>("Gemini:TimeoutSeconds") ?? 180;
    if (timeoutSeconds < 30) timeoutSeconds = 30;
    c.Timeout = TimeSpan.FromSeconds(timeoutSeconds);
});
builder.Services.AddScoped<CopilotoService>();
builder.Services.AddSingleton<IEmailSender, SmtpEmailSender>();
builder.Services.AddScoped<AuthTokenService>();

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    await EnsureAgendaHoraColumnAsync(db);
    await AuthUsersEndpoints.EnsureAuthGeoTablesAsync(db);
    await EnsureEstablecimientoReagendaTableAsync(db);
}

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

app.UseCors();

// SPA: archivos estáticos del build de Vite (wwwroot) en el mismo origen que /api.
app.UseDefaultFiles();
app.UseStaticFiles();

app.UseAuthentication();
app.UseAuthorization();

// Si el admin exige MFA y el usuario aún no lo confirmó, solo permite /api/me y setup/confirm.
app.Use(async (context, next) =>
{
    if (context.User.Identity?.IsAuthenticated == true)
    {
        var path = context.Request.Path.Value ?? "";
        if (path.StartsWith("/api/", StringComparison.OrdinalIgnoreCase)
            && !IsAllowedDuringMfaSetup(path))
        {
            var sub = context.User.FindFirstValue(JwtRegisteredClaimNames.Sub)
                ?? context.User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (int.TryParse(sub, out var userId))
            {
                using var scope = context.RequestServices.CreateScope();
                var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
                var flags = await db.Usuarios.AsNoTracking()
                    .Where(u => u.Id == userId && u.Activo)
                    .Select(u => new { u.MfaRequired, u.MfaEnabled })
                    .FirstOrDefaultAsync();
                if (flags is { MfaRequired: true, MfaEnabled: false })
                {
                    context.Response.StatusCode = StatusCodes.Status403Forbidden;
                    await context.Response.WriteAsJsonAsync(new
                    {
                        error = "Debés completar el registro MFA antes de continuar.",
                        mfaSetupRequired = true,
                    });
                    return;
                }
            }
        }
    }

    await next();
});

app.MapGet("/api/health", async (AppDbContext db) =>
{
    var canConnect = await db.Database.CanConnectAsync();
    var snapshots = await db.RankingSnapshots.CountAsync(s => s.EsVigente);
    return Results.Ok(new
    {
        ok = canConnect,
        database = "PfiPrevencion",
        server = "localhost",
        snapshotsVigentes = snapshots,
        utc = DateTime.UtcNow,
    });
});

app.MapPost("/api/auth/login", async (LoginRequest request, AppDbContext db) =>
{
    var email = request.Email.Trim().ToLowerInvariant();
    var user = await db.Usuarios.FirstOrDefaultAsync(u => u.Email == email && u.Activo);
    if (user is null || !BCrypt.Net.BCrypt.Verify(request.Password, user.PasswordHash))
    {
        return Results.Unauthorized();
    }

    if (user.DebeCambiarPassword)
    {
        return Results.BadRequest(new { error = "Debés aceptar la invitación por mail y crear tu contraseña antes de ingresar." });
    }

    if (user.MfaEnabled && !string.IsNullOrWhiteSpace(user.MfaSecret))
    {
        AuthUsersEndpoints.TryLoginWithMfa(user, jwtKey, jwtIssuer, out _, out var mfaToken, out _);
        return Results.Ok(new
        {
            mfaRequired = true,
            mfaToken,
            user = AuthUsersEndpoints.ToUserDtoExt(user),
        });
    }

    var token = CreateToken(user, jwtKey, jwtIssuer);
    return Results.Ok(new
    {
        access_token = token,
        token_type = "Bearer",
        user = AuthUsersEndpoints.ToUserDtoExt(user),
    });
});

app.MapAuthUsersAndGeo(jwtKey, jwtIssuer);

app.MapGet("/api/me", async (ClaimsPrincipal principal, AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    return Results.Ok(AuthUsersEndpoints.ToUserDtoExt(user));
}).RequireAuthorization();

app.MapPut("/api/me", async (UpdateProfileRequest request, ClaimsPrincipal principal, AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    var nombre = (request.Nombre ?? "").Trim();
    if (nombre.Length is < 2 or > 200)
    {
        return Results.BadRequest(new { error = "El nombre debe tener entre 2 y 200 caracteres." });
    }

    user.Nombre = nombre;
    await db.SaveChangesAsync();
    return Results.Ok(AuthUsersEndpoints.ToUserDtoExt(user));
}).RequireAuthorization();

app.MapPut("/api/me/password", async (ChangePasswordRequest request, ClaimsPrincipal principal, AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    if (!BCrypt.Net.BCrypt.Verify(request.Actual, user.PasswordHash))
    {
        return Results.BadRequest(new { error = "La contraseña actual no es correcta." });
    }

    if (string.IsNullOrWhiteSpace(request.Nueva) || request.Nueva.Length < 8)
    {
        return Results.BadRequest(new { error = "La nueva contraseña debe tener al menos 8 caracteres." });
    }

    user.PasswordHash = BCrypt.Net.BCrypt.HashPassword(request.Nueva);
    await db.SaveChangesAsync();
    return Results.Ok(new { ok = true });
}).RequireAuthorization();

app.MapGet("/api/resumen", async (AppDbContext db, string? horizonte) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    var snapshot = await GetVigenteAsync(db, horizonte);
    if (snapshot is null)
    {
        return Results.NotFound(new { error = $"No hay snapshot vigente para {horizonte}" });
    }

    var items = await db.RankingItems.AsNoTracking()
        .Where(i => i.SnapshotId == snapshot.Id)
        .Select(i => new { i.IdEstablecimiento, i.Banda, i.Ranking, i.EnCooldown, i.ObligacionPrs })
        .ToListAsync();

    var criticos = items.Count(i => i.Banda == "critico");
    var altos = items.Count(i => i.Banda == "alto");
    var cooldown = items.Count(i => i.EnCooldown);
    var prs = items.Count(i => i.ObligacionPrs);
    var universo = items.Count;
    var idsUniverso = items.Select(i => i.IdEstablecimiento).ToHashSet(StringComparer.Ordinal);

    var agendas = await db.AgendaItems.AsNoTracking()
        .Where(a => idsUniverso.Contains(a.IdEstablecimiento))
        .Select(a => new
        {
            a.Id,
            a.IdEstablecimiento,
            a.Estado,
            a.CreadoEn,
            a.ActualizadoEn,
            a.CanceladaEn,
        })
        .ToListAsync();

    // Último evento operativo por establecimiento (agenda más reciente por ActualizadoEn/Id).
    var ultimoPorEst = agendas
        .GroupBy(a => a.IdEstablecimiento)
        .ToDictionary(
            g => g.Key,
            g => g.OrderByDescending(a => a.ActualizadoEn).ThenByDescending(a => a.Id).First(),
            StringComparer.Ordinal);

    var estados = new Dictionary<string, int>(StringComparer.Ordinal)
    {
        ["pendiente"] = 0,
        ["programada"] = 0,
        ["realizada"] = 0,
        ["cancelada"] = 0,
    };

    foreach (var item in items)
    {
        if (!ultimoPorEst.TryGetValue(item.IdEstablecimiento, out var agenda))
        {
            estados["pendiente"]++;
            continue;
        }

        estados[agenda.Estado] = estados.GetValueOrDefault(agenda.Estado) + 1;
    }

    // Cobertura top-K: establecimientos distintos con agenda programada o realizada / tamaño real del top-K.
    static object CoberturaTopK(
        IEnumerable<(string Id, int Ranking)> rankingItems,
        IReadOnlyDictionary<string, string> estadoPorEst,
        int k)
    {
        var top = rankingItems.Where(i => i.Ranking <= k).ToList();
        var denominador = top.Count;
        var cubiertos = top
            .Select(i => i.Id)
            .Distinct(StringComparer.Ordinal)
            .Count(id =>
                estadoPorEst.TryGetValue(id, out var est) &&
                (est == "programada" || est == "realizada"));
        var pct = denominador == 0 ? 0.0 : Math.Round(100.0 * cubiertos / denominador, 1);
        return new
        {
            k,
            cantidad = cubiertos,
            denominador,
            porcentaje = pct,
            criterio = "Establecimientos distintos del top-K con visita programada o realizada (último estado de agenda).",
        };
    }

    var estadoPorEst = ultimoPorEst.ToDictionary(
        kv => kv.Key,
        kv => kv.Value.Estado,
        StringComparer.Ordinal);
    var rankingPairs = items.Select(i => (i.IdEstablecimiento, i.Ranking)).ToList();

    var sumaEstados = estados.Values.Sum();
    return Results.Ok(new
    {
        periodo = snapshot.Periodo,
        horizonte = snapshot.Horizonte,
        criticos,
        altos,
        enCooldown = cooldown,
        obligacionPrs = prs,
        capacidadCriticos = 50,
        capacidadMensual = 225,
        universo,
        estadosOperativos = new
        {
            pendiente = estados["pendiente"],
            programada = estados["programada"],
            realizada = estados["realizada"],
            cancelada = estados["cancelada"],
            suma = sumaEstados,
            exclusivos = sumaEstados == universo,
            nota = "Estados exclusivos según el último registro de agenda del establecimiento en el universo del ranking vigente.",
        },
        cobertura = new
        {
            top50 = CoberturaTopK(rankingPairs, estadoPorEst, 50),
            top225 = CoberturaTopK(rankingPairs, estadoPorEst, 225),
            nota = "Top 50 y top 225 no se suman entre sí: el top 50 está contenido en el top 225.",
        },
        nota = "El puntaje expresa prioridad relativa, no una probabilidad calibrada.",
    });
}).RequireAuthorization();

app.MapGet("/api/riesgo", async (
    AppDbContext db,
    string? horizonte,
    string? periodo,
    string? banda,
    string? sector,
    string? q,
    string? motivo,
    bool? enCooldown,
    bool? obligacionPrs,
    bool? alertaUmbral,
    bool? programada,
    string? estadoOperativo,
    double? scoreMin,
    double? scoreMax,
    int? top,
    int? page,
    int? pageSize) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    RankingSnapshot? snapshot;
    if (!string.IsNullOrWhiteSpace(periodo))
    {
        snapshot = await db.RankingSnapshots
            .Where(s => s.Periodo == periodo && s.Horizonte == horizonte)
            .OrderByDescending(s => s.GeneradoEn)
            .FirstOrDefaultAsync();
    }
    else
    {
        snapshot = await GetVigenteAsync(db, horizonte);
    }

    if (snapshot is null)
    {
        return Results.NotFound(new { error = "Snapshot no encontrado" });
    }

    var query = db.RankingItems.AsNoTracking().Where(i => i.SnapshotId == snapshot.Id);
    if (!string.IsNullOrWhiteSpace(banda))
    {
        var b = banda.Trim().ToLowerInvariant();
        query = query.Where(i => i.Banda == b);
    }
    if (!string.IsNullOrWhiteSpace(sector))
    {
        var s = sector.Trim();
        query = query.Where(i => i.Sector == s || i.CiiuDivision == s);
    }
    if (!string.IsNullOrWhiteSpace(motivo))
    {
        var m = motivo.Trim().ToLowerInvariant();
        query = query.Where(i => i.Motivo != null && i.Motivo.ToLower() == m);
    }
    if (enCooldown is not null)
    {
        query = query.Where(i => i.EnCooldown == enCooldown);
    }
    if (obligacionPrs is not null)
    {
        query = query.Where(i => i.ObligacionPrs == obligacionPrs);
    }
    if (alertaUmbral is not null)
    {
        query = query.Where(i => i.AlertaUmbral == alertaUmbral);
    }
    if (scoreMin is not null)
    {
        query = query.Where(i => i.ScoreRiesgo >= scoreMin);
    }
    if (scoreMax is not null)
    {
        query = query.Where(i => i.ScoreRiesgo <= scoreMax);
    }
    if (!string.IsNullOrWhiteSpace(q))
    {
        var term = q.Trim().ToUpperInvariant();
        query = query.Where(i =>
            i.IdEstablecimiento.Contains(term) ||
            (i.IdEmpleador != null && i.IdEmpleador.Contains(term)));
    }

    var desdeReciente = DateTime.UtcNow.AddMonths(-3);

    if (programada is not null)
    {
        var programadasQuery = db.AgendaItems.AsNoTracking()
            .Where(a => a.Estado == "programada")
            .Select(a => a.IdEstablecimiento);
        query = programada.Value
            ? query.Where(i => programadasQuery.Contains(i.IdEstablecimiento))
            : query.Where(i => !programadasQuery.Contains(i.IdEstablecimiento));
    }

    // Filtro por estado operativo (pendiente|programada|reprogramada|realizada|reagendar).
    var estadoFiltro = string.IsNullOrWhiteSpace(estadoOperativo)
        ? null
        : estadoOperativo.Trim().ToLowerInvariant();
    if (estadoFiltro is "programada" or "reprogramada")
    {
        var programadasQuery = db.AgendaItems.AsNoTracking()
            .Where(a => a.Estado == "programada")
            .Select(a => a.IdEstablecimiento);
        query = query.Where(i => programadasQuery.Contains(i.IdEstablecimiento));
    }
    else if (estadoFiltro == "reagendar")
    {
        var reagendarQuery = db.EstablecimientoReagendas.AsNoTracking()
            .Where(r => r.Estado == "pendiente")
            .Select(r => r.IdEstablecimiento);
        query = query.Where(i => reagendarQuery.Contains(i.IdEstablecimiento));
    }
    else if (estadoFiltro == "realizada")
    {
        var realizadasQuery = db.VisitasApp.AsNoTracking()
            .Where(v => v.Resultado == "realizada" && v.FechaHoraReal >= desdeReciente)
            .Select(v => v.IdEstablecimiento);
        var conReagenda = db.EstablecimientoReagendas.AsNoTracking()
            .Where(r => r.Estado == "pendiente")
            .Select(r => r.IdEstablecimiento);
        query = query.Where(i =>
            realizadasQuery.Contains(i.IdEstablecimiento)
            && !conReagenda.Contains(i.IdEstablecimiento));
    }
    else if (estadoFiltro == "pendiente")
    {
        var ocupadasQuery = db.AgendaItems.AsNoTracking()
            .Where(a => a.Estado == "programada")
            .Select(a => a.IdEstablecimiento)
            .Concat(
                db.VisitasApp.AsNoTracking()
                    .Where(v => v.Resultado == "realizada" && v.FechaHoraReal >= desdeReciente)
                    .Select(v => v.IdEstablecimiento))
            .Concat(
                db.EstablecimientoReagendas.AsNoTracking()
                    .Where(r => r.Estado == "pendiente")
                    .Select(r => r.IdEstablecimiento));
        query = query.Where(i => !ocupadasQuery.Contains(i.IdEstablecimiento));
    }

    // Cupo máximo del ranking operativo; la grilla pagina sobre ese universo.
    var limit = Math.Clamp(top ?? 1000, 1, 1000);
    var take = Math.Clamp(pageSize ?? 50, 1, 200);
    var pageNum = Math.Max(1, page ?? 1);
    var skip = (pageNum - 1) * take;

    // Divisiones CIIU del universo filtrado (barato; no requiere enriquecer agenda).
    var sectores = await query
        .Where(i => i.CiiuDivision != null && i.CiiuDivision != "")
        .Select(i => i.CiiuDivision!)
        .Distinct()
        .OrderBy(s => s)
        .ToListAsync();

    // programada/reprogramada se distinguen tras enriquecer agenda → materializar el
    // subconjunto (ya prefiltrado por agenda activa) y paginar en memoria.
    // En el resto de casos: Skip/Take en SQL y enriquecer solo la página.
    List<RankingItem> rows;
    int total;
    var needsPostFilterEstado = estadoFiltro is "programada" or "reprogramada";
    if (needsPostFilterEstado)
    {
        rows = await query
            .OrderBy(i => i.Ranking)
            .Take(limit)
            .ToListAsync();
        total = -1; // se recalcula tras filtrar estado
    }
    else
    {
        var totalUncapped = await query.CountAsync();
        total = Math.Min(totalUncapped, limit);
        var pageTake = skip >= limit ? 0 : Math.Min(take, limit - skip);
        rows = pageTake == 0
            ? new List<RankingItem>()
            : await query
                .OrderBy(i => i.Ranking)
                .Skip(skip)
                .Take(pageTake)
                .ToListAsync();
    }

    var ids = rows.Select(i => i.IdEstablecimiento).Distinct().ToList();
    var agendasActivas = ids.Count == 0
        ? new List<AgendaItem>()
        : await db.AgendaItems.AsNoTracking()
            .Include(a => a.Usuario)
            .Where(a => a.Estado == "programada" && ids.Contains(a.IdEstablecimiento))
            .ToListAsync();
    var agendaByEst = agendasActivas
        .GroupBy(a => a.IdEstablecimiento)
        .ToDictionary(g => g.Key, g => g.OrderBy(a => a.FechaPlanificada).First());

    var reagendasPendientes = ids.Count == 0
        ? new List<EstablecimientoReagenda>()
        : await db.EstablecimientoReagendas.AsNoTracking()
            .Where(r => r.Estado == "pendiente" && ids.Contains(r.IdEstablecimiento))
            .ToListAsync();
    var reagendaByEst = reagendasPendientes
        .GroupBy(r => r.IdEstablecimiento)
        .ToDictionary(g => g.Key, g => g.OrderBy(r => r.LimiteEn).First());

    Dictionary<string, (DateTime FechaHoraReal, int? AgendaItemId)> visitaByEst;
    if (ids.Count == 0)
    {
        visitaByEst = new Dictionary<string, (DateTime, int?)>();
    }
    else
    {
        var visitasRecientes = await db.VisitasApp.AsNoTracking()
            .Where(v =>
                v.Resultado == "realizada" &&
                v.FechaHoraReal >= desdeReciente &&
                ids.Contains(v.IdEstablecimiento))
            .Select(v => new { v.IdEstablecimiento, v.FechaHoraReal, v.AgendaItemId })
            .ToListAsync();
        visitaByEst = visitasRecientes
            .GroupBy(v => v.IdEstablecimiento)
            .ToDictionary(
                g => g.Key,
                g =>
                {
                    var first = g.OrderByDescending(x => x.FechaHoraReal).First();
                    return (first.FechaHoraReal, first.AgendaItemId);
                });
    }

    var hoy = DateOnly.FromDateTime(DateTime.Today);
    var items = rows.Select(i =>
    {
        agendaByEst.TryGetValue(i.IdEstablecimiento, out var agenda);
        reagendaByEst.TryGetValue(i.IdEstablecimiento, out var reagenda);
        var tieneVisita = visitaByEst.TryGetValue(i.IdEstablecimiento, out var visitaApp);
        var enDataApp = tieneVisita;
        var estado = ResolveEstadoOperativo(agenda, tieneVisita, reagenda);
        var efectividad = AciertoHistoricoLookup(snapshot.Horizonte, i.Ranking);
        return new
        {
            i.Id,
            i.IdEstablecimiento,
            i.IdEmpleador,
            i.Ranking,
            i.ScoreRiesgo,
            efectividadHistorica = efectividad?.Pct,
            efectividadTopK = efectividad?.TopK,
            i.Banda,
            i.Motivo,
            i.ObligacionPrs,
            EnData = enDataApp,
            i.UltimaVisitaHaceMeses,
            i.Sector,
            i.CiiuDivision,
            i.CantidadCapitas,
            i.DotacionNominaMes,
            i.AlertaUmbral,
            i.MotivoPrincipalTexto,
            estadoOperativo = estado,
            agendaId = agenda?.Id ?? (tieneVisita ? visitaApp.AgendaItemId : null),
            agendaActiva = agenda is null ? null : ToAgendaResumen(agenda),
            visitaAppRecienteEn = tieneVisita ? (DateTime?)visitaApp.FechaHoraReal : null,
            reagendaLimiteEn = reagenda?.LimiteEn,
            reagendaMesesPlazo = reagenda?.MesesPlazo,
            reagendaVencida = reagenda is not null && reagenda.LimiteEn < hoy,
        };
    }).ToList();

    if (needsPostFilterEstado)
    {
        items = items.Where(x => x.estadoOperativo == estadoFiltro).ToList();
        total = items.Count;
        items = items.Skip(skip).Take(take).ToList();
    }

    return Results.Ok(new
    {
        periodo = snapshot.Periodo,
        horizonte = snapshot.Horizonte,
        total,
        page = pageNum,
        pageSize = take,
        sectores,
        items,
    });
}).RequireAuthorization();

app.MapGet("/api/establecimientos/{id}", async (string id, AppDbContext db, string? horizonte) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    var snapshot = await GetVigenteAsync(db, horizonte);
    if (snapshot is null)
    {
        return Results.NotFound(new { error = "Sin snapshot vigente" });
    }

    var item = await db.RankingItems.AsNoTracking()
        .Include(i => i.Contribuciones)
        .FirstOrDefaultAsync(i => i.SnapshotId == snapshot.Id && i.IdEstablecimiento == id);
    if (item is null)
    {
        return Results.NotFound(new { error = "Establecimiento no encontrado en la lista vigente" });
    }

    var peers = db.RankingItems.AsNoTracking().Where(i => i.SnapshotId == snapshot.Id);
    var total = await peers.CountAsync();
    var mejorScore = await peers.CountAsync(i => i.ScoreRiesgo > item.ScoreRiesgo);
    var percentile = total == 0 ? 0 : Math.Round(100.0 * (total - mejorScore) / total, 1);
    var sameCiiu = string.IsNullOrWhiteSpace(item.CiiuDivision)
        ? 0
        : await peers.CountAsync(i => i.CiiuDivision == item.CiiuDivision);
    var avgScore = total == 0 ? 0 : await peers.AverageAsync(i => i.ScoreRiesgo);
    var capitasQuery = peers.Where(i => i.CantidadCapitas != null);
    var avgCapitas = await capitasQuery.AnyAsync()
        ? await capitasQuery.AverageAsync(i => i.CantidadCapitas!.Value)
        : 0;
    var visitaQuery = peers.Where(i => i.UltimaVisitaHaceMeses != null);
    var avgVisita = await visitaQuery.AnyAsync()
        ? await visitaQuery.AverageAsync(i => i.UltimaVisitaHaceMeses!.Value)
        : 0;

    var explicacion = BuildExplicacion(item, percentile, avgScore, avgVisita);
    var aciertoHistorico = BuildAciertoHistorico(snapshot.Horizonte, item.Ranking);
    var factoresShap = BuildFactoresShap(item.Contribuciones);

    var agendaActiva = await db.AgendaItems.AsNoTracking()
        .Include(a => a.Usuario)
        .Where(a => a.IdEstablecimiento == id && a.Estado == "programada")
        .OrderBy(a => a.FechaPlanificada)
        .FirstOrDefaultAsync();

    var desdeReciente = DateTime.UtcNow.AddMonths(-3);
    var ultimaVisitaApp = await db.VisitasApp.AsNoTracking()
        .Where(v =>
            v.IdEstablecimiento == id &&
            v.Resultado == "realizada" &&
            v.FechaHoraReal >= desdeReciente)
        .OrderByDescending(v => v.FechaHoraReal)
        .FirstOrDefaultAsync();

    // Evitar ciclo JSON: no serializar navegación Contribuciones dentro de item.
    var itemDto = new
    {
        item.Id,
        item.IdEstablecimiento,
        item.IdEmpleador,
        item.Ranking,
        item.ScoreRiesgo,
        item.Banda,
        item.Motivo,
        item.ObligacionPrs,
        item.EnCooldown,
        item.UltimaVisitaHaceMeses,
        item.Sector,
        item.CiiuDivision,
        item.CantidadCapitas,
        item.DotacionNominaMes,
        item.AlertaUmbral,
        item.MotivoPrincipalTexto,
    };

    return Results.Ok(new
    {
        item = itemDto,
        periodo = snapshot.Periodo,
        horizonte = snapshot.Horizonte,
        contexto = new
        {
            totalEnRanking = total,
            percentilScore = percentile,
            promedioScore = Math.Round(avgScore, 4),
            establecimientosMismaCiiu = sameCiiu,
            promedioCapitas = Math.Round(avgCapitas, 1),
            promedioUltimaVisitaMeses = Math.Round(avgVisita, 1),
        },
        aciertoHistorico,
        comoSeCalcula = new
        {
            puntaje =
                "El puntaje es la salida del modelo de machine learning (prioridad relativa 0–1). Combina historial de accidentes, actividad económica, exposición (cápitas/dotación), visitas preventivas y obligaciones. Se usa solo para ordenar la lista: mayor puntaje = mayor prioridad de visita. No es una probabilidad calibrada de accidente.",
            explicacionPrioridad =
                "La explicación reúne dos fuentes. Las tarjetas operativas (posición en la lista, motivo predictivo o PRS, alertas y estado de visitas) se calculan con reglas de negocio sobre el ranking vigente. Las tarjetas por tema (historial, dotación, prevención, período y CIIU) se generan en el pipeline a partir de la misma fila de valores SHAP, agrupada y traducida a lenguaje claro. El panel SHAP muestra, en cambio, las cinco contribuciones individuales de mayor magnitud con su valor numérico y dirección.",
            aciertoHistorico =
                "El acierto histórico es la precisión observada en la evaluación holdout 2025: entre los establecimientos que el modelo ubicó en el top-K correspondiente a la posición de este caso, qué porcentaje tuvo al menos un accidente en el horizonte. Es una referencia grupal, no una probabilidad individual del establecimiento.",
            shap =
                "Las contribuciones SHAP indican cuánto aportó cada factor al margen interno del modelo para este establecimiento. No son probabilidad, ni causalidad, ni porcentaje del puntaje mostrado.",
            fuente = $"reports/modelo/evaluation_metrics_{snapshot.Horizonte}.json (precisión media por mes en holdout 2025)",
        },
        explicacion,
        factoresShap,
        agendaActiva = agendaActiva is null ? null : ToAgendaDto(agendaActiva),
        visitaAppReciente = ultimaVisitaApp is null
            ? null
            : new
            {
                ultimaVisitaApp.Id,
                ultimaVisitaApp.FechaHoraReal,
                ultimaVisitaApp.Tipo,
                ultimaVisitaApp.Resultado,
            },
    });
}).RequireAuthorization();

app.MapGet("/api/establecimientos/{id}/dossier", async (string id, AppDbContext db, string? horizonte) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    var dossier = await db.EstablecimientoDossiers.AsNoTracking()
        .FirstOrDefaultAsync(d => d.IdEstablecimiento == id);
    if (dossier is null)
    {
        return Results.Ok(new
        {
            disponible = false,
            nota = "No hay historial de accidentes ni visitas cargado para este establecimiento.",
        });
    }

    var contenido = JsonSerializer.Deserialize<JsonElement>(dossier.DossierJson);
    var resumenIa = await db.ResumenesIaEstablecimiento.AsNoTracking()
        .FirstOrDefaultAsync(r => r.IdEstablecimiento == id && r.Horizonte == horizonte);

    return Results.Ok(new
    {
        disponible = true,
        idEstablecimiento = id,
        referencia = dossier.Referencia,
        fuente = dossier.Fuente,
        generadoEn = dossier.GeneradoEn,
        accidentes = contenido.TryGetProperty("accidentes", out var acc) && acc.ValueKind != JsonValueKind.Null
            ? (object)acc
            : null,
        visitas = contenido.TryGetProperty("visitas", out var vis) && vis.ValueKind != JsonValueKind.Null
            ? (object)vis
            : null,
        resumenIa = resumenIa is null
            ? null
            : new
            {
                Resumen = LimpiarResumenIa(resumenIa.Resumen),
                resumenIa.Modelo,
                resumenIa.GeneradoEn,
                resumenIa.Horizonte,
            },
    });
}).RequireAuthorization();

app.MapPost("/api/establecimientos/{id}/resumen-ia", async (
    string id,
    AppDbContext db,
    GeminiClient gemini,
    ClaimsPrincipal principal,
    string? horizonte,
    bool? refrescar) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    horizonte = NormalizeHorizonte(horizonte);
    var dossier = await db.EstablecimientoDossiers.AsNoTracking()
        .FirstOrDefaultAsync(d => d.IdEstablecimiento == id);
    if (dossier is null)
    {
        return Results.NotFound(new { error = "No hay historial cargado para este establecimiento." });
    }

    var forzar = (refrescar ?? false) && CanAssignAny(user);
    var cache = await db.ResumenesIaEstablecimiento
        .FirstOrDefaultAsync(r => r.IdEstablecimiento == id && r.Horizonte == horizonte);
    if (cache is not null && !forzar)
    {
        return Results.Ok(new
        {
            Resumen = LimpiarResumenIa(cache.Resumen),
            cache.Modelo,
            cache.GeneradoEn,
            cache.Horizonte,
            desdeCache = true,
        });
    }

    // Contexto del ranking (banda/posición) para orientar el resumen; opcional.
    var snapshot = await GetVigenteAsync(db, horizonte);
    var item = snapshot is null
        ? null
        : await db.RankingItems.AsNoTracking()
            .FirstOrDefaultAsync(i => i.SnapshotId == snapshot.Id && i.IdEstablecimiento == id);

    var prompt = BuildDossierPrompt(dossier.DossierJson, horizonte, item?.Banda, item?.Ranking);
    var promptHash = Convert.ToHexString(
        System.Security.Cryptography.SHA256.HashData(Encoding.UTF8.GetBytes(prompt)));

    GeminiResult resultado;
    try
    {
        resultado = await gemini.GenerarAsync(prompt);
    }
    catch (GeminiException ex)
    {
        return Results.Json(new { error = ex.Message }, statusCode: 502);
    }

    if (cache is null)
    {
        cache = new ResumenIaEstablecimiento
        {
            IdEstablecimiento = id,
            Horizonte = horizonte,
        };
        db.ResumenesIaEstablecimiento.Add(cache);
    }
    cache.Modelo = resultado.Modelo;
    cache.PromptHash = promptHash;
    cache.Resumen = LimpiarResumenIa(resultado.Texto);
    cache.TokensPrompt = resultado.TokensPrompt;
    cache.TokensSalida = resultado.TokensSalida;
    cache.GeneradoEn = DateTime.UtcNow;
    await db.SaveChangesAsync();

    return Results.Ok(new
    {
        cache.Resumen,
        cache.Modelo,
        cache.GeneradoEn,
        cache.Horizonte,
        desdeCache = false,
    });
}).RequireAuthorization();

app.MapPost("/api/establecimientos/{id}/copiloto", async (
    string id,
    CopilotoRequest body,
    CopilotoService copiloto,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    try
    {
        var resp = await copiloto.ResponderAsync(id, body);
        return Results.Ok(resp);
    }
    catch (ArgumentException ex)
    {
        return Results.BadRequest(new { error = ex.Message });
    }
    catch (GeminiException ex)
    {
        return Results.Json(new { error = ex.Message }, statusCode: 502);
    }
}).RequireAuthorization();

app.MapGet("/api/establecimientos/{id}/copiloto/guardados", async (
    string id,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureCopilotoGuardadoTableAsync(db);

    var items = await db.CopilotoGuardados.AsNoTracking()
        .Where(g => g.UsuarioId == user.Id && g.IdEstablecimiento == id)
        .OrderByDescending(g => g.GuardadoEn)
        .Select(g => new
        {
            g.Id,
            g.Pregunta,
            g.Respuesta,
            g.Tema,
            g.Seccion,
            g.Modelo,
            g.GuardadoEn,
        })
        .ToListAsync();

    return Results.Ok(new { total = items.Count, items });
}).RequireAuthorization();

app.MapPost("/api/establecimientos/{id}/copiloto/guardados", async (
    string id,
    CopilotoGuardadoRequest body,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureCopilotoGuardadoTableAsync(db);

    var pregunta = (body.Pregunta ?? "").Trim();
    var respuesta = (body.Respuesta ?? "").Trim();
    if (pregunta.Length < 3 || respuesta.Length < 3)
    {
        return Results.BadRequest(new { error = "Pregunta y respuesta son requeridas." });
    }
    if (pregunta.Length > 800) pregunta = pregunta[..800];

    // Evitar duplicar la misma pregunta para el mismo preventor + establecimiento.
    var existente = await db.CopilotoGuardados
        .FirstOrDefaultAsync(g =>
            g.UsuarioId == user.Id &&
            g.IdEstablecimiento == id &&
            g.Pregunta == pregunta);
    if (existente is not null)
    {
        existente.Respuesta = respuesta;
        existente.Tema = string.IsNullOrWhiteSpace(body.Tema) ? existente.Tema : body.Tema!.Trim();
        existente.Seccion = string.IsNullOrWhiteSpace(body.Seccion) ? existente.Seccion : body.Seccion!.Trim();
        existente.Modelo = string.IsNullOrWhiteSpace(body.Modelo) ? existente.Modelo : body.Modelo!.Trim();
        existente.GuardadoEn = DateTime.UtcNow;
        await db.SaveChangesAsync();
        return Results.Ok(new
        {
            existente.Id,
            existente.Pregunta,
            existente.Respuesta,
            existente.Tema,
            existente.Seccion,
            existente.Modelo,
            existente.GuardadoEn,
            actualizado = true,
        });
    }

    var row = new CopilotoGuardado
    {
        UsuarioId = user.Id,
        IdEstablecimiento = id,
        Pregunta = pregunta,
        Respuesta = respuesta,
        Tema = string.IsNullOrWhiteSpace(body.Tema) ? null : body.Tema!.Trim(),
        Seccion = string.IsNullOrWhiteSpace(body.Seccion) ? null : body.Seccion!.Trim(),
        Modelo = string.IsNullOrWhiteSpace(body.Modelo) ? null : body.Modelo!.Trim(),
        GuardadoEn = DateTime.UtcNow,
    };
    db.CopilotoGuardados.Add(row);
    await db.SaveChangesAsync();

    return Results.Ok(new
    {
        row.Id,
        row.Pregunta,
        row.Respuesta,
        row.Tema,
        row.Seccion,
        row.Modelo,
        row.GuardadoEn,
        actualizado = false,
    });
}).RequireAuthorization();

app.MapDelete("/api/establecimientos/{id}/copiloto/guardados/{guardadoId:int}", async (
    string id,
    int guardadoId,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureCopilotoGuardadoTableAsync(db);

    var row = await db.CopilotoGuardados
        .FirstOrDefaultAsync(g =>
            g.Id == guardadoId &&
            g.UsuarioId == user.Id &&
            g.IdEstablecimiento == id);
    if (row is null) return Results.NotFound(new { error = "Respuesta guardada no encontrada." });

    db.CopilotoGuardados.Remove(row);
    await db.SaveChangesAsync();
    return Results.Ok(new { ok = true, id = guardadoId });
}).RequireAuthorization();

app.MapGet("/api/normativa/stats", async (AppDbContext db) =>
{
    var total = await db.NormativaChunks.AsNoTracking().CountAsync(c => c.Activo);
    var porFuente = await db.NormativaChunks.AsNoTracking()
        .Where(c => c.Activo)
        .GroupBy(c => c.SourceId)
        .Select(g => new { sourceId = g.Key, n = g.Count() })
        .OrderByDescending(x => x.n)
        .ToListAsync();
    var porTema = await db.NormativaChunks.AsNoTracking()
        .Where(c => c.Activo)
        .GroupBy(c => c.Tema)
        .Select(g => new { tema = g.Key, n = g.Count() })
        .OrderByDescending(x => x.n)
        .ToListAsync();
    return Results.Ok(new { total, porFuente, porTema });
}).RequireAuthorization();

app.MapGet("/api/estadisticas", async (AppDbContext db, string? horizonte) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    var snapshot = await GetVigenteAsync(db, horizonte);
    if (snapshot is null)
    {
        return Results.NotFound(new { error = "Sin snapshot vigente" });
    }

    var items = await db.RankingItems.AsNoTracking()
        .Where(i => i.SnapshotId == snapshot.Id)
        .ToListAsync();

    var byBanda = items
        .GroupBy(i => i.Banda)
        .Select(g => new { clave = g.Key, valor = g.Count() })
        .OrderByDescending(x => x.valor)
        .ToList();

    var byMotivo = items
        .GroupBy(i => string.IsNullOrWhiteSpace(i.Motivo) ? "sin_dato" : i.Motivo!)
        .Select(g => new { clave = g.Key, valor = g.Count() })
        .OrderByDescending(x => x.valor)
        .Take(8)
        .ToList();

    var byCiiu = items
        .GroupBy(i => string.IsNullOrWhiteSpace(i.CiiuDivision) ? "s/d" : i.CiiuDivision!)
        .Select(g => new { clave = g.Key, valor = g.Count(), scorePromedio = Math.Round(g.Average(x => x.ScoreRiesgo), 4) })
        .OrderByDescending(x => x.valor)
        .Take(12)
        .ToList();

    var bySector = items
        .GroupBy(i => string.IsNullOrWhiteSpace(i.Sector) ? "Otros" : i.Sector!)
        .Select(g => new { clave = g.Key, valor = g.Count() })
        .OrderByDescending(x => x.valor)
        .Take(10)
        .ToList();

    var scoreBuckets = new[]
    {
        new { clave = "0.00–0.50", valor = items.Count(i => i.ScoreRiesgo < 0.5) },
        new { clave = "0.50–0.70", valor = items.Count(i => i.ScoreRiesgo >= 0.5 && i.ScoreRiesgo < 0.7) },
        new { clave = "0.70–0.85", valor = items.Count(i => i.ScoreRiesgo >= 0.7 && i.ScoreRiesgo < 0.85) },
        new { clave = "0.85–0.95", valor = items.Count(i => i.ScoreRiesgo >= 0.85 && i.ScoreRiesgo < 0.95) },
        new { clave = "0.95–1.00", valor = items.Count(i => i.ScoreRiesgo >= 0.95) },
    };

    // Distribución por acierto histórico (precision@K del tramo de cada ítem).
    var aciertoBuckets = items
        .Select(i => AciertoHistoricoLookup(snapshot.Horizonte, i.Ranking)?.Pct)
        .Where(p => p is not null)
        .GroupBy(p => p!.Value)
        .OrderByDescending(g => g.Key)
        .Select(g => new { clave = $"{g.Key:0.#}%", valor = g.Count() })
        .ToList();

    var visitasBuckets = new[]
    {
        new { clave = "0–1 m", valor = items.Count(i => i.UltimaVisitaHaceMeses is >= 0 and < 2) },
        new { clave = "2–3 m", valor = items.Count(i => i.UltimaVisitaHaceMeses is >= 2 and < 4) },
        new { clave = "4–6 m", valor = items.Count(i => i.UltimaVisitaHaceMeses is >= 4 and < 7) },
        new { clave = "7–12 m", valor = items.Count(i => i.UltimaVisitaHaceMeses is >= 7 and < 13) },
        new { clave = ">12 m", valor = items.Count(i => i.UltimaVisitaHaceMeses is >= 13) },
        new { clave = "Sin visita", valor = items.Count(i => i.UltimaVisitaHaceMeses is null) },
    };

    var flags = new
    {
        enCooldown = items.Count(i => i.EnCooldown),
        sinCooldown = items.Count(i => !i.EnCooldown),
        obligacionPrs = items.Count(i => i.ObligacionPrs),
        alertaUmbral = items.Count(i => i.AlertaUmbral),
    };

    var analitica = await BuildAnaliticaAsync(db, snapshot);

    return Results.Ok(new
    {
        periodo = snapshot.Periodo,
        horizonte = snapshot.Horizonte,
        snapshotId = snapshot.Id,
        total = items.Count,
        scorePromedio = items.Count == 0 ? 0 : Math.Round(items.Average(i => i.ScoreRiesgo), 4),
        scoreMediana = Median(items.Select(i => i.ScoreRiesgo).ToList()),
        byBanda,
        byMotivo,
        byCiiu,
        bySector,
        scoreBuckets,
        aciertoBuckets,
        visitasBuckets,
        flags,
        analitica,
    });
}).RequireAuthorization();

app.MapGet("/api/snapshots", async (
    AppDbContext db,
    string? horizonte,
    string? desde,
    string? hasta) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    var query = db.RankingSnapshots.AsNoTracking().Where(s => s.Horizonte == horizonte);
    if (!string.IsNullOrWhiteSpace(desde)) query = query.Where(s => string.Compare(s.Periodo, desde) >= 0);
    if (!string.IsNullOrWhiteSpace(hasta)) query = query.Where(s => string.Compare(s.Periodo, hasta) <= 0);

    var rows = await query
        .OrderByDescending(s => s.Periodo)
        .ThenByDescending(s => s.ImportadoEn)
        .Take(100)
        .Select(s => new
        {
            s.Id,
            s.Periodo,
            s.Horizonte,
            s.EsVigente,
            s.ModeloVersion,
            s.DatosHasta,
            s.ImportadoEn,
            s.ActivadoEn,
            s.UniversoFilas,
            s.ItemsImportados,
            s.ArtifactHash,
        })
        .ToListAsync();

    return Results.Ok(new { total = rows.Count, items = rows });
}).RequireAuthorization();

app.MapGet("/api/estadisticas/analitica", async (
    AppDbContext db,
    string? horizonte,
    int? snapshotId) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    RankingSnapshot? snapshot;
    if (snapshotId is not null)
    {
        snapshot = await db.RankingSnapshots.AsNoTracking()
            .FirstOrDefaultAsync(s => s.Id == snapshotId && s.Horizonte == horizonte);
    }
    else
    {
        snapshot = await GetVigenteAsync(db, horizonte);
    }

    if (snapshot is null)
    {
        return Results.NotFound(new { error = "Snapshot no encontrado" });
    }

    return Results.Ok(await BuildAnaliticaAsync(db, snapshot));
}).RequireAuthorization();

app.MapGet("/api/cobertura/historica", async (
    AppDbContext db,
    string? horizonte,
    int? topK) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    var k = topK is 50 or 225 ? topK.Value : 225;
    var rows = await (
        from c in db.SnapshotCoberturas.AsNoTracking()
        join s in db.RankingSnapshots.AsNoTracking() on c.SnapshotId equals s.Id
        where s.Horizonte == horizonte && c.TopK == k && (s.ItemsImportados == null || s.ItemsImportados > 0)
        orderby s.ActivadoEn ?? s.ImportadoEn ?? s.GeneradoEn
        select new
        {
            snapshotId = s.Id,
            periodoDecision = s.Periodo,
            horizonte = s.Horizonte,
            topK = c.TopK,
            ventanaInicio = c.VentanaInicio,
            ventanaFin = c.VentanaFin,
            denominador = c.Denominador,
            programados = c.Programados,
            realizados = c.Realizados,
            cubiertos = c.Cubiertos,
            porcentaje = c.Porcentaje,
            estado = c.Estado,
            activadoEn = s.ActivadoEn ?? s.ImportadoEn,
            nota = "Cobertura por cohorte operativa desde la activación del snapshot, no por el mes del ranking de datos.",
        }
    ).ToListAsync();

    return Results.Ok(new { horizonte, topK = k, total = rows.Count, items = rows });
}).RequireAuthorization();

app.MapGet("/api/precision-observada", async (
    AppDbContext db,
    string? horizonte,
    int? topK) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    var k = topK is 50 or 225 ? topK.Value : 225;
    var holdoutRef = horizonte == "3m" ? 0.790 : 0.515;

    var rows = await (
        from m in db.SnapshotMetricasObservadas.AsNoTracking()
        join s in db.RankingSnapshots.AsNoTracking() on m.SnapshotId equals s.Id
        where s.Horizonte == horizonte && m.TopK == k
        orderby s.Periodo
        select new
        {
            snapshotId = s.Id,
            periodo = s.Periodo,
            horizonte = s.Horizonte,
            topK = m.TopK,
            estado = m.Estado,
            denominador = m.Denominador,
            positivos = m.Positivos,
            precision = m.Precision,
            porcentaje = m.Precision == null ? (double?)null : Math.Round(m.Precision.Value * 100, 1),
            ventanaInicio = m.VentanaInicio,
            ventanaFin = m.VentanaFin,
            fuenteCompletaHasta = m.FuenteCompletaHasta,
            esHoldoutSeed = s.ModeloVersion == "holdout_metrics",
            holdoutReferenciaTop225 = holdoutRef,
        }
    ).ToListAsync();

    return Results.Ok(new
    {
        horizonte,
        topK = k,
        total = rows.Count,
        items = rows,
        metodologia =
            "Precisión observada = establecimientos del top-K con al menos un accidente en la ventana del horizonte, " +
            "solo cuando la fuente está completa hasta el fin de esa ventana. No es causalidad ni efecto de la visita.",
    });
}).RequireAuthorization();

app.MapGet("/api/usuarios/asignables", async (ClaimsPrincipal principal, AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    var query = db.Usuarios.AsNoTracking().Where(u => u.Activo);
    if (!CanAssignAny(user))
    {
        query = query.Where(u => u.Id == user.Id);
    }
    else
    {
        query = query.Where(u =>
            u.Rol == "Preventor" || u.Rol == "Coordinador" || u.Rol == "Admin");
    }

    var rows = await query
        .OrderBy(u => u.Nombre)
        .Select(u => new { u.Id, u.Email, u.Nombre, u.Rol, u.ZonaId })
        .ToListAsync();
    return Results.Ok(rows);
}).RequireAuthorization();

app.MapGet("/api/agenda", async (
    ClaimsPrincipal principal,
    AppDbContext db,
    string? estado,
    DateOnly? desde,
    DateOnly? hasta,
    int? usuarioId) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureAgendaHoraColumnAsync(db);

    var query = db.AgendaItems.AsNoTracking()
        .Include(a => a.Usuario)
        .Include(a => a.Visita!)
            .ThenInclude(v => v.Acta!)
            .ThenInclude(ac => ac.Hallazgos)
        .AsQueryable();

    if (!CanAssignAny(user))
    {
        query = query.Where(a => a.UsuarioId == user.Id);
    }
    else if (usuarioId is not null)
    {
        query = query.Where(a => a.UsuarioId == usuarioId);
    }

    if (!string.IsNullOrWhiteSpace(estado))
    {
        var e = estado.Trim().ToLowerInvariant();
        if (e is not ("programada" or "realizada" or "cancelada"))
        {
            return Results.BadRequest(new { error = "Estado inválido. Use programada, realizada o cancelada." });
        }
        query = query.Where(a => a.Estado == e);
    }

    if (desde is not null) query = query.Where(a => a.FechaPlanificada >= desde);
    if (hasta is not null) query = query.Where(a => a.FechaPlanificada <= hasta);

    var rows = await query
        .OrderBy(a => a.FechaPlanificada)
        .ThenBy(a => a.HoraPlanificada)
        .ThenBy(a => a.Id)
        .Take(500)
        .ToListAsync();

    return Results.Ok(new
    {
        total = rows.Count,
        items = rows.Select(ToAgendaDto).ToList(),
    });
}).RequireAuthorization();

app.MapGet("/api/agenda/{id:int}", async (
    int id,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureAgendaHoraColumnAsync(db);

    var agenda = await db.AgendaItems.AsNoTracking()
        .Include(a => a.Usuario)
        .Include(a => a.Visita!)
            .ThenInclude(v => v.Acta!)
            .ThenInclude(ac => ac.Hallazgos)
        .FirstOrDefaultAsync(a => a.Id == id);
    if (agenda is null) return Results.NotFound(new { error = "Visita no encontrada." });
    if (!CanAssignAny(user) && agenda.UsuarioId != user.Id)
        return Results.Json(new { error = "Sin permiso para ver este turno." }, statusCode: 403);

    return Results.Ok(ToAgendaDto(agenda));
}).RequireAuthorization();

app.MapPost("/api/agenda", async (
    ProgramarVisitaRequest request,
    ClaimsPrincipal principal,
    AppDbContext db,
    AuthTokenService tokens) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureAgendaHoraColumnAsync(db);
    await EnsureEstablecimientoReagendaTableAsync(db);

    var horizonte = NormalizeHorizonte(request.Horizonte);
    if (request.RankingItemId <= 0)
    {
        return Results.BadRequest(new { error = "RankingItemId es obligatorio." });
    }

    if (request.FechaPlanificada < DateOnly.FromDateTime(DateTime.Today))
    {
        return Results.BadRequest(new { error = "La fecha planificada debe ser hoy o una fecha futura." });
    }

    if (!TryParseHoraPlanificada(request.HoraPlanificada, out var horaPlanificada))
    {
        return Results.BadRequest(new { error = "Indicá una hora válida (HH:mm)." });
    }

    var rankingItem = await db.RankingItems.AsNoTracking()
        .Include(i => i.Snapshot)
        .FirstOrDefaultAsync(i => i.Id == request.RankingItemId);
    if (rankingItem is null || rankingItem.Snapshot is null)
    {
        return Results.NotFound(new { error = "Ítem de priorización no encontrado." });
    }

    var assigneeId = request.UsuarioId ?? user.Id;
    if (!CanAssignAny(user) && assigneeId != user.Id)
    {
        return Results.Json(new { error = "Solo podés asignarte visitas a vos mismo." }, statusCode: 403);
    }

    var assignee = await db.Usuarios.FirstOrDefaultAsync(u => u.Id == assigneeId && u.Activo);
    if (assignee is null)
    {
        return Results.BadRequest(new { error = "El responsable indicado no existe o está inactivo." });
    }

    var slotErr = await AuthUsersEndpoints.ValidateAssigneeForSlotAsync(
        db, assignee, request.FechaPlanificada, horaPlanificada, rankingItem.IdEstablecimiento);
    if (slotErr is not null)
    {
        return Results.BadRequest(new { error = slotErr });
    }

    var yaProgramada = await db.AgendaItems.AnyAsync(a =>
        a.IdEstablecimiento == rankingItem.IdEstablecimiento && a.Estado == "programada");
    if (yaProgramada)
    {
        return Results.Conflict(new { error = "Este establecimiento ya tiene una visita programada." });
    }

    var motivoVisita = InferMotivoVisita(rankingItem);
    await using var tx = await db.Database.BeginTransactionAsync();
    var agenda = new AgendaItem
    {
        UsuarioId = assignee.Id,
        IdEstablecimiento = rankingItem.IdEstablecimiento,
        Periodo = rankingItem.Snapshot.Periodo,
        Horizonte = horizonte,
        FechaPlanificada = request.FechaPlanificada,
        HoraPlanificada = horaPlanificada,
        MotivoVisita = motivoVisita,
        Estado = "programada",
        SnapshotId = rankingItem.SnapshotId,
        SnapshotItemId = rankingItem.Id,
        RankingOrigen = rankingItem.Ranking,
        ScoreOrigen = rankingItem.ScoreRiesgo,
        BandaOrigen = rankingItem.Banda,
        MotivoOrigen = rankingItem.Motivo,
        Notas = string.IsNullOrWhiteSpace(request.Notas) ? null : request.Notas.Trim(),
        CreadoEn = DateTime.UtcNow,
        ActualizadoEn = DateTime.UtcNow,
    };

    db.AgendaItems.Add(agenda);
    try
    {
        await db.SaveChangesAsync();
        AddAgendaEvento(
            db,
            agenda,
            user,
            tipo: "programada",
            estadoAnterior: null,
            estadoNuevo: "programada",
            datos: new
            {
                fechaPlanificada = agenda.FechaPlanificada,
                horaPlanificada = FormatHoraPlanificada(agenda.HoraPlanificada),
                responsableId = agenda.UsuarioId,
                responsableNombre = assignee.Nombre,
                actorEsResponsable = user.Id == assignee.Id,
                notas = agenda.Notas,
                rankingItemId = rankingItem.Id,
                horizonte,
            });
        await CubrirReagendasPendientesAsync(db, agenda.IdEstablecimiento, agenda.Id);
        await db.SaveChangesAsync();
        await tx.CommitAsync();
    }
    catch (DbUpdateException)
    {
        await tx.RollbackAsync();
        return Results.Conflict(new { error = "Este establecimiento ya tiene una visita programada." });
    }

    await db.Entry(agenda).Reference(a => a.Usuario).LoadAsync();
    await tokens.TryNotifyVisitaAsignadaAsync(assignee, agenda, reprogramacion: false);
    return Results.Ok(ToAgendaDto(agenda));
}).RequireAuthorization();

app.MapPut("/api/agenda/{id:int}", async (
    int id,
    ReprogramarVisitaRequest request,
    ClaimsPrincipal principal,
    AppDbContext db,
    AuthTokenService tokens) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureAgendaHoraColumnAsync(db);

    var agenda = await db.AgendaItems
        .Include(a => a.Usuario)
        .FirstOrDefaultAsync(a => a.Id == id);
    if (agenda is null) return Results.NotFound(new { error = "Visita no encontrada." });
    if (agenda.Estado != "programada")
    {
        return Results.BadRequest(new { error = "Solo se pueden reprogramar visitas en estado programada." });
    }
    if (!CanAssignAny(user))
    {
        return Results.Json(new { error = "El preventor no puede reprogramar; solo marcar la visita como realizada o cancelada." }, statusCode: 403);
    }

    var antes = SnapshotAgendaDatos(agenda);
    if (request.FechaPlanificada is not null)
    {
        if (request.FechaPlanificada < DateOnly.FromDateTime(DateTime.Today))
        {
            return Results.BadRequest(new { error = "La fecha planificada debe ser hoy o una fecha futura." });
        }
        agenda.FechaPlanificada = request.FechaPlanificada.Value;
    }

    if (request.HoraPlanificada is not null)
    {
        if (!TryParseHoraPlanificada(request.HoraPlanificada, out var hora))
        {
            return Results.BadRequest(new { error = "Indicá una hora válida (HH:mm)." });
        }
        agenda.HoraPlanificada = hora;
    }

    if (request.UsuarioId is not null && request.UsuarioId != agenda.UsuarioId)
    {
        if (!CanAssignAny(user))
        {
            return Results.Json(new { error = "Solo coordinadores o admin pueden reasignar." }, statusCode: 403);
        }
        var assignee = await db.Usuarios.FirstOrDefaultAsync(u => u.Id == request.UsuarioId && u.Activo);
        if (assignee is null)
        {
            return Results.BadRequest(new { error = "El responsable indicado no existe o está inactivo." });
        }
        agenda.UsuarioId = assignee.Id;
    }

    var responsable = await db.Usuarios.FirstOrDefaultAsync(u => u.Id == agenda.UsuarioId && u.Activo);
    if (responsable is not null)
    {
        var slotErr = await AuthUsersEndpoints.ValidateAssigneeForSlotAsync(
            db, responsable, agenda.FechaPlanificada, agenda.HoraPlanificada, agenda.IdEstablecimiento);
        if (slotErr is not null)
            return Results.BadRequest(new { error = slotErr });
    }

    if (request.Notas is not null)
    {
        agenda.Notas = string.IsNullOrWhiteSpace(request.Notas) ? null : request.Notas.Trim();
    }

    agenda.ActualizadoEn = DateTime.UtcNow;
    await using var tx = await db.Database.BeginTransactionAsync();
    AddAgendaEvento(
        db,
        agenda,
        user,
        tipo: "reprogramada",
        estadoAnterior: "programada",
        estadoNuevo: "programada",
        datos: new { antes, despues = SnapshotAgendaDatos(agenda) });
    await db.SaveChangesAsync();
    await tx.CommitAsync();
    await db.Entry(agenda).Reference(a => a.Usuario).LoadAsync();
    if (responsable is not null)
        await tokens.TryNotifyVisitaAsignadaAsync(responsable, agenda, reprogramacion: true);
    return Results.Ok(ToAgendaDto(agenda));
}).RequireAuthorization();

app.MapPost("/api/agenda/{id:int}/realizar", async (
    int id,
    RealizarVisitaRequest request,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureVisitaActaTablesAsync(db);
    await EnsureAgendaHoraColumnAsync(db);

    await using var tx = await db.Database.BeginTransactionAsync();
    var agenda = await db.AgendaItems
        .Include(a => a.Usuario)
        .Include(a => a.Visita)
        .FirstOrDefaultAsync(a => a.Id == id);
    if (agenda is null) return Results.NotFound(new { error = "Visita no encontrada." });
    if (agenda.Estado != "programada")
    {
        return Results.BadRequest(new { error = "Solo se pueden cerrar visitas en estado programada." });
    }
    if (!CanCerrarOCancelarVisita(user, agenda))
    {
        return Results.Json(new { error = "No tenés permiso para cerrar esta visita." }, statusCode: 403);
    }
    if (agenda.Visita is not null)
    {
        return Results.Conflict(new { error = "Esta agenda ya tiene un cierre registrado." });
    }

    var fechaReal = request.FechaHoraReal ?? DateTime.UtcNow;
    if (fechaReal > DateTime.UtcNow.AddDays(1))
    {
        return Results.BadRequest(new { error = "La fecha de realización no puede ser futura." });
    }

    var requiereRevisita = request.Revisita == true;
    DateOnly? fechaRevisita = null;
    TimeOnly horaRevisita = new(9, 0);
    int? plazoRevisitaDias = null;
    if (requiereRevisita)
    {
        if (request.FechaRevisita is null)
        {
            return Results.BadRequest(new { error = "Indicá la fecha de la revisita." });
        }
        if (request.FechaRevisita < DateOnly.FromDateTime(DateTime.Today))
        {
            return Results.BadRequest(new { error = "La fecha de revisita debe ser hoy o futura." });
        }
        if (!TryParseHoraPlanificada(request.HoraRevisita, out horaRevisita))
        {
            return Results.BadRequest(new { error = "Indicá una hora válida para la revisita (HH:mm)." });
        }
        fechaRevisita = request.FechaRevisita;
        plazoRevisitaDias = Math.Max(
            0,
            fechaRevisita.Value.DayNumber - DateOnly.FromDateTime(DateTime.Today).DayNumber);
        if (request.PlazoRevisitaDias is int plazoReq && plazoReq > 0)
            plazoRevisitaDias = plazoReq;

        var otraProgramada = await db.AgendaItems.AnyAsync(a =>
            a.IdEstablecimiento == agenda.IdEstablecimiento &&
            a.Estado == "programada" &&
            a.Id != agenda.Id);
        if (otraProgramada)
        {
            return Results.Conflict(new
            {
                error = "Ya hay otra visita programada para este establecimiento; no se puede crear la revisita.",
            });
        }
    }

    var resultadoGlobal = NormalizeResultadoGlobal(request.ResultadoGlobal);
    var hallazgosActa = (request.HallazgosActa ?? [])
        .Where(h => !string.IsNullOrWhiteSpace(h.Hallazgo))
        .ToList();
    var (hallazgosTexto, accionesTexto) = BuildResumenVisitaDesdeActa(
        request.Hallazgos, request.Acciones, hallazgosActa);

    var visita = new VisitaApp
    {
        IdEstablecimiento = agenda.IdEstablecimiento,
        UsuarioId = agenda.UsuarioId,
        AgendaItemId = agenda.Id,
        FechaHoraReal = fechaReal,
        Tipo = agenda.MotivoVisita switch
        {
            "prs" => "regulatoria",
            "seguimiento" => "seguimiento",
            "extraordinaria" => "extraordinaria",
            _ => "predictiva",
        },
        Resultado = "realizada",
        Hallazgos = hallazgosTexto,
        Acciones = accionesTexto,
        CreadoEn = DateTime.UtcNow,
    };

    agenda.Estado = "realizada";
    agenda.ActualizadoEn = DateTime.UtcNow;
    if (!string.IsNullOrWhiteSpace(request.Notas))
    {
        agenda.Notas = request.Notas.Trim();
    }

    db.VisitasApp.Add(visita);
    await db.SaveChangesAsync();

    var checklistJson = request.Checklist is { Count: > 0 }
        ? JsonSerializer.Serialize(request.Checklist.Select(c => new
        {
            id = c.Id,
            label = c.Label,
            estado = NormalizeChecklistEstado(c.Estado),
        }))
        : null;
    var acta = new VisitaActa
    {
        VisitaAppId = visita.Id,
        AgendaItemId = agenda.Id,
        ResultadoGlobal = resultadoGlobal,
        Revisita = requiereRevisita,
        PlazoRevisitaDias = plazoRevisitaDias,
        Notas = string.IsNullOrWhiteSpace(request.NotasActa) ? null : request.NotasActa.Trim(),
        ChecklistJson = checklistJson,
        CreadoEn = DateTime.UtcNow,
        CreadoPorUsuarioId = user.Id,
    };
    db.VisitasActa.Add(acta);
    await db.SaveChangesAsync();

    var abiertos = 0;
    foreach (var h in hallazgosActa)
    {
        var estado = NormalizeHallazgoEstado(h.Estado);
        if (estado == "abierto") abiertos++;
        db.VisitasHallazgos.Add(new VisitaHallazgo
        {
            ActaId = acta.Id,
            IdEstablecimiento = agenda.IdEstablecimiento,
            Severidad = NormalizeSeveridad(h.Severidad),
            Hallazgo = h.Hallazgo!.Trim(),
            Recomendacion = string.IsNullOrWhiteSpace(h.Recomendacion) ? null : h.Recomendacion.Trim(),
            PlazoDias = h.PlazoDias,
            NormaRef = string.IsNullOrWhiteSpace(h.NormaRef) ? null : h.NormaRef.Trim(),
            ItemRgrl = string.IsNullOrWhiteSpace(h.ItemRgrl) ? null : h.ItemRgrl.Trim(),
            Estado = estado,
            Origen = NormalizeOrigen(h.Origen),
            CreadoEn = DateTime.UtcNow,
        });
    }

    int? revisitaAgendaId = null;
    if (requiereRevisita && fechaRevisita is not null)
    {
        var revisitaAgenda = new AgendaItem
        {
            UsuarioId = agenda.UsuarioId,
            IdEstablecimiento = agenda.IdEstablecimiento,
            Periodo = agenda.Periodo,
            Horizonte = agenda.Horizonte,
            FechaPlanificada = fechaRevisita.Value,
            HoraPlanificada = horaRevisita,
            MotivoVisita = "seguimiento",
            Estado = "programada",
            SnapshotId = agenda.SnapshotId,
            SnapshotItemId = agenda.SnapshotItemId,
            RankingOrigen = agenda.RankingOrigen,
            ScoreOrigen = agenda.ScoreOrigen,
            BandaOrigen = agenda.BandaOrigen,
            MotivoOrigen = "Revisita por hallazgos / seguimiento",
            Notas = string.IsNullOrWhiteSpace(request.NotasActa)
                ? $"Revisita de la visita #{agenda.Id}"
                : $"Revisita de #{agenda.Id}: {request.NotasActa.Trim()}",
            CreadoEn = DateTime.UtcNow,
            ActualizadoEn = DateTime.UtcNow,
        };
        db.AgendaItems.Add(revisitaAgenda);
        await db.SaveChangesAsync();
        revisitaAgendaId = revisitaAgenda.Id;
        AddAgendaEvento(
            db,
            revisitaAgenda,
            user,
            tipo: "programada",
            estadoAnterior: null,
            estadoNuevo: "programada",
            datos: new
            {
                fechaPlanificada = revisitaAgenda.FechaPlanificada,
                horaPlanificada = FormatHoraPlanificada(revisitaAgenda.HoraPlanificada),
                origen = "revisita",
                visitaOrigenId = agenda.Id,
                responsableId = revisitaAgenda.UsuarioId,
            });
    }

    AddAgendaEvento(
        db,
        agenda,
        user,
        tipo: "realizada",
        estadoAnterior: "programada",
        estadoNuevo: "realizada",
        datos: new
        {
            fechaHoraReal = visita.FechaHoraReal,
            tipoVisita = visita.Tipo,
            hallazgos = visita.Hallazgos,
            acciones = visita.Acciones,
            notas = agenda.Notas,
            resultadoGlobal,
            revisita = acta.Revisita,
            fechaRevisita,
            horaRevisita = requiereRevisita ? FormatHoraPlanificada(horaRevisita) : null,
            plazoRevisitaDias,
            revisitaAgendaId,
            reagendaMesesPlazo = request.ReagendaMesesPlazo,
            hallazgosTotal = hallazgosActa.Count,
            hallazgosAbiertos = abiertos,
            responsableId = agenda.UsuarioId,
            actorEsResponsable = user.Id == agenda.UsuarioId,
        });

    // Plazo de reagenda (sin crear turno): el coordinador agenda después desde Priorización.
    if (request.ReagendaMesesPlazo is int meses && meses is 1 or 2 or 3 or 6)
    {
        await EnsureEstablecimientoReagendaTableAsync(db);
        var pendientes = await db.EstablecimientoReagendas
            .Where(r => r.IdEstablecimiento == agenda.IdEstablecimiento && r.Estado == "pendiente")
            .ToListAsync();
        foreach (var p in pendientes)
        {
            p.Estado = "cancelada";
            p.CubiertoEn = DateTime.UtcNow;
        }

        var limite = DateOnly.FromDateTime(DateTime.Today).AddMonths(meses);
        db.EstablecimientoReagendas.Add(new EstablecimientoReagenda
        {
            IdEstablecimiento = agenda.IdEstablecimiento,
            LimiteEn = limite,
            MesesPlazo = (byte)meses,
            VisitaOrigenId = visita.Id,
            Estado = "pendiente",
            CreadoEn = DateTime.UtcNow,
            CreadoPorUsuarioId = user.Id,
        });
    }

    await db.SaveChangesAsync();
    await tx.CommitAsync();

    await db.Entry(agenda).Reference(a => a.Visita).LoadAsync();
    if (agenda.Visita is not null)
    {
        await db.Entry(agenda.Visita).Reference(v => v.Acta).LoadAsync();
        if (agenda.Visita.Acta is not null)
            await db.Entry(agenda.Visita.Acta).Collection(ac => ac.Hallazgos).LoadAsync();
    }
    return Results.Ok(ToAgendaDto(agenda));
}).RequireAuthorization();

app.MapPost("/api/agenda/{id:int}/cancelar", async (
    int id,
    CancelarVisitaRequest request,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    var agenda = await db.AgendaItems
        .Include(a => a.Usuario)
        .FirstOrDefaultAsync(a => a.Id == id);
    if (agenda is null) return Results.NotFound(new { error = "Visita no encontrada." });
    if (agenda.Estado != "programada")
    {
        return Results.BadRequest(new { error = "Solo se pueden cancelar visitas en estado programada." });
    }
    if (!CanCerrarOCancelarVisita(user, agenda))
    {
        return Results.Json(new { error = "No tenés permiso para cancelar esta visita." }, statusCode: 403);
    }

    var motivo = (request.MotivoCancelacion ?? "").Trim();
    if (motivo.Length is < 3 or > 400)
    {
        return Results.BadRequest(new { error = "Indicá un motivo de cancelación (3–400 caracteres)." });
    }

    await using var tx = await db.Database.BeginTransactionAsync();
    agenda.Estado = "cancelada";
    agenda.MotivoCancelacion = motivo;
    agenda.CanceladaEn = DateTime.UtcNow;
    agenda.ActualizadoEn = DateTime.UtcNow;
    AddAgendaEvento(
        db,
        agenda,
        user,
        tipo: "cancelada",
        estadoAnterior: "programada",
        estadoNuevo: "cancelada",
        datos: new
        {
            motivoCancelacion = motivo,
            canceladaEn = agenda.CanceladaEn,
            responsableId = agenda.UsuarioId,
            actorEsResponsable = user.Id == agenda.UsuarioId,
        });
    await db.SaveChangesAsync();
    await tx.CommitAsync();
    return Results.Ok(ToAgendaDto(agenda));
}).RequireAuthorization();

app.MapGet("/api/establecimientos/{id}/acta/contexto-cierre", async (
    string id,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureVisitaActaTablesAsync(db);

    var estId = id.Trim();
    var abiertos = await db.VisitasHallazgos.AsNoTracking()
        .Where(h => h.IdEstablecimiento == estId && h.Estado == "abierto")
        .OrderByDescending(h => h.Severidad == "alta")
        .ThenByDescending(h => h.CreadoEn)
        .Take(40)
        .Select(h => new
        {
            h.Id,
            h.Severidad,
            h.Hallazgo,
            h.Recomendacion,
            h.PlazoDias,
            h.NormaRef,
            h.ItemRgrl,
            h.Estado,
            h.Origen,
            h.CreadoEn,
        })
        .ToListAsync();

    var checklist = await BuildChecklistSugeridoAsync(db, estId);

    return Results.Ok(new
    {
        idEstablecimiento = estId,
        hallazgosAbiertos = abiertos,
        checklistSugerido = checklist,
    });
}).RequireAuthorization();

// Catálogo de ítems del formulario RGRL (para agregar hallazgos fuera de los focos precargados).
app.MapGet("/api/acta/items-rgrl", async (
    ClaimsPrincipal principal,
    AppDbContext db,
    string? q) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    var items = await GetRgrlCatalogItemsAsync(db);
    if (!string.IsNullOrWhiteSpace(q))
    {
        var needle = q.Trim();
        items = items
            .Where(i => i.Label.Contains(needle, StringComparison.OrdinalIgnoreCase))
            .ToList();
    }

    return Results.Ok(new
    {
        total = items.Count,
        items = items.Select(i => new
        {
            id = i.Id,
            label = i.Label,
            actividad = i.Actividad,
            normaRef = i.NormaRef,
        }),
    });
}).RequireAuthorization();

app.MapGet("/api/establecimientos/{id}/hallazgos-abiertos", async (
    string id,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureVisitaActaTablesAsync(db);

    var estId = id.Trim();
    var items = await db.VisitasHallazgos.AsNoTracking()
        .Where(h => h.IdEstablecimiento == estId && h.Estado == "abierto")
        .OrderByDescending(h => h.Severidad == "alta")
        .ThenByDescending(h => h.CreadoEn)
        .Take(100)
        .Select(h => new
        {
            h.Id,
            h.Severidad,
            h.Hallazgo,
            h.Recomendacion,
            h.PlazoDias,
            h.NormaRef,
            h.ItemRgrl,
            h.Estado,
            h.Origen,
            h.CreadoEn,
            h.ActaId,
        })
        .ToListAsync();

    return Results.Ok(new { total = items.Count, items });
}).RequireAuthorization();

app.MapGet("/api/establecimientos/{id}/visitas", async (
    string id,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureVisitaActaTablesAsync(db);

    var estId = id.Trim();
    var rows = await db.VisitasApp.AsNoTracking()
        .Include(v => v.Usuario)
        .Include(v => v.Acta!)
            .ThenInclude(a => a.Hallazgos)
        .Where(v => v.IdEstablecimiento == estId && v.Resultado == "realizada")
        .OrderByDescending(v => v.FechaHoraReal)
        .ThenByDescending(v => v.Id)
        .Take(50)
        .ToListAsync();

    var items = rows.Select(v =>
    {
        object? checklist = null;
        if (!string.IsNullOrWhiteSpace(v.Acta?.ChecklistJson))
        {
            try { checklist = JsonSerializer.Deserialize<object>(v.Acta.ChecklistJson); }
            catch { checklist = null; }
        }

        var hallazgos = (v.Acta?.Hallazgos ?? [])
            .OrderByDescending(h => h.Severidad == "alta")
            .ThenBy(h => h.Id)
            .Select(h => new
            {
                h.Id,
                h.Severidad,
                h.Hallazgo,
                h.Recomendacion,
                h.PlazoDias,
                h.NormaRef,
                h.ItemRgrl,
                h.Estado,
                h.Origen,
            })
            .ToList();

        return new
        {
            v.Id,
            v.FechaHoraReal,
            v.Tipo,
            v.Resultado,
            v.Hallazgos,
            v.Acciones,
            v.AgendaItemId,
            responsable = v.Usuario is null
                ? null
                : new { v.Usuario.Id, v.Usuario.Nombre, v.Usuario.Email },
            acta = v.Acta is null
                ? null
                : new
                {
                    v.Acta.Id,
                    v.Acta.ResultadoGlobal,
                    v.Acta.Revisita,
                    v.Acta.PlazoRevisitaDias,
                    v.Acta.Notas,
                    checklist,
                    hallazgosTotal = hallazgos.Count,
                    hallazgosAbiertos = hallazgos.Count(h => h.Estado == "abierto"),
                    hallazgos,
                },
        };
    }).ToList();

    return Results.Ok(new { total = items.Count, items });
}).RequireAuthorization();

app.MapPatch("/api/hallazgos/{id:int}", async (
    int id,
    PatchHallazgoRequest request,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    await EnsureVisitaActaTablesAsync(db);

    var hallazgo = await db.VisitasHallazgos.FirstOrDefaultAsync(h => h.Id == id);
    if (hallazgo is null) return Results.NotFound(new { error = "Hallazgo no encontrado." });

    var estado = NormalizeHallazgoEstado(request.Estado);
    hallazgo.Estado = estado;
    await db.SaveChangesAsync();

    return Results.Ok(new
    {
        hallazgo.Id,
        hallazgo.Severidad,
        hallazgo.Hallazgo,
        hallazgo.Recomendacion,
        hallazgo.PlazoDias,
        hallazgo.NormaRef,
        hallazgo.ItemRgrl,
        hallazgo.Estado,
        hallazgo.Origen,
        hallazgo.CreadoEn,
        hallazgo.IdEstablecimiento,
    });
}).RequireAuthorization();

app.MapPost("/api/establecimientos/{id}/acta/sugerir", async (
    string id,
    SugerirActaRequest request,
    ClaimsPrincipal principal,
    AppDbContext db,
    GeminiClient gemini) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    if (!gemini.Configurado)
    {
        return Results.Json(new { error = "El servicio de IA no está configurado." }, statusCode: 503);
    }

    var estId = id.Trim();
    var dossier = await db.EstablecimientoDossiers.AsNoTracking()
        .FirstOrDefaultAsync(d => d.IdEstablecimiento == estId);
    var contexto = ExtractContextoCortoDossier(dossier?.DossierJson);

    var checklistObs = (request.Checklist ?? [])
        .Where(c => string.Equals(c.Estado, "observacion", StringComparison.OrdinalIgnoreCase))
        .Select(c => c.Label ?? c.Id ?? "")
        .Where(s => !string.IsNullOrWhiteSpace(s))
        .Take(12)
        .ToList();

    var sb = new StringBuilder();
    sb.AppendLine("Sos un asistente de prevención de riesgos laborales (Argentina, SRT).");
    sb.AppendLine("Proponé entre 1 y 5 hallazgos BORRADOR a partir del checklist marcado y las notas.");
    sb.AppendLine("Respondé SOLO un JSON array (sin markdown) con objetos:");
    sb.AppendLine("""{"severidad":"baja|media|alta","hallazgo":"...","recomendacion":"...","plazoDias":30,"normaRef":"Res. SRT …","itemRgrl":"opcional"}""");
    sb.AppendLine("No inventes datos del empleador. Sé concreto y accionable.");
    sb.AppendLine();
    if (!string.IsNullOrWhiteSpace(contexto))
    {
        sb.AppendLine("=== CONTEXTO HISTÓRICO (anonimizado) ===");
        sb.AppendLine(contexto);
        sb.AppendLine();
    }
    if (checklistObs.Count > 0)
    {
        sb.AppendLine("Ítems del checklist con observación:");
        foreach (var c in checklistObs) sb.Append("- ").AppendLine(c);
    }
    if (!string.IsNullOrWhiteSpace(request.Notas))
    {
        sb.AppendLine("Notas del preventor:");
        sb.AppendLine(request.Notas.Trim());
    }

    try
    {
        var result = await gemini.GenerarAsync(sb.ToString());
        var hallazgos = ParseHallazgosSugeridos(result.Texto);
        return Results.Ok(new
        {
            modelo = result.Modelo,
            hallazgos,
            nota = "Borradores efímeros: no se guardan hasta confirmar el cierre de la visita.",
        });
    }
    catch (GeminiException ex)
    {
        return Results.Json(new { error = ex.Message }, statusCode: 502);
    }
}).RequireAuthorization();

/// <summary>
/// Mejora el borrador de un hallazgo escrito por el preventor y completa campos
/// (recomendación, severidad, plazo, norma). No inventa hechos nuevos.
/// </summary>
app.MapPost("/api/establecimientos/{id}/acta/mejorar-hallazgo", async (
    string id,
    MejorarHallazgoRequest request,
    ClaimsPrincipal principal,
    AppDbContext db,
    GeminiClient gemini) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    if (!gemini.Configurado)
        return Results.Json(new { error = "El servicio de IA no está configurado." }, statusCode: 503);

    var borrador = (request.Borrador ?? request.Hallazgo ?? "").Trim();
    if (borrador.Length < 8)
        return Results.BadRequest(new { error = "Escribí un resumen del hallazgo (al menos unas palabras) para que la IA lo mejore." });

    var estId = id.Trim();
    var dossier = await db.EstablecimientoDossiers.AsNoTracking()
        .FirstOrDefaultAsync(d => d.IdEstablecimiento == estId);
    var contexto = ExtractContextoCortoDossier(dossier?.DossierJson);

    var sb = new StringBuilder();
    sb.AppendLine("Sos un asistente de prevención de riesgos laborales (Argentina, SRT).");
    sb.AppendLine("El preventor escribió un BORRADOR de hallazgo. Mejorá la redacción y completá los campos.");
    sb.AppendLine("REGLAS:");
    sb.AppendLine("- No inventes hechos que el preventor no mencionó.");
    sb.AppendLine("- Podés ordenar, aclarar y proponer recomendación/plazo/norma razonables.");
    sb.AppendLine("- Español rioplatense, concreto, accionable.");
    sb.AppendLine("- Respondé SOLO un JSON object (sin markdown):");
    sb.AppendLine("""{"severidad":"baja|media|alta","hallazgo":"...","recomendacion":"...","plazoDias":30,"normaRef":"Res. SRT … o null","itemRgrl":"opcional o null"}""");
    sb.AppendLine();
    if (!string.IsNullOrWhiteSpace(request.ItemLabel))
    {
        sb.AppendLine("Ítem del checklist vinculado:");
        sb.AppendLine(request.ItemLabel.Trim());
        sb.AppendLine();
    }
    if (!string.IsNullOrWhiteSpace(contexto))
    {
        sb.AppendLine("=== CONTEXTO HISTÓRICO (anonimizado, solo apoyo) ===");
        sb.AppendLine(contexto);
        sb.AppendLine();
    }
    sb.AppendLine("=== BORRADOR DEL PREVENTOR ===");
    sb.AppendLine(borrador);
    if (!string.IsNullOrWhiteSpace(request.Recomendacion))
    {
        sb.AppendLine();
        sb.AppendLine("Recomendación previa (mejorala si aporta):");
        sb.AppendLine(request.Recomendacion.Trim());
    }

    try
    {
        var result = await gemini.GenerarAsync(sb.ToString());
        var mejorado = ParseHallazgoMejorado(result.Texto);
        if (mejorado is null)
            return Results.Json(new { error = "La IA no devolvió un hallazgo usable. Reintentá." }, statusCode: 502);

        return Results.Ok(new
        {
            modelo = result.Modelo,
            hallazgo = mejorado,
            nota = "Borrador mejorado: revisá y editá antes de confirmar el acta.",
        });
    }
    catch (GeminiException ex)
    {
        return Results.Json(new { error = ex.Message }, statusCode: 502);
    }
}).RequireAuthorization();

app.MapGet("/api/agenda/{id:int}/eventos", async (
    int id,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    var agenda = await db.AgendaItems.AsNoTracking().FirstOrDefaultAsync(a => a.Id == id);
    if (agenda is null) return Results.NotFound(new { error = "Visita no encontrada." });
    if (!CanManageAgenda(user, agenda) && !CanAssignAny(user))
    {
        return Results.Json(new { error = "No tenés permiso para ver la auditoría de esta visita." }, statusCode: 403);
    }

    var eventos = await db.AgendaEventos.AsNoTracking()
        .Where(e => e.AgendaItemId == id)
        .OrderByDescending(e => e.OcurridoEn)
        .ThenByDescending(e => e.Id)
        .ToListAsync();

    return Results.Ok(new
    {
        agendaId = id,
        total = eventos.Count,
        items = eventos.Select(ToAgendaEventoDto).ToList(),
        nota = eventos.Count == 0
            ? "Sin eventos de auditoría. Las visitas creadas antes de habilitar la bitácora no tienen actor atribuido."
            : null,
    });
}).RequireAuthorization();

app.MapGet("/api/auditoria/agenda", async (
    ClaimsPrincipal principal,
    AppDbContext db,
    string? tipo,
    string? idEstablecimiento,
    int? agendaItemId,
    int? actorUsuarioId,
    DateTime? desde,
    DateTime? hasta,
    int? page,
    int? pageSize) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    var take = Math.Clamp(pageSize ?? 50, 1, 200);
    var skip = Math.Max(0, ((page ?? 1) - 1) * take);

    var query = db.AgendaEventos.AsNoTracking().AsQueryable();

    if (!CanAssignAny(user))
    {
        // Preventor: ve eventos de agendas propias o donde fue actor.
        var propias = db.AgendaItems.AsNoTracking()
            .Where(a => a.UsuarioId == user.Id)
            .Select(a => a.Id);
        query = query.Where(e => e.ActorUsuarioId == user.Id || propias.Contains(e.AgendaItemId));
    }

    if (!string.IsNullOrWhiteSpace(tipo))
    {
        var t = tipo.Trim().ToLowerInvariant();
        if (t is not ("programada" or "reprogramada" or "realizada" or "cancelada"))
        {
            return Results.BadRequest(new { error = "Tipo inválido." });
        }
        query = query.Where(e => e.Tipo == t);
    }

    if (!string.IsNullOrWhiteSpace(idEstablecimiento))
    {
        var est = idEstablecimiento.Trim();
        query = query.Where(e => e.IdEstablecimiento == est);
    }

    if (agendaItemId is not null) query = query.Where(e => e.AgendaItemId == agendaItemId);
    if (actorUsuarioId is not null) query = query.Where(e => e.ActorUsuarioId == actorUsuarioId);
    if (desde is not null) query = query.Where(e => e.OcurridoEn >= desde);
    if (hasta is not null) query = query.Where(e => e.OcurridoEn <= hasta);

    var total = await query.CountAsync();
    var rows = await query
        .OrderByDescending(e => e.OcurridoEn)
        .ThenByDescending(e => e.Id)
        .Skip(skip)
        .Take(take)
        .ToListAsync();

    return Results.Ok(new
    {
        total,
        page = page ?? 1,
        pageSize = take,
        items = rows.Select(ToAgendaEventoDto).ToList(),
    });
}).RequireAuthorization();

// Deep links del React Router → index.html (producción / publish).
app.MapFallbackToFile("/index.html");

app.Run();

static async Task EnsureCopilotoGuardadoTableAsync(AppDbContext db)
{
    await db.Database.ExecuteSqlRawAsync(
        """
        IF OBJECT_ID(N'app.CopilotoGuardado', N'U') IS NULL
        BEGIN
            CREATE TABLE app.CopilotoGuardado
            (
                Id                 int IDENTITY(1,1) NOT NULL PRIMARY KEY,
                UsuarioId          int            NOT NULL,
                IdEstablecimiento  varchar(64)    NOT NULL,
                Pregunta           nvarchar(800)  NOT NULL,
                Respuesta          nvarchar(max)  NOT NULL,
                Tema               nvarchar(64)   NULL,
                Seccion            nvarchar(80)   NULL,
                Modelo             nvarchar(80)   NULL,
                GuardadoEn         datetime2      NOT NULL CONSTRAINT DF_CopilotoGuardado_GuardadoEn DEFAULT SYSUTCDATETIME()
            );
            CREATE INDEX IX_CopilotoGuardado_User_Est
                ON app.CopilotoGuardado (UsuarioId, IdEstablecimiento, GuardadoEn DESC);
        END
        """);
}

static bool IsAllowedDuringMfaSetup(string path) =>
    path.Equals("/api/me", StringComparison.OrdinalIgnoreCase)
    || path.Equals("/api/me/mfa/setup", StringComparison.OrdinalIgnoreCase)
    || path.Equals("/api/me/mfa/confirm", StringComparison.OrdinalIgnoreCase);

static async Task EnsureAgendaHoraColumnAsync(AppDbContext db)
{
    await db.Database.ExecuteSqlRawAsync(
        """
        IF COL_LENGTH(N'app.AgendaItems', N'HoraPlanificada') IS NULL
        BEGIN
            ALTER TABLE app.AgendaItems
                ADD HoraPlanificada time NOT NULL
                    CONSTRAINT DF_AgendaItems_HoraPlanificada DEFAULT ('09:00:00');
        END
        """);
}

static async Task EnsureEstablecimientoReagendaTableAsync(AppDbContext db)
{
    await db.Database.ExecuteSqlRawAsync(
        """
        IF OBJECT_ID(N'app.EstablecimientoReagenda', N'U') IS NULL
        BEGIN
            CREATE TABLE app.EstablecimientoReagenda
            (
                Id                  int            NOT NULL IDENTITY(1,1) CONSTRAINT PK_EstablecimientoReagenda PRIMARY KEY,
                IdEstablecimiento   nvarchar(64)   NOT NULL,
                LimiteEn            date           NOT NULL,
                MesesPlazo          tinyint        NOT NULL,
                VisitaOrigenId      int            NULL,
                AgendaCubiertaId    int            NULL,
                Estado              nvarchar(20)   NOT NULL CONSTRAINT DF_EstablecimientoReagenda_Estado DEFAULT (N'pendiente'),
                CreadoEn            datetime2(0)   NOT NULL CONSTRAINT DF_EstablecimientoReagenda_CreadoEn DEFAULT (SYSUTCDATETIME()),
                CubiertoEn          datetime2(0)   NULL,
                CreadoPorUsuarioId  int            NULL,
                CONSTRAINT CK_EstablecimientoReagenda_Estado CHECK (Estado IN (N'pendiente', N'cubierta', N'cancelada')),
                CONSTRAINT CK_EstablecimientoReagenda_Meses CHECK (MesesPlazo IN (1, 2, 3, 6))
            );
            CREATE INDEX IX_EstablecimientoReagenda_Est_Estado
                ON app.EstablecimientoReagenda (IdEstablecimiento, Estado)
                INCLUDE (LimiteEn, MesesPlazo);
        END
        """);
}

static async Task CubrirReagendasPendientesAsync(AppDbContext db, string idEstablecimiento, int agendaId)
{
    var pendientes = await db.EstablecimientoReagendas
        .Where(r => r.IdEstablecimiento == idEstablecimiento && r.Estado == "pendiente")
        .ToListAsync();
    var ahora = DateTime.UtcNow;
    foreach (var r in pendientes)
    {
        r.Estado = "cubierta";
        r.AgendaCubiertaId = agendaId;
        r.CubiertoEn = ahora;
    }
}

static bool TryParseHoraPlanificada(string? value, out TimeOnly hora)
{
    hora = new TimeOnly(9, 0);
    if (string.IsNullOrWhiteSpace(value)) return true;
    var t = value.Trim();
    if (TimeOnly.TryParse(t, out hora)) return true;
    if (t.Length >= 5 && TimeOnly.TryParse(t[..5], out hora)) return true;
    return false;
}

static string FormatHoraPlanificada(TimeOnly hora) => hora.ToString("HH\\:mm");

static async Task EnsureVisitaActaTablesAsync(AppDbContext db)
{
    await db.Database.ExecuteSqlRawAsync(
        """
        IF OBJECT_ID(N'app.VisitaActa', N'U') IS NULL
        BEGIN
            CREATE TABLE app.VisitaActa
            (
                Id                   int IDENTITY(1,1) NOT NULL PRIMARY KEY,
                VisitaAppId          int            NOT NULL,
                AgendaItemId         int            NULL,
                ResultadoGlobal      nvarchar(20)   NOT NULL,
                Revisita             bit            NOT NULL CONSTRAINT DF_VisitaActa_Revisita DEFAULT 0,
                PlazoRevisitaDias    int            NULL,
                Notas                nvarchar(max)  NULL,
                ChecklistJson        nvarchar(max)  NULL,
                CreadoEn             datetime2      NOT NULL CONSTRAINT DF_VisitaActa_CreadoEn DEFAULT SYSUTCDATETIME(),
                CreadoPorUsuarioId   int            NULL,
                CONSTRAINT UQ_VisitaActa_VisitaAppId UNIQUE (VisitaAppId),
                CONSTRAINT FK_VisitaActa_VisitaApp FOREIGN KEY (VisitaAppId) REFERENCES app.VisitasApp (Id),
                CONSTRAINT CK_VisitaActa_Resultado CHECK (ResultadoGlobal IN (N'ok', N'observacion', N'critico'))
            );
            CREATE INDEX IX_VisitaActa_Agenda ON app.VisitaActa (AgendaItemId);
        END
        """);
    await db.Database.ExecuteSqlRawAsync(
        """
        IF OBJECT_ID(N'app.VisitaHallazgo', N'U') IS NULL
        BEGIN
            CREATE TABLE app.VisitaHallazgo
            (
                Id                   int IDENTITY(1,1) NOT NULL PRIMARY KEY,
                ActaId               int            NOT NULL,
                IdEstablecimiento    varchar(64)    NOT NULL,
                Severidad            nvarchar(16)   NOT NULL,
                Hallazgo             nvarchar(max)  NOT NULL,
                Recomendacion        nvarchar(max)  NULL,
                PlazoDias            int            NULL,
                NormaRef             nvarchar(200)  NULL,
                ItemRgrl             nvarchar(120)  NULL,
                Estado               nvarchar(16)   NOT NULL CONSTRAINT DF_VisitaHallazgo_Estado DEFAULT N'abierto',
                Origen               nvarchar(32)   NOT NULL CONSTRAINT DF_VisitaHallazgo_Origen DEFAULT N'manual',
                CreadoEn             datetime2      NOT NULL CONSTRAINT DF_VisitaHallazgo_CreadoEn DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_VisitaHallazgo_Acta FOREIGN KEY (ActaId) REFERENCES app.VisitaActa (Id) ON DELETE CASCADE,
                CONSTRAINT CK_VisitaHallazgo_Severidad CHECK (Severidad IN (N'baja', N'media', N'alta')),
                CONSTRAINT CK_VisitaHallazgo_Estado CHECK (Estado IN (N'abierto', N'cerrado')),
                CONSTRAINT CK_VisitaHallazgo_Origen CHECK (Origen IN (N'manual', N'sugerido_aceptado'))
            );
            CREATE INDEX IX_VisitaHallazgo_Est_Estado
                ON app.VisitaHallazgo (IdEstablecimiento, Estado, CreadoEn DESC);
        END
        """);
}

static string NormalizeResultadoGlobal(string? value) =>
    (value ?? "").Trim().ToLowerInvariant() switch
    {
        "ok" => "ok",
        "critico" => "critico",
        _ => "observacion",
    };

static string NormalizeSeveridad(string? value) =>
    (value ?? "").Trim().ToLowerInvariant() switch
    {
        "baja" => "baja",
        "alta" => "alta",
        _ => "media",
    };

static string NormalizeHallazgoEstado(string? value) =>
    string.Equals(value?.Trim(), "cerrado", StringComparison.OrdinalIgnoreCase) ? "cerrado" : "abierto";

static string NormalizeOrigen(string? value) =>
    string.Equals(value?.Trim(), "sugerido_aceptado", StringComparison.OrdinalIgnoreCase)
        ? "sugerido_aceptado"
        : "manual";

static string NormalizeChecklistEstado(string? value) =>
    (value ?? "").Trim().ToLowerInvariant() switch
    {
        "ok" => "ok",
        "observacion" => "observacion",
        "no_aplica" => "no_aplica",
        _ => "no_verificado",
    };

static (string? Hallazgos, string? Acciones) BuildResumenVisitaDesdeActa(
    string? hallazgosTexto,
    string? accionesTexto,
    List<HallazgoActaDto> hallazgosActa)
{
    if (!string.IsNullOrWhiteSpace(hallazgosTexto) || !string.IsNullOrWhiteSpace(accionesTexto))
    {
        return (
            string.IsNullOrWhiteSpace(hallazgosTexto) ? null : hallazgosTexto.Trim(),
            string.IsNullOrWhiteSpace(accionesTexto) ? null : accionesTexto.Trim());
    }

    if (hallazgosActa.Count == 0) return (null, null);

    var hallazgos = string.Join(
        "; ",
        hallazgosActa.Select(h =>
        {
            var sev = NormalizeSeveridad(h.Severidad);
            var txt = (h.Hallazgo ?? "").Trim();
            return $"[{sev}] {txt}";
        }).Where(s => s.Length > 4).Take(12));

    var acciones = string.Join(
        "; ",
        hallazgosActa
            .Where(h => !string.IsNullOrWhiteSpace(h.Recomendacion))
            .Select(h =>
            {
                var rec = h.Recomendacion!.Trim();
                return h.PlazoDias is int d ? $"{rec} (plazo {d} d)" : rec;
            })
            .Take(12));

    return (
        string.IsNullOrWhiteSpace(hallazgos) ? null : hallazgos,
        string.IsNullOrWhiteSpace(acciones) ? null : acciones);
}

static async Task<List<RgrlCatalogItem>> GetRgrlCatalogItemsAsync(AppDbContext db)
{
    lock (RgrlCatalogCache.Gate)
    {
        if (RgrlCatalogCache.Items is { Count: > 0 })
            return RgrlCatalogCache.Items;
    }

    var chunks = await db.NormativaChunks.AsNoTracking()
        .Where(c => c.Activo && c.SourceId == "rgrl" && c.Tema == "rgrl_checklist")
        .OrderBy(c => c.Orden)
        .Select(c => new { c.Id, c.Texto, c.Actividad, c.NormaRef })
        .ToListAsync();

    var itemRx = new System.Text.RegularExpressions.Regex(
        @"^(?<n>\d{1,3})\.\s+(?<body>.+)$",
        System.Text.RegularExpressions.RegexOptions.Multiline | System.Text.RegularExpressions.RegexOptions.CultureInvariant);
    var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var list = new List<RgrlCatalogItem>();

    foreach (var chunk in chunks)
    {
        foreach (System.Text.RegularExpressions.Match m in itemRx.Matches(chunk.Texto ?? ""))
        {
            var num = m.Groups["n"].Value;
            var label = FormatRgrlFormItemLabel(m.Groups["body"].Value);
            if (label.Length < 8 || IsVagueChecklistLabel(label)) continue;
            if (!seen.Add(label)) continue;
            list.Add(new RgrlCatalogItem(
                $"rgrl-{chunk.Id}-{num}",
                label,
                chunk.Actividad,
                chunk.NormaRef));
        }
    }

    lock (RgrlCatalogCache.Gate)
    {
        RgrlCatalogCache.Items = list;
        return list;
    }
}

static string FormatRgrlFormItemLabel(string raw)
{
    var t = (raw ?? "").Trim().Replace('\n', ' ').Replace('\r', ' ');
    t = System.Text.RegularExpressions.Regex.Replace(t, @"\s+", " ");
    // Cortar citas legales y encabezados de sección pegados al final.
    t = System.Text.RegularExpressions.Regex.Replace(
        t,
        @"\s*\?\s*(Art\.|Arts\.|Cap\.|Dec\.|Res\.|Ley)\b.*$",
        "?",
        System.Text.RegularExpressions.RegexOptions.IgnoreCase);
    t = System.Text.RegularExpressions.Regex.Replace(
        t,
        @"\s+(Art\.|Arts\.|Cap\.|Dec\.|Res\.|Ley)\b.*$",
        "",
        System.Text.RegularExpressions.RegexOptions.IgnoreCase);
    t = System.Text.RegularExpressions.Regex.Replace(t, @"\s+[A-ZÁÉÍÓÚÜÑ0-9 /()\-]{10,}$", "");
    t = System.Text.RegularExpressions.Regex.Replace(t, @"^¿\s*", "").Trim();
    t = t.TrimEnd('?', ' ', '.', ';');
    t = FormatChecklistLabel(t, max: 0);
    if (t.Length > 0)
        t = char.ToUpperInvariant(t[0]) + t[1..];
    return t;
}

static async Task<List<object>> BuildChecklistSugeridoAsync(AppDbContext db, string idEstablecimiento)
{
    // Focos de esta visita: núcleo + todos los del dossier (historial y accidentes).
    // No es el RGRL completo; el tope lo pone el dossier, no un recorte artificial.
    var items = new List<object>();
    var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var tieneHistorial = false;
    var tieneAccidentes = false;

    void Add(string id, string label, string origen)
    {
        var key = CleanChecklistFocusLabel(label);
        if (key.Length < 4 || !seen.Add(key)) return;
        if (IsVagueChecklistLabel(key)) return;
        items.Add(new { id, label = key, estado = "no_aplica", origen });
    }

    // Núcleo fijo: lo que casi siempre se mira en una visita.
    string[] nucleo =
    [
        "Orden y limpieza de áreas de trabajo",
        "Uso y estado de EPP",
        "Documentación de higiene y seguridad vigente",
    ];
    for (var i = 0; i < nucleo.Length; i++)
        Add($"core-{i}", nucleo[i], "nucleo");

    var dossier = await db.EstablecimientoDossiers.AsNoTracking()
        .FirstOrDefaultAsync(d => d.IdEstablecimiento == idEstablecimiento);
    if (dossier?.DossierJson is { Length: > 0 } json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;
            if (root.TryGetProperty("visitas", out var vis) &&
                vis.TryGetProperty("incumplimientos_frecuentes", out var inc) &&
                inc.ValueKind == JsonValueKind.Array)
            {
                var i = 0;
                foreach (var e in inc.EnumerateArray())
                {
                    var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
                    if (string.IsNullOrWhiteSpace(k)) continue;
                    var before = items.Count;
                    Add($"inc-{i}", k, "historial");
                    if (items.Count > before) tieneHistorial = true;
                    i++;
                }
            }
            if (root.TryGetProperty("accidentes", out var acc) &&
                acc.TryGetProperty("top_forma", out var formas) &&
                formas.ValueKind == JsonValueKind.Array)
            {
                var i = 0;
                foreach (var e in formas.EnumerateArray())
                {
                    var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
                    if (string.IsNullOrWhiteSpace(k)) continue;
                    var before = items.Count;
                    Add($"acc-{i}", FormatAccidentFocusLabel(k), "accidente");
                    if (items.Count > before) tieneAccidentes = true;
                    i++;
                }
            }
        }
        catch
        {
            // checklist parcial sin dossier
        }
    }

    // Solo si no hay focos propios del establecimiento: relleno genérico mínimo.
    if (!tieneHistorial && !tieneAccidentes)
    {
        string[] fallback =
        [
            "Señalización de riesgos y vías de evacuación",
            "Estado de extintores y medios de lucha contra incendio",
            "Protecciones de máquinas y resguardos",
            "Capacitación e inducción vigente del personal",
            "Botiquín y primeros auxilios",
            "Registro de entregas de EPP",
        ];
        var fi = 0;
        foreach (var f in fallback)
            Add($"base-{fi++}", f, "base");
    }

    return items;
}

static string FormatAccidentFocusLabel(string forma)
{
    var f = CleanChecklistFocusLabel(forma);
    f = System.Text.RegularExpressions.Regex.Replace(
        f,
        @"^ca[ií]das de personas que ocurren al\s+",
        "Caídas al ",
        System.Text.RegularExpressions.RegexOptions.IgnoreCase);
    f = System.Text.RegularExpressions.Regex.Replace(
        f,
        @"^choque de veh[ií]culos\.?$",
        "Choque de vehículos",
        System.Text.RegularExpressions.RegexOptions.IgnoreCase);
    // Sin ":" para no disparar subtítulos falsos en la UI.
    return $"Prevención de {f.TrimEnd('.')}";
}

static string CleanChecklistFocusLabel(string s, int max = 0)
{
    var t = FormatChecklistLabel(s, max: 0);
    // Corpus a veces llega cortado con "..." / "…" o a mitad de palabra (sanitize duro).
    var truncated = System.Text.RegularExpressions.Regex.IsMatch(t, @"(\.\.\.|…)\s*$")
        || LooksHardTruncatedChecklistLabel(t);
    t = System.Text.RegularExpressions.Regex.Replace(t, @"(\.\.\.|…)+\s*$", "").Trim();
    t = t.Trim().TrimEnd(',', ';', '·', '-', '–', '—', ' ');
    t = System.Text.RegularExpressions.Regex.Replace(t, @"\s+", " ");

    // "TEMA: detalle" → una sola frase legible.
    var colon = t.IndexOf(": ", StringComparison.Ordinal);
    if (colon is > 0 and < 48 && colon < t.Length - 3)
    {
        var head = t[..colon].Trim();
        var tail = t[(colon + 2)..].Trim();
        if (tail.Length > 0 && !head.Equals(tail, StringComparison.OrdinalIgnoreCase))
        {
            if (truncated || LooksIncompleteChecklistTail(tail) || LooksHardTruncatedChecklistLabel(tail))
                t = ToSentenceCase(head);
            else if (tail.Contains(head, StringComparison.OrdinalIgnoreCase) && tail.Length < head.Length + 40)
                t = ToSentenceCase(tail);
            else
                t = $"{ToSentenceCase(head)}. {ToSentenceCase(tail)}";
        }
    }
    else
    {
        // "Tema. Detalle cortado a medias" → quedarse con el tema (1ª oración completa).
        var dot = t.IndexOf(". ", StringComparison.Ordinal);
        if (dot > 12 && dot < t.Length - 3)
        {
            var head = t[..dot].Trim();
            var tail = t[(dot + 2)..].Trim();
            if (truncated || LooksIncompleteChecklistTail(tail) || LooksHardTruncatedChecklistLabel(tail))
                t = ToSentenceCase(head);
            else if (tail.Contains(head, StringComparison.OrdinalIgnoreCase) && tail.Length < head.Length + 40)
                t = ToSentenceCase(tail);
            else if (t.Length > 140 || LooksHardTruncatedChecklistLabel(t))
                t = truncated || LooksHardTruncatedChecklistLabel(t)
                    ? ToSentenceCase(head)
                    : $"{ToSentenceCase(head)}. {ToSentenceCase(tail)}";
        }
        else if ((truncated || LooksHardTruncatedChecklistLabel(t)) && t.Length > 24)
        {
            // Sin punto: sacar la última palabra incompleta.
            var lastSpace = t.LastIndexOf(' ');
            if (lastSpace > 16) t = t[..lastSpace].TrimEnd(',', ';', ' ');
        }
    }

    if (max > 0 && t.Length > max)
    {
        var cut = t[..max];
        var lastSpace = cut.LastIndexOf(' ');
        if (lastSpace > max / 2) cut = cut[..lastSpace];
        t = cut.TrimEnd(',', '.', ':', ';');
    }
    return t;
}

static bool LooksHardTruncatedChecklistLabel(string s)
{
    if (string.IsNullOrWhiteSpace(s)) return true;
    s = s.Trim();
    if (System.Text.RegularExpressions.Regex.IsMatch(s, @"(\.\.\.|…)\s*$")) return true;
    if (s.EndsWith(',') || s.EndsWith(';') || s.EndsWith('-') || s.EndsWith('/')) return true;
    // Última "palabra" de 1–3 letras que no es palabra funcional → corte a medias ("y ca").
    var parts = s.Split(' ', StringSplitOptions.RemoveEmptyEntries);
    if (parts.Length == 0) return true;
    var last = parts[^1];
    if (last.Length is >= 1 and <= 3 &&
        !System.Text.RegularExpressions.Regex.IsMatch(
            last,
            @"^(y|e|o|u|de|la|el|lo|un|en|al|no|si|sí|ya|ni|se|su|es|ha|he|me|te|le|nos|les|más|muy|sin|con|por|que|qué|cómo|como|epp|art|srt)$",
            System.Text.RegularExpressions.RegexOptions.IgnoreCase))
        return true;
    return false;
}

static bool LooksIncompleteChecklistTail(string s)
{
    if (string.IsNullOrWhiteSpace(s)) return true;
    if (s.Length < 16) return true;
    if (LooksHardTruncatedChecklistLabel(s)) return true;
    return System.Text.RegularExpressions.Regex.IsMatch(
        s,
        @"\b(y|e|o|u|de|del|la|las|el|los|un|una|unos|unas|a|al|en|con|por|para|que|se|su|sus|indicar|realizar|acreditar|disponer|medici[oó]n)\s*$",
        System.Text.RegularExpressions.RegexOptions.IgnoreCase);
}

static string ToSentenceCase(string s)
{
    if (string.IsNullOrWhiteSpace(s)) return "";
    s = s.Trim();
    // Si viene TODO EN MAYÚSCULAS, bajar y capitalizar.
    var letters = s.Where(char.IsLetter).ToArray();
    if (letters.Length >= 4 && letters.Count(char.IsUpper) >= letters.Length * 0.7)
    {
        s = s.ToLowerInvariant();
        return char.ToUpperInvariant(s[0]) + s[1..];
    }
    return s;
}

/// <summary>Filtra títulos meta del corpus RGRL que no sirven como ítem de acta.</summary>
static bool IsVagueChecklistLabel(string label)
{
    var t = label.Trim().ToLowerInvariant();
    if (t.Length < 8) return true;
    if (t.Contains("reglas generales del relevamiento", StringComparison.Ordinal)) return true;
    if (t.Contains("cumplimiento dec.", StringComparison.Ordinal)) return true;
    if (System.Text.RegularExpressions.Regex.IsMatch(t, @"[íi]tems?\s*\d+\s*[-–—]\s*\d+")) return true;
    if (System.Text.RegularExpressions.Regex.IsMatch(t, @"^rgrl(\s+(industria|obra|comercio|agro))?$")) return true;
    return false;
}

static string FormatChecklistLabel(string s, int max = 0)
{
    var t = (s ?? "").Trim()
        .Replace('\n', ' ')
        .Replace('\r', ' ');
    t = System.Text.RegularExpressions.Regex.Replace(t, @"(\d)[\u2014\u2013—–-](\d)", "$1-$2");
    t = t
        .Replace('\u2014', ':') // —
        .Replace('\u2013', ':'); // –
    // Separador de sección tipo "TEMA - subtítulo"
    t = System.Text.RegularExpressions.Regex.Replace(t, @"\s+[-–—]\s+", ": ");
    while (t.Contains("  ", StringComparison.Ordinal)) t = t.Replace("  ", " ", StringComparison.Ordinal);
    while (t.Contains("::", StringComparison.Ordinal)) t = t.Replace("::", ":", StringComparison.Ordinal);
    t = t.Replace(": :", ": ").Trim().TrimStart(':').Trim();

    var parts = t.Split(':', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
    for (var i = 0; i < parts.Length; i++)
        parts[i] = FormatChecklistSegment(parts[i]);
    t = string.Join(": ", parts);

    if (max <= 0 || t.Length <= max) return t;
    var cut = t[..max];
    var lastSpace = cut.LastIndexOf(' ');
    if (lastSpace > max / 2) cut = cut[..lastSpace];
    return cut.TrimEnd(',', '.', ':', ';') + "…";
}

static string FormatChecklistSegment(string segment)
{
    var s = segment.Trim();
    if (s.Length == 0) return s;
    var letters = s.Where(char.IsLetter).ToArray();
    if (letters.Length < 3) return s;
    var upper = letters.Count(char.IsUpper);
    // Formatear si está mayormente en mayúsculas o si tiene una ráfaga larga en mayúsculas.
    var needsFix = upper >= letters.Length * 0.45
        || System.Text.RegularExpressions.Regex.IsMatch(s, @"[A-ZÁÉÍÓÚÑ]{5,}");
    return needsFix ? ToSentenceCaseEs(s) : s;
}

static string ToSentenceCaseEs(string s)
{
    var lower = s.ToLowerInvariant();
    var chars = lower.ToCharArray();
    var capitalizeNext = true;
    for (var i = 0; i < chars.Length; i++)
    {
        if (capitalizeNext && char.IsLetter(chars[i]))
        {
            chars[i] = char.ToUpperInvariant(chars[i]);
            capitalizeNext = false;
        }
        else if (chars[i] is '.' or '!' or '?')
        {
            capitalizeNext = true;
        }
    }
    var result = new string(chars);
    string[] acros = ["rgrl", "epp", "prs", "pese", "srt", "art", "rar", "ige"];
    foreach (var a in acros)
    {
        result = System.Text.RegularExpressions.Regex.Replace(
            result,
            $@"\b{a}\b",
            a.ToUpperInvariant(),
            System.Text.RegularExpressions.RegexOptions.IgnoreCase);
    }
    return result;
}

static string TruncateLabel(string s, int max)
{
    return FormatChecklistLabel(s, max);
}

static string ExtractContextoCortoDossier(string? dossierJson)
{
    if (string.IsNullOrWhiteSpace(dossierJson)) return "";
    try
    {
        using var doc = JsonDocument.Parse(dossierJson);
        var root = doc.RootElement;
        var sb = new StringBuilder();
        if (root.TryGetProperty("visitas", out var vis) &&
            vis.TryGetProperty("incumplimientos_frecuentes", out var inc) &&
            inc.ValueKind == JsonValueKind.Array)
        {
            sb.AppendLine("Incumplimientos frecuentes:");
            var i = 0;
            foreach (var e in inc.EnumerateArray())
            {
                if (i++ >= 6) break;
                var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
                if (!string.IsNullOrWhiteSpace(k)) sb.Append("- ").AppendLine(TruncateLabel(k, 160));
            }
        }
        if (root.TryGetProperty("accidentes", out var acc) &&
            acc.TryGetProperty("top_forma", out var formas) &&
            formas.ValueKind == JsonValueKind.Array)
        {
            sb.AppendLine("Formas de accidente frecuentes:");
            var i = 0;
            foreach (var e in formas.EnumerateArray())
            {
                if (i++ >= 4) break;
                var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
                if (!string.IsNullOrWhiteSpace(k)) sb.Append("- ").AppendLine(TruncateLabel(k, 120));
            }
        }
        var ctx = sb.ToString().Trim();
        return ctx.Length > 1200 ? ctx[..1200] + "…" : ctx;
    }
    catch
    {
        return "";
    }
}

static string StripJsonFence(string texto)
{
    var raw = (texto ?? "").Trim();
    if (!raw.StartsWith("```", StringComparison.Ordinal)) return raw;
    var end = raw.LastIndexOf("```", StringComparison.Ordinal);
    if (end <= 3) return raw;
    raw = raw[3..end].Trim();
    if (raw.StartsWith("json", StringComparison.OrdinalIgnoreCase))
        raw = raw[4..].Trim();
    return raw;
}

static object? ParseHallazgoMejorado(string texto)
{
    var raw = StripJsonFence(texto);
    var start = raw.IndexOf('{');
    var endObj = raw.LastIndexOf('}');
    if (start < 0 || endObj <= start) return null;

    try
    {
        using var doc = JsonDocument.Parse(raw[start..(endObj + 1)]);
        var e = doc.RootElement;
        var hallazgo = e.TryGetProperty("hallazgo", out var h) ? h.GetString() : null;
        if (string.IsNullOrWhiteSpace(hallazgo)) return null;
        var sev = e.TryGetProperty("severidad", out var s) ? s.GetString() : "media";
        var rec = e.TryGetProperty("recomendacion", out var r) ? r.GetString() : null;
        int? plazo = e.TryGetProperty("plazoDias", out var p) && p.TryGetInt32(out var pd) ? pd : 30;
        var norma = e.TryGetProperty("normaRef", out var n) ? n.GetString() : null;
        var item = e.TryGetProperty("itemRgrl", out var ir) ? ir.GetString() : null;
        return new
        {
            severidad = NormalizeSeveridad(sev),
            hallazgo = hallazgo.Trim(),
            recomendacion = string.IsNullOrWhiteSpace(rec) ? null : rec.Trim(),
            plazoDias = plazo,
            normaRef = string.IsNullOrWhiteSpace(norma) ? null : norma.Trim(),
            itemRgrl = string.IsNullOrWhiteSpace(item) ? null : item.Trim(),
            estado = "abierto",
            origen = "sugerido_aceptado",
        };
    }
    catch
    {
        return null;
    }
}

static List<object> ParseHallazgosSugeridos(string texto)
{
    var raw = StripJsonFence(texto);
    var start = raw.IndexOf('[');
    var endArr = raw.LastIndexOf(']');
    if (start < 0 || endArr <= start) return [];

    try
    {
        using var doc = JsonDocument.Parse(raw[start..(endArr + 1)]);
        var list = new List<object>();
        foreach (var e in doc.RootElement.EnumerateArray())
        {
            if (list.Count >= 5) break;
            var hallazgo = e.TryGetProperty("hallazgo", out var h) ? h.GetString() : null;
            if (string.IsNullOrWhiteSpace(hallazgo)) continue;
            var sev = e.TryGetProperty("severidad", out var s) ? s.GetString() : "media";
            var rec = e.TryGetProperty("recomendacion", out var r) ? r.GetString() : null;
            int? plazo = e.TryGetProperty("plazoDias", out var p) && p.TryGetInt32(out var pd) ? pd : null;
            var norma = e.TryGetProperty("normaRef", out var n) ? n.GetString() : null;
            var item = e.TryGetProperty("itemRgrl", out var ir) ? ir.GetString() : null;
            list.Add(new
            {
                severidad = NormalizeSeveridad(sev),
                hallazgo = hallazgo.Trim(),
                recomendacion = string.IsNullOrWhiteSpace(rec) ? null : rec.Trim(),
                plazoDias = plazo,
                normaRef = string.IsNullOrWhiteSpace(norma) ? null : norma.Trim(),
                itemRgrl = string.IsNullOrWhiteSpace(item) ? null : item.Trim(),
                estado = "abierto",
                origen = "sugerido_aceptado",
            });
        }
        return list;
    }
    catch
    {
        return [];
    }
}

static object ToUserDto(Usuario user) => AuthUsersEndpoints.ToUserDtoExt(user);

static object ToAgendaResumen(AgendaItem a) => new
{
    a.Id,
    a.FechaPlanificada,
    horaPlanificada = FormatHoraPlanificada(a.HoraPlanificada),
    a.Estado,
    a.UsuarioId,
    responsable = a.Usuario?.Nombre,
    a.CreadoEn,
    a.ActualizadoEn,
};

static string ResolveEstadoOperativo(
    AgendaItem? agendaProgramada,
    bool tieneVisitaAppReciente,
    EstablecimientoReagenda? reagendaPendiente)
{
    // Agenda activa tiene prioridad.
    if (agendaProgramada is not null)
    {
        if (agendaProgramada.ActualizadoEn > agendaProgramada.CreadoEn.AddSeconds(2))
            return "reprogramada";
        return "programada";
    }
    // Plazo de reagenda pendiente (sin turno aún) → coordinador debe agendar.
    if (reagendaPendiente is not null)
        return "reagendar";
    if (tieneVisitaAppReciente) return "realizada";
    return "pendiente";
}

static object SnapshotAgendaDatos(AgendaItem a) => new
{
    a.FechaPlanificada,
    horaPlanificada = FormatHoraPlanificada(a.HoraPlanificada),
    a.UsuarioId,
    a.Notas,
    a.Estado,
    a.MotivoVisita,
    a.RankingOrigen,
    a.ScoreOrigen,
};

static void AddAgendaEvento(
    AppDbContext db,
    AgendaItem agenda,
    Usuario actor,
    string tipo,
    string? estadoAnterior,
    string? estadoNuevo,
    object datos)
{
    db.AgendaEventos.Add(new AgendaEvento
    {
        AgendaItemId = agenda.Id,
        SnapshotItemId = agenda.SnapshotItemId,
        IdEstablecimiento = agenda.IdEstablecimiento,
        Tipo = tipo,
        ActorUsuarioId = actor.Id,
        ActorNombre = actor.Nombre,
        ActorEmail = actor.Email,
        ActorRol = actor.Rol,
        OcurridoEn = DateTime.UtcNow,
        EstadoAnterior = estadoAnterior,
        EstadoNuevo = estadoNuevo,
        Datos = JsonSerializer.Serialize(datos),
        OperacionId = Guid.NewGuid(),
    });
}

static object ToAgendaEventoDto(AgendaEvento e) => new
{
    e.Id,
    e.AgendaItemId,
    e.SnapshotItemId,
    e.IdEstablecimiento,
    e.Tipo,
    actor = e.ActorUsuarioId is null
        ? null
        : new
        {
            id = e.ActorUsuarioId,
            nombre = e.ActorNombre,
            email = e.ActorEmail,
            rol = e.ActorRol,
        },
    e.OcurridoEn,
    e.EstadoAnterior,
    e.EstadoNuevo,
    datos = string.IsNullOrWhiteSpace(e.Datos) ? null : JsonSerializer.Deserialize<object>(e.Datos),
    e.OperacionId,
    legadoSinActor = e.ActorUsuarioId is null,
};

static object BuildFactoresShap(IEnumerable<RankingItemContribucion>? contribuciones)
{
    var list = (contribuciones ?? Enumerable.Empty<RankingItemContribucion>())
        .OrderBy(c => c.Orden)
        .ToList();
    var maxAbs = list.Count == 0 ? 0.0 : list.Max(c => Math.Abs(c.ShapValue));

    object Map(RankingItemContribucion c) => new
    {
        c.Orden,
        c.Feature,
        c.Tema,
        c.Etiqueta,
        c.ValorObservado,
        c.ShapValue,
        c.Direccion,
        c.Descripcion,
        intensidadRelativa = maxAbs <= 0 ? 0.0 : Math.Round(Math.Abs(c.ShapValue) / maxAbs, 3),
    };

    return new
    {
        disponible = list.Count > 0,
        aumentaron = list.Where(c => c.Direccion == "aumenta").Select(Map).ToList(),
        redujeron = list.Where(c => c.Direccion == "reduce").Select(Map).ToList(),
        todas = list.Select(Map).ToList(),
        advertencia =
            "Las contribuciones SHAP están aportes en la escala interna (margen) del modelo para este caso. " +
            "No representan probabilidad de accidente, causalidad ni un porcentaje del puntaje mostrado. " +
            "La intensidad relativa compara factores dentro del mismo establecimiento.",
    };
}

static object ToAgendaDto(AgendaItem a) => new
{
    a.Id,
    a.UsuarioId,
    responsable = a.Usuario is null
        ? null
        : new { a.Usuario.Id, a.Usuario.Nombre, a.Usuario.Email, a.Usuario.Rol },
    a.IdEstablecimiento,
    a.Periodo,
    a.Horizonte,
    a.FechaPlanificada,
    horaPlanificada = FormatHoraPlanificada(a.HoraPlanificada),
    a.MotivoVisita,
    a.Estado,
    a.SnapshotId,
    a.SnapshotItemId,
    a.RankingOrigen,
    a.ScoreOrigen,
    a.BandaOrigen,
    a.MotivoOrigen,
    a.Notas,
    a.CreadoEn,
    a.ActualizadoEn,
    a.CanceladaEn,
    a.MotivoCancelacion,
    visita = a.Visita is null
        ? null
        : new
        {
            a.Visita.Id,
            a.Visita.FechaHoraReal,
            a.Visita.Tipo,
            a.Visita.Resultado,
            a.Visita.Hallazgos,
            a.Visita.Acciones,
            acta = a.Visita.Acta is null
                ? null
                : new
                {
                    a.Visita.Acta.Id,
                    a.Visita.Acta.ResultadoGlobal,
                    a.Visita.Acta.Revisita,
                    a.Visita.Acta.PlazoRevisitaDias,
                    hallazgosTotal = a.Visita.Acta.Hallazgos?.Count ?? 0,
                    hallazgosAbiertos = a.Visita.Acta.Hallazgos?.Count(h => h.Estado == "abierto") ?? 0,
                },
        },
};

static bool CanAssignAny(Usuario user) =>
    user.Rol is "Admin" or "Coordinador";

static bool CanManageAgenda(Usuario user, AgendaItem agenda) =>
    CanAssignAny(user) || agenda.UsuarioId == user.Id;

/// <summary>Marcar realizada / cancelar: Admin (cualquiera) o Preventor (solo la propia). Coordinador no.</summary>
static bool CanCerrarOCancelarVisita(Usuario user, AgendaItem agenda) =>
    user.Rol == "Admin"
    || (user.Rol == "Preventor" && agenda.UsuarioId == user.Id);

static string InferMotivoVisita(RankingItem item)
{
    var motivo = (item.Motivo ?? "").ToLowerInvariant();
    if (item.ObligacionPrs || motivo.Contains("prs")) return "prs";
    if (motivo.Contains("seguim")) return "seguimiento";
    return "predictivo";
}

static async Task<Usuario?> GetCurrentUserAsync(ClaimsPrincipal principal, AppDbContext db)
{
    var idText = principal.FindFirstValue(JwtRegisteredClaimNames.Sub)
        ?? principal.FindFirstValue(ClaimTypes.NameIdentifier);
    if (!int.TryParse(idText, out var id)) return null;
    return await db.Usuarios.FirstOrDefaultAsync(u => u.Id == id && u.Activo);
}

static List<object> BuildExplicacion(
    RankingItem item,
    double percentile,
    double avgScore,
    double avgVisita)
{
    var bullets = new List<object>();

    bullets.Add(new
    {
        titulo = "Prioridad del modelo",
        detalle = $"Queda en el percentil {percentile} de la lista vigente (puntaje {item.ScoreRiesgo:0.0000} frente al promedio {avgScore:0.0000}). El puntaje ordena la prioridad de visita; no es una probabilidad de accidente.",
        severidad = item.Banda,
    });

    var motivo = (item.Motivo ?? "").ToLowerInvariant();
    var esPredictivo = motivo.Contains("predict");
    var esPrs = motivo.Contains("prs") || item.ObligacionPrs;
    if (esPredictivo)
    {
        bullets.Add(new
        {
            titulo = "Motivo predictivo",
            detalle = "Entra por el modelo ML: el patrón histórico (accidentes, exposición y contexto) lo ubica entre los establecimientos a priorizar en este horizonte.",
            severidad = "critico",
        });
    }
    if (esPrs)
    {
        bullets.Add(new
        {
            titulo = "Obligación regulatoria PRS",
            detalle = "Tiene obligación de Plan de Reducción de Siniestralidad: la visita no es solo predictiva, también responde a un requisito normativo.",
            severidad = "alto",
        });
    }
    if (!esPredictivo && !esPrs && !string.IsNullOrWhiteSpace(item.Motivo))
    {
        bullets.Add(new
        {
            titulo = $"Motivo: {item.Motivo}",
            detalle = "La política de priorización lo incorporó por una regla operativa (regulatoria, cobertura o excepción de capacidad). Los indicadores específicos se detallan debajo.",
            severidad = "alto",
        });
    }

    if (item.AlertaUmbral)
    {
        bullets.Add(new
        {
            titulo = "Alerta de umbral",
            detalle = "Supera el umbral operativo de atención: conviene revisar exposición reciente y cobertura preventiva antes de posponer la visita.",
            severidad = "critico",
        });
    }

    if (item.EnCooldown)
    {
        bullets.Add(new
        {
            titulo = "Visita reciente",
            detalle = "Ya tuvo una visita reciente. Puede permanecer en la lista por criticidad, pero la capacidad suele reasignarse a establecimientos que todavía no fueron visitados.",
            severidad = "medio",
        });
    }
    else if (item.UltimaVisitaHaceMeses is null)
    {
        bullets.Add(new
        {
            titulo = "Sin visita registrada",
            detalle = "No hay visita reciente en el panel. La falta de cobertura preventiva eleva la prioridad operativa.",
            severidad = "alto",
        });
    }
    else if (item.UltimaVisitaHaceMeses >= 6)
    {
        bullets.Add(new
        {
            titulo = "Visita antigua",
            detalle = $"Última visita hace {item.UltimaVisitaHaceMeses:0.#} meses (promedio de la lista: {avgVisita:0.#}). El intervalo sugiere revisar nuevamente.",
            severidad = "alto",
        });
    }

    return bullets;
}

/// <summary>
/// Precisión histórica del holdout 2025 (media por mes) según posición en la lista.
/// Fuente: reports/modelo/evaluation_metrics_{1m|3m}.json → top_k_per_month.
/// </summary>
// Tabla vigente del holdout 2025 (mean_precision_at_k_per_month) por tramo top-K.
static (double Pct, int TopK)? AciertoHistoricoLookup(string horizonte, int ranking)
{
    _ = horizonte;
    var tabla = new (int K, double Precision)[]
    {
        (50, 0.935),
        (100, 0.881),
        (200, 0.807),
        (225, 0.790),
        (300, 0.735),
        (400, 0.681),
        (500, 0.637),
        (675, 0.575),
        (1000, 0.495),
    };

    var fila = tabla.FirstOrDefault(t => ranking <= t.K);
    if (fila.K == 0)
    {
        return null;
    }

    return (Math.Round(fila.Precision * 100, 1), fila.K);
}

static object BuildAciertoHistorico(string horizonte, int ranking)
{
    var lookup = AciertoHistoricoLookup(horizonte, ranking);
    if (lookup is null)
    {
        return new
        {
            disponible = false,
            porcentaje = (double?)null,
            referenciaTopK = (int?)null,
            etiqueta = "Fuera de capacidad operativa",
            detalle =
                $"La posición #{ranking} está fuera del top 1000 evaluado. " +
                "No se reporta acierto histórico comparable; el puntaje sigue sirviendo para orden relativo.",
            holdoutAnio = 2025,
            horizonte,
        };
    }

    var (pct, topK) = lookup.Value;
    var banda = BandaPorAcierto(pct);
    return new
    {
        disponible = true,
        porcentaje = pct,
        referenciaTopK = topK,
        etiqueta = "Acierto histórico",
        detalle =
            $"En la evaluación con datos de 2025 (horizonte trimestral), " +
            $"el {pct:0.#}% de los establecimientos que el modelo ubicó en el mismo tramo de prioridad que este " +
            $"(primeros {topK} del ranking) registró al menos un accidente en el trimestre siguiente. " +
            $"Escala de riesgo por acierto: Crítico ≥80%, Alto ≥60%, Medio ≥30%, Bajo <30% → este caso queda en «{banda}». " +
            "Es una referencia grupal del modelo para ese tramo, no una probabilidad individual de este establecimiento.",
        holdoutAnio = 2025,
        horizonte,
    };
}

// Escala única de banda por acierto histórico (precision@K del tramo).
// Debe mantenerse en sync con BAND_ACCURACY_THRESHOLDS en src/pfi_prediccion/config.py.
static string BandaPorAcierto(double pct)
{
    if (pct >= 80) return "Crítico";
    if (pct >= 60) return "Alto";
    if (pct >= 30) return "Medio";
    return "Bajo";
}

// Arma un prompt ANONIMIZADO (sin hash ni identificadores) para el resumen del preventor.
static string BuildDossierPrompt(string dossierJson, string horizonte, string? banda, int? ranking)
{
    using var doc = JsonDocument.Parse(dossierJson);
    var root = doc.RootElement;
    var sb = new StringBuilder();

    // Los datos van PRIMERO y las instrucciones AL FINAL: los modelos siguen
    // mejor la última instrucción y así evitamos que "razonen en voz alta".
    sb.AppendLine("=== DATOS HISTÓRICOS ANONIMIZADOS DE UN ESTABLECIMIENTO ===");
    sb.Append("Contexto del modelo predictivo: horizonte trimestral (próximos tres meses).");
    if (!string.IsNullOrWhiteSpace(banda)) sb.Append(" Banda de riesgo: ").Append(banda).Append('.');
    if (ranking is not null) sb.Append(" Posición en la priorización: #").Append(ranking).Append('.');
    sb.AppendLine();
    sb.AppendLine();

    if (root.TryGetProperty("accidentes", out var acc) && acc.ValueKind == JsonValueKind.Object)
    {
        sb.AppendLine("ACCIDENTES HISTÓRICOS:");
        if (acc.TryGetProperty("total", out var tot)) sb.Append("- Total período: ").Append(tot.GetRawText());
        if (acc.TryGetProperty("ultimos_12m", out var u12)) sb.Append("; últimos 12 meses: ").Append(u12.GetRawText());
        sb.AppendLine();
        if (acc.TryGetProperty("por_anio", out var anio) && anio.ValueKind == JsonValueKind.Object)
        {
            sb.Append("- Por año:");
            foreach (var p in anio.EnumerateObject()) sb.Append(' ').Append(p.Name).Append(':').Append(p.Value.GetRawText());
            sb.AppendLine();
        }
        AppendTop(sb, acc, "top_forma", "- Formas más frecuentes");
        AppendTop(sb, acc, "top_zona", "- Zonas del cuerpo afectadas");
        AppendTop(sb, acc, "top_naturaleza", "- Naturaleza de la lesión");
        AppendTop(sb, acc, "top_gravedad", "- Gravedad");
        if (acc.TryGetProperty("recientes", out var recientes) && recientes.ValueKind == JsonValueKind.Array)
        {
            sb.AppendLine("- Relatos recientes:");
            foreach (var r in recientes.EnumerateArray())
            {
                var fecha = r.TryGetProperty("fecha", out var f) ? f.GetString() : null;
                var forma = r.TryGetProperty("forma", out var fo) ? fo.GetString() : null;
                var relato = r.TryGetProperty("relato", out var re) ? re.GetString() : null;
                if (string.IsNullOrWhiteSpace(relato)) continue;
                sb.Append("  * [").Append(fecha).Append("] ");
                if (!string.IsNullOrWhiteSpace(forma)) sb.Append(forma).Append(": ");
                sb.AppendLine(relato);
            }
        }
        sb.AppendLine();
    }

    if (root.TryGetProperty("visitas", out var vis) && vis.ValueKind == JsonValueKind.Object)
    {
        sb.Append("VISITAS PREVENTIVAS PREVIAS");
        if (vis.TryGetProperty("total", out var vt)) sb.Append(" (total realizadas: ").Append(vt.GetRawText()).Append(')');
        sb.AppendLine(":");

        // Incumplimientos DISTINTOS agregados sobre todas las visitas, con la
        // frecuencia (en cuántas visitas apareció) y la última fecha registrada.
        if (vis.TryGetProperty("incumplimientos_frecuentes", out var inc) && inc.ValueKind == JsonValueKind.Array &&
            inc.GetArrayLength() > 0)
        {
            sb.AppendLine("- Incumplimientos registrados (todos los distintos; \"n\" = en cuántas visitas apareció, mayor n = más persistente):");
            foreach (var e in inc.EnumerateArray())
            {
                var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
                if (string.IsNullOrWhiteSpace(k)) continue;
                var n = e.TryGetProperty("n", out var nv) ? nv.GetRawText() : null;
                var ultima = e.TryGetProperty("ultima", out var uv) && uv.ValueKind == JsonValueKind.String ? uv.GetString() : null;
                sb.Append("  * ").Append(k);
                if (n is not null) sb.Append(" (n=").Append(n);
                if (!string.IsNullOrWhiteSpace(ultima)) sb.Append(", última ").Append(ultima);
                if (n is not null) sb.Append(')');
                sb.AppendLine();
            }
        }

        if (vis.TryGetProperty("observaciones", out var obs) && obs.ValueKind == JsonValueKind.Array &&
            obs.GetArrayLength() > 0)
        {
            sb.AppendLine("- Observaciones del preventor en visitas previas:");
            foreach (var o in obs.EnumerateArray())
            {
                var texto = o.GetString();
                if (!string.IsNullOrWhiteSpace(texto)) sb.Append("  * ").AppendLine(texto);
            }
        }

        // Respaldo: si no hubiera agregación, usar las notas recientes.
        if ((!vis.TryGetProperty("incumplimientos_frecuentes", out var incChk) || incChk.GetArrayLength() == 0) &&
            vis.TryGetProperty("recientes", out var vr) && vr.ValueKind == JsonValueKind.Array)
        {
            foreach (var r in vr.EnumerateArray())
            {
                var fecha = r.TryGetProperty("fecha", out var f) ? f.GetString() : null;
                var resultado = r.TryGetProperty("resultado", out var re) ? re.GetString() : null;
                var obsTxt = r.TryGetProperty("observaciones", out var o2) ? o2.GetString() : null;
                var incTxt = r.TryGetProperty("incumplimientos", out var i2) ? i2.GetString() : null;
                sb.Append("  * [").Append(fecha).Append("] ");
                if (!string.IsNullOrWhiteSpace(resultado)) sb.Append(resultado).Append(". ");
                if (!string.IsNullOrWhiteSpace(obsTxt)) sb.Append("Obs: ").Append(obsTxt).Append(". ");
                if (!string.IsNullOrWhiteSpace(incTxt)) sb.Append("Incumplimientos: ").Append(incTxt);
                sb.AppendLine();
            }
        }
    }

    sb.AppendLine();
    sb.AppendLine("=== TAREA ===");
    sb.AppendLine(
        "Sos un asistente para un preventor de riesgos del trabajo de una ART (Argentina). " +
        "Con los datos de arriba, redactá una guía accionable para la próxima visita preventiva.");
    sb.AppendLine();
    sb.AppendLine("REGLAS ESTRICTAS DE SALIDA:");
    sb.AppendLine("- Empezá tu respuesta con una línea que diga exactamente: ===GUÍA=== y no escribas absolutamente nada antes de esa línea.");
    sb.AppendLine("- Respondé ÚNICAMENTE la guía final. NO muestres tu razonamiento, NO repitas estas instrucciones ni vuelquen los datos crudos, NO escribas nada en inglés.");
    sb.AppendLine("- Todo en español rioplatense, claro y concreto. No inventes datos que no figuren en el bloque de arriba. No uses el nombre de la empresa (no lo tenés).");
    sb.AppendLine("- ANCLÁ cada punto a la evidencia: cuando cites un foco, indicá entre paréntesis el dato que lo respalda (p. ej. cantidad de accidentes, forma más frecuente, incumplimiento previo).");
    sb.AppendLine("- Ordená los focos por criticidad (frecuencia y gravedad), del más importante al menos.");
    sb.AppendLine("- Para las medidas de control/EPP sugeridas por buenas prácticas (no figuran en los datos), aclaralo con \"sugerencia:\".");
    sb.AppendLine("- Máximo ~260 palabras en total.");
    sb.AppendLine("- Usá EXACTAMENTE este formato (títulos en negrita y viñetas con \"- \"):");
    sb.AppendLine();
    sb.AppendLine("**Resumen ejecutivo**");
    sb.AppendLine("- (una sola frase: banda de riesgo, tendencia y los 2 focos principales)");
    sb.AppendLine();
    sb.AppendLine("**1. Perfil de riesgo**");
    sb.AppendLine("- (2-3 viñetas con números y tendencia temporal si la hay: formas, zonas y naturaleza predominantes)");
    sb.AppendLine();
    sb.AppendLine("**2. Incumplimientos previos a verificar**");
    sb.AppendLine("- (incumplimientos u observaciones de visitas anteriores; marcá los que se repiten como \"recurrente / pendiente de subsanar\". Si no hay datos de visitas, escribí: \"Sin registros de visitas previas.\")");
    sb.AppendLine();
    sb.AppendLine("**3. Focos priorizados para la próxima visita**");
    sb.AppendLine("- Foco (evidencia): acción concreta. EPP/control sugerido cuando aplique.");
    sb.AppendLine("- (2-4 viñetas con este patrón dato→acción)");
    sb.AppendLine();
    sb.AppendLine("**4. Verificar, registrar y documentación a solicitar**");
    sb.AppendLine("- (2-4 viñetas: qué medir/observar, qué preguntar al empleador y qué documentación pedir —capacitaciones, estudios ergonómicos, servicio de Medicina Laboral e HyS—)");

    return sb.ToString();
}

/// <summary>
/// Los modelos Gemma tienden a "pensar en voz alta" antes de la respuesta final.
/// Nos quedamos desde la última aparición del primer título y normalizamos viñetas.
/// </summary>
static string LimpiarResumenIa(string? texto)
{
    if (string.IsNullOrWhiteSpace(texto)) return texto ?? string.Empty;
    var t = texto.Replace("\r\n", "\n").Replace("\r", "\n");

    // El modelo debe abrir la guía con el marcador "===GUÍA===". Tomamos todo lo
    // que sigue a la ÚLTIMA aparición del marcador (así descartamos el razonamiento
    // previo, aunque el modelo lo haya mencionado antes).
    var markerIdx = t.LastIndexOf("===GU", StringComparison.OrdinalIgnoreCase);
    if (markerIdx >= 0)
    {
        var nl = t.IndexOf('\n', markerIdx);
        t = nl >= 0 ? t[(nl + 1)..] : string.Empty;
    }
    else
    {
        // Respaldo: si no está el marcador, cortamos desde el primer título conocido.
        var idx = t.IndexOf("Resumen ejecutivo", StringComparison.OrdinalIgnoreCase);
        if (idx < 0) idx = t.IndexOf("Perfil de riesgo", StringComparison.OrdinalIgnoreCase);
        if (idx >= 0)
        {
            var lineStart = t.LastIndexOf('\n', Math.Min(idx, t.Length - 1)) + 1;
            t = t[lineStart..];
        }
    }
    // Quitar restos del marcador si quedaron pegados.
    t = t.Replace("===GUÍA===", "").Replace("===GUIA===", "");

    var outLines = new List<string>();
    foreach (var raw in t.Split('\n'))
    {
        var line = raw.TrimEnd();
        var trimmed = line.TrimStart();
        if (trimmed.StartsWith("* ") || trimmed.StartsWith("*\t"))
            line = "- " + trimmed[1..].TrimStart();
        else if (trimmed.StartsWith("•"))
            line = "- " + trimmed[1..].TrimStart();
        outLines.Add(line);
    }

    // Colapsar líneas en blanco consecutivas.
    var sb = new StringBuilder();
    var blank = false;
    foreach (var l in outLines)
    {
        if (l.Length == 0)
        {
            if (!blank) sb.AppendLine();
            blank = true;
        }
        else
        {
            sb.AppendLine(l);
            blank = false;
        }
    }
    return sb.ToString().Trim();
}

static void AppendTop(StringBuilder sb, JsonElement acc, string prop, string label)
{
    if (!acc.TryGetProperty(prop, out var arr) || arr.ValueKind != JsonValueKind.Array || arr.GetArrayLength() == 0)
        return;
    sb.Append(label).Append(": ");
    var parts = new List<string>();
    foreach (var e in arr.EnumerateArray())
    {
        var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
        var n = e.TryGetProperty("n", out var nv) ? nv.GetRawText() : null;
        if (!string.IsNullOrWhiteSpace(k)) parts.Add(n is null ? k : $"{k} ({n})");
    }
    sb.AppendLine(string.Join("; ", parts));
}

static double Median(List<double> values)
{
    if (values.Count == 0) return 0;
    values.Sort();
    var mid = values.Count / 2;
    return values.Count % 2 == 0
        ? Math.Round((values[mid - 1] + values[mid]) / 2.0, 4)
        : Math.Round(values[mid], 4);
}

static string NormalizeHorizonte(string? horizonte)
{
    _ = horizonte;
    return "3m";
}

static async Task<RankingSnapshot?> GetVigenteAsync(AppDbContext db, string horizonte) =>
    await db.RankingSnapshots
        .Where(s => s.Horizonte == horizonte && s.EsVigente)
        .OrderByDescending(s => s.Periodo)
        .ThenByDescending(s => s.ImportadoEn)
        .FirstOrDefaultAsync();

static async Task<object> BuildAnaliticaAsync(AppDbContext db, RankingSnapshot snapshot)
{
    var shap50 = await db.SnapshotShapAgregados.AsNoTracking()
        .Where(s => s.SnapshotId == snapshot.Id && s.TopK == 50)
        .OrderBy(s => s.OrdenImportancia)
        .Take(12)
        .Select(s => new
        {
            s.Feature,
            s.Tema,
            s.Etiqueta,
            s.OrdenImportancia,
            s.MeanAbsShap,
            s.MeanShap,
            s.PctAumenta,
            s.ItemsCohorte,
            s.Metodo,
        })
        .ToListAsync();

    var shap225 = await db.SnapshotShapAgregados.AsNoTracking()
        .Where(s => s.SnapshotId == snapshot.Id && s.TopK == 225)
        .OrderBy(s => s.OrdenImportancia)
        .Take(12)
        .Select(s => new
        {
            s.Feature,
            s.Tema,
            s.Etiqueta,
            s.OrdenImportancia,
            s.MeanAbsShap,
            s.MeanShap,
            s.PctAumenta,
            s.ItemsCohorte,
            s.Metodo,
        })
        .ToListAsync();

    var shap1000 = await db.SnapshotShapAgregados.AsNoTracking()
        .Where(s => s.SnapshotId == snapshot.Id && s.TopK == 1000)
        .OrderBy(s => s.OrdenImportancia)
        .Take(12)
        .Select(s => new
        {
            s.Feature,
            s.Tema,
            s.Etiqueta,
            s.OrdenImportancia,
            s.MeanAbsShap,
            s.MeanShap,
            s.PctAumenta,
            s.ItemsCohorte,
            s.Metodo,
        })
        .ToListAsync();

    var coberturas = await (
        from c in db.SnapshotCoberturas.AsNoTracking()
        join s in db.RankingSnapshots.AsNoTracking() on c.SnapshotId equals s.Id
        where s.Horizonte == snapshot.Horizonte && (s.ItemsImportados == null || s.ItemsImportados > 0)
        orderby s.ActivadoEn ?? s.ImportadoEn ?? s.GeneradoEn
        select new
        {
            snapshotId = s.Id,
            periodoDecision = s.Periodo,
            topK = c.TopK,
            ventanaInicio = c.VentanaInicio,
            ventanaFin = c.VentanaFin,
            denominador = c.Denominador,
            cubiertos = c.Cubiertos,
            porcentaje = c.Porcentaje,
            estado = c.Estado,
            activadoEn = s.ActivadoEn ?? s.ImportadoEn,
        }
    ).ToListAsync();

    var precisiones = await (
        from m in db.SnapshotMetricasObservadas.AsNoTracking()
        join s in db.RankingSnapshots.AsNoTracking() on m.SnapshotId equals s.Id
        where s.Horizonte == snapshot.Horizonte
        orderby s.Periodo
        select new
        {
            snapshotId = s.Id,
            periodo = s.Periodo,
            topK = m.TopK,
            estado = m.Estado,
            denominador = m.Denominador,
            positivos = m.Positivos,
            porcentaje = m.Precision == null ? (double?)null : Math.Round(m.Precision.Value * 100, 1),
            ventanaInicio = m.VentanaInicio,
            ventanaFin = m.VentanaFin,
            esHoldoutSeed = s.ModeloVersion == "holdout_metrics",
        }
    ).ToListAsync();

    var cobVigente50 = coberturas.FirstOrDefault(c => c.snapshotId == snapshot.Id && c.topK == 50);
    var cobVigente225 = coberturas.FirstOrDefault(c => c.snapshotId == snapshot.Id && c.topK == 225);
    var cobVigente1000 = coberturas.FirstOrDefault(c => c.snapshotId == snapshot.Id && c.topK == 1000);
    var precVigente50 = precisiones.FirstOrDefault(p => p.snapshotId == snapshot.Id && p.topK == 50);
    var precVigente225 = precisiones.FirstOrDefault(p => p.snapshotId == snapshot.Id && p.topK == 225);
    var precVigente1000 = precisiones.FirstOrDefault(p => p.snapshotId == snapshot.Id && p.topK == 1000);

    return new
    {
        snapshotId = snapshot.Id,
        periodo = snapshot.Periodo,
        horizonte = snapshot.Horizonte,
        datosHasta = snapshot.DatosHasta,
        activadoEn = snapshot.ActivadoEn ?? snapshot.ImportadoEn,
        shapAgregado = new
        {
            disponible = shap50.Count + shap225.Count + shap1000.Count > 0,
            top50 = shap50,
            top225 = shap225,
            top1000 = shap1000,
            advertencia =
                "Importancia media absoluta y aporte firmado calculados sobre la matriz SHAP completa del top-K. " +
                "No es probabilidad, causalidad ni porcentaje del puntaje.",
        },
        coberturaCohorte = new
        {
            top50 = cobVigente50,
            top225 = cobVigente225,
            top1000 = cobVigente1000,
            serieTop50 = coberturas.Where(c => c.topK == 50).ToList(),
            serieTop225 = coberturas.Where(c => c.topK == 225).ToList(),
            serieTop1000 = coberturas.Where(c => c.topK == 1000).ToList(),
            nota =
                "La cobertura mide la cohorte desde la activación del ranking en la app (reloj operativo), " +
                "no el mes del período de datos del modelo.",
        },
        precisionObservada = new
        {
            top50 = precVigente50,
            top225 = precVigente225,
            top1000 = precVigente1000,
            serieTop50 = precisiones.Where(p => p.topK == 50).ToList(),
            serieTop225 = precisiones.Where(p => p.topK == 225).ToList(),
            serieTop1000 = precisiones.Where(p => p.topK == 1000).ToList(),
            holdoutReferenciaTop225Pct = 79.0,
            holdoutReferenciaTop1000Pct = 49.5,
            nota =
                "Precisión observada del período de decisión T con accidentación en el trimestre siguiente (T+1 a T+3). " +
                "Solo madura si la fuente está completa. Los puntos holdout_metrics son evaluación histórica sin cohorte operativa.",
        },
        metodologia = new
        {
            cobertura =
                "Cubierto = establecimiento del top-K con visita programada o realizada en la ventana desde ActivadoEn.",
            precision =
                "Positivo = al menos un accidente en la ventana del horizonte. Pendientes no se cuentan como cero.",
            shap =
                "SHAP agregado = media de contribuciones por feature original sobre todos los ítems del top-K.",
        },
    };
}

static string CreateToken(Usuario user, string key, string issuer)
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

file static class RgrlCatalogCache
{
    public static readonly object Gate = new();
    public static List<RgrlCatalogItem>? Items;
}

record RgrlCatalogItem(string Id, string Label, string? Actividad, string? NormaRef);
record LoginRequest(string Email, string Password);
record UpdateProfileRequest(string Nombre);
record ChangePasswordRequest(string Actual, string Nueva);
record ProgramarVisitaRequest(
    long RankingItemId,
    DateOnly FechaPlanificada,
    string? HoraPlanificada,
    string? Horizonte,
    int? UsuarioId,
    string? Notas);
record ReprogramarVisitaRequest(DateOnly? FechaPlanificada, string? HoraPlanificada, int? UsuarioId, string? Notas);
record ChecklistItemDto(string? Id, string? Label, string? Estado);
record HallazgoActaDto(
    string? Severidad,
    string? Hallazgo,
    string? Recomendacion,
    int? PlazoDias,
    string? NormaRef,
    string? ItemRgrl,
    string? Estado,
    string? Origen);
record RealizarVisitaRequest(
    DateTime? FechaHoraReal,
    string? Hallazgos,
    string? Acciones,
    string? Notas,
    string? ResultadoGlobal,
    bool? Revisita,
    int? PlazoRevisitaDias,
    DateOnly? FechaRevisita,
    string? HoraRevisita,
    string? NotasActa,
    /// <summary>Meses máximos para la próxima visita (1|2|3|6). Null/0 = no requiere reagenda.</summary>
    int? ReagendaMesesPlazo,
    List<ChecklistItemDto>? Checklist,
    List<HallazgoActaDto>? HallazgosActa);
record SugerirActaRequest(
    List<ChecklistItemDto>? Checklist,
    string? Notas,
    List<HallazgoActaDto>? HallazgosPrevios);
record MejorarHallazgoRequest(
    string? Borrador,
    string? Hallazgo,
    string? Recomendacion,
    string? ItemLabel,
    string? Severidad);
record PatchHallazgoRequest(string? Estado);
record CancelarVisitaRequest(string MotivoCancelacion);
