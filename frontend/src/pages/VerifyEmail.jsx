import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api, { formatDetail } from "@/lib/api";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Logo } from "@/components/Logo";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState("loading"); // loading | ok | error
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("Missing verification token.");
      return;
    }
    (async () => {
      try {
        const { data } = await api.post("/auth/verify-email", { token });
        setState("ok");
        setMessage(data.message || "Email verified!");
      } catch (e) {
        setState("error");
        setMessage(formatDetail(e.response?.data?.detail || e.message));
      }
    })();
  }, [token]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 grain-bg">
      <div className="w-full max-w-md text-center fade-up">
        <Link to="/"><Logo size={104} className="shadow-xl mx-auto" /></Link>
        <h1 className="font-display font-bold text-2xl text-[var(--js-text)] mt-6">Verify your email</h1>

        <div className="mt-8 bg-white border border-[var(--js-border)] rounded-3xl p-8" data-testid="verify-email-card">
          {state === "loading" && (
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="w-10 h-10 text-[#C84B31] animate-spin" />
              <p className="text-sm text-[var(--js-text-secondary)]">Verifying…</p>
            </div>
          )}
          {state === "ok" && (
            <div className="flex flex-col items-center gap-4">
              <CheckCircle2 className="w-14 h-14 text-[#2D6A4F]" />
              <p className="text-sm text-[var(--js-text)] font-semibold">{message}</p>
              <Link to="/login" className="mt-2 bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-6 py-3 rounded-xl text-sm">
                Sign in now
              </Link>
            </div>
          )}
          {state === "error" && (
            <div className="flex flex-col items-center gap-4">
              <XCircle className="w-14 h-14 text-[#C84B31]" />
              <p className="text-sm text-[var(--js-text)] font-semibold">{message}</p>
              <Link to="/login" className="mt-2 text-[#C84B31] hover:underline text-sm font-semibold">
                Back to sign in
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
