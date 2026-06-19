import { useMemo } from "react"
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  Popup,
  useMap,
} from "react-leaflet"
import L from "leaflet"

// Color for each stop type (matches the legend below).
const STOP_COLORS = {
  current: "#16a34a",
  pickup: "#2563eb",
  dropoff: "#dc2626",
  fuel: "#ea580c",
  rest: "#6b7280",
  restart: "#6b7280",
  break: "#6b7280",
}

// Build a colored teardrop pin as an inline-SVG divIcon so each marker
// reliably renders in its own color (CSS filters on the default PNG are
// unreliable and were making every marker appear blue).
function makeIcon(color) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="40" viewBox="0 0 26 40">
    <path d="M13 0C5.82 0 0 5.82 0 13c0 9.25 13 27 13 27s13-17.75 13-27C26 5.82 20.18 0 13 0z" fill="${color}" stroke="#ffffff" stroke-width="2"/>
    <circle cx="13" cy="13" r="5" fill="#ffffff"/>
  </svg>`
  return L.divIcon({
    html: svg,
    className: "route-marker",
    iconSize: [26, 40],
    iconAnchor: [13, 40],
    popupAnchor: [0, -36],
  })
}

const ICONS = Object.fromEntries(
  Object.entries(STOP_COLORS).map(([type, color]) => [type, makeIcon(color)]),
)

const LEGEND = [
  { type: "current", color: STOP_COLORS.current, label: "Current Location" },
  { type: "pickup", color: STOP_COLORS.pickup, label: "Pickup" },
  { type: "dropoff", color: STOP_COLORS.dropoff, label: "Dropoff" },
  { type: "fuel", color: STOP_COLORS.fuel, label: "Fuel Stop" },
  { type: "rest", color: STOP_COLORS.rest, label: "Rest / Restart" },
]

function FitBounds({ polyline }) {
  const map = useMap()
  useMemo(() => {
    if (polyline && polyline.length > 1) {
      map.fitBounds(polyline, { padding: [40, 40] })
    }
  }, [polyline, map])
  return null
}

export default function RouteMap({ polyline, stops }) {
  const center = polyline?.length
    ? polyline[Math.floor(polyline.length / 2)]
    : [39.5, -86.5]

  return (
    <div className="overflow-hidden rounded-2xl bg-white shadow-xl ring-1 ring-slate-200">
      <div className="h-[420px] w-full sm:h-[480px]">
        <MapContainer
          center={center}
          zoom={5}
          scrollWheelZoom
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {polyline?.length > 1 && (
            <Polyline positions={polyline} pathOptions={{ color: "#2563eb", weight: 4 }} />
          )}
          {stops?.map((stop, i) => (
            <Marker
              key={`${stop.type}-${i}`}
              position={[stop.lat, stop.lng]}
              icon={ICONS[stop.type] || ICONS.rest}
            >
              <Popup>
                <div className="text-sm">
                  <p className="font-semibold text-slate-900">{stop.label}</p>
                  <p className="text-slate-600">Arrival: {stop.arrival}</p>
                  <p className="text-slate-600">Departure: {stop.departure}</p>
                  <p className="text-slate-600">
                    Duration: {stop.duration_hours} h
                  </p>
                </div>
              </Popup>
            </Marker>
          ))}
          <FitBounds polyline={polyline} />
        </MapContainer>
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-200 px-5 py-4">
        {LEGEND.map((item) => (
          <div key={item.type} className="flex items-center gap-2">
            <span
              className="inline-block h-3.5 w-3.5 rounded-full ring-2 ring-white"
              style={{ backgroundColor: item.color }}
              aria-hidden="true"
            />
            <span className="text-sm font-medium text-slate-700">
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
