/** Textos de ayuda (tooltips) para columnas, filtros y celdas de la grilla. */

export const VISITA_RECIENTE_MESES = 3;
// Escala de riesgo por acierto histórico (precision@K del tramo), holdout 2025.
export const RIESGO_ACIERTO_CRITICO = 80;
export const RIESGO_ACIERTO_ALTO = 60;
export const RIESGO_ACIERTO_MEDIO = 30;

export const COLUMN_HELP: Record<string, string> = {
  ranking:
    "Posición en la lista de prioridad del próximo trimestre. #1 = máxima prioridad de visita para ese horizonte.",
  establecimiento:
    "Identificador anonimizado del establecimiento (hash). Se muestra abreviado en la grilla; el valor completo está en el detalle.",
  score:
    "Puntaje del modelo (0–1): prioriza a quién visitar primero. No es una probabilidad calibrada de accidente. Más alto = más prioritario.",
  efectividad:
    "Efectividad histórica (holdout 2025): entre los establecimientos que el modelo ubicó en el mismo tramo del ranking (top 50/100/200/300/500/675/1000), qué porcentaje registró al menos un accidente en el trimestre siguiente. Es una referencia grupal por tramo, no una probabilidad individual del establecimiento.",
  banda:
    "Nivel de riesgo según el acierto histórico (precision@K) del tramo del ranking, medido en holdout 2025 sobre el horizonte trimestral: Crítico ≥80%, Alto ≥60%, Medio ≥30% y Bajo <30% de acierto.",
  motivo:
    "Por qué entra en la lista: Predictivo = solo el modelo ML; Predictivo + PRS = modelo y además obligación de Plan de Reducción de Siniestralidad; PRS = regla regulatoria.",
  ciiu:
    "Actividad económica del establecimiento (división CIIU Rev. 3). Se muestra el nombre y el código entre paréntesis.",
  sector: "Rubro agregado (Construcción, Industria, Comercio, etc.) usado para agrupar actividades similares.",
  capitas:
    "Cantidad de cápitas afiliadas: proxy de personas expuestas. Más cápitas suele implicar mayor impacto potencial si ocurre un evento.",
  dotacion: "Trabajadores en nómina del mes del corte: proxy del tamaño operativo actual del establecimiento.",
  ultimaVisita:
    `Meses transcurridos desde la última visita de prevención registrada hasta el período del corte. “Sin visita” = no hay visita en el historial del panel.`,
  cooldown:
    `Visita reciente = última visita hace menos de ${VISITA_RECIENTE_MESES} meses. Tilde verde = sí (en “enfriamiento”: normalmente no debería consumir capacidad nueva, salvo criticidad alta). Cruz = no (disponible para priorizar visita).`,
  prs: "Obligación de Plan de Reducción de Siniestralidad (PRS): la visita tiene componente regulatorio además del predictivo.",
  alerta:
    "El puntaje supera el umbral operativo del modelo (calibrado en entrenamiento). Marca atención reforzada, no un accidente seguro.",
  empleador: "Identificador anonimizado del empleador al que pertenece el establecimiento.",
  programada:
    "Si el establecimiento ya tiene una visita en Agenda en estado programada. No programadas = disponibles para agendar desde esta grilla.",
  estadoOperativo:
    "Estado operativo: Pendiente, Reagendar (plazo del preventor sin turno aún), Programada, Reprogramada o Realizada. Filtrá por Reagendar para agenda próximas visitas.",
};

export function help(key: keyof typeof COLUMN_HELP | string): string {
  return COLUMN_HELP[key] ?? "";
}

export function tipRanking(ranking: number): string {
  return `#${ranking} en la lista de prioridad. ${help("ranking")}`;
}

export function tipScore(score: number): string {
  return `Puntaje ${score.toFixed(4)}. ${help("score")}`;
}

export function tipEfectividad(pct: number | null, topK: number | null): string {
  if (pct == null || topK == null) {
    return `Sin referencia de efectividad para esta posición. ${help("efectividad")}`;
  }
  return (
    `${pct.toLocaleString("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}% de acierto histórico en el tramo top ${topK} (holdout 2025). ` +
    `${help("efectividad")}`
  );
}

export function tipRiesgo(banda: string, ranking: number): string {
  const nivel =
    banda === "critico"
      ? `Crítico: acierto histórico ≥${RIESGO_ACIERTO_CRITICO}% en su tramo (holdout 2025).`
      : banda === "alto"
        ? `Alto: acierto histórico ≥${RIESGO_ACIERTO_ALTO}% y <${RIESGO_ACIERTO_CRITICO}%.`
        : banda === "medio"
          ? `Medio: acierto histórico ≥${RIESGO_ACIERTO_MEDIO}% y <${RIESGO_ACIERTO_ALTO}%.`
          : `Bajo: acierto histórico <${RIESGO_ACIERTO_MEDIO}% (cola de la lista).`;
  return `Posición #${ranking}. ${nivel} Escala: Crítico ≥${RIESGO_ACIERTO_CRITICO}%, Alto ≥${RIESGO_ACIERTO_ALTO}%, Medio ≥${RIESGO_ACIERTO_MEDIO}%, Bajo <${RIESGO_ACIERTO_MEDIO}%.`;
}

export function tipMotivo(motivo: string | null): string {
  if (!motivo) return help("motivo");
  const key = motivo.toLowerCase();
  if (key.includes("predict") && key.includes("prs")) {
    return "Predictivo + PRS: el modelo lo prioriza y además tiene obligación de Plan de Reducción de Siniestralidad.";
  }
  if (key.includes("predict")) {
    return "Predictivo: entra por el modelo de machine learning (patrón histórico de accidentes, exposición y contexto).";
  }
  if (key.includes("prs")) {
    return "PRS: obligación regulatoria de Plan de Reducción de Siniestralidad.";
  }
  return `${motivo}. ${help("motivo")}`;
}

export function tipCapitas(value: number | null): string {
  if (value == null) return `Sin dato de cápitas. ${help("capitas")}`;
  return `${Math.round(value).toLocaleString("es-AR")} cápitas. ${help("capitas")}`;
}

export function tipUltimaVisita(meses: number | null): string {
  if (meses == null) {
    return `Sin visita registrada en el panel. ${help("ultimaVisita")}`;
  }
  const reciente =
    meses < VISITA_RECIENTE_MESES
      ? `Se considera visita reciente (< ${VISITA_RECIENTE_MESES} meses).`
      : `No es visita reciente (≥ ${VISITA_RECIENTE_MESES} meses).`;
  return `Última visita hace ${meses} mes(es). ${reciente}`;
}

export function tipVisitaReciente(enCooldown: boolean, meses: number | null): string {
  if (enCooldown) {
    return (
      `Sí: última visita hace ${meses ?? "?"} mes(es), menor a ${VISITA_RECIENTE_MESES} meses. ` +
      "Criterio de “visita reciente”: meses desde la última visita de prevención < " +
      `${VISITA_RECIENTE_MESES}. Suele evitar consumir capacidad nueva, salvo criticidad alta.`
    );
  }
  if (meses == null) {
    return (
      `No: sin visita registrada. Criterio: se marca “visita reciente” solo si hubo visita hace menos de ` +
      `${VISITA_RECIENTE_MESES} meses.`
    );
  }
  return (
    `No: última visita hace ${meses} mes(es) (≥ ${VISITA_RECIENTE_MESES}). ` +
    `Criterio: visita reciente = menos de ${VISITA_RECIENTE_MESES} meses desde la última visita de prevención.`
  );
}
