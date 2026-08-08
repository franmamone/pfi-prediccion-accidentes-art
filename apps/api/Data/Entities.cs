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
    [MaxLength(80)] public string? ModeloVersion { get; set; }
    [MaxLength(64)] public string? ArtifactHash { get; set; }
    [MaxLength(7)] public string? DatosHasta { get; set; }
    public DateTime? ImportadoEn { get; set; }
    public DateTime? ActivadoEn { get; set; }
    public int? UniversoFilas { get; set; }
    public int? ItemsImportados { get; set; }
    public ICollection<RankingItem> Items { get; set; } = new List<RankingItem>();
    public ICollection<SnapshotShapAgregado> ShapAgregados { get; set; } = new List<SnapshotShapAgregado>();
    public ICollection<SnapshotMetricaObservada> MetricasObservadas { get; set; } = new List<SnapshotMetricaObservada>();
    public ICollection<SnapshotCobertura> Coberturas { get; set; } = new List<SnapshotCobertura>();
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
    public ICollection<RankingItemContribucion> Contribuciones { get; set; } = new List<RankingItemContribucion>();
    public RankingItemOutcome? Outcome { get; set; }
}

[Table("RankingItemContribuciones", Schema = "app")]
public class RankingItemContribucion
{
    public long Id { get; set; }
    public long RankingItemId { get; set; }
    public RankingItem? RankingItem { get; set; }
    public byte Orden { get; set; }
    [MaxLength(120)] public string Feature { get; set; } = "";
    [MaxLength(80)] public string? Tema { get; set; }
    [MaxLength(200)] public string Etiqueta { get; set; } = "";
    [MaxLength(200)] public string? ValorObservado { get; set; }
    public double ShapValue { get; set; }
    [MaxLength(20)] public string Direccion { get; set; } = "aumenta";
    [MaxLength(500)] public string? Descripcion { get; set; }
}

[Table("SnapshotShapAgregados", Schema = "app")]
public class SnapshotShapAgregado
{
    public long Id { get; set; }
    public int SnapshotId { get; set; }
    public RankingSnapshot? Snapshot { get; set; }
    public int TopK { get; set; }
    [MaxLength(120)] public string Feature { get; set; } = "";
    [MaxLength(80)] public string? Tema { get; set; }
    [MaxLength(200)] public string Etiqueta { get; set; } = "";
    public int OrdenImportancia { get; set; }
    public int ItemsCohorte { get; set; }
    public double MeanAbsShap { get; set; }
    public double MeanShap { get; set; }
    public double? P50AbsShap { get; set; }
    public double? P90AbsShap { get; set; }
    public double PctAumenta { get; set; }
    [MaxLength(60)] public string Metodo { get; set; } = "matriz_completa";
    public DateTime GeneradoEn { get; set; }
}

[Table("RankingItemOutcomes", Schema = "app")]
public class RankingItemOutcome
{
    public long Id { get; set; }
    public long RankingItemId { get; set; }
    public RankingItem? RankingItem { get; set; }
    public int SnapshotId { get; set; }
    [MaxLength(7)] public string PeriodoDecision { get; set; } = "";
    [MaxLength(2)] public string Horizonte { get; set; } = "1m";
    [MaxLength(7)] public string VentanaInicio { get; set; } = "";
    [MaxLength(7)] public string VentanaFin { get; set; } = "";
    [MaxLength(20)] public string Estado { get; set; } = "pendiente";
    public int? CantidadAccidentes { get; set; }
    public bool? OutcomeBinario { get; set; }
    [MaxLength(7)] public string? FuenteCompletaHasta { get; set; }
    public DateTime? EvaluadoEn { get; set; }
}

[Table("SnapshotMetricasObservadas", Schema = "app")]
public class SnapshotMetricaObservada
{
    public int Id { get; set; }
    public int SnapshotId { get; set; }
    public RankingSnapshot? Snapshot { get; set; }
    public int TopK { get; set; }
    [MaxLength(20)] public string Estado { get; set; } = "pendiente";
    public int Denominador { get; set; }
    public int? Positivos { get; set; }
    public double? Precision { get; set; }
    [MaxLength(7)] public string VentanaInicio { get; set; } = "";
    [MaxLength(7)] public string VentanaFin { get; set; } = "";
    [MaxLength(7)] public string? FuenteCompletaHasta { get; set; }
    public DateTime CalculadoEn { get; set; }
}

[Table("SnapshotCoberturas", Schema = "app")]
public class SnapshotCobertura
{
    public int Id { get; set; }
    public int SnapshotId { get; set; }
    public RankingSnapshot? Snapshot { get; set; }
    public int TopK { get; set; }
    public DateOnly VentanaInicio { get; set; }
    public DateOnly VentanaFin { get; set; }
    public int Denominador { get; set; }
    public int Programados { get; set; }
    public int Realizados { get; set; }
    public int Cubiertos { get; set; }
    public double Porcentaje { get; set; }
    [MaxLength(20)] public string Estado { get; set; } = "abierta";
    public DateTime? CorteEn { get; set; }
    public DateTime CalculadoEn { get; set; }
}

