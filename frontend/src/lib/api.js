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

// ---------------------------------------------------------------------------
// Request dedupe + tiny TTL cache
// ---------------------------------------------------------------------------
// On low-resource hosts a Marketplace render with 200 ProductCards firing 200
// simultaneous /favorites GETs is a self-DoS. `getCached(url, ttlMs)` solves
// this by:
//   • Returning the same in-flight Promise to all callers in the same tick
//     (request dedupe), and
//   • Caching the resolved data for `ttlMs` so subsequent renders skip the
//     network entirely.
// Cache is invalidated by `invalidateCache(prefix)` (called after writes that
// would change the cached data — e.g. toggling a favorite).
const _cache = new Map();   // url → { exp, data }
const _inflight = new Map(); // url → Promise

export const getCached = (path, ttlMs = 30000) => {
  const now = Date.now();
  const hit = _cache.get(path);
  if (hit && hit.exp > now) return Promise.resolve(hit.data);
  const pending = _inflight.get(path);
  if (pending) return pending;
  const p = api
    .get(path)
    .then((r) => {
      _cache.set(path, { exp: Date.now() + ttlMs, data: r.data });
      _inflight.delete(path);
      return r.data;
    })
    .catch((err) => {
      _inflight.delete(path);
      throw err;
    });
  _inflight.set(path, p);
  return p;
};

export const invalidateCache = (prefix = "") => {
  if (!prefix) {
    _cache.clear();
    return;
  }
  for (const key of Array.from(_cache.keys())) {
    if (key.startsWith(prefix)) _cache.delete(key);
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
