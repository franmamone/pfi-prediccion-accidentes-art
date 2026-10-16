using PfiPrevencion.Api.Services;

namespace PfiPrevencion.Api.Tests;

public class DossierLlmContextBuilderTests
{
    private const string SampleDossier = """
        {
          "accidentes": {
            "total": 10,
            "ultimos_12m": 3,
            "por_anio": { "2024": 4, "2025": 3 },
            "top_forma": [ { "k": "Caída", "n": 5 } ],
            "top_zona": [ { "k": "Mano", "n": 2 } ],
            "recientes": [
              {
                "fecha": "2025-01-01",
                "forma": "Caída",
                "relato": "Juan Pérez en Av. Corrientes 1234 CUIT 30-71234567-8"
              }
            ]
          },
          "visitas": {
            "total": 4,
            "incumplimientos_frecuentes": [
              { "k": "Orden y Limpieza", "n": 3, "ultima": "2025-02-01" },
              { "k": "Observar domicilio Calle Falsa 99 del operario", "n": 1, "ultima": "2025-01-01" }
            ],
            "observaciones": [ "Llamar a María al 1145678901" ],
            "recientes": [
              {
                "fecha": "2025-02-01",
                "observaciones": "Trabajador José, tel 1145678901",
                "incumplimientos": "Falta EPP"
              }
            ]
          }
        }
        """;

    [Fact]
    public void BuildAggregatesOnly_excluye_relatos_y_observaciones()
    {
        var ctx = DossierLlmContextBuilder.BuildAggregatesOnly(SampleDossier);

        Assert.Contains("Total período: 10", ctx);
        Assert.Contains("Caída", ctx);
        Assert.Contains("Orden y Limpieza", ctx);

        Assert.DoesNotContain("Juan Pérez", ctx);
        Assert.DoesNotContain("Corrientes", ctx);
        Assert.DoesNotContain("71234567", ctx);
        Assert.DoesNotContain("María", ctx);
        Assert.DoesNotContain("1145678901", ctx);
        Assert.DoesNotContain("José", ctx);
        Assert.DoesNotContain("2025-01-01", ctx); // fecha de relato no debe colarse
        Assert.DoesNotContain("Llamar a", ctx);
    }

    [Fact]
    public void BuildAggregatesOnly_omite_incumplimiento_prosa_riesgosa()
    {
        var ctx = DossierLlmContextBuilder.BuildAggregatesOnly(SampleDossier);
        Assert.DoesNotContain("Calle Falsa", ctx);
        Assert.DoesNotContain("operario", ctx);
    }
}
