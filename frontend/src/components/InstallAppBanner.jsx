import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";
import { canInstall, onInstallAvailable, promptInstall, isStandalone } from "@/lib/pwa";

/**
 * Floating "Install app" banner. Auto-hides:
 *  - when the browser hasn't dispatched beforeinstallprompt (unsupported / already installed / iOS Safari)
 *  - when the user dismisses (persisted in localStorage for 14 days)
 *  - when the PWA is already running standalone
 */
const DISMISS_KEY = "js_install_dismissed_until";

function isDismissed() {
  try {
    const raw = localStorage.getItem(DISMISS_KEY);
    if (!raw) return false;
    return Date.now() < Number(raw);
  } catch { return false; }
}

function dismissFor(days = 14) {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now() + days * 86400 * 1000));
  } catch {/* */}
}

export default function InstallAppBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isStandalone()) return; // already installed
    if (isDismissed()) return;
    const off = onInstallAvailable((available) => setVisible(!!available && !isDismissed()));
    return () => { try { off && off(); } catch {/* */} };
  }, []);

  if (!visible || !canInstall()) return null;

  const onInstall = async () => {
    const res = await promptInstall();
    if (res?.outcome !== "accepted") dismissFor(3);
    setVisible(false);
  };

  const onDismiss = () => {
    dismissFor(14);
    setVisible(false);
  };

  return (
    <div
      className="fixed z-50 bottom-4 left-1/2 -translate-x-1/2 w-[min(96vw,420px)] bg-[#0E1A2B] text-white rounded-2xl shadow-2xl border border-white/10 p-4 flex items-center gap-3"
      role="dialog"
      aria-label="Install JubaSquare"
      data-testid="pwa-install-banner"
    >
      <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
        <img src="/icons/icon-192.png" alt="" className="w-8 h-8 rounded-lg" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-display font-bold text-sm">Install JubaSquare</p>
        <p className="text-xs text-white/70 leading-tight mt-0.5">
          Add to your home screen for one-tap access, faster loads, and push notifications.
        </p>
      </div>
      <button
        onClick={onInstall}
        className="inline-flex items-center gap-1 bg-[#C84B31] hover:bg-[#A83A23] text-white text-xs font-semibold px-3 py-1.5 rounded-full shrink-0"
        data-testid="pwa-install-button"
      >
        <Download className="w-3.5 h-3.5" /> Install
      </button>
      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        className="p-1 rounded-full hover:bg-white/10 shrink-0"
        data-testid="pwa-install-dismiss"
      >
        <X className="w-4 h-4 text-white/70" />
      </button>
    </div>
  );
}
