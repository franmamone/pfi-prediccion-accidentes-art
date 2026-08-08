using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using PfiPrevencion.Api.Data;

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

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    await SeedAdminAsync(db);
}

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

app.UseCors();
app.UseAuthentication();
app.UseAuthorization();

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

    var token = CreateToken(user, jwtKey, jwtIssuer);
    return Results.Ok(new
    {
        access_token = token,
        token_type = "Bearer",
        user = ToUserDto(user),
    });
});

app.MapGet("/api/me", async (ClaimsPrincipal principal, AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();
    return Results.Ok(ToUserDto(user));
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
    return Results.Ok(ToUserDto(user));
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
    int? top) =>
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

    // Filtro por estado operativo de la grilla (pendiente|programada|reprogramada|realizada).
    // Se aplica en memoria después de enriquecer, salvo realizadas/programadas que se pueden
    // prefiltrar parcialmente para no perder cupo del top.
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
    else if (estadoFiltro == "realizada")
    {
        var realizadasQuery = db.VisitasApp.AsNoTracking()
            .Where(v => v.Resultado == "realizada" && v.FechaHoraReal >= desdeReciente)
            .Select(v => v.IdEstablecimiento);
        query = query.Where(i => realizadasQuery.Contains(i.IdEstablecimiento));
    }
    else if (estadoFiltro == "pendiente")
    {
        var ocupadasQuery = db.AgendaItems.AsNoTracking()
            .Where(a => a.Estado == "programada")
            .Select(a => a.IdEstablecimiento)
            .Concat(
                db.VisitasApp.AsNoTracking()
                    .Where(v => v.Resultado == "realizada" && v.FechaHoraReal >= desdeReciente)
                    .Select(v => v.IdEstablecimiento));
        query = query.Where(i => !ocupadasQuery.Contains(i.IdEstablecimiento));
    }

    // Si hay realizadas recientes, igual queremos verlas en priorización: ampliar el tope
    // un poco cuando se pide el cupo operativo completo.
    var limit = Math.Clamp(top ?? 225, 1, 1000);
    var rows = await query
        .OrderBy(i => i.Ranking)
        .Take(limit)
        .ToListAsync();

    var ids = rows.Select(i => i.IdEstablecimiento).Distinct().ToList();
    var agendasActivas = await db.AgendaItems.AsNoTracking()
        .Include(a => a.Usuario)
        .Where(a => a.Estado == "programada" && ids.Contains(a.IdEstablecimiento))
        .ToListAsync();
    var agendaByEst = agendasActivas
        .GroupBy(a => a.IdEstablecimiento)
        .ToDictionary(g => g.Key, g => g.OrderBy(a => a.FechaPlanificada).First());

    var visitasRecientes = await db.VisitasApp.AsNoTracking()
        .Where(v =>
            v.Resultado == "realizada" &&
            v.FechaHoraReal >= desdeReciente &&
            ids.Contains(v.IdEstablecimiento))
        .Select(v => new { v.IdEstablecimiento, v.FechaHoraReal, v.AgendaItemId })
        .ToListAsync();
    var visitaByEst = visitasRecientes
        .GroupBy(v => v.IdEstablecimiento)
        .ToDictionary(
            g => g.Key,
            g => g.OrderByDescending(x => x.FechaHoraReal).First());

    var items = rows.Select(i =>
    {
        agendaByEst.TryGetValue(i.IdEstablecimiento, out var agenda);
        visitaByEst.TryGetValue(i.IdEstablecimiento, out var visitaApp);
        var enCooldownApp = visitaApp is not null || i.EnCooldown;
        var estado = ResolveEstadoOperativo(agenda, visitaApp is not null);
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
            EnCooldown = enCooldownApp,
            i.UltimaVisitaHaceMeses,
            i.Sector,
            i.CiiuDivision,
            i.CantidadCapitas,
            i.DotacionNominaMes,
            i.AlertaUmbral,
            i.MotivoPrincipalTexto,
            estadoOperativo = estado,
            agendaId = agenda?.Id ?? visitaApp?.AgendaItemId,
            agendaActiva = agenda is null ? null : ToAgendaResumen(agenda),
            visitaAppRecienteEn = visitaApp?.FechaHoraReal,
        };
    }).ToList();

    if (estadoFiltro is "programada" or "reprogramada")
    {
        items = items.Where(x => x.estadoOperativo == estadoFiltro).ToList();
    }

    return Results.Ok(new
    {
        periodo = snapshot.Periodo,
        horizonte = snapshot.Horizonte,
        total = items.Count,
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
            u.Rol == "Prevencionista" || u.Rol == "Coordinador" || u.Rol == "Admin");
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

    var query = db.AgendaItems.AsNoTracking()
        .Include(a => a.Usuario)
        .Include(a => a.Visita)
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
        .ThenBy(a => a.Id)
        .Take(500)
        .ToListAsync();

    return Results.Ok(new
    {
        total = rows.Count,
        items = rows.Select(ToAgendaDto).ToList(),
    });
}).RequireAuthorization();

