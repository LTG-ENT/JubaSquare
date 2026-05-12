import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { formatDetail } from "@/lib/api";
import { Logo } from "@/components/Logo";
import { User, Store, Loader2, CheckCircle2, Mail } from "lucide-react";
import { toast } from "sonner";

export default function Signup() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("customer");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/signup", {
        email: email.trim().toLowerCase(),
        password,
        name: name.trim(),
        phone: phone.trim(),
        role,
      });
      setDone(true);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail || e.message));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 grain-bg">
        <div className="w-full max-w-md text-center fade-up">
          <div className="w-20 h-20 rounded-full bg-[#2D6A4F]/10 border-4 border-[#2D6A4F]/20 flex items-center justify-center mx-auto mb-6">
            <Mail className="w-10 h-10 text-[#2D6A4F]" />
          </div>
          <h1 className="font-display font-bold text-2xl text-[var(--js-text)] mb-3">Check your inbox</h1>
          <p className="text-sm text-[var(--js-text-secondary)] mb-6">
            We sent a verification link to <strong>{email}</strong>. Click it to activate your account, then sign in.
          </p>
          <p className="text-xs text-[var(--js-text-secondary)] mb-6">
            Didn't get the email? Check your spam folder, or{" "}
            <button
              onClick={async () => {
                try {
                  await api.post("/auth/resend-verification", { email });
                  toast.success("Verification email resent");
                } catch (e) {
                  toast.error(formatDetail(e.response?.data?.detail || e.message));
                }
              }}
              className="text-[#C84B31] font-semibold hover:underline"
            >
              resend it
            </button>.
          </p>
          <button
            onClick={() => navigate("/login")}
            className="bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-6 py-3 rounded-xl text-sm"
          >
            Go to sign in
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 grain-bg">
      <div className="w-full max-w-md fade-up">
        <div className="flex flex-col items-center mb-8">
          <Link to="/"><Logo size={160} className="drop-shadow-2xl sm:w-48 sm:h-48 md:w-56 md:h-56 lg:w-64 lg:h-64 xl:w-72 xl:h-72" /></Link>
          <h1 className="font-display font-bold text-2xl text-[var(--js-text)] mt-2">Create your account</h1>
          <p className="text-sm text-[var(--js-text-secondary)] mt-2">Join JubaSquare — it's free.</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white border border-[var(--js-border)] rounded-3xl p-6 sm:p-8 shadow-[0_8px_32px_rgba(0,0,0,0.06)] space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setRole("customer")}
              data-testid="role-customer"
              className={`flex flex-col items-center gap-1.5 py-3 px-3 rounded-xl border-2 transition ${role === "customer" ? "border-[#C84B31] bg-[#C84B31]/5" : "border-[var(--js-border)] hover:border-[#1A1A1A]"}`}
            >
              <User className="w-5 h-5" />
              <span className="text-xs font-semibold">Shop as Customer</span>
            </button>
            <button
              type="button"
              onClick={() => setRole("seller")}
              data-testid="role-seller"
              className={`flex flex-col items-center gap-1.5 py-3 px-3 rounded-xl border-2 transition ${role === "seller" ? "border-[#C84B31] bg-[#C84B31]/5" : "border-[var(--js-border)] hover:border-[#1A1A1A]"}`}
            >
              <Store className="w-5 h-5" />
              <span className="text-xs font-semibold">Sell on JubaSquare</span>
            </button>
          </div>

          <label className="block">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">Full name</span>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required data-testid="signup-name"
                   className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]" />
          </label>

          <label className="block">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">Email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="signup-email"
                   className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]" />
          </label>

          <label className="block">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">Phone (optional)</span>
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+211 9XX XXX XXX" data-testid="signup-phone"
                   className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]" />
          </label>

          <label className="block">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">Password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} data-testid="signup-password"
                   className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]" />
            <span className="text-[11px] text-[var(--js-text-secondary)] mt-1 inline-block">At least 6 characters.</span>
          </label>

          <button type="submit" disabled={busy} data-testid="signup-submit"
            className="w-full bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition disabled:opacity-60">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            Create account
          </button>

          <p className="text-center text-xs text-[var(--js-text-secondary)]">
            By signing up you agree to our <Link to="/terms" className="underline">Terms</Link> and <Link to="/privacy" className="underline">Privacy Policy</Link>.
          </p>
          <p className="text-center text-sm text-[var(--js-text-secondary)]">
            Already have an account? <Link to="/login" className="text-[#C84B31] font-semibold hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
