import { useEffect, useState } from "react";
import { fetchEstadisticas, type Estadisticas } from "../api";
import { BarChart, DivergingBarChart, DonutChart, TimeSeriesChart } from "../charts";
import { ciiuDivisionLabel } from "../ciiu";
import { AnimatedNumber, SkeletonPanel, SkeletonStats } from "../components/UiKit";
import { useHorizonte } from "../hooks/useHorizonte";
import { motivoLabel, riesgoLabel } from "../labels";

const BANDA_COLORS: Record<string, string> = {
  critico: "#f04438",
  alto: "#f79009",
  medio: "#12b76a",
};

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toFixed(1)}%`;
}

export function EstadisticasPage() {
  const [horizonte, setHorizonte] = useHorizonte();
  const [data, setData] = useState<Estadisticas | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    setData(null);
    fetchEstadisticas(horizonte)
      .then((res) => {
        if (alive) setData(res);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "Error al cargar estadísticas");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [horizonte]);

  const a = data?.analitica;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 className="page-title">Estadísticas</h1>
          <p className="page-sub">
            Panorama de la lista vigente y seguimiento histórico
            {data ? (
              <>
                {" "}
                · período <span className="mono">{data.periodo}</span>
              </>
            ) : null}
          </p>
        </div>
        <div className="horizon-toggle">
          <button className={horizonte === "1m" ? "active" : ""} onClick={() => setHorizonte("1m")}>
            Mes
          </button>
          <button className={horizonte === "3m" ? "active" : ""} onClick={() => setHorizonte("3m")}>
            Trimestre
          </button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && (
        <>
          <SkeletonStats />
          <div className="charts-grid">
            <SkeletonPanel lines={6} />
            <SkeletonPanel lines={6} />
          </div>
        </>
      )}

      {data && (
        <>
          <div className="stats">
            <div className="stat">
              <div className="label">Establecimientos</div>
              <div className="value mono">
                <AnimatedNumber value={data.total} />
              </div>
            </div>
            <div className="stat" title={a?.coberturaCohorte.nota}>
              <div className="label">Cobertura top-50</div>
              <div className="value mono" style={{ fontSize: 22 }}>
                {fmtPct(a?.coberturaCohorte.top50?.porcentaje)}
              </div>
            </div>
            <div className="stat" title={a?.coberturaCohorte.nota}>
              <div className="label">Cobertura top-225</div>
              <div className="value mono" style={{ fontSize: 22 }}>
                {fmtPct(a?.coberturaCohorte.top225?.porcentaje)}
              </div>
            </div>
            <div className="stat" title={a?.precisionObservada.nota}>
              <div className="label">Acierto obs. top-225</div>
              <div className="value mono" style={{ fontSize: 22 }}>
                {a?.precisionObservada.top225?.estado === "maduro"
                  ? fmtPct(a.precisionObservada.top225.porcentaje)
                  : a?.precisionObservada.top225
                    ? "Pendiente"
                    : "—"}
              </div>
            </div>
          </div>

          <div className="charts-grid">
            <TimeSeriesChart
              title="Cobertura operativa top-225"
              subtitle="Porcentaje cubierto de cada cohorte desde su activación en la app"
              series={(a?.coberturaCohorte.serieTop225 ?? []).map((p) => ({
                clave: p.activadoEn
                  ? new Date(p.activadoEn).toLocaleDateString("es-AR", { month: "short", year: "2-digit" })
                  : p.periodoDecision,
                valor: p.porcentaje,
              }))}
              emptyHint="Aún no hay cohortes operativas con cobertura calculada"
            />
            <TimeSeriesChart
              title="Precisión observada top-225"
              subtitle={`Outcome maduro por período de decisión · holdout ref. ${a?.precisionObservada.holdoutReferenciaTop225Pct ?? "—"}%`}
              series={(a?.precisionObservada.serieTop225 ?? []).map((p) => ({
                clave: p.periodo,
                valor: p.estado === "maduro" ? p.porcentaje : null,
                color: p.esHoldoutSeed ? "#94a3b8" : "#3b82f6",
              }))}
              emptyHint="Sin períodos maduros todavía (hace falta fuente completa hasta el fin de la ventana)"
            />

            <BarChart
              title="SHAP top-50 · importancia"
              subtitle="Media absoluta en la escala interna del modelo"
              data={(a?.shapAgregado.top50 ?? []).map((f) => ({
                clave: f.etiqueta,
                valor: f.meanAbsShap,
              }))}
              valueFormatter={(n) => n.toFixed(3)}
            />
            <DivergingBarChart
              title="SHAP top-50 · aporte firmado"
              subtitle="Aumenta (derecha) vs reduce (izquierda) el margen"
              data={(a?.shapAgregado.top50 ?? []).map((f) => ({
                clave: f.etiqueta,
                valor: f.meanShap,
              }))}
            />
            <BarChart
              title="SHAP top-225 · importancia"
              subtitle="Media absoluta sobre la cohorte operativa completa"
              data={(a?.shapAgregado.top225 ?? []).map((f) => ({
                clave: f.etiqueta,
                valor: f.meanAbsShap,
              }))}
              valueFormatter={(n) => n.toFixed(3)}
            />
            <DivergingBarChart
              title="SHAP top-225 · aporte firmado"
              subtitle={a?.shapAgregado.advertencia}
              data={(a?.shapAgregado.top225 ?? []).map((f) => ({
                clave: f.etiqueta,
                valor: f.meanShap,
              }))}
            />

            <DonutChart
              title="Distribución por riesgo"
              subtitle="Críticos, altos y medios del cupo operativo"
              data={data.byBanda.map((d) => ({
                clave: riesgoLabel(d.clave),
                valor: d.valor,
                color: BANDA_COLORS[d.clave] ?? undefined,
              }))}
            />
            <DonutChart
              title="Visita reciente"
              subtitle="Disponibles vs visitados recientemente"
              data={[
                { clave: "Con visita reciente", valor: data.flags.enCooldown, color: "#94a3b8" },
                { clave: "Sin visita reciente", valor: data.flags.sinCooldown, color: "#3b82f6" },
              ]}
            />
            <BarChart title="Distribución del puntaje" subtitle="Cuántos caen en cada tramo" data={data.scoreBuckets} />
            <BarChart
              title="Antigüedad de visitas"
              subtitle="Meses desde la última visita de prevención"
              data={data.visitasBuckets}
            />
            <BarChart
              title="Top motivos"
              subtitle="Reglas que explican la inclusión"
              data={data.byMotivo.map((d) => ({ ...d, clave: motivoLabel(d.clave) }))}
            />
            <BarChart title="Por sector" subtitle="Volumen en la lista maestra" data={data.bySector} />
            <BarChart
              title="Top divisiones CIIU"
              subtitle="Cantidad de establecimientos priorizados"
              data={data.byCiiu.map((item) => ({
                ...item,
                clave: ciiuDivisionLabel(item.clave),
              }))}
              maxBars={12}
            />
          </div>

          {a && (
            <div className="panel" style={{ marginTop: 14 }}>
              <h2 className="page-title" style={{ fontSize: 16, marginBottom: 8 }}>
                Metodología y alcance
              </h2>
              <ul className="muted" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.55 }}>
                <li>{a.metodologia.cobertura}</li>
                <li>{a.metodologia.precision}</li>
                <li>{a.metodologia.shap}</li>
                <li>
                  Reloj operativo ≠ período de datos: el ranking {a.periodo} se evalúa por cobertura
                  desde su activación
                  {a.activadoEn ? ` (${new Date(a.activadoEn).toLocaleDateString("es-AR")})` : ""}, no
                  como si hubiera operado en ese mes calendario.
                </li>
                {a.datosHasta && (
                  <li>
                    Corte de datos del snapshot: <span className="mono">{a.datosHasta}</span>
                  </li>
                )}
              </ul>
            </div>
          )}
        </>
      )}
    </>
  );
}
