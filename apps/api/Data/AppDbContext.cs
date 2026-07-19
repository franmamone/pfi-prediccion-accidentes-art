using Microsoft.EntityFrameworkCore;

namespace PfiPrevencion.Api.Data;

public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<Zona> Zonas => Set<Zona>();
    public DbSet<Usuario> Usuarios => Set<Usuario>();
    public DbSet<RankingSnapshot> RankingSnapshots => Set<RankingSnapshot>();
    public DbSet<RankingItem> RankingItems => Set<RankingItem>();
    public DbSet<AppConfigEntry> AppConfig => Set<AppConfigEntry>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Usuario>()
            .HasIndex(u => u.Email)
            .IsUnique();

        modelBuilder.Entity<RankingSnapshot>()
            .HasIndex(s => new { s.Periodo, s.Horizonte })
            .IsUnique();

        modelBuilder.Entity<RankingItem>()
            .HasOne(i => i.Snapshot)
            .WithMany(s => s.Items)
            .HasForeignKey(i => i.SnapshotId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
