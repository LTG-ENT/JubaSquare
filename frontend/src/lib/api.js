import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("js_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;

// ---------------------------------------------------------------------------
// Safe-array fallback layer
// ---------------------------------------------------------------------------
// Guarantees every consumer of a list endpoint gets an array — even if the
// API returns null, an object error, or undefined. Eliminates the entire
// class of "x.map is not a function" runtime crashes and makes the app
// resilient on flaky low-resource hosts where requests can return early.
//
// Usage: const products = safeArray(r.data); products.map(...)
//        const products = await getList("/products?limit=50");
export const safeArray = (val, key) => {
  if (Array.isArray(val)) return val;
  if (val && typeof val === "object" && key && Array.isArray(val[key])) return val[key];
  return [];
};

export const getList = async (path, options = {}) => {
  try {
    const r = await api.get(path, options);
    return safeArray(r.data);
  } catch {
    return [];
  }
};

export const formatDetail = (detail) => {
  if (detail == null) return "Something went wrong.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .join(" ");
  if (detail?.msg) return detail.msg;
  return String(detail);
};

export const formatUSD = (n) =>
  `$${(Number(n) || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

export const formatSSP = (usd, rate) => {
  const ssp = (Number(usd) || 0) * (Number(rate) || 600);
  return `SSP ${ssp.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
};

// Returns the primary price string based on currency preference.
export const formatPrice = (usd, rate, currency = "SSP") =>
  currency === "USD" ? formatUSD(usd) : formatSSP(usd, rate);

// Returns the secondary (smaller) price string — the OPPOSITE of primary.
export const formatPriceAlt = (usd, rate, currency = "SSP") =>
  currency === "USD" ? formatSSP(usd, rate) : formatUSD(usd);
