using Microsoft.EntityFrameworkCore;

namespace PfiPrevencion.Api.Data;

public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<Zona> Zonas => Set<Zona>();
    public DbSet<Usuario> Usuarios => Set<Usuario>();
    public DbSet<UsuarioDisponibilidad> UsuarioDisponibilidades => Set<UsuarioDisponibilidad>();
    public DbSet<AuthToken> AuthTokens => Set<AuthToken>();
    public DbSet<EstablecimientoUbicacion> EstablecimientoUbicaciones => Set<EstablecimientoUbicacion>();
    public DbSet<RankingSnapshot> RankingSnapshots => Set<RankingSnapshot>();
    public DbSet<RankingItem> RankingItems => Set<RankingItem>();
    public DbSet<RankingItemContribucion> RankingItemContribuciones => Set<RankingItemContribucion>();
    public DbSet<SnapshotShapAgregado> SnapshotShapAgregados => Set<SnapshotShapAgregado>();
    public DbSet<RankingItemOutcome> RankingItemOutcomes => Set<RankingItemOutcome>();
    public DbSet<SnapshotMetricaObservada> SnapshotMetricasObservadas => Set<SnapshotMetricaObservada>();
    public DbSet<SnapshotCobertura> SnapshotCoberturas => Set<SnapshotCobertura>();
    public DbSet<AppConfigEntry> AppConfig => Set<AppConfigEntry>();
    public DbSet<AgendaItem> AgendaItems => Set<AgendaItem>();
    public DbSet<VisitaApp> VisitasApp => Set<VisitaApp>();
    public DbSet<VisitaActa> VisitasActa => Set<VisitaActa>();
    public DbSet<VisitaHallazgo> VisitasHallazgos => Set<VisitaHallazgo>();
    public DbSet<EstablecimientoReagenda> EstablecimientoReagendas => Set<EstablecimientoReagenda>();
    public DbSet<AgendaEvento> AgendaEventos => Set<AgendaEvento>();
    public DbSet<EstablecimientoDossier> EstablecimientoDossiers => Set<EstablecimientoDossier>();
    public DbSet<ResumenIaEstablecimiento> ResumenesIaEstablecimiento => Set<ResumenIaEstablecimiento>();
    public DbSet<NormativaChunk> NormativaChunks => Set<NormativaChunk>();
    public DbSet<CopilotoRespuestaCache> CopilotoRespuestasCache => Set<CopilotoRespuestaCache>();
    public DbSet<CopilotoGuardado> CopilotoGuardados => Set<CopilotoGuardado>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Usuario>()
            .HasIndex(u => u.Email)
            .IsUnique();

        modelBuilder.Entity<UsuarioDisponibilidad>()
            .HasOne(d => d.Usuario)
            .WithMany(u => u.Disponibilidades)
            .HasForeignKey(d => d.UsuarioId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<AuthToken>()
            .HasOne(t => t.Usuario)
            .WithMany()
            .HasForeignKey(t => t.UsuarioId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<AuthToken>()
            .HasIndex(t => t.TokenHash)
            .IsUnique();

        modelBuilder.Entity<EstablecimientoUbicacion>()
            .HasKey(e => e.IdEstablecimiento);

        modelBuilder.Entity<RankingSnapshot>()
            .HasIndex(s => new { s.Periodo, s.Horizonte, s.ArtifactHash });

        modelBuilder.Entity<RankingItem>()
            .HasOne(i => i.Snapshot)
            .WithMany(s => s.Items)
            .HasForeignKey(i => i.SnapshotId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<RankingItem>()
            .HasIndex(i => new { i.SnapshotId, i.IdEstablecimiento })
            .IsUnique();

        modelBuilder.Entity<RankingItem>()
            .HasIndex(i => new { i.SnapshotId, i.Ranking })
            .IsUnique();

        modelBuilder.Entity<RankingItemContribucion>()
            .HasOne(c => c.RankingItem)
            .WithMany(i => i.Contribuciones)
            .HasForeignKey(c => c.RankingItemId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<RankingItemContribucion>()
            .HasIndex(c => new { c.RankingItemId, c.Orden })
            .IsUnique();

        modelBuilder.Entity<SnapshotShapAgregado>()
            .HasOne(s => s.Snapshot)
            .WithMany(s => s.ShapAgregados)
            .HasForeignKey(s => s.SnapshotId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<SnapshotShapAgregado>()
            .HasIndex(s => new { s.SnapshotId, s.TopK, s.Feature })
            .IsUnique();

        modelBuilder.Entity<RankingItemOutcome>()
            .HasOne(o => o.RankingItem)
            .WithOne(i => i.Outcome)
            .HasForeignKey<RankingItemOutcome>(o => o.RankingItemId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<RankingItemOutcome>()
            .HasIndex(o => o.RankingItemId)
            .IsUnique();

        modelBuilder.Entity<SnapshotMetricaObservada>()
            .HasOne(m => m.Snapshot)
            .WithMany(s => s.MetricasObservadas)
            .HasForeignKey(m => m.SnapshotId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<SnapshotMetricaObservada>()
            .HasIndex(m => new { m.SnapshotId, m.TopK })
            .IsUnique();

        modelBuilder.Entity<SnapshotCobertura>()
            .HasOne(c => c.Snapshot)
            .WithMany(s => s.Coberturas)
            .HasForeignKey(c => c.SnapshotId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<SnapshotCobertura>()
            .HasIndex(c => new { c.SnapshotId, c.TopK })
            .IsUnique();

        modelBuilder.Entity<AgendaItem>()
            .HasOne(a => a.Usuario)
            .WithMany()
            .HasForeignKey(a => a.UsuarioId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<AgendaItem>()
            .HasOne(a => a.Snapshot)
            .WithMany()
            .HasForeignKey(a => a.SnapshotId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<AgendaItem>()
            .HasOne(a => a.SnapshotItem)
            .WithMany()
            .HasForeignKey(a => a.SnapshotItemId)
            .OnDelete(DeleteBehavior.SetNull);

        modelBuilder.Entity<AgendaItem>()
            .Property(a => a.RowVersion)
            .IsRowVersion();

        modelBuilder.Entity<VisitaApp>()
            .HasOne(v => v.Usuario)
            .WithMany()
            .HasForeignKey(v => v.UsuarioId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<VisitaApp>()
            .HasOne(v => v.AgendaItem)
            .WithOne(a => a.Visita)
            .HasForeignKey<VisitaApp>(v => v.AgendaItemId)
            .OnDelete(DeleteBehavior.SetNull);

        modelBuilder.Entity<VisitaActa>()
            .HasOne(a => a.VisitaApp)
            .WithOne(v => v.Acta)
            .HasForeignKey<VisitaActa>(a => a.VisitaAppId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<VisitaActa>()
            .HasIndex(a => a.VisitaAppId)
            .IsUnique();

        modelBuilder.Entity<VisitaHallazgo>()
            .HasOne(h => h.Acta)
            .WithMany(a => a.Hallazgos)
            .HasForeignKey(h => h.ActaId)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<VisitaHallazgo>()
            .HasIndex(h => new { h.IdEstablecimiento, h.Estado, h.CreadoEn });

        modelBuilder.Entity<AgendaEvento>()
            .HasOne(e => e.AgendaItem)
            .WithMany(a => a.Eventos)
            .HasForeignKey(e => e.AgendaItemId)
            .OnDelete(DeleteBehavior.Restrict);

        modelBuilder.Entity<AgendaEvento>()
            .HasOne(e => e.Actor)
            .WithMany()
            .HasForeignKey(e => e.ActorUsuarioId)
            .OnDelete(DeleteBehavior.SetNull);

        modelBuilder.Entity<AgendaEvento>()
            .HasIndex(e => e.OperacionId)
            .IsUnique();

        modelBuilder.Entity<ResumenIaEstablecimiento>()
            .HasIndex(r => new { r.IdEstablecimiento, r.Horizonte })
            .IsUnique();

        modelBuilder.Entity<CopilotoRespuestaCache>()
            .HasIndex(c => new { c.IdEstablecimiento, c.Seccion })
            .IsUnique();

        modelBuilder.Entity<CopilotoGuardado>()
            .HasIndex(g => new { g.UsuarioId, g.IdEstablecimiento, g.GuardadoEn });
    }
}
