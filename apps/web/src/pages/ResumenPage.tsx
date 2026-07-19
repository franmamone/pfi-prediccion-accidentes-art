import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchResumen, type Horizonte, type Resumen } from "../api";

export function ResumenPage() {
  const [horizonte, setHorizonte] = useState<Horizonte>("1m");
  const [data, setData] = useState<Resumen | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    fetchResumen(horizonte)
      .then((res) => {
        if (alive) setData(res);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "Error al cargar resumen");
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

      {data && (
        <>
          <div className="stats">
            <div className="stat">
              <div className="label">Críticos (top-50)</div>
              <div className="value mono">{data.criticos}</div>
            </div>
            <div className="stat">
              <div className="label">Altos (51–225)</div>
              <div className="value mono">{data.altos}</div>
            </div>
            <div className="stat">
              <div className="label">En cooldown</div>
              <div className="value mono">{data.enCooldown}</div>
            </div>
            <div className="stat">
              <div className="label">Obligación PRS</div>
              <div className="value mono">{data.obligacionPrs}</div>
            </div>
          </div>

          <div className="panel">
            <p className="page-sub" style={{ marginBottom: 12 }}>
              Período vigente <strong className="mono">{data.periodo}</strong> · horizonte{" "}
              <strong>{data.horizonte}</strong> · capacidad mensual {data.capacidadMensual}
            </p>
            <p className="muted">{data.nota}</p>
            <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
              <Link className="btn" to="/riesgo" style={{ display: "inline-flex", alignItems: "center" }}>
                Ir a priorización
              </Link>
            </div>
          </div>
        </>
      )}
    </>
  );
}
