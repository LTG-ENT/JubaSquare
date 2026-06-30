import { useEffect, useState, useCallback } from "react";
import api, { formatDetail } from "@/lib/api";
import { toast } from "sonner";
import { Key, RefreshCw, Copy, AlertTriangle, ShieldCheck, ShieldAlert, Eye, EyeOff, X } from "lucide-react";

/**
 * Admin Dashboard → Odoo Integration Settings → Service Token Manager
 *
 * Security model:
 * - Only admin JWT can access these endpoints (verified server-side).
 * - Raw token returned only once on generate/rotate; we surface it in a modal
 *   that the admin must explicitly dismiss after copying.
 * - Stored React state holding the raw token is wiped when the modal closes.
 * - Status endpoint never returns the raw token — only masked preview + dates.
 */
export default function AdminOdooTokenManager() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [revealedToken, setRevealedToken] = useState(null);
  const [revealedKind, setRevealedKind] = useState(null); // "generated" | "rotated"
  const [showFullToken, setShowFullToken] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get("/admin/odoo/service-token");
      setStatus(data);
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to load token status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleGenerate = async () => {
    if (acting) return;
    setActing(true);
    try {
      const { data } = await api.post("/admin/odoo/service-token/generate");
      setRevealedToken(data.raw_token);
      setRevealedKind("generated");
      setShowFullToken(false);
      await loadStatus();
    } catch (err) {
      const code = err.response?.status;
      if (code === 409) {
        toast.error("A token already exists. Click Rotate to replace it.");
      } else {
        toast.error(formatDetail(err.response?.data?.detail) || "Failed to generate token");
      }
    } finally {
      setActing(false);
    }
  };

  const handleRotate = async () => {
    if (acting) return;
    if (!window.confirm(
      "Rotate the Odoo service token now?\n\n" +
      "The previous token will stop working IMMEDIATELY. " +
      "Make sure you can update the Odoo connector configuration with the new token afterwards."
    )) return;
    setActing(true);
    try {
      const { data } = await api.post("/admin/odoo/service-token/rotate");
      setRevealedToken(data.raw_token);
      setRevealedKind("rotated");
      setShowFullToken(false);
      await loadStatus();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to rotate token");
    } finally {
      setActing(false);
    }
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text).then(
      () => toast.success("Token copied to clipboard"),
      () => toast.error("Copy failed — please select and copy manually")
    );
  };

  const handleDismissReveal = () => {
    setRevealedToken(null);
    setRevealedKind(null);
    setShowFullToken(false);
  };

  const fmt = (iso) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  const isActive = status?.status === "active";
  const isDbBacked = status?.source === "database";
  const isEnvFallback = status?.source === "env";

  return (
    <div data-testid="odoo-token-manager" className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#C84B31]/10 text-[#C84B31] flex items-center justify-center flex-shrink-0">
          <Key className="w-5 h-5" />
        </div>
        <div>
          <h2 className="font-display font-bold text-xl text-[var(--js-text)]">Odoo Service Token</h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1">
            Used by the Odoo 18 connector to authenticate against JubaSquare. Keep it secret.
            If exposed, rotate it immediately.
          </p>
        </div>
      </div>

      {/* Status card */}
      <div className="bg-[var(--js-card)] border border-[var(--js-border)] rounded-2xl p-5">
        {loading ? (
          <div className="text-sm text-[var(--js-text-secondary)]">Loading token status…</div>
        ) : (
          <>
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-2">
                {isActive ? (
                  <ShieldCheck className="w-5 h-5 text-emerald-600" />
                ) : (
                  <ShieldAlert className="w-5 h-5 text-amber-600" />
                )}
                <span
                  data-testid="token-status-label"
                  className={`text-sm font-bold ${isActive ? "text-emerald-700" : "text-amber-700"}`}
                >
                  {isActive ? "Active" : "Not Generated"}
                </span>
                {isEnvFallback && (
                  <span className="text-[10px] uppercase tracking-wide bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full font-bold">
                    env fallback
                  </span>
                )}
                {isDbBacked && (
                  <span className="text-[10px] uppercase tracking-wide bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold">
                    database
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 font-mono text-sm" data-testid="token-masked-preview">
                {status?.masked_preview || "—"}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4 text-sm">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--js-text-secondary)] font-bold">Created</p>
                <p data-testid="token-created-at" className="text-[var(--js-text)] mt-0.5">{fmt(status?.created_at)}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--js-text-secondary)] font-bold">Last Rotated</p>
                <p data-testid="token-rotated-at" className="text-[var(--js-text)] mt-0.5">{fmt(status?.last_rotated_at)}</p>
              </div>
              {status?.created_by && (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--js-text-secondary)] font-bold">Created By</p>
                  <p className="text-[var(--js-text)] mt-0.5">{status.created_by}</p>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-2 mt-5">
              {!isDbBacked && (
                <button
                  data-testid="generate-token-btn"
                  onClick={handleGenerate}
                  disabled={acting}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#C84B31] text-white font-semibold text-sm hover:bg-[#a83d27] disabled:opacity-50 transition"
                >
                  <Key className="w-4 h-4" />
                  {acting ? "Generating…" : "Generate New Service Token"}
                </button>
              )}
              {isDbBacked && (
                <button
                  data-testid="rotate-token-btn"
                  onClick={handleRotate}
                  disabled={acting}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-600 text-white font-semibold text-sm hover:bg-amber-700 disabled:opacity-50 transition"
                >
                  <RefreshCw className={`w-4 h-4 ${acting ? "animate-spin" : ""}`} />
                  {acting ? "Rotating…" : "Rotate Token"}
                </button>
              )}
            </div>

            {isEnvFallback && (
              <div className="mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800">
                <strong>Heads up:</strong> JubaSquare is currently using the env-file token as a fallback.
                Click <em>Generate New Service Token</em> to take ownership of token rotation from the admin UI.
                Once generated, the env token will stop being accepted.
              </div>
            )}
          </>
        )}
      </div>

      {/* Security note */}
      <div className="bg-[var(--js-card)] border border-[var(--js-border)] rounded-2xl p-4 text-xs text-[var(--js-text-secondary)] flex gap-3">
        <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
        <p>
          This token is used by Odoo to connect to JubaSquare. Keep it secret. If exposed, rotate it immediately.
          The full token is only displayed once at generation/rotation — JubaSquare stores only a SHA-256 hash.
        </p>
      </div>

      {/* Reveal modal */}
      {revealedToken && (
        <div
          data-testid="reveal-token-modal"
          className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
        >
          <div className="bg-white dark:bg-zinc-900 rounded-2xl max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center">
                  <Key className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-[var(--js-text)]">
                    {revealedKind === "rotated" ? "Token Rotated" : "Token Generated"}
                  </h3>
                  <p className="text-xs text-[var(--js-text-secondary)] mt-0.5">
                    Copy this token now. It will not be shown again.
                  </p>
                </div>
              </div>
              <button
                onClick={handleDismissReveal}
                className="text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-5 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-xl p-3 break-all font-mono text-sm">
              <span data-testid="reveal-token-value">
                {showFullToken ? revealedToken : "•".repeat(Math.max(0, revealedToken.length - 4)) + revealedToken.slice(-4)}
              </span>
            </div>

            <div className="flex flex-wrap gap-2 mt-4">
              <button
                data-testid="copy-token-btn"
                onClick={() => handleCopy(revealedToken)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#C84B31] text-white font-semibold text-sm hover:bg-[#a83d27] transition"
              >
                <Copy className="w-4 h-4" /> Copy Token
              </button>
              <button
                data-testid="toggle-reveal-btn"
                onClick={() => setShowFullToken((v) => !v)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-zinc-200 dark:bg-zinc-700 text-[var(--js-text)] font-semibold text-sm hover:bg-zinc-300 transition"
              >
                {showFullToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                {showFullToken ? "Hide" : "Reveal"}
              </button>
              <button
                data-testid="dismiss-reveal-btn"
                onClick={handleDismissReveal}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-[var(--js-border)] text-[var(--js-text)] font-semibold text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
              >
                I&apos;ve copied it — close
              </button>
            </div>

            <div className="mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800">
              <strong>Next step:</strong> Open your Odoo instance →
              JubaSquare Connector → Configuration → <em>API Token</em>, paste the value above, and save.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
