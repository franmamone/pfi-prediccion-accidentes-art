import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  fetchCandidatosAsignacion,
  programarVisita,
  shortId,
  type CandidatoAsignacion,
  type Horizonte,
  type RankingItem,
} from "../api";
import { useAuth } from "../auth";
import { useLockBodyScroll } from "../hooks/useLockBodyScroll";
import { motivoLabel, riesgoLabel } from "../labels";
import { puedeGestionar } from "../roles";
import { AsignacionMap } from "./AsignacionMap";
import { DateField } from "./DateField";
import { TimeField } from "./TimeField";

type Props = {
  item: RankingItem;
  horizonte: Horizonte;
  onClose: () => void;
  onDone: () => void;
};

function todayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function horasDe(c: CandidatoAsignacion | undefined): string[] {
  return (c?.huecosDisponibles ?? []).map((h) => h.slice(0, 5));
}

function anclaLabel(origen: string | undefined): string {
  switch (origen) {
    case "visita_anterior":
      return "desde visita anterior";
    case "visita_siguiente":
      return "desde visita siguiente";
    case "visita_ruta":
      return "desde ruta del día";
    default:
      return "desde base";
  }
}

export function ProgramarVisitaDialog({ item, horizonte, onClose, onDone }: Props) {
  useLockBodyScroll(true);
  const { user } = useAuth();
  const canAssign = puedeGestionar(user?.rol);
  const [fecha, setFecha] = useState(todayIso());
  const [hora, setHora] = useState("09:00");
  const [usuarioId, setUsuarioId] = useState<number>(user?.id ?? 0);
  const [hoverId, setHoverId] = useState<number | null>(null);
  const [notas, setNotas] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loadingCand, setLoadingCand] = useState(false);
  const [candidatos, setCandidatos] = useState<CandidatoAsignacion[]>([]);
  const [recomendadoId, setRecomendadoId] = useState<number | null>(null);
  const [gapHoras, setGapHoras] = useState(2);
  const [tamanoEst, setTamanoEst] = useState<string | null>(null);
  const [establecimiento, setEstablecimiento] = useState<{
    latitud: number;
    longitud: number;
  } | null>(null);

  useEffect(() => {
    if (!canAssign) {
      setUsuarioId(user?.id ?? 0);
      return;
    }
    let cancelled = false;
    setLoadingCand(true);
    setError(null);
    // La hora afecta ancla (visita anterior/siguiente) y disponibilidad en ese slot.
    fetchCandidatosAsignacion(fecha, hora || "09:00", item.idEstablecimiento)
      .then((res) => {
        if (cancelled) return;
        setCandidatos(res.candidatos);
        setRecomendadoId(res.recomendadoId);
        setEstablecimiento(res.establecimiento);
        setGapHoras(res.gapHoras ?? res.establecimiento.duracionEstimadaHoras ?? 2);
        setTamanoEst(res.establecimiento.tamano ?? null);
        setUsuarioId((prev) => {
          if (prev && res.candidatos.some((c) => c.id === prev)) return prev;
          return res.recomendadoId ?? res.candidatos[0]?.id ?? 0;
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setCandidatos([]);
        setEstablecimiento(null);
        setTamanoEst(null);
        setError(err instanceof Error ? err.message : "No se pudieron cargar candidatos");
      })
      .finally(() => {
        if (!cancelled) setLoadingCand(false);
      });
    return () => {
      cancelled = true;
    };
  }, [fecha, hora, item.idEstablecimiento, canAssign, user?.id]);

  const focoId = hoverId ?? usuarioId;
  const foco = useMemo(
    () => candidatos.find((c) => c.id === focoId),
    [candidatos, focoId],
  );
  const horasDisponibles = useMemo(() => horasDe(foco), [foco]);
  const seleccion = candidatos.find((c) => c.id === usuarioId);
  const recomendado = candidatos.find((c) => c.id === recomendadoId) ?? candidatos[0];
  const horaValidaSeleccion = !!seleccion && horasDe(seleccion).includes(hora);

  useEffect(() => {
    if (horasDisponibles.length === 0) return;
    if (!horasDisponibles.includes(hora)) {
      setHora(horasDisponibles[0]);
    }
  }, [focoId, horasDisponibles, hora]);

  function elegirPreventor(id: number) {
    setUsuarioId(id);
    setHoverId(null);
    const c = candidatos.find((x) => x.id === id);
    const horas = horasDe(c);
    if (horas.length > 0 && !horas.includes(hora)) {
      setHora(horas[0]);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!fecha) {
      setError("Elegí una fecha planificada.");
      return;
    }
    if (!usuarioId) {
      setError("Elegí un responsable disponible.");
      return;
    }
    if (canAssign && seleccion && !horasDe(seleccion).includes(hora)) {
      setError(`Elegí una hora disponible para ${seleccion.nombre}.`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await programarVisita({
        rankingItemId: item.id,
        fechaPlanificada: fecha,
        horaPlanificada: hora,
        horizonte,
        usuarioId: usuarioId || undefined,
        notas: notas.trim() || undefined,
      });
      onDone();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo programar la visita");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <div
        className="modal panel programar-modal programar-modal-wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="programar-title"
      >
        <div className="programar-modal-head">
          <h2 id="programar-title" className="page-title programar-modal-title">
            Programar visita
          </h2>
          <p className="page-sub programar-modal-sub">
            {shortId(item.idEstablecimiento)} · #{item.ranking} · {riesgoLabel(item.banda)} ·{" "}
            {motivoLabel(item.motivo)}
          </p>
        </div>

        <form onSubmit={submit} className="form-stack programar-form">
          <div className="programar-modal-scroll">
            <div className="fecha-hora-row">
              <div className="field">
                <label htmlFor="fecha-planificada">Fecha</label>
                <DateField
                  ariaLabel="Fecha planificada"
                  min={todayIso()}
                  value={fecha}
                  onChange={setFecha}
                />
              </div>
              <div className="field">
                <label htmlFor="hora-planificada">Hora</label>
                <TimeField
                  ariaLabel="Hora planificada"
                  value={hora}
                  onChange={setHora}
                  allowedHours={canAssign ? horasDisponibles : undefined}
                  disabled={canAssign && horasDisponibles.length === 0}
                />
              </div>
            </div>

            {canAssign ? (
              <>
                {recomendado && (
                  <div className="recomendado-banner">
                    Recomendado: {recomendado.nombre} ({recomendado.distanciaKm} km{" "}
                    {anclaLabel(recomendado.anclaOrigen)}
                    {horasDe(recomendado).includes(hora) ? `, disponible a las ${hora}` : ""})
                  </div>
                )}
                <p className="muted" style={{ margin: 0, fontSize: 12 }}>
                  Duración estimada de esta visita: {gapHoras} h
                  {tamanoEst ? ` (${tamanoEst})` : ""} por cápitas. Distancia desde la visita
                  anterior del día si ya hay agenda; si no, desde la base. El combo Hora muestra
                  huecos del preventor (sin solapar duraciones).
                </p>
                {loadingCand ? (
                  <p className="muted">Buscando preventores disponibles…</p>
                ) : candidatos.length === 0 ? (
                  <div className="error">
                    No hay preventores con huecos libres ese día (franja laboral + duración estimada
                    de {gapHoras} h).
                  </div>
                ) : (
                  <div className="asignacion-layout">
                    {/* Lista antes que el mapa en el DOM: en móvil Leaflet no puede taparla al montarse. */}
                    <ul
                      className="candidatos-list"
                      onMouseLeave={() => setHoverId(null)}
                      onWheel={(e) => e.stopPropagation()}
                    >
                      {candidatos.map((c) => (
                        <li key={c.id}>
                          <div
                            className={
                              c.id === usuarioId
                                ? "candidato-item is-selected"
                                : c.id === hoverId
                                  ? "candidato-item is-hover"
                                  : "candidato-item"
                            }
                            onMouseEnter={() => setHoverId(c.id)}
                          >
                            <button
                              type="button"
                              className="candidato-pick"
                              onClick={() => elegirPreventor(c.id)}
                            >
                              <span className="candidato-name">
                                {c.nombre}
                                {c.id === recomendadoId ? " · top" : ""}
                              </span>
                              <span className="candidato-meta">
                                {c.distanciaKm} km {anclaLabel(c.anclaOrigen)} ·{" "}
                                {c.horasCargaDia ?? 0} h cargadas
                                {c.visitasDelDia > 0 ? ` (${c.visitasDelDia})` : ""}
                                {c.horasOcupadas.length > 0
                                  ? ` · ${c.horasOcupadas.join(", ")}`
                                  : ""}
                              </span>
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                    {establecimiento && (
                      <AsignacionMap
                        key={`map-${fecha}-${item.idEstablecimiento}`}
                        establecimiento={establecimiento}
                        candidatos={candidatos}
                        seleccionadoId={usuarioId}
                        recomendadoId={recomendadoId}
                        onSelect={elegirPreventor}
                      />
                    )}
                  </div>
                )}
              </>
            ) : (
              <p className="muted">Se asignará a tu usuario ({user?.nombre}).</p>
            )}

            <div className="field">
              <label htmlFor="notas">Notas (opcional)</label>
              <textarea
                id="notas"
                rows={3}
                value={notas}
                onChange={(e) => setNotas(e.target.value)}
                placeholder="Observaciones para el preventor…"
              />
            </div>

            {error && <div className="error">{error}</div>}
          </div>

          <div className="modal-actions programar-modal-foot">
            <button type="button" className="ghost-btn" onClick={onClose} disabled={saving}>
              Cancelar
            </button>
            <button
              type="submit"
              className="btn success"
              disabled={
                saving ||
                !usuarioId ||
                (canAssign && (candidatos.length === 0 || !horaValidaSeleccion))
              }
            >
              {saving ? "Guardando…" : "Programar visita"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
