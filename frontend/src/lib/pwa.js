/**
 * PWA + Web Push helper.
 *
 * Public API:
 *   registerServiceWorker()         → register /sw.js (call once at app boot)
 *   subscribeToPush()               → request permission + subscribe; POST to /api/push/subscribe
 *   unsubscribeFromPush()           → unsubscribe locally and POST to /api/push/unsubscribe
 *   getSubscription()               → current PushSubscription | null
 *   isPushSupported()               → bool
 *   getPushPermission()             → "granted" | "denied" | "default"
 */

import api from "@/lib/api";

const SW_PATH = "/sw.js";

/** Convert a base64url string to a Uint8Array (needed for applicationServerKey). */
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const out = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) out[i] = rawData.charCodeAt(i);
  return out;
}

export function isPushSupported() {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function getPushPermission() {
  if (typeof Notification === "undefined") return "denied";
  return Notification.permission; // "granted" | "denied" | "default"
}

export async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return null;
  try {
    const reg = await navigator.serviceWorker.register(SW_PATH, { scope: "/" });
    // Auto-update: check for a new SW on visibility (once per session is enough)
    if (reg.update) {
      try { reg.update(); } catch { /* ignore */ }
    }
    return reg;
  } catch (e) {
    console.warn("[pwa] SW register failed:", e);
    return null;
  }
}

export async function getSubscription() {
  if (!isPushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  if (!reg) return null;
  return reg.pushManager.getSubscription();
}

export async function subscribeToPush() {
  if (!isPushSupported()) throw new Error("Push is not supported on this device");

  // Ask permission
  let perm = Notification.permission;
  if (perm === "default") {
    perm = await Notification.requestPermission();
  }
  if (perm !== "granted") {
    throw new Error("Notifications permission was denied.");
  }

  // Register SW if not already
  let reg = await navigator.serviceWorker.getRegistration();
  if (!reg) reg = await registerServiceWorker();
  if (!reg) throw new Error("Could not register the service worker.");
  await navigator.serviceWorker.ready;

  // Fetch VAPID public key from backend
  const { data } = await api.get("/push/public-key");
  const publicKey = data?.public_key;
  if (!publicKey) throw new Error("Server has no VAPID key configured.");

  // Subscribe (or reuse existing)
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
  }

  // Persist server-side
  await api.post("/push/subscribe", { subscription: sub.toJSON() });
  return sub;
}

export async function unsubscribeFromPush() {
  const sub = await getSubscription();
  if (!sub) return true;
  const endpoint = sub.endpoint;
  try { await sub.unsubscribe(); } catch { /* ignore */ }
  try { await api.post("/push/unsubscribe", { endpoint }); } catch { /* ignore */ }
  return true;
}

/**
 * beforeinstallprompt helper — captures the event so we can show a custom
 * "Install app" button in the UI. Returns { prompt(): Promise<{outcome:"accepted"|"dismissed"}> } or null.
 */
let _deferredPrompt = null;
const _installListeners = new Set();

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    _deferredPrompt = e;
    _installListeners.forEach((cb) => { try { cb(true); } catch {/* */} });
  });
  window.addEventListener("appinstalled", () => {
    _deferredPrompt = null;
    _installListeners.forEach((cb) => { try { cb(false); } catch {/* */} });
  });
}

export function canInstall() {
  return !!_deferredPrompt;
}

export function onInstallAvailable(cb) {
  _installListeners.add(cb);
  // Fire immediately with current state
  try { cb(!!_deferredPrompt); } catch {/* */}
  return () => _installListeners.delete(cb);
}

export async function promptInstall() {
  if (!_deferredPrompt) return { outcome: "unavailable" };
  const evt = _deferredPrompt;
  _deferredPrompt = null;
  evt.prompt();
  try {
    const choice = await evt.userChoice;
    return choice; // { outcome, platform }
  } catch (e) {
    return { outcome: "dismissed" };
  }
}

/** True when app is already installed / running as standalone PWA */
export function isStandalone() {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}
