using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.Extensions.Hosting;
using PfiPrevencion.Api.Data;
using PfiPrevencion.Api.Services;
using PfiPrevencion.Api.Tests.Fakes;

namespace PfiPrevencion.Api.Tests;

public sealed class ApiFactory : WebApplicationFactory<Program>
{
    private readonly string _dbName = $"PfiPrevencion_Test_{Guid.NewGuid():N}";

    public FakeEmailSender Email { get; } = new();
    public FakeGeminiClient Gemini { get; } = new();

    public string ConnectionString =>
        $"Server=(localdb)\\mssqllocaldb;Database={_dbName};Trusted_Connection=True;TrustServerCertificate=True;Encrypt=False";

    protected override IHost CreateHost(IHostBuilder builder)
    {
        // Crear BD antes del startup (Ensure*Async en Program).
        var opts = new DbContextOptionsBuilder<AppDbContext>()
            .UseSqlServer(ConnectionString)
            .Options;
        using (var db = new AppDbContext(opts))
        {
            db.Database.EnsureCreated();
        }

        return base.CreateHost(builder);
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Development");
        builder.UseSetting("ConnectionStrings:PfiPrevencion", ConnectionString);
        builder.UseSetting("Jwt:Key", "PfiPrevencionTestKey_ChangeMe_32chars!!");
        builder.UseSetting("Jwt:Issuer", "PfiPrevencionTest");
        builder.UseSetting("Gemini:ApiKey", "");
        builder.UseSetting("App:PublicBaseUrl", "http://localhost:5173");

        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IEmailSender>();
            services.AddSingleton<IEmailSender>(Email);

            services.RemoveAll<IGeminiClient>();
            services.AddSingleton<IGeminiClient>(Gemini);

            services.RemoveAll<DbContextOptions<AppDbContext>>();
            services.RemoveAll<AppDbContext>();
            services.AddDbContext<AppDbContext>(opt => opt.UseSqlServer(ConnectionString));
        });
    }

    public async Task ResetAndSeedAsync()
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        await db.Database.EnsureCreatedAsync();

        // Limpieza sin dropear la BD (evita conexiones huérfanas del pool).
        db.CopilotoGuardados.RemoveRange(db.CopilotoGuardados);
        db.CopilotoRespuestasCache.RemoveRange(db.CopilotoRespuestasCache);
        db.NormativaChunks.RemoveRange(db.NormativaChunks);
        db.EstablecimientoDossiers.RemoveRange(db.EstablecimientoDossiers);
        db.EstablecimientoUbicaciones.RemoveRange(db.EstablecimientoUbicaciones);
        db.RankingItems.RemoveRange(db.RankingItems);
        db.RankingSnapshots.RemoveRange(db.RankingSnapshots);
        db.AuthTokens.RemoveRange(db.AuthTokens);
        db.Usuarios.RemoveRange(db.Usuarios);
        await db.SaveChangesAsync();

        var hash = BCrypt.Net.BCrypt.HashPassword("Test1234!");
        var now = DateTime.UtcNow;
        db.Usuarios.AddRange(
            new Usuario
            {
                Email = "admin@test.local",
                Nombre = "Admin Test",
                Rol = "Admin",
                PasswordHash = hash,
                Activo = true,
                CreadoEn = now,
                Latitud = -34.60,
                Longitud = -58.38,
            },
            new Usuario
            {
                Email = "prev@test.local",
                Nombre = "Preventor Test",
                Rol = "Preventor",
                PasswordHash = hash,
                Activo = true,
                CreadoEn = now,
                Latitud = -34.61,
                Longitud = -58.40,
            },
            new Usuario
            {
                Email = "coord@test.local",
                Nombre = "Coord Test",
                Rol = "Coordinador",
                PasswordHash = hash,
                Activo = true,
                CreadoEn = now,
            });

        var snap = new RankingSnapshot
        {
            Periodo = "2025-01",
            Horizonte = "3m",
            EsVigente = true,
            GeneradoEn = now,
            ArtifactHash = "testhash",
            Filas = 1,
            Criticos = 1,
            Altos = 0,
        };
        db.RankingSnapshots.Add(snap);
        await db.SaveChangesAsync();

        db.RankingItems.Add(new RankingItem
        {
            SnapshotId = snap.Id,
            IdEstablecimiento = "EST-TEST-001",
            Ranking = 1,
            ScoreRiesgo = 0.91,
            Banda = "critico",
            Sector = "Construcción",
            CantidadCapitas = 40,
            Motivo = "Historial alto",
        });
        db.EstablecimientoUbicaciones.Add(new EstablecimientoUbicacion
        {
            IdEstablecimiento = "EST-TEST-001",
            Latitud = -34.6037,
            Longitud = -58.3816,
            ActualizadoEn = now,
        });
        db.EstablecimientoDossiers.Add(new EstablecimientoDossier
        {
            IdEstablecimiento = "EST-TEST-001",
            DossierJson = """{"accidentes":{"total":3},"visitas":[]}""",
            GeneradoEn = now,
            AccidentesTotal = 3,
        });
        db.NormativaChunks.Add(new NormativaChunk
        {
            SourceId = "rgrl-1",
            NormaRef = "Res. SRT 463/2009",
            Titulo = "RGRL",
            Tema = "rgrl_checklist",
            Texto = "Orden y limpieza de puestos de trabajo. Pasillos libres.",
            Orden = 1,
            Activo = true,
            CreadoEn = now,
        });
        await db.SaveChangesAsync();
    }
}
