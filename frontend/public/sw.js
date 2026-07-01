/*
 * JubaSquare Service Worker
 * - Basic offline shell (network-first for API + navigation, cache-first for assets)
 * - Web Push handler
 * - Notification click handler
 *
 * Version bumped to invalidate old caches on deploys.
 */

const SW_VERSION = "js-sw-v1";
const RUNTIME_CACHE = `js-runtime-${SW_VERSION}`;
const STATIC_CACHE = `js-static-${SW_VERSION}`;

const STATIC_ASSETS = [
  "/",
  "/manifest.json",
  "/favicon.ico",
  "/favicon-16.png",
  "/favicon-32.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/apple-touch-icon.png",
  "/icons/apple-touch-icon.png",
];

// ---- Install ----
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) =>
      cache.addAll(STATIC_ASSETS).catch(() => { /* best-effort */ })
    )
  );
  self.skipWaiting();
});

// ---- Activate: clean up old caches ----
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== RUNTIME_CACHE && k !== STATIC_CACHE)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ---- Fetch: network-first for API + navigations, cache-first for static assets ----
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Skip cross-origin (e.g., unsplash, cdn) - let browser handle
  if (url.origin !== location.origin) return;

  // Never cache API responses (they change often)
  if (url.pathname.startsWith("/api/")) return;

  // HTML navigations: network-first, fallback to cache
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(RUNTIME_CACHE).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match("/")))
    );
    return;
  }

  // Static assets: cache-first
  if (
    url.pathname.startsWith("/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname.endsWith(".png") ||
    url.pathname.endsWith(".jpg") ||
    url.pathname.endsWith(".jpeg") ||
    url.pathname.endsWith(".webp") ||
    url.pathname.endsWith(".svg") ||
    url.pathname.endsWith(".ico") ||
    url.pathname.endsWith(".woff2") ||
    url.pathname.endsWith(".woff") ||
    url.pathname.endsWith(".css") ||
    url.pathname.endsWith(".js")
  ) {
    event.respondWith(
      caches.match(req).then(
        (cached) =>
          cached ||
          fetch(req).then((res) => {
            const copy = res.clone();
            caches.open(RUNTIME_CACHE).then((c) => c.put(req, copy));
            return res;
          }).catch(() => cached)
      )
    );
  }
});

// ---- Web Push ----
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "JubaSquare", body: (event.data && event.data.text()) || "" };
  }
  const title = data.title || "JubaSquare";
  const options = {
    body: data.body || "",
    icon: data.icon || "/icons/icon-192.png",
    badge: "/icons/icon-96.png",
    tag: data.tag || undefined,
    data: {
      url: data.url || "/",
      ...(data.data || {}),
    },
    vibrate: [80, 40, 80],
    requireInteraction: !!data.requireInteraction,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// ---- Notification click: focus or open the target URL ----
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      // If any client is already open at the target, focus it
      for (const client of clientList) {
        const url = new URL(client.url);
        if (url.pathname === targetUrl && "focus" in client) return client.focus();
      }
      // Otherwise, if any client is open, navigate it
      if (clientList.length > 0) {
        const client = clientList[0];
        if ("navigate" in client) client.navigate(targetUrl);
        return client.focus();
      }
      // Otherwise, open a new window
      if (self.clients.openWindow) return self.clients.openWindow(targetUrl);
    })
  );
});

// ---- Push subscription change (browser rotated the endpoint) ----
self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(
    self.registration.pushManager
      .subscribe({ userVisibleOnly: true, applicationServerKey: event.oldSubscription && event.oldSubscription.options.applicationServerKey })
      .then((newSub) => {
        // Best-effort: POST the new subscription to the backend if we know the URL.
        // (Endpoint on backend: POST /api/push/subscribe with the subscription body.)
        return fetch("/api/push/subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ subscription: newSub.toJSON() }),
          credentials: "include",
        }).catch(() => {});
      })
  );
});
