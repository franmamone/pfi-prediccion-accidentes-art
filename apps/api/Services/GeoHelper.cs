namespace PfiPrevencion.Api.Services;

public static class GeoHelper
{
    /// <summary>
    /// Peso de cada hora ya cargada ese día, en “km equivalentes”.
    /// score = distanciaKm + LoadWeightKmPerHora * horasCargaDia (menor = mejor).
    /// 1,5 → una visita media (2 h) pesa como 3 km, igual que el peso por visita anterior.
    /// </summary>
    public const double LoadWeightKmPerHora = 1.5;

    /// <summary>Duración por defecto (establecimiento medio / cápitas desconocidas).</summary>
    public const double DuracionDefaultHoras = 2.0;

    /// <summary>Separación mínima legacy (igual a duración media). Preferir gap por duración.</summary>
    public static readonly TimeSpan GapEntreVisitas = TimeSpan.FromHours(DuracionDefaultHoras);

    /// <summary>Grilla de huecos propuestos dentro de la franja laboral.</summary>
    public static readonly TimeSpan PasoHueco = TimeSpan.FromMinutes(30);

    // Bounding box aproximado CABA
    public const double CabaLatMin = -34.70;
    public const double CabaLatMax = -34.53;
    public const double CabaLonMin = -58.53;
    public const double CabaLonMax = -58.34;

    public readonly record struct SlotOcupado(TimeOnly Hora, double DuracionHoras);
    public readonly record struct VisitaDia(TimeOnly Hora, double Lat, double Lon);

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

    /// <summary>
    /// Heurística por exposición (nómina/cápitas). Sin medición empírica de duración real.
    /// Chico &lt;30 → 1 h; medio 30–150 → 2 h; grande &gt;150 → 3 h.
    /// </summary>
    public static double DuracionEstimadaHoras(double? cantidadCapitas)
    {
        if (cantidadCapitas is null) return DuracionDefaultHoras;
        if (cantidadCapitas.Value < 30) return 1.0;
        if (cantidadCapitas.Value <= 150) return 2.0;
        return 3.0;
    }

    public static string TamanoEtiqueta(double? cantidadCapitas) =>
        DuracionEstimadaHoras(cantidadCapitas) switch
        {
            <= 1.0 => "chico",
            >= 3.0 => "grande",
            _ => "medio",
        };

    /// <summary>Menor score = más recomendado (cerca del ancla y con menos horas cargadas).</summary>
    public static double Score(double distanciaKm, double horasCargaDia) =>
        distanciaKm + LoadWeightKmPerHora * horasCargaDia;

    /// <summary>
    /// Ancla de distancia: visita anterior en el día (por hora); si no, la siguiente;
    /// si el día está vacío, base del preventor.
    /// </summary>
    public static (double Lat, double Lon, string Origen) ResolverAncla(
        double baseLat,
        double baseLon,
        TimeOnly horaCandidata,
        IReadOnlyList<VisitaDia> visitasDia)
    {
        if (visitasDia.Count == 0)
            return (baseLat, baseLon, "base");

        foreach (var p in visitasDia.Where(v => v.Hora < horaCandidata).OrderByDescending(v => v.Hora).Take(1))
            return (p.Lat, p.Lon, "visita_anterior");

        foreach (var n in visitasDia.Where(v => v.Hora > horaCandidata).OrderBy(v => v.Hora).Take(1))
            return (n.Lat, n.Lon, "visita_siguiente");

        // Misma hora u otro caso raro: establecimiento ya en ruta más cercano a la base.
        var nearest = visitasDia
            .OrderBy(v => HaversineKm(baseLat, baseLon, v.Lat, v.Lon))
            .First();
        return (nearest.Lat, nearest.Lon, "visita_ruta");
    }

    /// <summary>
    /// Separación por inicio: la visita que empieza antes debe terminar (duración estimada)
    /// antes de que empiece la otra.
    /// </summary>
    public static bool RespetaGap(
        TimeOnly candidata,
        double duracionCandidataHoras,
        IEnumerable<SlotOcupado> ocupadas)
    {
        var durCand = NormalizeDuracion(duracionCandidataHoras);
        foreach (var o in ocupadas)
        {
            if (candidata == o.Hora) return false;
            var durO = NormalizeDuracion(o.DuracionHoras);
            if (candidata > o.Hora)
            {
                if (!TerminaAntesDe(o.Hora, durO, candidata)) return false;
            }
            else
            {
                if (!TerminaAntesDe(candidata, durCand, o.Hora)) return false;
            }
        }
        return true;
    }

    /// <summary>Compat: trata ocupadas como duración media (2 h).</summary>
    public static bool RespetaGap(TimeOnly candidata, IEnumerable<TimeOnly> ocupadas, TimeSpan? gap = null)
    {
        var horas = (gap ?? GapEntreVisitas).TotalHours;
        var slots = ocupadas.Select(h => new SlotOcupado(h, horas));
        return RespetaGap(candidata, horas, slots);
    }

    public static TimeSpan AbsDiff(TimeOnly a, TimeOnly b)
    {
        var ticks = Math.Abs(a.Ticks - b.Ticks);
        return TimeSpan.FromTicks(ticks);
    }

    public static List<TimeOnly> CalcularHuecos(
        IEnumerable<(TimeOnly Desde, TimeOnly Hasta)> franjas,
        IReadOnlyList<SlotOcupado> ocupadas,
        double duracionCandidataHoras,
        TimeSpan? paso = null)
    {
        var step = paso ?? PasoHueco;
        var set = new SortedSet<TimeOnly>();
        foreach (var (desde, hasta) in franjas)
        {
            if (hasta <= desde) continue;
            for (var t = desde; t < hasta; t = t.Add(step))
            {
                if (ocupadas.Any(o => o.Hora == t)) continue;
                if (!RespetaGap(t, duracionCandidataHoras, ocupadas)) continue;
                set.Add(t);
            }
        }
        return set.ToList();
    }

    /// <summary>Compat: huecos con gap fijo (duración media).</summary>
    public static List<TimeOnly> CalcularHuecos(
        IEnumerable<(TimeOnly Desde, TimeOnly Hasta)> franjas,
        IReadOnlyList<TimeOnly> ocupadas,
        TimeSpan? gap = null,
        TimeSpan? paso = null)
    {
        var horas = (gap ?? GapEntreVisitas).TotalHours;
        var slots = ocupadas.Select(h => new SlotOcupado(h, horas)).ToList();
        return CalcularHuecos(franjas, slots, horas, paso);
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

    static double NormalizeDuracion(double horas) =>
        horas is < 0.5 or > 8 ? DuracionDefaultHoras : horas;

    static bool TerminaAntesDe(TimeOnly inicio, double duracionHoras, TimeOnly limite)
    {
        var finMinutos = inicio.Hour * 60 + inicio.Minute + (int)Math.Round(duracionHoras * 60);
        var limMinutos = limite.Hour * 60 + limite.Minute;
        return finMinutos <= limMinutos;
    }
}
