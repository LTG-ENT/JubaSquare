import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useSystem } from "@/context/SystemContext";
import api, { formatDetail } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

const Toggle = ({ label, hint, checked, onChange, testId }) => (
  <label className="flex items-start gap-3 py-3 border-b border-[var(--js-border)] last:border-b-0 cursor-pointer">
    <span className="js-switch shrink-0 mt-0.5">
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} data-testid={testId} />
      <span className="slider" />
    </span>
    <div className="flex-1">
      <p className="font-semibold text-sm text-[var(--js-text)]">{label}</p>
      {hint && <p className="text-xs text-[var(--js-text-secondary)] mt-0.5">{hint}</p>}
    </div>
  </label>
);

export default function Settings() {
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) navigate("/login");
  }, [user, navigate]);

  if (!user) return null;

  return (
    <div className="min-h-screen flex flex-col bg-[var(--js-bg)]">
      <Header />
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-2">Settings</p>
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[var(--js-text)]">{user.role === "admin" ? "Platform settings" : user.role === "seller" ? "Seller settings" : "Account settings"}</h1>

        <div className="mt-8 space-y-6">
          {user.role === "admin" && <AdminSettings />}
          {user.role === "seller" && <SellerSettings />}
          {user.role === "customer" && <CustomerSettings />}
          <ProfileSection />
          <PasswordSection />
        </div>
      </div>
      <Footer />
    </div>
  );
}

