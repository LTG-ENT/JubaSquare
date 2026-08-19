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
// Error message extraction
// ---------------------------------------------------------------------------
// FastAPI returns `detail` as either:
//   - a string  (custom HTTPException)
//   - a list of objects (Pydantic 422 ValidationError)
// React/JSX cannot render objects → if we pass the raw detail to toast or
// JSX it triggers "Objects are not valid as a React child" and crashes the
// tree via the ErrorBoundary. This helper always returns a printable string.
export const extractErrorMessage = (err, fallback = "Something went wrong") => {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map((e) => e?.msg || JSON.stringify(e)).join(", ") || fallback;
  }
  if (d && typeof d === "object") return JSON.stringify(d);
  return err?.message || fallback;
};

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

// Quantity-aware unit price for wholesale products. Picks the best pricing
// tier whose min_qty <= qty, else bulk_price_usd (when qty >= min_order_qty),
// else the item's base price_usd. Mirrors backend effective_unit_price_usd.
export const wholesaleUnitPrice = (item, qty) => {
  const base = Number(item?.price_usd) || 0;
  const q = Math.max(1, parseInt(qty, 10) || 1);
  if (!item?.is_wholesale) return base;
  let best = null;
  for (const t of Array.isArray(item.pricing_tiers) ? item.pricing_tiers : []) {
    const mq = parseInt(t?.min_qty, 10);
    const tp = parseFloat(t?.price_usd);
    if (Number.isFinite(mq) && mq >= 1 && Number.isFinite(tp) && tp > 0 && q >= mq) {
      if (!best || mq > best.mq) best = { mq, tp };
    }
  }
  if (best) return best.tp;
  const bulk = parseFloat(item.bulk_price_usd);
  const moq = parseInt(item.min_order_qty, 10) || 1;
  if (Number.isFinite(bulk) && bulk > 0 && q >= moq) return bulk;
  return base;
};
