import { useEffect, useState, useMemo, useCallback } from "react";
import api, { formatPrice, formatDetail } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { useTranslation } from "react-i18next";
import { useOptimizedPolling } from "@/hooks/useOptimizedPolling";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import AdminAnalytics from "@/components/AdminAnalytics";
import PerformanceMonitor from "@/components/PerformanceMonitor";
import AdminIntegrations from "@/components/AdminIntegrations";
import AdminPagesTab from "@/components/AdminPagesTab";
import AdminSettingsTab from "@/components/AdminSettingsTab";
import AdminFooterTab from "@/components/AdminFooterTab";
import AdminCategoriesTab from "@/components/AdminCategoriesTab";
import AdminDeliveryTab from "@/components/AdminDeliveryTab";
import AdminDeliveryPricingTab from "@/components/AdminDeliveryPricingTab";
import AdminOdooTokenManager from "@/components/AdminOdooTokenManager";
import { Store, Mail, CheckCircle2, XCircle, Clock, Plus, Trash2, X, BarChart3, Settings as SettingsIcon, BookOpen, Sliders, PanelBottom, FolderTree, Ban, Activity, Truck, MapPin, Key } from "lucide-react";
import { toast } from "sonner";

const TABS = [
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "performance", label: "Performance", icon: Activity },
  { id: "shops", label: "Shops & Restaurants", icon: Store },
  { id: "categories", label: "Categories", icon: FolderTree },
  { id: "delivery", label: "Delivery & Payouts", icon: Truck },
  { id: "delivery-pricing", label: "Delivery Pricing", icon: MapPin },
  { id: "cancellations", label: "Cancellation Requests", icon: Ban },
  { id: "emails", label: "Blocked Emails", icon: Mail },
  { id: "pages", label: "Pages", icon: BookOpen },
  { id: "footer", label: "Footer", icon: PanelBottom },
  { id: "settings", label: "Settings", icon: Sliders },
  { id: "integrations", label: "Integrations", icon: SettingsIcon },
  { id: "odoo", label: "Odoo Integration", icon: Key },
];

