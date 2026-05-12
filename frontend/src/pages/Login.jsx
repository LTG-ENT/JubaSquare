import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Loader2, LogIn as LogInIcon } from "lucide-react";
import { toast } from "sonner";
import { Logo } from "@/components/Logo";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Enter your email and password");
      return;
    }
    setBusy(true);
    const res = await login(email.trim().toLowerCase(), password);
    setBusy(false);
    if (!res.ok) {
      toast.error(res.error);
      return;
    }
    toast.success(`Welcome back, ${res.user.name}!`);
    if (res.user.role === "admin") navigate("/admin");
    else if (res.user.role === "seller") navigate("/seller");
    else navigate("/");
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 grain-bg">
      <div className="w-full max-w-md fade-up">
        <div className="flex flex-col items-center mb-10">
          <Link to="/"><Logo size={80} className="shadow-xl sm:w-24 sm:h-24 md:w-28 md:h-28 lg:w-32 lg:h-32" /></Link>
          <h1 className="font-display font-bold text-3xl text-[var(--js-text)] mt-5">JubaSquare</h1>
          <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--js-text-secondary)] font-bold mt-1">by L.T.G Enterprise</p>
          <p className="text-sm text-[var(--js-text-secondary)] mt-4 text-center">Sign in to your JubaSquare account</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white border border-[var(--js-border)] rounded-3xl p-6 sm:p-8 shadow-[0_8px_32px_rgba(0,0,0,0.06)]">
          <label className="block mb-4">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              data-testid="login-email"
              autoComplete="email"
              required
              className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#1A1A1A] transition"
            />
          </label>
          <label className="block mb-2">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              data-testid="login-password"
              autoComplete="current-password"
              required
              className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#1A1A1A] transition"
            />
          </label>
          <div className="flex justify-end mb-6">
            <Link to="/forgot-password" className="text-xs text-[#C84B31] hover:underline font-semibold" data-testid="forgot-password-link">
              Forgot password?
            </Link>
          </div>
          <button
            type="submit"
            disabled={busy}
            data-testid="login-submit"
            className="w-full bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition disabled:opacity-60"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogInIcon className="w-4 h-4" />}
            Sign in
          </button>
          <p className="text-center text-sm text-[var(--js-text-secondary)] mt-6">
            New to JubaSquare?{" "}
            <Link to="/signup" className="text-[#C84B31] font-semibold hover:underline" data-testid="signup-link">Create an account</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
