import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchResumen, type Resumen } from "../api";
import { AnimatedNumber, EmptyState, Reveal, SkeletonPanel, SkeletonStats } from "../components/UiKit";
import { useHorizonte } from "../hooks/useHorizonte";

function pctBar(value: number): number {
  return Math.max(0, Math.min(100, value));
}

export function ResumenPage() {
  const [horizonte, setHorizonte] = useHorizonte();
  const [data, setData] = useState<Resumen | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setError(null);
    setLoading(true);
    fetchResumen(horizonte)
      .then((res) => {
        if (alive) setData(res);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "Error al cargar resumen");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [horizonte]);

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 className="page-title">Resumen</h1>
          <p className="page-sub">¿Qué conviene hacer hoy con la capacidad disponible?</p>
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
          <SkeletonPanel lines={4} />
        </>
      )}

      {!loading && !data && !error ? (
        <div className="panel">
          <EmptyState
            title="Sin resumen disponible"
            detail="Todavía no hay un snapshot vigente importado para este horizonte."
            action={
              <Link className="btn" to="/riesgo">
                Ir a priorización
              </Link>
            }
          />
        </div>
      ) : null}

      {data && (
        <>
          <div className="stats">
            <div className="stat" title="Establecimientos con ranking 1–50 en la lista vigente">
              <div className="label">Críticos (top-50)</div>
              <div className="value mono">
                <AnimatedNumber value={data.criticos} />
              </div>
            </div>
            <div className="stat" title="Establecimientos con ranking 51–225">
              <div className="label">Altos (51–225)</div>
              <div className="value mono">
                <AnimatedNumber value={data.altos} />
              </div>
            </div>
            <div className="stat" title="Con visita reciente en el panel (&lt; cooldown)">
              <div className="label">Con visita reciente</div>
              <div className="value mono">
                <AnimatedNumber value={data.enCooldown} />
              </div>
            </div>
            <div className="stat" title="Con obligación de Plan de Reducción de Siniestralidad">
              <div className="label">Obligación PRS</div>
              <div className="value mono">
                <AnimatedNumber value={data.obligacionPrs} />
              </div>
            </div>
          </div>

          <Reveal>
            <div className="panel">
              <h2 className="page-title" style={{ fontSize: 16, marginBottom: 8 }}>
                Estados operativos
              </h2>
              <p className="page-sub" style={{ marginBottom: 12 }} title={data.estadosOperativos.nota}>
                Universo del ranking vigente: <strong className="mono">{data.universo}</strong>
                {data.estadosOperativos.exclusivos ? (
                  <span className="muted"> · suma de estados = universo</span>
                ) : (
                  <span className="muted"> · revisar consistencia de estados</span>
                )}
              </p>
              <div className="stats">
                <div
                  className="stat"
                  title="Sin agenda activa ni cierre reciente como último estado de agenda"
                >
                  <div className="label">Pendientes</div>
                  <div className="value mono">
                    <AnimatedNumber value={data.estadosOperativos.pendiente} />
                  </div>
                </div>
                <div className="stat" title="Último estado de agenda = programada">
                  <div className="label">Programadas</div>
                  <div className="value mono">
                    <AnimatedNumber value={data.estadosOperativos.programada} />
                  </div>
                </div>
                <div className="stat" title="Último estado de agenda = realizada">
                  <div className="label">Realizadas</div>
                  <div className="value mono">
                    <AnimatedNumber value={data.estadosOperativos.realizada} />
                  </div>
                </div>
                <div className="stat" title="Último estado de agenda = cancelada">
                  <div className="label">Canceladas</div>
                  <div className="value mono">
                    <AnimatedNumber value={data.estadosOperativos.cancelada} />
                  </div>
                </div>
              </div>
            </div>
          </Reveal>

          <Reveal>
            <div className="panel">
              <h2 className="page-title" style={{ fontSize: 16, marginBottom: 8 }}>
                Cobertura de visitas
              </h2>
              <p className="page-sub" style={{ marginBottom: 14 }} title={data.cobertura.nota}>
                Establecimientos distintos <strong>programados o realizados</strong> sobre el tamaño
                real del top-K. El top 50 no se suma al top 225.
              </p>
              {[data.cobertura.top50, data.cobertura.top225].map((c) => (
                <div key={c.k} style={{ marginBottom: 14 }} title={c.criterio}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <strong>Top {c.k}</strong>
                    <span className="mono">
                      {c.cantidad}/{c.denominador} ({c.porcentaje.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="coverage-bar" aria-hidden>
                    <div className="coverage-fill animate-bar" style={{ width: `${pctBar(c.porcentaje)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </Reveal>

          <Reveal>
            <div className="panel">
              <p className="page-sub" style={{ marginBottom: 12 }}>
                Período vigente <strong className="mono">{data.periodo}</strong> · horizonte{" "}
                <strong>{data.horizonte}</strong> · capacidad mensual {data.capacidadMensual}
              </p>
              <p className="muted">{data.nota}</p>
              <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
                <Link className="btn" to={`/riesgo?horizonte=${horizonte}`}>
                  Ir a priorización
                </Link>
                <Link className="ghost-btn" to="/agenda">
                  Ver agenda
                </Link>
                <Link className="ghost-btn" to="/auditoria">
                  Auditoría
                </Link>
                <Link className="ghost-btn" to="/estadisticas">
                  Ver estadísticas
                </Link>
              </div>
            </div>
          </Reveal>
        </>
      )}
    </>
  );
}
