import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Shield, Store, User, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Logo } from "@/components/Logo";

const ROLES = [
  { id: "admin", email: "admin@demo.com", label: "Login as Admin", desc: "Verify shops, manage emails & view all orders", icon: Shield, color: "#1A1A1A" },
  { id: "seller", email: "seller@demo.com", label: "Login as Seller", desc: "Manage shops, products & track orders", icon: Store, color: "#2D6A4F" },
  { id: "customer", email: "customer@demo.com", label: "Login as Customer", desc: "Browse, order from shops & restaurants", icon: User, color: "#C84B31" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(null);

  const handleLogin = async (role) => {
    setBusy(role.id);
    const res = await login(role.email, "1234");
    setBusy(null);
    if (!res.ok) { toast.error(res.error); return; }
    toast.success(`Welcome, ${res.user.name}!`);
    if (res.user.role === "admin") navigate("/admin");
    else if (res.user.role === "seller") navigate("/seller");
    else navigate("/");
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 grain-bg">
      <div className="w-full max-w-md fade-up">
        <div className="flex flex-col items-center mb-10">
          <Logo size={88} className="shadow-xl" />
          <h1 className="font-display font-bold text-3xl text-[var(--js-text)] mt-5">JubaSquare</h1>
          <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--js-text-secondary)] font-bold mt-1">by L.T.G Enterprise</p>
          <p className="text-sm text-[var(--js-text-secondary)] mt-4 text-center max-w-xs">
            Demo showcase — pick a role below to instantly explore the platform. No signup required.
          </p>
        </div>

        <div className="bg-white border border-[var(--js-border)] rounded-3xl p-5 sm:p-7 shadow-[0_8px_32px_rgba(0,0,0,0.06)]">
          <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-4 text-center">Choose a demo role</p>
          <div className="space-y-3">
            {ROLES.map((r) => {
              const Icon = r.icon;
              const loading = busy === r.id;
              return (
                <button
                  key={r.id} disabled={busy !== null} onClick={() => handleLogin(r)}
                  data-testid={`login-${r.id}-button`}
                  className="w-full group flex items-center gap-4 bg-[var(--js-bg)] hover:bg-white border border-[var(--js-border)] hover:border-[#1A1A1A] rounded-2xl p-4 transition-all disabled:opacity-60 disabled:cursor-not-allowed text-left"
                >
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 transition-transform group-hover:scale-110" style={{ background: r.color, color: "white" }}>
                    {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Icon className="w-5 h-5" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-display font-semibold text-base text-[var(--js-text)]">{r.label}</p>
                    <p className="text-xs text-[var(--js-text-secondary)] mt-0.5 truncate">{r.desc}</p>
                  </div>
                  <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded-full bg-[var(--js-subtle)] text-[var(--js-text-secondary)]">{r.id}</span>
                </button>
              );
            })}
          </div>
          <div className="mt-6 pt-5 border-t border-[var(--js-border)] text-center">
            <p className="text-xs text-[var(--js-text-secondary)]">
              All demo accounts use password <code className="bg-[var(--js-subtle)] px-1.5 py-0.5 rounded text-[var(--js-text)] font-bold">1234</code>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
