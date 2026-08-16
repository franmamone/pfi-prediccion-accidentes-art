import { useEffect, useState } from "react";
import { fetchEstadisticas, HORIZONTE_OPERATIVO, type Estadisticas } from "../api";
import { BarChart, DivergingBarChart, DonutChart, TimeSeriesChart } from "../charts";
import { ciiuDivisionLabel } from "../ciiu";
import { SkeletonPanel } from "../components/UiKit";
import { riesgoLabel } from "../labels";
import {
  getEstadisticasTab,
  setEstadisticasTab,
  type EstadisticasSectionKey,
} from "../prefs";

const BANDA_COLORS: Record<string, string> = {
  critico: "#f04438",
  alto: "#f79009",
  medio: "#12b76a",
  bajo: "#7c8aa5",
};

const TABS: { key: EstadisticasSectionKey; label: string; count: number }[] = [
  { key: "operativa", label: "Cobertura operativa", count: 1 },
  { key: "shap", label: "Explicabilidad del modelo (SHAP)", count: 2 },
  { key: "composicion", label: "Composición y riesgo de la lista", count: 4 },
  { key: "sectores", label: "Sectores", count: 2 },
];

export function EstadisticasPage() {
  const horizonte = HORIZONTE_OPERATIVO;
  const [data, setData] = useState<Estadisticas | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<EstadisticasSectionKey>(() => getEstadisticasTab());

  function selectTab(key: EstadisticasSectionKey) {
    setTab(key);
    setEstadisticasTab(key);
  }

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
      <div>
        <h1 className="page-title">Estadísticas</h1>
        <p className="page-sub">Cobertura y desempeño del ranking trimestral</p>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && (
        <div className="charts-grid">
          <SkeletonPanel lines={6} />
          <SkeletonPanel lines={6} />
        </div>
      )}

      {data && (
        <>
          <div className="stats-tabs" role="tablist" aria-label="Secciones de estadísticas">
            {TABS.map((t) => (
              <button
                key={t.key}
                role="tab"
                type="button"
                aria-selected={tab === t.key}
                className={`stats-tab${tab === t.key ? " active" : ""}`}
                onClick={() => selectTab(t.key)}
              >
                {t.label} <span className="stats-tab-count">({t.count})</span>
              </button>
            ))}
          </div>

          {tab === "operativa" && (
            <div className="charts-grid">
              <TimeSeriesChart
                title="Cobertura operativa del trimestre (top-1000)"
                subtitle="Porcentaje cubierto de la lista trimestral (top-1000) desde su activación"
                series={(a?.coberturaCohorte.serieTop1000 ?? []).map((p) => ({
                  clave: p.activadoEn
                    ? new Date(p.activadoEn).toLocaleDateString("es-AR", { month: "short", year: "2-digit" })
                    : p.periodoDecision,
                  valor: p.porcentaje,
                }))}
                emptyHint="Aún no hay cohortes operativas con cobertura calculada"
              />
            </div>
          )}

          {tab === "shap" && (
            <div className="charts-grid">
              <BarChart
                title="SHAP top-1000 · importancia"
                subtitle="Media absoluta sobre la lista completa mostrada (top-1000)"
                data={(a?.shapAgregado.top1000 ?? []).map((f) => ({
                  clave: f.etiqueta,
                  valor: f.meanAbsShap,
                }))}
                valueFormatter={(n) => n.toFixed(3)}
              />
              <DivergingBarChart
                title="SHAP top-1000 · aporte firmado"
                subtitle={a?.shapAgregado.advertencia ?? "Aumenta (derecha) vs reduce (izquierda) sobre el top-1000"}
                data={(a?.shapAgregado.top1000 ?? []).map((f) => ({
                  clave: f.etiqueta,
                  valor: f.meanShap,
                }))}
              />
            </div>
          )}

          {tab === "composicion" && (
            <div className="charts-grid">
              <DonutChart
                title="Distribución por riesgo"
                subtitle="Críticos, altos, medios y bajos de la lista"
                data={data.byBanda.map((d) => ({
                  clave: riesgoLabel(d.clave),
                  valor: d.valor,
                  color: BANDA_COLORS[d.clave] ?? undefined,
                }))}
              />
              <BarChart
                title="Distribución de acierto histórico"
                subtitle="Cuántos establecimientos caen en cada nivel de acierto (precision@K por tramo)"
                data={data.aciertoBuckets}
              />
              <DonutChart
                title="Visita reciente"
                subtitle="Disponibles vs visitados recientemente"
                data={[
                  { clave: "Con visita reciente", valor: data.flags.enCooldown, color: "#94a3b8" },
                  { clave: "Sin visita reciente", valor: data.flags.sinCooldown, color: "#3b82f6" },
                ]}
              />
              <BarChart
                title="Antigüedad de visitas"
                subtitle="Meses desde la última visita de prevención"
                data={data.visitasBuckets}
              />
            </div>
          )}

          {tab === "sectores" && (
            <div className="charts-grid">
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
          )}
        </>
      )}
    </>
  );
}