app.MapPost("/api/agenda", async (
    ProgramarVisitaRequest request,
    ClaimsPrincipal principal,
    AppDbContext db) =>
{
    var user = await GetCurrentUserAsync(principal, db);
    if (user is null) return Results.Unauthorized();

    var horizonte = NormalizeHorizonte(request.Horizonte);
    if (request.RankingItemId <= 0)
    {
        return Results.BadRequest(new { error = "RankingItemId es obligatorio." });
    }

    if (request.FechaPlanificada < DateOnly.FromDateTime(DateTime.Today))
    {
        return Results.BadRequest(new { error = "La fecha planificada debe ser hoy o una fecha futura." });
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
                responsableId = agenda.UsuarioId,
                responsableNombre = assignee.Nombre,
                actorEsResponsable = user.Id == assignee.Id,
                notas = agenda.Notas,
                rankingItemId = rankingItem.Id,
                horizonte,
            });
        await db.SaveChangesAsync();
        await tx.CommitAsync();
    }
    catch (DbUpdateException)
    {
        await tx.RollbackAsync();
        return Results.Conflict(new { error = "Este establecimiento ya tiene una visita programada." });
    }

    await db.Entry(agenda).Reference(a => a.Usuario).LoadAsync();
    return Results.Ok(ToAgendaDto(agenda));
}).RequireAuthorization();

app.MapPut("/api/agenda/{id:int}", async (
    int id,
    ReprogramarVisitaRequest request,
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
        return Results.BadRequest(new { error = "Solo se pueden reprogramar visitas en estado programada." });
    }
    if (!CanManageAgenda(user, agenda))
    {
        return Results.Json(new { error = "No tenés permiso para modificar esta visita." }, statusCode: 403);
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
    if (!CanManageAgenda(user, agenda))
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
        Hallazgos = string.IsNullOrWhiteSpace(request.Hallazgos) ? null : request.Hallazgos.Trim(),
        Acciones = string.IsNullOrWhiteSpace(request.Acciones) ? null : request.Acciones.Trim(),
        CreadoEn = DateTime.UtcNow,
    };

    agenda.Estado = "realizada";
    agenda.ActualizadoEn = DateTime.UtcNow;
    if (!string.IsNullOrWhiteSpace(request.Notas))
    {
        agenda.Notas = request.Notas.Trim();
    }

    db.VisitasApp.Add(visita);
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
            responsableId = agenda.UsuarioId,
            actorEsResponsable = user.Id == agenda.UsuarioId,
        });
    await db.SaveChangesAsync();
    await tx.CommitAsync();

    await db.Entry(agenda).Reference(a => a.Visita).LoadAsync();
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
    if (!CanManageAgenda(user, agenda))
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
        // Prevencionista: ve eventos de agendas propias o donde fue actor.
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

app.Run();

static object ToUserDto(Usuario user) => new
{
    user.Id,
    user.Email,
    user.Nombre,
    user.Rol,
    user.ZonaId,
};

static object ToAgendaResumen(AgendaItem a) => new
{
    a.Id,
    a.FechaPlanificada,
    a.Estado,
    a.UsuarioId,
    responsable = a.Usuario?.Nombre,
    a.CreadoEn,
    a.ActualizadoEn,
};

static string ResolveEstadoOperativo(AgendaItem? agendaProgramada, bool tieneVisitaAppReciente)
{
    // Agenda activa tiene prioridad (puede haber una nueva visita tras una realizada reciente).
    if (agendaProgramada is not null)
    {
        if (agendaProgramada.ActualizadoEn > agendaProgramada.CreadoEn.AddSeconds(2))
            return "reprogramada";
        return "programada";
    }
    if (tieneVisitaAppReciente) return "realizada";
    return "pendiente";
}

static object SnapshotAgendaDatos(AgendaItem a) => new
{
    a.FechaPlanificada,
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
        },
};

static bool CanAssignAny(Usuario user) =>
    user.Rol is "Admin" or "Coordinador";

