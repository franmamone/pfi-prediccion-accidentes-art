import { useEffect, useState } from "react";
import { fetchRiesgo, type Horizonte } from "../api";
import { ciiuDivisionName } from "../ciiu";
import { motivoLabel, riesgoLabel } from "../labels";

export function ExportPage() {
  const [horizonte, setHorizonte] = useState<Horizonte>("1m");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    setStatus(null);
  }, [horizonte]);

  async function exportCsv() {
    setStatus("Generando…");
    try {
      const data = await fetchRiesgo({ horizonte, top: 225 });
      const header = [
        "posicion_prioridad",
        "id_establecimiento",
        "puntaje_riesgo",
        "riesgo",
        "motivo",
        "ciiu_division",
        "actividad",
        "cantidad_capitas",
        "dotacion_nomina_mes",
      ];
      const lines = [header.join(";")];
      for (const item of data.items) {
        lines.push(
          [
            item.ranking,
            item.idEstablecimiento,
            item.scoreRiesgo,
            riesgoLabel(item.banda),
            motivoLabel(item.motivo),
            item.ciiuDivision ?? "",
            ciiuDivisionName(item.ciiuDivision),
            item.cantidadCapitas ?? "",
            item.dotacionNominaMes ?? "",
          ].join(";"),
        );
      }
      const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lista_prioridad_${data.horizonte}_${data.periodo}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus(`Exportados ${data.items.length} registros (${data.periodo}).`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Error al exportar");
    }
  }

  return (
    <>
      <h1 className="page-title">Exportaciones</h1>
      <p className="page-sub">Descargá la lista de prioridad vigente para llevar a campo.</p>
      <div className="panel" style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
        <div className="horizon-toggle">
          <button className={horizonte === "1m" ? "active" : ""} onClick={() => setHorizonte("1m")}>
            Mes
          </button>
          <button className={horizonte === "3m" ? "active" : ""} onClick={() => setHorizonte("3m")}>
            Trimestre
          </button>
        </div>
        <button className="btn" onClick={exportCsv}>
          Descargar CSV
        </button>
        {status && <span className="muted">{status}</span>}
      </div>
    </>
  );
}
