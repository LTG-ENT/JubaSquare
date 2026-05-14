import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api, { formatDetail } from "@/lib/api";
import { Logo } from "@/components/Logo";
import { ArrowLeft, User, Store, Loader2, CheckCircle2, Mail } from "lucide-react";
import { toast } from "sonner";

export default function Signup() {
  const navigate = useNavigate();
  const { t } = useTranslation();
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
      toast.error(t("toastPasswordMin6"));
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
          <h1 className="font-display font-bold text-2xl text-[var(--js-text)] mb-3">{t("checkInbox")}</h1>
          <p className="text-sm text-[var(--js-text-secondary)] mb-6">
            {t("weSentVerify")} <strong>{email}</strong>. {t("activateThenSignIn")}
          </p>
          <p className="text-xs text-[var(--js-text-secondary)] mb-6">
            {t("didntGetEmail")}{" "}
            <button
              onClick={async () => {
                try {
                  await api.post("/auth/resend-verification", { email });
                  toast.success(t("verificationEmailResent"));
                } catch (e) {
                  toast.error(formatDetail(e.response?.data?.detail || e.message));
                }
              }}
              className="text-[#C84B31] font-semibold hover:underline"
            >
              {t("resendIt")}
            </button>.
          </p>
          <button
            onClick={() => navigate("/login")}
            className="bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-6 py-3 rounded-xl text-sm"
          >
            {t("goToSignIn")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 grain-bg">
      <button
        type="button"
        onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/"))}
        data-testid="signup-back-button"
        className="fixed top-5 left-5 z-50 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white border border-[var(--js-border)] text-[var(--js-text)] text-sm font-semibold shadow-sm hover:bg-[var(--js-subtle)] transition"
      >
        <ArrowLeft className="w-4 h-4" />
        {t("back")}
      </button>
      <div className="w-full max-w-md fade-up">
        <div className="flex flex-col items-center mb-8">
          <Link to="/"><Logo size={88} className="drop-shadow-2xl sm:w-24 sm:h-24 md:w-28 md:h-28 lg:w-32 lg:h-32 xl:w-36 xl:h-36" /></Link>
          <h1 className="font-display font-bold text-2xl text-[var(--js-text)] mt-2">{t("createYourAccount")}</h1>
          <p className="text-sm text-[var(--js-text-secondary)] mt-2">{t("joinFree")}</p>
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
              <span className="text-xs font-semibold">{t("shopAsCustomer")}</span>
            </button>
            <button
              type="button"
              onClick={() => setRole("seller")}
              data-testid="role-seller"
              className={`flex flex-col items-center gap-1.5 py-3 px-3 rounded-xl border-2 transition ${role === "seller" ? "border-[#C84B31] bg-[#C84B31]/5" : "border-[var(--js-border)] hover:border-[#1A1A1A]"}`}
            >
              <Store className="w-5 h-5" />
              <span className="text-xs font-semibold">{t("sellOnJubaSquare")}</span>
            </button>
          </div>

          <label className="block">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">{t("fullName")}</span>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required data-testid="signup-name"
                   className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]" />
          </label>

          <label className="block">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">{t("email")}</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="signup-email"
                   className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]" />
          </label>

          <label className="block">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">{t("phoneOptional")}</span>
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+211 9XX XXX XXX" data-testid="signup-phone"
                   className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]" />
          </label>

          <label className="block">
            <span className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">{t("password")}</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} data-testid="signup-password"
                   className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]" />
            <span className="text-[11px] text-[var(--js-text-secondary)] mt-1 inline-block">{t("atLeast6Chars")}</span>
          </label>

          <button type="submit" disabled={busy} data-testid="signup-submit"
            className="w-full bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition disabled:opacity-60">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            {t("createAccount")}
          </button>

          <p className="text-center text-xs text-[var(--js-text-secondary)]">
            {t("bySigningUpAgree")} <Link to="/terms" className="underline">{t("terms")}</Link> {t("andOur")} <Link to="/privacy" className="underline">{t("privacyPolicy")}</Link>.
          </p>
          <p className="text-center text-sm text-[var(--js-text-secondary)]">
            {t("alreadyHaveAccount")} <Link to="/login" className="text-[#C84B31] font-semibold hover:underline">{t("signIn")}</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
