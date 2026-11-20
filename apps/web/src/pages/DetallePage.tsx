import { useEffect, useState, type ReactElement } from "react";
import { Link, useParams } from "react-router-dom";
import {
  eliminarCopilotoGuardado,
  fetchAuditoriaAgenda,
  fetchCopilotoGuardados,
  fetchDossier,
  fetchEstablecimiento,
  fetchVisitasEstablecimiento,
  guardarCopilotoRespuesta,
  patchHallazgo,
  preguntarCopiloto,
  shortId,
  HORIZONTE_OPERATIVO,
  type AgendaEvento,
  type CopilotoGuardado,
  type CopilotoRespuesta,
  type DetalleEstablecimiento,
  type DossierEstablecimiento,
  type VisitaHistorialItem,
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
  const esPreventor = user?.rol === "Preventor";
  const { id = "" } = useParams();
  const horizonte = HORIZONTE_OPERATIVO;
  const [data, setData] = useState<DetalleEstablecimiento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showProgramar, setShowProgramar] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [openInfo, setOpenInfo] = useState<InfoKey>(null);
  const [tab, setTab] = useState<DetalleSectionKey>("establecimiento");
  const [dossier, setDossier] = useState<DossierEstablecimiento | null>(null);
  const [copilotoUltimaPregunta, setCopilotoUltimaPregunta] = useState("");
  const [copilotoLoading, setCopilotoLoading] = useState(false);
  const [copilotoError, setCopilotoError] = useState<string | null>(null);
  const [copilotoResp, setCopilotoResp] = useState<CopilotoRespuesta | null>(null);
  const [copilotoGuardando, setCopilotoGuardando] = useState(false);
  const [guardados, setGuardados] = useState<CopilotoGuardado[]>([]);
  const [cerrandoId, setCerrandoId] = useState<number | null>(null);
  const [visitasHist, setVisitasHist] = useState<VisitaHistorialItem[]>([]);
  const [visitasLoading, setVisitasLoading] = useState(false);
  const [visitaExpandidaId, setVisitaExpandidaId] = useState<number | null>(null);
  const [guardadosLoading, setGuardadosLoading] = useState(false);
  const [guardadoSeleccionadoId, setGuardadoSeleccionadoId] = useState<number | null>(null);
  const [movimientos, setMovimientos] = useState<AgendaEvento[]>([]);

  type CopilotoChip = {
    label: string;
    tema: string;
  };

  /** Botonera fija (sin chat libre): misma para todos los establecimientos.
   * PESE/PRS y RAR/exámenes quedan ocultos en UI; el backend sigue soportándolos. */
  const copilotoChips: CopilotoChip[] = [
    { label: "Qué verificar (RGRL)", tema: "rgrl_checklist" },
    { label: "Accidentes previos", tema: "accidentes_previos" },
    { label: "Visitas previas", tema: "visitas_previas" },
  ];

  // Al abrir un establecimiento, siempre entrar por la ficha agrupada.
  useEffect(() => {
    setTab("establecimiento");
    setDetalleTab("establecimiento");
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

  useEffect(() => {
    let alive = true;
    setVisitasLoading(true);
    setVisitaExpandidaId(null);
    fetchVisitasEstablecimiento(id)
      .then((res) => {
        if (!alive) return;
        setVisitasHist(res.items);
      })
      .catch(() => {
        if (alive) setVisitasHist([]);
      })
      .finally(() => {
        if (alive) setVisitasLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [id, reloadKey]);

  async function handleCerrarHallazgo(hallazgoId: number) {
    setCerrandoId(hallazgoId);
    try {
      await patchHallazgo(hallazgoId, { estado: "cerrado" });
      setVisitasHist((prev) =>
        prev.map((v) => {
          if (!v.acta?.hallazgos.some((h) => h.id === hallazgoId)) return v;
          const hallazgos = v.acta.hallazgos.map((h) =>
            h.id === hallazgoId ? { ...h, estado: "cerrado" } : h,
          );
          return {
            ...v,
            acta: {
              ...v.acta,
              hallazgos,
              hallazgosAbiertos: hallazgos.filter((h) => h.estado === "abierto").length,
            },
          };
        }),
      );
      toast.success("Hallazgo cerrado");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "No se pudo cerrar el hallazgo");
    } finally {
      setCerrandoId(null);
    }
  }

  async function handleChip(chip: CopilotoChip, regenerar = false) {
    setCopilotoLoading(true);
    setCopilotoError(null);
    setCopilotoUltimaPregunta(chip.label);
    try {
      const res = await preguntarCopiloto(id, {
        tema: chip.tema,
        refrescar: regenerar,
      });
      setCopilotoResp(res);
      if (res.sinFundamento) {
        toast.info("Sin fundamento suficiente para esta consulta");
      } else if (res.desdeCache) {
        toast.info("Respuesta recuperada");
      } else {
        toast.success(regenerar ? "Respuesta regenerada" : "Respuesta generada");
      }
    } catch (err) {
      setCopilotoError(err instanceof Error ? err.message : "No se pudo consultar Prevex IA.");
    } finally {
      setCopilotoLoading(false);
    }
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

  const tabs: { key: DetalleSectionKey; label: string; count?: number }[] = [
    { key: "establecimiento", label: "Establecimiento" },
    { key: "copiloto", label: "Prevex IA" },
    { key: "guardadas", label: "Guardadas", count: guardados.length || undefined },
    { key: "visitas", label: "Visitas", count: visitasHist.length || undefined },
  ];
  const activeTab: DetalleSectionKey = tabs.some((t) => t.key === tab)
    ? tab
    : "establecimiento";

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
        <p className="page-sub mono" title={id}>
          {shortId(id)}
        </p>
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
          <div className="panel detalle-meta-panel">
            <div className="detalle-meta-row">
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
              {data.agendaActiva ? (
                <Link className="badge motivo-prs" to="/agenda" title="Ver en Agenda">
                  Programada · {data.agendaActiva.fechaPlanificada.slice(0, 10)}
                  {data.agendaActiva.horaPlanificada
                    ? ` · ${data.agendaActiva.horaPlanificada.slice(0, 5)}`
                    : ""}
                </Link>
              ) : (
                !esPreventor && (
                  <button
                    type="button"
                    className="btn success detalle-programar-btn"
                    onClick={() => setShowProgramar(true)}
                  >
                    <IconCalendar size={16} />
                    Programar visita
                  </button>
                )
              )}
            </div>
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
            {activeTab === "establecimiento" && (
              <div className="detalle-establecimiento">
                <section className="detalle-est-section">
                  <h3 className="detalle-est-title">Historial de accidentes</h3>
                  {dossier?.disponible && dossier.accidentes ? (
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
                  ) : (
                    <p className="muted" style={{ marginBottom: 0 }}>
                      No hay historial de accidentes cargado para este establecimiento.
                    </p>
                  )}
                </section>

                <section className="detalle-est-section">
                  <h3 className="detalle-est-title">Ficha operativa</h3>
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
                </section>

                {data.factoresShap && (
                  <section className="detalle-est-section">
                    <div className="detalle-est-title-row">
                      <h3 className="detalle-est-title">Factores de priorización</h3>
                      {data.comoSeCalcula.shap && (
                        <InfoHint
                          title="Factores de priorización"
                          body={data.comoSeCalcula.shap}
                          open={openInfo === "shap"}
                          onToggle={() => toggleInfo("shap")}
                        />
                      )}
                    </div>
                    {!data.factoresShap.disponible ? (
                      <p className="muted" style={{ marginBottom: 0 }}>
                        Todavía no hay contribuciones SHAP importadas para este ítem.
                      </p>
                    ) : (
                      <Reveal>
                        <h4 style={{ fontSize: 13, margin: "0 0 6px" }}>Factores que aumentaron</h4>
                        {data.factoresShap.aumentaron.length === 0 ? (
                          <p className="muted">Ninguno entre los principales.</p>
                        ) : (
                          <div className="shap-list">
                            {data.factoresShap.aumentaron.map((f) => (
                              <div key={`up-${f.orden}-${f.feature}`} className="shap-row">
                                <strong>{f.etiqueta}</strong>
                                <span className="mono">
                                  {f.shapValue >= 0 ? "+" : ""}
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

                        <h4 style={{ fontSize: 13, margin: "16px 0 6px" }}>Factores que redujeron</h4>
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
                  </section>
                )}

                <section className="detalle-est-section">
                  <h3 className="detalle-est-title">Historial de cambios</h3>
                  {movimientos.length === 0 ? (
                    <p className="muted" style={{ margin: 0 }}>
                      Sin movimientos registrados. Las visitas creadas antes de habilitar la bitácora
                      no generan historial.
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
                  )}
                </section>
              </div>
            )}

            {activeTab === "copiloto" && (
              <>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                  {copilotoChips.map((chip) => {
                    const activa = copilotoResp?.seccion === chip.tema;
                    return (
                      <button
                        key={chip.tema}
                        type="button"
                        className={activa ? "btn" : "ghost-btn"}
                        disabled={copilotoLoading}
                        onClick={() => void handleChip(chip, false)}
                      >
                        {chip.label}
                      </button>
                    );
                  })}
                </div>
                {copilotoResp && (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={copilotoLoading}
                      onClick={() => {
                        const chip = copilotoChips.find((c) => c.tema === copilotoResp.seccion);
                        if (chip) void handleChip(chip, true);
                      }}
                    >
                      Regenerar
                    </button>
                  </div>
                )}
                {copilotoError && <div className="error" style={{ marginBottom: 10 }}>{copilotoError}</div>}
                {copilotoLoading && (
                  <p className="muted copiloto-escribiendo" style={{ marginBottom: 12, fontSize: 13 }}>
                    Prevex IA está preparando la respuesta…
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
              </>
            )}

            {activeTab === "guardadas" && (
              <div className="guardadas-layout">
                <div className="guardadas-card">
                  <div className="guardadas-card-head">
                    <h3>Consultas guardadas</h3>
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
                      Todavía no guardaste consultas. En Prevex IA, elegí una opción de la botonera y
                      tocá <strong>Guardar</strong> en la respuesta.
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
                          Seleccioná una consulta de la lista para ver la respuesta completa.
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

            {activeTab === "visitas" && (
              <div>
                <p className="page-sub" style={{ marginTop: 0, marginBottom: 12 }}>
                  Tocá una visita para ver el acta y sus hallazgos.
                </p>
                {visitasLoading ? (
                  <p className="muted">Cargando visitas…</p>
                ) : visitasHist.length === 0 ? (
                  <p className="muted" style={{ marginBottom: 0 }}>
                    Todavía no hay visitas realizadas registradas para este establecimiento.
                  </p>
                ) : (
                  <ul className="visitas-hist-list">
                    {visitasHist.map((v) => {
                      const open = visitaExpandidaId === v.id;
                      const acta = v.acta;
                      const resultadoLabel =
                        acta?.resultadoGlobal === "ok"
                          ? "OK"
                          : acta?.resultadoGlobal === "critico"
                            ? "Crítico"
                            : acta?.resultadoGlobal === "observacion"
                              ? "Con observaciones"
                              : null;
                      return (
                        <li key={v.id} className={`visita-hist-item${open ? " is-open" : ""}`}>
                          <button
                            type="button"
                            className="visita-hist-toggle"
                            onClick={() => setVisitaExpandidaId(open ? null : v.id)}
                            aria-expanded={open}
                          >
                            <div className="visita-hist-summary">
                              <strong>{formatMovDateTime(v.fechaHoraReal)}</strong>
                              <span className="muted">
                                {v.responsable?.nombre ?? "Sin responsable"}
                                {v.tipo ? ` · ${v.tipo}` : ""}
                              </span>
                            </div>
                            <div className="visita-hist-badges">
                              {resultadoLabel && (
                                <span className={`badge-resultado ${acta?.resultadoGlobal}`}>
                                  {resultadoLabel}
                                </span>
                              )}
                              {acta ? (
                                <span className="muted" style={{ fontSize: 12 }}>
                                  {acta.hallazgosTotal} hallazgos
                                  {acta.hallazgosAbiertos > 0
                                    ? ` · ${acta.hallazgosAbiertos} abiertos`
                                    : ""}
                                  {acta.revisita ? " · revisita" : ""}
                                </span>
                              ) : v.hallazgos ? (
                                <span className="muted" style={{ fontSize: 12 }}>
                                  Sin acta estructurada
                                </span>
                              ) : null}
                              <span className="visita-hist-chevron">{open ? "▾" : "▸"}</span>
                            </div>
                          </button>
                          {open && (
                            <div className="visita-hist-body">
                              {acta?.notas && (
                                <p className="visita-hist-notas">
                                  <span className="muted">Notas:</span> {acta.notas}
                                </p>
                              )}
                              {!acta && (v.hallazgos || v.acciones) && (
                                <div className="visita-hist-legacy">
                                  {v.hallazgos && (
                                    <p>
                                      <span className="muted">Hallazgos:</span> {v.hallazgos}
                                    </p>
                                  )}
                                  {v.acciones && (
                                    <p>
                                      <span className="muted">Acciones:</span> {v.acciones}
                                    </p>
                                  )}
                                </div>
                              )}

                              <h4 className="visita-hist-hallazgos-title">Hallazgos</h4>
                              {acta && acta.hallazgos.length > 0 ? (
                                <ul className="pendientes-list compact">
                                  {acta.hallazgos.map((h) => (
                                    <li key={h.id} className="pendiente-item">
                                      <div className="pendiente-head">
                                        <span className={`badge-sev ${h.severidad}`}>
                                          {h.severidad}
                                        </span>
                                        <span className={`badge-estado ${h.estado}`}>{h.estado}</span>
                                        {h.plazoDias != null && (
                                          <span className="muted" style={{ fontSize: 12 }}>
                                            Plazo {h.plazoDias} d
                                          </span>
                                        )}
                                        {h.normaRef && (
                                          <span className="muted" style={{ fontSize: 12 }}>
                                            {h.normaRef}
                                          </span>
                                        )}
                                      </div>
                                      <p className="pendiente-text">{h.hallazgo}</p>
                                      {h.recomendacion && (
                                        <p className="pendiente-rec muted">{h.recomendacion}</p>
                                      )}
                                      {h.estado === "abierto" && (
                                        <button
                                          type="button"
                                          className="ghost-btn"
                                          disabled={cerrandoId === h.id}
                                          onClick={() => void handleCerrarHallazgo(h.id)}
                                        >
                                          {cerrandoId === h.id ? "Cerrando…" : "Cerrar hallazgo"}
                                        </button>
                                      )}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="muted" style={{ marginBottom: 0 }}>
                                  {acta
                                    ? "Esta visita no tiene hallazgos registrados."
                                    : "Sin hallazgos estructurados en esta visita."}
                                </p>
                              )}
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
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

type ParsedHeading = { text: string; kind: "section" | "item" };

/** Detecta títulos de sección (azules) o subtítulos de ítem RGRL. */
function parseHeading(line: string): ParsedHeading | null {
  const t = line.trim();
  if (!t) return null;

  const asHeading = (raw: string): ParsedHeading => {
    const text = cleanHeadingText(raw);
    const isItem = /^ítem\s+\d+/i.test(text) || /^item\s+\d+/i.test(text);
    return { text, kind: isItem ? "item" : "section" };
  };

  const hash = t.match(/^#{1,4}\s+(.+)$/);
  if (hash) return asHeading(hash[1]);

  const numbered = t.match(/^\d+[.)]\s+(.+)$/);
  if (numbered && numbered[1].length <= 80 && !numbered[1].includes(". ")) {
    return asHeading(numbered[1]);
  }

  // "**Título**" / "**Título:**" / "**Título**:"
  const boldLine = t.match(/^\*\*(.+?)\*\*:?\s*$/);
  if (boldLine) return asHeading(boldLine[1]);

  // "- **Título:**" (sección disfrazada de viñeta, sin cuerpo extra)
  const boldBullet = t.match(/^[-*]\s+\*\*(.+?)\*\*:?\s*$/);
  if (boldBullet && boldBullet[1].length <= 90) return asHeading(boldBullet[1]);

  return null;
}

/** Si la línea es viñeta con ítem + texto, separa título y cuerpo. */
function splitItemBullet(line: string): { title: string; body: string } | null {
  const t = line.trim();
  const m = t.match(
    /^[-*]\s+\*\*(Ítem\s+\d+\s*[:\-–—]\s*[^:*]+?)\*\*\s*:?\s*(.+)$/i,
  );
  if (!m) return null;
  const title = cleanHeadingText(m[1].replace(/[–—]/g, ":").replace(/\s*:\s*/, ": "));
  return { title, body: m[2].trim() };
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

    const split = splitItemBullet(line);
    if (split) {
      flushBullets();
      blocks.push(
        <h5 key={`h-${key++}`} className="ia-item-title">
          {split.title}
        </h5>,
      );
      if (split.body) {
        blocks.push(
          <p key={`p-${key++}`} className="ia-item-body">
            {renderInline(split.body)}
          </p>,
        );
      }
      continue;
    }

    const heading = parseHeading(line);
    if (heading) {
      flushBullets();
      blocks.push(
        heading.kind === "item" ? (
          <h5 key={`h-${key++}`} className="ia-item-title">
            {heading.text}
          </h5>
        ) : (
          <h4 key={`h-${key++}`} className="ia-heading">
            {heading.text}
          </h4>
        ),
      );
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      bullets.push(line.replace(/^[-*]\s+/, ""));
      continue;
    }

    flushBullets();
    // Párrafo bajo un ítem: un poco más compacto si viene pegado al título
    blocks.push(
      <p key={`p-${key++}`} className="ia-par">
        {renderInline(line)}
      </p>,
    );
  }
  flushBullets();

  return <div className="ia-resumen">{blocks}</div>;
}
