using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
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
        user = new { user.Id, user.Email, user.Nombre, user.Rol, user.ZonaId },
    });
});

app.MapGet("/api/resumen", async (AppDbContext db, string? horizonte) =>
{
    horizonte = NormalizeHorizonte(horizonte);
    var snapshot = await GetVigenteAsync(db, horizonte);
    if (snapshot is null)
    {
        return Results.NotFound(new { error = $"No hay snapshot vigente para {horizonte}" });
    }

    var items = db.RankingItems.Where(i => i.SnapshotId == snapshot.Id);
    var criticos = await items.CountAsync(i => i.Banda == "critico");
    var altos = await items.CountAsync(i => i.Banda == "alto");
    var cooldown = await items.CountAsync(i => i.EnCooldown);
    var prs = await items.CountAsync(i => i.ObligacionPrs);

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
        nota = "Score = prioridad relativa, no probabilidad calibrada.",
    });
}).RequireAuthorization();

app.MapGet("/api/riesgo", async (
    AppDbContext db,
    string? horizonte,
    string? periodo,
    string? banda,
    string? sector,
    string? q,
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
    if (!string.IsNullOrWhiteSpace(q))
    {
        var term = q.Trim().ToUpperInvariant();
        query = query.Where(i =>
            i.IdEstablecimiento.Contains(term) ||
            (i.IdEmpleador != null && i.IdEmpleador.Contains(term)));
    }

    var limit = Math.Clamp(top ?? 225, 1, 1000);
    var rows = await query
        .OrderBy(i => i.Ranking)
        .Take(limit)
        .Select(i => new
        {
            i.Id,
            i.IdEstablecimiento,
            i.IdEmpleador,
            i.Ranking,
            i.ScoreRiesgo,
            i.Banda,
            i.Motivo,
            i.ObligacionPrs,
            i.EnCooldown,
            i.UltimaVisitaHaceMeses,
            i.Sector,
            i.CiiuDivision,
            i.CantidadCapitas,
            i.DotacionNominaMes,
            i.AlertaUmbral,
            i.MotivoPrincipalTexto,
        })
        .ToListAsync();

    return Results.Ok(new
    {
        periodo = snapshot.Periodo,
        horizonte = snapshot.Horizonte,
        total = rows.Count,
        items = rows,
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
        .FirstOrDefaultAsync(i => i.SnapshotId == snapshot.Id && i.IdEstablecimiento == id);
    if (item is null)
    {
        return Results.NotFound(new { error = "Establecimiento no encontrado en ranking vigente" });
    }

    return Results.Ok(item);
}).RequireAuthorization();

app.Run();

static string NormalizeHorizonte(string? horizonte) =>
    horizonte is "3m" or "1m" ? horizonte : "1m";

static async Task<RankingSnapshot?> GetVigenteAsync(AppDbContext db, string horizonte) =>
    await db.RankingSnapshots
        .Where(s => s.Horizonte == horizonte && s.EsVigente)
        .OrderByDescending(s => s.Periodo)
        .FirstOrDefaultAsync();

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
    var admin = await db.Usuarios.FirstOrDefaultAsync(u => u.Email == "admin@pfi.local");
    if (admin is null)
    {
        return;
    }

    if (admin.PasswordHash is "PENDING_SEED" or "" ||
        !admin.PasswordHash.StartsWith("$2", StringComparison.Ordinal))
    {
        admin.PasswordHash = BCrypt.Net.BCrypt.HashPassword("Admin123!");
        await db.SaveChangesAsync();
    }
}

record LoginRequest(string Email, string Password);
