import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import { useEffect } from "react";
import type { CandidatoAsignacion } from "../api";
import "leaflet/dist/leaflet.css";

type Props = {
  establecimiento: { latitud: number; longitud: number };
  candidatos: CandidatoAsignacion[];
  seleccionadoId: number;
  recomendadoId: number | null;
  onSelect: (id: number) => void;
};

function FitBounds({
  establecimiento,
  candidatos,
}: {
  establecimiento: { latitud: number; longitud: number };
  candidatos: CandidatoAsignacion[];
}) {
  const map = useMap();
  useEffect(() => {
    // Tras montar en un modal (p. ej. al cambiar de domingo a lunes) el tamaño puede ser 0.
    const t = window.setTimeout(() => map.invalidateSize(), 80);
    const pts: [number, number][] = [[establecimiento.latitud, establecimiento.longitud]];
    for (const c of candidatos) pts.push([c.latitud, c.longitud]);
    if (pts.length === 1) {
      map.setView(pts[0], 13);
    } else {
      map.fitBounds(pts, { padding: [28, 28], maxZoom: 14 });
    }
    return () => window.clearTimeout(t);
  }, [map, establecimiento, candidatos]);
  return null;
}

/** Color por carga relativa (sin tope duro). */
function colorCarga(n: number): string {
  if (n >= 6) return "#b45309";
  if (n >= 4) return "#ca8a04";
  if (n >= 2) return "#2563eb";
  return "#059669";
}

export function AsignacionMap({
  establecimiento,
  candidatos,
  seleccionadoId,
  recomendadoId,
  onSelect,
}: Props) {
  return (
    <div className="asignacion-map">
      <MapContainer
        center={[establecimiento.latitud, establecimiento.longitud]}
        zoom={12}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%", borderRadius: 10 }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds establecimiento={establecimiento} candidatos={candidatos} />
        <CircleMarker
          center={[establecimiento.latitud, establecimiento.longitud]}
          radius={11}
          pathOptions={{ color: "#dc2626", fillColor: "#ef4444", fillOpacity: 0.9, weight: 2 }}
        >
          <Popup>Establecimiento</Popup>
        </CircleMarker>
        {candidatos.map((c) => (
          <CircleMarker
            key={c.id}
            center={[c.latitud, c.longitud]}
            radius={c.id === seleccionadoId ? 10 : 7}
            pathOptions={{
              color: c.id === seleccionadoId ? "#eaf0fb" : colorCarga(c.visitasDelDia),
              fillColor: colorCarga(c.visitasDelDia),
              fillOpacity: 0.85,
              weight: c.id === seleccionadoId ? 3 : c.id === recomendadoId ? 2 : 1,
            }}
            eventHandlers={{ click: () => onSelect(c.id) }}
          >
            <Popup>
              {c.nombre}
              <br />
              {c.distanciaKm} km · {c.visitasDelDia} visitas
              {c.disponibleEnHora ? " · libre en hora elegida" : " · elegir otro horario"}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
