import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchRiesgo, shortId, type Horizonte, type RankingItem } from "../api";

type Props = {
  forceSectorFilter?: boolean;
};

export function RiesgoPage({ forceSectorFilter = false }: Props) {
  const [params, setParams] = useSearchParams();
  const horizonte = (params.get("horizonte") as Horizonte) || "1m";
  const banda = params.get("banda") || "";
  const sector = params.get("sector") || "";
  const q = params.get("q") || "";
  const [items, setItems] = useState<RankingItem[]>([]);
  const [periodo, setPeriodo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fetchRiesgo({
      horizonte,
      banda: banda || undefined,
      sector: sector || undefined,
      q: q || undefined,
      top: 225,
    })
      .then((res) => {
        if (!alive) return;
        setItems(res.items);
        setPeriodo(res.periodo);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "Error al cargar ranking");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [horizonte, banda, sector, q]);

  const sectors = useMemo(() => {
    const set = new Set(items.map((i) => i.ciiuDivision).filter(Boolean) as string[]);
    return Array.from(set).sort();
  }, [items]);

  function patch(next: Record<string, string>) {
    const merged = new URLSearchParams(params);
    Object.entries(next).forEach(([k, v]) => {
      if (!v) merged.delete(k);
      else merged.set(k, v);
    });
    setParams(merged);
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 className="page-title">{forceSectorFilter ? "Por actividad" : "Priorización"}</h1>
          <p className="page-sub">
            Lista maestra · período <span className="mono">{periodo || "…"}</span>
            {forceSectorFilter ? " · filtrá por división CIIU sin forzar top-50 por rubro" : ""}
          </p>
        </div>
        <div className="horizon-toggle">
          <button
            className={horizonte === "1m" ? "active" : ""}
            onClick={() => patch({ horizonte: "1m" })}
          >
            Mes
          </button>
          <button
            className={horizonte === "3m" ? "active" : ""}
            onClick={() => patch({ horizonte: "3m" })}
          >
            Trimestre
          </button>
        </div>
      </div>

      <div className="panel filters">
        <div className="field">
          <label>Banda</label>
          <select value={banda} onChange={(e) => patch({ banda: e.target.value })}>
            <option value="">Todas</option>
            <option value="critico">Crítico</option>
            <option value="alto">Alto</option>
            <option value="medio">Medio</option>
          </select>
        </div>
        <div className="field">
          <label>División CIIU</label>
          <select value={sector} onChange={(e) => patch({ sector: e.target.value })}>
            <option value="">Todas</option>
            {sectors.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ minWidth: 220, flex: 1 }}>
          <label>Buscar id</label>
          <input
            value={q}
            placeholder="hash establecimiento…"
            onChange={(e) => patch({ q: e.target.value })}
          />
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <p className="muted">Cargando ranking…</p>}

      <div className="table-wrap panel" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th>#</th>
              <th>Establecimiento</th>
              <th>Score</th>
              <th>Banda</th>
              <th>Motivo</th>
              <th>CIIU</th>
              <th>Cápitas</th>
              <th>Última visita</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td className="mono">{item.ranking}</td>
                <td className="mono" title={item.idEstablecimiento}>
                  {shortId(item.idEstablecimiento)}
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="mono">{item.scoreRiesgo.toFixed(3)}</span>
                    <div className="score-bar">
                      <span style={{ width: `${Math.min(100, item.scoreRiesgo * 100)}%` }} />
                    </div>
                  </div>
                </td>
                <td>
                  <span className={`badge ${item.banda}`}>{item.banda}</span>
                </td>
                <td>{item.motivo ?? "—"}</td>
                <td className="mono">{item.ciiuDivision ?? "—"}</td>
                <td className="mono">
                  {item.cantidadCapitas != null ? Math.round(item.cantidadCapitas).toLocaleString("es-AR") : "—"}
                </td>
                <td className="mono">
                  {item.ultimaVisitaHaceMeses != null ? `${item.ultimaVisitaHaceMeses} m` : "sin visita"}
                </td>
                <td>
                  <Link to={`/establecimientos/${item.idEstablecimiento}?horizonte=${horizonte}`}>Detalle</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
