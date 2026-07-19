import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { fetchEstablecimiento, shortId, type Horizonte, type RankingItem } from "../api";

export function DetallePage() {
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const horizonte = (params.get("horizonte") as Horizonte) || "1m";
  const [item, setItem] = useState<RankingItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    fetchEstablecimiento(id, horizonte)
      .then((res) => {
        if (alive) setItem(res);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "No se pudo cargar");
      });
    return () => {
      alive = false;
    };
  }, [id, horizonte]);

  return (
    <>
      <div>
        <Link to={`/riesgo?horizonte=${horizonte}`} className="muted">
          ← Volver a priorización
        </Link>
        <h1 className="page-title" style={{ marginTop: 8 }}>
          Establecimiento
        </h1>
        <p className="page-sub mono">{id}</p>
      </div>

      {error && <div className="error">{error}</div>}

      {item && (
        <div className="panel">
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 14 }}>
            <span className={`badge ${item.banda}`}>{item.banda}</span>
            <span className="mono">#{item.ranking}</span>
            <span className="mono">score {item.scoreRiesgo.toFixed(4)}</span>
          </div>
          <div className="detail-grid">
            <div className="kv">
              <div className="k">ID establecimiento</div>
              <div className="v mono">{item.idEstablecimiento}</div>
            </div>
            <div className="kv">
              <div className="k">ID empleador</div>
              <div className="v mono">{item.idEmpleador ? shortId(item.idEmpleador) : "—"}</div>
            </div>
            <div className="kv">
              <div className="k">Motivo</div>
              <div className="v">{item.motivo ?? "—"}</div>
            </div>
            <div className="kv">
              <div className="k">Sector / CIIU</div>
              <div className="v">
                {item.sector ?? "—"} · Div. {item.ciiuDivision ?? "—"}
              </div>
            </div>
            <div className="kv">
              <div className="k">Cápitas</div>
              <div className="v mono">
                {item.cantidadCapitas != null ? item.cantidadCapitas.toLocaleString("es-AR") : "—"}
              </div>
            </div>
            <div className="kv">
              <div className="k">Dotación nómina mes</div>
              <div className="v mono">
                {item.dotacionNominaMes != null ? item.dotacionNominaMes.toLocaleString("es-AR") : "—"}
              </div>
            </div>
            <div className="kv">
              <div className="k">Última visita</div>
              <div className="v mono">
                {item.ultimaVisitaHaceMeses != null ? `${item.ultimaVisitaHaceMeses} meses` : "sin visita"}
              </div>
            </div>
            <div className="kv">
              <div className="k">Flags</div>
              <div className="v">
                {item.enCooldown ? "cooldown · " : ""}
                {item.obligacionPrs ? "PRS · " : ""}
                {item.alertaUmbral ? "alerta umbral" : "sin alerta"}
              </div>
            </div>
          </div>
          <p className="muted" style={{ marginTop: 14 }}>
            El score ordena prioridad relativa. No interpretarlo como probabilidad de accidente.
          </p>
        </div>
      )}
    </>
  );
}
