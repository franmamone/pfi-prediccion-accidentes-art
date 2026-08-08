import { useEffect, useState, type ReactElement } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  fetchDossier,
  fetchEstablecimiento,
  generarResumenIa,
  type DetalleEstablecimiento,
  type DossierEstablecimiento,
  type Horizonte,
  type ResumenIa,
} from "../api";
import { useAuth } from "../auth";
import { ciiuDivisionLabel } from "../ciiu";
import { help, tipMotivo, tipRiesgo } from "../columnHelp";
import { CollapsiblePanel } from "../components/CollapsiblePanel";
import { InfoHint } from "../components/InfoHint";
import { ProgramarVisitaDialog } from "../components/ProgramarVisitaDialog";
import { Reveal, SkeletonPanel, SkeletonStats } from "../components/UiKit";
import { IconArrowLeft, IconCalendar } from "../icons";
import { motivoBadgeClass, motivoLabel, riesgoLabel } from "../labels";
import {
  getDetalleSections,
  setDetalleSection,
  type DetalleSectionKey,
} from "../prefs";
import { useToast } from "../toast";

type InfoKey = "shap" | "acierto" | null;

export function DetallePage() {
  const toast = useToast();
  const { user } = useAuth();
  const puedeRegenerar = user?.rol === "Admin" || user?.rol === "Coordinador";
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const horizonte = (params.get("horizonte") as Horizonte) || "1m";
  const [data, setData] = useState<DetalleEstablecimiento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showProgramar, setShowProgramar] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [openInfo, setOpenInfo] = useState<InfoKey>(null);
  const [sections, setSections] = useState(() => getDetalleSections());
  const [dossier, setDossier] = useState<DossierEstablecimiento | null>(null);
  const [ia, setIa] = useState<ResumenIa | null>(null);
  const [iaLoading, setIaLoading] = useState(false);
  const [iaError, setIaError] = useState<string | null>(null);

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

  function toggleSection(key: DetalleSectionKey) {
    setSections((prev) => {
      const next = setDetalleSection(key, !prev[key]);
      return next;
    });
  }

  return (
    <>
      <div>
        <Link
          to={`/riesgo?horizonte=${horizonte}`}
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
                período {data.periodo} · horizonte {data.horizonte}
              </span>
              {data.agendaActiva ? (
                <Link className="badge motivo-prs" to="/agenda" title="Ver en Agenda">
                  Programada · {data.agendaActiva.fechaPlanificada.slice(0, 10)}
                </Link>
              ) : (
                <button
                  type="button"
                  className="btn"
                  style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                  onClick={() => setShowProgramar(true)}
                >
                  <IconCalendar size={16} />
                  Programar visita
                </button>
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

          <div className="detail-sections">
            {dossier?.disponible && dossier.accidentes && (
              <CollapsiblePanel
                id="historial-title"
                title="Historial de accidentes"
                className="detail-accidentes"
                open={sections.historial}
                onToggle={() => toggleSection("historial")}
              >
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
              </CollapsiblePanel>
            )}

            {dossier?.disponible && (dossier.accidentes || dossier.visitas) && (
              <CollapsiblePanel
                id="resumen-ia-title"
                title="Resumen IA para la próxima visita"
                className="detail-ia"
                open={sections.resumenIa}
                onToggle={() => toggleSection("resumenIa")}
              >
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
                {ia ? (
                  <ResumenIaContenido texto={ia.resumen} />
                ) : (
                  <p className="muted" style={{ marginBottom: 0 }}>
                    Resumen accionable a partir del historial de accidentes y las visitas previas
                    (datos anonimizados: sin nombre ni identificador del establecimiento).
                  </p>
                )}
              </CollapsiblePanel>
            )}

            <CollapsiblePanel
              id="ficha-title"
              title="Ficha operativa"
              className="detail-operational"
              open={sections.ficha}
              onToggle={() => toggleSection("ficha")}
            >
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
            </CollapsiblePanel>

            {data.factoresShap && (
              <CollapsiblePanel
                id="shap-title"
                title="Factores de priorización"
                className="detail-shap"
                open={sections.shap}
                onToggle={() => toggleSection("shap")}
                trailing={
                  data.comoSeCalcula.shap ? (
                    <InfoHint
                      title="Factores de priorización"
                      body={data.comoSeCalcula.shap}
                      open={openInfo === "shap"}
                      onToggle={() => toggleInfo("shap")}
                    />
                  ) : null
                }
              >
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
              </CollapsiblePanel>
            )}
          </div>
        </>
      )}
    </>
  );
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
