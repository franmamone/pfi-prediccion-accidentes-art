import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchRiesgo, shortId, type Horizonte, type RankingItem } from "../api";
import { ciiuDivisionLabel } from "../ciiu";
import {
  help,
  tipCapitas,
  tipEfectividad,
  tipRanking,
  tipRiesgo,
  tipUltimaVisita,
} from "../columnHelp";
import { ProgramarVisitaDialog } from "../components/ProgramarVisitaDialog";
import { Select } from "../components/Select";
import { EmptyState, SkeletonTable } from "../components/UiKit";
import { IconCalendar, IconExternal } from "../icons";
import {
  estadoOperativoBadgeClass,
  estadoOperativoLabel,
  riesgoLabel,
} from "../labels";
import { consumeRiesgoScroll, getHorizontePref, saveRiesgoScroll, setHorizontePref } from "../prefs";
import { useToast } from "../toast";

function Th({ id, children }: { id: string; children: ReactNode }) {
  return <th title={help(id)}>{children}</th>;
}

export function RiesgoPage() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const horizonte = (params.get("horizonte") as Horizonte) || getHorizontePref();
  const banda = params.get("banda") || "";
  const sector = params.get("sector") || "";
  const q = params.get("q") || "";
  const obligacionPrs = params.get("obligacionPrs") || "";
  const programada = params.get("programada") || "";
  const estadoOperativo = params.get("estado") || "";
  const [items, setItems] = useState<RankingItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [programar, setProgramar] = useState<RankingItem | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 50;

  useEffect(() => {
    if (!params.get("horizonte")) {
      const merged = new URLSearchParams(params);
      merged.set("horizonte", getHorizontePref());
      setParams(merged, { replace: true });
    }
  }, [params, setParams]);

  useEffect(() => {
    setHorizontePref(horizonte);
  }, [horizonte]);

  useEffect(() => {
    const y = consumeRiesgoScroll();
    if (y == null) return;
    const id = window.setTimeout(() => window.scrollTo({ top: y, behavior: "auto" }), 40);
    return () => window.clearTimeout(id);
  }, []);

  const load = useCallback(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fetchRiesgo({
      horizonte,
      banda: banda || undefined,
      sector: sector || undefined,
      q: q || undefined,
      obligacionPrs: obligacionPrs || undefined,
      programada: programada || undefined,
      estadoOperativo: estadoOperativo || undefined,
      top: 1000,
    })
      .then((res) => {
        if (!alive) return;
        setItems(res.items);
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
    q,
    obligacionPrs,
    programada,
    estadoOperativo,
  ]);

  useEffect(() => {
    return load();
  }, [load, reloadKey]);

  const sectors = useMemo(() => {
    const set = new Set(items.map((i) => i.ciiuDivision).filter(Boolean) as string[]);
    return Array.from(set).sort();
  }, [items]);

  useEffect(() => {
    setPage(1);
  }, [horizonte, banda, sector, q, obligacionPrs, programada, estadoOperativo, reloadKey]);

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedItems = useMemo(
    () => items.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [items, currentPage],
  );
  const rangeStart = items.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const rangeEnd = Math.min(currentPage * pageSize, items.length);

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

  function rememberScroll() {
    saveRiesgoScroll(window.scrollY);
  }

  return (
    <div className="riesgo-layout">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 className="page-title">Priorización</h1>
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
          <Select
            value={banda}
            onChange={(v) => patch({ banda: v })}
            ariaLabel="Filtrar por riesgo"
            options={[
              { value: "", label: "Todos" },
              { value: "critico", label: "Crítico" },
              { value: "alto", label: "Alto" },
              { value: "medio", label: "Medio" },
              { value: "bajo", label: "Bajo" },
            ]}
          />
        </div>
        <div className="field">
          <label title={help("ciiu")}>División CIIU</label>
          <Select
            value={sector}
            onChange={(v) => patch({ sector: v })}
            ariaLabel="Filtrar por división CIIU"
            searchable
            options={[
              { value: "", label: "Todas" },
              ...sectors.map((s) => ({ value: s, label: ciiuDivisionLabel(s) })),
            ]}
          />
        </div>
        <div className="field">
          <label title={help("estadoOperativo")}>Estado</label>
          <Select
            value={estadoOperativo}
            onChange={(v) => patch({ estado: v, programada: "" })}
            ariaLabel="Filtrar por estado"
            options={[
              { value: "", label: "Todos" },
              { value: "pendiente", label: "Pendiente" },
              { value: "programada", label: "Programada" },
              { value: "reprogramada", label: "Reprogramada" },
              { value: "realizada", label: "Realizada" },
            ]}
          />
        </div>
        <div className="field">
          <label title={help("prs")}>PRS</label>
          <Select
            value={obligacionPrs}
            onChange={(v) => patch({ obligacionPrs: v })}
            ariaLabel="Filtrar por PRS"
            options={[
              { value: "", label: "Todos" },
              { value: "true", label: "Con PRS" },
              { value: "false", label: "Sin PRS" },
            ]}
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
      {loading && <SkeletonTable rows={10} />}

      {programar && (
        <ProgramarVisitaDialog
          item={programar}
          horizonte={horizonte}
          onClose={() => setProgramar(null)}
          onDone={() => {
            setProgramar(null);
            toast.success("Visita programada", "Ya está disponible en Agenda.");
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {!loading && items.length === 0 && !error ? (
        <div className="panel">
          <EmptyState
            title="Ningún establecimiento con estos filtros"
            detail="Probá limpiar filtros o cambiar el horizonte Mes / Trimestre."
            action={
              <button type="button" className="ghost-btn" onClick={clearFilters}>
                Limpiar filtros
              </button>
            }
          />
        </div>
      ) : null}

      {!loading && items.length > 0 ? (
      <div className="table-wrap panel table-sticky" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <Th id="ranking"> </Th>
              <Th id="establecimiento">Establecimiento</Th>
              <Th id="efectividad">Efectividad histórica</Th>
              <Th id="banda">Riesgo</Th>
              <Th id="ciiu">Actividad</Th>
              <Th id="capitas">Cápitas</Th>
              <Th id="ultimaVisita">Última visita</Th>
              <Th id="estadoOperativo">Estado</Th>
              <th title="Programar visita">Acción</th>
              <th title="Abrir la ficha del establecimiento con explicación del puntaje y acierto histórico"></th>
            </tr>
          </thead>
          <tbody>
            {pagedItems.map((item) => {
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
                <td title={tipEfectividad(item.efectividadHistorica, item.efectividadTopK)}>
                  {item.efectividadHistorica != null ? (
                    <div className="score-cell">
                      <span className="mono">{item.efectividadHistorica.toFixed(1)}%</span>
                      <div className="score-bar">
                        <span style={{ width: `${Math.min(100, item.efectividadHistorica)}%` }} />
                      </div>
                    </div>
                  ) : (
                    <span className="muted" title={tipEfectividad(null, null)}>
                      —
                    </span>
                  )}
                </td>
                <td>
                  <span className={`badge ${item.banda}`} title={tipRiesgo(item.banda, item.ranking)}>
                    {riesgoLabel(item.banda)}
                  </span>
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
                  <Link
                    className={`badge ${estadoOperativoBadgeClass(estado)} estado-link`}
                    to={estadoLink}
                    title={estadoTitle}
                    onClick={estado === "pendiente" ? rememberScroll : undefined}
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
                      onClick={() => setProgramar(item)}
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
                    onClick={rememberScroll}
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
      ) : null}

      {!loading && items.length > 0 ? (
        <div className="pagination">
          <span className="pagination-info">
            {rangeStart}–{rangeEnd} de {items.length.toLocaleString("es-AR")}
          </span>
          <div className="pagination-controls">
            <button
              type="button"
              className="ghost-btn"
              disabled={currentPage <= 1}
              onClick={() => {
                setPage(1);
                window.scrollTo({ top: 0, behavior: "auto" });
              }}
              title="Primera página"
            >
              «
            </button>
            <button
              type="button"
              className="ghost-btn"
              disabled={currentPage <= 1}
              onClick={() => {
                setPage((p) => Math.max(1, p - 1));
                window.scrollTo({ top: 0, behavior: "auto" });
              }}
              title="Página anterior"
            >
              ‹ Anterior
            </button>
            <span className="pagination-page">
              Página {currentPage} / {totalPages}
            </span>
            <button
              type="button"
              className="ghost-btn"
              disabled={currentPage >= totalPages}
              onClick={() => {
                setPage((p) => Math.min(totalPages, p + 1));
                window.scrollTo({ top: 0, behavior: "auto" });
              }}
              title="Página siguiente"
            >
              Siguiente ›
            </button>
            <button
              type="button"
              className="ghost-btn"
              disabled={currentPage >= totalPages}
              onClick={() => {
                setPage(totalPages);
                window.scrollTo({ top: 0, behavior: "auto" });
              }}
              title="Última página"
            >
              »
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
