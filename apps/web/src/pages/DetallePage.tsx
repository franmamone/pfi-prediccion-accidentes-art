import { useEffect, useState, type ReactElement } from "react";
import { Link, useParams } from "react-router-dom";
import {
  eliminarCopilotoGuardado,
  fetchAuditoriaAgenda,
  fetchCopilotoGuardados,
  fetchDossier,
  fetchEstablecimiento,
  guardarCopilotoRespuesta,
  preguntarCopiloto,
  HORIZONTE_OPERATIVO,
  type AgendaEvento,
  type CopilotoGuardado,
  type CopilotoRespuesta,
  type DetalleEstablecimiento,
  type DossierEstablecimiento,
} from "../api";
import { useAuth } from "../auth";
import { ciiuDivisionLabel } from "../ciiu";
import { help, tipMotivo, tipRiesgo } from "../columnHelp";
import { InfoHint } from "../components/InfoHint";
import { ProgramarVisitaDialog } from "../components/ProgramarVisitaDialog";
import { Reveal, SkeletonPanel, SkeletonStats } from "../components/UiKit";
import { IconArrowLeft, IconBookmark, IconBookmarkFilled, IconCalendar, IconTrash } from "../icons";
import { motivoBadgeClass, motivoLabel, riesgoLabel } from "../labels";
import {
  setDetalleTab,
  type DetalleSectionKey,
} from "../prefs";
import { useToast } from "../toast";

type InfoKey = "shap" | "acierto" | null;

