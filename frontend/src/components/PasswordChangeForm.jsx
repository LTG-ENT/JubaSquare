import { useState } from "react";
import { useTranslation } from "react-i18next";
import { KeyRound, Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import api, { formatDetail } from "@/lib/api";
import PasswordInput from "@/components/PasswordInput";

/**
 * "Update password" form.
 *  - Current password
 *  - New password
 *  - Confirm new password
 *  - Each field has a per-field show/hide toggle (via PasswordInput)
 *  - Live validation: length + match
 * Calls POST /api/auth/change-password with {current_password, new_password}.
 */
export default function PasswordChangeForm({ compact = false, cardClass = "" }) {
  const { t } = useTranslation();
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [busy, setBusy] = useState(false);

  const meetsLength = newPw.length >= 6;
  const matches = !!newPw && newPw === confirmPw;
  const canSubmit = !!currentPw && meetsLength && matches && !busy;

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
      <PasswordInput
        label="Current password"
        value={currentPw}
        onChange={setCurrentPw}
        testId="current-pw"
        autoComplete="current-password"
      />
      <PasswordInput
        label="New password"
        value={newPw}
        onChange={setNewPw}
        testId="new-pw"
        autoComplete="new-password"
        minLength={6}
      />
      <PasswordInput
        label="Confirm new password"
        value={confirmPw}
        onChange={setConfirmPw}
        testId="confirm-pw"
        autoComplete="new-password"
        minLength={6}
      />

      <ul className="text-[11px] space-y-1" data-testid="password-hints">
        <li className={`flex items-center gap-1.5 ${meetsLength ? "text-green-700" : "text-[var(--js-text-secondary)]"}`}>
          <CheckCircle2 className={`w-3.5 h-3.5 ${meetsLength ? "opacity-100" : "opacity-30"}`} /> At least 6 characters
        </li>
        <li className={`flex items-center gap-1.5 ${matches ? "text-green-700" : "text-[var(--js-text-secondary)]"}`}>
          <CheckCircle2 className={`w-3.5 h-3.5 ${matches ? "opacity-100" : "opacity-30"}`} /> Both new passwords match
        </li>
      </ul>

      <button
        type="submit"
        disabled={!canSubmit}
        data-testid="change-pw-btn"
        className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] disabled:cursor-not-allowed text-white text-sm font-semibold px-5 py-2.5 rounded-full"
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
        {busy ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}
