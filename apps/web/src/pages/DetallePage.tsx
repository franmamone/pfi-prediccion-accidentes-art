import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  fetchEstablecimiento,
  shortId,
  type DetalleEstablecimiento,
  type Horizonte,
} from "../api";
import { ciiuDivisionLabel } from "../ciiu";
import { help, tipMotivo, tipRiesgo, VISITA_RECIENTE_MESES } from "../columnHelp";
import { InfoHint, SectionTitleWithInfo } from "../components/InfoHint";
import { ProgramarVisitaDialog } from "../components/ProgramarVisitaDialog";
import { IconArrowLeft, IconCalendar } from "../icons";
import { motivoBadgeClass, motivoLabel, riesgoLabel } from "../labels";

type InfoKey = "puntaje" | "explicacion" | "shap" | "acierto" | null;

export function DetallePage() {
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const horizonte = (params.get("horizonte") as Horizonte) || "1m";
  const [data, setData] = useState<DetalleEstablecimiento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showProgramar, setShowProgramar] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [openInfo, setOpenInfo] = useState<InfoKey>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    setOpenInfo(null);
    fetchEstablecimiento(id, horizonte)
      .then((res) => {
        if (alive) setData(res);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "No se pudo cargar");
      });
    return () => {
      alive = false;
    };
  }, [id, horizonte, reloadKey]);

  const item = data?.item;
  const explicacionPrioridad = item?.motivoPrincipalTexto
    ?.split(";")
    .map((parte) => parte.trim())
    .filter(Boolean);

  const toggleInfo = (key: Exclude<InfoKey, null>) => {
    setOpenInfo((current) => (current === key ? null : key));
  };

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
      {success && <div className="success">{success}</div>}

      {item && data && showProgramar && (
        <ProgramarVisitaDialog
          item={item}
          horizonte={horizonte}
          onClose={() => setShowProgramar(false)}
          onDone={() => {
            setShowProgramar(false);
            setSuccess("Visita programada. Podés verla en Agenda.");
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {item && data && (
        <>
          <div className="panel">
            <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
              <span className={`badge ${item.banda}`} title={tipRiesgo(item.banda, item.ranking)}>
                {riesgoLabel(item.banda)}
              </span>
              {item.motivo && (
                <span className={`badge ${motivoBadgeClass(item.motivo)}`} title={tipMotivo(item.motivo)}>
                  {motivoLabel(item.motivo)}
                </span>
              )}
              <span className="mono" title={help("ranking")}>
                #{item.ranking}
              </span>
              <span className="score-with-info">
                <span className="mono" title={help("score")}>
                  puntaje {item.scoreRiesgo.toFixed(4)}
                </span>
                <InfoHint
                  title="Puntaje"
                  body={data.comoSeCalcula.puntaje}
                  open={openInfo === "puntaje"}
                  onToggle={() => toggleInfo("puntaje")}
                />
              </span>
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
          {(data.explicacion.length > 0 || (explicacionPrioridad && explicacionPrioridad.length > 0)) && (
            <section className="panel priority-explanation" aria-labelledby="priority-explanation-title">
              <SectionTitleWithInfo
                id="priority-explanation-title"
                infoTitle="Explicación de la prioridad"
                infoBody={data.comoSeCalcula.explicacionPrioridad ?? data.comoSeCalcula.puntaje}
                open={openInfo === "explicacion"}
                onToggle={() => toggleInfo("explicacion")}
              >
                Explicación de la prioridad
              </SectionTitleWithInfo>
              <div className="priority-explanation-grid">
                {data.explicacion.map((bloque) => (
                  <div className="priority-explanation-item" key={`operativo-${bloque.titulo}`}>
                    <h3>{bloque.titulo}</h3>
                    <p>{bloque.detalle}</p>
                  </div>
                ))}
                {(explicacionPrioridad ?? []).map((parte, index) => {
                  const separador = parte.indexOf(":");
                  const titulo = separador > 0 ? parte.slice(0, separador).trim() : `Indicador ${index + 1}`;
                  const detalle = separador > 0 ? parte.slice(separador + 1).trim() : parte;
                  return (
                    <div className="priority-explanation-item" key={`${titulo}-${index}`}>
                      <h3>{titulo}</h3>
                      <p>{detalle}</p>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {data.factoresShap && (
            <div className="panel detail-shap">
              <SectionTitleWithInfo
                infoTitle="Factores del modelo (SHAP)"
                infoBody={data.comoSeCalcula.shap}
                open={openInfo === "shap"}
                onToggle={() => toggleInfo("shap")}
              >
                Factores del modelo (SHAP)
              </SectionTitleWithInfo>
              {!data.factoresShap.disponible ? (
                <p className="muted" style={{ marginBottom: 0 }}>
                  Todavía no hay contribuciones SHAP importadas para este ítem.
                </p>
              ) : (
                <>
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
                              className="shap-bar-fill aumenta"
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
                              className="shap-bar-fill reduce"
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

                  <p className="muted" style={{ marginTop: 14, marginBottom: 0 }}>
                    {data.factoresShap.advertencia}
                  </p>
                </>
              )}
            </div>
          )}

          <div className="panel detail-accuracy">
            <SectionTitleWithInfo
              infoTitle="Acierto histórico del modelo"
              infoBody={data.comoSeCalcula.aciertoHistorico}
              infoFooter={`Fuente: holdout ${data.aciertoHistorico.holdoutAnio} · ${data.comoSeCalcula.fuente}`}
              open={openInfo === "acierto"}
              onToggle={() => toggleInfo("acierto")}
            >
              Acierto histórico del modelo
            </SectionTitleWithInfo>
            <div className="stats" style={{ marginBottom: 12 }}>
              <div className="stat">
                <div className="label">{data.aciertoHistorico.etiqueta}</div>
                <div className="value mono">
                  {data.aciertoHistorico.disponible && data.aciertoHistorico.porcentaje != null
                    ? `${data.aciertoHistorico.porcentaje.toFixed(1)}%`
                    : "—"}
                </div>
              </div>
              <div className="stat" title={help("score")}>
                <div className="label">Percentil del puntaje</div>
                <div className="value mono">{data.contexto.percentilScore}</div>
              </div>
              <div className="stat">
                <div className="label">Promedio de la lista</div>
                <div className="value mono" style={{ fontSize: 22 }}>
                  {data.contexto.promedioScore.toFixed(3)}
                </div>
              </div>
              <div className="stat">
                <div className="label">Total en lista</div>
                <div className="value mono">{data.contexto.totalEnRanking}</div>
              </div>
            </div>
            <p className="page-sub" style={{ marginBottom: 0 }}>
              {data.aciertoHistorico.detalle}
            </p>
          </div>

          <div className="panel detail-operational">
            <h2 className="page-title" style={{ fontSize: 16, marginBottom: 12 }}>
              Ficha operativa
            </h2>
            <div className="detail-grid">
              <div className="kv" title={help("establecimiento")}>
                <div className="k">ID establecimiento</div>
                <div className="v mono">{item.idEstablecimiento}</div>
              </div>
              <div className="kv" title={help("empleador")}>
                <div className="k">ID empleador</div>
                <div className="v mono">{item.idEmpleador ? shortId(item.idEmpleador) : "—"}</div>
              </div>
              <div className="kv" title={help("motivo")}>
                <div className="k">Motivo</div>
                <div className="v">
                  {item.motivo ? (
                    <span className={`badge ${motivoBadgeClass(item.motivo)}`}>
                      {motivoLabel(item.motivo)}
                    </span>
                  ) : (
                    "—"
                  )}
                </div>
              </div>
              <div className="kv" title={help("sector")}>
                <div className="k">Actividad económica</div>
                <div className="v">{ciiuDivisionLabel(item.ciiuDivision)}</div>
              </div>
              <div className="kv" title={help("ciiu")}>
                <div className="k">Misma CIIU en lista</div>
                <div className="v mono">{data.contexto.establecimientosMismaCiiu}</div>
              </div>
              <div className="kv" title={help("capitas")}>
                <div className="k">Cápitas</div>
                <div className="v mono">
                  {item.cantidadCapitas != null ? item.cantidadCapitas.toLocaleString("es-AR") : "—"}
                  <span className="muted"> · prom. {data.contexto.promedioCapitas.toLocaleString("es-AR")}</span>
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
                  <span className="muted">
                    {" "}
                    · prom. {data.contexto.promedioUltimaVisitaMeses.toFixed(1)} m
                  </span>
                </div>
              </div>
              <div className="kv" title={help("cooldown")}>
                <div className="k">Visita reciente (&lt;{VISITA_RECIENTE_MESES} m)</div>
                <div className="v">
                  {item.enCooldown
                    ? `Sí (hace ${item.ultimaVisitaHaceMeses ?? "?"} m)`
                    : "No"}
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
            <p className="muted" style={{ marginTop: 14 }}>
              El puntaje ordena la prioridad relativa. No debe interpretarse como probabilidad de accidente.
            </p>
          </div>
          </div>
        </>
      )}
    </>
  );
}