export function DetallePage() {
  const toast = useToast();
  const { user } = useAuth();
  const esPreventor = user?.rol === "Prevencionista";
  const { id = "" } = useParams();
  const horizonte = HORIZONTE_OPERATIVO;
  const [data, setData] = useState<DetalleEstablecimiento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showProgramar, setShowProgramar] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [openInfo, setOpenInfo] = useState<InfoKey>(null);
  const [tab, setTab] = useState<DetalleSectionKey>("historial");
  const [dossier, setDossier] = useState<DossierEstablecimiento | null>(null);
  const [copilotoPregunta, setCopilotoPregunta] = useState("");
  const [copilotoUltimaPregunta, setCopilotoUltimaPregunta] = useState("");
  const [copilotoLoading, setCopilotoLoading] = useState(false);
  const [copilotoError, setCopilotoError] = useState<string | null>(null);
  const [copilotoResp, setCopilotoResp] = useState<CopilotoRespuesta | null>(null);
  const [copilotoGuardando, setCopilotoGuardando] = useState(false);
  const [guardados, setGuardados] = useState<CopilotoGuardado[]>([]);
  const [guardadosLoading, setGuardadosLoading] = useState(false);
  const [guardadoSeleccionadoId, setGuardadoSeleccionadoId] = useState<number | null>(null);
  const [movimientos, setMovimientos] = useState<AgendaEvento[]>([]);

  type CopilotoChip = {
    label: string;
    tema: string;
    kind: "normativa" | "accidentes";
    pregunta?: string;
  };

  const copilotoChips: CopilotoChip[] = [
    {
      label: "Qué verificar (RGRL)",
      pregunta: "¿Qué debo verificar en esta visita según el RGRL?",
      tema: "rgrl_checklist",
      kind: "normativa",
    },
    {
      label: "Accidentes previos",
      pregunta:
        "Armame un briefing de accidentes previos de este establecimiento para preparar la visita: patrones, gravedad e incumplimientos recurrentes.",
      tema: "accidentes_previos",
      kind: "accidentes",
    },
    {
      label: "Frecuencia de visitas",
      pregunta: "¿Qué frecuencia de visita aplica según la normativa?",
      tema: "visitas_frecuencia",
      kind: "normativa",
    },
    {
      label: "Obligaciones PESE/PRS",
      pregunta: "Si el establecimiento está en PESE o tiene PRS, ¿qué obligaciones hay?",
      tema: "pese",
      kind: "normativa",
    },
    {
      label: "RAR / exámenes",
      pregunta: "¿Qué implica el RAR y los exámenes médicos periódicos?",
      tema: "rar_examenes",
      kind: "normativa",
    },
  ];

  /** Preguntas típicas de un preventor. Sin `tema`: cada una se cachea y responde por su texto. */
  const copilotoEjemplos: { pregunta: string }[] = [
    {
      pregunta: "Mañana visito este establecimiento: ¿qué 8 puntos del RGRL no me puedo olvidar de verificar?",
    },
    {
      pregunta: "Encontré andamios sin baranda: ¿qué le reclamo al empleador y con qué respaldo normativo?",
    },
    {
      pregunta: "¿Cómo armo el recorrido de la visita si hay historial de caídas y cortes?",
    },
    {
      pregunta: "El empleador dice que ya tiene HyS: ¿qué documentación le pido para comprobarlo en la visita?",
    },
    {
      pregunta: "¿Cada cuánto tengo que volver a este tipo de establecimiento y qué dejo asentado al salir?",
    },
    {
      pregunta: "Está en PESE/PRS: ¿qué tengo que controlar sí o sí en esta visita y qué denuncio si no cumple?",
    },
    {
      pregunta: "Hay ruido fuerte en planta: ¿qué miro en campo y qué tiene que ver el RAR / exámenes periódicos?",
    },
    {
      pregunta: "Cierro la visita con observaciones: ¿qué le comunico al empleador y qué plazos puedo plantear?",
    },
  ];

  // Al abrir un establecimiento, siempre entrar por Historial de accidentes.
  useEffect(() => {
    setTab("historial");
    setDetalleTab("historial");
  }, [id]);

  useEffect(() => {
    let alive = true;
    setMovimientos([]);
    fetchAuditoriaAgenda({ idEstablecimiento: id, pageSize: 100 })
      .then((res) => {
        if (alive) setMovimientos(res.items);
      })
      .catch(() => {
        if (alive) setMovimientos([]);
      });
    return () => {
      alive = false;
    };
  }, [id, reloadKey]);

  useEffect(() => {
    let alive = true;
    setError(null);
    setOpenInfo(null);
    setLoading(true);
    fetchEstablecimiento(id, horizonte)
      .then((res) => {
        if (alive) setData(res);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "No se pudo cargar");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [id, horizonte, reloadKey]);

  useEffect(() => {
    let alive = true;
    setDossier(null);
    setCopilotoResp(null);
    setCopilotoError(null);
    setCopilotoPregunta("");
    setCopilotoUltimaPregunta("");
    setGuardados([]);
    setGuardadoSeleccionadoId(null);
    fetchDossier(id, horizonte)
      .then((res) => {
        if (!alive) return;
        setDossier(res);
      })
      .catch(() => {
        if (alive) setDossier({ disponible: false });
      });
    return () => {
      alive = false;
    };
  }, [id, horizonte]);

  useEffect(() => {
    let alive = true;
    setGuardadosLoading(true);
    fetchCopilotoGuardados(id)
      .then((res) => {
        if (!alive) return;
        setGuardados(res.items);
        setGuardadoSeleccionadoId((prev) => {
          if (prev != null && res.items.some((g) => g.id === prev)) return prev;
          return res.items[0]?.id ?? null;
        });
      })
      .catch(() => {
        if (alive) setGuardados([]);
      })
      .finally(() => {
        if (alive) setGuardadosLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [id]);

  async function handleCopiloto(pregunta: string, tema?: string, regenerar = false) {
    const q = pregunta.trim();
    if (q.length < 5) {
      setCopilotoError("Escribí una pregunta un poco más concreta.");
      return;
    }
    setCopilotoLoading(true);
    setCopilotoError(null);
    setCopilotoUltimaPregunta(q);
    setCopilotoPregunta("");
    try {
      const res = await preguntarCopiloto(id, {
        pregunta: q,
        tema,
        refrescar: regenerar,
      });
      setCopilotoResp(res);
      if (res.sinFundamento) {
        toast.info("Sin fundamento suficiente en el corpus");
      } else if (res.desdeCache) {
        toast.info("Respuesta recuperada");
      } else {
        toast.success(regenerar ? "Respuesta regenerada" : "Respuesta generada");
      }
    } catch (err) {
      // Si falló, devolver el texto al campo para que pueda reintentar.
      setCopilotoPregunta(q);
      setCopilotoError(err instanceof Error ? err.message : "No se pudo consultar el copiloto.");
    } finally {
      setCopilotoLoading(false);
    }
  }

  function handleChip(chip: CopilotoChip, regenerar = false) {
    // Accidentes previos va por copiloto (sección propia + caché), no por Resumen IA.
    void handleCopiloto(chip.pregunta ?? "", chip.tema, regenerar);
  }

  const guardadoActivoId =
    copilotoResp &&
    guardados.find(
      (g) =>
        g.pregunta === copilotoUltimaPregunta &&
        g.respuesta === copilotoResp.respuesta,
    )?.id;

  async function handleGuardarRespuesta() {
    if (!copilotoResp || !copilotoUltimaPregunta.trim()) {
      toast.info("No hay respuesta para guardar");
      return;
    }
    setCopilotoGuardando(true);
    try {
      const saved = await guardarCopilotoRespuesta(id, {
        pregunta: copilotoUltimaPregunta,
        respuesta: copilotoResp.respuesta,
        tema: copilotoResp.tema,
        seccion: copilotoResp.seccion,
        modelo: copilotoResp.modelo,
      });
      setGuardados((prev) => {
        const sinDup = prev.filter((g) => g.id !== saved.id && g.pregunta !== saved.pregunta);
        return [saved, ...sinDup];
      });
      setGuardadoSeleccionadoId(saved.id);
      toast.success(saved.actualizado ? "Respuesta actualizada" : "Respuesta guardada");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setCopilotoGuardando(false);
    }
  }

  async function handleEliminarGuardado(guardadoId: number) {
    try {
      await eliminarCopilotoGuardado(id, guardadoId);
      setGuardados((prev) => {
        const next = prev.filter((g) => g.id !== guardadoId);
        setGuardadoSeleccionadoId((sel) => {
          if (sel !== guardadoId) return sel;
          return next[0]?.id ?? null;
        });
        return next;
      });
      toast.success("Respuesta eliminada");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo eliminar");
    }
  }

  const item = data?.item;

  const toggleInfo = (key: Exclude<InfoKey, null>) => {
    setOpenInfo((current) => (current === key ? null : key));
  };

  const tabs: { key: DetalleSectionKey; label: string; count?: number }[] = [];
  if (dossier?.disponible && dossier.accidentes) {
    tabs.push({ key: "historial", label: "Historial de accidentes", count: dossier.accidentes.total });
  }
  tabs.push({ key: "copiloto", label: "Copiloto normativo" });
  tabs.push({ key: "guardadas", label: "Guardadas", count: guardados.length || undefined });
  tabs.push({ key: "ficha", label: "Ficha operativa" });
  if (data?.factoresShap) {
    tabs.push({ key: "shap", label: "Factores de priorización" });
  }
  tabs.push({ key: "movimientos", label: "Historial de cambios", count: movimientos.length });
  const activeTab: DetalleSectionKey = tabs.some((t) => t.key === tab)
    ? tab
    : tabs[0]?.key ?? "ficha";

  function selectTab(key: DetalleSectionKey) {
    setTab(key);
    setDetalleTab(key);
  }

  return (
    <>
      <div>
        <Link
          to="/riesgo"
          className="icon-btn"
          title="Volver a priorización"
          aria-label="Volver a priorización"
          style={{ width: "auto", gap: 8, padding: "0 10px" }}
        >
          <IconArrowLeft size={16} />
          <span className="muted">Priorización</span>
        </Link>
        <h1 className="page-title" style={{ marginTop: 8 }}>
          Establecimiento
        </h1>
        <p className="page-sub mono">{id}</p>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && (
        <>
          <SkeletonPanel lines={2} />
          <SkeletonStats />
          <SkeletonPanel lines={5} />
        </>
      )}

      {item && data && showProgramar && (
        <ProgramarVisitaDialog
          item={item}
          horizonte={horizonte}
          onClose={() => setShowProgramar(false)}
          onDone={() => {
            setShowProgramar(false);
            toast.success("Visita programada", "Ya está disponible en Agenda.");
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {item && data && (
        <>
          <div className="panel">
            <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
              <span className={`badge pop-in ${item.banda}`} title={tipRiesgo(item.banda, item.ranking)}>
                {riesgoLabel(item.banda)}
              </span>
              {item.motivo && (
                <span className={`badge pop-in ${motivoBadgeClass(item.motivo)}`} title={tipMotivo(item.motivo)}>
                  {motivoLabel(item.motivo)}
                </span>
              )}
              <span className="mono" title={help("ranking")}>
                #{item.ranking}
              </span>
              {data.aciertoHistorico.disponible && data.aciertoHistorico.porcentaje != null && (
                <span className="score-with-info">
                  <span className="acierto-chip mono">
                    {data.aciertoHistorico.porcentaje.toFixed(1)}%
                    <span className="acierto-chip-label"> {data.aciertoHistorico.etiqueta}</span>
                  </span>
                  <InfoHint
                    title="Acierto histórico del modelo"
                    body={data.aciertoHistorico.detalle}
                    footer={`Percentil ${data.contexto.percentilScore.toFixed(1)} · Promedio lista ${data.contexto.promedioScore.toFixed(3)} · Total ${data.contexto.totalEnRanking} · Holdout ${data.aciertoHistorico.holdoutAnio}`}
                    open={openInfo === "acierto"}
                    onToggle={() => toggleInfo("acierto")}
                  />
                </span>
              )}
              <span className="muted">
                período {data.periodo} · trimestre próximo
              </span>
              {data.agendaActiva ? (
                <Link className="badge motivo-prs" to="/agenda" title="Ver en Agenda">
                  Programada · {data.agendaActiva.fechaPlanificada.slice(0, 10)}
                </Link>
              ) : (
                !esPreventor && (
                  <button
                    type="button"
                    className="btn"
                    style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                    onClick={() => setShowProgramar(true)}
                  >
                    <IconCalendar size={16} />
                    Programar visita
                  </button>
                )
              )}
            </div>
            {data.visitaAppReciente && (
              <p className="page-sub" style={{ marginBottom: 0 }}>
                Visita realizada en app el{" "}
                {new Date(data.visitaAppReciente.fechaHoraReal).toLocaleString("es-AR")} (cuenta como
                visita reciente).
              </p>
            )}
          </div>

          <div className="stats-tabs" role="tablist" aria-label="Secciones del establecimiento">
            {tabs.map((t) => (
              <button
                key={t.key}
                role="tab"
                type="button"
                aria-selected={activeTab === t.key}
                className={`stats-tab${activeTab === t.key ? " active" : ""}`}
                onClick={() => selectTab(t.key)}
              >
                {t.label}
                {t.count != null ? <span className="stats-tab-count"> ({t.count})</span> : null}
              </button>
            ))}
          </div>

          <div className="panel detail-tab-panel">
            {activeTab === "historial" && dossier?.disponible && dossier.accidentes && (
              <>
                <div className="stats" style={{ marginBottom: 12 }}>
                  <div className="stat">
                    <div className="label">Accidentes (total)</div>
                    <div className="value mono">{dossier.accidentes.total}</div>
                  </div>
                  <div className="stat">
                    <div className="label">Últimos 12 meses</div>
                    <div className="value mono">{dossier.accidentes.ultimos_12m}</div>
                  </div>
                </div>

                {Object.keys(dossier.accidentes.por_anio ?? {}).length > 0 && (
                  <div className="anio-bars">
                    {Object.entries(dossier.accidentes.por_anio).map(([anio, n]) => {
                      const max = Math.max(1, ...Object.values(dossier.accidentes!.por_anio));
                      return (
                        <div key={anio} className="anio-bar">
                          <span className="anio-bar-label mono">{anio}</span>
                          <div className="anio-bar-track">
                            <div className="anio-bar-fill" style={{ width: `${(n / max) * 100}%` }} />
                          </div>
                          <span className="anio-bar-val mono">{n}</span>
                        </div>
                      );
                    })}
                  </div>
                )}

                <div className="cat-groups">
                  {(
                    [
                      ["Formas de accidente", dossier.accidentes.top_forma],
                      ["Zonas del cuerpo", dossier.accidentes.top_zona],
                      ["Naturaleza de la lesión", dossier.accidentes.top_naturaleza],
                      ["Gravedad", dossier.accidentes.top_gravedad],
                    ] as const
                  )
                    .filter(([, arr]) => arr && arr.length > 0)
                    .map(([titulo, arr]) => (
                      <div className="cat-group" key={titulo}>
                        <h4>{titulo}</h4>
                        <div className="chips">
                          {arr.map((c) => (
                            <span className="chip" key={`${titulo}-${c.k}`}>
                              {c.k} <b className="mono">{c.n}</b>
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                </div>
              </>
            )}

            {activeTab === "copiloto" && (
              <>
                <p className="muted" style={{ marginTop: 0, marginBottom: 12, fontSize: 13 }}>
                  Chips de normativa (RGRL, PESE, RAR) y resumen de accidentes previos del establecimiento.
                  No es asesoramiento legal: el preventor confirma en campo.
                </p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                  {copilotoChips.map((chip) => {
                    const activa = copilotoResp?.seccion === chip.tema;
                    return (
                      <button
                        key={chip.tema + chip.label}
                        type="button"
                        className={activa ? "btn" : "ghost-btn"}
                        disabled={copilotoLoading}
                        onClick={() => handleChip(chip, false)}
                      >
                        {chip.label}
                      </button>
                    );
                  })}
                </div>
                <div className="form-stack" style={{ marginBottom: 12 }}>
                  <div className="field">
                    <label htmlFor="copiloto-pregunta">Tu pregunta</label>
                    <textarea
                      id="copiloto-pregunta"
                      rows={2}
                      placeholder="Ej.: Mañana visito: ¿qué puntos del RGRL priorizo?"
                      value={copilotoPregunta}
                      disabled={copilotoLoading}
                      onChange={(e) => setCopilotoPregunta(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key !== "Enter" || e.shiftKey) return;
                        e.preventDefault();
                        if (copilotoLoading) return;
                        void handleCopiloto(copilotoPregunta, undefined, false);
                      }}
                    />
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn"
                      disabled={copilotoLoading}
                      onClick={() => void handleCopiloto(copilotoPregunta, undefined, false)}
                    >
                      {copilotoLoading ? "Consultando…" : "Preguntar"}
                    </button>
                    {copilotoResp && (
                      <button
                        type="button"
                        className="ghost-btn"
                        disabled={copilotoLoading}
                        onClick={() => {
                          const chip = copilotoChips.find((c) => c.tema === copilotoResp.seccion);
                          if (chip) {
                            handleChip(chip, true);
                            return;
                          }
                          void handleCopiloto(
                            copilotoPregunta.trim() || copilotoUltimaPregunta,
                            undefined,
                            true,
                          );
                        }}
                      >
                        Regenerar
                      </button>
                    )}
                  </div>
                </div>
                {copilotoError && <div className="error" style={{ marginBottom: 10 }}>{copilotoError}</div>}
                {copilotoLoading && (
                  <p className="muted copiloto-escribiendo" style={{ marginBottom: 12, fontSize: 13 }}>
                    El copiloto está preparando la respuesta…
                  </p>
                )}
                {copilotoResp && !copilotoLoading && (
                  <div className="copiloto-respuesta" style={{ marginBottom: 16 }}>
                    <div className="copiloto-respuesta-toolbar">
                      <button
                        type="button"
                        className={`copiloto-save-btn${guardadoActivoId ? " is-saved" : ""}`}
                        disabled={copilotoGuardando}
                        title={
                          guardadoActivoId
                            ? "Ya está en Guardadas (tocá para actualizar)"
                            : "Guardar para la visita"
                        }
                        aria-label={
                          guardadoActivoId ? "Respuesta guardada" : "Guardar respuesta"
                        }
                        onClick={() => void handleGuardarRespuesta()}
                      >
                        {guardadoActivoId ? (
                          <IconBookmarkFilled size={15} />
                        ) : (
                          <IconBookmark size={15} />
                        )}
                        <span>{guardadoActivoId ? "Guardada" : "Guardar"}</span>
                      </button>
                    </div>
                    <TypewriterIa
                      key={`${copilotoResp.seccion}-${copilotoResp.generadoEn ?? ""}-${copilotoResp.desdeCache ? "cache" : "new"}`}
                      texto={copilotoResp.respuesta}
                      animar={!copilotoResp.desdeCache}
                    />
                  </div>
                )}
                <div className="copiloto-ejemplos" style={{ marginBottom: 8 }}>
                  <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                    Preguntas útiles para el preventor (tocá una para enviar):
                  </div>
                  <ul className="copiloto-ejemplos-list">
                    {copilotoEjemplos.map((ej) => (
                      <li key={ej.pregunta}>
                        <button
                          type="button"
                          className="copiloto-ejemplo-btn"
                          disabled={copilotoLoading}
                          onClick={() => void handleCopiloto(ej.pregunta, undefined, false)}
                        >
                          {ej.pregunta}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            )}

            {activeTab === "guardadas" && (
              <div className="guardadas-layout">
                <div className="guardadas-card">
                  <div className="guardadas-card-head">
                    <h3>Preguntas guardadas</h3>
                    <span className="muted" style={{ fontSize: 12 }}>
                      {guardados.length} {guardados.length === 1 ? "ítem" : "ítems"}
                    </span>
                  </div>
                  {guardadosLoading ? (
                    <p className="muted" style={{ fontSize: 13, margin: 0 }}>
                      Cargando…
                    </p>
                  ) : guardados.length === 0 ? (
                    <p className="muted" style={{ fontSize: 13, margin: 0, lineHeight: 1.45 }}>
                      Todavía no guardaste respuestas. En el Copiloto normativo, tocá{" "}
                      <strong>Guardar</strong> arriba de una respuesta que te sirva para la visita.
                    </p>
                  ) : (
                    <ul className="guardadas-list">
                      {guardados.map((g) => {
                        const activa = g.id === guardadoSeleccionadoId;
                        return (
                          <li key={g.id}>
                            <button
                              type="button"
                              className={`guardadas-list-item${activa ? " active" : ""}`}
                              onClick={() => setGuardadoSeleccionadoId(g.id)}
                            >
                              <span className="guardadas-list-q">{g.pregunta}</span>
                              <span className="guardadas-list-meta muted">
                                {new Date(g.guardadoEn).toLocaleString("es-AR", {
                                  day: "2-digit",
                                  month: "2-digit",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
                <div className="guardadas-card guardadas-detail">
                  <div className="guardadas-card-head">
                    <h3>Respuesta</h3>
                    {guardadoSeleccionadoId != null && (
                      <button
                        type="button"
                        className="guardadas-delete-btn"
                        title="Eliminar de guardadas"
                        aria-label="Eliminar respuesta guardada"
                        onClick={() => void handleEliminarGuardado(guardadoSeleccionadoId)}
                      >
                        <IconTrash size={15} />
                        <span>Eliminar</span>
                      </button>
                    )}
                  </div>
                  {(() => {
                    const sel = guardados.find((g) => g.id === guardadoSeleccionadoId);
                    if (!sel) {
                      return (
                        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
                          Seleccioná una pregunta de la lista para ver la respuesta completa.
                        </p>
                      );
                    }
                    return (
                      <div className="guardadas-detail-body">
                        <p className="guardadas-detail-q">{sel.pregunta}</p>
                        <div className="guardadas-detail-a">
                          <ResumenIaContenido texto={sel.respuesta} />
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            )}

            {activeTab === "ficha" && (
              <div className="detail-grid">
                <div className="kv" title={help("sector")}>
                  <div className="k">Actividad económica</div>
                  <div className="v">{ciiuDivisionLabel(item.ciiuDivision)}</div>
                </div>
                <div className="kv" title={help("capitas")}>
                  <div className="k">Cápitas</div>
                  <div className="v mono">
                    {item.cantidadCapitas != null ? item.cantidadCapitas.toLocaleString("es-AR") : "—"}
                  </div>
                </div>
                <div className="kv" title={help("dotacion")}>
                  <div className="k">Dotación nómina mes</div>
                  <div className="v mono">
                    {item.dotacionNominaMes != null ? item.dotacionNominaMes.toLocaleString("es-AR") : "—"}
                  </div>
                </div>
                <div className="kv" title={help("ultimaVisita")}>
                  <div className="k">Última visita</div>
                  <div className="v mono">
                    {item.ultimaVisitaHaceMeses != null ? `${item.ultimaVisitaHaceMeses} meses` : "sin visita"}
                  </div>
                </div>
                <div className="kv" title={help("prs")}>
                  <div className="k">PRS</div>
                  <div className="v">{item.obligacionPrs ? "Sí" : "No"}</div>
                </div>
                <div className="kv" title={help("alerta")}>
                  <div className="k">Alerta umbral</div>
                  <div className="v">{item.alertaUmbral ? "Sí" : "No"}</div>
                </div>
              </div>
            )}

            {activeTab === "shap" && data.factoresShap && (
              <>
                {data.comoSeCalcula.shap && (
                  <div className="detail-tab-head">
                    <InfoHint
                      title="Factores de priorización"
                      body={data.comoSeCalcula.shap}
                      open={openInfo === "shap"}
                      onToggle={() => toggleInfo("shap")}
                    />
                  </div>
                )}
                {!data.factoresShap.disponible ? (
                  <p className="muted" style={{ marginBottom: 0 }}>
                    Todavía no hay contribuciones SHAP importadas para este ítem.
                  </p>
                ) : (
                  <Reveal>
                    <h3 style={{ fontSize: 14, margin: "0 0 6px" }}>Factores que aumentaron</h3>
                    {data.factoresShap.aumentaron.length === 0 ? (
                      <p className="muted">Ninguno entre los principales.</p>
                    ) : (
                      <div className="shap-list">
                        {data.factoresShap.aumentaron.map((f) => (
                          <div key={`up-${f.orden}-${f.feature}`} className="shap-row">
                            <strong>{f.etiqueta}</strong>
                            <span className="mono">{f.shapValue >= 0 ? "+" : ""}
                              {f.shapValue.toFixed(4)}
                            </span>
                            <div className="shap-bar-track">
                              <div
                                className="shap-bar-fill aumenta animate-bar"
                                style={{ width: `${Math.round(f.intensidadRelativa * 100)}%` }}
                              />
                            </div>
                            <div className="shap-meta muted" style={{ fontSize: 12 }}>
                              {f.tema ?? "Factor"}
                              {f.valorObservado != null ? ` · valor ${f.valorObservado}` : ""}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <h3 style={{ fontSize: 14, margin: "16px 0 6px" }}>Factores que redujeron</h3>
                    {data.factoresShap.redujeron.length === 0 ? (
                      <p className="muted">Ninguno entre los principales.</p>
                    ) : (
                      <div className="shap-list">
                        {data.factoresShap.redujeron.map((f) => (
                          <div key={`dn-${f.orden}-${f.feature}`} className="shap-row">
                            <strong>{f.etiqueta}</strong>
                            <span className="mono">{f.shapValue.toFixed(4)}</span>
                            <div className="shap-bar-track">
                              <div
                                className="shap-bar-fill reduce animate-bar"
                                style={{ width: `${Math.round(f.intensidadRelativa * 100)}%` }}
                              />
                            </div>
                            <div className="shap-meta muted" style={{ fontSize: 12 }}>
                              {f.tema ?? "Factor"}
                              {f.valorObservado != null ? ` · valor ${f.valorObservado}` : ""}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </Reveal>
                )}
              </>
            )}

            {activeTab === "movimientos" && (
              movimientos.length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>
                  Sin movimientos registrados para este establecimiento. Las visitas creadas antes
                  de habilitar la bitácora no generan historial.
                </p>
              ) : (
                <ul className="mov-list">
                  {movimientos.map((ev) => (
                    <li key={ev.id} className="mov-item">
                      <div className="mov-head">
                        <span className={`badge mov-${ev.tipo}`}>{movTipoLabel(ev.tipo)}</span>
                        <span className="mono muted">{formatMovDateTime(ev.ocurridoEn)}</span>
                      </div>
                      <div className="mov-meta">
                        {ev.actor ? (
                          <span title={ev.actor.email ?? undefined}>
                            {ev.actor.nombre}
                            <span className="muted"> · {ev.actor.rol}</span>
                          </span>
                        ) : (
                          <span className="muted">Sin actor atribuido</span>
                        )}
                        <span className="muted">
                          {(ev.estadoAnterior ?? "—") + " → " + (ev.estadoNuevo ?? "—")}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )
            )}
          </div>
        </>
      )}
    </>
  );
}

function formatMovDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-AR", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function movTipoLabel(tipo: string): string {
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

function renderInline(text: string): (string | ReactElement)[] {
  const nodes: (string | ReactElement)[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    nodes.push(<strong key={key++}>{match[1]}</strong>);
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

/** Detecta títulos de sección (azules) aunque el modelo agregue ":" o los mande como viñeta. */
function parseHeading(line: string): string | null {
  const t = line.trim();
  if (!t) return null;

  const hash = t.match(/^#{1,4}\s+(.+)$/);
  if (hash) return cleanHeadingText(hash[1]);

  const numbered = t.match(/^\d+[.)]\s+(.+)$/);
  if (numbered && numbered[1].length <= 80 && !numbered[1].includes(". ")) {
    return cleanHeadingText(numbered[1]);
  }

  // "**Título**" / "**Título:**" / "**Título**:"
  const boldLine = t.match(/^\*\*(.+?)\*\*:?\s*$/);
  if (boldLine) return cleanHeadingText(boldLine[1]);

  // "- **Título:**" (sección disfrazada de viñeta)
  const boldBullet = t.match(/^[-*]\s+\*\*(.+?)\*\*:?\s*$/);
  if (boldBullet && boldBullet[1].length <= 90) return cleanHeadingText(boldBullet[1]);

  return null;
}

function cleanHeadingText(raw: string): string {
  return raw
    .replace(/^\*\*|\*\*$/g, "")
    .replace(/\*\*/g, "")
    .replace(/:\s*$/, "")
    .trim();
}

/** Efecto de escritura solo en generación nueva (no en respuestas desde caché). */
function TypewriterIa({ texto, animar }: { texto: string; animar: boolean }) {
  const [shown, setShown] = useState(animar ? "" : texto);
  const [done, setDone] = useState(!animar);

  useEffect(() => {
    const full = texto ?? "";
    if (!animar || !full) {
      setShown(full);
      setDone(true);
      return;
    }
    setShown("");
    setDone(false);
    const step = Math.max(4, Math.ceil(full.length / 55));
    let i = 0;
    const id = window.setInterval(() => {
      i += step;
      if (i >= full.length) {
        setShown(full);
        setDone(true);
        window.clearInterval(id);
      } else {
        setShown(full.slice(0, i));
      }
    }, 16);
    return () => window.clearInterval(id);
  }, [texto, animar]);

  if (done || !animar) {
    return <ResumenIaContenido texto={texto} />;
  }

  return (
    <div className="ia-resumen ia-typing" aria-live="polite">
      <pre className="ia-typing-text">
        {shown}
        <span className="ia-caret" aria-hidden="true" />
      </pre>
    </div>
  );
}

function ResumenIaContenido({ texto }: { texto: string }) {
  const lines = texto.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactElement[] = [];
  let bullets: string[] = [];
  let key = 0;

  const flushBullets = () => {
    if (bullets.length === 0) return;
    blocks.push(
      <ul key={`ul-${key++}`} className="ia-list">
        {bullets.map((b, i) => (
          <li key={i}>{renderInline(b)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (line.length === 0) {
      flushBullets();
      continue;
    }

    const heading = parseHeading(line);
    if (heading) {
      flushBullets();
      blocks.push(
        <h4 key={`h-${key++}`} className="ia-heading">
          {heading}
        </h4>,
      );
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      bullets.push(line.replace(/^[-*]\s+/, ""));
      continue;
    }

    flushBullets();
    blocks.push(
      <p key={`p-${key++}`} className="ia-par">
        {renderInline(line)}
      </p>,
    );
  }
  flushBullets();

  return <div className="ia-resumen">{blocks}</div>;
}
