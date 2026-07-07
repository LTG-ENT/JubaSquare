import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api, { formatDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ImageUpload from "@/components/ImageUpload";
import AreaSelectField from "@/components/AreaSelectField";
import { ArrowLeft, ExternalLink, Save, Trash2, Plus, AlertCircle, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

export default function SellerShopEdit() {
  const { shop_id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [shop, setShop] = useState(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    area: "Munuki",
    image_url: "",
    banner_url: "",
    logo_url: "",
    opening_hours: "",
    is_open: true,
    delivery_mode: "free",
    delivery_fee_usd: 0,
    delivery_per_area: [],
    receipt_show_logo: false,
    receipt_logo_url: "",
    eta_mode: "off",
    eta_fixed_minutes: 30,
    eta_min_minutes: 25,
    eta_max_minutes: 45,
  });

  useEffect(() => {
    let cancelled = false;
    api.get(`/shops/${shop_id}`)
      .then((r) => {
        if (cancelled) return;
        const s = r.data;
        setShop(s);
        setForm({
          name: s.name || "",
          description: s.description || "",
          area: s.area || "Munuki",
          image_url: s.image_url || "",
          banner_url: s.banner_url || "",
          logo_url: s.logo_url || "",
          opening_hours: s.opening_hours || "",
          is_open: s.is_open !== false,
          delivery_mode: s.delivery_mode || "free",
          delivery_fee_usd: s.delivery_fee_usd || 0,
          delivery_per_area: s.delivery_per_area || [],
          receipt_show_logo: !!s.receipt_show_logo,
          receipt_logo_url: s.receipt_logo_url || "",
          eta_mode: s.eta_mode || "off",
          eta_fixed_minutes: s.eta_fixed_minutes ?? 30,
          eta_min_minutes: s.eta_min_minutes ?? 25,
          eta_max_minutes: s.eta_max_minutes ?? 45,
        });
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.status === 404 ? "Shop not found" : "Could not load shop");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [shop_id]);

  const isOwner = !!(user && shop && (user.role === "admin" || user.id === shop.seller_id));

  const onSave = async (e) => {
    e?.preventDefault?.();
    if (!form.name.trim()) {
      toast.error("Shop name is required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description,
        area: form.area,
        image_url: form.image_url,
        banner_url: form.banner_url,
        logo_url: form.logo_url,
        opening_hours: form.opening_hours,
        is_open: !!form.is_open,
        delivery_mode: form.delivery_mode,
        delivery_fee_usd: form.delivery_mode === "fixed" ? parseFloat(form.delivery_fee_usd) || 0 : 0,
        delivery_per_area: form.delivery_mode === "per_area"
          ? (form.delivery_per_area || [])
            .filter((a) => a.area && a.area.trim())
            .map((a) => ({ area: a.area.trim(), fee_usd: parseFloat(a.fee_usd) || 0 }))
          : [],
        receipt_show_logo: !!form.receipt_show_logo,
        receipt_logo_url: (form.receipt_logo_url || "").trim(),
        eta_mode: form.eta_mode || "off",
        eta_fixed_minutes: form.eta_mode === "fixed" ? (parseInt(form.eta_fixed_minutes, 10) || null) : null,
        eta_min_minutes: form.eta_mode === "range" ? (parseInt(form.eta_min_minutes, 10) || null) : null,
        eta_max_minutes: form.eta_mode === "range" ? (parseInt(form.eta_max_minutes, 10) || null) : null,
      };
      const { data } = await api.put(`/shops/${shop_id}`, payload);
      setShop(data);
      toast.success("Shop page updated");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Wrapper>
        <div className="max-w-3xl mx-auto px-4 py-20 text-center">
          <p className="text-[var(--js-text-secondary)]">Loading shop…</p>
        </div>
      </Wrapper>
    );
  }
  if (error || !shop) {
    return (
      <Wrapper>
        <div className="max-w-2xl mx-auto px-4 py-20 text-center">
          <AlertCircle className="w-12 h-12 mx-auto text-[#D90429] mb-4" />
          <h1 className="font-display font-bold text-2xl">{error || "Shop unavailable"}</h1>
          <Link to="/seller" className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-[#C84B31] hover:underline">
            <ArrowLeft className="w-4 h-4" /> Back to dashboard
          </Link>
        </div>
      </Wrapper>
    );
  }
  if (!isOwner) {
    return (
      <Wrapper>
        <div className="max-w-2xl mx-auto px-4 py-20 text-center">
          <ShieldCheck className="w-12 h-12 mx-auto text-[#D90429] mb-4" />
          <h1 className="font-display font-bold text-2xl">Not your shop</h1>
          <p className="text-sm text-[var(--js-text-secondary)] mt-2">You can only edit shops you own.</p>
          <Link to="/seller" className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-[#C84B31] hover:underline">
            <ArrowLeft className="w-4 h-4" /> Back to dashboard
          </Link>
        </div>
      </Wrapper>
    );
  }

  return (
    <Wrapper>
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="flex items-start justify-between gap-3 flex-wrap mb-8">
          <div>
            <Link to="/seller" className="inline-flex items-center gap-1 text-xs font-bold text-[var(--js-text-secondary)] hover:text-[var(--js-text)] mb-2">
              <ArrowLeft className="w-3.5 h-3.5" /> Dashboard
            </Link>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold">Shop page editor</p>
            <h1 className="font-display font-bold text-3xl sm:text-4xl text-[var(--js-text)]" data-testid="shop-edit-title">{shop.name}</h1>
            <p className="text-sm text-[var(--js-text-secondary)] mt-1">Customize how customers see your standalone shop page.</p>
          </div>
          <Link
            to={`/shop/${shop_id}`}
            target="_blank"
            data-testid="view-public-link"
            className="inline-flex items-center gap-1.5 bg-white border border-[var(--js-border)] hover:border-[#1A1A1A] text-[var(--js-text)] text-sm font-bold px-4 py-2.5 rounded-full"
          >
            <ExternalLink className="w-4 h-4" /> View public page
          </Link>
        </div>

        <form onSubmit={onSave} noValidate className="space-y-6" data-testid="shop-edit-form">
          {/* Storefront identity */}
          <Section title="Storefront identity" subtitle="Logo, banner, and basic info shown to customers.">
            <Field label="Shop name" required>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                data-testid="shop-edit-name"
                className="js-input"
              />
            </Field>
            <Field label="Description" hint="Tell customers what makes your shop unique.">
              <textarea
                rows={3}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                data-testid="shop-edit-description"
                className="js-input"
              />
            </Field>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Area">
                <AreaSelectField
                  value={form.area}
                  onChange={(v) => setForm({ ...form, area: v })}
                  testId="shop-edit-area"
                />
              </Field>
              <Field label="Opening hours" hint="e.g. Mon–Sat · 9:00 AM – 8:00 PM">
                <input
                  type="text"
                  value={form.opening_hours}
                  onChange={(e) => setForm({ ...form, opening_hours: e.target.value })}
                  placeholder="Mon–Sat · 9:00 AM – 8:00 PM"
                  data-testid="shop-edit-hours"
                  className="js-input"
                />
              </Field>
            </div>
          </Section>

          {/* Imagery */}
          <Section title="Branding & imagery" subtitle="A wide banner and a square logo make your shop page feel professional.">
            <ImageUpload
              label="Logo (square)"
              value={form.logo_url}
              onChange={(v) => setForm({ ...form, logo_url: v })}
              testId="shop-edit-logo"
            />
            <ImageUpload
              label="Banner (wide cover image)"
              value={form.banner_url}
              onChange={(v) => setForm({ ...form, banner_url: v })}
              testId="shop-edit-banner"
            />
            <ImageUpload
              label="Default shop photo (used as fallback)"
              value={form.image_url}
              onChange={(v) => setForm({ ...form, image_url: v })}
              testId="shop-edit-image"
            />
          </Section>

          {/* Status */}
          <Section title="Shop status" subtitle="Temporarily close your shop without deleting anything.">
            <div className="flex items-center gap-3 bg-[var(--js-subtle)] border border-[var(--js-border)] rounded-2xl p-4">
              <input
                id="is_open"
                type="checkbox"
                checked={form.is_open}
                onChange={(e) => setForm({ ...form, is_open: e.target.checked })}
                data-testid="shop-edit-is-open"
                className="w-5 h-5 accent-[#C84B31]"
              />
              <label htmlFor="is_open" className="flex-1 cursor-pointer">
                <p className="font-display font-semibold text-sm text-[var(--js-text)]">
                  {form.is_open ? "Shop is OPEN" : "Shop is CLOSED"}
                </p>
                <p className="text-xs text-[var(--js-text-secondary)]">
                  {form.is_open
                    ? "Customers can browse your products and place orders."
                    : "Customers will see a closed banner; new orders may be paused."}
                </p>
              </label>
            </div>
          </Section>

          {/* Delivery */}
          <Section title="Delivery settings" subtitle="Pick a pricing model for delivery from this shop.">
            <DeliveryEditor form={form} setForm={setForm} />
          </Section>

          {/* Estimated delivery */}
          <Section
            title="Estimated delivery time"
            subtitle="Shown on the customer's checkout and order-tracking page. Set a fixed value, a range, or leave off."
          >
            <ShopEtaEditor form={form} setForm={setForm} />
          </Section>

          {/* Receipt logo */}
          <Section
            title="Customer receipt logo"
            subtitle="Turn this on to print your shop's logo at the top of every customer receipt."
          >
            <ShopReceiptLogoEditor form={form} setForm={setForm} />
          </Section>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => navigate("/seller")}
              className="text-sm font-bold px-5 py-2.5 rounded-full border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              data-testid="shop-edit-save"
              className="inline-flex items-center gap-1.5 bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-bold px-6 py-2.5 rounded-full disabled:bg-[#A3A39E]"
            >
              <Save className="w-4 h-4" /> {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </Wrapper>
  );
}

function Wrapper({ children }) {
  return (
    <div className="min-h-screen flex flex-col bg-[var(--js-bg)]">
      <Header />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}

function Section({ title, subtitle, children }) {
  return (
    <section className="bg-white border border-[var(--js-border)] rounded-3xl p-5 sm:p-6 space-y-4">
      <div>
        <h2 className="font-display font-bold text-lg text-[var(--js-text)]">{title}</h2>
        {subtitle && <p className="text-xs text-[var(--js-text-secondary)] mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({ label, required, hint, children }) {
  return (
    <div>
      <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)] block mb-1.5">
        {label} {required && <span className="text-[#D90429]">*</span>}
      </label>
      {children}
      {hint && <p className="text-[10px] text-[var(--js-text-secondary)] mt-1">{hint}</p>}
    </div>
  );
}

function DeliveryEditor({ form, setForm }) {
  const mode = form.delivery_mode || "free";
  const setMode = (m) => setForm({ ...form, delivery_mode: m });
  const updateAreaFee = (idx, key, value) => {
    const next = [...(form.delivery_per_area || [])];
    next[idx] = { ...next[idx], [key]: value };
    setForm({ ...form, delivery_per_area: next });
  };
  const addArea = () => {
    setForm({
      ...form,
      delivery_per_area: [...(form.delivery_per_area || []), { area: "", fee_usd: 0 }],
    });
  };
  const removeArea = (idx) => {
    const next = [...(form.delivery_per_area || [])];
    next.splice(idx, 1);
    setForm({ ...form, delivery_per_area: next });
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        {[
          { id: "free", label: "🆓 Free", hint: "No charge" },
          { id: "fixed", label: "💵 Fixed", hint: "One amount" },
          { id: "per_area", label: "📍 Per area", hint: "Different per location" },
        ].map((opt) => (
          <button
            type="button"
            key={opt.id}
            onClick={() => setMode(opt.id)}
            data-testid={`shop-edit-delivery-mode-${opt.id}`}
            className={`p-3 rounded-2xl border-2 text-left transition ${
              mode === opt.id
                ? "border-[#C84B31] bg-[#C84B31]/5"
                : "border-[var(--js-border)] bg-white hover:border-[var(--js-text)]"
            }`}
          >
            <p className="text-sm font-bold text-[var(--js-text)]">{opt.label}</p>
            <p className="text-[10px] text-[var(--js-text-secondary)]">{opt.hint}</p>
          </button>
        ))}
      </div>

      {mode === "fixed" && (
        <Field label="Delivery fee (USD)">
          <input
            type="number"
            step="0.01"
            min="0"
            value={form.delivery_fee_usd ?? 0}
            onChange={(e) => setForm({ ...form, delivery_fee_usd: e.target.value })}
            data-testid="shop-edit-delivery-fee"
            className="js-input"
            placeholder="e.g. 2.50"
          />
        </Field>
      )}

      {mode === "per_area" && (
        <div className="space-y-2">
          <p className="text-xs text-[var(--js-text-secondary)]">Set a different delivery fee per area you serve.</p>
          {(form.delivery_per_area || []).map((entry, idx) => (
            <div key={idx} className="flex gap-2 items-center" data-testid={`shop-edit-area-row-${idx}`}>
              <div className="flex-1">
                <AreaSelectField
                  value={entry.area}
                  onChange={(v) => updateAreaFee(idx, "area", v)}
                  testId={`shop-edit-area-select-${idx}`}
                  placeholder="Select area"
                />
              </div>
              <div className="relative w-32">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-[var(--js-text-secondary)]">USD</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={entry.fee_usd ?? 0}
                  onChange={(e) => updateAreaFee(idx, "fee_usd", e.target.value)}
                  data-testid={`shop-edit-area-fee-${idx}`}
                  className="js-input pl-12"
                  placeholder="0.00"
                />
              </div>
              <button
                type="button"
                onClick={() => removeArea(idx)}
                data-testid={`shop-edit-area-remove-${idx}`}
                className="p-2 text-[#D90429] hover:bg-[#D90429]/10 rounded-full"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={addArea}
            data-testid="shop-edit-area-add"
            className="text-xs font-semibold text-[#C84B31] hover:underline inline-flex items-center gap-1"
          >
            <Plus className="w-3 h-3" /> Add area
          </button>
        </div>
      )}
    </div>
  );
}

function ShopEtaEditor({ form, setForm }) {
  return (
    <div className="space-y-3">
      <div className="inline-flex bg-[var(--js-subtle)] rounded-full p-1">
        {[
          { id: "off", label: "Off" },
          { id: "fixed", label: "Fixed" },
          { id: "range", label: "Range" },
        ].map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => setForm({ ...form, eta_mode: opt.id })}
            data-testid={`shop-edit-eta-mode-${opt.id}`}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold ${
              form.eta_mode === opt.id ? "bg-[#C84B31] text-white shadow" : "text-[var(--js-text-secondary)]"
            }`}
          >{opt.label}</button>
        ))}
      </div>
      {form.eta_mode === "fixed" && (
        <div>
          <label className="block text-xs font-semibold text-[var(--js-text-secondary)] mb-1">Delivery in (minutes)</label>
          <input
            type="number" min={1} max={240}
            value={form.eta_fixed_minutes}
            onChange={(e) => setForm({ ...form, eta_fixed_minutes: e.target.value })}
            data-testid="shop-edit-eta-fixed"
            className="w-32 px-3 py-2 rounded-lg border border-[var(--js-border)] bg-[var(--js-bg)] text-[var(--js-text)] text-sm"
          />
        </div>
      )}
      {form.eta_mode === "range" && (
        <div className="flex items-end gap-3">
          <div>
            <label className="block text-xs font-semibold text-[var(--js-text-secondary)] mb-1">Min minutes</label>
            <input
              type="number" min={1} max={240}
              value={form.eta_min_minutes}
              onChange={(e) => setForm({ ...form, eta_min_minutes: e.target.value })}
              data-testid="shop-edit-eta-min"
              className="w-28 px-3 py-2 rounded-lg border border-[var(--js-border)] bg-[var(--js-bg)] text-[var(--js-text)] text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[var(--js-text-secondary)] mb-1">Max minutes</label>
            <input
              type="number" min={1} max={240}
              value={form.eta_max_minutes}
              onChange={(e) => setForm({ ...form, eta_max_minutes: e.target.value })}
              data-testid="shop-edit-eta-max"
              className="w-28 px-3 py-2 rounded-lg border border-[var(--js-border)] bg-[var(--js-bg)] text-[var(--js-text)] text-sm"
            />
          </div>
        </div>
      )}
    </div>
  );
}

function ShopReceiptLogoEditor({ form, setForm }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 bg-[var(--js-subtle)] border border-[var(--js-border)] rounded-2xl p-4">
        <input
          id="shop_receipt_show_logo"
          type="checkbox"
          checked={!!form.receipt_show_logo}
          onChange={(e) => setForm({ ...form, receipt_show_logo: e.target.checked })}
          className="w-5 h-5 accent-[#C84B31]"
          data-testid="shop-edit-receipt-logo-toggle"
        />
        <label htmlFor="shop_receipt_show_logo" className="flex-1 cursor-pointer">
          <p className="font-display font-semibold text-sm text-[var(--js-text)]">Print my logo on customer receipts</p>
          <p className="text-xs text-[var(--js-text-secondary)]">Shows above the CUSTOMER RECEIPT header. Falls back to your shop logo/photo if no URL is set.</p>
        </label>
      </div>
      {form.receipt_show_logo && (
        <div>
          <label className="block text-xs font-semibold text-[var(--js-text-secondary)] mb-1">Logo image URL</label>
          <input
            type="url"
            placeholder="https://…/logo.png (leave blank to use shop logo)"
            value={form.receipt_logo_url}
            onChange={(e) => setForm({ ...form, receipt_logo_url: e.target.value })}
            data-testid="shop-edit-receipt-logo-url"
            className="w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-[var(--js-bg)] text-[var(--js-text)] text-sm"
          />
        </div>
      )}
    </div>
  );
}