static bool CanManageAgenda(Usuario user, AgendaItem agenda) =>
    CanAssignAny(user) || agenda.UsuarioId == user.Id;

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
    var tabla = horizonte == "3m"
        ? new (int K, double Precision)[]
        {
            (50, 0.935),
            (100, 0.881),
            (200, 0.807),
            (225, 0.790),
        }
        : new (int K, double Precision)[]
        {
            (50, 0.764),
            (100, 0.671),
            (200, 0.540),
            (225, 0.515),
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
                $"La posición #{ranking} está fuera del top 225 evaluado para capacidad operativa. " +
                "No se reporta acierto histórico comparable; el puntaje sigue sirviendo para orden relativo.",
            holdoutAnio = 2025,
            horizonte,
        };
    }

    var (pct, topK) = lookup.Value;
    return new
    {
        disponible = true,
        porcentaje = pct,
        referenciaTopK = topK,
        etiqueta = $"Acierto histórico top {topK}",
        detalle =
            $"En la evaluación con datos de 2025 (horizonte {(horizonte == "3m" ? "trimestral" : "mensual")}), " +
            $"el {pct:0.#}% de los establecimientos ubicados entre los primeros {topK} del ranking " +
            "registró al menos un accidente en el horizonte. Es una referencia grupal del modelo, " +
            "no una probabilidad individual de este establecimiento.",
        holdoutAnio = 2025,
        horizonte,
    };
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

static string NormalizeHorizonte(string? horizonte) =>
    horizonte is "3m" or "1m" ? horizonte : "1m";

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
    var precVigente50 = precisiones.FirstOrDefault(p => p.snapshotId == snapshot.Id && p.topK == 50);
    var precVigente225 = precisiones.FirstOrDefault(p => p.snapshotId == snapshot.Id && p.topK == 225);

    return new
    {
        snapshotId = snapshot.Id,
        periodo = snapshot.Periodo,
        horizonte = snapshot.Horizonte,
        datosHasta = snapshot.DatosHasta,
        activadoEn = snapshot.ActivadoEn ?? snapshot.ImportadoEn,
        shapAgregado = new
        {
            disponible = shap50.Count + shap225.Count > 0,
            top50 = shap50,
            top225 = shap225,
            advertencia =
                "Importancia media absoluta y aporte firmado calculados sobre la matriz SHAP completa del top-K. " +
                "No es probabilidad, causalidad ni porcentaje del puntaje.",
        },
        coberturaCohorte = new
        {
            top50 = cobVigente50,
            top225 = cobVigente225,
            serieTop50 = coberturas.Where(c => c.topK == 50).ToList(),
            serieTop225 = coberturas.Where(c => c.topK == 225).ToList(),
            nota =
                "La cobertura mide la cohorte desde la activación del ranking en la app (reloj operativo), " +
                "no el mes del período de datos del modelo.",
        },
        precisionObservada = new
        {
            top50 = precVigente50,
            top225 = precVigente225,
            serieTop50 = precisiones.Where(p => p.topK == 50).ToList(),
            serieTop225 = precisiones.Where(p => p.topK == 225).ToList(),
            holdoutReferenciaTop225Pct = snapshot.Horizonte == "3m" ? 79.0 : 51.5,
            nota =
                "Precisión observada del período de decisión T con outcome en T+1 (1m) o T+1..T+3 (3m). " +
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

static async Task SeedAdminAsync(AppDbContext db)
{
    var zonaId = await db.Zonas.Select(z => (int?)z.Id).FirstOrDefaultAsync();

    var admin = await db.Usuarios.FirstOrDefaultAsync(u => u.Email == "admin@pfi.local");
    if (admin is not null &&
        (admin.PasswordHash is "PENDING_SEED" or "" ||
         !admin.PasswordHash.StartsWith("$2", StringComparison.Ordinal)))
    {
        admin.PasswordHash = BCrypt.Net.BCrypt.HashPassword("Admin123!");
    }

    var prev = await db.Usuarios.FirstOrDefaultAsync(u => u.Email == "prevencionista@pfi.local");
    if (prev is null)
    {
        db.Usuarios.Add(new Usuario
        {
            Email = "prevencionista@pfi.local",
            Nombre = "Prevencionista Demo",
            PasswordHash = BCrypt.Net.BCrypt.HashPassword("Prev123!"),
            Rol = "Prevencionista",
            ZonaId = zonaId,
            Activo = true,
            CreadoEn = DateTime.UtcNow,
        });
    }

    await db.SaveChangesAsync();
}

record LoginRequest(string Email, string Password);
record UpdateProfileRequest(string Nombre);
record ChangePasswordRequest(string Actual, string Nueva);
record ProgramarVisitaRequest(
    long RankingItemId,
    DateOnly FechaPlanificada,
    string? Horizonte,
    int? UsuarioId,
    string? Notas);
record ReprogramarVisitaRequest(DateOnly? FechaPlanificada, int? UsuarioId, string? Notas);
record RealizarVisitaRequest(DateTime? FechaHoraReal, string? Hallazgos, string? Acciones, string? Notas);
record CancelarVisitaRequest(string MotivoCancelacion);