export default function AdminDashboard() {
  const [tab, setTab] = useState("analytics");
  const [alerts, setAlerts] = useState({});
  const { t: tr } = useTranslation();

  // Load admin alerts
  const loadAlerts = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/alerts");
      setAlerts(data || {});
    } catch (err) {
      // Silent fail - keep last value
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  // Optimized polling with visibility detection
  useOptimizedPolling(loadAlerts, 30000, { runOnMount: false });

  // Map tab id -> number of pending items
  const tabBadge = {
    delivery: (alerts.orders_needing_driver || 0) + (alerts.cash_pending || 0) + (alerts.payouts_ready || 0) + (alerts.disputes_open || 0),
    cancellations: alerts.cancellations_open || 0,
  };

  return (
    <div className="min-h-screen flex flex-col bg-[var(--js-bg)]">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-2">{tr("dashboard")}</p>
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[var(--js-text)]">{tr("platformControl")}</h1>

        <div className="mt-8 flex flex-wrap gap-2 border-b border-[var(--js-border)]">
          {TABS.map((t) => {
            const Icon = t.icon;
            const badge = tabBadge[t.id] || 0;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                data-testid={`admin-tab-${t.id}`}
                className={`relative flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition ${
                  tab === t.id ? "border-[#C84B31] text-[#C84B31]" : "border-transparent text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"
                }`}
              >
                <Icon className="w-4 h-4" /> {t.label}
                {badge > 0 && (
                  <span
                    data-testid={`admin-tab-badge-${t.id}`}
                    className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-[#D90429] text-white text-[10px] font-bold ml-1"
                  >
                    {badge > 99 ? "99+" : badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Inline alerts banner — visible across tabs so admins never miss it */}
        {(alerts.orders_needing_driver > 0 || alerts.cash_pending > 0 || alerts.payouts_ready > 0 || alerts.disputes_open > 0) && (
          <div
            data-testid="admin-alerts-banner"
            className="mt-4 flex flex-wrap gap-2 text-xs"
          >
            {alerts.orders_needing_driver > 0 && (
              <button
                onClick={() => setTab("delivery")}
                data-testid="alert-pill-needs-driver"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-100 text-amber-900 font-semibold hover:bg-amber-200 transition"
              >
                <Truck className="w-3 h-3" /> {alerts.orders_needing_driver} order{alerts.orders_needing_driver > 1 ? "s" : ""} need a driver
              </button>
            )}
            {alerts.cash_pending > 0 && (
              <button
                onClick={() => setTab("delivery")}
                data-testid="alert-pill-cash"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-100 text-blue-900 font-semibold hover:bg-blue-200 transition"
              >
                💵 {alerts.cash_pending} cash pending handover
              </button>
            )}
            {alerts.payouts_ready > 0 && (
              <button
                onClick={() => setTab("delivery")}
                data-testid="alert-pill-payouts"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-100 text-emerald-900 font-semibold hover:bg-emerald-200 transition"
              >
                ✅ {alerts.payouts_ready} payouts ready
              </button>
            )}
            {alerts.disputes_open > 0 && (
              <button
                onClick={() => setTab("delivery")}
                data-testid="alert-pill-disputes"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-red-100 text-red-900 font-semibold hover:bg-red-200 transition"
              >
                <Ban className="w-3 h-3" /> {alerts.disputes_open} dispute{alerts.disputes_open > 1 ? "s" : ""} open
              </button>
            )}
          </div>
        )}

        <div className="mt-8">
          {tab === "analytics" && <AdminAnalytics />}
          {tab === "performance" && <PerformanceMonitor />}
          {tab === "shops" && <AdminShopsTab />}
          {tab === "categories" && <AdminCategoriesTab />}
          {tab === "delivery" && <AdminDeliveryTab />}
          {tab === "delivery-pricing" && <AdminDeliveryPricingTab />}
          {tab === "cancellations" && <AdminCancellationsTab />}
          {tab === "emails" && <AdminEmailsTab />}
          {tab === "pages" && <AdminPagesTab />}
          {tab === "footer" && <AdminFooterTab />}
          {tab === "settings" && <AdminSettingsTab onGoToShop={() => setTab("shops")} />}
          {tab === "integrations" && <AdminIntegrations />}
          {tab === "odoo" && <AdminOdooTokenManager />}
        </div>
      </div>
      <Footer />
    </div>
  );
}

function AdminShopsTab() {
  const [shops, setShops] = useState([]);
  const [restaurants, setRestaurants] = useState([]);
  const [detail, setDetail] = useState(null); // { ...row, _kind: 'shop' | 'restaurant' }
  const [commissionDraft, setCommissionDraft] = useState("");
  const [invoiceFrequencyDraft, setInvoiceFrequencyDraft] = useState("");
  const [payoutFrequencyDraft, setPayoutFrequencyDraft] = useState("");
  const [globalRate, setGlobalRate] = useState(0.10);
  const [globalFrequency, setGlobalFrequency] = useState("weekly");
  const [searchQuery, setSearchQuery] = useState("");
  const [kindFilter, setKindFilter] = useState("all"); // all | shops | restaurants

  const load = async () => {
    const [s, r, g] = await Promise.all([
      api.get("/shops?limit=200"),
      api.get("/restaurants?limit=200"),
      api.get("/admin/settings"),
    ]);
    setShops((s.data || []).map((x) => ({ ...x, _kind: "shop" })));
    setRestaurants((r.data || []).map((x) => ({ ...x, _kind: "restaurant" })));
    setGlobalRate(g.data.commission_rate || 0.10);
    setGlobalFrequency(g.data.invoice_frequency || "weekly");
  };
  useEffect(() => { load(); }, []);

  const openDetail = (s) => {
    setDetail(s);
    setCommissionDraft(s.commission_rate != null ? String(s.commission_rate) : "");
    setInvoiceFrequencyDraft(s.invoice_frequency || "");
    setPayoutFrequencyDraft(s.payout_frequency || "");
  };

  const verify = async (row) => {
    const path = row._kind === "restaurant" ? `/admin/restaurants/${row.id}/verify` : `/admin/shops/${row.id}/verify`;
    await api.put(path);
    toast.success("Verified");
    load();
    if (detail?.id === row.id) setDetail({ ...detail, verification: "Verified" });
  };
  const reject = async (row) => {
    const path = row._kind === "restaurant" ? `/admin/restaurants/${row.id}/reject` : `/admin/shops/${row.id}/reject`;
    await api.put(path);
    toast.success("Rejected");
    load();
    if (detail?.id === row.id) setDetail({ ...detail, verification: "Rejected" });
  };

  const saveCommission = async () => {
    const v = commissionDraft === "" ? null : parseFloat(commissionDraft);
    try {
      const base = detail._kind === "restaurant" ? `/admin/restaurants/${detail.id}/commission` : `/admin/shops/${detail.id}/commission`;
      const { data } = await api.put(base, { commission_rate: v });
      toast.success(v === null ? "Commission reset to global" : `Commission set to ${(v * 100).toFixed(1)}%`);
      try { await api.post("/admin/invoices/generate"); } catch { /* ignore */ }
      setDetail({ ...data, _kind: detail._kind });
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const saveInvoiceFrequency = async () => {
    const freq = invoiceFrequencyDraft === "" ? null : invoiceFrequencyDraft;
    try {
      const base = detail._kind === "restaurant"
        ? `/admin/restaurants/${detail.id}/invoice-frequency`
        : `/admin/shops/${detail.id}/invoice-frequency`;
      const { data } = await api.put(base, { frequency: freq });
      toast.success(freq === null ? "Invoice frequency reset to global" : `Invoice frequency set to ${freq}`);
      setDetail({ ...data, _kind: detail._kind });
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const savePayoutFrequency = async () => {
    const freq = payoutFrequencyDraft === "" ? null : payoutFrequencyDraft;
    try {
      const base = detail._kind === "restaurant"
        ? `/admin/restaurants/${detail.id}/payout-frequency`
        : `/admin/shops/${detail.id}/payout-frequency`;
      const { data } = await api.put(base, { payout_frequency: freq });
      toast.success(freq === null ? "Payout frequency reset to default (weekly)" : `Payout frequency set to ${freq}`);
      setDetail({ ...data, _kind: detail._kind });
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const allRows = useMemo(() => {
    if (kindFilter === "shops") return shops;
    if (kindFilter === "restaurants") return restaurants;
    return [...shops, ...restaurants];
  }, [shops, restaurants, kindFilter]);

  const filteredShops = useMemo(() =>
    allRows.filter(s =>
      (s.name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.area || "").toLowerCase().includes(searchQuery.toLowerCase())
    ),
    [allRows, searchQuery]
  );

  const counts = useMemo(() => {
    const merged = [...shops, ...restaurants];
    return {
      Verified: merged.filter((s) => s.verification === "Verified").length,
      Pending: merged.filter((s) => s.verification === "Pending").length,
      Rejected: merged.filter((s) => s.verification === "Rejected").length,
    };
  }, [shops, restaurants]);

  const frequencyOptions = [
    { value: "daily", label: "Daily" },
    { value: "weekly", label: "Weekly" },
    { value: "monthly", label: "Monthly" },
    { value: "quarterly", label: "Quarterly" },
    { value: "yearly", label: "Yearly" },
  ];

  const payoutFrequencyOptions = [
    { value: "daily", label: "Daily" },
    { value: "weekly", label: "Weekly" },
    { value: "monthly", label: "Monthly" },
  ];

  return (
    <div>
      <div className="grid grid-cols-3 gap-3 mb-6">
        <Stat label="Verified" value={counts.Verified} color="#2D6A4F" />
        <Stat label="Pending" value={counts.Pending} color="#E9C46A" />
        <Stat label="Rejected" value={counts.Rejected} color="#D90429" />
      </div>

      {/* Search Bar + kind filter */}
      <div className="mb-4 flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Search shops & restaurants by name or area..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 px-4 py-3 border border-[var(--js-border)] rounded-xl text-sm focus:outline-none focus:border-[#C84B31]"
        />
        <div className="inline-flex bg-white border border-[var(--js-border)] rounded-xl p-1">
          {[
            { id: "all", label: `All (${shops.length + restaurants.length})` },
            { id: "shops", label: `Shops (${shops.length})` },
            { id: "restaurants", label: `Restaurants (${restaurants.length})` },
          ].map((k) => (
            <button
              key={k.id}
              type="button"
              onClick={() => setKindFilter(k.id)}
              data-testid={`shops-kind-filter-${k.id}`}
              className={`px-3 py-2 text-xs font-semibold rounded-lg transition ${
                kindFilter === k.id
                  ? "bg-[#C84B31] text-white"
                  : "text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"
              }`}
            >
              {k.label}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--js-bg)] text-[var(--js-text-secondary)] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-4 font-bold">Name</th>
                <th className="text-left p-4 font-bold hidden sm:table-cell">Type</th>
                <th className="text-left p-4 font-bold hidden lg:table-cell">Area</th>
                <th className="text-left p-4 font-bold hidden md:table-cell">Commission</th>
                <th className="text-left p-4 font-bold">Status</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {filteredShops.map((s) => (
                <tr key={`${s._kind}-${s.id}`} className="border-t border-[var(--js-border)] hover:bg-[var(--js-bg)] cursor-pointer" onClick={() => openDetail(s)} data-testid={`admin-${s._kind}-row-${s.id}`}>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <img src={s.image_url || undefined} alt="" className="w-10 h-10 rounded-lg object-cover bg-gray-100" />
                      <p className="font-semibold text-[var(--js-text)]">{s.name}</p>
                    </div>
                  </td>
                  <td className="p-4 hidden sm:table-cell">
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full ${
                      s._kind === "restaurant" ? "bg-amber-100 text-amber-800" : "bg-blue-100 text-blue-800"
                    }`}>
                      {s._kind === "restaurant" ? "Restaurant" : "Shop"}
                    </span>
                  </td>
                  <td className="p-4 text-[var(--js-text-secondary)] hidden lg:table-cell">{s.area}</td>
                  <td className="p-4 hidden md:table-cell text-xs">
                    {s.commission_rate != null
                      ? <span className="font-bold text-[#C84B31]">{(s.commission_rate * 100).toFixed(1)}%</span>
                      : <span className="text-[var(--js-text-secondary)]">global ({(globalRate * 100).toFixed(1)}%)</span>}
                  </td>
                  <td className="p-4">
                    {s.verification === "Verified" && <span className="inline-flex items-center gap-1 bg-[#2D6A4F]/10 text-[#2D6A4F] text-xs font-bold px-2 py-1 rounded-full"><CheckCircle2 className="w-3 h-3" /> Verified</span>}
                    {s.verification === "Pending" && <span className="inline-flex items-center gap-1 bg-[#E9C46A]/30 text-[var(--js-text)] text-xs font-bold px-2 py-1 rounded-full"><Clock className="w-3 h-3" /> Pending</span>}
                    {s.verification === "Rejected" && <span className="inline-flex items-center gap-1 bg-[#D90429]/10 text-[#D90429] text-xs font-bold px-2 py-1 rounded-full"><XCircle className="w-3 h-3" /> Rejected</span>}
                  </td>
                  <td className="p-4 text-right">
                    <div className="inline-flex gap-2" onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => verify(s)} data-testid={`verify-${s._kind}-${s.id}`} className="text-xs font-semibold bg-[#2D6A4F] hover:bg-[#1B4332] text-white px-3 py-1.5 rounded-full">Verify</button>
                      <button onClick={() => reject(s)} data-testid={`reject-${s._kind}-${s.id}`} className="text-xs font-semibold bg-[#D90429]/10 text-[#D90429] hover:bg-[#D90429] hover:text-white px-3 py-1.5 rounded-full transition">Reject</button>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredShops.length === 0 && (
                <tr><td colSpan={6} className="p-8 text-center text-[var(--js-text-secondary)]">
                  {searchQuery ? `No results matching "${searchQuery}"` : "Nothing here yet."}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {detail && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-t-3xl sm:rounded-3xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()} data-testid="admin-shop-detail">
            <div className="aspect-[16/8] overflow-hidden relative">
              <img src={detail.image_url} alt="" className="w-full h-full object-cover" />
              <button onClick={() => setDetail(null)} className="absolute top-4 right-4 bg-white/90 backdrop-blur rounded-full p-2 hover:bg-white" data-testid="close-shop-detail">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-5">
              <div>
                <h2 className="font-display font-bold text-2xl text-[var(--js-text)]">{detail.name}</h2>
                <p className="text-sm text-[var(--js-text-secondary)] mt-1">{detail.description}</p>
                <p className="text-xs text-[var(--js-text-secondary)] mt-2">📍 {detail.area}</p>
              </div>

              <div className="flex gap-2">
                <button onClick={() => verify(detail.id)} className="flex-1 bg-[#2D6A4F] hover:bg-[#1B4332] text-white text-sm font-semibold py-2.5 rounded-full">✓ Verify</button>
                <button onClick={() => reject(detail.id)} className="flex-1 bg-[#D90429]/10 text-[#D90429] hover:bg-[#D90429] hover:text-white text-sm font-semibold py-2.5 rounded-full transition">✗ Reject</button>
              </div>

              <div className="bg-[var(--js-subtle)] rounded-2xl p-4">
                <h3 className="font-display font-semibold text-sm mb-1">Custom commission rate</h3>
                <p className="text-xs text-[var(--js-text-secondary)] mb-3">
                  Leave empty to inherit global rate ({(globalRate * 100).toFixed(1)}%). Enter as decimal, e.g. <code className="bg-white px-1 rounded">0.08</code> for 8%.
                </p>
                <div className="flex gap-2 items-center">
                  <input
                    type="number" step="0.01" min="0" max="1"
                    placeholder={`inherit (${(globalRate * 100).toFixed(1)}%)`}
                    value={commissionDraft}
                    onChange={(e) => setCommissionDraft(e.target.value)}
                    data-testid="shop-commission-input"
                    className="js-input flex-1"
                  />
                  <span className="text-xs text-[var(--js-text-secondary)]">
                    {commissionDraft ? `${(parseFloat(commissionDraft) * 100).toFixed(1)}%` : "—"}
                  </span>
                </div>
                <div className="flex gap-2 mt-3">
                  <button onClick={saveCommission} data-testid="save-shop-commission" className="flex-1 bg-[#1A1A1A] hover:bg-[#C84B31] text-white text-sm font-semibold py-2 rounded-full transition">Save commission</button>
                  <button onClick={() => { setCommissionDraft(""); }} className="bg-white border border-[var(--js-border)] text-[var(--js-text)] text-sm font-semibold px-3 py-2 rounded-full">Reset</button>
                </div>
                <p className="text-[10px] text-[var(--js-text-secondary)] mt-2">Saving will automatically regenerate invoices for this shop.</p>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
                <h3 className="font-display font-semibold text-sm mb-1 text-blue-900">Invoice Frequency Override</h3>
                <p className="text-xs text-blue-700 mb-3">
                  Set custom invoice frequency for this shop. Leave unset to use global frequency ({globalFrequency}).
                </p>
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {frequencyOptions.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setInvoiceFrequencyDraft(opt.value)}
                      className={`px-2 py-2 rounded-lg text-xs font-semibold transition border-2 ${
                        invoiceFrequencyDraft === opt.value
                          ? "border-blue-600 bg-blue-100 text-blue-900"
                          : "border-blue-200 text-blue-700 hover:border-blue-400"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <button onClick={saveInvoiceFrequency} className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold py-2 rounded-full transition">Save frequency</button>
                  <button onClick={() => { setInvoiceFrequencyDraft(""); }} className="bg-white border border-blue-200 text-blue-700 text-sm font-semibold px-3 py-2 rounded-full">Use global</button>
                </div>
                <p className="text-[10px] text-blue-600 mt-2">
                  Current: {detail.invoice_frequency ? <strong>{detail.invoice_frequency}</strong> : <span>using global ({globalFrequency})</span>}
                </p>
              </div>

              {/* Odoo Connection Section - Admin Only */}
              <OdooConnectionSection detail={detail} onUpdate={() => load()} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Odoo Connection Section Component
function OdooConnectionSection({ detail, onUpdate }) {
  const [odooSettings, setOdooSettings] = useState(detail?.odoo_connection || {});
  const [isSaving, setIsSaving] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [syncLogs, setSyncLogs] = useState([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [selectedLogs, setSelectedLogs] = useState([]);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [connectionTestResult, setConnectionTestResult] = useState(null);

  useEffect(() => {
    setOdooSettings(detail?.odoo_connection || {
      enabled: false,
      company_id: null,
      company_name: null,
      warehouse_id: null,
      warehouse_name: null,
      pricelist_id: null,
      pricelist_name: null,
      pos_config_id: null,
      sync_products: false,
      sync_stock: false,
      send_orders: false,
      send_delivery_updates: false,
      sync_status: "not_configured"
    });
  }, [detail]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const endpoint = detail._kind === "restaurant"
        ? `/admin/restaurants/${detail.id}/odoo-connection`
        : `/admin/shops/${detail.id}/odoo-connection`;
      
      await api.put(endpoint, {
        enabled: odooSettings.enabled,
        company_id: odooSettings.company_id || null,
        company_name: odooSettings.company_name || null,
        warehouse_id: odooSettings.warehouse_id || null,
        warehouse_name: odooSettings.warehouse_name || null,
        pricelist_id: odooSettings.pricelist_id || null,
        pricelist_name: odooSettings.pricelist_name || null,
        pos_config_id: odooSettings.pos_config_id || null,
        sync_products: odooSettings.sync_products,
        sync_stock: odooSettings.sync_stock,
        send_orders: odooSettings.send_orders,
        send_delivery_updates: odooSettings.send_delivery_updates
      });
      
      toast.success("Odoo connection settings saved");
      onUpdate();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to save Odoo settings");
    } finally {
      setIsSaving(false);
    }
  };

  const loadSyncLogs = async () => {
    setLoadingLogs(true);
    try {
      const params = new URLSearchParams({
        limit: "50"
      });
      
      // Filter by shop or restaurant
      if (detail._kind === "shop" && detail.id) {
        params.append("shop_id", detail.id);
      } else if (detail._kind === "restaurant" && detail.id) {
        params.append("restaurant_id", detail.id);
      }
      
      const { data } = await api.get(`/admin/odoo/sync-logs?${params.toString()}`);
      setSyncLogs(data || []);
    } catch (err) {
      toast.error("Failed to load sync logs");
      setSyncLogs([]);
    } finally {
      setLoadingLogs(false);
    }
  };

  const handleViewLogs = () => {
    setShowLogsModal(true);
    loadSyncLogs();
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setConnectionTestResult(null);
    try {
      const payload = detail._kind === "restaurant"
        ? { restaurant_id: detail.id }
        : { shop_id: detail.id };
      
      const { data } = await api.post("/admin/odoo/test-connection", payload);
      setConnectionTestResult({
        success: data.status !== "error",
        message: data.message || "Connection test completed",
        details: data
      });
      
      if (data.status === "placeholder") {
        toast.info("Test connection - to be implemented by your Odoo module");
      } else {
        toast.success("Connection test completed");
      }
    } catch (err) {
      setConnectionTestResult({
        success: false,
        message: err.response?.data?.detail || "Connection test failed",
        details: err.response?.data
      });
      toast.error("Connection test failed");
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleRetryFailed = async () => {
    if (selectedLogs.length === 0) {
      toast.error("Please select logs to retry");
      return;
    }

    try {
      await api.post("/admin/odoo/retry-failed", {
        log_ids: selectedLogs
      });
      toast.success(`Retrying ${selectedLogs.length} failed sync(s)`);
      setSelectedLogs([]);
      loadSyncLogs();
    } catch (err) {
      toast.error("Failed to retry syncs");
    }
  };

  const getStatusColor = () => {
    if (!odooSettings.enabled) return "gray";
    switch (odooSettings.sync_status) {
      case "active": return "green";
      case "error": return "red";
      case "disabled": return "gray";
      default: return "gray";
    }
  };

  const getStatusText = () => {
    if (!odooSettings.enabled) return "Disabled";
    switch (odooSettings.sync_status) {
      case "active": return "Connected";
      case "error": return "Error";
      case "disabled": return "Disabled";
      case "not_configured": return "Not Configured";
      default: return "Unknown";
    }
  };

  const statusColor = getStatusColor();
  const statusBgColor = {
    green: "bg-green-100 text-green-800",
    red: "bg-red-100 text-red-800",
    gray: "bg-gray-100 text-gray-600"
  }[statusColor];

  const failedLogsCount = syncLogs.filter(log => log.status === "failed").length;

  return (
    <>
      <div className="bg-gradient-to-br from-purple-50 to-blue-50 border-2 border-purple-200 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-600 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h3 className="font-display font-semibold text-sm text-purple-900">Odoo Connection</h3>
              <p className="text-xs text-purple-700">Admin-only integration settings</p>
            </div>
          </div>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-2 rounded-lg hover:bg-purple-100 transition"
          >
            <svg
              className={`w-5 h-5 text-purple-600 transition-transform ${isExpanded ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>

        {/* Status Badge */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className={`inline-flex items-center gap-1 text-xs font-bold px-3 py-1 rounded-full ${statusBgColor}`}>
            <span className={`w-2 h-2 rounded-full ${statusColor === 'green' ? 'bg-green-500' : statusColor === 'red' ? 'bg-red-500' : 'bg-gray-400'}`}></span>
            {getStatusText()}
          </span>
          {odooSettings.last_sync_at && (
            <span className="text-xs text-purple-600">
              Last sync: {new Date(odooSettings.last_sync_at).toLocaleString()}
            </span>
          )}
          {failedLogsCount > 0 && (
            <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full bg-red-100 text-red-800">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              {failedLogsCount} failed
            </span>
          )}
        </div>

        {/* Quick Actions - Always Visible */}
        {!isExpanded && odooSettings.enabled && (
          <div className="flex gap-2">
            <button
              onClick={handleViewLogs}
              className="flex-1 bg-white border border-purple-300 text-purple-700 hover:bg-purple-50 text-xs font-semibold py-2 rounded-lg transition flex items-center justify-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              View Logs
            </button>
            <button
              onClick={handleTestConnection}
              disabled={isTestingConnection}
              className="bg-white border border-purple-300 text-purple-700 hover:bg-purple-50 text-xs font-semibold px-3 py-2 rounded-lg transition disabled:opacity-50"
            >
              {isTestingConnection ? "..." : "Test"}
            </button>
          </div>
        )}

        {isExpanded && (
          <div className="space-y-4 mt-4">
            {/* Enable/Disable Toggle */}
            <div className="flex items-center gap-3 p-3 bg-white rounded-lg">
              <input
                type="checkbox"
                id="odoo-enabled"
                checked={odooSettings.enabled}
                onChange={(e) => setOdooSettings({ ...odooSettings, enabled: e.target.checked })}
                className="w-5 h-5 text-purple-600 rounded focus:ring-purple-500"
              />
              <label htmlFor="odoo-enabled" className="flex-1 cursor-pointer">
                <span className="font-semibold text-sm text-purple-900">Connect this {detail._kind} to Odoo</span>
                <p className="text-xs text-purple-600">Enable to sync with your Odoo 18 instance</p>
              </label>
            </div>

            {odooSettings.enabled && (
              <>
                {/* Odoo Configuration Fields */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-purple-900 mb-1">Company ID</label>
                    <input
                      type="text"
                      value={odooSettings.company_id || ""}
                      onChange={(e) => setOdooSettings({ ...odooSettings, company_id: e.target.value })}
                      placeholder="e.g., 1"
                      className="w-full px-3 py-2 text-sm border border-purple-200 rounded-lg focus:outline-none focus:border-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-purple-900 mb-1">Company Name</label>
                    <input
                      type="text"
                      value={odooSettings.company_name || ""}
                      onChange={(e) => setOdooSettings({ ...odooSettings, company_name: e.target.value })}
                      placeholder="e.g., My Company"
                      className="w-full px-3 py-2 text-sm border border-purple-200 rounded-lg focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-purple-900 mb-1">Warehouse ID</label>
                    <input
                      type="text"
                      value={odooSettings.warehouse_id || ""}
                      onChange={(e) => setOdooSettings({ ...odooSettings, warehouse_id: e.target.value })}
                      placeholder="e.g., WH/01"
                      className="w-full px-3 py-2 text-sm border border-purple-200 rounded-lg focus:outline-none focus:border-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-purple-900 mb-1">Warehouse Name</label>
                    <input
                      type="text"
                      value={odooSettings.warehouse_name || ""}
                      onChange={(e) => setOdooSettings({ ...odooSettings, warehouse_name: e.target.value })}
                      placeholder="e.g., Main Warehouse"
                      className="w-full px-3 py-2 text-sm border border-purple-200 rounded-lg focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-purple-900 mb-1">Pricelist ID</label>
                    <input
                      type="text"
                      value={odooSettings.pricelist_id || ""}
                      onChange={(e) => setOdooSettings({ ...odooSettings, pricelist_id: e.target.value })}
                      placeholder="e.g., 1"
                      className="w-full px-3 py-2 text-sm border border-purple-200 rounded-lg focus:outline-none focus:border-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-purple-900 mb-1">Pricelist Name</label>
                    <input
                      type="text"
                      value={odooSettings.pricelist_name || ""}
                      onChange={(e) => setOdooSettings({ ...odooSettings, pricelist_name: e.target.value })}
                      placeholder="e.g., Public Pricelist"
                      className="w-full px-3 py-2 text-sm border border-purple-200 rounded-lg focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-purple-900 mb-1">POS Config ID</label>
                  <input
                    type="text"
                    value={odooSettings.pos_config_id || ""}
                    onChange={(e) => setOdooSettings({ ...odooSettings, pos_config_id: e.target.value })}
                    placeholder="e.g., pos_config_1"
                    className="w-full px-3 py-2 text-sm border border-purple-200 rounded-lg focus:outline-none focus:border-purple-500"
                  />
                </div>

                {/* Sync Options */}
                <div className="bg-white rounded-lg p-3 space-y-2">
                  <p className="text-xs font-semibold text-purple-900 mb-2">Sync Options</p>
                  
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={odooSettings.sync_products}
                      onChange={(e) => setOdooSettings({ ...odooSettings, sync_products: e.target.checked })}
                      className="w-4 h-4 text-purple-600 rounded focus:ring-purple-500"
                    />
                    <span className="text-sm text-purple-900">Sync {detail._kind === "restaurant" ? "Menu Items" : "Products"} from Odoo</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={odooSettings.sync_stock}
                      onChange={(e) => setOdooSettings({ ...odooSettings, sync_stock: e.target.checked })}
                      className="w-4 h-4 text-purple-600 rounded focus:ring-purple-500"
                    />
                    <span className="text-sm text-purple-900">Sync Stock from Odoo</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={odooSettings.send_orders}
                      onChange={(e) => setOdooSettings({ ...odooSettings, send_orders: e.target.checked })}
                      className="w-4 h-4 text-purple-600 rounded focus:ring-purple-500"
                    />
                    <span className="text-sm text-purple-900">Send Orders to Odoo</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={odooSettings.send_delivery_updates}
                      onChange={(e) => setOdooSettings({ ...odooSettings, send_delivery_updates: e.target.checked })}
                      className="w-4 h-4 text-purple-600 rounded focus:ring-purple-500"
                    />
                    <span className="text-sm text-purple-900">Send Delivery Updates to Odoo</span>
                  </label>
                </div>

                {/* Connection Test Result */}
                {connectionTestResult && (
                  <div className={`rounded-lg p-3 ${connectionTestResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                    <p className={`text-xs font-semibold mb-1 ${connectionTestResult.success ? 'text-green-900' : 'text-red-900'}`}>
                      {connectionTestResult.success ? '✓ Connection Test' : '✗ Connection Test Failed'}
                    </p>
                    <p className={`text-xs ${connectionTestResult.success ? 'text-green-700' : 'text-red-700'}`}>
                      {connectionTestResult.message}
                    </p>
                  </div>
                )}

                {/* Error Display */}
                {odooSettings.sync_error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <p className="text-xs font-semibold text-red-900 mb-1">Sync Error</p>
                    <p className="text-xs text-red-700">{odooSettings.sync_error}</p>
                  </div>
                )}
              </>
            )}

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-2 pt-2">
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="bg-purple-600 hover:bg-purple-700 text-white text-sm font-semibold py-2.5 rounded-full transition disabled:opacity-50"
              >
                {isSaving ? "Saving..." : "Save Settings"}
              </button>
              <button
                onClick={handleTestConnection}
                disabled={isTestingConnection || !odooSettings.enabled}
                className="bg-white border-2 border-purple-600 text-purple-600 hover:bg-purple-50 text-sm font-semibold py-2.5 rounded-full transition disabled:opacity-50 disabled:border-gray-300 disabled:text-gray-400"
              >
                {isTestingConnection ? "Testing..." : "Test Connection"}
              </button>
            </div>

            {odooSettings.enabled && (
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={handleViewLogs}
                  className="bg-white border border-purple-300 text-purple-700 hover:bg-purple-50 text-sm font-semibold py-2.5 rounded-full transition flex items-center justify-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  View Sync Logs
                </button>
                <button
                  onClick={handleRetryFailed}
                  disabled={failedLogsCount === 0}
                  className="bg-white border border-orange-300 text-orange-700 hover:bg-orange-50 text-sm font-semibold py-2.5 rounded-full transition disabled:opacity-50 disabled:border-gray-300 disabled:text-gray-400 flex items-center justify-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Retry Failed ({failedLogsCount})
                </button>
              </div>
            )}

            <p className="text-xs text-purple-600">
              ℹ️ This configuration will be used by your Odoo 18 module to communicate with JubaSquare.
            </p>
          </div>
        )}
      </div>

      {/* Sync Logs Modal */}
      {showLogsModal && (
        <OdooSyncLogsModal
          logs={syncLogs}
          loading={loadingLogs}
          onClose={() => setShowLogsModal(false)}
          onRefresh={loadSyncLogs}
          selectedLogs={selectedLogs}
          onSelectLog={(logId) => {
            setSelectedLogs(prev =>
              prev.includes(logId)
                ? prev.filter(id => id !== logId)
                : [...prev, logId]
            );
          }}
          onRetrySelected={handleRetryFailed}
        />
      )}
    </>
  );
}

// Sync Logs Modal Component
function OdooSyncLogsModal({ logs, loading, onClose, onRefresh, selectedLogs, onSelectLog, onRetrySelected }) {
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterType, setFilterType] = useState("all");

  const filteredLogs = logs.filter(log => {
    if (filterStatus !== "all" && log.status !== filterStatus) return false;
    if (filterType !== "all" && log.operation_type !== filterType) return false;
    return true;
  });

  const getStatusBadge = (status) => {
    const colors = {
      success: "bg-green-100 text-green-800",
      failed: "bg-red-100 text-red-800",
      pending: "bg-yellow-100 text-yellow-800",
      ignored: "bg-gray-100 text-gray-600",
      duplicate: "bg-blue-100 text-blue-800"
    };
    return colors[status] || "bg-gray-100 text-gray-600";
  };

  const getDirectionIcon = (direction) => {
    if (direction === "juba_to_odoo") {
      return <span title="JubaSquare → Odoo">→</span>;
    }
    return <span title="Odoo → JubaSquare">←</span>;
  };

  return (
    <div className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-4xl max-h-[85vh] overflow-hidden shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-600 to-blue-600 p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-display font-bold text-2xl">Odoo Sync Logs</h2>
              <p className="text-sm text-purple-100 mt-1">{logs.length} total operations</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-full hover:bg-white/20 transition"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Filters */}
          <div className="flex gap-3 mt-4">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-2 bg-white/20 backdrop-blur border border-white/30 rounded-lg text-sm text-white focus:outline-none focus:border-white/50"
            >
              <option value="all">All Status</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="pending">Pending</option>
              <option value="ignored">Ignored</option>
            </select>

            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-3 py-2 bg-white/20 backdrop-blur border border-white/30 rounded-lg text-sm text-white focus:outline-none focus:border-white/50"
            >
              <option value="all">All Types</option>
              <option value="product_sync">Product Sync</option>
              <option value="stock_sync">Stock Sync</option>
              <option value="order_sync">Order Sync</option>
              <option value="test_connection">Test Connection</option>
              <option value="webhook">Webhook</option>
            </select>

            <button
              onClick={onRefresh}
              disabled={loading}
              className="ml-auto px-4 py-2 bg-white/20 backdrop-blur hover:bg-white/30 border border-white/30 rounded-lg text-sm font-semibold transition disabled:opacity-50 flex items-center gap-2"
            >
              <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </div>
        </div>

        {/* Logs List */}
        <div className="overflow-y-auto max-h-[calc(85vh-200px)] p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p>No sync logs found</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredLogs.map((log) => (
                <div
                  key={log.id}
                  className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition"
                >
                  <div className="flex items-start gap-3">
                    {/* Checkbox for failed logs */}
                    {log.status === "failed" && (
                      <input
                        type="checkbox"
                        checked={selectedLogs.includes(log.id)}
                        onChange={() => onSelectLog(log.id)}
                        className="mt-1 w-4 h-4 text-purple-600 rounded focus:ring-purple-500"
                      />
                    )}

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full ${getStatusBadge(log.status)}`}>
                          {log.status}
                        </span>
                        <span className="text-xs text-gray-500">{getDirectionIcon(log.direction)}</span>
                        <span className="text-xs font-semibold text-gray-700">{log.operation_type}</span>
                        <span className="text-xs text-gray-400 ml-auto">
                          {new Date(log.created_at).toLocaleString()}
                        </span>
                      </div>

                      {log.error_message && (
                        <div className="bg-red-50 border border-red-200 rounded p-2 mb-2">
                          <p className="text-xs text-red-700 font-mono">{log.error_message}</p>
                        </div>
                      )}

                      <div className="text-xs text-gray-600 space-y-1">
                        {log.product_id && <p>Product: {log.product_id}</p>}
                        {log.order_id && <p>Order: {log.order_id}</p>}
                        {log.shop_id && <p>Shop: {log.shop_id}</p>}
                        {log.restaurant_id && <p>Restaurant: {log.restaurant_id}</p>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        {selectedLogs.length > 0 && (
          <div className="border-t border-gray-200 p-4 bg-gray-50">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-600">
                {selectedLogs.length} log(s) selected
              </p>
              <button
                onClick={onRetrySelected}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-semibold rounded-lg transition flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Retry Selected
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function AdminEmailsTab() {
  const [list, setList] = useState([]);
  const [email, setEmail] = useState("");

  const load = () => api.get("/admin/blocked-emails").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);

  const block = async (e) => {
    e.preventDefault();
    try { await api.post("/admin/block-email", { email }); toast.success("Email blocked"); setEmail(""); load(); }
    catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };
  const unblock = async (em) => { await api.delete(`/admin/block-email/${encodeURIComponent(em)}`); toast.success("Unblocked"); load(); };

  return (
    <div className="max-w-2xl">
      <form onSubmit={block} className="bg-white border border-[var(--js-border)] rounded-3xl p-6 mb-6 flex gap-3">
        <input type="email" required data-testid="block-email-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" className="js-input flex-1" />
        <button type="submit" data-testid="block-email-btn" className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-5 py-2.5 rounded-full">
          <Plus className="w-4 h-4" /> Block
        </button>
      </form>
      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-[var(--js-border)] bg-[var(--js-bg)]">
          <p className="text-xs uppercase tracking-wider text-[var(--js-text-secondary)] font-bold">Blocked emails ({list.length})</p>
        </div>
        {list.length === 0 ? (
          <p className="p-8 text-center text-[var(--js-text-secondary)]">No blocked emails.</p>
        ) : (
          <ul className="divide-y divide-[var(--js-border)]">
            {list.map((b) => (
              <li key={b.email} className="flex items-center justify-between p-4" data-testid={`blocked-${b.email}`}>
                <div>
                  <p className="font-semibold text-[var(--js-text)]">{b.email}</p>
                  <p className="text-xs text-[var(--js-text-secondary)]">Blocked {new Date(b.blocked_at).toLocaleDateString()}</p>
                </div>
                <button onClick={() => unblock(b.email)} data-testid={`unblock-${b.email}`} className="text-xs font-semibold bg-[var(--js-subtle)] hover:bg-[var(--js-border)] text-[var(--js-text)] px-3 py-1.5 rounded-full inline-flex items-center gap-1"><Trash2 className="w-3 h-3" /> Unblock</button>
              </li>
            ))}
          </ul>
        )}
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

// ---------------------------------------------------------------------------
// Cancellation Requests: admin approve or reject seller cancellation requests
// ---------------------------------------------------------------------------
function AdminCancellationsTab() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const { currency = "USD", exchangeRate = 600 } = useCart() || {};

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/cancel-requests");
      setRequests(data);
    } catch (e) {
      toast.error("Failed to load cancellation requests");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const approve = async (orderId) => {
    if (!window.confirm("Approve cancellation? The order will be cancelled and the customer notified.")) return;
    try {
      await api.post(`/admin/cancel-requests/${orderId}/approve`);
      toast.success("Cancellation approved");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to approve");
    }
  };

  const reject = async (orderId) => {
    const note = window.prompt("Optional note to seller/customer (why was rejection issued?):", "");
    if (note === null) return;
    try {
      await api.post(`/admin/cancel-requests/${orderId}/reject`, { admin_note: note });
      toast.success("Cancellation rejected — order restored");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to reject");
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display font-semibold text-xl text-[var(--js-text)]">Pending cancellation requests</h2>
        <button onClick={load} className="text-sm text-[#C84B31] hover:underline" data-testid="refresh-cancellations">Refresh</button>
      </div>

      {loading ? (
        <p className="text-sm text-[var(--js-text-secondary)]">Loading…</p>
      ) : requests.length === 0 ? (
        <div className="bg-white border border-[var(--js-border)] rounded-2xl p-10 text-center text-[var(--js-text-secondary)]" data-testid="empty-cancellations">
          No pending cancellation requests.
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map((o) => (
            <div key={o.id} className="bg-white border border-[var(--js-border)] rounded-2xl p-5" data-testid={`cancel-row-${o.id}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-bold text-[var(--js-text)]">
                    Order #{o.id.slice(0, 8)} <span className="text-[var(--js-text-secondary)] font-normal">— {o.restaurant_name}</span>
                  </p>
                  <p className="text-xs text-[var(--js-text-secondary)] mt-1">
                    Previous status: <span className="font-semibold text-[var(--js-text)]">{o.previous_status || "—"}</span>
                    {" · "}Customer: <span className="font-semibold text-[var(--js-text)]">{o.customer_name}</span>
                    {" · "}Total: <span className="font-semibold text-[var(--js-text)]">{formatPrice(o.total, exchangeRate, currency)}</span>
                  </p>
                  {o.cancel_reason && (
                    <p className="text-sm text-[var(--js-text)] mt-2 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                      <span className="font-semibold">Reason:</span> {o.cancel_reason}
                    </p>
                  )}
                  <p className="text-[10px] text-[var(--js-text-secondary)] mt-2">
                    Requested: {o.cancel_requested_at ? new Date(o.cancel_requested_at).toLocaleString() : "—"}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => reject(o.id)}
                    data-testid={`reject-cancel-${o.id}`}
                    className="bg-white border border-[var(--js-border)] hover:border-[var(--js-text)] text-[var(--js-text)] text-sm font-semibold px-4 py-2 rounded-full"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => approve(o.id)}
                    data-testid={`approve-cancel-${o.id}`}
                    className="bg-[#D90429] hover:bg-[#A60320] text-white text-sm font-semibold px-4 py-2 rounded-full"
                  >
                    Approve
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

