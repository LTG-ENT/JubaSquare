import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Eye, EyeOff, KeyRound, Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import api, { formatDetail } from "@/lib/api";

/**
 * Reusable "Update password" form with:
 *   - Current password
 *   - New password
 *   - Confirm new password
 *   - Individual show/hide toggle per field
 *   - Client-side validation (match + minimum length)
 * Calls POST /api/auth/change-password with {current_password, new_password}.
 */
export default function PasswordChangeForm({ compact = false, cardClass = "" }) {
  const { t } = useTranslation();
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [show, setShow] = useState({ current: false, next: false, confirm: false });
  const [busy, setBusy] = useState(false);

  const meetsLength = newPw.length >= 6;
  const matches = newPw && newPw === confirmPw;

  const submit = async (e) => {
    e.preventDefault();
    if (!currentPw) return toast.error("Please enter your current password");
    if (!meetsLength) return toast.error("New password must be at least 6 characters");
    if (!matches) return toast.error("New passwords do not match");

    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: currentPw, new_password: newPw });
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
      toast.success("Password updated");
    } catch (err) {
      toast.error(formatDetail(err?.response?.data?.detail) || "Could not update password");
    } finally {
      setBusy(false);
    }
  };

  const Field = ({ label, value, onChange, testId, revealKey, autoComplete }) => {
    const isShown = show[revealKey];
    return (
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider text-[var(--js-text-secondary)] block mb-1.5">
          {label}
        </label>
        <div className="relative">
          <input
            type={isShown ? "text" : "password"}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            data-testid={testId}
            autoComplete={autoComplete}
            className="w-full pr-10 px-3 py-2.5 rounded-xl border border-[var(--js-border)] bg-[var(--js-bg)] text-sm text-[var(--js-text)] focus:outline-none focus:border-[#1A1A1A] transition"
          />
          <button
            type="button"
            onClick={() => setShow((s) => ({ ...s, [revealKey]: !s[revealKey] }))}
            aria-label={isShown ? "Hide password" : "Show password"}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full text-[var(--js-text-secondary)] hover:bg-[var(--js-subtle)] hover:text-[var(--js-text)] transition"
            data-testid={`${testId}-toggle`}
            tabIndex={-1}
          >
            {isShown ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </div>
    );
  };

  const wrap = compact
    ? `space-y-3 ${cardClass}`
    : `bg-white dark:bg-[var(--js-panel)] border border-[var(--js-border)] rounded-3xl p-5 sm:p-6 space-y-4 ${cardClass}`;

  return (
    <form onSubmit={submit} className={wrap} data-testid="password-change-form">
      {!compact && (
        <h2 className="font-display font-semibold text-lg text-[var(--js-text)] flex items-center gap-2">
          <KeyRound className="w-5 h-5 text-[#C84B31]" /> Update password
        </h2>
      )}
      <Field label="Current password" value={currentPw} onChange={setCurrentPw} testId="current-pw" revealKey="current" autoComplete="current-password" />
      <Field label="New password" value={newPw} onChange={setNewPw} testId="new-pw" revealKey="next" autoComplete="new-password" />
      <Field label="Confirm new password" value={confirmPw} onChange={setConfirmPw} testId="confirm-pw" revealKey="confirm" autoComplete="new-password" />

      {/* Live hints */}
      <ul className="text-[11px] space-y-1">
        <li className={`flex items-center gap-1.5 ${meetsLength ? "text-green-700" : "text-[var(--js-text-secondary)]"}`}>
          <CheckCircle2 className={`w-3.5 h-3.5 ${meetsLength ? "opacity-100" : "opacity-30"}`} /> At least 6 characters
        </li>
        <li className={`flex items-center gap-1.5 ${matches ? "text-green-700" : "text-[var(--js-text-secondary)]"}`}>
          <CheckCircle2 className={`w-3.5 h-3.5 ${matches ? "opacity-100" : "opacity-30"}`} /> Both new passwords match
        </li>
      </ul>

      <button
        type="submit"
        disabled={busy || !currentPw || !meetsLength || !matches}
        data-testid="change-pw-btn"
        className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] disabled:cursor-not-allowed text-white text-sm font-semibold px-5 py-2.5 rounded-full"
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
        {busy ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}
