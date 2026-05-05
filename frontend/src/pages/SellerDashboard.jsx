import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatUSD, formatDetail } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Store, Package, ShoppingBag, DollarSign, Settings, Plus, X, Edit2, Trash2, CheckCircle2, Clock, XCircle } from "lucide-react";
import { toast } from "sonner";

const TABS = [
  { id: "shops", label: "My Shops", icon: Store },
  { id: "products", label: "Products", icon: Package },
  { id: "orders", label: "Orders", icon: ShoppingBag },
  { id: "rate", label: "Exchange Rate", icon: DollarSign },
  { id: "settings", label: "Settings", icon: Settings },
];

const CATEGORIES = ["Electronics", "Fashion", "Home Essentials", "Pharmacy", "Automotive", "Other"];
const AREAS = ["Munuki", "Jebel", "Gudele", "Konyo Konyo", "Hai Cinema", "Nyakuron", "Atlabara"];

export default function SellerDashboard() {
  const [tab, setTab] = useState("shops");
  return (
    <div className="min-h-screen flex flex-col bg-[#F9F9F6]">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">Seller Dashboard</p>
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">Manage your business</h1>

        <div className="mt-8 flex flex-wrap gap-2 border-b border-[#E2E2D9] overflow-x-auto">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                data-testid={`seller-tab-${t.id}`}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition whitespace-nowrap ${
                  tab === t.id
                    ? "border-[#C84B31] text-[#C84B31]"
                    : "border-transparent text-[#5C5C5C] hover:text-[#1A1A1A]"
                }`}
              >
                <Icon className="w-4 h-4" /> {t.label}
              </button>
            );
          })}
        </div>

        <div className="mt-8">
          {tab === "shops" && <ShopsTab />}
          {tab === "products" && <ProductsTab />}
          {tab === "orders" && <OrdersTab />}
          {tab === "rate" && <RateTab />}
          {tab === "settings" && <SettingsTab />}
        </div>
      </div>
      <Footer />
    </div>
  );
}

const VerificationBadge = ({ status }) => {
  if (status === "Verified") return <span className="inline-flex items-center gap-1 bg-[#2D6A4F]/10 text-[#2D6A4F] text-xs font-bold px-2 py-1 rounded-full"><CheckCircle2 className="w-3 h-3" /> Verified</span>;
  if (status === "Rejected") return <span className="inline-flex items-center gap-1 bg-[#D90429]/10 text-[#D90429] text-xs font-bold px-2 py-1 rounded-full"><XCircle className="w-3 h-3" /> Rejected</span>;
  return <span className="inline-flex items-center gap-1 bg-[#E9C46A]/30 text-[#1A1A1A] text-xs font-bold px-2 py-1 rounded-full"><Clock className="w-3 h-3" /> Pending</span>;
};

function ShopsTab() {
  const [shops, setShops] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", category: "Electronics", description: "", area: "Munuki", image_url: "" });

  const load = () => api.get("/shops/mine").then((r) => setShops(r.data));
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        await api.put(`/shops/${editing.id}`, form);
        toast.success("Shop updated");
      } else {
        await api.post("/shops", form);
        toast.success("Shop created (pending verification)");
      }
      setShowForm(false); setEditing(null);
      setForm({ name: "", category: "Electronics", description: "", area: "Munuki", image_url: "" });
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const onEdit = (s) => { setEditing(s); setForm({ name: s.name, category: s.category, description: s.description, area: s.area, image_url: s.image_url }); setShowForm(true); };
  const onDelete = async (id) => {
    if (!window.confirm("Delete this shop and its products?")) return;
    await api.delete(`/shops/${id}`);
    toast.success("Shop deleted");
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-[#5C5C5C]">{shops.length} shop{shops.length !== 1 && "s"}</p>
        <button
          onClick={() => { setShowForm(true); setEditing(null); }}
          data-testid="add-shop-btn"
          className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-4 py-2.5 rounded-full"
        >
          <Plus className="w-4 h-4" /> Add Shop
        </button>
      </div>

      {showForm && (
        <Modal onClose={() => { setShowForm(false); setEditing(null); }} title={editing ? "Edit shop" : "New shop"}>
          <form onSubmit={submit} className="space-y-3">
            <Input label="Shop name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required testId="shop-name-input" />
            <Select label="Category" value={form.category} onChange={(v) => setForm({ ...form, category: v })} options={CATEGORIES} testId="shop-category-select" />
            <Select label="Area" value={form.area} onChange={(v) => setForm({ ...form, area: v })} options={AREAS} testId="shop-area-select" />
            <Input label="Image URL" value={form.image_url} onChange={(v) => setForm({ ...form, image_url: v })} testId="shop-image-input" />
            <Textarea label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} testId="shop-desc-input" />
            <button type="submit" data-testid="shop-submit-btn" className="w-full bg-[#1A1A1A] text-white font-semibold py-3 rounded-full">{editing ? "Save changes" : "Create shop"}</button>
          </form>
        </Modal>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {shops.map((s) => (
          <div key={s.id} data-testid={`my-shop-${s.id}`} className="bg-white border border-[#E2E2D9] rounded-2xl overflow-hidden">
            <div className="aspect-[16/9] bg-[#F2EBE5] overflow-hidden relative">
              <img src={s.image_url} alt={s.name} className="w-full h-full object-cover" />
              <div className="absolute top-3 right-3"><VerificationBadge status={s.verification} /></div>
            </div>
            <div className="p-4">
              <p className="text-[10px] uppercase tracking-wider text-[#5C5C5C] font-bold">{s.category} · {s.area}</p>
              <h3 className="font-display font-semibold text-lg text-[#1A1A1A] mt-0.5">{s.name}</h3>
              <p className="text-sm text-[#5C5C5C] mt-1 line-clamp-2">{s.description}</p>
              <div className="mt-3 flex gap-2">
                <button onClick={() => onEdit(s)} data-testid={`edit-shop-${s.id}`} className="flex-1 bg-[#F2EBE5] text-[#1A1A1A] text-xs font-semibold py-2 rounded-full inline-flex items-center justify-center gap-1"><Edit2 className="w-3 h-3" /> Edit</button>
                <button onClick={() => onDelete(s.id)} data-testid={`delete-shop-${s.id}`} className="flex-1 bg-[#D90429]/10 text-[#D90429] text-xs font-semibold py-2 rounded-full inline-flex items-center justify-center gap-1"><Trash2 className="w-3 h-3" /> Delete</button>
              </div>
            </div>
          </div>
        ))}
        {shops.length === 0 && <p className="text-sm text-[#5C5C5C] col-span-full">No shops yet. Click "Add Shop" to get started.</p>}
      </div>
    </div>
  );
}

function ProductsTab() {
  const [shops, setShops] = useState([]);
  const [products, setProducts] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ shop_id: "", name: "", category: "Electronics", price_usd: 0, image_url: "", description: "", stock: 100 });
  const [rate, setRate] = useState(600);

  const loadAll = async () => {
    const s = (await api.get("/shops/mine")).data;
    setShops(s);
    if (s.length && !form.shop_id) setForm((f) => ({ ...f, shop_id: s[0].id, category: s[0].category }));
    const allProducts = [];
    for (const sh of s) {
      const r = await api.get(`/products?shop_id=${sh.id}`);
      allProducts.push(...r.data.map((p) => ({ ...p, shop_name: sh.name })));
    }
    setProducts(allProducts);
    const rateRes = await api.get("/exchange-rate");
    setRate(rateRes.data?.rate || 600);
  };
  useEffect(() => { loadAll(); }, []); // eslint-disable-line

  const submit = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form, price_usd: parseFloat(form.price_usd), stock: parseInt(form.stock) };
      if (editing) {
        await api.put(`/products/${editing.id}`, payload);
        toast.success("Product updated");
      } else {
        await api.post("/products", payload);
        toast.success("Product added");
      }
      setShowForm(false); setEditing(null);
      setForm({ shop_id: shops[0]?.id || "", name: "", category: "Electronics", price_usd: 0, image_url: "", description: "", stock: 100 });
      loadAll();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const onEdit = (p) => { setEditing(p); setForm({ shop_id: p.shop_id, name: p.name, category: p.category, price_usd: p.price_usd, image_url: p.image_url, description: p.description, stock: p.stock }); setShowForm(true); };
  const onDelete = async (id) => {
    if (!window.confirm("Delete this product?")) return;
    await api.delete(`/products/${id}`);
    toast.success("Deleted");
    loadAll();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-[#5C5C5C]">{products.length} products · Exchange rate <span className="font-bold text-[#1A1A1A]">1 USD = {rate} SSP</span></p>
        <button
          onClick={() => { setShowForm(true); setEditing(null); }}
          disabled={shops.length === 0}
          data-testid="add-product-btn"
          className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] text-white text-sm font-semibold px-4 py-2.5 rounded-full"
        >
          <Plus className="w-4 h-4" /> Add Product
        </button>
      </div>

      {showForm && shops.length > 0 && (
        <Modal onClose={() => { setShowForm(false); setEditing(null); }} title={editing ? "Edit product" : "New product"}>
          <form onSubmit={submit} className="space-y-3">
            <Select label="Shop" value={form.shop_id} onChange={(v) => setForm({ ...form, shop_id: v })} options={shops.map((s) => ({ value: s.id, label: s.name }))} testId="product-shop-select" />
            <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required testId="product-name-input" />
            <Select label="Category" value={form.category} onChange={(v) => setForm({ ...form, category: v })} options={CATEGORIES} testId="product-cat-select" />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Price (USD)" type="number" step="0.01" value={form.price_usd} onChange={(v) => setForm({ ...form, price_usd: v })} required testId="product-price-input" />
              <Input label="Stock" type="number" value={form.stock} onChange={(v) => setForm({ ...form, stock: v })} testId="product-stock-input" />
            </div>
            <p className="text-xs text-[#5C5C5C]">≈ <strong>SSP {(parseFloat(form.price_usd || 0) * rate).toLocaleString()}</strong> at current rate</p>
            <Input label="Image URL" value={form.image_url} onChange={(v) => setForm({ ...form, image_url: v })} testId="product-image-input" />
            <Textarea label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} testId="product-desc-input" />
            <button type="submit" data-testid="product-submit-btn" className="w-full bg-[#1A1A1A] text-white font-semibold py-3 rounded-full">{editing ? "Save" : "Create product"}</button>
          </form>
        </Modal>
      )}

      <div className="bg-white border border-[#E2E2D9] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F9F9F6] text-[#5C5C5C] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-4 font-bold">Product</th>
                <th className="text-left p-4 font-bold hidden md:table-cell">Shop</th>
                <th className="text-left p-4 font-bold">Price</th>
                <th className="text-left p-4 font-bold hidden sm:table-cell">Stock</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="border-t border-[#E2E2D9]" data-testid={`product-row-${p.id}`}>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <img src={p.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                      <div className="min-w-0">
                        <p className="font-semibold text-[#1A1A1A] truncate">{p.name}</p>
                        <p className="text-xs text-[#5C5C5C]">{p.category}</p>
                      </div>
                    </div>
                  </td>
                  <td className="p-4 text-[#5C5C5C] hidden md:table-cell">{p.shop_name}</td>
                  <td className="p-4">
                    <p className="font-bold text-[#1A1A1A]">{formatUSD(p.price_usd)}</p>
                    <p className="text-xs text-[#5C5C5C]">SSP {(p.price_usd * rate).toLocaleString()}</p>
                  </td>
                  <td className="p-4 hidden sm:table-cell">{p.stock}</td>
                  <td className="p-4 text-right">
                    <div className="inline-flex gap-1">
                      <button onClick={() => onEdit(p)} data-testid={`edit-product-${p.id}`} className="p-2 hover:bg-[#F2EBE5] rounded-full"><Edit2 className="w-3.5 h-3.5" /></button>
                      <button onClick={() => onDelete(p.id)} data-testid={`delete-product-${p.id}`} className="p-2 hover:bg-[#D90429]/10 rounded-full"><Trash2 className="w-3.5 h-3.5 text-[#D90429]" /></button>
                    </div>
                  </td>
                </tr>
              ))}
              {products.length === 0 && (
                <tr><td colSpan={5} className="p-8 text-center text-[#5C5C5C]">No products yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function OrdersTab() {
  const [orders, setOrders] = useState([]);
  const load = () => api.get("/orders/seller").then((r) => setOrders(r.data));
  useEffect(() => { load(); }, []);

  const updateStatus = async (id, status) => {
    await api.put(`/orders/${id}/status`, { status });
    toast.success(`Status updated to ${status}`);
    load();
  };

  return (
    <div className="bg-white border border-[#E2E2D9] rounded-2xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F9F9F6] text-[#5C5C5C] text-xs uppercase tracking-wider">
            <tr>
              <th className="text-left p-4 font-bold">Order</th>
              <th className="text-left p-4 font-bold hidden sm:table-cell">Customer</th>
              <th className="text-left p-4 font-bold hidden lg:table-cell">Items</th>
              <th className="text-left p-4 font-bold">Total</th>
              <th className="text-left p-4 font-bold">Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} className="border-t border-[#E2E2D9]" data-testid={`seller-order-${o.id}`}>
                <td className="p-4">
                  <p className="font-semibold text-[#1A1A1A]">#{o.id.slice(0, 8).toUpperCase()}</p>
                  <p className="text-xs text-[#5C5C5C]">{new Date(o.created_at).toLocaleDateString()}</p>
                </td>
                <td className="p-4 hidden sm:table-cell">
                  <p className="font-semibold text-[#1A1A1A]">{o.customer_name}</p>
                  <p className="text-xs text-[#5C5C5C]">{o.area}</p>
                </td>
                <td className="p-4 hidden lg:table-cell text-[#5C5C5C]">{o.items.length} item{o.items.length !== 1 && "s"}</td>
                <td className="p-4 font-bold">{formatUSD(o.subtotal_usd)}</td>
                <td className="p-4">
                  <select
                    value={o.status}
                    onChange={(e) => updateStatus(o.id, e.target.value)}
                    data-testid={`seller-order-status-${o.id}`}
                    className="bg-white border border-[#E2E2D9] rounded-full px-3 py-1.5 text-xs font-semibold focus:border-[#C84B31] focus:outline-none"
                  >
                    <option>Pending</option>
                    <option>In Progress</option>
                    <option>Delivered</option>
                  </select>
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan={5} className="p-8 text-center text-[#5C5C5C]">No orders yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RateTab() {
  const [rate, setRate] = useState(600);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/exchange-rate").then((r) => setRate(r.data?.rate || 600));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/exchange-rate", { rate: parseFloat(rate) });
      toast.success("Exchange rate saved");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-xl bg-white border border-[#E2E2D9] rounded-3xl p-8">
      <h2 className="font-display font-semibold text-2xl text-[#1A1A1A]">Exchange rate</h2>
      <p className="text-sm text-[#5C5C5C] mt-1">Set how SSP is calculated from USD on your products. Customers see both prices.</p>
      <div className="mt-6 flex items-end gap-3">
        <div className="flex-1">
          <label className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">1 USD =</label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              data-testid="exchange-rate-input"
              value={rate}
              onChange={(e) => setRate(e.target.value)}
              className="js-input flex-1"
            />
            <span className="font-display font-semibold text-[#1A1A1A]">SSP</span>
          </div>
        </div>
        <button onClick={save} disabled={saving} data-testid="save-rate-btn" className="bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-6 py-3 rounded-full">{saving ? "Saving..." : "Save rate"}</button>
      </div>
      <div className="mt-6 p-4 bg-[#F2EBE5] rounded-2xl text-sm">
        <p className="font-bold text-[#1A1A1A]">Preview</p>
        <p className="text-[#5C5C5C] mt-1">$10.00 → SSP {(10 * (parseFloat(rate) || 600)).toLocaleString()}</p>
        <p className="text-[#5C5C5C]">$100.00 → SSP {(100 * (parseFloat(rate) || 600)).toLocaleString()}</p>
      </div>
    </div>
  );
}

function SettingsTab() {
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({ name: user?.name || "", phone: user?.phone || "" });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });

  const saveProfile = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.put("/auth/profile", form);
      setUser(data);
      toast.success("Profile updated");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const changePw = async (e) => {
    e.preventDefault();
    try {
      await api.post("/auth/change-password", pw);
      setPw({ current_password: "", new_password: "" });
      toast.success("Password changed");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-4xl">
      <form onSubmit={saveProfile} className="bg-white border border-[#E2E2D9] rounded-3xl p-6 space-y-3">
        <h2 className="font-display font-semibold text-xl">Profile</h2>
        <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="settings-name-input" />
        <Input label="Phone" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} testId="settings-phone-input" />
        <button type="submit" data-testid="save-profile-btn" className="bg-[#1A1A1A] text-white font-semibold px-5 py-2.5 rounded-full">Save profile</button>
      </form>
      <form onSubmit={changePw} className="bg-white border border-[#E2E2D9] rounded-3xl p-6 space-y-3">
        <h2 className="font-display font-semibold text-xl">Change password</h2>
        <Input label="Current password" type="password" value={pw.current_password} onChange={(v) => setPw({ ...pw, current_password: v })} testId="current-pw-input" />
        <Input label="New password" type="password" value={pw.new_password} onChange={(v) => setPw({ ...pw, new_password: v })} testId="new-pw-input" />
        <button type="submit" data-testid="change-pw-btn" className="bg-[#C84B31] text-white font-semibold px-5 py-2.5 rounded-full">Update password</button>
      </form>
    </div>
  );
}

// Form helpers
function Input({ label, type = "text", value, onChange, required = false, testId, step }) {
  return (
    <label className="block">
      <span className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">{label}</span>
      <input type={type} step={step} value={value} required={required}
        onChange={(e) => onChange(e.target.value)} data-testid={testId}
        className="js-input" />
    </label>
  );
}
function Textarea({ label, value, onChange, testId }) {
  return (
    <label className="block">
      <span className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">{label}</span>
      <textarea rows={3} value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId} className="js-input" />
    </label>
  );
}
function Select({ label, value, onChange, options, testId }) {
  const opts = options.map((o) => typeof o === "string" ? { value: o, label: o } : o);
  return (
    <label className="block">
      <span className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId} className="js-input">
        {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}
function Modal({ children, onClose, title }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div className="bg-white rounded-t-3xl sm:rounded-3xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-semibold text-xl">{title}</h2>
          <button onClick={onClose} data-testid="close-modal" className="p-2 hover:bg-[#F2EBE5] rounded-full"><X className="w-4 h-4" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
