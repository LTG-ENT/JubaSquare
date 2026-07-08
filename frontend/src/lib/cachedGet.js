import api from "@/lib/api";

/**
 * Simple localStorage-backed cache for GET endpoints that rarely change
 * (like /categories/tree). Falls back to a live fetch on cache miss or
 * TTL expiry, and swallows Storage errors silently (Safari private mode,
 * quota exceeded, etc.).
 *
 * Usage:
 *   const cats = await cachedGet("/categories/tree?group=retail");
 *
 * Iter 31 — Wave 3 perf.
 */
const DEFAULT_TTL_MS = 5 * 60 * 1000; // 5 minutes

function readCache(key) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const { at, data } = JSON.parse(raw);
    if (!at || !data) return null;
    if (Date.now() - at > DEFAULT_TTL_MS) return null;
    return data;
  } catch {
    return null;
  }
}

function writeCache(key, data) {
  try {
    window.localStorage.setItem(key, JSON.stringify({ at: Date.now(), data }));
  } catch {
    /* ignore */
  }
}

export async function cachedGet(path, { ttlMs = DEFAULT_TTL_MS } = {}) {
  const key = `jubasq:cache:${path}`;
  const cached = readCache(key);
  if (cached) return cached;
  const { data } = await api.get(path);
  writeCache(key, data);
  return data;
}

export function bustCache(prefix = "jubasq:cache:") {
  try {
    Object.keys(window.localStorage)
      .filter((k) => k.startsWith(prefix))
      .forEach((k) => window.localStorage.removeItem(k));
  } catch {
    /* ignore */
  }
}
