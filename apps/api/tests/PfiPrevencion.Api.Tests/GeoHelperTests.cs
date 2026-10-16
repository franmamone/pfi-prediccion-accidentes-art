using PfiPrevencion.Api.Services;

namespace PfiPrevencion.Api.Tests;

public class GeoHelperTests
{
    [Fact]
    public void HaversineKm_MismaCoordenada_EsCero()
    {
        var d = GeoHelper.HaversineKm(-34.60, -58.38, -34.60, -58.38);
        Assert.True(d < 0.001);
    }

    [Fact]
    public void HaversineKm_DistintosPuntos_Positiva()
    {
        var d = GeoHelper.HaversineKm(-34.60, -58.38, -34.62, -58.40);
        Assert.True(d > 1 && d < 10);
    }

    [Theory]
    [InlineData(null, 2.0)]
    [InlineData(10.0, 1.0)]
    [InlineData(30.0, 2.0)]
    [InlineData(150.0, 2.0)]
    [InlineData(151.0, 3.0)]
    public void DuracionEstimadaHoras_PorCapitas(double? capitas, double esperada) =>
        Assert.Equal(esperada, GeoHelper.DuracionEstimadaHoras(capitas));

    [Theory]
    [InlineData(null, "medio")]
    [InlineData(10.0, "chico")]
    [InlineData(80.0, "medio")]
    [InlineData(200.0, "grande")]
    public void TamanoEtiqueta_Ok(double? capitas, string etiqueta) =>
        Assert.Equal(etiqueta, GeoHelper.TamanoEtiqueta(capitas));

    [Fact]
    public void Score_CombinaDistanciaYCarga()
    {
        var s = GeoHelper.Score(3.0, 2.0);
        Assert.Equal(3.0 + GeoHelper.LoadWeightKmPerHora * 2.0, s);
    }

    [Fact]
    public void ResolverAncla_SinVisitas_UsaBase()
    {
        var (lat, lon, origen) = GeoHelper.ResolverAncla(-34.6, -58.4, new TimeOnly(10, 0), []);
        Assert.Equal(-34.6, lat);
        Assert.Equal(-58.4, lon);
        Assert.Equal("base", origen);
    }

    [Fact]
    public void ResolverAncla_PrefiereVisitaAnterior()
    {
        var visitas = new List<GeoHelper.VisitaDia>
        {
            new(new TimeOnly(9, 0), -34.61, -58.41),
            new(new TimeOnly(14, 0), -34.63, -58.43),
        };
        var (lat, lon, origen) = GeoHelper.ResolverAncla(-34.6, -58.4, new TimeOnly(11, 0), visitas);
        Assert.Equal(-34.61, lat);
        Assert.Equal(-58.41, lon);
        Assert.Equal("visita_anterior", origen);
    }

    [Fact]
    public void ResolverAncla_SinAnterior_UsaSiguiente()
    {
        var visitas = new List<GeoHelper.VisitaDia>
        {
            new(new TimeOnly(15, 0), -34.63, -58.43),
        };
        var (_, _, origen) = GeoHelper.ResolverAncla(-34.6, -58.4, new TimeOnly(10, 0), visitas);
        Assert.Equal("visita_siguiente", origen);
    }

    [Fact]
    public void RespetaGap_Solapamiento_False()
    {
        var ocupadas = new[] { new GeoHelper.SlotOcupado(new TimeOnly(10, 0), 2) };
        Assert.False(GeoHelper.RespetaGap(new TimeOnly(11, 0), 2, ocupadas));
    }

    [Fact]
    public void RespetaGap_SinSolape_True()
    {
        var ocupadas = new[] { new GeoHelper.SlotOcupado(new TimeOnly(10, 0), 2) };
        Assert.True(GeoHelper.RespetaGap(new TimeOnly(12, 0), 1, ocupadas));
    }

    [Fact]
    public void RespetaGap_CompatTimeOnly()
    {
        Assert.True(GeoHelper.RespetaGap(new TimeOnly(14, 0), [new TimeOnly(10, 0)]));
        Assert.False(GeoHelper.RespetaGap(new TimeOnly(10, 0), [new TimeOnly(10, 0)]));
    }

    [Fact]
    public void CalcularHuecos_EncuentraSlots()
    {
        var franjas = new[] { (new TimeOnly(9, 0), new TimeOnly(12, 0)) };
        var huecos = GeoHelper.CalcularHuecos(franjas, Array.Empty<GeoHelper.SlotOcupado>(), 1.0);
        Assert.NotEmpty(huecos);
        Assert.Contains(new TimeOnly(9, 0), huecos);
    }

    [Fact]
    public void CalcularHuecos_CompatTimeOnly()
    {
        var franjas = new[] { (new TimeOnly(9, 0), new TimeOnly(11, 0)) };
        var huecos = GeoHelper.CalcularHuecos(franjas, Array.Empty<TimeOnly>());
        Assert.NotEmpty(huecos);
    }

    [Fact]
    public void HoraEnFranjas_Y_RandomCaba_Y_Iso()
    {
        var franjas = new[] { (new TimeOnly(9, 0), new TimeOnly(13, 0)) };
        Assert.True(GeoHelper.HoraEnFranjas(new TimeOnly(10, 0), franjas));
        Assert.False(GeoHelper.HoraEnFranjas(new TimeOnly(14, 0), franjas));

        var (lat, lon) = GeoHelper.RandomCaba(new Random(1));
        Assert.InRange(lat, GeoHelper.CabaLatMin, GeoHelper.CabaLatMax);
        Assert.InRange(lon, GeoHelper.CabaLonMin, GeoHelper.CabaLonMax);

        Assert.Equal(1, GeoHelper.ToIsoDiaSemana(new DateOnly(2026, 10, 12))); // lunes
        Assert.Equal(7, GeoHelper.ToIsoDiaSemana(new DateOnly(2026, 10, 11))); // domingo
        Assert.True(GeoHelper.AbsDiff(new TimeOnly(10, 0), new TimeOnly(11, 0)) == TimeSpan.FromHours(1));
    }
}
