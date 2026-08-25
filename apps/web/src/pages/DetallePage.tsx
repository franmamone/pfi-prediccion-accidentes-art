import { useEffect, useState, type ReactElement } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fetchAuditoriaAgenda,
  fetchDossier,
  fetchEstablecimiento,
  generarResumenIa,
  HORIZONTE_OPERATIVO,
  type AgendaEvento,
  type DetalleEstablecimiento,
  type DossierEstablecimiento,
  type ResumenIa,
} from "../api";
import { useAuth } from "../auth";
import { ciiuDivisionLabel } from "../ciiu";
import { help, tipMotivo, tipRiesgo } from "../columnHelp";
import { InfoHint } from "../components/InfoHint";
import { ProgramarVisitaDialog } from "../components/ProgramarVisitaDialog";
import { Reveal, SkeletonPanel, SkeletonStats } from "../components/UiKit";
import { IconArrowLeft, IconCalendar } from "../icons";
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
  const puedeRegenerar = user?.rol === "Admin" || user?.rol === "Coordinador";
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
  const [ia, setIa] = useState<ResumenIa | null>(null);
  const [iaLoading, setIaLoading] = useState(false);
  const [iaError, setIaError] = useState<string | null>(null);
  const [movimientos, setMovimientos] = useState<AgendaEvento[]>([]);

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
    setIa(null);
    setIaError(null);
    fetchDossier(id, horizonte)
      .then((res) => {
        if (!alive) return;
        setDossier(res);
        if (res.resumenIa) setIa(res.resumenIa);
      })
      .catch(() => {
        if (alive) setDossier({ disponible: false });
      });
    return () => {
      alive = false;
    };
  }, [id, horizonte]);

  async function handleResumenIa(refrescar = false) {
    setIaLoading(true);
    setIaError(null);
    try {
      const res = await generarResumenIa(id, horizonte, refrescar);
      setIa(res);
      toast.success(res.desdeCache ? "Resumen recuperado" : "Resumen generado");
    } catch (err) {
      setIaError(err instanceof Error ? err.message : "No se pudo generar el resumen.");
    } finally {
      setIaLoading(false);
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
  if (dossier?.disponible && (dossier.accidentes || dossier.visitas)) {
    tabs.push({ key: "resumenIa", label: "Resumen IA" });
  }
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

            {activeTab === "resumenIa" && (
              <>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
                  {(!ia || puedeRegenerar) && (
                    <button
                      type="button"
                      className="btn"
                      onClick={() => handleResumenIa(Boolean(ia))}
                      disabled={iaLoading}
                    >
                      {iaLoading ? "Generando…" : ia ? "Regenerar resumen" : "Generar resumen con IA"}
                    </button>
                  )}
                </div>
                {iaError && <div className="error" style={{ marginBottom: 10 }}>{iaError}</div>}
                {ia && <ResumenIaContenido texto={ia.resumen} />}
              </>
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
    const isHeading =
      /^\*\*.+\*\*$/.test(line) || /^#{1,4}\s+/.test(line) || /^\d+[.)]\s+/.test(line);
    if (isHeading) {
      flushBullets();
      const clean = line
        .replace(/^#{1,4}\s+/, "")
        .replace(/^\*\*|\*\*$/g, "")
        .replace(/^\d+[.)]\s*/, "")
        .replace(/\*\*/g, "")
        .trim();
      blocks.push(
        <h4 key={`h-${key++}`} className="ia-heading">
          {clean}
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
