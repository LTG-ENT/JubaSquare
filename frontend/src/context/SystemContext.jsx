import { createContext, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const SystemContext = createContext(null);

const DEFAULTS = {
  global_rate: 600,
  currency_display: true,
  verified_first: true,
  module_marketplace: true,
  module_restaurants: true,
  module_wholesale: true,
  maintenance_mode: false,
  areas: ["Munuki", "Jebel", "Gudele", "Konyo Konyo", "Hai Cinema", "Nyakuron", "Atlabara"],
};

/**
 * Cache the last-known maintenance flag in localStorage so a returning visitor
 * gets the correct page rendered synchronously on first paint (no flash of the
 * normal site before the API says "maintenance is on").
 */
const CACHE_KEY = "js_system_last_known";

function readCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    // Only trust the cache for a short window (5 minutes) so a stale flag
    // doesn't keep the whole site down after admin flips it off.
    if (!v || !v.ts || Date.now() - v.ts > 5 * 60 * 1000) return null;
    return v.data;
  } catch { return null; }
}
function writeCache(data) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data })); } catch { /* ignore */ }
}

export const SystemProvider = ({ children }) => {
  // Boot with the last-known snapshot if we have one — kills the flash.
  const initial = readCache();
  const [settings, setSettings] = useState({ ...DEFAULTS, ...(initial || {}) });
  const [ready, setReady] = useState(!!initial);

  const refresh = async () => {
    try {
      const { data } = await api.get("/settings/public");
      const merged = { ...DEFAULTS, ...data };
      setSettings(merged);
      writeCache(merged);
    } catch { /* ignore transient failures */ }
    finally { setReady(true); }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <SystemContext.Provider value={{ settings, ready, refresh }}>
      {children}
    </SystemContext.Provider>
  );
};

export const useSystem = () => useContext(SystemContext);
