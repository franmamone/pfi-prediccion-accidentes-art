namespace PfiPrevencion.Api.Services;

public static class GeoHelper
{
    /// <summary>
    /// Peso de cada visita ya asignada ese día, en “km equivalentes”.
    /// score = distanciaKm + LoadWeightKm * visitasDelDia (menor = mejor).
    /// </summary>
    public const double LoadWeightKm = 3.0;

    /// <summary>Separación mínima entre visitas del mismo preventor (viaje + margen).</summary>
    public static readonly TimeSpan GapEntreVisitas = TimeSpan.FromHours(2);

    /// <summary>Grilla de huecos propuestos dentro de la franja laboral.</summary>
    public static readonly TimeSpan PasoHueco = TimeSpan.FromMinutes(30);

    // Bounding box aproximado CABA
    public const double CabaLatMin = -34.70;
    public const double CabaLatMax = -34.53;
    public const double CabaLonMin = -58.53;
    public const double CabaLonMax = -58.34;

    public static double HaversineKm(double lat1, double lon1, double lat2, double lon2)
    {
        const double R = 6371.0;
        static double Rad(double d) => d * Math.PI / 180.0;
        var dLat = Rad(lat2 - lat1);
        var dLon = Rad(lon2 - lon1);
        var a = Math.Sin(dLat / 2) * Math.Sin(dLat / 2)
            + Math.Cos(Rad(lat1)) * Math.Cos(Rad(lat2))
            * Math.Sin(dLon / 2) * Math.Sin(dLon / 2);
        var c = 2 * Math.Atan2(Math.Sqrt(a), Math.Sqrt(1 - a));
        return R * c;
    }

    /// <summary>Menor score = más recomendado (cerca y con menos visitas ese día).</summary>
    public static double Score(double distanciaKm, int visitasDelDia) =>
        distanciaKm + LoadWeightKm * visitasDelDia;

    public static bool RespetaGap(TimeOnly candidata, IEnumerable<TimeOnly> ocupadas, TimeSpan? gap = null)
    {
        var g = gap ?? GapEntreVisitas;
        foreach (var o in ocupadas)
        {
            var diff = AbsDiff(candidata, o);
            if (diff < g) return false;
        }
        return true;
    }

    public static TimeSpan AbsDiff(TimeOnly a, TimeOnly b)
    {
        var ticks = Math.Abs(a.Ticks - b.Ticks);
        return TimeSpan.FromTicks(ticks);
    }

    /// <summary>
    /// Huecos cada 30 min dentro de las franjas del día, libres respecto de visitas ocupadas (±2 h).
    /// </summary>
    public static List<TimeOnly> CalcularHuecos(
        IEnumerable<(TimeOnly Desde, TimeOnly Hasta)> franjas,
        IReadOnlyList<TimeOnly> ocupadas,
        TimeSpan? gap = null,
        TimeSpan? paso = null)
    {
        var g = gap ?? GapEntreVisitas;
        var step = paso ?? PasoHueco;
        var set = new SortedSet<TimeOnly>();
        foreach (var (desde, hasta) in franjas)
        {
            if (hasta <= desde) continue;
            for (var t = desde; t < hasta; t = t.Add(step))
            {
                if (ocupadas.Contains(t)) continue;
                if (!RespetaGap(t, ocupadas, g)) continue;
                set.Add(t);
            }
        }
        return set.ToList();
    }

    public static bool HoraEnFranjas(TimeOnly hora, IEnumerable<(TimeOnly Desde, TimeOnly Hasta)> franjas) =>
        franjas.Any(f => hora >= f.Desde && hora < f.Hasta);

    public static (double Lat, double Lon) RandomCaba(Random rng) =>
    (
        CabaLatMin + rng.NextDouble() * (CabaLatMax - CabaLatMin),
        CabaLonMin + rng.NextDouble() * (CabaLonMax - CabaLonMin)
    );

    /// <summary>ISO: 1=Lunes .. 7=Domingo.</summary>
    public static byte ToIsoDiaSemana(DateOnly fecha)
    {
        var d = (int)fecha.DayOfWeek; // 0=Dom .. 6=Sab
        return (byte)(d == 0 ? 7 : d);
    }
}