[Table("AppConfig", Schema = "app")]
public class AppConfigEntry
{
    [Key, MaxLength(80)] public string Clave { get; set; } = "";
    [MaxLength(400)] public string Valor { get; set; } = "";
    public DateTime Actualizado { get; set; }
}

[Table("AgendaItems", Schema = "app")]
public class AgendaItem
{
    public int Id { get; set; }
    public int UsuarioId { get; set; }
    public Usuario? Usuario { get; set; }
    [MaxLength(64)] public string IdEstablecimiento { get; set; } = "";
    [MaxLength(7)] public string Periodo { get; set; } = "";
    [MaxLength(2)] public string Horizonte { get; set; } = "1m";
    public DateOnly FechaPlanificada { get; set; }
    [MaxLength(40)] public string MotivoVisita { get; set; } = "predictivo";
    [MaxLength(30)] public string Estado { get; set; } = "programada";
    public int? SnapshotId { get; set; }
    public RankingSnapshot? Snapshot { get; set; }
    public long? SnapshotItemId { get; set; }
    public RankingItem? SnapshotItem { get; set; }
    public int? RankingOrigen { get; set; }
    public double? ScoreOrigen { get; set; }
    [MaxLength(20)] public string? BandaOrigen { get; set; }
    [MaxLength(80)] public string? MotivoOrigen { get; set; }
    [MaxLength(1000)] public string? Notas { get; set; }
    public DateTime CreadoEn { get; set; }
    public DateTime ActualizadoEn { get; set; }
    public DateTime? CanceladaEn { get; set; }
    [MaxLength(400)] public string? MotivoCancelacion { get; set; }
    [Timestamp] public byte[] RowVersion { get; set; } = Array.Empty<byte>();
    public VisitaApp? Visita { get; set; }
    public ICollection<AgendaEvento> Eventos { get; set; } = new List<AgendaEvento>();
}

[Table("AgendaEventos", Schema = "app")]
public class AgendaEvento
{
    public long Id { get; set; }
    public int AgendaItemId { get; set; }
    public AgendaItem? AgendaItem { get; set; }
    public long? SnapshotItemId { get; set; }
    [MaxLength(64)] public string IdEstablecimiento { get; set; } = "";
    [MaxLength(30)] public string Tipo { get; set; } = "";
    public int? ActorUsuarioId { get; set; }
    public Usuario? Actor { get; set; }
    [MaxLength(200)] public string? ActorNombre { get; set; }
    [MaxLength(256)] public string? ActorEmail { get; set; }
    [MaxLength(40)] public string? ActorRol { get; set; }
    public DateTime OcurridoEn { get; set; }
    [MaxLength(30)] public string? EstadoAnterior { get; set; }
    [MaxLength(30)] public string? EstadoNuevo { get; set; }
    public string? Datos { get; set; }
    public Guid OperacionId { get; set; }
}

[Table("EstablecimientoDossier", Schema = "app")]
public class EstablecimientoDossier
{
    [Key, MaxLength(64)] public string IdEstablecimiento { get; set; } = "";
    [MaxLength(10)] public string? Referencia { get; set; }
    [MaxLength(200)] public string? Fuente { get; set; }
    public int? AccidentesTotal { get; set; }
    public int? AccidentesUlt12m { get; set; }
    public int? VisitasTotal { get; set; }
    public string DossierJson { get; set; } = "";
    public DateTime GeneradoEn { get; set; }
}

[Table("ResumenIaEstablecimiento", Schema = "app")]
public class ResumenIaEstablecimiento
{
    public int Id { get; set; }
    [MaxLength(64)] public string IdEstablecimiento { get; set; } = "";
    [MaxLength(2)] public string Horizonte { get; set; } = "1m";
    [MaxLength(80)] public string Modelo { get; set; } = "";
    [MaxLength(64)] public string? PromptHash { get; set; }
    public string Resumen { get; set; } = "";
    public int? TokensPrompt { get; set; }
    public int? TokensSalida { get; set; }
    public DateTime GeneradoEn { get; set; }
}

[Table("VisitasApp", Schema = "app")]
public class VisitaApp
{
    public int Id { get; set; }
    [MaxLength(64)] public string IdEstablecimiento { get; set; } = "";
    public int UsuarioId { get; set; }
    public Usuario? Usuario { get; set; }
    public int? AgendaItemId { get; set; }
    public AgendaItem? AgendaItem { get; set; }
    public DateTime FechaHoraReal { get; set; }
    [MaxLength(40)] public string Tipo { get; set; } = "predictiva";
    [MaxLength(30)] public string Resultado { get; set; } = "realizada";
    [MaxLength(200)] public string? MotivoNoRealizada { get; set; }
    public string? Hallazgos { get; set; }
    public string? Acciones { get; set; }
    public DateTime CreadoEn { get; set; }
}