function AdminSettings() {
  const { refresh: refreshSystem } = useSystem();
  const [s, setS] = useState(null);
  const [areaDraft, setAreaDraft] = useState("");

  const load = () => api.get("/admin/settings").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);

  if (!s) return null;

  const update = async (patch) => {
    const { data } = await api.put("/admin/settings", patch);
    setS(data); refreshSystem(); toast.success("Saved");
  };

  const addArea = async (e) => {
    e.preventDefault();
    if (!areaDraft.trim()) return;
    try {
      const { data } = await api.post("/admin/areas", { area: areaDraft.trim() });
      setS({ ...s, areas: data.areas });
      setAreaDraft("");
      refreshSystem();
      toast.success("Area added");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };
  const removeArea = async (a) => {
    const { data } = await api.delete(`/admin/areas`, { params: { area: a } });
    setS({ ...s, areas: data.areas });
    refreshSystem();
  };

  const forceLogout = async () => {
    if (!window.confirm("Force-logout ALL users including yourself?")) return;
    await api.post("/admin/force-logout-all");
    toast.success("All sessions invalidated. You will be logged out.");
    setTimeout(() => { localStorage.removeItem("js_token"); window.location.href = "/login"; }, 1200);
  };

  return (
    <>
      <Card title="🏪 Shop Control">
        <Toggle label="Auto-approve new shops" hint="When ON, new shops go live immediately" checked={s.auto_approve_shops} onChange={(v) => update({ auto_approve_shops: v })} testId="admin-auto-approve" />
        <Toggle label="Require verification before going live" checked={s.require_verification} onChange={(v) => update({ require_verification: v })} testId="admin-require-verif" />
        <Toggle label="Allow shop suspension system" checked={s.allow_suspension} onChange={(v) => update({ allow_suspension: v })} testId="admin-allow-suspension" />
      </Card>

      <Card title="⭐ Verification">
        <Toggle label="Verified shops appear first" checked={s.verified_first} onChange={(v) => update({ verified_first: v })} testId="admin-verified-first" />
        <Toggle label="Require document upload for verification" hint="Demo only — not enforced" checked={s.require_doc_for_verification} onChange={(v) => update({ require_doc_for_verification: v })} testId="admin-require-doc" />
      </Card>

      <Card title="📊 Modules">
        <Toggle label="Marketplace module" checked={s.module_marketplace} onChange={(v) => update({ module_marketplace: v })} testId="admin-mod-marketplace" />
        <Toggle label="Wholesale module" checked={s.module_wholesale} onChange={(v) => update({ module_wholesale: v })} testId="admin-mod-wholesale" />
        <Toggle label="Restaurants module" checked={s.module_restaurants} onChange={(v) => update({ module_restaurants: v })} testId="admin-mod-restaurants" />
        <Toggle label="Maintenance mode" hint="Customers cannot place orders" checked={s.maintenance_mode} onChange={(v) => update({ maintenance_mode: v })} testId="admin-maintenance" />
      </Card>

      <Card title="🔐 Security">
        <Row label="Login attempt limit (per email/IP)">
          <input type="number" min={1} value={s.login_attempt_limit} onChange={(e) => setS({ ...s, login_attempt_limit: parseInt(e.target.value) || 5 })}
            onBlur={() => update({ login_attempt_limit: parseInt(s.login_attempt_limit) || 5 })}
            data-testid="admin-login-limit" className="js-input max-w-[200px]" />
        </Row>
        <div className="pt-4 mt-3 border-t border-[var(--js-border)]">
          <p className="font-semibold text-sm text-[var(--js-text)]">Force-logout all users</p>
          <p className="text-xs text-[var(--js-text-secondary)] mt-0.5 mb-3">Emergency: invalidate every active session including your own.</p>
          <button onClick={forceLogout} data-testid="admin-force-logout" className="bg-[#D90429] hover:bg-[#A80020] text-white text-sm font-semibold px-5 py-2.5 rounded-full">
            🚨 Force logout all users
          </button>
        </div>
      </Card>

      <Card title="📍 Delivery Areas">
        <form onSubmit={addArea} className="flex gap-2 mb-3">
          <input value={areaDraft} onChange={(e) => setAreaDraft(e.target.value)} placeholder="New area name..." data-testid="admin-area-input" className="js-input flex-1" />
          <button type="submit" data-testid="admin-area-add" className="bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-5 py-2.5 rounded-full">Add</button>
        </form>
        <ul className="flex flex-wrap gap-2">
          {(s.areas || []).map((a) => (
            <li key={a} data-testid={`admin-area-chip-${a.replace(/\s+/g, "-").toLowerCase()}`} className="inline-flex items-center gap-1 bg-[var(--js-subtle)] text-[var(--js-text)] text-sm font-semibold px-3 py-1.5 rounded-full">
              {a}
              <button onClick={() => removeArea(a)} className="ml-1 hover:text-[#D90429]">×</button>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

function SellerSettings() {
  const { user, setUser } = useAuth();
  const cur = user.settings || {};
  const [form, setForm] = useState({
    low_stock_alert: !!cur.low_stock_alert,
    low_stock_threshold: cur.low_stock_threshold || 5,
    auto_hide_out_of_stock: !!cur.auto_hide_out_of_stock,
    order_notifications: cur.order_notifications !== false,
  });

  const save = async (patch) => {
    const next = { ...form, ...patch };
    setForm(next);
    try {
      const { data } = await api.put("/seller/settings", next);
      setUser(data); toast.success("Saved");
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };

  return (
    <Card title="📦 Product & Orders">
      <Toggle label="Low stock alert" hint="Show banner when product stock is low" checked={form.low_stock_alert} onChange={(v) => save({ low_stock_alert: v })} testId="seller-low-stock-alert" />
      <Row label="Low stock threshold">
        <input type="number" value={form.low_stock_threshold} onChange={(e) => setForm({ ...form, low_stock_threshold: parseInt(e.target.value) || 5 })}
          onBlur={() => save({ low_stock_threshold: parseInt(form.low_stock_threshold) || 5 })}
          data-testid="seller-low-stock-threshold" className="js-input max-w-[120px]" />
      </Row>
      <Toggle label="Auto-hide out-of-stock products" hint="Customers won't see products with stock = 0" checked={form.auto_hide_out_of_stock} onChange={(v) => save({ auto_hide_out_of_stock: v })} testId="seller-auto-hide" />
      <Toggle label="Order notifications" hint="Show toast when a new order arrives (in-app)" checked={form.order_notifications} onChange={(v) => save({ order_notifications: v })} testId="seller-order-notifs" />
    </Card>
  );
}

function CustomerSettings() {
  const { user, setUser } = useAuth();
  const { settings: sys } = useSystem();
  const cur = user.settings || {};
  const [form, setForm] = useState({
    default_area: cur.default_area || "Munuki",
    order_notifications: cur.order_notifications !== false,
    promotion_notifications: !!cur.promotion_notifications,
  });

  const save = async (patch) => {
    const next = { ...form, ...patch };
    setForm(next);
    try {
      const { data } = await api.put("/customer/settings", next);
      setUser(data);
      toast.success("Saved");
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };

  return (
    <>
      <Card title="📍 Location">
        <Row label="Default Juba area">
          <select value={form.default_area} onChange={(e) => save({ default_area: e.target.value })} data-testid="customer-default-area" className="js-input max-w-[240px]">
            {(sys.areas || []).map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </Row>
      </Card>
      <Card title="🔔 Notifications">
        <Toggle label="Order updates" checked={form.order_notifications} onChange={(v) => save({ order_notifications: v })} testId="customer-order-notifs" />
        <Toggle label="Promotion messages" checked={form.promotion_notifications} onChange={(v) => save({ promotion_notifications: v })} testId="customer-promo-notifs" />
      </Card>
    </>
  );
}

function ProfileSection() {
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({ name: user.name, phone: user.phone || "" });

  const save = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.put("/auth/profile", form);
      setUser(data); toast.success("Profile updated");
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };

  return (
    <Card title="👤 Profile">
      <form onSubmit={save} className="space-y-3">
        <Row label="Name"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="profile-name" className="js-input max-w-md" /></Row>
        <Row label="Email"><input value={user.email} disabled className="js-input max-w-md opacity-60" /></Row>
        <Row label="Phone"><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid="profile-phone" className="js-input max-w-md" /></Row>
        <button type="submit" data-testid="profile-save" className="bg-[#1A1A1A] text-white text-sm font-semibold px-5 py-2.5 rounded-full">Save profile</button>
      </form>
    </Card>
  );
}

function PasswordSection() {
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/auth/change-password", pw);
      setPw({ current_password: "", new_password: "" });
      toast.success("Password changed");
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };
  return (
    <Card title="🔑 Change password">
      <form onSubmit={submit} className="space-y-3">
        <Row label="Current password"><input type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} data-testid="current-pw" className="js-input max-w-md" /></Row>
        <Row label="New password"><input type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} data-testid="new-pw" className="js-input max-w-md" /></Row>
        <button type="submit" data-testid="change-pw-btn" className="bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-5 py-2.5 rounded-full">Update password</button>
      </form>
    </Card>
  );
}

function Card({ title, children }) {
  return (
    <section className="bg-white border border-[var(--js-border)] rounded-3xl p-6">
      <h2 className="font-display font-semibold text-lg text-[var(--js-text)] mb-2">{title}</h2>
      {children}
    </section>
  );
}
function Row({ label, children }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 py-2">
      <span className="text-sm font-semibold text-[var(--js-text)]">{label}</span>
      <div>{children}</div>
    </div>
  );
}
