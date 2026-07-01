import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Loader2, LogIn as LogInIcon } from "lucide-react";
import PasswordInput from "@/components/PasswordInput";
import { toast } from "sonner";
import { Logo } from "@/components/Logo";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!identifier || !password) {
      toast.error(t("toastEnterEmailPassword"));
      return;
    }
    setBusy(true);
    // Only lowercase full string when it looks like an email.
    // Usernames are also compared lowercased server-side but we keep the raw
    // value so display/error messages match user input.
    const value = identifier.trim();
    const normalized = value.includes("@") ? value.toLowerCase() : value.toLowerCase();
    const res = await login(normalized, password);
    setBusy(false);
    if (!res.ok) {
      toast.error(res.error);
      return;
    }
    toast.success(`${t("toastWelcomeBack")}, ${res.user.name}!`);
    if (res.user.role === "admin") navigate("/admin");
    else if (res.user.role === "seller") navigate("/seller");
    else navigate("/");
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 grain-bg">
      <button
        type="button"
        onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/"))}
        data-testid="login-back-button"
        className="fixed top-5 left-5 z-50 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white border border-[var(--js-border)] text-[var(--js-text)] text-sm font-semibold shadow-sm hover:bg-[var(--js-subtle)] transition"
      >
        <ArrowLeft className="w-4 h-4" />
        {t("back")}
      </button>
      <div className="w-full max-w-md fade-up">
        <div className="flex flex-col items-center mb-10">
          <Link to="/"><Logo size={96} className="drop-shadow-2xl sm:w-28 sm:h-28 md:w-32 md:h-32 lg:w-36 lg:h-36 xl:w-40 xl:h-40" /></Link>
          <h1 className="font-display font-bold text-3xl text-[var(--js-text)] mt-2">JubaSquare</h1>
          <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--js-text-secondary)] font-bold mt-1">by L.T.G Enterprise</p>
          <p className="text-sm text-[var(--js-text-secondary)] mt-4 text-center">{t("signInSubtitle")}</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white border border-[var(--js-border)] rounded-3xl p-6 sm:p-8 shadow-[0_8px_32px_rgba(0,0,0,0.06)]">
          <label className="block mb-4">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">{t("email")} / Username</span>
            <input
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="you@example.com or admin"
              data-testid="login-email"
              autoComplete="username"
              required
              className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#1A1A1A] transition"
            />
          </label>
          <div className="mb-2">
            <PasswordInput
              label={t("password")}
              value={password}
              onChange={setPassword}
              placeholder="••••••••"
              testId="login-password"
              autoComplete="current-password"
              required
              inputClassName="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-3 pr-11 text-sm focus:outline-none focus:border-[#1A1A1A] transition"
              labelClassName="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider"
            />
          </div>
          <div className="flex justify-end mb-6">
            <Link to="/forgot-password" className="text-xs text-[#C84B31] hover:underline font-semibold" data-testid="forgot-password-link">
              {t("forgotPassword")}
            </Link>
          </div>
          <button
            type="submit"
            disabled={busy}
            data-testid="login-submit"
            className="w-full bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition disabled:opacity-60"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogInIcon className="w-4 h-4" />}
            {t("signIn")}
          </button>
          <p className="text-center text-sm text-[var(--js-text-secondary)] mt-6">
            {t("newToJubaSquare")}{" "}
            <Link to="/signup" className="text-[#C84B31] font-semibold hover:underline" data-testid="signup-link">{t("createAnAccount")}</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
