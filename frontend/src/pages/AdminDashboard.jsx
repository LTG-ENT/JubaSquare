import { useEffect, useState, useMemo } from "react";
import api, { formatUSD, formatPrice, formatDetail } from "@/lib/api";
import { useCart } from "@/context/CartContext";
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
import { Store, Mail, ShoppingBag, FileText, CheckCircle2, XCircle, Clock, Plus, Trash2, Percent, Eye, X, BarChart3, Settings as SettingsIcon, BookOpen, Sliders, PanelBottom, FolderTree, Ban, Activity, Truck, MapPin } from "lucide-react";
import { toast } from "sonner";

const TABS = [
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "performance", label: "Performance", icon: Activity },
  { id: "shops", label: "Shops", icon: Store },
  { id: "categories", label: "Categories", icon: FolderTree },
  { id: "delivery", label: "Delivery & Payouts", icon: Truck },
  { id: "delivery-pricing", label: "Delivery Pricing", icon: MapPin },
  { id: "invoices", label: "Invoices", icon: FileText },
  { id: "cancellations", label: "Cancellation Requests", icon: Ban },
  { id: "emails", label: "Blocked Emails", icon: Mail },
  { id: "orders", label: "All Orders", icon: ShoppingBag },
  { id: "pages", label: "Pages", icon: BookOpen },
  { id: "footer", label: "Footer", icon: PanelBottom },
  { id: "settings", label: "Settings", icon: Sliders },
  { id: "integrations", label: "Integrations", icon: SettingsIcon },
];

