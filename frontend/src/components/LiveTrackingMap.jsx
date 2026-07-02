import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import api from "@/lib/api";
import { Bike, MapPin, Loader2 } from "lucide-react";

// Fix Leaflet's default icon paths — CRA bundles break the default lookup.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const driverIcon = new L.DivIcon({
  className: "",
  html: '<div style="width:34px;height:34px;background:#C84B31;border:3px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.25);"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="18.5" cy="17.5" r="3.5"/><circle cx="5.5" cy="17.5" r="3.5"/><circle cx="15" cy="5" r="1"/><path d="M12 17.5V14l-3-3 4-3 2 3h2"/></svg></div>',
  iconSize: [34, 34],
  iconAnchor: [17, 17],
});

/**
 * Customer-side live tracking panel. Polls
 * GET /api/customer/orders/{order_id}/live-tracking every 10 s,
 * renders a Leaflet map with a driver marker and destination marker,
 * shows distance and ETA.
 */
export default function LiveTrackingMap({ orderId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const { data } = await api.get(`/customer/orders/${orderId}/live-tracking`);
        if (!cancelled) {
          setData(data);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) setErr(e.response?.data?.detail || "Could not load live tracking");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 10_000);
    return () => { cancelled = true; clearInterval(id); };
  }, [orderId]);

  const center = useMemo(() => {
    if (!data) return [4.8517, 31.5825];
    const first = data.assignments?.find((a) => a.driver_location);
    if (first) return [first.driver_location.lat, first.driver_location.lng];
    return [data.destination.lat, data.destination.lng];
  }, [data]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--js-text-secondary)] p-4" data-testid="live-tracking-loading">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading map…
      </div>
    );
  }
  if (err) {
    return <p className="text-sm text-[#D90429] p-4" data-testid="live-tracking-error">{err}</p>;
  }
  if (!data || !data.assignments?.length) {
    return (
      <div className="p-4 text-sm text-[var(--js-text-secondary)] bg-[var(--js-subtle)] rounded-2xl" data-testid="live-tracking-empty">
        <p className="font-semibold text-[var(--js-text)] mb-1">No live driver yet</p>
        <p>We&apos;ll show a live map here as soon as a driver is on the way with your order.</p>
      </div>
    );
  }

  const drivers = data.assignments.filter((a) => a.driver_location);

  return (
    <div className="space-y-3" data-testid="live-tracking-panel">
      <div className="rounded-2xl overflow-hidden border border-[var(--js-border)]" style={{ height: 320 }}>
        <MapContainer center={center} zoom={14} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <Marker position={[data.destination.lat, data.destination.lng]}>
            <Popup>Delivery destination · {data.destination.area}</Popup>
          </Marker>
          {drivers.map((a) => (
            <Marker
              key={a.assignment_id}
              position={[a.driver_location.lat, a.driver_location.lng]}
              icon={driverIcon}
            >
              <Popup>
                <div className="text-xs">
                  <p className="font-bold">{a.driver_name}</p>
                  {a.eta_minutes != null && <p>ETA ~ {a.eta_minutes} min · {a.distance_km} km</p>}
                </div>
              </Popup>
            </Marker>
          ))}
          {drivers.map((a) => (
            <Polyline
              key={`line-${a.assignment_id}`}
              positions={[
                [a.driver_location.lat, a.driver_location.lng],
                [data.destination.lat, data.destination.lng],
              ]}
              pathOptions={{ color: "#C84B31", weight: 3, dashArray: "6 6" }}
            />
          ))}
        </MapContainer>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {data.assignments.map((a) => (
          <div
            key={a.assignment_id}
            className="bg-white border border-[var(--js-border)] rounded-2xl p-3"
            data-testid={`live-tracking-driver-${a.assignment_id}`}
          >
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-[#C84B31] text-white flex items-center justify-center">
                <Bike className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="font-display font-bold text-sm text-[var(--js-text)] truncate">{a.driver_name}</p>
                <p className="text-[10px] uppercase tracking-wider text-[var(--js-text-secondary)] font-bold">
                  {a.status?.replaceAll("_", " ")}
                </p>
              </div>
            </div>
            {a.driver_location ? (
              <div className="mt-2 text-xs flex items-center gap-3 text-[var(--js-text-secondary)]">
                <span>~{a.eta_minutes} min</span>
                <span>·</span>
                <span>{a.distance_km} km away</span>
              </div>
            ) : (
              <p className="mt-2 text-xs text-[var(--js-text-secondary)] inline-flex items-center gap-1">
                <MapPin className="w-3 h-3" /> Location not shared yet
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
