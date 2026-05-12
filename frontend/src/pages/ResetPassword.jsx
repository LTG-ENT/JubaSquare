import { useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import api, { formatDetail } from "@/lib/api";
import { Logo } from "@/components/Logo";
import { KeyRound, Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password.length < 6) { toast.error("Password must be at least 6 characters"); return; }
    if (password !== confirm) { toast.error("Passwords don't match"); return; }
    if (!token) { toast.error("Missing reset token"); return; }
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: password });
      setDone(true);
      setTimeout(() => navigate("/login"), 2500);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail || e.message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 grain-bg">
      <div className="w-full max-w-md fade-up">
        <div className="flex flex-col items-center mb-8">
          <Link to="/"><Logo size={72} className="shadow-xl sm:w-24 sm:h-24 md:w-28 md:h-28 lg:w-32 lg:h-32" /></Link>
          <h1 className="font-display font-bold text-2xl text-[var(--js-text)] mt-4">Set a new password</h1>
        </div>

        {done ? (
          <div className="bg-white border border-[var(--js-border)] rounded-3xl p-8 text-center" data-testid="reset-done">
            <CheckCircle2 className="w-14 h-14 text-[#2D6A4F] mx-auto mb-4" />
            <p className="text-sm font-semibold">Password updated!</p>
            <p className="text-xs text-[var(--js-text-secondary)] mt-2">Redirecting to sign in…</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-white border border-[var(--js-border)] rounded-3xl p-6 sm:p-8 space-y-4">
            <label className="block">
              <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">New password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required data-testid="reset-password"
                className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#1A1A1A]" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">Confirm new password</span>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} minLength={6} required data-testid="reset-confirm"
                className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#1A1A1A]" />
            </label>
            <button type="submit" disabled={busy} data-testid="reset-submit"
              className="w-full bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
              Update password
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