export default function AdminDashboard() {
  const [tab, setTab] = useState("analytics");
  const { currency, exchangeRate } = useCart(); // Get currency and exchange rate

  return (
    <div className="min-h-screen flex flex-col bg-[var(--js-bg)]">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-2">Admin Dashboard</p>
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[var(--js-text)]">Platform control</h1>

        <div className="mt-8 flex flex-wrap gap-2 border-b border-[var(--js-border)]">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                data-testid={`admin-tab-${t.id}`}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition ${
                  tab === t.id ? "border-[#C84B31] text-[#C84B31]" : "border-transparent text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"
                }`}
              >
                <Icon className="w-4 h-4" /> {t.label}
              </button>
            );
          })}
        </div>

        <div className="mt-8">
          {tab === "analytics" && <AdminAnalytics />}
          {tab === "performance" && <PerformanceMonitor />}
          {tab === "shops" && <AdminShopsTab />}
          {tab === "categories" && <AdminCategoriesTab />}
          {tab === "delivery" && <AdminDeliveryTab />}
          {tab === "delivery-pricing" && <AdminDeliveryPricingTab />}
          {tab === "invoices" && <AdminInvoicesPane />}
          {tab === "cancellations" && <AdminCancellationsTab />}
          {tab === "emails" && <AdminEmailsTab />}
          {tab === "orders" && <AdminOrdersTab />}
          {tab === "pages" && <AdminPagesTab />}
          {tab === "footer" && <AdminFooterTab />}
          {tab === "settings" && <AdminSettingsTab onGoToShop={() => setTab("shops")} />}
          {tab === "integrations" && <AdminIntegrations />}
        </div>
      </div>
      <Footer />
    </div>
  );
}

function AdminShopsTab() {
  const [shops, setShops] = useState([]);
  const [detail, setDetail] = useState(null);
  const [commissionDraft, setCommissionDraft] = useState("");
  const [invoiceFrequencyDraft, setInvoiceFrequencyDraft] = useState("");
  const [globalRate, setGlobalRate] = useState(0.10);
  const [globalFrequency, setGlobalFrequency] = useState("weekly");
  const [searchQuery, setSearchQuery] = useState("");

  const load = async () => {
    const [s, g] = await Promise.all([api.get("/shops?limit=200"), api.get("/admin/settings")]);
    setShops(s.data);
    setGlobalRate(g.data.commission_rate || 0.10);
    setGlobalFrequency(g.data.invoice_frequency || "weekly");
  };
  useEffect(() => { load(); }, []);

  const openDetail = (s) => {
    setDetail(s);
    setCommissionDraft(s.commission_rate != null ? String(s.commission_rate) : "");
    setInvoiceFrequencyDraft(s.invoice_frequency || "");
  };

  const verify = async (id) => { await api.put(`/admin/shops/${id}/verify`); toast.success("Verified"); load(); if (detail?.id === id) setDetail({ ...detail, verification: "Verified" }); };
  const reject = async (id) => { await api.put(`/admin/shops/${id}/reject`); toast.success("Rejected"); load(); if (detail?.id === id) setDetail({ ...detail, verification: "Rejected" }); };

  const saveCommission = async () => {
    const v = commissionDraft === "" ? null : parseFloat(commissionDraft);
    try {
      const { data } = await api.put(`/admin/shops/${detail.id}/commission`, { commission_rate: v });
      toast.success(v === null ? "Commission reset to global" : `Commission set to ${(v * 100).toFixed(1)}%`);
      await api.post("/admin/invoices/generate");
      setDetail(data);
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const saveInvoiceFrequency = async () => {
    const freq = invoiceFrequencyDraft === "" ? null : invoiceFrequencyDraft;
    try {
      const { data } = await api.put(`/admin/shops/${detail.id}/invoice-frequency`, { frequency: freq });
      toast.success(freq === null ? "Invoice frequency reset to global" : `Invoice frequency set to ${freq}`);
      setDetail(data);
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const filteredShops = useMemo(() => 
    shops.filter(s => 
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.area.toLowerCase().includes(searchQuery.toLowerCase())
    ),
    [shops, searchQuery]
  );

  const counts = useMemo(() => ({
    Verified: shops.filter((s) => s.verification === "Verified").length,
    Pending: shops.filter((s) => s.verification === "Pending").length,
    Rejected: shops.filter((s) => s.verification === "Rejected").length,
  }), [shops]);

  const frequencyOptions = [
    { value: "daily", label: "Daily" },
    { value: "weekly", label: "Weekly" },
    { value: "monthly", label: "Monthly" },
    { value: "quarterly", label: "Quarterly" },
    { value: "yearly", label: "Yearly" },
  ];

  return (
    <div>
      <div className="grid grid-cols-3 gap-3 mb-6">
        <Stat label="Verified" value={counts.Verified} color="#2D6A4F" />
        <Stat label="Pending" value={counts.Pending} color="#E9C46A" />
        <Stat label="Rejected" value={counts.Rejected} color="#D90429" />
      </div>

      {/* Search Bar */}
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search shops by name or area..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-4 py-3 border border-[var(--js-border)] rounded-xl text-sm focus:outline-none focus:border-[#C84B31]"
        />
      </div>

      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--js-bg)] text-[var(--js-text-secondary)] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-4 font-bold">Shop</th>
                <th className="text-left p-4 font-bold hidden lg:table-cell">Area</th>
                <th className="text-left p-4 font-bold hidden md:table-cell">Commission</th>
                <th className="text-left p-4 font-bold">Status</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {filteredShops.map((s) => (
                <tr key={s.id} className="border-t border-[var(--js-border)] hover:bg-[var(--js-bg)] cursor-pointer" onClick={() => openDetail(s)} data-testid={`admin-shop-row-${s.id}`}>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <img src={s.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                      <p className="font-semibold text-[var(--js-text)]">{s.name}</p>
                    </div>
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
                      <button onClick={() => verify(s.id)} data-testid={`verify-shop-${s.id}`} className="text-xs font-semibold bg-[#2D6A4F] hover:bg-[#1B4332] text-white px-3 py-1.5 rounded-full">Verify</button>
                      <button onClick={() => reject(s.id)} data-testid={`reject-shop-${s.id}`} className="text-xs font-semibold bg-[#D90429]/10 text-[#D90429] hover:bg-[#D90429] hover:text-white px-3 py-1.5 rounded-full transition">Reject</button>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredShops.length === 0 && (
                <tr><td colSpan={5} className="p-8 text-center text-[var(--js-text-secondary)]">
                  {searchQuery ? `No shops found matching "${searchQuery}"` : "No shops."}
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
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AdminInvoicesTab() {
  const [invoices, setInvoices] = useState([]);
  const [filter, setFilter] = useState("all");
  const [commissionRate, setCommissionRate] = useState(0.10);
  const [detail, setDetail] = useState(null);

  const load = async () => {
    const q = filter === "all" ? "" : `?status=${filter === "paid" ? "Paid" : "Unpaid"}`;
    const [inv, s] = await Promise.all([
      api.get(`/admin/invoices${q}`),
      api.get("/admin/settings"),
    ]);
    setInvoices(inv.data);
    setCommissionRate(s.data.commission_rate || 0.10);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const setStatus = async (id, status) => {
    await api.put(`/admin/invoices/${id}/status`, { status });
    toast.success(`Marked as ${status}`);
    load();
  };

  const regenerate = async () => {
    await api.post("/admin/invoices/generate");
    toast.success("Invoices regenerated");
    load();
  };

  const saveRate = async (v) => {
    setCommissionRate(v);
    await api.put("/admin/settings", { commission_rate: parseFloat(v) });
    toast.success("Commission rate updated — regenerating invoices");
    await api.post("/admin/invoices/generate");
    load();
  };

  const totalSales = invoices.reduce((s, i) => s + (i.total_sales || 0), 0);
  const totalCommission = invoices.reduce((s, i) => s + (i.commission || 0), 0);
  const unpaidAmount = invoices.filter((i) => i.status === "Unpaid").reduce((s, i) => s + (i.commission || 0), 0);

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="Invoices" value={invoices.length} color="#1A1A1A" />
        <Stat label="Total Sales" value={formatPrice(totalSales, exchangeRate, currency)} color="#2D6A4F" />
        <Stat label="Commission" value={formatPrice(totalCommission, exchangeRate, currency)} color="#C84B31" />
        <Stat label="Unpaid" value={formatPrice(unpaidAmount, exchangeRate, currency)} color="#D90429" />
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex items-center gap-2 bg-white border border-[var(--js-border)] rounded-full px-3 py-2">
          <Percent className="w-4 h-4 text-[var(--js-text-secondary)]" />
          <span className="text-xs font-semibold text-[var(--js-text-secondary)]">Commission</span>
          <input
            type="number" step="0.01" min="0" max="1"
            value={commissionRate}
            onChange={(e) => setCommissionRate(parseFloat(e.target.value) || 0)}
            onBlur={(e) => saveRate(parseFloat(e.target.value) || 0)}
            data-testid="commission-rate-input"
            className="w-16 bg-transparent text-sm font-bold focus:outline-none"
          />
          <span className="text-xs text-[var(--js-text-secondary)]">({(commissionRate * 100).toFixed(1)}%)</span>
        </div>

        <select value={filter} onChange={(e) => setFilter(e.target.value)} data-testid="invoice-filter-select" className="bg-white border border-[var(--js-border)] rounded-full px-4 py-2 text-sm font-semibold focus:outline-none focus:border-[#C84B31]">
          <option value="all">All invoices</option>
          <option value="paid">Paid only</option>
          <option value="unpaid">Unpaid only</option>
        </select>

        <button onClick={regenerate} data-testid="regenerate-invoices-btn" className="ml-auto bg-[var(--js-subtle)] hover:bg-[var(--js-border)] text-[var(--js-text)] text-sm font-semibold px-4 py-2 rounded-full">
          🔄 Regenerate
        </button>
        <button
          onClick={async () => {
            try {
              const { data } = await api.post("/admin/notifications/run-reminders");
              toast.success(`Reminders sent: ${data.seller_reminders} seller, ${data.admin_reminders} admin`);
            } catch (e) {
              toast.error("Failed to send reminders");
            }
          }}
          data-testid="send-reminders-btn"
          className="bg-[#E9C46A] hover:bg-[#D6B45F] text-[#1A1A1A] text-sm font-semibold px-4 py-2 rounded-full"
        >
          🔔 Send unpaid reminders
        </button>
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
                <th className="text-left p-4 font-bold">Status</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-t border-[var(--js-border)]" data-testid={`invoice-row-${inv.id}`}>
                  <td className="p-4 font-semibold text-[var(--js-text)]">{inv.shop_name}</td>
                  <td className="p-4 text-[var(--js-text-secondary)] hidden sm:table-cell text-xs">{inv.week_label}</td>
                  <td className="p-4 font-bold">{formatPrice(inv.total_sales, exchangeRate, currency)}</td>
                  <td className="p-4 hidden md:table-cell">
                    <p className="font-semibold text-[#C84B31]">{formatPrice(inv.commission, exchangeRate, currency)}</p>
                    <p className="text-[10px] text-[var(--js-text-secondary)]">{(inv.commission_rate * 100).toFixed(1)}%</p>
                  </td>
                  <td className="p-4">
                    {inv.status === "Paid" ? (
                      <span className="inline-flex items-center gap-1 bg-[#2D6A4F]/10 text-[#2D6A4F] text-xs font-bold px-2 py-1 rounded-full" data-testid={`invoice-status-${inv.id}`}><CheckCircle2 className="w-3 h-3" /> Paid</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 bg-[#D90429]/10 text-[#D90429] text-xs font-bold px-2 py-1 rounded-full" data-testid={`invoice-status-${inv.id}`}><Clock className="w-3 h-3" /> Unpaid</span>
                    )}
                  </td>
                  <td className="p-4 text-right">
                    <div className="inline-flex gap-1">
                      <button onClick={() => setDetail(inv)} data-testid={`invoice-view-${inv.id}`} className="p-2 hover:bg-[var(--js-subtle)] rounded-full" title="View details"><Eye className="w-3.5 h-3.5" /></button>
                      {inv.status === "Unpaid" ? (
                        <button onClick={() => setStatus(inv.id, "Paid")} data-testid={`mark-paid-${inv.id}`} className="text-xs font-semibold bg-[#2D6A4F] hover:bg-[#1B4332] text-white px-3 py-1.5 rounded-full">Mark Paid</button>
                      ) : (
                        <button onClick={() => setStatus(inv.id, "Unpaid")} data-testid={`mark-unpaid-${inv.id}`} className="text-xs font-semibold bg-[var(--js-subtle)] text-[var(--js-text)] hover:bg-[var(--js-border)] px-3 py-1.5 rounded-full">Mark Unpaid</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {invoices.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-[var(--js-text-secondary)]">No invoices yet. Orders generate weekly invoices automatically.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {detail && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-3xl p-6 w-full max-w-md shadow-2xl" onClick={(e) => e.stopPropagation()} data-testid="invoice-detail-modal">
            <h3 className="font-display font-bold text-xl">{detail.shop_name}</h3>
            <p className="text-sm text-[var(--js-text-secondary)]">{detail.week_label}</p>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-[var(--js-text-secondary)]">Total Sales</dt><dd className="font-bold">{formatPrice(detail.total_sales, exchangeRate, currency)}</dd></div>
              <div className="flex justify-between"><dt className="text-[var(--js-text-secondary)]">Order count</dt><dd className="font-bold">{detail.order_count}</dd></div>
              <div className="flex justify-between"><dt className="text-[var(--js-text-secondary)]">Commission ({(detail.commission_rate * 100).toFixed(1)}%)</dt><dd className="font-bold text-[#C84B31]">{formatPrice(detail.commission, exchangeRate, currency)}</dd></div>
              <div className="flex justify-between border-t border-[var(--js-border)] pt-2"><dt className="font-semibold">Amount owed</dt><dd className="font-display font-bold text-lg">{formatPrice(detail.amount_owed, exchangeRate, currency)}</dd></div>
              <div className="flex justify-between"><dt className="text-[var(--js-text-secondary)]">Status</dt><dd className="font-bold">{detail.status}</dd></div>
            </dl>
            <button onClick={() => setDetail(null)} className="mt-5 w-full bg-[#1A1A1A] text-white text-sm font-semibold py-2.5 rounded-full">Close</button>
          </div>
        </div>
      )}
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

function AdminOrdersTab() {
  const [orders, setOrders] = useState([]);
  const load = () => api.get("/orders?limit=200").then((r) => setOrders(r.data));
  useEffect(() => { load(); }, []);

  const updateStatus = async (id, status) => { await api.put(`/orders/${id}/status`, { status }); toast.success("Status updated"); load(); };

  const total = orders.reduce((s, o) => s + (o.subtotal_usd || 0), 0);

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="Total Orders" value={orders.length} color="#1A1A1A" />
        <Stat label="Pending" value={orders.filter((o) => o.status === "Pending").length} color="#E9C46A" />
        <Stat label="In Progress" value={orders.filter((o) => o.status === "In Progress").length} color="#2A9D8F" />
        <Stat label="Revenue" value={formatPrice(total, exchangeRate, currency)} color="#C84B31" />
      </div>

      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--js-bg)] text-[var(--js-text-secondary)] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-4 font-bold">Order</th>
                <th className="text-left p-4 font-bold hidden sm:table-cell">Customer</th>
                <th className="text-left p-4 font-bold hidden md:table-cell">Type</th>
                <th className="text-left p-4 font-bold">Total</th>
                <th className="text-left p-4 font-bold">Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className="border-t border-[var(--js-border)]" data-testid={`admin-order-${o.id}`}>
                  <td className="p-4">
                    <p className="font-semibold text-[var(--js-text)]">#{o.id.slice(0, 8).toUpperCase()}</p>
                    <p className="text-xs text-[var(--js-text-secondary)]">{new Date(o.created_at).toLocaleDateString()}</p>
                  </td>
                  <td className="p-4 hidden sm:table-cell">
                    <p className="font-semibold">{o.customer_name}</p>
                    <p className="text-xs text-[var(--js-text-secondary)]">{o.area}</p>
                  </td>
                  <td className="p-4 hidden md:table-cell text-[var(--js-text-secondary)] capitalize">{o.order_kind}</td>
                  <td className="p-4 font-bold">{formatPrice(o.subtotal_usd, exchangeRate, currency)}</td>
                  <td className="p-4">
                    <select value={o.status} onChange={(e) => updateStatus(o.id, e.target.value)} data-testid={`admin-order-status-${o.id}`} className="bg-white border border-[var(--js-border)] rounded-full px-3 py-1.5 text-xs font-semibold focus:border-[#C84B31] focus:outline-none">
                      <option>Pending</option><option>In Progress</option><option>Delivered</option>
                    </select>
                  </td>
                </tr>
              ))}
              {orders.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-[var(--js-text-secondary)]">No orders.</td></tr>}
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

// ---------------------------------------------------------------------------
// Invoices pane: sub-tab toggle between Shop invoices and Restaurant invoices.
// Kept as a wrapper so the existing AdminInvoicesTab can stay untouched.
// ---------------------------------------------------------------------------
function AdminInvoicesPane() {
  const [kind, setKind] = useState("shop");
  return (
    <div>
      <div className="inline-flex items-center bg-[var(--js-subtle)] rounded-full p-1 mb-6" data-testid="invoice-kind-toggle">
        <button
          onClick={() => setKind("shop")}
          data-testid="invoice-kind-shop"
          className={`px-5 py-2 text-sm font-semibold rounded-full transition ${
            kind === "shop" ? "bg-white shadow text-[var(--js-text)]" : "text-[var(--js-text-secondary)]"
          }`}
        >
          Shop invoices
        </button>
        <button
          onClick={() => setKind("restaurant")}
          data-testid="invoice-kind-restaurant"
          className={`px-5 py-2 text-sm font-semibold rounded-full transition ${
            kind === "restaurant" ? "bg-white shadow text-[var(--js-text)]" : "text-[var(--js-text-secondary)]"
          }`}
        >
          Restaurant invoices
        </button>
      </div>
      {kind === "shop" ? <AdminInvoicesTab /> : <AdminRestaurantInvoicesTab />}
    </div>
  );
}

function AdminRestaurantInvoicesTab() {
  const [invoices, setInvoices] = useState([]);
  const [filter, setFilter] = useState("all");

  const load = async () => {
    const q = filter === "all" ? "" : `?status=${filter === "paid" ? "Paid" : "Unpaid"}`;
    const { data } = await api.get(`/admin/restaurant-invoices${q}`);
    setInvoices(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const regenerate = async () => {
    await api.post("/admin/restaurant-invoices/generate");
    toast.success("Restaurant invoices regenerated");
    load();
  };

  const setStatus = async (id, status) => {
    await api.put(`/admin/restaurant-invoices/${id}/status`, { status });
    toast.success(`Marked as ${status}`);
    load();
  };

  const totalSales = invoices.reduce((s, i) => s + (i.total_sales || 0), 0);
  const totalCommission = invoices.reduce((s, i) => s + (i.commission || 0), 0);
  const unpaidAmount = invoices.filter((i) => i.status === "Unpaid").reduce((s, i) => s + (i.commission || 0), 0);

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="Restaurant Invoices" value={invoices.length} color="#1A1A1A" />
        <Stat label="Food Sales (commissionable)" value={formatPrice(totalSales, exchangeRate, currency)} color="#2D6A4F" />
        <Stat label="Commission" value={formatPrice(totalCommission, exchangeRate, currency)} color="#C84B31" />
        <Stat label="Unpaid" value={formatPrice(unpaidAmount, exchangeRate, currency)} color="#D90429" />
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select value={filter} onChange={(e) => setFilter(e.target.value)} data-testid="restaurant-invoice-filter-select" className="bg-white border border-[var(--js-border)] rounded-full px-4 py-2 text-sm font-semibold focus:outline-none focus:border-[#C84B31]">
          <option value="all">All</option>
          <option value="paid">Paid only</option>
          <option value="unpaid">Unpaid only</option>
        </select>
        <button onClick={regenerate} data-testid="regenerate-restaurant-invoices-btn" className="ml-auto bg-[var(--js-subtle)] hover:bg-[var(--js-border)] text-[var(--js-text)] text-sm font-semibold px-4 py-2 rounded-full">
          🔄 Regenerate from completed orders
        </button>
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
                <th className="text-left p-4 font-bold">Status</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-t border-[var(--js-border)]" data-testid={`restaurant-invoice-row-${inv.id}`}>
                  <td className="p-4 font-semibold text-[var(--js-text)]">{inv.restaurant_name}</td>
                  <td className="p-4 text-[var(--js-text-secondary)] hidden sm:table-cell text-xs">{inv.week_label}</td>
                  <td className="p-4 font-bold">{formatPrice(inv.total_sales, exchangeRate, currency)}</td>
                  <td className="p-4 hidden md:table-cell">
                    <p className="font-semibold text-[#C84B31]">{formatPrice(inv.commission, exchangeRate, currency)}</p>
                    <p className="text-[10px] text-[var(--js-text-secondary)]">{(inv.commission_rate * 100).toFixed(1)}%</p>
                  </td>
                  <td className="p-4">
                    {inv.status === "Paid" ? (
                      <span className="inline-flex items-center gap-1 bg-[#2D6A4F]/10 text-[#2D6A4F] text-xs font-bold px-2 py-1 rounded-full"><CheckCircle2 className="w-3 h-3" /> Paid</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 bg-[#D90429]/10 text-[#D90429] text-xs font-bold px-2 py-1 rounded-full"><Clock className="w-3 h-3" /> Unpaid</span>
                    )}
                  </td>
                  <td className="p-4 text-right">
                    {inv.status === "Unpaid" ? (
                      <button
                        onClick={() => setStatus(inv.id, "Paid")}
                        data-testid={`mark-paid-restaurant-${inv.id}`}
                        className="bg-[#2D6A4F] hover:bg-[#245940] text-white text-xs font-bold px-3 py-1.5 rounded-full"
                      >
                        Mark paid
                      </button>
                    ) : (
                      <button
                        onClick={() => setStatus(inv.id, "Unpaid")}
                        data-testid={`mark-unpaid-restaurant-${inv.id}`}
                        className="bg-[var(--js-subtle)] hover:bg-[var(--js-border)] text-[var(--js-text)] text-xs font-bold px-3 py-1.5 rounded-full"
                      >
                        Mark unpaid
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {invoices.length === 0 && (
                <tr><td colSpan={6} className="p-10 text-center text-[var(--js-text-secondary)]">
                  No restaurant invoices yet. They auto-generate when restaurant orders are marked completed in the Kitchen Dashboard.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cancellation Requests: admin approve or reject seller cancellation requests
// ---------------------------------------------------------------------------
function AdminCancellationsTab() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);

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

