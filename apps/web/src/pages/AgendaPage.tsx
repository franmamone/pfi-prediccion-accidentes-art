import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchAgenda,
  fetchAgendaEventos,
  fetchUsuariosAsignables,
  reprogramarVisita,
  shortId,
  type AgendaEvento,
  type AgendaItem,
  type EstadoAgenda,
  type UsuarioAsignable,
} from "../api";
import { useAuth } from "../auth";
import { CancelarVisitaDialog } from "../components/CancelarVisitaDialog";
import { RealizarVisitaDialog } from "../components/RealizarVisitaDialog";
import { EmptyState, SkeletonTable } from "../components/UiKit";
import { motivoLabel, riesgoLabel } from "../labels";
import { useToast } from "../toast";

const TABS: { id: EstadoAgenda; label: string }[] = [
  { id: "programada", label: "Programadas" },
  { id: "realizada", label: "Realizadas" },
  { id: "cancelada", label: "Canceladas" },
];

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatDate(iso: string): string {
  if (!iso) return "—";
  const d = iso.slice(0, 10);
  const [y, m, day] = d.split("-");
  return `${day}/${m}/${y}`;
}

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

export function AgendaPage() {
  const toast = useToast();
  const { user } = useAuth();
  const canAssign = user?.rol === "Admin" || user?.rol === "Coordinador";
  const [params, setParams] = useSearchParams();
  const tabFromUrl = (params.get("estado") as EstadoAgenda | null) || "programada";
  const initialTab: EstadoAgenda =
    tabFromUrl === "realizada" || tabFromUrl === "cancelada" || tabFromUrl === "programada"
      ? tabFromUrl
      : "programada";
  const [tab, setTab] = useState<EstadoAgenda>(initialTab);
  const [items, setItems] = useState<AgendaItem[]>([]);
  const [usuarios, setUsuarios] = useState<UsuarioAsignable[]>([]);
  const [usuarioId, setUsuarioId] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [editFecha, setEditFecha] = useState("");
  const [editUsuario, setEditUsuario] = useState(0);
  const [editNotas, setEditNotas] = useState("");
  const [cancelarItem, setCancelarItem] = useState<AgendaItem | null>(null);
  const [realizarItem, setRealizarItem] = useState<AgendaItem | null>(null);
  const [timelineId, setTimelineId] = useState<number | null>(null);
  const [timeline, setTimeline] = useState<AgendaEvento[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineNota, setTimelineNota] = useState<string | null>(null);

  useEffect(() => {
    const fromUrl = params.get("estado");
    if (fromUrl === "programada" || fromUrl === "realizada" || fromUrl === "cancelada") {
      setTab(fromUrl);
    }
  }, [params]);

  const load = () => {
    setLoading(true);
    setError(null);
    fetchAgenda({
      estado: tab,
      desde: desde || undefined,
      hasta: hasta || undefined,
      usuarioId: usuarioId || undefined,
    })
      .then((res) => setItems(res.items))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "No se pudo cargar la agenda");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, desde, hasta, usuarioId]);

  useEffect(() => {
    if (!canAssign) return;
    fetchUsuariosAsignables()
      .then(setUsuarios)
      .catch(() => undefined);
  }, [canAssign]);

  const emptyHint = useMemo(() => {
    if (tab === "programada") return "No hay visitas programadas. Programalas desde Priorización.";
    if (tab === "realizada") return "Todavía no hay visitas realizadas.";
    return "No hay visitas canceladas.";
  }, [tab]);

  function startEdit(item: AgendaItem) {
    setEditId(item.id);
    setEditFecha(item.fechaPlanificada.slice(0, 10));
    setEditUsuario(item.usuarioId);
    setEditNotas(item.notas ?? "");
    setError(null);
  }

  async function toggleTimeline(id: number) {
    if (timelineId === id) {
      setTimelineId(null);
      setTimeline([]);
      setTimelineNota(null);
      return;
    }
    setTimelineId(id);
    setTimelineLoading(true);
    setTimelineNota(null);
    try {
      const res = await fetchAgendaEventos(id);
      setTimeline(res.items);
      setTimelineNota(res.nota);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo cargar la cronología");
      setTimelineId(null);
    } finally {
      setTimelineLoading(false);
    }
  }

  async function saveEdit(id: number) {
    setBusyId(id);
    setError(null);
    try {
      await reprogramarVisita(id, {
        fechaPlanificada: editFecha,
        usuarioId: canAssign ? editUsuario : undefined,
        notas: editNotas,
      });
      setEditId(null);
      toast.success("Visita reprogramada");
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo reprogramar");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <div>
        <h1 className="page-title">Agenda de visitas</h1>
        <p className="page-sub">
          Flujo operativo: programar desde la priorización, realizar o cancelar. El ranking no se
          modifica.
        </p>
      </div>

      {cancelarItem && (
        <CancelarVisitaDialog
          item={cancelarItem}
          onClose={() => setCancelarItem(null)}
          onDone={() => {
            setCancelarItem(null);
            toast.success("Visita cancelada", "El establecimiento vuelve a Priorización.");
            load();
          }}
        />
      )}

      {realizarItem && (
        <RealizarVisitaDialog
          item={realizarItem}
          onClose={() => setRealizarItem(null)}
          onDone={() => {
            setRealizarItem(null);
            toast.success("Visita realizada");
            load();
          }}
        />
      )}

      <div className="horizon-toggle" style={{ marginBottom: 12 }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "active" : ""}
            onClick={() => {
              setTab(t.id);
              setEditId(null);
              setCancelarItem(null);
              setRealizarItem(null);
              const next = new URLSearchParams(params);
              next.set("estado", t.id);
              setParams(next, { replace: true });
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="panel filters">
        <div className="field" style={{ minWidth: 150 }}>
          <label>Desde</label>
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </div>
        <div className="field" style={{ minWidth: 150 }}>
          <label>Hasta</label>
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </div>
        {canAssign && (
          <div className="field" style={{ minWidth: 200 }}>
            <label>Responsable</label>
            <select value={usuarioId} onChange={(e) => setUsuarioId(e.target.value)}>
              <option value="">Todos</option>
              {usuarios.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre}
                </option>
              ))}
            </select>
          </div>
        )}
        <button
          type="button"
          className="ghost-btn"
          onClick={() => {
            setDesde("");
            setHasta("");
            setUsuarioId("");
          }}
        >
          Limpiar
        </button>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <SkeletonTable rows={6} />}

      {!loading && items.length === 0 && (
        <div className="panel">
          <EmptyState
            title={emptyHint}
            detail={tab === "programada" ? "Podés programar visitas desde la lista de priorización." : undefined}
            action={
              tab === "programada" ? (
                <Link className="btn" to="/riesgo">
                  Ir a priorización
                </Link>
              ) : undefined
            }
          />
        </div>
      )}

      {items.length > 0 && (
        <div className="table-wrap panel table-sticky" style={{ padding: 0 }}>
          <table className="data">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Establecimiento</th>
                <th>Riesgo origen</th>
                <th>Motivo</th>
                <th>Responsable</th>
                <th>Estado / detalle</th>
                <th>Historial</th>
                {tab === "programada" && <th>Acciones</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <Fragment key={item.id}>
                  <tr>
                    <td className="mono">
                      {editId === item.id ? (
                        <input
                          type="date"
                          min={todayIso()}
                          value={editFecha}
                          onChange={(e) => setEditFecha(e.target.value)}
                        />
                      ) : (
                        formatDate(item.fechaPlanificada)
                      )}
                    </td>
                    <td className="mono" title={item.idEstablecimiento}>
                      <Link to={`/establecimientos/${item.idEstablecimiento}?horizonte=${item.horizonte}`}>
                        {shortId(item.idEstablecimiento)}
                      </Link>
                      {item.rankingOrigen != null && (
                        <div className="muted" style={{ fontSize: 11 }}>
                          origen #{item.rankingOrigen}
                        </div>
                      )}
                    </td>
                    <td>
                      {item.bandaOrigen ? (
                        <span className={`badge ${item.bandaOrigen}`}>{riesgoLabel(item.bandaOrigen)}</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>{motivoLabel(item.motivoOrigen ?? item.motivoVisita)}</td>
                    <td>
                      {editId === item.id && canAssign ? (
                        <select
                          value={editUsuario}
                          onChange={(e) => setEditUsuario(Number(e.target.value))}
                        >
                          {usuarios.map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.nombre}
                            </option>
                          ))}
                        </select>
                      ) : (
                        item.responsable?.nombre ?? "—"
                      )}
                    </td>
                    <td>
                      {item.estado === "realizada" && item.visita && (
                        <span title={item.visita.hallazgos ?? undefined}>
                          Realizada {formatDateTime(item.visita.fechaHoraReal)}
                        </span>
                      )}
                      {item.estado === "cancelada" && (
                        <span title={item.motivoCancelacion ?? undefined}>
                          Cancelada
                          {item.motivoCancelacion ? `: ${item.motivoCancelacion}` : ""}
                        </span>
                      )}
                      {item.estado === "programada" && (
                        editId === item.id ? (
                          <textarea
                            rows={2}
                            value={editNotas}
                            onChange={(e) => setEditNotas(e.target.value)}
                            placeholder="Notas…"
                          />
                        ) : (
                          <span className="badge motivo-predictivo">Programada</span>
                        )
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="ghost-btn"
                        onClick={() => toggleTimeline(item.id)}
                        title="Ver cronología de auditoría"
                      >
                        {timelineId === item.id ? "Ocultar" : "Cronología"}
                      </button>
                    </td>
                    {tab === "programada" && (
                      <td>
                        <div className="row-actions">
                          {editId === item.id ? (
                            <>
                              <button
                                type="button"
                                className="btn"
                                disabled={busyId === item.id}
                                onClick={() => saveEdit(item.id)}
                              >
                                Guardar
                              </button>
                              <button
                                type="button"
                                className="ghost-btn"
                                onClick={() => setEditId(null)}
                              >
                                Descartar
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                type="button"
                                className="btn"
                                disabled={busyId === item.id}
                                onClick={() => {
                                  setRealizarItem(item);
                                }}
                                title="Marcar visita como realizada"
                              >
                                Realizada
                              </button>
                              <button
                                type="button"
                                className="ghost-btn"
                                disabled={busyId === item.id}
                                onClick={() => startEdit(item)}
                                title="Reprogramar fecha o responsable"
                              >
                                Reprogramar
                              </button>
                              <button
                                type="button"
                                className="ghost-btn danger"
                                disabled={busyId === item.id}
                                onClick={() => {
                                  setCancelarItem(item);
                                }}
                                title="Cancelar y devolver a priorización"
                              >
                                Cancelar
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                  {timelineId === item.id && (
                    <tr>
                      <td colSpan={tab === "programada" ? 8 : 7}>
                        {timelineLoading ? (
                          <p className="muted">Cargando cronología…</p>
                        ) : timeline.length === 0 ? (
                          <p className="muted" style={{ margin: 0 }}>
                            {timelineNota ??
                              "Sin eventos de auditoría para esta visita (posible registro anterior a la bitácora)."}
                          </p>
                        ) : (
                          <div className="timeline">
                            {timeline.map((ev) => (
                              <div key={ev.id} className="timeline-item">
                                <strong>{ev.tipo}</strong>{" "}
                                <span className="mono muted">{formatDateTime(ev.ocurridoEn)}</span>
                                <div className="muted" style={{ fontSize: 12 }}>
                                  Actor:{" "}
                                  {ev.actor
                                    ? `${ev.actor.nombre} (${ev.actor.rol})`
                                    : "sin actor (legado)"}
                                  {" · "}
                                  {(ev.estadoAnterior ?? "—") + " → " + (ev.estadoNuevo ?? "—")}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
