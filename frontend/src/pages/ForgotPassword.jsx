import { useState } from "react";
import { Link } from "react-router-dom";
import api, { formatDetail } from "@/lib/api";
import { Logo } from "@/components/Logo";
import { Mail, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email: email.trim().toLowerCase() });
      setSent(true);
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
          <Link to="/"><Logo size={104} className="shadow-xl" /></Link>
          <h1 className="font-display font-bold text-2xl text-[var(--js-text)] mt-4">Forgot password?</h1>
          <p className="text-sm text-[var(--js-text-secondary)] mt-2 text-center">
            Enter your email and we'll send you a reset link.
          </p>
        </div>

        {sent ? (
          <div className="bg-white border border-[var(--js-border)] rounded-3xl p-8 text-center" data-testid="forgot-sent">
            <div className="w-16 h-16 rounded-full bg-[#2D6A4F]/10 border-4 border-[#2D6A4F]/20 flex items-center justify-center mx-auto mb-4">
              <Mail className="w-8 h-8 text-[#2D6A4F]" />
            </div>
            <p className="text-sm text-[var(--js-text)] font-semibold mb-2">Check your email</p>
            <p className="text-xs text-[var(--js-text-secondary)]">
              If an account exists for <strong>{email}</strong>, we sent a password reset link. The link expires in 1 hour.
            </p>
            <Link to="/login" className="inline-block mt-6 text-[#C84B31] hover:underline text-sm font-semibold">
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-white border border-[var(--js-border)] rounded-3xl p-6 sm:p-8">
            <label className="block mb-5">
              <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="forgot-email"
                className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#1A1A1A]"
              />
            </label>
            <button type="submit" disabled={busy} data-testid="forgot-submit"
              className="w-full bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
              Send reset link
            </button>
            <p className="text-center text-sm text-[var(--js-text-secondary)] mt-5">
              Remembered it? <Link to="/login" className="text-[#C84B31] font-semibold hover:underline">Back to sign in</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
