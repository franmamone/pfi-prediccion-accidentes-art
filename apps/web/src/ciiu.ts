const CIIU_DIVISION_NAMES: Record<string, string> = {
  "01": "Agricultura y ganadería",
  "02": "Silvicultura",
  "05": "Pesca",
  "10": "Extracción de carbón",
  "11": "Extracción de petróleo y gas",
  "12": "Extracción de uranio",
  "13": "Extracción de minerales metalíferos",
  "14": "Explotación de otras minas",
  "15": "Alimentos y bebidas",
  "16": "Tabaco",
  "17": "Textiles",
  "18": "Prendas de vestir",
  "19": "Cuero y calzado",
  "20": "Madera",
  "21": "Papel",
  "22": "Edición e impresión",
  "23": "Coque y refinación de petróleo",
  "24": "Productos químicos",
  "25": "Caucho y plástico",
  "26": "Minerales no metálicos",
  "27": "Metales comunes",
  "28": "Productos elaborados de metal",
  "29": "Maquinaria y equipo",
  "30": "Maquinaria de oficina",
  "31": "Maquinaria y aparatos eléctricos",
  "32": "Radio, TV y comunicaciones",
  "33": "Instrumentos médicos y de precisión",
  "34": "Vehículos automotores",
  "35": "Otros equipos de transporte",
  "36": "Muebles y otras manufacturas",
  "37": "Reciclamiento",
  "40": "Electricidad y gas",
  "41": "Captación y distribución de agua",
  "45": "Construcción",
  "50": "Venta y reparación de vehículos",
  "51": "Comercio mayorista",
  "52": "Comercio minorista",
  "55": "Hoteles y restaurantes",
  "60": "Transporte terrestre",
  "61": "Transporte por agua",
  "62": "Transporte aéreo",
  "63": "Servicios auxiliares de transporte",
  "64": "Correo y telecomunicaciones",
  "65": "Intermediación financiera",
  "66": "Seguros",
  "67": "Servicios auxiliares financieros",
  "70": "Actividades inmobiliarias",
  "71": "Alquiler de maquinaria y equipo",
  "72": "Informática",
  "73": "Investigación y desarrollo",
  "74": "Servicios empresariales",
  "75": "Administración pública y defensa",
  "80": "Enseñanza",
  "85": "Servicios sociales y de salud",
  "90": "Saneamiento y gestión de residuos",
  "91": "Actividades asociativas",
  "92": "Actividades culturales y deportivas",
  "93": "Otros servicios",
  "95": "Hogares con servicio doméstico",
  "99": "Organizaciones extraterritoriales",
};

export function ciiuDivisionName(code: string | null | undefined): string {
  if (!code) return "Sin actividad informada";
  const normalized = code.padStart(2, "0");
  return CIIU_DIVISION_NAMES[normalized] ?? "Actividad no catalogada";
}

export function ciiuDivisionLabel(code: string | null | undefined): string {
  if (!code) return "Sin actividad informada";
  const normalized = code.padStart(2, "0");
  return `${ciiuDivisionName(normalized)} (${normalized})`;
}
