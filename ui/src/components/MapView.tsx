import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { MapData } from "../api";

const riskColor = (r: number) => (r >= 0.6 ? "#ef4444" : r >= 0.4 ? "#f59e0b" : "#22c55e");

export default function MapView({ data }: { data: MapData | null }) {
  return (
    <MapContainer center={[22, 40]} zoom={2} minZoom={2} className="h-[420px] w-full rounded-lg" worldCopyJump>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {data?.suppliers.map((s) => (
        <CircleMarker
          key={s.id}
          center={[s.lat, s.lon]}
          radius={s.tier === 1 ? 4 : 3}
          pathOptions={{ color: s.status === "disrupted" ? "#ef4444" : riskColor(s.risk_score), weight: 1, fillOpacity: 0.6 }}
        >
          <Tooltip>
            {s.name} ({s.id}) tier {s.tier}, {s.country}, risk {s.risk_score}
            {s.status === "disrupted" ? " DISRUPTED" : ""}
          </Tooltip>
        </CircleMarker>
      ))}
      {data?.plants.map((p) => (
        <CircleMarker key={p.id} center={[p.lat, p.lon]} radius={5} pathOptions={{ color: "#2dd4bf", weight: 2, fillOpacity: 0.3 }}>
          <Tooltip>
            {p.name} ({p.id}) ships from {p.port}
          </Tooltip>
        </CircleMarker>
      ))}
      {data?.ports.map((p) => (
        <CircleMarker
          key={p.id}
          center={[p.lat, p.lon]}
          radius={p.status === "disrupted" ? 11 : 7}
          pathOptions={{ color: p.status === "disrupted" ? "#ef4444" : "#38bdf8", weight: 2, fillOpacity: p.status === "disrupted" ? 0.7 : 0.4 }}
        >
          <Tooltip>
            Port {p.name} ({p.id}) {p.status === "disrupted" ? "CLOSED" : "open"}, risk {p.risk_score}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
