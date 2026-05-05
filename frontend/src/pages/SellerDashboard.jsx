import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatUSD, formatDetail } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Store, Package, ShoppingBag, DollarSign, Settings, Plus, X, Edit2, Trash2, CheckCircle2, Clock, XCircle, FileText, ShoppingCart, UtensilsCrossed, Warehouse } from "lucide-react";
import { toast } from "sonner";

const TABS = [
  { id: "shops", label: "My Shops", icon: Store },
  { id: "products", label: "Products", icon: Package },
  { id: "orders", label: "Orders", icon: ShoppingBag },
  { id: "invoices", label: "Invoices", icon: FileText },
  { id: "rate", label: "Exchange Rate", icon: DollarSign },
  { id: "settings", label: "Settings", icon: Settings },
];

const CATEGORIES = [
  "Groceries", "Clothing & Fashion", "Shoes & Bags", "Beauty & Cosmetics",
  "Electronics & Accessories", "Home Essentials", "Health & Pharmacy",
  "Building & Materials", "Automotive",
  "Wholesale Food Supply", "Wholesale Electronics", "Wholesale Clothing",
  "Restaurant Supplies", "Construction Materials", "General Bulk Goods",
];
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
          {tab === "invoices" && <InvoicesTab />}
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

const FOOD_SUBCATEGORIES = [
  "Fried Chicken", "Burgers", "Shawarma", "Fries", "Sandwiches", "Kisra & Stews",
  "Asida", "Goat Meat Dishes", "Fish Dishes", "Pizza & Pasta", "Rice Meals",
  "Drinks & Cafés", "Cakes & Desserts", "Grills & BBQ", "Asian Food", "Healthy Food",
];
const RESTAURANT_CATEGORIES = ["Fast Food", "Local Food", "Drinks", "Bakery"];
const RETAIL_CATEGORIES = [
  "Groceries", "Clothing & Fashion", "Shoes & Bags", "Beauty & Cosmetics",
  "Electronics & Accessories", "Home Essentials", "Health & Pharmacy",
  "Building & Materials", "Automotive",
];
const WHOLESALE_CATEGORIES = [
  "Wholesale Food Supply", "Wholesale Electronics", "Wholesale Clothing",
  "Restaurant Supplies", "Construction Materials", "General Bulk Goods",
];

const MODE_CONFIG = {
  marketplace: { label: "Marketplace", icon: ShoppingCart, color: "#C84B31", hint: "Normal retail product" },
  restaurant:  { label: "Restaurant",  icon: UtensilsCrossed, color: "#2D6A4F", hint: "Menu item with side options" },
  wholesale:   { label: "Wholesale",   icon: Warehouse, color: "#1A1A1A", hint: "Bulk pricing + minimum order qty" },
};

