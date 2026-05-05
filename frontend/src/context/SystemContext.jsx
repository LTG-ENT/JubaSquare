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

export const SystemProvider = ({ children }) => {
  const [settings, setSettings] = useState(DEFAULTS);

  const refresh = async () => {
    try {
      const { data } = await api.get("/settings/public");
      setSettings({ ...DEFAULTS, ...data });
    } catch { /* ignore */ }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <SystemContext.Provider value={{ settings, refresh }}>{children}</SystemContext.Provider>
  );
};

export const useSystem = () => useContext(SystemContext);
