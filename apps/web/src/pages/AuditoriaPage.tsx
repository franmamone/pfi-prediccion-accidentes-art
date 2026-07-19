import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchAuditoriaAgenda,
  shortId,
  type AgendaEvento,
} from "../api";

const TIPOS = ["", "programada", "reprogramada", "realizada", "cancelada"] as const;

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-AR", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function tipoLabel(tipo: string): string {
  switch (tipo) {
    case "programada":
      return "Programada";
    case "reprogramada":
      return "Reprogramada";
    case "realizada":
      return "Realizada";
    case "cancelada":
      return "Cancelada";
    default:
      return tipo;
  }
}

export function AuditoriaPage() {
  const [tipo, setTipo] = useState("");
  const [qEst, setQEst] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<AgendaEvento[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const pageSize = 40;

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchAuditoriaAgenda({
      tipo: tipo || undefined,
      idEstablecimiento: qEst.trim() || undefined,
      page,
      pageSize,
    })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "No se pudo cargar la auditoría");
      })
      .finally(() => setLoading(false));
  }, [tipo, qEst, page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <>
      <div>
        <h1 className="page-title">Auditoría de visitas</h1>
        <p className="page-sub">
          Bitácora append-only del ciclo de agenda. El actor es quien ejecutó la acción (puede
          diferir del responsable asignado). Registros anteriores a la auditoría no inventan actor.
        </p>
      </div>

      <div className="panel filters">
        <div className="field" style={{ minWidth: 160 }}>
          <label>Tipo</label>
          <select
            value={tipo}
            onChange={(e) => {
              setPage(1);
              setTipo(e.target.value);
            }}
          >
            {TIPOS.map((t) => (
              <option key={t || "todos"} value={t}>
                {t ? tipoLabel(t) : "Todos"}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ minWidth: 220, flex: 1 }}>
          <label>ID establecimiento</label>
          <input
            value={qEst}
            onChange={(e) => {
              setPage(1);
              setQEst(e.target.value);
            }}
            placeholder="Hash completo o vacío"
          />
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <p className="muted">Cargando eventos…</p>}

      {!loading && items.length === 0 && (
        <div className="panel">
          <p className="page-sub" style={{ marginBottom: 0 }}>
            No hay eventos con estos filtros. Las visitas creadas antes de habilitar la bitácora no
            generan filas retroactivas.
          </p>
        </div>
      )}

      {items.length > 0 && (
        <div className="table-wrap panel" style={{ padding: 0 }}>
          <table className="data">
            <thead>
              <tr>
                <th>Cuándo</th>
                <th>Tipo</th>
                <th>Establecimiento</th>
                <th>Agenda</th>
                <th>Actor</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {items.map((ev) => (
                <tr key={ev.id}>
                  <td className="mono">{formatDateTime(ev.ocurridoEn)}</td>
                  <td>
                    <span className="badge motivo-predictivo">{tipoLabel(ev.tipo)}</span>
                  </td>
                  <td className="mono" title={ev.idEstablecimiento}>
                    <Link to={`/establecimientos/${ev.idEstablecimiento}`}>
                      {shortId(ev.idEstablecimiento)}
                    </Link>
                  </td>
                  <td className="mono">
                    <Link to={`/agenda`}>{ev.agendaItemId}</Link>
                  </td>
                  <td>
                    {ev.actor ? (
                      <span title={ev.actor.email ?? undefined}>
                        {ev.actor.nombre}
                        <span className="muted"> · {ev.actor.rol}</span>
                      </span>
                    ) : (
                      <span className="muted" title="Registro anterior a la bitácora o sin actor">
                        Sin actor
                      </span>
                    )}
                  </td>
                  <td className="muted">
                    {(ev.estadoAnterior ?? "—") + " → " + (ev.estadoNuevo ?? "—")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > pageSize && (
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12 }}>
          <button
            type="button"
            className="ghost-btn"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Anterior
          </button>
          <span className="mono muted">
            Página {page}/{totalPages} · {total} eventos
          </span>
          <button
            type="button"
            className="ghost-btn"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Siguiente
          </button>
        </div>
      )}
    </>
  );
}
