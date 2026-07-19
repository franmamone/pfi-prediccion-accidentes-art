import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchRiesgo, shortId, type Horizonte, type RankingItem } from "../api";
import { ciiuDivisionLabel } from "../ciiu";
import {
  help,
  tipCapitas,
  tipMotivo,
  tipRanking,
  tipRiesgo,
  tipScore,
  tipUltimaVisita,
  tipVisitaReciente,
  VISITA_RECIENTE_MESES,
} from "../columnHelp";
import { ProgramarVisitaDialog } from "../components/ProgramarVisitaDialog";
import { IconCalendar, IconCheck, IconExternal, IconX } from "../icons";
import {
  estadoOperativoBadgeClass,
  estadoOperativoLabel,
  motivoBadgeClass,
  motivoLabel,
  riesgoLabel,
} from "../labels";

function Th({ id, children }: { id: string; children: ReactNode }) {
  return <th title={help(id)}>{children}</th>;
}

export function RiesgoPage() {
  const [params, setParams] = useSearchParams();
  const horizonte = (params.get("horizonte") as Horizonte) || "1m";
  const banda = params.get("banda") || "";
  const sector = params.get("sector") || "";
  const motivo = params.get("motivo") || "";
  const q = params.get("q") || "";
  const enCooldown = params.get("enCooldown") || "";
  const obligacionPrs = params.get("obligacionPrs") || "";
  const alertaUmbral = params.get("alertaUmbral") || "";
  const programada = params.get("programada") || "";
  const estadoOperativo = params.get("estado") || "";
  const scoreMin = params.get("scoreMin") || "";
  const scoreMax = params.get("scoreMax") || "";
  const [items, setItems] = useState<RankingItem[]>([]);
  const [periodo, setPeriodo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [programar, setProgramar] = useState<RankingItem | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fetchRiesgo({
      horizonte,
      banda: banda || undefined,
      sector: sector || undefined,
      motivo: motivo || undefined,
      q: q || undefined,
      enCooldown: enCooldown || undefined,
      obligacionPrs: obligacionPrs || undefined,
      alertaUmbral: alertaUmbral || undefined,
      programada: programada || undefined,
      estadoOperativo: estadoOperativo || undefined,
      scoreMin: scoreMin || undefined,
      scoreMax: scoreMax || undefined,
      top: 225,
    })
      .then((res) => {
        if (!alive) return;
        setItems(res.items);
        setPeriodo(res.periodo);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "Error al cargar la lista de prioridad");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [
    horizonte,
    banda,
    sector,
    motivo,
    q,
    enCooldown,
    obligacionPrs,
    alertaUmbral,
    programada,
    estadoOperativo,
    scoreMin,
    scoreMax,
  ]);

  useEffect(() => {
    return load();
  }, [load, reloadKey]);

  const sectors = useMemo(() => {
    const set = new Set(items.map((i) => i.ciiuDivision).filter(Boolean) as string[]);
    return Array.from(set).sort();
  }, [items]);

  const motivos = useMemo(() => {
    const set = new Set(items.map((i) => i.motivo).filter(Boolean) as string[]);
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

  function clearFilters() {
    setParams(new URLSearchParams({ horizonte }));
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 className="page-title">Priorización</h1>
          <p className="page-sub">
            Lista maestra · período <span className="mono">{periodo || "…"}</span> · {items.length} filas
          </p>
        </div>
        <div className="horizon-toggle">
          <button className={horizonte === "1m" ? "active" : ""} onClick={() => patch({ horizonte: "1m" })}>
            Mes
          </button>
          <button className={horizonte === "3m" ? "active" : ""} onClick={() => patch({ horizonte: "3m" })}>
            Trimestre
          </button>
        </div>
      </div>

      <div className="panel filters">
        <div className="field">
          <label title={help("banda")}>Riesgo</label>
          <select value={banda} onChange={(e) => patch({ banda: e.target.value })}>
            <option value="">Todos</option>
            <option value="critico">Crítico</option>
            <option value="alto">Alto</option>
            <option value="medio">Medio</option>
          </select>
        </div>
        <div className="field">
          <label title={help("motivo")}>Motivo</label>
          <select value={motivo} onChange={(e) => patch({ motivo: e.target.value })}>
            <option value="">Todos</option>
            {motivos.map((m) => (
              <option key={m} value={m}>
                {motivoLabel(m)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label title={help("ciiu")}>División CIIU</label>
          <select value={sector} onChange={(e) => patch({ sector: e.target.value })}>
            <option value="">Todas</option>
            {sectors.map((s) => (
              <option key={s} value={s}>
                {ciiuDivisionLabel(s)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label title={help("estadoOperativo")}>Estado</label>
          <select value={estadoOperativo} onChange={(e) => patch({ estado: e.target.value, programada: "" })}>
            <option value="">Todos</option>
            <option value="pendiente">Pendiente</option>
            <option value="programada">Programada</option>
            <option value="reprogramada">Reprogramada</option>
            <option value="realizada">Realizada</option>
          </select>
        </div>
        <div className="field">
          <label title={help("cooldown")}>
            Visita reciente (&lt;{VISITA_RECIENTE_MESES} m)
          </label>
          <select value={enCooldown} onChange={(e) => patch({ enCooldown: e.target.value })}>
            <option value="">Todos</option>
            <option value="true">Con visita reciente</option>
            <option value="false">Sin visita reciente</option>
          </select>
        </div>
        <div className="field">
          <label title={help("prs")}>PRS</label>
          <select value={obligacionPrs} onChange={(e) => patch({ obligacionPrs: e.target.value })}>
            <option value="">Todos</option>
            <option value="true">Con PRS</option>
            <option value="false">Sin PRS</option>
          </select>
        </div>
        <div className="field">
          <label title={help("alerta")}>Alerta</label>
          <select value={alertaUmbral} onChange={(e) => patch({ alertaUmbral: e.target.value })}>
            <option value="">Todas</option>
            <option value="true">Con alerta</option>
            <option value="false">Sin alerta</option>
          </select>
        </div>
        <div className="field" style={{ minWidth: 110 }}>
          <label title={help("score")}>Puntaje mín.</label>
          <input
            type="number"
            step="0.01"
            min="0"
            max="1"
            value={scoreMin}
            placeholder="0.00"
            onChange={(e) => patch({ scoreMin: e.target.value })}
          />
        </div>
        <div className="field" style={{ minWidth: 110 }}>
          <label title={help("score")}>Puntaje máx.</label>
          <input
            type="number"
            step="0.01"
            min="0"
            max="1"
            value={scoreMax}
            placeholder="1.00"
            onChange={(e) => patch({ scoreMax: e.target.value })}
          />
        </div>
        <div className="field" style={{ minWidth: 220, flex: 1 }}>
          <label title={help("establecimiento")}>Buscar id</label>
          <input
            value={q}
            placeholder="establecimiento…"
            onChange={(e) => patch({ q: e.target.value })}
          />
        </div>
        <button className="ghost-btn" type="button" onClick={clearFilters}>
          Limpiar
        </button>
      </div>

      {error && <div className="error">{error}</div>}
      {success && <div className="success">{success}</div>}
      {loading && <p className="muted">Cargando lista de prioridad…</p>}

      {programar && (
        <ProgramarVisitaDialog
          item={programar}
          horizonte={horizonte}
          onClose={() => setProgramar(null)}
          onDone={() => {
            setProgramar(null);
            setSuccess("Visita programada. Podés verla en Agenda.");
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      <div className="table-wrap panel" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <Th id="ranking"> </Th>
              <Th id="establecimiento">Establecimiento</Th>
              <Th id="score">Puntaje</Th>
              <Th id="banda">Riesgo</Th>
              <Th id="motivo">Motivo</Th>
              <Th id="ciiu">Actividad</Th>
              <Th id="capitas">Cápitas</Th>
              <Th id="ultimaVisita">Última visita</Th>
              <Th id="cooldown">{`Visita reciente (<${VISITA_RECIENTE_MESES} m)`}</Th>
              <Th id="estadoOperativo">Estado</Th>
              <th title="Programar visita">Acción</th>
              <th title="Abrir la ficha del establecimiento con explicación del puntaje y acierto histórico"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const estado = item.estadoOperativo ?? "pendiente";
              const estadoLink =
                estado === "pendiente"
                  ? `/establecimientos/${item.idEstablecimiento}?horizonte=${horizonte}`
                  : estado === "realizada"
                    ? "/agenda?estado=realizada"
                    : "/agenda?estado=programada";
              const estadoTitle =
                estado === "pendiente"
                  ? "Pendiente de programar. Abrir detalle."
                  : estado === "realizada"
                    ? "Visita realizada. Abrir Agenda → Realizadas."
                    : estado === "reprogramada"
                      ? `Reprogramada${item.agendaActiva ? ` · ${item.agendaActiva.fechaPlanificada}` : ""}. Abrir Agenda.`
                      : `Programada${item.agendaActiva ? ` · ${item.agendaActiva.fechaPlanificada}` : ""}. Abrir Agenda.`;

              return (
              <tr key={item.id}>
                <td className="mono" title={tipRanking(item.ranking)}>
                  {item.ranking}
                </td>
                <td
                  className="mono"
                  title={`${item.idEstablecimiento}\n${help("establecimiento")}`}
                >
                  {shortId(item.idEstablecimiento)}
                </td>
                <td title={tipScore(item.scoreRiesgo)}>
                  <div className="score-cell">
                    <span className="mono">{item.scoreRiesgo.toFixed(3)}</span>
                    <div className="score-bar">
                      <span style={{ width: `${Math.min(100, item.scoreRiesgo * 100)}%` }} />
                    </div>
                  </div>
                </td>
                <td>
                  <span className={`badge ${item.banda}`} title={tipRiesgo(item.banda, item.ranking)}>
                    {riesgoLabel(item.banda)}
                  </span>
                </td>
                <td>
                  {item.motivo ? (
                    <span
                      className={`badge ${motivoBadgeClass(item.motivo)}`}
                      title={tipMotivo(item.motivo)}
                    >
                      {motivoLabel(item.motivo)}
                    </span>
                  ) : (
                    <span title={help("motivo")}>—</span>
                  )}
                </td>
                <td
                  title={`${ciiuDivisionLabel(item.ciiuDivision)}. ${help("ciiu")}`}
                >
                  {ciiuDivisionLabel(item.ciiuDivision)}
                </td>
                <td className="mono" title={tipCapitas(item.cantidadCapitas)}>
                  {item.cantidadCapitas != null ? Math.round(item.cantidadCapitas).toLocaleString("es-AR") : "—"}
                </td>
                <td className="mono" title={tipUltimaVisita(item.ultimaVisitaHaceMeses)}>
                  {item.ultimaVisitaHaceMeses != null ? `${item.ultimaVisitaHaceMeses} m` : "sin visita"}
                </td>
                <td>
                  {item.enCooldown ? (
                    <span
                      className="bool-icon ok"
                      title={tipVisitaReciente(true, item.ultimaVisitaHaceMeses)}
                    >
                      <IconCheck size={18} />
                    </span>
                  ) : (
                    <span
                      className="bool-icon no"
                      title={tipVisitaReciente(false, item.ultimaVisitaHaceMeses)}
                    >
                      <IconX size={18} />
                    </span>
                  )}
                </td>
                <td>
                  <Link
                    className={`badge ${estadoOperativoBadgeClass(estado)} estado-link`}
                    to={estadoLink}
                    title={estadoTitle}
                  >
                    {estadoOperativoLabel(estado)}
                  </Link>
                </td>
                <td>
                  {estado === "pendiente" || estado === "realizada" ? (
                    <button
                      type="button"
                      className="icon-btn primary"
                      title="Programar visita con fecha y responsable"
                      aria-label="Programar visita"
                      onClick={() => {
                        setSuccess(null);
                        setProgramar(item);
                      }}
                    >
                      <IconCalendar size={16} />
                    </button>
                  ) : (
                    <Link
                      className="icon-btn"
                      to="/agenda?estado=programada"
                      title="Ver en Agenda"
                      aria-label="Ver en Agenda"
                    >
                      <IconCalendar size={16} />
                    </Link>
                  )}
                </td>
                <td>
                  <Link
                    className="icon-btn"
                    to={`/establecimientos/${item.idEstablecimiento}?horizonte=${horizonte}`}
                    title="Ver detalle: explicación del puntaje, acierto histórico y ficha operativa"
                    aria-label="Ver detalle"
                  >
                    <IconExternal size={16} />
                  </Link>
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
