import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";

/**
 * Silent driver-side beacon: while `active` is true, subscribes to
 * geolocation updates and pushes them to POST /api/driver/location
 * roughly every 10 seconds. No UI beyond an optional inline status.
 *
 * Mount this at the driver dashboard whenever the driver has ≥1
 * assignment in `out_for_delivery` state. Unmounts safely.
 */
export default function DriverGeoBeacon({ active }) {
  const watchIdRef = useRef(null);
  const lastPushRef = useRef(0);
  const [status, setStatus] = useState("idle"); // idle | live | error | denied
  const [lastPushed, setLastPushed] = useState(null);

  useEffect(() => {
    if (!active) {
      cleanup();
      setStatus("idle");
      return;
    }
    if (!("geolocation" in navigator)) {
      setStatus("error");
      return;
    }

    const push = async (coords) => {
      try {
        await api.post("/driver/location", {
          lat: coords.latitude,
          lng: coords.longitude,
          accuracy: coords.accuracy || null,
        });
        setLastPushed(new Date());
        setStatus("live");
      } catch {
        setStatus("error");
      }
    };

    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const now = Date.now();
        // Throttle: at most once every 10 s.
        if (now - lastPushRef.current < 10_000) return;
        lastPushRef.current = now;
        push(pos.coords);
      },
      (err) => {
        // 1 = PERMISSION_DENIED, 2 = POSITION_UNAVAILABLE, 3 = TIMEOUT
        setStatus(err.code === 1 ? "denied" : "error");
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );

    return cleanup;
  }, [active]);

  const cleanup = () => {
    if (watchIdRef.current !== null && "geolocation" in navigator) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
  };

  if (!active) return null;

  const label = {
    idle: "Getting your location…",
    live: lastPushed ? `Live · last updated ${timeAgo(lastPushed)}` : "Live",
    error: "Location error — retrying",
    denied: "Location permission denied — enable in your browser to be tracked.",
  }[status];

  return (
    <div
      data-testid="driver-geo-beacon"
      className={`text-xs font-semibold px-3 py-1.5 rounded-full inline-flex items-center gap-2 border ${
        status === "denied" || status === "error"
          ? "bg-[#D90429]/10 border-[#D90429]/40 text-[#D90429]"
          : "bg-[#2D6A4F]/10 border-[#2D6A4F]/40 text-[#2D6A4F]"
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${status === "live" ? "bg-[#2D6A4F] animate-pulse" : "bg-current"}`} />
      {label}
    </div>
  );
}

function timeAgo(date) {
  const s = Math.max(1, Math.floor((Date.now() - date.getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  return `${Math.floor(s / 60)}m ago`;
}
