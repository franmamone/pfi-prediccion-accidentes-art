import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
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
import { DateField } from "../components/DateField";
import { RealizarVisitaDialog } from "../components/RealizarVisitaDialog";
import { Select } from "../components/Select";
import { EmptyState } from "../components/UiKit";
import { motivoLabel, riesgoLabel } from "../labels";
import { getAgendaVista, setAgendaVista, type AgendaVista } from "../prefs";
import { puedeGestionar } from "../roles";
import { useToast } from "../toast";

type FiltroEstado = EstadoAgenda | "todas";

const WEEKDAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const ESTADO_FILTROS: { id: FiltroEstado; label: string }[] = [
  { id: "programada", label: "Programadas" },
  { id: "realizada", label: "Realizadas" },
  { id: "cancelada", label: "Canceladas" },
  { id: "todas", label: "Todas" },
];

function toIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function todayIso(): string {
  return toIso(new Date());
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function startOfWeek(d: Date): Date {
  const r = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dow = (r.getDay() + 6) % 7; // lunes = 0
  return addDays(r, -dow);
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function monthMatrix(cursor: Date): Date[] {
  const start = startOfWeek(startOfMonth(cursor));
  return Array.from({ length: 42 }, (_, i) => addDays(start, i));
}

function weekDays(cursor: Date): Date[] {
  const start = startOfWeek(cursor);
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

function formatLong(d: Date): string {
  return d.toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function AgendaPage() {
  const toast = useToast();
  const { user } = useAuth();
  const canAssign = puedeGestionar(user?.rol);

  const [vista, setVista] = useState<AgendaVista>(() => getAgendaVista());
  const [cursor, setCursor] = useState<Date>(() => new Date());
  const [filtro, setFiltro] = useState<FiltroEstado>("programada");
  const [usuarioId, setUsuarioId] = useState("");
  const [usuarios, setUsuarios] = useState<UsuarioAsignable[]>([]);

  const [items, setItems] = useState<AgendaItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [realizarItem, setRealizarItem] = useState<AgendaItem | null>(null);
  const [cancelarItem, setCancelarItem] = useState<AgendaItem | null>(null);

  // Reprogramación (solo gestión)
  const [editando, setEditando] = useState(false);
  const [editFecha, setEditFecha] = useState("");
  const [editUsuario, setEditUsuario] = useState(0);
  const [editNotas, setEditNotas] = useState("");
  const [busy, setBusy] = useState(false);

  // Cronología
  const [timeline, setTimeline] = useState<AgendaEvento[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineNota, setTimelineNota] = useState<string | null>(null);
  const [verTimeline, setVerTimeline] = useState(false);

  const rango = useMemo(() => {
    if (vista === "mes") {
      const m = monthMatrix(cursor);
      return { desde: m[0], hasta: m[41] };
    }
    if (vista === "semana") {
      const w = weekDays(cursor);
      return { desde: w[0], hasta: w[6] };
    }
    const dia = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate());
    return { desde: dia, hasta: dia };
  }, [vista, cursor]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchAgenda({
      estado: filtro === "todas" ? undefined : filtro,
      desde: toIso(rango.desde),
      hasta: toIso(rango.hasta),
      usuarioId: usuarioId || undefined,
    })
      .then((res) => setItems(res.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudo cargar la agenda"))
      .finally(() => setLoading(false));
  }, [rango, filtro, usuarioId, reloadKey]);

  useEffect(() => {
    if (!canAssign) return;
    fetchUsuariosAsignables().then(setUsuarios).catch(() => undefined);
  }, [canAssign]);

  const porDia = useMemo(() => {
    const map = new Map<string, AgendaItem[]>();
    for (const it of items) {
      const key = it.fechaPlanificada.slice(0, 10);
      const arr = map.get(key);
      if (arr) arr.push(it);
      else map.set(key, [it]);
    }
    return map;
  }, [items]);

  const selected = useMemo(
    () => items.find((i) => i.id === selectedId) ?? null,
    [items, selectedId],
  );

  useEffect(() => {
    // Al cambiar de ítem seleccionado, resetear edición/cronología.
    setEditando(false);
    setVerTimeline(false);
    setTimeline([]);
    setTimelineNota(null);
  }, [selectedId]);

  function periodoLabel(): string {
    if (vista === "mes") return capitalize(cursor.toLocaleDateString("es-AR", { month: "long", year: "numeric" }));
    if (vista === "semana") {
      const w = weekDays(cursor);
      const a = w[0];
      const b = w[6];
      const fmt = (d: Date) => d.toLocaleDateString("es-AR", { day: "numeric", month: "short" });
      return `${fmt(a)} – ${fmt(b)} ${b.getFullYear()}`;
    }
    return capitalize(formatLong(cursor));
  }

  function step(dir: number) {
    if (vista === "mes") setCursor((c) => new Date(c.getFullYear(), c.getMonth() + dir, 1));
    else if (vista === "semana") setCursor((c) => addDays(c, 7 * dir));
    else setCursor((c) => addDays(c, dir));
  }

  function cambiarVista(v: AgendaVista) {
    setVista(v);
    setAgendaVista(v);
  }

  function abrirDia(d: Date) {
    setCursor(d);
    cambiarVista("dia");
  }

  function startEdit(item: AgendaItem) {
    setEditando(true);
    setEditFecha(item.fechaPlanificada.slice(0, 10));
    setEditUsuario(item.usuarioId);
    setEditNotas(item.notas ?? "");
  }

  async function guardarReprogramacion(item: AgendaItem) {
    setBusy(true);
    try {
      await reprogramarVisita(item.id, {
        fechaPlanificada: editFecha,
        usuarioId: canAssign ? editUsuario : undefined,
        notas: editNotas,
      });
      toast.success("Visita reprogramada");
      setEditando(false);
      setReloadKey((k) => k + 1);
    } catch (err: unknown) {
      toast.error("No se pudo reprogramar", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  }

  async function toggleTimeline(item: AgendaItem) {
    if (verTimeline) {
      setVerTimeline(false);
      return;
    }
    setVerTimeline(true);
    setTimelineLoading(true);
    try {
      const res = await fetchAgendaEventos(item.id);
      setTimeline(res.items);
      setTimelineNota(res.nota);
    } catch {
      setTimelineNota("No se pudo cargar la cronología.");
    } finally {
      setTimelineLoading(false);
    }
  }

  const totalRango = items.length;

  return (
    <div className="agenda-layout">
      {realizarItem && (
        <RealizarVisitaDialog
          item={realizarItem}
          onClose={() => setRealizarItem(null)}
          onDone={() => {
            setRealizarItem(null);
            toast.success("Visita realizada");
            setReloadKey((k) => k + 1);
          }}
        />
      )}
      {cancelarItem && (
        <CancelarVisitaDialog
          item={cancelarItem}
          onClose={() => setCancelarItem(null)}
          onDone={() => {
            setCancelarItem(null);
            toast.success("Visita cancelada");
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      <div className="agenda-topbar">
        <div>
          <h1 className="page-title" style={{ marginBottom: 2 }}>
            {canAssign ? "Agenda de visitas" : "Mi agenda"}
          </h1>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            {totalRango} visita{totalRango === 1 ? "" : "s"} en el período visible
          </p>
        </div>
        <div className="agenda-view-toggle">
          {(["dia", "semana", "mes"] as AgendaVista[]).map((v) => (
            <button
              key={v}
              type="button"
              className={vista === v ? "active" : ""}
              onClick={() => cambiarVista(v)}
            >
              {v === "dia" ? "Día" : v === "semana" ? "Semana" : "Mes"}
            </button>
          ))}
        </div>
      </div>

      <div className="agenda-controls">
        <div className="agenda-nav">
          <button type="button" className="icon-btn" onClick={() => step(-1)} aria-label="Anterior">
            ‹
          </button>
          <button type="button" className="ghost-btn" onClick={() => setCursor(new Date())}>
            Hoy
          </button>
          <button type="button" className="icon-btn" onClick={() => step(1)} aria-label="Siguiente">
            ›
          </button>
          <strong className="agenda-period">{periodoLabel()}</strong>
        </div>

        <div className="agenda-filtros">
          <div className="agenda-estado-chips">
            {ESTADO_FILTROS.map((f) => (
              <button
                key={f.id}
                type="button"
                className={`chip${filtro === f.id ? " active" : ""}`}
                onClick={() => setFiltro(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
          {canAssign && (
            <div style={{ minWidth: 220 }}>
              <Select
                value={usuarioId}
                onChange={setUsuarioId}
                ariaLabel="Filtrar por responsable"
                options={[
                  { value: "", label: "Todos los responsables" },
                  ...usuarios.map((u) => ({ value: String(u.id), label: u.nombre })),
                ]}
              />
            </div>
          )}
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="agenda-body">
        <div className={`agenda-calendar${loading ? " is-loading" : ""}`}>
          {vista === "mes" && (
            <MonthGrid
              cursor={cursor}
              porDia={porDia}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onOpenDay={abrirDia}
            />
          )}
          {vista === "semana" && (
            <WeekView
              cursor={cursor}
              porDia={porDia}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onOpenDay={abrirDia}
            />
          )}
          {vista === "dia" && (
            <DayView cursor={cursor} porDia={porDia} selectedId={selectedId} onSelect={setSelectedId} />
          )}
        </div>

        {selected && (
          <aside className="agenda-drawer panel">
            <div className="agenda-drawer-head">
              <div>
                <span className={`badge ${selected.bandaOrigen ?? "medio"}`}>
                  {riesgoLabel(selected.bandaOrigen ?? "medio")}
                </span>
                <h3 style={{ margin: "8px 0 2px" }}>{shortId(selected.idEstablecimiento)}</h3>
                <p className="muted" style={{ margin: 0, fontSize: 12 }} title={selected.idEstablecimiento}>
                  {selected.idEstablecimiento}
                </p>
              </div>
              <button type="button" className="icon-btn" onClick={() => setSelectedId(null)} aria-label="Cerrar">
                ×
              </button>
            </div>

            <dl className="agenda-drawer-kv">
              <div>
                <dt>Fecha planificada</dt>
                <dd>{selected.fechaPlanificada.slice(0, 10)}</dd>
              </div>
              <div>
                <dt>Motivo</dt>
                <dd>{motivoLabel(selected.motivoOrigen ?? selected.motivoVisita)}</dd>
              </div>
              <div>
                <dt>Estado</dt>
                <dd>
                  <span className={`cal-dot ${selected.estado}`} /> {capitalize(selected.estado)}
                </dd>
              </div>
              {selected.rankingOrigen != null && (
                <div>
                  <dt>Ranking origen</dt>
                  <dd>#{selected.rankingOrigen}</dd>
                </div>
              )}
              {selected.responsable && (
                <div>
                  <dt>Responsable</dt>
                  <dd>{selected.responsable.nombre}</dd>
                </div>
              )}
            </dl>

            {selected.notas && (
              <p className="agenda-notas">
                <span className="muted">Notas:</span> {selected.notas}
              </p>
            )}

            {selected.estado === "realizada" && selected.visita && (
              <div className="agenda-resultado ok">
                Realizada el {formatDateTime(selected.visita.fechaHoraReal)}
                {selected.visita.hallazgos ? ` · ${selected.visita.hallazgos}` : ""}
              </div>
            )}
            {selected.estado === "cancelada" && (
              <div className="agenda-resultado bad">
                Cancelada{selected.motivoCancelacion ? `: ${selected.motivoCancelacion}` : ""}
              </div>
            )}

            {selected.estado === "programada" && editando && canAssign ? (
              <div className="agenda-reprogramar">
                <div className="field">
                  <label>Nueva fecha</label>
                  <DateField
                    ariaLabel="Nueva fecha"
                    min={todayIso()}
                    value={editFecha}
                    onChange={setEditFecha}
                  />
                </div>
                <div className="field">
                  <label>Responsable</label>
                  <Select
                    value={String(editUsuario)}
                    onChange={(v) => setEditUsuario(Number(v))}
                    ariaLabel="Responsable"
                    options={usuarios.map((u) => ({ value: String(u.id), label: u.nombre }))}
                  />
                </div>
                <div className="field">
                  <label>Notas</label>
                  <textarea rows={2} value={editNotas} onChange={(e) => setEditNotas(e.target.value)} />
                </div>
                <div className="row-actions">
                  <button type="button" className="btn" disabled={busy} onClick={() => guardarReprogramacion(selected)}>
                    Guardar
                  </button>
                  <button type="button" className="ghost-btn" onClick={() => setEditando(false)}>
                    Descartar
                  </button>
                </div>
              </div>
            ) : (
              selected.estado === "programada" && (
                <div className="agenda-drawer-actions">
                  <button type="button" className="btn" onClick={() => setRealizarItem(selected)}>
                    Marcar realizada
                  </button>
                  <button type="button" className="ghost-btn danger" onClick={() => setCancelarItem(selected)}>
                    Cancelar
                  </button>
                  {canAssign && (
                    <button type="button" className="ghost-btn" onClick={() => startEdit(selected)}>
                      Reprogramar
                    </button>
                  )}
                </div>
              )
            )}

            <div className="agenda-drawer-links">
              <Link className="btn ghost-btn" to={`/establecimientos/${selected.idEstablecimiento}`}>
                Ver ficha del establecimiento
              </Link>
              <button type="button" className="ghost-btn" onClick={() => toggleTimeline(selected)}>
                {verTimeline ? "Ocultar cronología" : "Ver cronología"}
              </button>
            </div>

            {verTimeline && (
              <div className="agenda-timeline">
                {timelineLoading ? (
                  <p className="muted">Cargando…</p>
                ) : timeline.length === 0 ? (
                  <p className="muted" style={{ margin: 0 }}>
                    {timelineNota ?? "Sin eventos registrados."}
                  </p>
                ) : (
                  timeline.map((ev) => (
                    <div key={ev.id} className="timeline-item">
                      <strong>{ev.tipo}</strong>{" "}
                      <span className="mono muted">{formatDateTime(ev.ocurridoEn)}</span>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {ev.actor ? `${ev.actor.nombre} (${ev.actor.rol})` : "sin actor"}
                        {" · "}
                        {(ev.estadoAnterior ?? "—") + " → " + (ev.estadoNuevo ?? "—")}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </aside>
        )}
      </div>

      {!loading && totalRango === 0 && (
        <div className="panel" style={{ marginTop: 12 }}>
          <EmptyState
            title="Sin visitas en este período"
            detail={
              filtro === "programada"
                ? canAssign
                  ? "Programá visitas desde Priorización o cambiá el período."
                  : "No tenés visitas programadas en este período."
                : "Cambiá el filtro de estado o el período."
            }
          />
        </div>
      )}
    </div>
  );
}

function EventChip({
  item,
  selected,
  onSelect,
}: {
  item: AgendaItem;
  selected: boolean;
  onSelect: (id: number) => void;
}) {
  return (
    <button
      type="button"
      className={`cal-event ${item.estado}${selected ? " selected" : ""}`}
      title={`${shortId(item.idEstablecimiento)} · ${item.estado}`}
      onClick={() => onSelect(item.id)}
    >
      <span className={`cal-dot ${item.estado}`} />
      <span className="cal-event-label">{shortId(item.idEstablecimiento)}</span>
    </button>
  );
}

function MonthGrid({
  cursor,
  porDia,
  selectedId,
  onSelect,
  onOpenDay,
}: {
  cursor: Date;
  porDia: Map<string, AgendaItem[]>;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onOpenDay: (d: Date) => void;
}) {
  const dias = monthMatrix(cursor);
  const mesActual = cursor.getMonth();
  const hoy = toIso(new Date());
  return (
    <div className="cal-month">
      <div className="cal-weekhead">
        {WEEKDAYS.map((w) => (
          <div key={w}>{w}</div>
        ))}
      </div>
      <div className="cal-grid">
        {dias.map((d) => {
          const iso = toIso(d);
          const eventos = porDia.get(iso) ?? [];
          const visibles = eventos.slice(0, 3);
          const resto = eventos.length - visibles.length;
          return (
            <div
              key={iso}
              className={`cal-cell${d.getMonth() === mesActual ? "" : " otro-mes"}${iso === hoy ? " hoy" : ""}`}
            >
              <button type="button" className="cal-daynum" onClick={() => onOpenDay(d)}>
                {d.getDate()}
              </button>
              <div className="cal-events">
                {visibles.map((it) => (
                  <EventChip key={it.id} item={it} selected={it.id === selectedId} onSelect={onSelect} />
                ))}
                {resto > 0 && (
                  <button type="button" className="cal-more" onClick={() => onOpenDay(d)}>
                    +{resto} más
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WeekView({
  cursor,
  porDia,
  selectedId,
  onSelect,
  onOpenDay,
}: {
  cursor: Date;
  porDia: Map<string, AgendaItem[]>;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onOpenDay: (d: Date) => void;
}) {
  const dias = weekDays(cursor);
  const hoy = toIso(new Date());
  return (
    <div className="cal-week">
      {dias.map((d) => {
        const iso = toIso(d);
        const eventos = porDia.get(iso) ?? [];
        return (
          <div key={iso} className={`cal-weekcol${iso === hoy ? " hoy" : ""}`}>
            <button type="button" className="cal-weekhead-day" onClick={() => onOpenDay(d)}>
              <span className="cal-weekhead-dow">{WEEKDAYS[(d.getDay() + 6) % 7]}</span>
              <span className="cal-weekhead-num">{d.getDate()}</span>
            </button>
            <div className="cal-weekcol-events">
              {eventos.length === 0 ? (
                <span className="muted cal-empty">—</span>
              ) : (
                eventos.map((it) => (
                  <EventChip key={it.id} item={it} selected={it.id === selectedId} onSelect={onSelect} />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DayView({
  cursor,
  porDia,
  selectedId,
  onSelect,
}: {
  cursor: Date;
  porDia: Map<string, AgendaItem[]>;
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const iso = toIso(cursor);
  const eventos = porDia.get(iso) ?? [];
  return (
    <div className="cal-day">
      {eventos.length === 0 ? (
        <p className="muted" style={{ padding: 16 }}>
          No hay visitas para este día.
        </p>
      ) : (
        eventos.map((it) => (
          <button
            key={it.id}
            type="button"
            className={`cal-day-row${it.id === selectedId ? " selected" : ""}`}
            onClick={() => onSelect(it.id)}
          >
            <span className={`cal-dot ${it.estado}`} />
            <span className="cal-day-est">{shortId(it.idEstablecimiento)}</span>
            <span className="muted">{motivoLabel(it.motivoOrigen ?? it.motivoVisita)}</span>
            <span className={`badge ${it.bandaOrigen ?? "medio"}`}>{riesgoLabel(it.bandaOrigen ?? "medio")}</span>
          </button>
        ))
      )}
    </div>
  );
}
