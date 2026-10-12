import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const CABA_CENTER: [number, number] = [-34.6037, -58.3816];
const CABA_BOUNDS = {
  latMin: -34.7,
  latMax: -34.53,
  lonMin: -58.53,
  lonMax: -58.34,
};

function clampCaba(lat: number, lon: number): { lat: number; lon: number } {
  return {
    lat: Math.min(CABA_BOUNDS.latMax, Math.max(CABA_BOUNDS.latMin, lat)),
    lon: Math.min(CABA_BOUNDS.lonMax, Math.max(CABA_BOUNDS.lonMin, lon)),
  };
}

function ClickHandler({
  onPick,
}: {
  onPick: (lat: number, lon: number) => void;
}) {
  useMapEvents({
    click(e) {
      const c = clampCaba(e.latlng.lat, e.latlng.lng);
      onPick(c.lat, c.lon);
    },
  });
  return null;
}

function Recenter({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lon], map.getZoom(), { animate: true });
  }, [map, lat, lon]);
  return null;
}

type Props = {
  lat: number;
  lon: number;
  onChange: (lat: number, lon: number) => void;
};

export function CabaLocationPicker({ lat, lon, onChange }: Props) {
  const point = clampCaba(lat, lon);

  return (
    <div className="field">
      <label>Ubicación en CABA</label>
      <p className="muted" style={{ margin: "0 0 8px", fontSize: 12 }}>
        Hacé clic en el mapa para marcar el punto de trabajo del preventor.
      </p>
      <div className="caba-picker-map">
        <MapContainer
          center={[point.lat, point.lon]}
          zoom={12}
          scrollWheelZoom
          style={{ height: "100%", width: "100%", borderRadius: 10 }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickHandler onPick={onChange} />
          <Recenter lat={point.lat} lon={point.lon} />
          <CircleMarker
            center={[point.lat, point.lon]}
            radius={10}
            pathOptions={{
              color: "#1d4ed8",
              fillColor: "#3b82f6",
              fillOpacity: 0.9,
              weight: 2,
            }}
          />
        </MapContainer>
      </div>
      <p className="caba-picker-coords muted">
        {point.lat.toFixed(5)}, {point.lon.toFixed(5)}
      </p>
    </div>
  );
}

export { CABA_CENTER };
