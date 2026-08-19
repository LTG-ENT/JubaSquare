import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useCart } from "@/context/CartContext";
import { useTranslation } from "react-i18next";
import api, { formatUSD, formatPrice, formatDetail } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ImageUpload from "@/components/ImageUpload";
import AreaSelectField from "@/components/AreaSelectField";
import OrderChatButton from "@/components/OrderChatButton";
import SellerWalletTab from "@/components/SellerWalletTab";
import BulkImportModal from "@/components/BulkImportModal";
import SellerAnalyticsTab from "@/components/SellerAnalyticsTab";
import PasswordChangeForm from "@/components/PasswordChangeForm";
import SellerOnboardingCard from "@/components/SellerOnboardingCard";
import SellerFirstLoginWizard from "@/components/SellerFirstLoginWizard";
import SellerDashboardTour from "@/components/SellerDashboardTour";
import CategoryTreeSelect from "@/components/CategoryTreeSelect";
import AttributeFieldsEditor from "@/components/AttributeFieldsEditor";
import { Pagination } from "@/components/Pagination";
import { Store, Package, ShoppingBag, DollarSign, Settings, Plus, X, Edit2, Trash2, CheckCircle2, Clock, XCircle, FileText, ShoppingCart, UtensilsCrossed, Warehouse, Bell, AlertTriangle, ExternalLink, MessageCircle, Mail, Phone, ChefHat, Wallet, MapPin, Upload, TrendingUp, PackageCheck, GraduationCap, Printer, Sparkles } from "lucide-react";
import { useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";

const TABS = [
  { id: "shops", label: "My Shops", icon: Store },
  { id: "products", label: "Products", icon: Package },
  { id: "analytics", label: "Analytics", icon: TrendingUp },
  { id: "wallet", label: "Wallet & Active Orders", icon: Wallet },
  { id: "messages", label: "Messages", icon: MessageCircle },
  { id: "notifications", label: "Notifications", icon: Bell },
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

export default function SellerDashboard() {
  const { user } = useAuth();
  const { currency = "USD", exchangeRate = 1 } = useCart() || {}; // Get currency and exchange rate with defaults
  const { t: tr } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const initial = searchParams.get("tab") || "shops";
  const [tab, setTab] = useState(initial);
  const [lowStockCount, setLowStockCount] = useState(0);
  const [unreadMessages, setUnreadMessages] = useState(0);
  const [runTour, setRunTour] = useState(false);

  useEffect(() => {
    const t = searchParams.get("tab");
    if (t && t !== tab) setTab(t);
    // eslint-disable-next-line
  }, [searchParams]);

  // Pull unread message count for the badge
  useEffect(() => {
    if (!user?.id) return;
    let cancelled = false;
    api.get("/messages/seller/unread-count")
      .then((r) => { if (!cancelled) setUnreadMessages(r.data?.count || 0); })
      .catch(() => { if (!cancelled) setUnreadMessages(0); });
    return () => { cancelled = true; };
    // Refresh only when the user changes — refetching on every tab click would
    // be wasteful on a low-resource host.
  }, [user?.id]);

  // Compute low-stock products at dashboard level so the banner is visible from any tab
  const lowStockEnabled = user?.settings?.low_stock_alert !== false; // default ON
  const lowStockThreshold = parseInt(user?.settings?.low_stock_threshold ?? 5, 10) || 5;

  useEffect(() => {
    if (!user?.id) return;
    let cancelled = false;
    api
      .get(`/seller/low-stock-count?threshold=${lowStockThreshold}`)
      .then((r) => { if (!cancelled) setLowStockCount(r.data?.count || 0); })
      .catch(() => { if (!cancelled) setLowStockCount(0); });
    return () => { cancelled = true; };
    // Intentionally NOT depending on `tab` — this would otherwise refetch
    // products on every tab click. The count refreshes when the threshold
    // changes (settings) or when the user remounts the dashboard.
  }, [user?.id, lowStockThreshold]);

  const goToLowStock = () => {
    setSearchParams({ tab: "products", filter: "low-stock" }, { replace: false });
    setTab("products");
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F9F9F6]">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">{tr("dashboard")}</p>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <h1 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">{tr("manageBusiness")}</h1>
          <Link
            to="/seller/guide"
            data-testid="seller-header-guide-link"
            className="inline-flex items-center gap-1.5 rounded-full border border-[#E2E2D9] hover:border-[#C84B31] hover:text-[#C84B31] text-[#5C5C5C] text-xs font-semibold px-3 py-1.5 transition"
            aria-label="Open seller guide"
          >
            <GraduationCap className="w-3.5 h-3.5" />
            Seller Guide
          </Link>
        </div>

        {/* Onboarding progress card (auto-hides at 100%) */}
        <SellerOnboardingCard onStartTour={() => setRunTour(true)} />

        {/* First-login wizard modal (dismissable, persists on server) */}
        <SellerFirstLoginWizard />

        {/* Interactive dashboard tour */}
        <SellerDashboardTour run={runTour} onFinish={() => setRunTour(false)} />

        {/* Low-stock alert banner */}
        {lowStockEnabled && lowStockCount > 0 && (
          <div className="mt-6 rounded-2xl border border-[#E9C46A] bg-[#FFF7E0] p-4 flex flex-col sm:flex-row items-start sm:items-center gap-3" data-testid="low-stock-banner">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-[#E9C46A]/30 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5 text-[#9F6B00]" />
              </div>
              <div className="min-w-0">
                <p className="font-display font-bold text-sm text-[#1A1A1A]">
                  {lowStockCount} product{lowStockCount > 1 ? "s are" : " is"} low on stock
                </p>
                <p className="text-xs text-[#5C5C5C] mt-0.5">
                  Stock at or below your threshold ({lowStockThreshold}). Restock soon to avoid lost sales.
                </p>
              </div>
            </div>
            <button
              onClick={goToLowStock}
              data-testid="low-stock-banner-action"
              className="bg-[#1A1A1A] hover:bg-black text-white text-xs font-semibold px-4 py-2 rounded-full whitespace-nowrap"
            >
              View low-stock items
            </button>
          </div>
        )}

        <div className="mt-8 flex flex-wrap gap-2 border-b border-[#E2E2D9] overflow-x-auto">
          {TABS.map((t) => {
            const Icon = t.icon;
            const showLowStockBadge = t.id === "products" && lowStockEnabled && lowStockCount > 0;
            const showMsgBadge = t.id === "messages" && unreadMessages > 0;
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
                {showLowStockBadge && (
                  <span className="ml-1 inline-flex items-center justify-center min-w-[18px] h-[18px] text-[10px] font-bold bg-[#E9C46A] text-[#1A1A1A] rounded-full px-1.5">
                    {lowStockCount}
                  </span>
                )}
                {showMsgBadge && (
                  <span data-testid="seller-messages-badge" className="ml-1 inline-flex items-center justify-center min-w-[18px] h-[18px] text-[10px] font-bold bg-[#C84B31] text-white rounded-full px-1.5">
                    {unreadMessages}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="mt-8">
          {tab === "shops" && <ShopsTab currency={currency} exchangeRate={exchangeRate} />}
          {tab === "products" && <ProductsTab currency={currency} exchangeRate={exchangeRate} />}
          {tab === "analytics" && <SellerAnalyticsTab />}
          {tab === "wallet" && <SellerWalletTab />}
          {tab === "messages" && <MessagesTab onChange={(n) => setUnreadMessages(n)} />}
          {tab === "notifications" && <NotificationsTab />}
          {tab === "invoices" && <InvoicesTab currency={currency} exchangeRate={exchangeRate} />}
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

function ShopsTab({ currency, exchangeRate }) {
  const [shops, setShops] = useState([]);
  const [restaurants, setRestaurants] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const emptyForm = {
    name: "", type: "shop", description: "", area: "Munuki", image_url: "",
    // Delivery pricing removed - controlled by admin
  };
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const [s, r] = await Promise.all([api.get("/shops/mine?limit=200"), api.get("/restaurants/mine?limit=200")]);
    setShops(s.data);
    setRestaurants(r.data);
  };
  useEffect(() => { load(); }, []);

  const togglePublic = async (s, next) => {
    try {
      await api.patch(`/shops/${s.id}/visibility`, { is_public: next });
      setShops((prev) => prev.map((x) => (x.id === s.id ? { ...x, is_public: next } : x)));
      toast.success(next ? "Shop is now public" : "Shop hidden from marketplace");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to update visibility");
    }
  };

  const toggleOpen = async (r) => {
    try {
      const response = await api.put(`/restaurants/${r.id}/toggle-open`);
      const newState = response.data.is_open;
      setRestaurants((prev) => prev.map((x) => (x.id === r.id ? { ...x, is_open: newState } : x)));
      toast.success(newState ? "Restaurant is now open" : "Restaurant closed");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to update status");
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (form.type === "restaurant") {
        const payload = {
          name: form.name, 
          description: form.description, 
          area: form.area,
          image_url: form.image_url, 
          is_open: true,
          // Delivery pricing removed - controlled by admin
        };
        if (editing?._kind === "restaurant") {
          await api.put(`/restaurants/${editing.id}`, payload);
          toast.success("Restaurant updated");
        } else {
          await api.post("/restaurants", payload);
          toast.success("Restaurant created (pending verification)");
        }
      } else {
        const payload = {
          name: form.name,
          description: form.description,
          area: form.area,
          image_url: form.image_url,
          // Delivery pricing removed - controlled by admin
        };
        if (editing?._kind !== "restaurant" && editing) await api.put(`/shops/${editing.id}`, payload);
        else await api.post("/shops", payload);
        toast.success(editing ? "Shop updated" : "Shop created (pending verification)");
      }
      setShowForm(false); setEditing(null);
      setForm(emptyForm);
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const onEdit = (s, kind) => {
    setEditing({ ...s, _kind: kind });
    
    // Delivery pricing removed - controlled by admin
    setForm({
      name: s.name,
      type: kind,
      description: s.description || "",
      area: s.area,
      image_url: s.image_url,
      // Delivery pricing removed - controlled by admin
    });
    setShowForm(true);
  };

  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [shopProducts, setShopProducts] = useState([]);
  const [moveToShop, setMoveToShop] = useState("");

  const onDelete = async (s, kind) => {
    // Fetch products/menu items first
    try {
      if (kind === "restaurant") {
        const response = await api.get(`/restaurants/${s.id}/menu`);
        const menuItems = response.data || [];
        setShopProducts(menuItems);
        setDeleteConfirm({ ...s, _kind: kind });
        setMoveToShop("");
      } else {
        const response = await api.get(`/products?shop_id=${s.id}&limit=200`);
        const products = response.data || [];
        setShopProducts(products);
        setDeleteConfirm({ ...s, _kind: kind });
        setMoveToShop("");
      }
    } catch (err) {
      toast.error(`Failed to load ${kind === "restaurant" ? "menu items" : "products"}`);
    }
  };

  const confirmDelete = async () => {
    if (!deleteConfirm) return;
    
    try {
      const isRestaurant = deleteConfirm._kind === "restaurant";
      
      if (moveToShop && shopProducts.length > 0) {
        // Move products/menu items to another shop/restaurant
        if (isRestaurant) {
          await Promise.all(
            shopProducts.map((item) => 
              api.put(`/menu-items/${item.id}`, { ...item, restaurant_id: moveToShop })
            )
          );
        } else {
          await Promise.all(
            shopProducts.map((p) => 
              api.put(`/products/${p.id}`, { ...p, shop_id: moveToShop })
            )
          );
        }
        toast.success(`${shopProducts.length} ${isRestaurant ? "menu item(s)" : "product(s)"} moved successfully`);
      }
      
      // Delete the shop/restaurant
      if (isRestaurant) {
        await api.delete(`/restaurants/${deleteConfirm.id}`);
        toast.success("Restaurant deleted successfully");
      } else {
        await api.delete(`/shops/${deleteConfirm.id}`);
        toast.success("Shop deleted successfully");
      }
      
      setDeleteConfirm(null);
      setShopProducts([]);
      setMoveToShop("");
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to delete");
    }
  };

  const combined = [
    ...shops.map((s) => ({ ...s, _kind: "shop" })),
    ...restaurants.map((r) => ({ ...r, _kind: "restaurant" })),
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-[var(--js-text-secondary)]">{combined.length} business{combined.length !== 1 && "es"} ({shops.length} shops · {restaurants.length} restaurants)</p>
        <button
          onClick={() => { setShowForm(true); setEditing(null); setForm(emptyForm); }}
          data-testid="add-shop-btn"
          className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-4 py-2.5 rounded-full"
        >
          <Plus className="w-4 h-4" /> Add Business
        </button>
      </div>

      {showForm && (
        <Modal onClose={() => { setShowForm(false); setEditing(null); }} title={editing ? `Edit ${editing._kind}` : "New business"}>
          <form onSubmit={submit} noValidate className="space-y-3">
            <div>
              <span className="text-xs text-[var(--js-text-secondary)] font-semibold block mb-1.5">What are you opening?</span>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: "shop", label: "🛍️ Shop", hint: "Sells products" },
                  { id: "restaurant", label: "🍔 Restaurant", hint: "Sells menu items" },
                ].map((t) => (
                  <button type="button" key={t.id}
                    onClick={() => setForm({ ...form, type: t.id })}
                    disabled={!!editing}
                    data-testid={`shop-type-${t.id}`}
                    className={`p-3 rounded-2xl border-2 transition text-left ${
                      form.type === t.id ? "border-[#C84B31] bg-[#C84B31]/5" : "border-[var(--js-border)] bg-white hover:border-[var(--js-text)]"
                    } ${editing ? "opacity-60 cursor-not-allowed" : ""}`}
                  >
                    <p className="font-display font-semibold text-sm text-[var(--js-text)]">{t.label}</p>
                    <p className="text-xs text-[var(--js-text-secondary)]">{t.hint}</p>
                  </button>
                ))}
              </div>
            </div>
            <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required testId="shop-name-input" />
            <label className="block">
              <span className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">Area</span>
              <AreaSelectField value={form.area} onChange={(v) => setForm({ ...form, area: v })} testId="shop-area-select" />
            </label>

            <ImageUpload label="Shop photo" value={form.image_url} onChange={(v) => setForm({ ...form, image_url: v })} testId="shop-image-upload" />
            <Textarea label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} testId="shop-desc-input" />

            <DeliveryEditor form={form} setForm={setForm} />

            <button type="submit" data-testid="shop-submit-btn" className="w-full bg-[#1A1A1A] text-white font-semibold py-3 rounded-full">{editing ? "Save changes" : `Create ${form.type}`}</button>
          </form>
        </Modal>
      )}

      {deleteConfirm && (
        <Modal 
          onClose={() => { setDeleteConfirm(null); setShopProducts([]); setMoveToShop(""); }} 
          title={`Delete ${deleteConfirm.name}?`}
        >
          <div className="space-y-4">
            <div className="bg-[#FFF7E0] border border-[#E9C46A] rounded-2xl p-4">
              <p className="text-sm text-[#7A5C12] font-semibold">
                ⚠️ This {deleteConfirm._kind === "restaurant" ? "restaurant" : "shop"} has {shopProducts.length} {deleteConfirm._kind === "restaurant" ? "menu item(s)" : "product(s)"}
              </p>
            </div>

            {shopProducts.length > 0 && (
              <>
                <div className="max-h-60 overflow-y-auto space-y-2">
                  <p className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">
                    {deleteConfirm._kind === "restaurant" ? "Menu items in this restaurant:" : "Products in this shop:"}
                  </p>
                  {shopProducts.map((p) => (
                    <div key={p.id} className="flex items-center gap-3 p-2 bg-[var(--js-subtle)] rounded-xl border border-[var(--js-border)]">
                      <img src={p.image_url} alt={p.name} className="w-12 h-12 object-cover rounded-lg" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-[var(--js-text)] truncate">{p.name}</p>
                        <p className="text-xs text-[var(--js-text-secondary)]">
                          {deleteConfirm._kind === "restaurant" ? p.food_category || p.category : p.category}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="space-y-2">
                  <label className="block">
                    <span className="text-xs text-[var(--js-text-secondary)] font-semibold block mb-1.5">
                      What do you want to do with these {deleteConfirm._kind === "restaurant" ? "menu items" : "products"}?
                    </span>
                    <select
                      value={moveToShop}
                      onChange={(e) => setMoveToShop(e.target.value)}
                      className="w-full px-3 py-2.5 bg-white border border-[var(--js-border)] rounded-xl text-sm text-[var(--js-text)] focus:outline-none focus:border-[#C84B31]"
                      data-testid="move-items-select"
                    >
                      <option value="">Delete all {deleteConfirm._kind === "restaurant" ? "menu items" : "products"}</option>
                      {deleteConfirm._kind === "restaurant" 
                        ? restaurants.filter(r => r.id !== deleteConfirm.id).map((r) => (
                            <option key={r.id} value={r.id}>Move to: {r.name}</option>
                          ))
                        : shops.filter(s => s.id !== deleteConfirm.id && !s.is_deleted).map((s) => (
                            <option key={s.id} value={s.id}>Move to: {s.name}</option>
                          ))
                      }
                    </select>
                  </label>
                  {moveToShop ? (
                    <p className="text-xs text-[#2D6A4F] bg-[#2D6A4F]/10 p-2 rounded-lg">
                      ✓ {deleteConfirm._kind === "restaurant" ? "Menu items" : "Products"} will be moved to the selected {deleteConfirm._kind === "restaurant" ? "restaurant" : "shop"}
                    </p>
                  ) : (
                    <p className="text-xs text-[#D90429] bg-[#D90429]/10 p-2 rounded-lg">
                      ⚠️ All {deleteConfirm._kind === "restaurant" ? "menu items" : "products"} will be deactivated (can be restored later)
                    </p>
                  )}
                </div>
              </>
            )}

            {shopProducts.length === 0 && (
              <p className="text-sm text-[var(--js-text-secondary)] text-center py-4">
                This {deleteConfirm._kind === "restaurant" ? "restaurant" : "shop"} has no {deleteConfirm._kind === "restaurant" ? "menu items" : "products"}.
              </p>
            )}

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => { setDeleteConfirm(null); setShopProducts([]); setMoveToShop(""); }}
                className="flex-1 bg-[var(--js-subtle)] text-[var(--js-text)] font-semibold py-2.5 rounded-full hover:bg-[var(--js-border)]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                data-testid="confirm-delete-business"
                className="flex-1 bg-[#D90429] hover:bg-[#A83A23] text-white font-semibold py-2.5 rounded-full"
              >
                {moveToShop 
                  ? `Move & Delete ${deleteConfirm._kind === "restaurant" ? "Restaurant" : "Shop"}` 
                  : `Delete ${deleteConfirm._kind === "restaurant" ? "Restaurant" : "Shop"}`
                }
              </button>
            </div>
          </div>
        </Modal>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {combined.map((s) => (
          <div key={`${s._kind}-${s.id}`} data-testid={`my-shop-${s.id}`} className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
            <div className="aspect-[16/9] bg-[var(--js-subtle)] overflow-hidden relative">
              <img src={s.image_url} alt={s.name} className="w-full h-full object-cover" />
              <div className="absolute top-3 right-3"><VerificationBadge status={s.verification} /></div>
              <span className="absolute top-3 left-3 text-[10px] font-bold px-2 py-1 rounded-full" style={{ background: s._kind === "restaurant" ? "#2D6A4F" : "#C84B31", color: "white" }}>
                {s._kind === "restaurant" ? "🍔 RESTAURANT" : "🛍️ SHOP"}
              </span>
              {s._kind !== "restaurant" && s.is_deleted && (
                <span data-testid={`shop-deleted-badge-${s.id}`} className="absolute bottom-3 left-3 text-[10px] font-bold px-2 py-1 rounded-full bg-[#D90429] text-white inline-flex items-center gap-1">
                  ● DELETED
                </span>
              )}
              {s._kind !== "restaurant" && !s.is_deleted && s.is_public === false && (
                <span data-testid={`shop-hidden-badge-${s.id}`} className="absolute bottom-3 left-3 text-[10px] font-bold px-2 py-1 rounded-full bg-[#1A1A1A] text-white inline-flex items-center gap-1">
                  ● HIDDEN
                </span>
              )}
            </div>
            <div className="p-4">
              <p className="text-[10px] uppercase tracking-wider text-[var(--js-text-secondary)] font-bold">{s.area}</p>
              <h3 className="font-display font-semibold text-lg text-[var(--js-text)] mt-0.5">{s.name}</h3>
              <p className="text-sm text-[var(--js-text-secondary)] mt-1 line-clamp-2">{s.description}</p>
              {s._kind === "restaurant" && (
                <div className="mt-3 flex items-center justify-between gap-2 bg-[var(--js-subtle)] border border-[var(--js-border)] rounded-2xl px-3 py-2">
                  <div className="min-w-0">
                    <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Status</p>
                    <p className="text-xs text-[var(--js-text)] truncate">
                      {s.is_open ? "Open — accepting orders" : "Closed — not accepting orders"}
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={s.is_open !== false}
                    onClick={() => toggleOpen(s)}
                    data-testid={`toggle-restaurant-open-${s.id}`}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition shrink-0 ${
                      s.is_open !== false ? "bg-[#2D6A4F]" : "bg-[#A3A39E]"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                        s.is_open !== false ? "translate-x-6" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>
              )}
              {s._kind !== "restaurant" && (
                <div className="mt-3 flex items-center justify-between gap-2 bg-[var(--js-subtle)] border border-[var(--js-border)] rounded-2xl px-3 py-2">
                  <div className="min-w-0">
                    <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">{s.is_deleted ? "Status" : "Public visibility"}</p>
                    <p className="text-xs text-[var(--js-text)] truncate">
                      {s.is_deleted
                        ? "Deleted — products deactivated. Edit shop to restore."
                        : s.is_public === false
                          ? "Hidden — not listed in marketplace"
                          : "Live — visible to customers"}
                    </p>
                  </div>
                  {!s.is_deleted && (
                    <button
                      type="button"
                      role="switch"
                      aria-checked={s.is_public !== false}
                      onClick={() => togglePublic(s, s.is_public === false)}
                      data-testid={`toggle-shop-public-${s.id}`}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition shrink-0 ${
                        s.is_public !== false ? "bg-[#2D6A4F]" : "bg-[#A3A39E]"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                          s.is_public !== false ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  )}
                </div>
              )}
              <div className="mt-3 flex gap-2">
                <button onClick={() => onEdit(s, s._kind)} data-testid={`edit-shop-${s.id}`} className="flex-1 bg-[var(--js-subtle)] text-[var(--js-text)] text-xs font-semibold py-2 rounded-full inline-flex items-center justify-center gap-1"><Edit2 className="w-3 h-3" /> Quick edit</button>
                <button onClick={() => onDelete(s, s._kind)} data-testid={`delete-shop-${s.id}`} className="flex-1 bg-[#D90429]/10 text-[#D90429] text-xs font-semibold py-2 rounded-full inline-flex items-center justify-center gap-1"><Trash2 className="w-3 h-3" /> Delete</button>
              </div>
              {s._kind === "restaurant" && (
                <div className="mt-2 space-y-2">
                  <Link
                    to={`/kitchen/${s.id}`}
                    data-testid={`kitchen-dashboard-${s.id}`}
                    className="w-full bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-bold py-3 rounded-full inline-flex items-center justify-center gap-2"
                  >
                    <ChefHat className="w-4 h-4" /> Open Kitchen Dashboard
                  </Link>
                  <Link
                    to={`/seller/restaurant/${s.id}/edit`}
                    data-testid={`edit-restaurant-page-${s.id}`}
                    className="w-full bg-[#1A1A1A] text-white text-xs font-bold py-2 rounded-full inline-flex items-center justify-center gap-1 hover:bg-[#C84B31]"
                  >
                    <Edit2 className="w-3 h-3" /> Edit Restaurant Page &amp; Delivery
                  </Link>
                </div>
              )}
              {s._kind !== "restaurant" && (
                <div className="mt-2 flex gap-2">
                  <Link
                    to={`/seller/shop/${s.id}/edit`}
                    data-testid={`edit-shop-page-${s.id}`}
                    className="flex-1 bg-[#1A1A1A] text-white text-xs font-bold py-2 rounded-full inline-flex items-center justify-center gap-1 hover:bg-[#C84B31]"
                  >
                    <Edit2 className="w-3 h-3" /> Edit Shop Page
                  </Link>
                  <Link
                    to={`/shop/${s.id}`}
                    target="_blank"
                    data-testid={`view-shop-page-${s.id}`}
                    className="flex-1 bg-white border border-[var(--js-border)] text-[var(--js-text)] text-xs font-bold py-2 rounded-full inline-flex items-center justify-center gap-1 hover:border-[#1A1A1A]"
                  >
                    <ExternalLink className="w-3 h-3" /> View public
                  </Link>
                </div>
              )}
            </div>
          </div>
        ))}
        {combined.length === 0 && <p className="text-sm text-[var(--js-text-secondary)] col-span-full">No businesses yet. Click "Add Business".</p>}
      </div>
    </div>
  );
}

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

function ProductsTab({ currency, exchangeRate }) {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [shops, setShops] = useState([]);
  const [restaurants, setRestaurants] = useState([]);
  const [products, setProducts] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [rate, setRate] = useState(600);
  const [mode, setMode] = useState("marketplace");
  const [form, setForm] = useState(defaultForm());
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [showBulkStock, setShowBulkStock] = useState(false);
  const [restaurantCategoriesMap, setRestaurantCategoriesMap] = useState({});
  const [retailCategoriesMap, setRetailCategoriesMap] = useState({});
  const [wholesaleCategoriesMap, setWholesaleCategoriesMap] = useState({});

  // Filter / search state
  const initialFilter = searchParams.get("filter");
  const [stockFilter, setStockFilter] = useState(
    initialFilter === "out-of-stock" ? "out" : initialFilter === "low-stock" ? "low" : "all"
  );
  const [shopFilter, setShopFilter] = useState("all"); // "all" | "s:<id>" | "r:<id>"
  const [searchQ, setSearchQ] = useState("");
  // Iter 34 — "Add product details" nudge: session-scoped dismiss
  const [attrsNudgeDismissed, setAttrsNudgeDismissed] = useState(
    () => sessionStorage.getItem("seller_attrs_nudge_dismissed") === "1"
  );
  // Iter 35 — server-side pagination (50 items/page)
  const PAGE_SIZE = 50;
  const [productsPage, setProductsPage] = useState(1);
  const [productsTotal, setProductsTotal] = useState(0);
  const [menuPage, setMenuPage] = useState(1);
  const [menuTotal, setMenuTotal] = useState(0);
  const [outCount, setOutCount] = useState(0);
  const [lowCount, setLowCount] = useState(0);

  const lowStockThreshold = parseInt(user?.settings?.low_stock_threshold ?? 5, 10) || 5;
  const stockBucket = (stock) => {
    const s = Number(stock ?? 0);
    if (s <= 0) return "out";
    if (s <= lowStockThreshold) return "low";
    return "ok";
  };

  // Sync URL ?filter=low-stock / out-of-stock with stockFilter
  useEffect(() => {
    const f = searchParams.get("filter");
    const next = f === "out-of-stock" ? "out" : f === "low-stock" ? "low" : "all";
    if (next !== stockFilter) setStockFilter(next);
    // eslint-disable-next-line
  }, [searchParams]);

  const setStockFilterAndUrl = (val) => {
    setStockFilter(val);
    const sp = new URLSearchParams(searchParams);
    sp.set("tab", "products");
    if (val === "low") sp.set("filter", "low-stock");
    else if (val === "out") sp.set("filter", "out-of-stock");
    else sp.delete("filter");
    setSearchParams(sp, { replace: true });
  };

  function defaultForm() {
    return {
      shop_id: "", restaurant_id: "",
      name: "", 
      category_id: "",  // PRIMARY: UUID (required)
      category: "",     // DEPRECATED: for display only
      description: "", image_url: "",
      price_usd: 0, stock: 100,
      min_order_qty: "", bulk_price_usd: "",
      pricing_tiers: [],
      product_section_id: "",
      category_id_menu: "",  // PRIMARY: UUID for menu items (required)
      food_category: "",     // DEPRECATED: for display only
      side_items: [],
      prep_time_minutes: "",
      sides_required: false,
      sides_min_choices: 1,
      sides_max_choices: null,
      menu_section_id: "",
      promo: { active: false, type: "percent", value: 0, starts_at: "", ends_at: "" },
      attributes: {},  // Iter 33 — dynamic attribute values
    };
  }

  const loadAll = async () => {
    const [sRes, rRes, rateRes] = await Promise.all([
      api.get("/shops/mine?limit=200"),
      api.get("/restaurants/mine?limit=200"),
      api.get(user?.id ? `/exchange-rate?seller_id=${user.id}` : "/exchange-rate"),
    ]);
    setShops(sRes.data);
    setRestaurants(rRes.data);
    setRate(rateRes.data?.rate || 600);

    // Iter 35 — server-side pagination; products + menu items are fetched
    // by loadPage() (triggered by the filter/page useEffect below).

    // Fetch all category groups with sub-categories from database
    // Returns: { parentId: { id, name, children: [{id, name}, ...] }, ... }
    const fetchCategoriesForGroup = async (group) => {
      try {
        const categoriesRes = await api.get(`/categories/tree?group=${group}`);
        const tree = categoriesRes.data || [];
        
        // Build map of parent category id -> {id, name, children: [{id, name}]}
        const catMap = {};
        
        tree.forEach(parent => {
          catMap[parent.id] = {
            id: parent.id,
            name: parent.name,
            children: (parent.children || []).map(child => ({
              id: child.id,
              name: child.name
            }))
          };
        });
        
        return catMap;
      } catch (err) {
        console.error(`Failed to load ${group} categories:`, err);
        return {};
      }
    };

    // Fetch all category groups in parallel
    const [restaurantCats, retailCats, wholesaleCats] = await Promise.all([
      fetchCategoriesForGroup("restaurant"),
      fetchCategoriesForGroup("retail"),
      fetchCategoriesForGroup("wholesale"),
    ]);

    setRestaurantCategoriesMap(restaurantCats);
    setRetailCategoriesMap(retailCats);
    setWholesaleCategoriesMap(wholesaleCats);
  };
  useEffect(() => { loadAll(); }, [user?.id]); // eslint-disable-line

  // Iter 35 — paginated fetch. Re-runs when filters / page change.
  // Fetches at most PAGE_SIZE products AND PAGE_SIZE menu items — so the DOM
  // stays lightweight even for sellers with thousands of items.
  const loadPage = async () => {
    const shopId = shopFilter.startsWith("s:") ? shopFilter.slice(2) : "";
    const restaurantId = shopFilter.startsWith("r:") ? shopFilter.slice(2) : "";
    const params = new URLSearchParams();
    params.set("page", String(productsPage));
    params.set("page_size", String(PAGE_SIZE));
    if (shopId) params.set("shop_id", shopId);
    if (searchQ.trim()) params.set("q", searchQ.trim());
    if (stockFilter !== "all") params.set("stock", stockFilter);
    params.set("low_threshold", String(lowStockThreshold));

    // If the seller has narrowed to a specific restaurant, skip fetching products.
    const productsPromise = shopFilter.startsWith("r:")
      ? Promise.resolve({ data: { items: [], total: 0 } })
      : api.get(`/seller/products/paged?${params.toString()}`);

    // Menu items don't have stock — hide when stock filter is set.
    const menuParams = new URLSearchParams();
    menuParams.set("page", String(menuPage));
    menuParams.set("page_size", String(PAGE_SIZE));
    if (restaurantId) menuParams.set("restaurant_id", restaurantId);
    if (searchQ.trim()) menuParams.set("q", searchQ.trim());
    const menuPromise = (stockFilter !== "all" || shopFilter.startsWith("s:"))
      ? Promise.resolve({ data: { items: [], total: 0 } })
      : api.get(`/seller/menu-items/paged?${menuParams.toString()}`);

    // Pill counts (out / low) — fetched separately so they reflect *totals*
    // across all pages regardless of the current stock filter.
    const pillsBase = new URLSearchParams();
    pillsBase.set("page", "1");
    pillsBase.set("page_size", "1");
    if (shopId) pillsBase.set("shop_id", shopId);
    if (searchQ.trim()) pillsBase.set("q", searchQ.trim());
    pillsBase.set("low_threshold", String(lowStockThreshold));
    const outParams = new URLSearchParams(pillsBase);
    outParams.set("stock", "out");
    const lowParams = new URLSearchParams(pillsBase);
    lowParams.set("stock", "low");

    try {
      const [pRes, mRes, oRes, lRes] = await Promise.all([
        productsPromise,
        menuPromise,
        shopFilter.startsWith("r:")
          ? Promise.resolve({ data: { total: 0 } })
          : api.get(`/seller/products/paged?${outParams.toString()}`),
        shopFilter.startsWith("r:")
          ? Promise.resolve({ data: { total: 0 } })
          : api.get(`/seller/products/paged?${lowParams.toString()}`),
      ]);
      setProducts(pRes.data.items || []);
      setProductsTotal(pRes.data.total || 0);
      setMenuItems(mRes.data.items || []);
      setMenuTotal(mRes.data.total || 0);
      setOutCount(oRes.data.total || 0);
      setLowCount(lRes.data.total || 0);
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to load products");
    }
  };
  useEffect(() => {
    if (!user?.id) return;
    loadPage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, productsPage, menuPage, shopFilter, stockFilter, searchQ, lowStockThreshold]);
  // Reset page → 1 when any filter changes (avoids landing on empty page 5
  // after narrowing the result set).
  useEffect(() => {
    setProductsPage(1);
    setMenuPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopFilter, stockFilter, searchQ]);

  // Auto-initialize category_id when form is open but category_id is empty
  useEffect(() => {
    if (showForm && !editing) {
      // For products (marketplace/wholesale)
      if (mode !== "restaurant" && !form.category_id) {
        const isWholesale = mode === "wholesale";
        const categoriesMap = isWholesale ? wholesaleCategoriesMap : retailCategoriesMap;
        const firstParentId = Object.keys(categoriesMap)[0];
        const firstParent = categoriesMap[firstParentId];
        
        if (firstParent) {
          const firstChild = firstParent.children[0];
          const newCatId = firstChild ? firstChild.id : firstParent.id;
          const newCatName = firstChild ? `${firstParent.name} > ${firstChild.name}` : firstParent.name;
          setForm(prev => ({ ...prev, category_id: newCatId, category: newCatName }));
        }
      }
      // For menu items (restaurant)
      else if (mode === "restaurant" && !form.category_id_menu) {
        const firstParentId = Object.keys(restaurantCategoriesMap)[0];
        const firstParent = restaurantCategoriesMap[firstParentId];
        
        if (firstParent) {
          setForm(prev => ({ 
            ...prev, 
            category_id_menu: firstParent.id,
            food_category: firstParent.name
          }));
        }
      }
    }
  }, [showForm, mode, editing, form.category_id, form.category_id_menu, retailCategoriesMap, wholesaleCategoriesMap, restaurantCategoriesMap]);

  const retailShops = shops.filter((s) => s.kind !== "wholesale");
  const wholesaleShops = shops.filter((s) => s.kind === "wholesale");

  const openNew = () => {
    setEditing(null);
    const next = defaultForm();
    
    // Set default shop or restaurant
    if (shops.length > 0) {
      next.shop_id = shops[0].id;
      setMode("marketplace");
    } else if (restaurants.length > 0) {
      next.restaurant_id = restaurants[0].id;
      setMode("restaurant");
    }
    
    setForm(next);
    setShowForm(true);
    // Note: category_id will be auto-set by useEffect when categories are loaded
  };

  const openEditProduct = (p) => {
    const isWholesale = !!p.is_wholesale || p.mode === "wholesale";
    setMode(isWholesale ? "wholesale" : "marketplace");
    setEditing({ kind: "product", ...p });
    setForm({
      ...defaultForm(),
      shop_id: p.shop_id, name: p.name, 
      category_id: p.category_id || "",  // PRIMARY
      category: p.category || "",         // DEPRECATED (for display)
      price_usd: p.price_usd, stock: p.stock,
      description: p.description || "", image_url: p.image_url || "",
      min_order_qty: p.min_order_qty && p.min_order_qty > 1 ? p.min_order_qty : "",
      bulk_price_usd: p.bulk_price_usd || "",
      pricing_tiers: p.pricing_tiers || [],
      product_section_id: p.product_section_id || "",
      promo: p.promo || { active: false, type: "percent", value: 0, starts_at: "", ends_at: "" },
      attributes: p.attributes || {},
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
      category_id_menu: m.category_id || "",  // PRIMARY
      food_category: m.food_category || "",   // DEPRECATED (for display)
      side_items: m.side_items || [],
      prep_time_minutes: m.prep_time_minutes ?? "",
      sides_required: !!m.sides_required,
      sides_min_choices: m.sides_min_choices ?? 1,
      sides_max_choices: m.sides_max_choices ?? null,
      menu_section_id: m.menu_section_id || "",
      promo: m.promo || { active: false, type: "percent", value: 0, starts_at: "", ends_at: "" },
      attributes: m.attributes || {},
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
          category_id: form.category_id_menu,  // PRIMARY (required)
          food_category: form.food_category,   // DEPRECATED (backward compat)
          side_items: (form.side_items || []).map((s) => ({ name: s.name, price_usd: parseFloat(s.price_usd) || 0 })),
          prep_time_minutes: form.prep_time_minutes === "" ? null : (parseInt(form.prep_time_minutes, 10) || null),
          sides_required: !!form.sides_required,
          sides_min_choices: form.sides_required
            ? (Number.isFinite(parseInt(form.sides_min_choices, 10)) ? Math.max(1, parseInt(form.sides_min_choices, 10)) : 1)
            : null,
          sides_max_choices: form.sides_required && form.sides_max_choices !== null && form.sides_max_choices !== "" && Number.isFinite(parseInt(form.sides_max_choices, 10))
            ? parseInt(form.sides_max_choices, 10)
            : null,
          menu_section_id: form.menu_section_id || null,
          promo: form.promo && form.promo.active ? {
            active: true,
            type: form.promo.type || "percent",
            value: parseFloat(form.promo.value) || 0,
            bogo_min_qty: parseInt(form.promo.bogo_min_qty || 2, 10) || 2,
            starts_at: form.promo.starts_at || null,
            ends_at: form.promo.ends_at || null,
          } : { active: false, type: "percent", value: 0, bogo_min_qty: 2, starts_at: null, ends_at: null },
          attributes: form.attributes || {},
        };
        if (editing?.kind === "menu") await api.put(`/menu-items/${editing.id}`, payload);
        else await api.post("/menu-items", payload);
        toast.success(editing ? "Menu item updated" : "Menu item added");
      } else {
        const payload = {
          shop_id: form.shop_id, name: form.name, 
          category_id: form.category_id,  // PRIMARY (required)
          category: form.category,        // DEPRECATED (backward compat)
          price_usd: parseFloat(form.price_usd) || 0,
          stock: parseInt(form.stock) || 0,
          image_url: form.image_url, description: form.description,
          mode,
          is_wholesale: mode === "wholesale",
          min_order_qty: mode === "wholesale" ? (parseInt(form.min_order_qty) || 1) : 1,
          bulk_price_usd: mode === "wholesale" && form.bulk_price_usd !== "" ? parseFloat(form.bulk_price_usd) : null,
          pricing_tiers: mode === "wholesale"
            ? (form.pricing_tiers || []).filter((t) => t.min_qty && t.price_usd)
                .map((t) => ({ min_qty: parseInt(t.min_qty), price_usd: parseFloat(t.price_usd) }))
            : [],
          product_section_id: form.product_section_id || null,
          promo: form.promo && form.promo.active ? {
            active: true,
            type: form.promo.type || "percent",
            value: parseFloat(form.promo.value) || 0,
            bogo_min_qty: parseInt(form.promo.bogo_min_qty || 2, 10) || 2,
            starts_at: form.promo.starts_at || null,
            ends_at: form.promo.ends_at || null,
          } : { active: false, type: "percent", value: 0, bogo_min_qty: 2, starts_at: null, ends_at: null },
          attributes: form.attributes || {},
        };
        if (editing?.kind === "product") await api.put(`/products/${editing.id}`, payload);
        else await api.post("/products", payload);
        toast.success(editing ? "Product updated" : "Product added");
      }
      setShowForm(false); setEditing(null);
      loadAll(); loadPage();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const onDeleteProduct = async (id) => {
    if (!window.confirm("Delete this product?")) return;
    await api.delete(`/products/${id}`);
    toast.success("Deleted"); loadAll(); loadPage();
  };
  const onDeleteMenu = async (id) => {
    if (!window.confirm("Delete this menu item?")) return;
    await api.delete(`/menu-items/${id}`);
    toast.success("Deleted"); loadAll(); loadPage();
  };

  const totalItems = productsTotal + menuTotal;

  // Iter 35 — server did the filtering; the rendered page is already the
  // filtered slice. `filteredCount` reflects the current-page cardinality
  // for the "N of M items" indicator.
  const filteredProducts = products;
  const filteredMenuItems = menuItems;
  const filteredCount = filteredProducts.length + filteredMenuItems.length;

  // Iter 34 — "Add product details" nudge banner.
  // Simple heuristic: items whose `attributes` dict is empty/missing.
  // Filling attributes powers customer-side filters and improves discoverability.
  const isAttrsEmpty = (item) => {
    const a = item?.attributes;
    return !a || typeof a !== "object" || Object.keys(a).length === 0;
  };
  const productsMissingAttrs = products.filter(isAttrsEmpty);
  const menuItemsMissingAttrs = menuItems.filter(isAttrsEmpty);
  const missingAttrsCount = productsMissingAttrs.length + menuItemsMissingAttrs.length;
  const openFirstMissingAttrs = () => {
    if (productsMissingAttrs.length > 0) {
      openEditProduct(productsMissingAttrs[0]);
      return;
    }
    if (menuItemsMissingAttrs.length > 0) {
      openEditMenu(menuItemsMissingAttrs[0]);
    }
  };
  const dismissAttrsNudge = () => {
    sessionStorage.setItem("seller_attrs_nudge_dismissed", "1");
    setAttrsNudgeDismissed(true);
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <p className="text-sm text-[var(--js-text-secondary)]">{totalItems} item{totalItems !== 1 && "s"} · Exchange rate <span className="font-bold text-[var(--js-text)]">1 USD = {rate} SSP</span></p>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setShowBulkStock(true)}
            disabled={shops.length === 0}
            data-testid="bulk-stock-btn"
            className="inline-flex items-center gap-2 bg-[#2A9D8F] hover:bg-[#218075] disabled:bg-[#A3A39E] disabled:cursor-not-allowed text-white text-sm font-semibold px-4 py-2.5 rounded-full"
            title="Bulk update stock and prices"
          >
            <PackageCheck className="w-4 h-4" /> Bulk Stock Update
          </button>
          <button
            onClick={() => setShowBulkImport(true)}
            disabled={shops.length === 0}
            data-testid="bulk-import-btn"
            className="inline-flex items-center gap-2 bg-[#0E1A2B] hover:bg-[#1E3A5F] disabled:bg-[#A3A39E] disabled:cursor-not-allowed text-white text-sm font-semibold px-4 py-2.5 rounded-full"
          >
            <Upload className="w-4 h-4" /> Bulk Import
          </button>
          {/* Iter 31 — printable low-stock / out-of-stock report */}
          <a
            href="/seller/low-stock?autoprint=0"
            target="_blank"
            rel="noopener noreferrer"
            data-testid="low-stock-report-btn"
            className="inline-flex items-center gap-2 bg-[#8B6B00] hover:bg-[#6A4F00] text-white text-sm font-semibold px-4 py-2.5 rounded-full"
            title="Open printable low-stock / out-of-stock report"
          >
            <Printer className="w-4 h-4" /> Low-Stock Report
          </a>
          <button
            onClick={openNew}
            disabled={shops.length === 0 && restaurants.length === 0}
            data-testid="add-item-btn"
            className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] disabled:cursor-not-allowed text-white text-sm font-semibold px-4 py-2.5 rounded-full"
          >
            <Plus className="w-4 h-4" /> Add Item
          </button>
        </div>
      </div>

      {/* Iter 34 — "Add product details" nudge banner (missing attributes) */}
      {!attrsNudgeDismissed && missingAttrsCount > 0 && (
        <div
          className="mb-4 rounded-2xl border border-[#7C3AED]/30 bg-gradient-to-r from-[#F5F0FF] to-[#EFE7FF] p-4 flex flex-col sm:flex-row items-start sm:items-center gap-3"
          data-testid="attrs-nudge-banner"
        >
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-[#7C3AED]/15 flex items-center justify-center shrink-0">
              <Sparkles className="w-5 h-5 text-[#7C3AED]" />
            </div>
            <div className="min-w-0">
              <p className="font-display font-bold text-sm text-[#1A1A1A]">
                Add product details to {missingAttrsCount} item{missingAttrsCount > 1 ? "s" : ""}
              </p>
              <p className="text-xs text-[#5C5C5C] mt-0.5">
                Filling in attributes (size, color, material, etc.) helps buyers filter and find your items faster.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={openFirstMissingAttrs}
              data-testid="attrs-nudge-action"
              className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-xs font-semibold px-4 py-2 rounded-full whitespace-nowrap inline-flex items-center gap-1.5"
            >
              <Edit2 className="w-3.5 h-3.5" /> Add details
            </button>
            <button
              onClick={dismissAttrsNudge}
              data-testid="attrs-nudge-dismiss"
              aria-label="Dismiss"
              className="p-2 rounded-full hover:bg-white/60 text-[#5C5C5C]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Filter / search bar */}
      <div className="mb-4 bg-white border border-[var(--js-border)] rounded-2xl p-3 flex flex-wrap items-center gap-2 shadow-sm">
        <div className="relative flex-1 min-w-[200px]">
          <input
            type="text"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Search products by name or category..."
            data-testid="seller-products-search"
            className="w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-full pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
          />
          <svg className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
        </div>
        <select
          value={shopFilter}
          onChange={(e) => setShopFilter(e.target.value)}
          data-testid="seller-products-shop-filter"
          className="bg-[var(--js-bg)] border border-[var(--js-border)] rounded-full px-4 py-2 text-sm font-semibold focus:outline-none focus:border-[#C84B31] min-w-[180px]"
        >
          <option value="all">🏬 All shops &amp; restaurants</option>
          {shops.length > 0 && (
            <optgroup label="🛍️ Shops">
              {shops.map((s) => <option key={s.id} value={`s:${s.id}`}>{s.name}</option>)}
            </optgroup>
          )}
          {restaurants.length > 0 && (
            <optgroup label="🍔 Restaurants">
              {restaurants.map((r) => <option key={r.id} value={`r:${r.id}`}>{r.name}</option>)}
            </optgroup>
          )}
        </select>
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            type="button"
            onClick={() => setStockFilterAndUrl("all")}
            data-testid="stock-filter-all"
            className={`text-xs font-bold px-3 py-2 rounded-full border transition ${stockFilter === "all" ? "bg-[#1A1A1A] text-white border-[#1A1A1A]" : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#1A1A1A]"}`}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setStockFilterAndUrl("low")}
            data-testid="stock-filter-low"
            className={`text-xs font-bold px-3 py-2 rounded-full border transition inline-flex items-center gap-1.5 ${stockFilter === "low" ? "bg-[#E9C46A] text-[#1A1A1A] border-[#E9C46A]" : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#E9C46A]"}`}
          >
            <AlertTriangle className="w-3.5 h-3.5" /> Low stock
            <span className="bg-white/70 text-[#9F6B00] rounded-full px-1.5 py-0.5 text-[10px]">{lowCount}</span>
          </button>
          <button
            type="button"
            onClick={() => setStockFilterAndUrl("out")}
            data-testid="stock-filter-out"
            className={`text-xs font-bold px-3 py-2 rounded-full border transition inline-flex items-center gap-1.5 ${stockFilter === "out" ? "bg-[#D90429] text-white border-[#D90429]" : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#D90429]"}`}
          >
            <XCircle className="w-3.5 h-3.5" /> Out
            <span className={`${stockFilter === "out" ? "bg-white/30 text-white" : "bg-[#D90429]/10 text-[#D90429]"} rounded-full px-1.5 py-0.5 text-[10px]`}>{outCount}</span>
          </button>
        </div>
        <p className="ml-auto text-xs text-[var(--js-text-secondary)]" data-testid="seller-products-count">
          {filteredCount} of {totalItems} item{totalItems !== 1 && "s"}
        </p>
      </div>

      {showForm && (
        <Modal onClose={() => { setShowForm(false); setEditing(null); }} title={editing ? "Edit item" : "New item"}>
          <form onSubmit={submit} noValidate className="space-y-3">
            {/* Business selector — unified shops + restaurants */}
            <div>
              <label className="text-xs text-[var(--js-text-secondary)] font-semibold block mb-1.5">Business</label>
              <select
                value={mode === "restaurant" ? `r:${form.restaurant_id}` : `s:${form.shop_id}`}
                onChange={(e) => {
                  const [kind, id] = e.target.value.split(":");
                  if (kind === "r") {
                    setMode("restaurant");
                    // Default food_category to the first admin-defined restaurant category.
                    // No hardcoded fallback — if admin has none, leave blank.
                    const firstFoodCat = Object.keys(restaurantCategoriesMap)[0] || "";
                    setForm({ ...form, restaurant_id: id, food_category: firstFoodCat });
                  } else {
                    // Shop selected - set retail category with sub-category
                    const shop = shops.find(s => s.id === id);
                    const isWholesale = shop?.kind === "wholesale";
                    setMode(isWholesale ? "wholesale" : "marketplace");
                    
                    const categoriesMap = isWholesale ? wholesaleCategoriesMap : retailCategoriesMap;
                    const firstParent = Object.keys(categoriesMap)[0] || (isWholesale ? "Wholesale Food Supply" : "Groceries");
                    const firstSubcat = categoriesMap[firstParent]?.[0] || "";
                    
                    setForm({ 
                      ...form, 
                      shop_id: id, 
                      category: firstSubcat ? `${firstParent} > ${firstSubcat}` : firstParent 
                    });
                  }
                }}
                disabled={!!editing}
                data-testid="product-business-select"
                className="js-input"
              >
                {shops.length > 0 && <optgroup label="🛍️ Shops">
                  {shops.map((s) => <option key={s.id} value={`s:${s.id}`}>{s.name}</option>)}
                </optgroup>}
                {restaurants.length > 0 && <optgroup label="🍔 Restaurants">
                  {restaurants.map((r) => <option key={r.id} value={`r:${r.id}`}>{r.name}</option>)}
                </optgroup>}
              </select>
            </div>

            {mode === "restaurant" ? (
              <>
                <Input label="Food name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required testId="product-name-input" />
                {/* Iter 33 — hierarchical restaurant category selector */}
                <CategoryTreeSelect
                  group="restaurant"
                  value={form.category_id_menu}
                  onChange={(id, pathName) => setForm({ ...form, category_id_menu: id, food_category: pathName, attributes: id === form.category_id_menu ? form.attributes : {} })}
                  testIdPrefix="food-category"
                />
                {/* Iter 33 — dynamic category attributes */}
                {form.category_id_menu && (
                  <AttributeFieldsEditor
                    categoryId={form.category_id_menu}
                    values={form.attributes}
                    onChange={(v) => setForm({ ...form, attributes: v })}
                  />
                )}
                <Input label="Price (USD)" type="number" step="0.01" value={form.price_usd} onChange={(v) => setForm({ ...form, price_usd: v })} required testId="product-price-input" />
                <Input label="Prep time (minutes)" type="number" min="1" step="1" value={form.prep_time_minutes} onChange={(v) => setForm({ ...form, prep_time_minutes: v })} testId="menu-prep-time-input" placeholder="e.g. 15" />
                <ImageUpload label="Food photo" value={form.image_url} onChange={(v) => setForm({ ...form, image_url: v })} testId="product-image-upload" />
                <Textarea label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} testId="product-desc-input" />
                <SideItemsEditor sides={form.side_items} setSides={(s) => setForm({ ...form, side_items: s })} currency={currency} exchangeRate={rate} />
                <RequiredSidesEditor
                  form={form}
                  setForm={setForm}
                  hasSides={(form.side_items || []).length > 0}
                />
                <SectionPicker
                  form={form}
                  setForm={setForm}
                  fieldKey="menu_section_id"
                  sections={(restaurants.find((r) => r.id === form.restaurant_id) || {}).menu_sections || []}
                  label="Menu section"
                  hint="Where should this item appear on the customer menu?"
                  emptyHint="Add sections in your Restaurant page settings first."
                />
                <PromoEditor form={form} setForm={setForm} />
              </>
            ) : (
              <>
                <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required testId="product-name-input" />

                {/* Iter 33 — hierarchical category selector (unlimited depth) */}
                <CategoryTreeSelect
                  group={mode === "wholesale" ? "wholesale" : "retail"}
                  value={form.category_id}
                  onChange={(id, pathName) => setForm({ ...form, category_id: id, category: pathName, attributes: id === form.category_id ? form.attributes : {} })}
                  testIdPrefix="product-cat"
                />
                {/* Iter 33 — dynamic category attributes */}
                {form.category_id && (
                  <AttributeFieldsEditor
                    categoryId={form.category_id}
                    values={form.attributes}
                    onChange={(v) => setForm({ ...form, attributes: v })}
                  />
                )}

                <div className="grid grid-cols-2 gap-3">
                  <Input label="Price (USD)" type="number" step="0.01" value={form.price_usd} onChange={(v) => setForm({ ...form, price_usd: v })} required testId="product-price-input" />
                  <Input label="Stock" type="number" value={form.stock} onChange={(v) => setForm({ ...form, stock: v })} testId="product-stock-input" />
                </div>
                <p className="text-xs text-[var(--js-text-secondary)]">≈ <strong>SSP {(parseFloat(form.price_usd || 0) * rate).toLocaleString()}</strong> at current rate</p>
                <ImageUpload label="Product photo" value={form.image_url} onChange={(v) => setForm({ ...form, image_url: v })} testId="product-image-upload" />
                <Textarea label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} testId="product-desc-input" />

                {/* Wholesale toggle only for shops */}
                <label className="flex items-start gap-3 bg-[var(--js-subtle)] rounded-2xl p-4 cursor-pointer">
                  <span className="js-switch shrink-0 mt-0.5">
                    <input
                      type="checkbox"
                      checked={mode === "wholesale"}
                      onChange={(e) => setMode(e.target.checked ? "wholesale" : "marketplace")}
                      data-testid="wholesale-toggle"
                    />
                    <span className="slider" />
                  </span>
                  <div>
                    <p className="font-semibold text-sm text-[var(--js-text)]">📦 Enable wholesale pricing</p>
                    <p className="text-xs text-[var(--js-text-secondary)] mt-0.5">Mark this product as wholesale. MOQ, bulk price, and tiers are all optional.</p>
                  </div>
                </label>

                {mode === "wholesale" && (
                  <div className="bg-[var(--js-subtle)] rounded-2xl p-4 space-y-3">
                    <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Wholesale pricing</p>
                    <div className="grid grid-cols-2 gap-3">
                      <Input label="Minimum order qty (optional)" type="number" value={form.min_order_qty} onChange={(v) => setForm({ ...form, min_order_qty: v })} testId="min-order-qty-input" />
                      <Input label="Bulk price (USD, optional)" type="number" step="0.01" value={form.bulk_price_usd} onChange={(v) => setForm({ ...form, bulk_price_usd: v })} testId="bulk-price-input" />
                    </div>
                    <PricingTiersEditor tiers={form.pricing_tiers} setTiers={(t) => setForm({ ...form, pricing_tiers: t })} currency={currency} exchangeRate={rate} />
                  </div>
                )}
                <SectionPicker
                  form={form}
                  setForm={setForm}
                  fieldKey="product_section_id"
                  sections={(shops.find((sh) => sh.id === form.shop_id) || {}).product_sections || []}
                  label="Shop section"
                  hint="Where should this product appear in your shop?"
                  emptyHint="Add sections in your Shop page settings first."
                />
                <PromoEditor form={form} setForm={setForm} />
              </>
            )}

            <button type="submit" data-testid="product-submit-btn" className="w-full bg-[#1A1A1A] text-white font-semibold py-3 rounded-full">
              {editing ? "Save changes" : "Create item"}
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
              {filteredProducts.map((p) => {
                const isWs = !!p.is_wholesale || p.mode === "wholesale";
                const bucket = stockBucket(p.stock);
                return (
                  <tr key={`p-${p.id}`} className={`border-t border-[var(--js-border)] ${bucket === "out" ? "bg-[#D90429]/5" : bucket === "low" ? "bg-[#FFF7E0]" : ""}`} data-testid={`product-row-${p.id}`}>
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <img src={p.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="font-semibold text-[var(--js-text)] truncate">{p.name}</p>
                            {bucket === "out" && (
                              <span data-testid={`out-badge-${p.id}`} className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#D90429] text-white">
                                <XCircle className="w-3 h-3" /> OUT OF STOCK
                              </span>
                            )}
                            {bucket === "low" && (
                              <span data-testid={`low-badge-${p.id}`} className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#E9C46A] text-[#1A1A1A]">
                                <AlertTriangle className="w-3 h-3" /> LOW STOCK
                              </span>
                            )}
                          </div>
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
                      <p className="font-bold text-[var(--js-text)]">{formatPrice(p.price_usd, p.exchange_rate_ssp || rate, currency)}</p>
                      {isWs && p.bulk_price_usd && <p className="text-[10px] text-[#2D6A4F] font-bold">Bulk: {formatPrice(p.bulk_price_usd, p.exchange_rate_ssp || rate, currency)}</p>}
                    </td>
                    <td className="p-4 hidden sm:table-cell text-xs">
                      <p className={bucket === "out" ? "text-[#D90429] font-bold" : bucket === "low" ? "text-[#9F6B00] font-bold" : ""}>Stock: {p.stock}</p>
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
              {filteredMenuItems.map((m) => (
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
                    <p className="font-bold text-[var(--js-text)]">{formatPrice(m.price_usd, m.exchange_rate_ssp || rate, currency)}</p>
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
              {filteredCount === 0 && (
                <tr><td colSpan={6} className="p-8 text-center text-[var(--js-text-secondary)]" data-testid="seller-products-empty">
                  {totalItems === 0
                    ? "No products or menu items yet. Click a button above to add one."
                    : (searchQ.trim() || shopFilter !== "all" || stockFilter !== "all")
                      ? `No items match the current filters${searchQ.trim() ? ` for "${searchQ.trim()}"` : ""}.`
                      : "No products or menu items yet."}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        {/* Iter 35 — pagination controls (separate for products & menu items) */}
        {productsTotal > PAGE_SIZE && (
          <Pagination
            page={productsPage}
            total={productsTotal}
            pageSize={PAGE_SIZE}
            onChange={setProductsPage}
            testIdPrefix="products-pagination"
          />
        )}
        {menuTotal > PAGE_SIZE && (
          <div className="mt-2">
            <p className="text-xs text-[var(--js-text-secondary)] mb-1">Menu items</p>
            <Pagination
              page={menuPage}
              total={menuTotal}
              pageSize={PAGE_SIZE}
              onChange={setMenuPage}
              testIdPrefix="menu-pagination"
            />
          </div>
        )}
      </div>
      {showBulkImport && (
        <BulkImportModal
          mode="import"
          shops={shops}
          onClose={() => setShowBulkImport(false)}
          onSuccess={() => { setShowBulkImport(false); loadAll(); loadPage(); }}
        />
      )}
      {showBulkStock && (
        <BulkImportModal
          mode="stock-update"
          shops={shops}
          onClose={() => setShowBulkStock(false)}
          onSuccess={() => { setShowBulkStock(false); loadAll(); loadPage(); }}
        />
      )}
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

function SideItemsEditor({ sides, setSides, currency, exchangeRate }) {
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
      <div className="grid grid-cols-[1fr_88px_auto] gap-2">
        <input placeholder="Side name (e.g., Fries)" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className="js-input text-sm min-w-0" data-testid="side-name-input" />
        <input placeholder="USD" type="number" step="0.01" value={draft.price_usd} onChange={(e) => setDraft({ ...draft, price_usd: e.target.value })} className="js-input text-sm min-w-0" data-testid="side-price-input" />
        <button type="button" onClick={add} data-testid="side-add-btn" className="bg-[#1A1A1A] text-white text-sm font-semibold px-4 rounded-xl">Add</button>
      </div>
      {(sides || []).length > 0 && (
        <ul className="space-y-1">
          {sides.map((s, i) => (
            <li key={i} className="flex items-center justify-between text-sm bg-white rounded-lg px-3 py-1.5">
              <span>{s.name} <span className="text-[var(--js-text-secondary)]">· {formatPrice(s.price_usd, exchangeRate, currency)}</span></span>
              <button type="button" onClick={() => remove(i)} data-testid={`side-remove-${i}`} className="text-[#D90429] text-xs font-bold">×</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PricingTiersEditor({ tiers, setTiers, currency, exchangeRate }) {
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
      <div className="grid grid-cols-[1fr_1fr_auto] gap-2 items-end">
        <label className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)] flex flex-col gap-1">
          Min qty
          <input
            placeholder="e.g. 10"
            type="number"
            min="1"
            value={draft.min_qty}
            onChange={(e) => setDraft({ ...draft, min_qty: e.target.value })}
            className="js-input text-sm w-full"
            data-testid="tier-min-qty-input"
          />
        </label>
        <label className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)] flex flex-col gap-1">
          Price (USD)
          <input
            placeholder="e.g. 8.50"
            type="number"
            step="0.01"
            min="0"
            value={draft.price_usd}
            onChange={(e) => setDraft({ ...draft, price_usd: e.target.value })}
            className="js-input text-sm w-full"
            data-testid="tier-price-input"
          />
        </label>
        <button
          type="button"
          onClick={add}
          data-testid="tier-add-btn"
          className="bg-[#1A1A1A] text-white text-sm font-semibold px-4 py-2 rounded-xl whitespace-nowrap h-[42px]"
        >
          Add tier
        </button>
      </div>
      {(tiers || []).length > 0 && (
        <ul className="mt-2 space-y-1">
          {tiers.map((t, i) => (
            <li key={i} className="flex items-center justify-between text-sm bg-white rounded-lg px-3 py-1.5">
              <span>{t.min_qty}+ units → <strong>{formatPrice(t.price_usd, exchangeRate, currency)}</strong> / unit</span>
              <button type="button" onClick={() => remove(i)} data-testid={`tier-remove-${i}`} className="text-[#D90429] text-xs font-bold">×</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function InvoicesTab({ currency, exchangeRate }) {
  const [kind, setKind] = useState("shop");
  return (
    <div>
      <div className="inline-flex items-center bg-[var(--js-subtle)] rounded-full p-1 mb-6" data-testid="seller-invoice-kind-toggle">
        <button
          onClick={() => setKind("shop")}
          data-testid="seller-invoice-kind-shop"
          className={`px-5 py-2 text-sm font-semibold rounded-full transition ${
            kind === "shop" ? "bg-white shadow text-[var(--js-text)]" : "text-[var(--js-text-secondary)]"
          }`}
        >
          Shop invoices
        </button>
        <button
          onClick={() => setKind("restaurant")}
          data-testid="seller-invoice-kind-restaurant"
          className={`px-5 py-2 text-sm font-semibold rounded-full transition ${
            kind === "restaurant" ? "bg-white shadow text-[var(--js-text)]" : "text-[var(--js-text-secondary)]"
          }`}
        >
          Restaurant invoices
        </button>
      </div>
      {kind === "shop" ? <SellerShopInvoices /> : <SellerRestaurantInvoices />}
    </div>
  );
}

function SellerShopInvoices() {
  const { currency = "USD", exchangeRate = 1 } = useCart() || {};
  const [invoices, setInvoices] = useState([]);
  // Iter 35 — server-side pagination
  const PAGE_SIZE = 50;
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState({ total_sales: 0, total_commission: 0, amount_owed: 0 });
  const load = () =>
    api.get(`/seller/invoices/paged?page=${page}&page_size=${PAGE_SIZE}`).then((r) => {
      setInvoices(r.data.items || []);
      setTotal(r.data.total || 0);
      setStats(r.data.stats || { total_sales: 0, total_commission: 0, amount_owed: 0 });
    });
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [page]);

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="Invoices" value={total} color="#1A1A1A" />
        <Stat label="Total Sales" value={formatPrice(stats.total_sales, exchangeRate, currency)} color="#2D6A4F" />
        <Stat label="Commission" value={formatPrice(stats.total_commission, exchangeRate, currency)} color="#C84B31" />
        <Stat label="Amount Owed" value={formatPrice(stats.amount_owed, exchangeRate, currency)} color="#D90429" />
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
                  <td className="p-4 font-bold">{formatPrice(inv.total_sales, exchangeRate, currency)}</td>
                  <td className="p-4 hidden md:table-cell text-[#C84B31] font-semibold">{formatPrice(inv.commission, exchangeRate, currency)}</td>
                  <td className="p-4 font-display font-bold">{formatPrice(inv.amount_owed, exchangeRate, currency)}</td>
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
      <Pagination
        page={page}
        total={total}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        testIdPrefix="shop-invoices-pagination"
      />
    </div>
  );
}

function SellerRestaurantInvoices() {
  const { currency = "USD", exchangeRate = 1 } = useCart() || {};
  const [invoices, setInvoices] = useState([]);
  // Iter 35 — server-side pagination
  const PAGE_SIZE = 50;
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState({ total_sales: 0, total_commission: 0, amount_owed: 0 });
  useEffect(() => {
    api
      .get(`/seller/restaurant-invoices/paged?page=${page}&page_size=${PAGE_SIZE}`)
      .then((r) => {
        setInvoices(r.data.items || []);
        setTotal(r.data.total || 0);
        setStats(r.data.stats || { total_sales: 0, total_commission: 0, amount_owed: 0 });
      })
      .catch(() => {
        setInvoices([]);
        setTotal(0);
      });
  }, [page]);

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="Restaurant Invoices" value={total} color="#1A1A1A" />
        <Stat label="Food Sales" value={formatPrice(stats.total_sales, exchangeRate, currency)} color="#2D6A4F" />
        <Stat label="Commission" value={formatPrice(stats.total_commission, exchangeRate, currency)} color="#C84B31" />
        <Stat label="Amount Owed" value={formatPrice(stats.amount_owed, exchangeRate, currency)} color="#D90429" />
      </div>
      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--js-bg)] text-[var(--js-text-secondary)] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-4 font-bold">Restaurant</th>
                <th className="text-left p-4 font-bold hidden sm:table-cell">Week</th>
                <th className="text-left p-4 font-bold">Sales</th>
                <th className="text-left p-4 font-bold hidden md:table-cell">Commission</th>
                <th className="text-left p-4 font-bold">Amount Owed</th>
                <th className="text-left p-4 font-bold">Status</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-t border-[var(--js-border)]" data-testid={`seller-restaurant-invoice-${inv.id}`}>
                  <td className="p-4 font-semibold">{inv.restaurant_name}</td>
                  <td className="p-4 text-[var(--js-text-secondary)] hidden sm:table-cell text-xs">{inv.week_label}</td>
                  <td className="p-4 font-bold">{formatPrice(inv.total_sales, exchangeRate, currency)}</td>
                  <td className="p-4 hidden md:table-cell text-[#C84B31] font-semibold">{formatPrice(inv.commission, exchangeRate, currency)}</td>
                  <td className="p-4 font-display font-bold">{formatPrice(inv.amount_owed, exchangeRate, currency)}</td>
                  <td className="p-4">
                    {inv.status === "Paid"
                      ? <span className="inline-flex items-center gap-1 bg-[#2D6A4F]/10 text-[#2D6A4F] text-xs font-bold px-2 py-1 rounded-full"><CheckCircle2 className="w-3 h-3" /> Paid</span>
                      : <span className="inline-flex items-center gap-1 bg-[#D90429]/10 text-[#D90429] text-xs font-bold px-2 py-1 rounded-full"><Clock className="w-3 h-3" /> Unpaid</span>}
                  </td>
                </tr>
              ))}
              {invoices.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-[var(--js-text-secondary)]">No restaurant invoices yet. They auto-generate when restaurant orders are marked completed.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <Pagination
        page={page}
        total={total}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        testIdPrefix="restaurant-invoices-pagination"
      />
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

function DeliveryEditor({ form, setForm }) {
  // Delivery pricing is now controlled by admin via delivery pricing rules
  return (
    <div className="border-2 border-[#E9C46A] rounded-2xl p-4 bg-[#E9C46A]/10">
      <div className="flex items-start gap-3">
        <div className="bg-[#E9C46A] rounded-full p-2 flex-shrink-0">
          <MapPin className="w-5 h-5 text-[#1A1A1A]" />
        </div>
        <div>
          <p className="font-bold text-sm text-[var(--js-text)] mb-1">Delivery Pricing — Hybrid Model</p>
          <p className="text-xs text-[var(--js-text-secondary)] leading-relaxed">
            By default, sellers manage their own delivery via the shop editor (free / fixed fee / per-area). If JubaSquare enables platform-wide admin delivery, admin-defined rules take over. A per-shop override can lock any shop to seller-mode or admin-mode regardless of the platform toggle.
          </p>
        </div>
      </div>
    </div>
  );
}

function OrdersTab() {
  const { user } = useAuth();
  // Read exchange rate + currency from cart context to prevent
  // ReferenceError when this component is rendered.
  const { currency = "USD", exchangeRate = 1 } = useCart() || {};
  const [orders, setOrders] = useState([]);
  const [stockMap, setStockMap] = useState({}); // product_id -> stock
  const [search, setSearch] = useState("");
  const [stockAlertOnly, setStockAlertOnly] = useState(false);
  // Iter 35 — server-side pagination
  const PAGE_SIZE = 50;
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const lowStockThreshold = parseInt(user?.settings?.low_stock_threshold ?? 5, 10) || 5;
  const stockBucket = (stock) => {
    const s = Number(stock ?? 0);
    if (s <= 0) return "out";
    if (s <= lowStockThreshold) return "low";
    return "ok";
  };

  const load = async () => {
    const oRes = await api.get(`/seller/orders/paged?page=${page}&page_size=${PAGE_SIZE}`);
    setOrders(oRes.data.items || []);
    setTotal(oRes.data.total || 0);
    // Iter 35 — stock_map is embedded in the paged response now (server-side
    // lookup for products referenced by the current page's orders).
    setStockMap(oRes.data.stock_map || {});
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [page]);

  const updateStatus = async (id, status) => {
    await api.put(`/orders/${id}/status`, { status });
    toast.success(`Status updated to ${status}`);
    load();
  };

  // Returns {low: n, out: n} for an order based on its product items' current stock
  const orderStockAlerts = (o) => {
    let low = 0, out = 0;
    for (const it of (o.items || [])) {
      if (it.item_type !== "product") continue;
      const s = stockMap[it.item_id];
      if (s === undefined) continue;
      const b = stockBucket(s);
      if (b === "out") out += 1;
      else if (b === "low") low += 1;
    }
    return { low, out };
  };

  const q = search.trim().toLowerCase();
  let filtered = !q ? orders : orders.filter((o) =>
    (o.customer_name || "").toLowerCase().includes(q) ||
    (o.id || "").toLowerCase().includes(q) ||
    (o.id || "").slice(0, 8).toLowerCase().includes(q)
  );
  if (stockAlertOnly) {
    filtered = filtered.filter((o) => {
      const a = orderStockAlerts(o);
      return a.low > 0 || a.out > 0;
    });
  }

  const totalAlertOrders = orders.filter((o) => {
    const a = orderStockAlerts(o);
    return a.low > 0 || a.out > 0;
  }).length;

  return (
    <div>
      <div className="mb-4 flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by customer name or Order ID..."
            data-testid="seller-orders-search"
            className="w-full bg-white border border-[var(--js-border)] rounded-full pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-[#C84B31] shadow-sm"
          />
          <svg className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
        </div>
        <button
          type="button"
          onClick={() => setStockAlertOnly((v) => !v)}
          data-testid="seller-orders-stock-alert-toggle"
          className={`text-xs font-bold px-3 py-2 rounded-full border transition inline-flex items-center gap-1.5 ${stockAlertOnly ? "bg-[#E9C46A] text-[#1A1A1A] border-[#E9C46A]" : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#E9C46A]"}`}
        >
          <AlertTriangle className="w-3.5 h-3.5" /> Stock alerts only
          <span className={`${stockAlertOnly ? "bg-white/70 text-[#9F6B00]" : "bg-[#E9C46A]/30 text-[#9F6B00]"} rounded-full px-1.5 py-0.5 text-[10px]`}>{totalAlertOrders}</span>
        </button>
        <p className="text-xs text-[var(--js-text-secondary)]" data-testid="seller-orders-count">
          {filtered.length} of {orders.length} order{orders.length !== 1 && "s"}
        </p>
      </div>

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
            {filtered.map((o) => {
              const alerts = orderStockAlerts(o);
              const hasAlert = alerts.low > 0 || alerts.out > 0;
              return (
              <tr key={o.id} className={`border-t border-[#E2E2D9] ${alerts.out > 0 ? "bg-[#D90429]/5" : alerts.low > 0 ? "bg-[#FFF7E0]" : ""}`} data-testid={`seller-order-${o.id}`}>
                <td className="p-4">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold text-[#1A1A1A]">#{o.id.slice(0, 8).toUpperCase()}</p>
                    {alerts.out > 0 && (
                      <span data-testid={`order-out-badge-${o.id}`} className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#D90429] text-white">
                        <XCircle className="w-3 h-3" /> {alerts.out} out
                      </span>
                    )}
                    {alerts.low > 0 && (
                      <span data-testid={`order-low-badge-${o.id}`} className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#E9C46A] text-[#1A1A1A]">
                        <AlertTriangle className="w-3 h-3" /> {alerts.low} low
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[#5C5C5C]">{new Date(o.created_at).toLocaleDateString()}</p>
                </td>
                <td className="p-4 hidden sm:table-cell">
                  <p className="font-semibold text-[#1A1A1A]">{o.customer_name}</p>
                  <p className="text-xs text-[#5C5C5C]">{o.area}</p>
                </td>
                <td className="p-4 hidden lg:table-cell text-[#5C5C5C]">
                  <p>{o.items.length} item{o.items.length !== 1 && "s"}</p>
                  {hasAlert && (
                    <p className="text-[10px] text-[#9F6B00] font-semibold mt-0.5">⚠ Restock needed for some items</p>
                  )}
                </td>
                <td className="p-4 font-bold">{formatPrice(o.subtotal_usd, exchangeRate, currency)}</td>
                <td className="p-4">
                  <div className="flex items-center gap-2">
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
                    <OrderChatButton orderId={o.id} label="Chat" />
                  </div>
                </td>
              </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr><td colSpan={5} className="p-8 text-center text-[#5C5C5C]" data-testid="seller-orders-empty">
                {stockAlertOnly && orders.length > 0
                  ? "No orders contain low or out-of-stock items right now. 🎉"
                  : q ? `No orders match "${search}"` : "No orders yet."}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      </div>
      <Pagination
        page={page}
        total={total}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        testIdPrefix="orders-pagination"
      />
    </div>
  );
}

function RateTab() {
  const { user } = useAuth();
  const [rate, setRate] = useState(600);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user?.id) return;
    // Fetch the CURRENT seller's own rate (not the global rate).
    api.get(`/exchange-rate?seller_id=${user.id}`).then((r) => setRate(r.data?.rate || 600));
  }, [user?.id]);

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/exchange-rate", { rate: parseFloat(rate) });
      setRate(data?.rate || parseFloat(rate));
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-4xl">
      <form onSubmit={saveProfile} noValidate className="bg-white border border-[#E2E2D9] rounded-3xl p-6 space-y-3">
        <h2 className="font-display font-semibold text-xl">Profile</h2>
        <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="settings-name-input" />
        <Input label="Phone" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} testId="settings-phone-input" />
        <button type="submit" data-testid="save-profile-btn" className="bg-[#1A1A1A] text-white font-semibold px-5 py-2.5 rounded-full">Save profile</button>
      </form>
      <PasswordChangeForm />
    </div>
  );
}

// Form helpers
function Input({ label, type = "text", value, onChange, required = false, testId, step, min, placeholder }) {
  return (
    <label className="block">
      <span className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">{label}</span>
      <input type={type} step={step} min={min} placeholder={placeholder} value={value} required={required}
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
      <select 
        value={value} 
        onChange={(e) => onChange(e.target.value)} 
        data-testid={testId} 
        className="js-input"
        size={opts.length > 6 ? 6 : undefined}
        style={opts.length > 6 ? { height: 'auto', overflowY: 'auto' } : undefined}
      >
        {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}
function Modal({ children, onClose, title }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div className="bg-white rounded-t-3xl sm:rounded-3xl w-full max-w-lg max-h-[90vh] sm:max-h-[85vh] flex flex-col shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 pt-6 pb-3 shrink-0 border-b border-[var(--js-border)]/60">
          <h2 className="font-display font-semibold text-xl">{title}</h2>
          <button onClick={onClose} data-testid="close-modal" className="p-2 hover:bg-[#F2EBE5] rounded-full"><X className="w-4 h-4" /></button>
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-6 py-5">
          {children}
        </div>
      </div>
    </div>
  );
}

function NotificationsTab() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  // Iter 35 — server-side pagination
  const PAGE_SIZE = 50;
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/notifications/paged?page=${page}&page_size=${PAGE_SIZE}`);
      setItems(data.items || []);
      setTotal(data.total || 0);
      setUnreadCount(data.unread_count || 0);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [page]);

  const markRead = async (n) => {
    if (n.is_read) return;
    try {
      await api.put(`/notifications/${n.id}/read`);
      setItems((prev) => prev.map((it) => (it.id === n.id ? { ...it, is_read: true } : it)));
      setUnreadCount((u) => Math.max(0, u - 1));
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail)); }
  };

  const markAll = async () => {
    try {
      await api.put("/notifications/read-all");
      setItems((prev) => prev.map((it) => ({ ...it, is_read: true })));
      setUnreadCount(0);
      toast.success("All notifications marked as read");
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail)); }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/notifications/${id}`);
      setItems((prev) => prev.filter((it) => it.id !== id));
      setTotal((t) => Math.max(0, t - 1));
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail)); }
  };

  const TYPE_BADGE = {
    order: { label: "Order", cls: "bg-[#2A9D8F]/15 text-[#1F7A6F]" },
    commission: { label: "Commission", cls: "bg-[#E9C46A]/25 text-[#7A5C12]" },
    alert: { label: "Alert", cls: "bg-[#C84B31]/15 text-[#A83A23]" },
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <p className="text-sm text-[#5C5C5C]">{total} notification{total !== 1 && "s"} · <span className="font-bold text-[#1A1A1A]">{unreadCount} unread</span></p>
        {unreadCount > 0 && (
          <button
            onClick={markAll}
            data-testid="seller-notif-mark-all"
            className="bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-4 py-2.5 rounded-full"
          >
            Mark all as read
          </button>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-[#5C5C5C]">Loading…</p>
      ) : items.length === 0 ? (
        <div className="bg-white border border-[#E2E2D9] rounded-3xl p-10 text-center">
          <Bell className="w-10 h-10 text-[#A3A39E] mx-auto mb-3" />
          <p className="font-display font-semibold text-lg text-[#1A1A1A]">No notifications yet</p>
          <p className="text-sm text-[#5C5C5C] mt-1">You'll see new orders and commission reminders here.</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((n) => {
            const t = TYPE_BADGE[n.type] || TYPE_BADGE.alert;
            return (
              <li
                key={n.id}
                data-testid={`seller-notif-${n.id}`}
                className={`bg-white border rounded-2xl p-4 flex items-start gap-3 transition ${n.is_read ? "border-[#E2E2D9]" : "border-[#C84B31]/40 bg-[#FFF8EE]"}`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full ${t.cls}`}>{t.label}</span>
                    {!n.is_read && <span className="text-[10px] uppercase tracking-wider font-bold text-[#C84B31]">● New</span>}
                  </div>
                  <p className={`text-sm ${n.is_read ? "text-[#1A1A1A]" : "font-semibold text-[#1A1A1A]"}`}>{n.message}</p>
                  <p className="text-xs text-[#5C5C5C] mt-1">{new Date(n.created_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {!n.is_read && (
                    <button
                      onClick={() => markRead(n)}
                      data-testid={`seller-notif-read-${n.id}`}
                      className="text-xs font-semibold text-[#C84B31] hover:underline px-2 py-1"
                    >
                      Mark read
                    </button>
                  )}
                  <button
                    onClick={() => remove(n.id)}
                    data-testid={`seller-notif-del-${n.id}`}
                    className="p-1.5 hover:bg-[#F2EBE5] rounded-full"
                    title="Dismiss"
                  >
                    <X className="w-4 h-4 text-[#5C5C5C]" />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <Pagination
        page={page}
        total={total}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        testIdPrefix="notif-pagination"
      />
    </div>
  );
}


function MessagesTab({ onChange }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all"); // all | unread
  const [replyingTo, setReplyingTo] = useState(null); // Message ID being replied to
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  // Iter 35 — server-side pagination
  const PAGE_SIZE = 50;
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const refreshUnread = async () => {
    try {
      const r = await api.get("/messages/seller/unread-count");
      onChange?.(r.data?.count || 0);
    } catch { /* ignore */ }
  };

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/messages/seller/paged?page=${page}&page_size=${PAGE_SIZE}`);
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); refreshUnread(); /* eslint-disable-next-line */ }, [page]);

  const markRead = async (m) => {
    if (m.is_read) return;
    try {
      await api.put(`/messages/${m.id}/read`);
      setItems((prev) => prev.map((it) => (it.id === m.id ? { ...it, is_read: true } : it)));
      refreshUnread();
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail)); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this message?")) return;
    try {
      await api.delete(`/messages/${id}`);
      setItems((prev) => prev.filter((it) => it.id !== id));
      refreshUnread();
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail)); }
  };

  const sendReply = async (messageId) => {
    if (replyText.trim().length < 2) {
      toast.error("Please write a reply");
      return;
    }
    setSending(true);
    try {
      await api.post(`/messages/${messageId}/reply`, { reply_body: replyText.trim() });
      toast.success("Reply sent!");
      setReplyingTo(null);
      setReplyText("");
      load(); // Reload to show updated message with reply
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to send reply");
    } finally {
      setSending(false);
    }
  };

  const visible = filter === "unread" ? items.filter((i) => !i.is_read) : items;
  const unreadN = items.filter((i) => !i.is_read).length;

  return (
    <div data-testid="seller-messages-tab">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <p className="text-sm text-[#5C5C5C]">
            {items.length} message{items.length !== 1 && "s"} · <span className="font-bold text-[#1A1A1A]">{unreadN} unread</span>
          </p>
          <p className="text-xs text-[#5C5C5C] mt-1">Customers reach you here from your shop's public page. Reply to their messages directly.</p>
        </div>
        <div className="flex gap-2">
          {[{ id: "all", label: "All" }, { id: "unread", label: `Unread (${unreadN})` }].map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              data-testid={`seller-messages-filter-${f.id}`}
              className={`text-xs font-bold px-3 py-2 rounded-full border transition ${
                filter === f.id ? "bg-[#1A1A1A] text-white border-[#1A1A1A]" : "bg-white text-[#1A1A1A] border-[var(--js-border)] hover:border-[#1A1A1A]"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-[#5C5C5C]">Loading…</p>
      ) : visible.length === 0 ? (
        <div className="bg-white border border-[#E2E2D9] rounded-3xl p-10 text-center">
          <MessageCircle className="w-10 h-10 text-[#A3A39E] mx-auto mb-3" />
          <p className="font-display font-semibold text-lg text-[#1A1A1A]">No {filter === "unread" ? "unread " : ""}messages</p>
          <p className="text-sm text-[#5C5C5C] mt-1">When customers contact your shop, you'll see their messages here.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {visible.map((m) => (
            <li
              key={m.id}
              data-testid={`seller-message-${m.id}`}
              className={`bg-white border rounded-2xl p-4 transition ${m.is_read ? "border-[#E2E2D9]" : "border-[#C84B31]/40 bg-[#FFF8EE]"}`}
            >
              <div className="flex items-start gap-3 flex-wrap">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-xs font-bold text-[#1A1A1A]">{m.customer_name || "Guest"}</span>
                    {!m.is_read && <span className="text-[10px] uppercase tracking-wider font-bold text-[#C84B31]">● NEW</span>}
                    {m.conversation_status === "replied" && <span className="text-[10px] uppercase tracking-wider font-bold text-[#2D6A4F]">✓ REPLIED</span>}
                    <span className="text-[10px] uppercase tracking-wider text-[#5C5C5C]">to {m.shop_name}</span>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap text-[11px] text-[#5C5C5C] mb-2">
                    {m.customer_email && (
                      <a href={`mailto:${m.customer_email}`} className="inline-flex items-center gap-1 hover:underline" data-testid={`msg-email-${m.id}`}>
                        <Mail className="w-3 h-3" /> {m.customer_email}
                      </a>
                    )}
                    {m.customer_phone && (
                      <a href={`tel:${m.customer_phone}`} className="inline-flex items-center gap-1 hover:underline" data-testid={`msg-phone-${m.id}`}>
                        <Phone className="w-3 h-3" /> {m.customer_phone}
                      </a>
                    )}
                    <span>· {new Date(m.created_at).toLocaleString()}</span>
                  </div>
                  {m.subject && (
                    <p className="font-display font-semibold text-sm text-[#1A1A1A] mb-1">{m.subject}</p>
                  )}
                  <p className="text-sm text-[#1A1A1A] whitespace-pre-wrap leading-relaxed">{m.body}</p>
                  
                  {/* Show existing reply if present */}
                  {m.reply_body && (
                    <div className="mt-3 p-3 bg-[#E9F5E9] border border-[#2D6A4F]/20 rounded-xl">
                      <p className="text-[10px] uppercase tracking-wider font-bold text-[#2D6A4F] mb-1">Your Reply · {m.replied_at ? new Date(m.replied_at).toLocaleString() : ""}</p>
                      <p className="text-sm text-[#1A1A1A] whitespace-pre-wrap">{m.reply_body}</p>
                    </div>
                  )}
                  
                  {/* Reply form */}
                  {replyingTo === m.id && (
                    <div className="mt-3 space-y-2">
                      <textarea
                        value={replyText}
                        onChange={(e) => setReplyText(e.target.value)}
                        placeholder="Write your reply..."
                        rows={3}
                        maxLength={2000}
                        className="w-full bg-white border border-[#E2E2D9] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
                      />
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => { setReplyingTo(null); setReplyText(""); }}
                          className="text-xs font-semibold text-[#5C5C5C] px-3 py-1.5 rounded-full hover:bg-[#F2EBE5]"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => sendReply(m.id)}
                          disabled={sending || replyText.trim().length < 2}
                          className="text-xs font-bold text-white bg-[#C84B31] hover:bg-[#A83A23] px-4 py-1.5 rounded-full disabled:bg-[#A3A39E]"
                        >
                          {sending ? "Sending..." : "Send Reply"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {!m.reply_body && replyingTo !== m.id && (
                    <button
                      onClick={() => { setReplyingTo(m.id); setReplyText(""); markRead(m); }}
                      className="text-xs font-semibold text-[#2D6A4F] hover:underline px-2 py-1"
                    >
                      Reply
                    </button>
                  )}
                  {!m.is_read && (
                    <button
                      onClick={() => markRead(m)}
                      data-testid={`msg-read-${m.id}`}
                      className="text-xs font-semibold text-[#C84B31] hover:underline px-2 py-1"
                    >
                      Mark read
                    </button>
                  )}
                  <button
                    onClick={() => remove(m.id)}
                    data-testid={`msg-del-${m.id}`}
                    className="p-1.5 hover:bg-[#F2EBE5] rounded-full"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4 text-[#5C5C5C]" />
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Pagination
        page={page}
        total={total}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        testIdPrefix="msg-pagination"
      />
    </div>
  );
}


function RequiredSidesEditor({ form, setForm, hasSides }) {
  // Only meaningful when at least one side item exists. Sellers configure
  // this to force customers to choose e.g. a pizza size or burger-meal
  // fries before adding to cart. See MenuItemIn validation on the backend.
  const required = !!form.sides_required;
  const min = form.sides_min_choices ?? 1;
  const max = form.sides_max_choices;
  return (
    <div className="border border-[var(--js-border)] rounded-2xl p-3 bg-[var(--js-subtle)] space-y-3">
      <div className="flex items-start gap-3">
        <input
          id="menu_sides_required"
          type="checkbox"
          disabled={!hasSides}
          checked={required}
          onChange={(e) => setForm({ ...form, sides_required: e.target.checked })}
          className="mt-1 w-5 h-5 accent-[#C84B31] disabled:opacity-40"
          data-testid="menu-sides-required-toggle"
        />
        <label htmlFor="menu_sides_required" className={`flex-1 ${hasSides ? "cursor-pointer" : "opacity-50"}`}>
          <p className="font-display font-semibold text-sm text-[var(--js-text)]">Force customer to choose sides</p>
          <p className="text-xs text-[var(--js-text-secondary)]">
            {hasSides
              ? "Turn on for items like pizza (must pick size) or burger meals (must pick fries)."
              : "Add at least one side item above to enable this."}
          </p>
        </label>
      </div>
      {required && hasSides && (
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs">
            <span className="block font-semibold text-[var(--js-text-secondary)] mb-1">Minimum choices</span>
            <input
              type="number"
              min={1}
              max={(form.side_items || []).length}
              value={min}
              onChange={(e) => setForm({ ...form, sides_min_choices: e.target.value })}
              data-testid="menu-sides-min-input"
              className="w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-[var(--js-bg)] text-sm"
            />
          </label>
          <label className="text-xs">
            <span className="block font-semibold text-[var(--js-text-secondary)] mb-1">Maximum choices (blank = unlimited)</span>
            <input
              type="number"
              min={1}
              max={(form.side_items || []).length}
              value={max ?? ""}
              onChange={(e) =>
                setForm({ ...form, sides_max_choices: e.target.value === "" ? null : e.target.value })
              }
              data-testid="menu-sides-max-input"
              className="w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-[var(--js-bg)] text-sm"
              placeholder="unlimited"
            />
          </label>
          <p className="col-span-2 text-[11px] text-[var(--js-text-secondary)] italic">
            Preset examples:
            <span className="ml-2 inline-block bg-white border border-[var(--js-border)] rounded px-2 py-0.5 mr-1">Pizza size → min 1, max 1</span>
            <span className="inline-block bg-white border border-[var(--js-border)] rounded px-2 py-0.5">Burger meal → min 1, max blank</span>
          </p>
        </div>
      )}
    </div>
  );
}


function SectionPicker({ form, setForm, fieldKey, sections, label, hint, emptyHint }) {
  return (
    <div>
      <span className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">{label}</span>
      {sections && sections.length > 0 ? (
        <select
          value={form[fieldKey] || ""}
          onChange={(e) => setForm({ ...form, [fieldKey]: e.target.value })}
          data-testid={`${fieldKey}-select`}
          className="w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white text-sm"
        >
          <option value="">— No section (Other) —</option>
          {sections.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      ) : (
        <p className="text-xs text-[var(--js-text-secondary)] italic bg-[var(--js-subtle)] rounded-lg px-3 py-2 border border-[var(--js-border)]">
          {emptyHint}
        </p>
      )}
      {hint && <p className="text-[11px] text-[var(--js-text-secondary)] mt-1">{hint}</p>}
    </div>
  );
}

function PromoEditor({ form, setForm }) {
  const promo = form.promo || { active: false, type: "percent", value: 0, starts_at: "", ends_at: "" };
  const set = (patch) => setForm({ ...form, promo: { ...promo, ...patch } });
  // ISO → <input type="datetime-local"> compatible (YYYY-MM-DDTHH:mm)
  const toLocal = (iso) => (iso ? iso.slice(0, 16) : "");
  return (
    <div className="border border-[var(--js-border)] rounded-2xl p-3 bg-[var(--js-subtle)] space-y-3">
      <div className="flex items-start gap-3">
        <input
          id="promo_active"
          type="checkbox"
          checked={!!promo.active}
          onChange={(e) => set({ active: e.target.checked })}
          className="mt-1 w-5 h-5 accent-emerald-600"
          data-testid="promo-active-toggle"
        />
        <label htmlFor="promo_active" className="flex-1 cursor-pointer">
          <p className="font-display font-semibold text-sm text-[var(--js-text)]">Limited-time promo</p>
          <p className="text-xs text-[var(--js-text-secondary)]">
            Discount is applied automatically when a customer views this item. Backend re-computes at checkout — safe from tampering.
          </p>
        </label>
      </div>
      {promo.active && (
        <div className="space-y-3">
          <div className="flex items-end gap-3 flex-wrap">
            <div>
              <span className="block text-xs font-semibold text-[var(--js-text-secondary)] mb-1">Type</span>
              <div className="inline-flex bg-white rounded-full p-1 border border-[var(--js-border)]">
                {[
                  { id: "percent", label: "%" },
                  { id: "amount", label: "$" },
                  { id: "bogo", label: "BOGO" },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => set({ type: opt.id })}
                    data-testid={`promo-type-${opt.id}`}
                    className={`px-3 py-1 rounded-full text-xs font-semibold ${
                      promo.type === opt.id ? "bg-emerald-600 text-white" : "text-[var(--js-text-secondary)]"
                    }`}
                  >{opt.label}</button>
                ))}
              </div>
            </div>
            {promo.type !== "bogo" ? (
              <div>
                <span className="block text-xs font-semibold text-[var(--js-text-secondary)] mb-1">
                  {promo.type === "percent" ? "Discount %" : "Discount $"}
                </span>
                <input
                  type="number"
                  min={0}
                  step={promo.type === "percent" ? 1 : 0.1}
                  max={promo.type === "percent" ? 100 : undefined}
                  value={promo.value ?? 0}
                  onChange={(e) => set({ value: e.target.value })}
                  data-testid="promo-value-input"
                  className="w-28 px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white text-sm"
                />
              </div>
            ) : (
              <div>
                <span className="block text-xs font-semibold text-[var(--js-text-secondary)] mb-1">
                  Buy how many to get 1 free?
                </span>
                <input
                  type="number"
                  min={2}
                  max={10}
                  value={promo.bogo_min_qty ?? 2}
                  onChange={(e) => set({ bogo_min_qty: e.target.value })}
                  data-testid="promo-bogo-input"
                  className="w-28 px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white text-sm"
                />
                <p className="text-[10px] text-[var(--js-text-secondary)] mt-1">
                  Ordering {promo.bogo_min_qty || 2}× charges for {(promo.bogo_min_qty || 2) - 1}× at checkout.
                </p>
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="block text-xs font-semibold text-[var(--js-text-secondary)] mb-1">Start (optional)</span>
              <input
                type="datetime-local"
                value={toLocal(promo.starts_at)}
                onChange={(e) => set({ starts_at: e.target.value ? new Date(e.target.value).toISOString() : "" })}
                data-testid="promo-starts-input"
                className="w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white text-sm"
              />
            </div>
            <div>
              <span className="block text-xs font-semibold text-[var(--js-text-secondary)] mb-1">End (optional)</span>
              <input
                type="datetime-local"
                value={toLocal(promo.ends_at)}
                onChange={(e) => set({ ends_at: e.target.value ? new Date(e.target.value).toISOString() : "" })}
                data-testid="promo-ends-input"
                className="w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white text-sm"
              />
            </div>
          </div>
          <p className="text-[11px] text-[var(--js-text-secondary)] italic">
            Leave dates blank to run indefinitely. Toggle off any time to end the promo instantly.
          </p>
        </div>
      )}
    </div>
  );
}

