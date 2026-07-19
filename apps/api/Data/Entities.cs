using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace PfiPrevencion.Api.Data;

[Table("Zonas", Schema = "app")]
public class Zona
{
    public int Id { get; set; }
    [MaxLength(120)] public string Nombre { get; set; } = "";
    public bool Activa { get; set; } = true;
}

[Table("Usuarios", Schema = "app")]
public class Usuario
{
    public int Id { get; set; }
    [MaxLength(256)] public string Email { get; set; } = "";
    [MaxLength(200)] public string Nombre { get; set; } = "";
    [MaxLength(500)] public string PasswordHash { get; set; } = "";
    [MaxLength(40)] public string Rol { get; set; } = "Prevencionista";
    public int? ZonaId { get; set; }
    public Zona? Zona { get; set; }
    public bool Activo { get; set; } = true;
    public DateTime CreadoEn { get; set; }
}

[Table("RankingSnapshots", Schema = "app")]
public class RankingSnapshot
{
    public int Id { get; set; }
    [MaxLength(7)] public string Periodo { get; set; } = "";
    [MaxLength(2)] public string Horizonte { get; set; } = "1m";
    public DateTime GeneradoEn { get; set; }
    [MaxLength(400)] public string? ArchivoOrigen { get; set; }
    public int Filas { get; set; }
    public int Criticos { get; set; }
    public int Altos { get; set; }
    public bool EsVigente { get; set; } = true;
    public ICollection<RankingItem> Items { get; set; } = new List<RankingItem>();
}

[Table("RankingItems", Schema = "app")]
public class RankingItem
{
    public long Id { get; set; }
    public int SnapshotId { get; set; }
    public RankingSnapshot? Snapshot { get; set; }
    [MaxLength(64)] public string IdEstablecimiento { get; set; } = "";
    [MaxLength(64)] public string? IdEmpleador { get; set; }
    public int Ranking { get; set; }
    public double ScoreRiesgo { get; set; }
    [MaxLength(20)] public string Banda { get; set; } = "medio";
    [MaxLength(80)] public string? Motivo { get; set; }
    public bool ObligacionPrs { get; set; }
    public bool EnCooldown { get; set; }
    public double? UltimaVisitaHaceMeses { get; set; }
    [MaxLength(120)] public string? Sector { get; set; }
    [MaxLength(10)] public string? CiiuDivision { get; set; }
    public double? CantidadCapitas { get; set; }
    public double? DotacionNominaMes { get; set; }
    public bool AlertaUmbral { get; set; }
    [MaxLength(500)] public string? MotivoPrincipalTexto { get; set; }
}

[Table("AppConfig", Schema = "app")]
public class AppConfigEntry
{
    [Key, MaxLength(80)] public string Clave { get; set; } = "";
    [MaxLength(400)] public string Valor { get; set; } = "";
    public DateTime Actualizado { get; set; }
}
