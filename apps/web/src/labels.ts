/** Etiquetas amigables para valores crudos de la API. */

const RIESGO_LABEL: Record<string, string> = {
  critico: "Crítico",
  alto: "Alto",
  medio: "Medio",
  bajo: "Bajo",
};

const MOTIVO_LABEL: Record<string, string> = {
  predictivo: "Predictivo",
  "predictivo+prs": "Predictivo + PRS",
  prs: "PRS",
  regulatorio: "Regulatorio",
};

export function riesgoLabel(banda: string | null | undefined): string {
  if (!banda) return "—";
  const key = banda.toLowerCase();
  return RIESGO_LABEL[key] ?? banda;
}

export function motivoLabel(motivo: string | null | undefined): string {
  if (!motivo) return "—";
  const key = motivo.toLowerCase().trim();
  return MOTIVO_LABEL[key] ?? motivo;
}

/** Clase CSS del badge de motivo (además de `.badge`). */
export function motivoBadgeClass(motivo: string | null | undefined): string {
  if (!motivo) return "motivo-otro";
  const key = motivo.toLowerCase().trim();
  if (key === "predictivo+prs" || key.includes("prs")) return "motivo-prs";
  if (key === "predictivo" || key.includes("predict")) return "motivo-predictivo";
  if (key.includes("regulator")) return "motivo-regulatorio";
  return "motivo-otro";
}

export function estadoOperativoLabel(estado: string | null | undefined): string {
  switch ((estado ?? "").toLowerCase()) {
    case "programada":
      return "Programada";
    case "reprogramada":
      return "Reprogramada";
    case "realizada":
      return "Realizada";
    case "reagendar":
      return "Reagendar";
    case "pendiente":
    default:
      return "Pendiente";
  }
}

export function estadoOperativoBadgeClass(estado: string | null | undefined): string {
  switch ((estado ?? "").toLowerCase()) {
    case "programada":
      return "estado-programada";
    case "reprogramada":
      return "estado-reprogramada";
    case "realizada":
      return "estado-realizada";
    case "reagendar":
      return "estado-reagendar";
    case "pendiente":
    default:
      return "estado-pendiente";
  }
}

export function formatFechaCorta(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = iso.slice(0, 10);
  const [y, m, day] = d.split("-");
  if (!y || !m || !day) return d;
  return `${day}/${m}/${y}`;
}