function ProductsTab() {
  const [shops, setShops] = useState([]);
  const [restaurants, setRestaurants] = useState([]);
  const [products, setProducts] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [rate, setRate] = useState(600);
  const [mode, setMode] = useState("marketplace");
  const [form, setForm] = useState(defaultForm());

  function defaultForm() {
    return {
      shop_id: "", restaurant_id: "",
      name: "", category: "", description: "", image_url: "",
      price_usd: 0, stock: 100,
      min_order_qty: 1, bulk_price_usd: "",
      pricing_tiers: [],
      food_category: "Fried Chicken",
      side_items: [],
    };
  }

  const loadAll = async () => {
    const [sRes, rRes, rateRes] = await Promise.all([
      api.get("/shops/mine"),
      api.get("/restaurants"),
      api.get("/exchange-rate"),
    ]);
    setShops(sRes.data);
    setRestaurants(rRes.data);
    setRate(rateRes.data?.rate || 600);

    const allProducts = [];
    for (const sh of sRes.data) {
      const r = await api.get(`/products?shop_id=${sh.id}`);
      allProducts.push(...r.data.map((p) => ({ ...p, shop_name: sh.name, shop_kind: sh.kind })));
    }
    setProducts(allProducts);

    const allMenu = [];
    for (const r of rRes.data.filter((x) => x.seller_id === sRes.data[0]?.seller_id || true)) {
      const m = await api.get(`/restaurants/${r.id}/menu`);
      allMenu.push(...m.data.map((mi) => ({ ...mi, restaurant_name: r.name })));
    }
    setMenuItems(allMenu);
  };
  useEffect(() => { loadAll(); }, []); // eslint-disable-line

  const retailShops = shops.filter((s) => s.kind !== "wholesale");
  const wholesaleShops = shops.filter((s) => s.kind === "wholesale");

  const openNew = (selectedMode) => {
    setMode(selectedMode);
    setEditing(null);
    const next = defaultForm();
    if (selectedMode === "marketplace") {
      next.shop_id = retailShops[0]?.id || "";
      next.category = retailShops[0]?.category || RETAIL_CATEGORIES[0];
    } else if (selectedMode === "wholesale") {
      next.shop_id = wholesaleShops[0]?.id || "";
      next.category = wholesaleShops[0]?.category || WHOLESALE_CATEGORIES[0];
    } else {
      next.restaurant_id = restaurants[0]?.id || "";
      next.food_category = FOOD_SUBCATEGORIES[0];
    }
    setForm(next);
    setShowForm(true);
  };

  const openEditProduct = (p) => {
    const isWholesale = p.shop_kind === "wholesale" || p.mode === "wholesale";
    setMode(isWholesale ? "wholesale" : "marketplace");
    setEditing({ kind: "product", ...p });
    setForm({
      ...defaultForm(),
      shop_id: p.shop_id, name: p.name, category: p.category,
      price_usd: p.price_usd, stock: p.stock,
      description: p.description || "", image_url: p.image_url || "",
      min_order_qty: p.min_order_qty || 1,
      bulk_price_usd: p.bulk_price_usd || "",
      pricing_tiers: p.pricing_tiers || [],
    });
    setShowForm(true);
  };

  const openEditMenu = (m) => {
    setMode("restaurant");
    setEditing({ kind: "menu", ...m });
    setForm({
      ...defaultForm(),
      restaurant_id: m.restaurant_id, name: m.name,
      price_usd: m.price_usd,
      description: m.description || "", image_url: m.image_url || "",
      food_category: m.food_category || FOOD_SUBCATEGORIES[0],
      side_items: m.side_items || [],
    });
    setShowForm(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (mode === "restaurant") {
        const payload = {
          restaurant_id: form.restaurant_id, name: form.name,
          price_usd: parseFloat(form.price_usd) || 0,
          image_url: form.image_url, description: form.description,
          food_category: form.food_category,
          side_items: (form.side_items || []).map((s) => ({ name: s.name, price_usd: parseFloat(s.price_usd) || 0 })),
        };
        if (editing?.kind === "menu") await api.put(`/menu-items/${editing.id}`, payload);
        else await api.post("/menu-items", payload);
        toast.success(editing ? "Menu item updated" : "Menu item added");
      } else {
        const payload = {
          shop_id: form.shop_id, name: form.name, category: form.category,
          price_usd: parseFloat(form.price_usd) || 0,
          stock: parseInt(form.stock) || 0,
          image_url: form.image_url, description: form.description,
          mode,
          min_order_qty: mode === "wholesale" ? (parseInt(form.min_order_qty) || 1) : 1,
          bulk_price_usd: mode === "wholesale" && form.bulk_price_usd !== "" ? parseFloat(form.bulk_price_usd) : null,
          pricing_tiers: mode === "wholesale"
            ? (form.pricing_tiers || []).filter((t) => t.min_qty && t.price_usd)
                .map((t) => ({ min_qty: parseInt(t.min_qty), price_usd: parseFloat(t.price_usd) }))
            : [],
        };
        if (editing?.kind === "product") await api.put(`/products/${editing.id}`, payload);
        else await api.post("/products", payload);
        toast.success(editing ? "Product updated" : "Product added");
      }
      setShowForm(false); setEditing(null);
      loadAll();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const onDeleteProduct = async (id) => {
    if (!window.confirm("Delete this product?")) return;
    await api.delete(`/products/${id}`);
    toast.success("Deleted"); loadAll();
  };
  const onDeleteMenu = async (id) => {
    if (!window.confirm("Delete this menu item?")) return;
    await api.delete(`/menu-items/${id}`);
    toast.success("Deleted"); loadAll();
  };

  const totalItems = products.length + menuItems.length;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <p className="text-sm text-[var(--js-text-secondary)]">{totalItems} item{totalItems !== 1 && "s"} · Exchange rate <span className="font-bold text-[var(--js-text)]">1 USD = {rate} SSP</span></p>
        <div className="flex flex-wrap gap-2">
          {Object.entries(MODE_CONFIG).map(([k, cfg]) => {
            const Icon = cfg.icon;
            const disabled = (k === "marketplace" && retailShops.length === 0) ||
                             (k === "wholesale" && wholesaleShops.length === 0) ||
                             (k === "restaurant" && restaurants.length === 0);
            return (
              <button
                key={k} onClick={() => openNew(k)} disabled={disabled}
                data-testid={`add-${k}-btn`}
                className="inline-flex items-center gap-2 text-white text-sm font-semibold px-4 py-2.5 rounded-full disabled:bg-[#A3A39E] disabled:cursor-not-allowed hover:opacity-90 transition"
                style={{ background: disabled ? "#A3A39E" : cfg.color }}
                title={disabled ? `No ${k} shop/restaurant — create one first` : `Add ${cfg.label} item`}
              >
                <Icon className="w-4 h-4" /> {cfg.label}
              </button>
            );
          })}
        </div>
      </div>

      {showForm && (
        <Modal onClose={() => { setShowForm(false); setEditing(null); }} title={editing ? `Edit ${mode} item` : `New ${MODE_CONFIG[mode].label.toLowerCase()} item`}>
          <ModeToggle mode={mode} setMode={(m) => { setMode(m); const next = defaultForm();
            if (m === "marketplace") { next.shop_id = retailShops[0]?.id || ""; next.category = retailShops[0]?.category || RETAIL_CATEGORIES[0]; }
            else if (m === "wholesale") { next.shop_id = wholesaleShops[0]?.id || ""; next.category = wholesaleShops[0]?.category || WHOLESALE_CATEGORIES[0]; }
            else { next.restaurant_id = restaurants[0]?.id || ""; next.food_category = FOOD_SUBCATEGORIES[0]; }
            setForm(next); setEditing(null); }} disabledEditing={!!editing} />

          <form onSubmit={submit} className="space-y-3 mt-4">
            {mode === "restaurant" ? (
              <>
                <Select label="Restaurant" value={form.restaurant_id} onChange={(v) => setForm({ ...form, restaurant_id: v })} options={restaurants.map((r) => ({ value: r.id, label: r.name }))} testId="product-restaurant-select" />
                <Input label="Food name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required testId="product-name-input" />
                <Select label="Food category" value={form.food_category} onChange={(v) => setForm({ ...form, food_category: v })} options={FOOD_SUBCATEGORIES} testId="food-category-select" />
                <Input label="Price (USD)" type="number" step="0.01" value={form.price_usd} onChange={(v) => setForm({ ...form, price_usd: v })} required testId="product-price-input" />
                <Input label="Image URL" value={form.image_url} onChange={(v) => setForm({ ...form, image_url: v })} testId="product-image-input" />
                <Textarea label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} testId="product-desc-input" />
                <SideItemsEditor sides={form.side_items} setSides={(s) => setForm({ ...form, side_items: s })} />
              </>
            ) : (
              <>
                <Select label="Shop" value={form.shop_id}
                  onChange={(v) => {
                    const sh = shops.find((x) => x.id === v);
                    setForm({ ...form, shop_id: v, category: sh?.category || form.category });
                  }}
                  options={(mode === "wholesale" ? wholesaleShops : retailShops).map((s) => ({ value: s.id, label: s.name }))}
                  testId="product-shop-select" />
                <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required testId="product-name-input" />
                <Select label="Category" value={form.category} onChange={(v) => setForm({ ...form, category: v })} options={mode === "wholesale" ? WHOLESALE_CATEGORIES : RETAIL_CATEGORIES} testId="product-cat-select" />
                <div className="grid grid-cols-2 gap-3">
                  <Input label="Price (USD)" type="number" step="0.01" value={form.price_usd} onChange={(v) => setForm({ ...form, price_usd: v })} required testId="product-price-input" />
                  <Input label="Stock" type="number" value={form.stock} onChange={(v) => setForm({ ...form, stock: v })} testId="product-stock-input" />
                </div>
                <p className="text-xs text-[var(--js-text-secondary)]">≈ <strong>SSP {(parseFloat(form.price_usd || 0) * rate).toLocaleString()}</strong> at current rate</p>
                <Input label="Image URL" value={form.image_url} onChange={(v) => setForm({ ...form, image_url: v })} testId="product-image-input" />
                <Textarea label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} testId="product-desc-input" />
                {mode === "wholesale" && (
                  <div className="bg-[var(--js-subtle)] rounded-2xl p-4 space-y-3">
                    <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Wholesale pricing</p>
                    <div className="grid grid-cols-2 gap-3">
                      <Input label="Minimum order qty" type="number" value={form.min_order_qty} onChange={(v) => setForm({ ...form, min_order_qty: v })} testId="min-order-qty-input" />
                      <Input label="Bulk price (USD, optional)" type="number" step="0.01" value={form.bulk_price_usd} onChange={(v) => setForm({ ...form, bulk_price_usd: v })} testId="bulk-price-input" />
                    </div>
                    <PricingTiersEditor tiers={form.pricing_tiers} setTiers={(t) => setForm({ ...form, pricing_tiers: t })} />
                  </div>
                )}
              </>
            )}
            <button type="submit" data-testid="product-submit-btn" className="w-full bg-[#1A1A1A] text-white font-semibold py-3 rounded-full">
              {editing ? "Save changes" : `Create ${MODE_CONFIG[mode].label.toLowerCase()} item`}
            </button>
          </form>
        </Modal>
      )}

      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--js-bg)] text-[var(--js-text-secondary)] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-4 font-bold">Item</th>
                <th className="text-left p-4 font-bold hidden md:table-cell">Shop / Restaurant</th>
                <th className="text-left p-4 font-bold">Mode</th>
                <th className="text-left p-4 font-bold">Price</th>
                <th className="text-left p-4 font-bold hidden sm:table-cell">Stock / MOQ</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => {
                const isWs = p.shop_kind === "wholesale" || p.mode === "wholesale";
                return (
                  <tr key={`p-${p.id}`} className="border-t border-[var(--js-border)]" data-testid={`product-row-${p.id}`}>
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <img src={p.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                        <div className="min-w-0">
                          <p className="font-semibold text-[var(--js-text)] truncate">{p.name}</p>
                          <p className="text-xs text-[var(--js-text-secondary)]">{p.category}</p>
                        </div>
                      </div>
                    </td>
                    <td className="p-4 text-[var(--js-text-secondary)] hidden md:table-cell">{p.shop_name}</td>
                    <td className="p-4">
                      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full" style={{ background: `${isWs ? "#1A1A1A" : "#C84B31"}15`, color: isWs ? "#1A1A1A" : "#C84B31" }}>
                        {isWs ? "WHOLESALE" : "MARKETPLACE"}
                      </span>
                    </td>
                    <td className="p-4">
                      <p className="font-bold text-[var(--js-text)]">{formatUSD(p.price_usd)}</p>
                      {isWs && p.bulk_price_usd && <p className="text-[10px] text-[#2D6A4F] font-bold">Bulk: {formatUSD(p.bulk_price_usd)}</p>}
                    </td>
                    <td className="p-4 hidden sm:table-cell text-xs">
                      <p>Stock: {p.stock}</p>
                      {isWs && <p className="text-[var(--js-text-secondary)]">MOQ: {p.min_order_qty}</p>}
                    </td>
                    <td className="p-4 text-right">
                      <div className="inline-flex gap-1">
                        <button onClick={() => openEditProduct(p)} data-testid={`edit-product-${p.id}`} className="p-2 hover:bg-[var(--js-subtle)] rounded-full"><Edit2 className="w-3.5 h-3.5" /></button>
                        <button onClick={() => onDeleteProduct(p.id)} data-testid={`delete-product-${p.id}`} className="p-2 hover:bg-[#D90429]/10 rounded-full"><Trash2 className="w-3.5 h-3.5 text-[#D90429]" /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {menuItems.map((m) => (
                <tr key={`m-${m.id}`} className="border-t border-[var(--js-border)]" data-testid={`menu-row-${m.id}`}>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <img src={m.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                      <div className="min-w-0">
                        <p className="font-semibold text-[var(--js-text)] truncate">{m.name}</p>
                        <p className="text-xs text-[var(--js-text-secondary)]">{m.food_category || "Menu item"}</p>
                      </div>
                    </div>
                  </td>
                  <td className="p-4 text-[var(--js-text-secondary)] hidden md:table-cell">{m.restaurant_name}</td>
                  <td className="p-4">
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-[#2D6A4F]/15 text-[#2D6A4F]">RESTAURANT</span>
                  </td>
                  <td className="p-4">
                    <p className="font-bold text-[var(--js-text)]">{formatUSD(m.price_usd)}</p>
                    {(m.side_items || []).length > 0 && <p className="text-[10px] text-[var(--js-text-secondary)]">+ {m.side_items.length} sides</p>}
                  </td>
                  <td className="p-4 hidden sm:table-cell text-xs">—</td>
                  <td className="p-4 text-right">
                    <div className="inline-flex gap-1">
                      <button onClick={() => openEditMenu(m)} data-testid={`edit-menu-${m.id}`} className="p-2 hover:bg-[var(--js-subtle)] rounded-full"><Edit2 className="w-3.5 h-3.5" /></button>
                      <button onClick={() => onDeleteMenu(m.id)} data-testid={`delete-menu-${m.id}`} className="p-2 hover:bg-[#D90429]/10 rounded-full"><Trash2 className="w-3.5 h-3.5 text-[#D90429]" /></button>
                    </div>
                  </td>
                </tr>
              ))}
              {totalItems === 0 && (
                <tr><td colSpan={6} className="p-8 text-center text-[var(--js-text-secondary)]">No products or menu items yet. Click a button above to add one.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ModeToggle({ mode, setMode, disabledEditing }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {Object.entries(MODE_CONFIG).map(([k, cfg]) => {
        const Icon = cfg.icon;
        const active = mode === k;
        return (
          <button
            type="button" key={k}
            disabled={disabledEditing}
            onClick={() => setMode(k)}
            data-testid={`mode-toggle-${k}`}
            className={`flex flex-col items-center gap-1 p-3 rounded-2xl border-2 transition-all ${
              active ? "text-white border-transparent" : "bg-white border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
            } ${disabledEditing ? "opacity-50 cursor-not-allowed" : ""}`}
            style={{ background: active ? cfg.color : undefined }}
          >
            <Icon className="w-5 h-5" />
            <span className="text-xs font-bold">{cfg.label}</span>
            <span className={`text-[10px] ${active ? "text-white/80" : "text-[var(--js-text-secondary)]"} text-center leading-tight`}>{cfg.hint}</span>
          </button>
        );
      })}
    </div>
  );
}

function SideItemsEditor({ sides, setSides }) {
  const [draft, setDraft] = useState({ name: "", price_usd: "" });
  const add = () => {
    if (!draft.name.trim()) return;
    setSides([...(sides || []), { name: draft.name.trim(), price_usd: parseFloat(draft.price_usd) || 0 }]);
    setDraft({ name: "", price_usd: "" });
  };
  const remove = (idx) => setSides(sides.filter((_, i) => i !== idx));
  return (
    <div className="bg-[var(--js-subtle)] rounded-2xl p-3 space-y-2">
      <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Side options</p>
      <div className="flex gap-2">
        <input placeholder="Side name (e.g., Fries)" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className="js-input flex-1 text-sm" data-testid="side-name-input" />
        <input placeholder="$" type="number" step="0.01" value={draft.price_usd} onChange={(e) => setDraft({ ...draft, price_usd: e.target.value })} className="js-input w-24 text-sm" data-testid="side-price-input" />
        <button type="button" onClick={add} data-testid="side-add-btn" className="bg-[#1A1A1A] text-white text-sm font-semibold px-3 rounded-xl">Add</button>
      </div>
      {(sides || []).length > 0 && (
        <ul className="space-y-1">
          {sides.map((s, i) => (
            <li key={i} className="flex items-center justify-between text-sm bg-white rounded-lg px-3 py-1.5">
              <span>{s.name} <span className="text-[var(--js-text-secondary)]">· {formatUSD(s.price_usd)}</span></span>
              <button type="button" onClick={() => remove(i)} data-testid={`side-remove-${i}`} className="text-[#D90429] text-xs font-bold">×</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PricingTiersEditor({ tiers, setTiers }) {
  const [draft, setDraft] = useState({ min_qty: "", price_usd: "" });
  const add = () => {
    const q = parseInt(draft.min_qty); const p = parseFloat(draft.price_usd);
    if (!q || !p) return;
    const next = [...(tiers || []), { min_qty: q, price_usd: p }].sort((a, b) => a.min_qty - b.min_qty);
    setTiers(next);
    setDraft({ min_qty: "", price_usd: "" });
  };
  const remove = (idx) => setTiers(tiers.filter((_, i) => i !== idx));
  return (
    <div>
      <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)] mb-2">Pricing tiers (optional)</p>
      <div className="flex gap-2">
        <input placeholder="Min qty" type="number" value={draft.min_qty} onChange={(e) => setDraft({ ...draft, min_qty: e.target.value })} className="js-input flex-1 text-sm" data-testid="tier-min-qty-input" />
        <input placeholder="Price $" type="number" step="0.01" value={draft.price_usd} onChange={(e) => setDraft({ ...draft, price_usd: e.target.value })} className="js-input w-28 text-sm" data-testid="tier-price-input" />
        <button type="button" onClick={add} data-testid="tier-add-btn" className="bg-[#1A1A1A] text-white text-sm font-semibold px-3 rounded-xl">Add tier</button>
      </div>
      {(tiers || []).length > 0 && (
        <ul className="mt-2 space-y-1">
          {tiers.map((t, i) => (
            <li key={i} className="flex items-center justify-between text-sm bg-white rounded-lg px-3 py-1.5">
              <span>{t.min_qty}+ units → <strong>{formatUSD(t.price_usd)}</strong> / unit</span>
              <button type="button" onClick={() => remove(i)} data-testid={`tier-remove-${i}`} className="text-[#D90429] text-xs font-bold">×</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function InvoicesTab() {
  const [invoices, setInvoices] = useState([]);
  const load = () => api.get("/seller/invoices").then((r) => setInvoices(r.data));
  useEffect(() => { load(); }, []);

  const totalSales = invoices.reduce((s, i) => s + (i.total_sales || 0), 0);
  const totalCommission = invoices.reduce((s, i) => s + (i.commission || 0), 0);
  const owed = invoices.filter((i) => i.status === "Unpaid").reduce((s, i) => s + (i.amount_owed || 0), 0);

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="Invoices" value={invoices.length} color="#1A1A1A" />
        <Stat label="Total Sales" value={formatUSD(totalSales)} color="#2D6A4F" />
        <Stat label="Commission" value={formatUSD(totalCommission)} color="#C84B31" />
        <Stat label="Amount Owed" value={formatUSD(owed)} color="#D90429" />
      </div>
      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--js-bg)] text-[var(--js-text-secondary)] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-4 font-bold">Shop</th>
                <th className="text-left p-4 font-bold hidden sm:table-cell">Week</th>
                <th className="text-left p-4 font-bold">Sales</th>
                <th className="text-left p-4 font-bold hidden md:table-cell">Commission</th>
                <th className="text-left p-4 font-bold">Amount Owed</th>
                <th className="text-left p-4 font-bold">Status</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-t border-[var(--js-border)]" data-testid={`seller-invoice-${inv.id}`}>
                  <td className="p-4 font-semibold">{inv.shop_name}</td>
                  <td className="p-4 text-[var(--js-text-secondary)] hidden sm:table-cell text-xs">{inv.week_label}</td>
                  <td className="p-4 font-bold">{formatUSD(inv.total_sales)}</td>
                  <td className="p-4 hidden md:table-cell text-[#C84B31] font-semibold">{formatUSD(inv.commission)}</td>
                  <td className="p-4 font-display font-bold">{formatUSD(inv.amount_owed)}</td>
                  <td className="p-4">
                    {inv.status === "Paid"
                      ? <span className="inline-flex items-center gap-1 bg-[#2D6A4F]/10 text-[#2D6A4F] text-xs font-bold px-2 py-1 rounded-full"><CheckCircle2 className="w-3 h-3" /> Paid</span>
                      : <span className="inline-flex items-center gap-1 bg-[#D90429]/10 text-[#D90429] text-xs font-bold px-2 py-1 rounded-full"><Clock className="w-3 h-3" /> Unpaid</span>}
                  </td>
                </tr>
              ))}
              {invoices.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-[var(--js-text-secondary)]">No invoices yet. They're auto-generated weekly from your orders.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="bg-white border border-[var(--js-border)] rounded-2xl p-4">
      <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--js-text-secondary)] font-bold">{label}</p>
      <p className="font-display font-bold text-2xl mt-1" style={{ color }}>{value}</p>
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
