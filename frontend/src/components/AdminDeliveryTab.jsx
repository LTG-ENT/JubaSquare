import { useEffect, useState, useCallback } from "react";
import api, { formatUSD, formatDetail, formatPrice } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { toast } from "sonner";
import {
  Truck,
  UserPlus,
  Trash2,
  Coins,
  CheckCircle2,
  AlertTriangle,
  Wallet,
  Eye,
  X,
  Play,
  Pause,
} from "lucide-react";

const SUB_TABS = [
  { id: "drivers", label: "Drivers", icon: Truck },
  { id: "assignments", label: "Assignments", icon: UserPlus },
  { id: "cash", label: "Cash Handovers", icon: Coins },
  { id: "payouts", label: "Payouts", icon: Wallet },
  { id: "disputes", label: "Disputes", icon: AlertTriangle },
];

const PILL = {
  unassigned: "bg-gray-100 text-gray-700",
  assigned: "bg-blue-100 text-blue-700",
  pending_pickup: "bg-blue-100 text-blue-700",
  picked_up: "bg-amber-100 text-amber-700",
  out_for_delivery: "bg-amber-100 text-amber-800",
  delivered: "bg-emerald-100 text-emerald-700",
  delivery_failed: "bg-red-100 text-red-700",
  return_to_seller_pending: "bg-orange-100 text-orange-700",
  returned_to_seller: "bg-gray-100 text-gray-700",
  not_ready: "bg-gray-100 text-gray-600",
  ready_for_payout: "bg-emerald-100 text-emerald-700",
  pending_payout: "bg-amber-100 text-amber-700",
  paid: "bg-emerald-200 text-emerald-800",
  paused: "bg-orange-100 text-orange-700",
  cancelled: "bg-red-100 text-red-700",
  pending_collection: "bg-gray-100 text-gray-700",
  collected_by_driver: "bg-amber-100 text-amber-700",
  received_by_admin: "bg-emerald-100 text-emerald-700",
  pending: "bg-amber-100 text-amber-700",
  received: "bg-emerald-100 text-emerald-700",
  none: "bg-gray-100 text-gray-700",
  opened: "bg-red-100 text-red-700",
  resolved: "bg-emerald-100 text-emerald-700",
};

function Pill({ value }) {
  const cls = PILL[value] || "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold ${cls}`}>
      {String(value || "—").replace(/_/g, " ")}
    </span>
  );
}

export default function AdminDeliveryTab() {
  const [sub, setSub] = useState("drivers");
  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-6 border-b border-[var(--js-border)]">
        {SUB_TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setSub(t.id)}
              data-testid={`delivery-sub-${t.id}`}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold border-b-2 ${
                sub === t.id
                  ? "border-[#C84B31] text-[#C84B31]"
                  : "border-transparent text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"
              }`}
            >
              <Icon className="w-4 h-4" /> {t.label}
            </button>
          );
        })}
      </div>

      {sub === "drivers" && <DriversPane />}
      {sub === "assignments" && <AssignmentsPane />}
      {sub === "cash" && <CashHandoversPane />}
      {sub === "payouts" && <PayoutsPane />}
      {sub === "disputes" && <DisputesPane />}
    </div>
  );
}

// ---------------- DRIVERS ----------------
function DriversPane() {
  const [list, setList] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", phone: "" });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get("/admin/drivers");
      setList(r.data || []);
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail) || "Failed to load drivers"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/admin/drivers", form);
      toast.success("Driver created");
      setShowForm(false);
      setForm({ name: "", email: "", password: "", phone: "" });
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to create driver");
    } finally { setSaving(false); }
  };

  const toggle = async (d) => {
    try {
      await api.put(`/admin/drivers/${d.id}/status`, { is_active: !d.is_active });
      load();
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };

  const remove = async (d) => {
    if (!confirm(`Delete driver ${d.name}?`)) return;
    try {
      await api.delete(`/admin/drivers/${d.id}`);
      toast.success("Driver deleted");
      load();
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-[var(--js-text-secondary)]">{list.length} driver(s)</p>
        <button onClick={() => setShowForm(true)} data-testid="new-driver-btn" className="bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-4 py-2 rounded-full flex items-center gap-2">
          <UserPlus className="w-4 h-4" /> New driver
        </button>
      </div>

      {showForm && (
        <form onSubmit={submit} className="bg-white border border-[var(--js-border)] rounded-2xl p-5 mb-6 grid sm:grid-cols-2 gap-3">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="Full name" data-testid="driver-name" className="px-3 py-2 border border-[var(--js-border)] rounded-lg" />
          <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required type="email" placeholder="Email" data-testid="driver-email" className="px-3 py-2 border border-[var(--js-border)] rounded-lg" />
          <input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={6} placeholder="Password (min 6)" data-testid="driver-password" className="px-3 py-2 border border-[var(--js-border)] rounded-lg" />
          <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="Phone (optional)" data-testid="driver-phone" className="px-3 py-2 border border-[var(--js-border)] rounded-lg" />
          <div className="sm:col-span-2 flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm font-semibold text-[var(--js-text-secondary)]">Cancel</button>
            <button type="submit" disabled={saving} className="bg-[#1A1A1A] text-white text-sm font-semibold px-4 py-2 rounded-full">{saving ? "Saving…" : "Create driver"}</button>
          </div>
        </form>
      )}

      <div className="overflow-x-auto bg-white border border-[var(--js-border)] rounded-2xl">
        <table className="min-w-full text-sm">
          <thead className="bg-[var(--js-bg)] text-xs uppercase tracking-wide text-[var(--js-text-secondary)]">
            <tr>
              <th className="text-left px-3 py-3">Name</th>
              <th className="text-left px-3 py-3">Email</th>
              <th className="text-left px-3 py-3">Phone</th>
              <th className="text-left px-3 py-3">Active deliveries</th>
              <th className="text-left px-3 py-3">Cash pending</th>
              <th className="text-left px-3 py-3">Status</th>
              <th className="text-right px-3 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {list.map((d) => (
              <tr key={d.id} className="border-t border-[var(--js-border)]">
                <td className="px-3 py-2 font-semibold">{d.name}</td>
                <td className="px-3 py-2">{d.email}</td>
                <td className="px-3 py-2">{d.phone || "—"}</td>
                <td className="px-3 py-2">{d.active_deliveries || 0}</td>
                <td className="px-3 py-2 font-semibold">{formatPrice(d.cash_pending_handover_usd || 0, exchangeRate, currency)}</td>
                <td className="px-3 py-2">{d.is_active ? <Pill value="resolved" /> : <Pill value="opened" />}</td>
                <td className="px-3 py-2 text-right space-x-1">
                  <button onClick={() => toggle(d)} title={d.is_active ? "Disable" : "Enable"} className="text-xs px-2 py-1 rounded-full hover:bg-gray-100">
                    {d.is_active ? <Pause className="w-4 h-4 inline" /> : <Play className="w-4 h-4 inline" />}
                  </button>
                  <button onClick={() => remove(d)} className="text-xs px-2 py-1 rounded-full hover:bg-red-50 text-red-600">
                    <Trash2 className="w-4 h-4 inline" />
                  </button>
                </td>
              </tr>
            ))}
            {list.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-[var(--js-text-secondary)]">No drivers yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------- ASSIGNMENTS ----------------
function AssignmentsPane() {
  const [splits, setSplits] = useState([]);
  const [restOrders, setRestOrders] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [filter, setFilter] = useState(""); // status filter
  const [actingIds, setActingIds] = useState(new Set());
  const { currency = "USD", exchangeRate = 600 } = useCart() || {};

  const load = useCallback(async () => {
    try {
      const [s, r, d] = await Promise.all([
        api.get(`/admin/order-splits${filter ? `?status=${filter}` : ""}`),
        api.get(`/admin/restaurant-orders-cod${filter ? `?status=${filter}` : ""}`),
        api.get("/admin/drivers"),
      ]);
      setSplits(s.data || []);
      setRestOrders(r.data || []);
      setDrivers(d.data || []);
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail)); }
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  const assign = async (row) => {
    if (actingIds.has(row.id)) return;
    const id = prompt(
      `Pick a driver to assign:\n\n${drivers.map((d, i) => `${i + 1}. ${d.name} (${d.email})`).join("\n")}\n\nEnter the driver number:`
    );
    const idx = parseInt(id, 10) - 1;
    if (isNaN(idx) || idx < 0 || !drivers[idx]) return;
    setActingIds((p) => { const n = new Set(p); n.add(row.id); return n; });
    try {
      const base = row._kind === "rest" ? `/admin/restaurant-orders/${row.id}` : `/admin/order-splits/${row.id}`;
      await api.post(`${base}/assign-driver`, { driver_id: drivers[idx].id });
      toast.success(`Assigned to ${drivers[idx].name}`);
      load();
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
    finally { setActingIds((p) => { const n = new Set(p); n.delete(row.id); return n; }); }
  };

  const all = [
    ...splits.map((s) => ({ ...s, _kind: "split" })),
    ...restOrders.map((r) => ({ ...r, _kind: "rest" })),
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <select value={filter} onChange={(e) => setFilter(e.target.value)} data-testid="assign-filter" className="px-3 py-2 border border-[var(--js-border)] rounded-lg text-sm">
          <option value="">All statuses</option>
          <option value="unassigned">Unassigned</option>
          <option value="assigned">Assigned</option>
          <option value="pending_pickup">Pending pickup</option>
          <option value="picked_up">Picked up</option>
          <option value="out_for_delivery">Out for delivery</option>
          <option value="delivered">Delivered</option>
          <option value="delivery_failed">Delivery failed</option>
        </select>
        <p className="text-sm text-[var(--js-text-secondary)]">{all.length} item(s)</p>
      </div>

      <div className="overflow-x-auto bg-white border border-[var(--js-border)] rounded-2xl">
        <table className="min-w-full text-sm">
          <thead className="bg-[var(--js-bg)] text-xs uppercase tracking-wide text-[var(--js-text-secondary)]">
            <tr>
              <th className="text-left px-3 py-3">Type / ID</th>
              <th className="text-left px-3 py-3">Shop</th>
              <th className="text-left px-3 py-3">Customer</th>
              <th className="text-left px-3 py-3">Total</th>
              <th className="text-left px-3 py-3">Driver</th>
              <th className="text-left px-3 py-3">Delivery</th>
              <th className="text-left px-3 py-3">Payment</th>
              <th className="text-right px-3 py-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {all.map((row) => (
              <tr key={row.id} className="border-t border-[var(--js-border)]">
                <td className="px-3 py-2 font-mono text-xs">{row._kind === "rest" ? "R" : "M"} • {row.id.slice(0, 8)}</td>
                <td className="px-3 py-2">{row.shop_name || row.restaurant_name}</td>
                <td className="px-3 py-2">
                  <div className="font-medium">{row.customer_name}</div>
                  <div className="text-xs text-[var(--js-text-secondary)]">{row.customer_phone || row.phone} • {row.customer_area || row.area}</div>
                </td>
                <td className="px-3 py-2 font-semibold">{formatPrice(row.order_total_usd, exchangeRate, currency)}</td>
                <td className="px-3 py-2">{row.driver_name || "—"}</td>
                <td className="px-3 py-2"><Pill value={row.delivery_status} /></td>
                <td className="px-3 py-2"><Pill value={row.payment_status} /></td>
                <td className="px-3 py-2 text-right">
                  {!row.driver_id || row.delivery_status === "unassigned" || row.delivery_status === "delivery_failed" ? (
                    <button
                      onClick={() => assign(row)}
                      disabled={actingIds.has(row.id)}
                      data-testid={`assign-${row.id.slice(0,8)}`}
                      className="bg-[#1A1A1A] hover:bg-black disabled:bg-[#1A1A1A]/40 disabled:cursor-not-allowed text-white text-xs font-semibold px-3 py-1.5 rounded-full"
                    >
                      {actingIds.has(row.id) ? "Assigning…" : "Assign driver"}
                    </button>
                  ) : (
                    <span className="text-xs text-[var(--js-text-secondary)]">Assigned</span>
                  )}
                </td>
              </tr>
            ))}
            {all.length === 0 && <tr><td colSpan={8} className="text-center py-8 text-[var(--js-text-secondary)]">No orders found.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------- CASH HANDOVERS ----------------
function CashHandoversPane() {
  const [data, setData] = useState({ splits: [], restaurant_orders: [], totals: {} });
  const [actingIds, setActingIds] = useState(new Set());
  const { currency = "USD", exchangeRate = 600 } = useCart() || {};
  
  const load = useCallback(async () => {
    try {
      const r = await api.get("/admin/cash-handovers");
      setData(r.data || { splits: [], restaurant_orders: [], totals: {} });
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const receive = async (row) => {
    if (actingIds.has(row.id)) return;
    const base = row._kind === "rest" ? `/admin/cash-handovers/restaurant-order/${row.id}/receive` : `/admin/cash-handovers/split/${row.id}/receive`;
    if (!confirm(`Confirm cash of ${row.order_total_usd?.toFixed?.(2)} USD received from driver ${row.driver_name || row.driver_id}?`)) return;
    setActingIds((p) => { const n = new Set(p); n.add(row.id); return n; });
    try {
      await api.post(base);
      toast.success("Cash received");
      load();
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
    finally { setActingIds((p) => { const n = new Set(p); n.delete(row.id); return n; }); }
  };

  const all = [
    ...(data.splits || []).map((s) => ({ ...s, _kind: "split" })),
    ...(data.restaurant_orders || []).map((r) => ({ ...r, _kind: "rest" })),
  ];

  const totalPending = (data.totals?.splits_usd || 0) + (data.totals?.restaurant_orders_usd || 0);

  return (
    <div>
      <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 mb-6 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wider font-bold text-amber-800">Total cash with drivers</p>
          <p className="text-2xl font-bold text-amber-900">{formatPrice(totalPending, exchangeRate, currency)}</p>
        </div>
        <Coins className="w-8 h-8 text-amber-700" />
      </div>

      <div className="overflow-x-auto bg-white border border-[var(--js-border)] rounded-2xl">
        <table className="min-w-full text-sm">
          <thead className="bg-[var(--js-bg)] text-xs uppercase tracking-wide text-[var(--js-text-secondary)]">
            <tr>
              <th className="text-left px-3 py-3">Order</th>
              <th className="text-left px-3 py-3">Driver</th>
              <th className="text-left px-3 py-3">Seller / Shop</th>
              <th className="text-left px-3 py-3">Customer</th>
              <th className="text-left px-3 py-3">Amount</th>
              <th className="text-left px-3 py-3">Collected at</th>
              <th className="text-right px-3 py-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {all.map((r) => (
              <tr key={r.id} className="border-t border-[var(--js-border)]">
                <td className="px-3 py-2 font-mono text-xs">{r._kind === "rest" ? "R" : "M"} • {r.id.slice(0, 8)}</td>
                <td className="px-3 py-2">{r.driver_name || "—"}</td>
                <td className="px-3 py-2">{r.shop_name || r.restaurant_name}</td>
                <td className="px-3 py-2">{r.customer_name}</td>
                <td className="px-3 py-2 font-semibold">{formatPrice(r.order_total_usd, exchangeRate, currency)}</td>
                <td className="px-3 py-2 text-xs">{(r.cash_collected_at || "").slice(0, 16).replace("T", " ")}</td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => receive(r)}
                    disabled={actingIds.has(r.id)}
                    data-testid={`cash-receive-${r.id.slice(0,8)}`}
                    className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-300 disabled:cursor-not-allowed text-white text-xs font-semibold px-3 py-1.5 rounded-full flex items-center gap-1 inline-flex"
                  >
                    <CheckCircle2 className="w-3 h-3" /> {actingIds.has(r.id) ? "Receiving…" : "Mark received"}
                  </button>
                </td>
              </tr>
            ))}
            {all.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-[var(--js-text-secondary)]">No pending cash handovers.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------- PAYOUTS ----------------
function PayoutsPane() {
  const [payouts, setPayouts] = useState([]);
  const [detail, setDetail] = useState(null);
  const [filter, setFilter] = useState("");
  const [generating, setGenerating] = useState(false);
  const [payingIds, setPayingIds] = useState(new Set());
  const [otpModal, setOtpModal] = useState(null); // { payout, otp?, confirming? }
  const { currency = "USD", exchangeRate = 600 } = useCart() || {}; // Get currency preference

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/admin/payouts${filter ? `?status=${filter}` : ""}`);
      setPayouts(r.data || []);
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail)); }
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  const generate = async () => {
    if (generating) return;
    setGenerating(true);
    try {
      const r = await api.post("/admin/payouts/generate", { seller_id: null });
      const n = r.data?.created || 0;
      toast.success(n > 0 ? `${n} payout(s) generated` : "No eligible orders");
      load();
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
    finally { setGenerating(false); }
  };

  const initiatePayment = async (p) => {
    try {
      const r = await api.post(`/admin/payouts/${p.id}/generate-otp`);
      setOtpModal({ payout: p, otp: r.data.otp, inputOtp: "", confirming: false });
      toast.success("OTP generated! Show this to the seller.");
    } catch (err) { 
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to generate OTP"); 
    }
  };

  const confirmOTP = async () => {
    if (!otpModal || otpModal.confirming) return;
    const { payout, inputOtp } = otpModal;
    if (!inputOtp || inputOtp.trim().length !== 4) {
      toast.error("Please enter the 4-digit OTP");
      return;
    }
    setOtpModal(prev => ({ ...prev, confirming: true }));
    try {
      await api.post(`/admin/payouts/${payout.id}/confirm-otp`, { otp: inputOtp.trim() });
      toast.success("Payment confirmed!");
      setOtpModal(null);
      load();
    } catch (err) { 
      toast.error(formatDetail(err.response?.data?.detail) || "OTP verification failed"); 
      setOtpModal(prev => ({ ...prev, confirming: false }));
    }
  };

  const markPaid = async (p) => {
    if (payingIds.has(p.id)) return;
    if (!confirm(`Mark payout of ${formatPrice(p.amount_usd, p.exchange_rate_ssp || exchangeRate, currency)} to ${p.seller_name} as paid directly (no OTP)?`)) return;
    setPayingIds((prev) => { const n = new Set(prev); n.add(p.id); return n; });
    try {
      await api.post(`/admin/payouts/${p.id}/mark-paid`);
      toast.success("Payout marked paid");
      load();
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
    finally { setPayingIds((prev) => { const n = new Set(prev); n.delete(p.id); return n; }); }
  };

  const open = async (p) => {
    try {
      const r = await api.get(`/admin/payouts/${p.id}`);
      setDetail(r.data);
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="px-3 py-2 border border-[var(--js-border)] rounded-lg text-sm">
          <option value="">All payouts</option>
          <option value="pending_payout">Pending payout</option>
          <option value="paid">Paid</option>
        </select>
        <button
          onClick={generate}
          disabled={generating}
          data-testid="generate-payouts"
          className="bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#C84B31]/40 disabled:cursor-not-allowed text-white text-sm font-semibold px-4 py-2 rounded-full"
        >
          {generating ? "Generating…" : "Generate payouts (all eligible)"}
        </button>
      </div>

      <div className="overflow-x-auto bg-white border border-[var(--js-border)] rounded-2xl">
        <table className="min-w-full text-sm">
          <thead className="bg-[var(--js-bg)] text-xs uppercase tracking-wide text-[var(--js-text-secondary)]">
            <tr>
              <th className="text-left px-3 py-3">Payout</th>
              <th className="text-left px-3 py-3">Seller</th>
              <th className="text-left px-3 py-3">Orders</th>
              <th className="text-left px-3 py-3">Amount</th>
              <th className="text-left px-3 py-3">Commission</th>
              <th className="text-left px-3 py-3">Status</th>
              <th className="text-right px-3 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {payouts.map((p) => (
              <tr key={p.id} className="border-t border-[var(--js-border)]">
                <td className="px-3 py-2 font-mono text-xs">{p.id.slice(0, 8)}</td>
                <td className="px-3 py-2">
                  <div className="font-medium">{p.seller_name}</div>
                  <div className="text-xs text-[var(--js-text-secondary)]">{p.seller_email}</div>
                </td>
                <td className="px-3 py-2">{(p.split_ids?.length || 0) + (p.restaurant_order_ids?.length || 0)}</td>
                <td className="px-3 py-2 font-semibold text-emerald-700">{formatPrice(p.amount_usd, p.exchange_rate_ssp || exchangeRate, currency)}</td>
                <td className="px-3 py-2">{formatPrice(p.commission_deducted_usd, p.exchange_rate_ssp || exchangeRate, currency)}</td>
                <td className="px-3 py-2"><Pill value={p.status} /></td>
                <td className="px-3 py-2 text-right space-x-1">
                  <button onClick={() => open(p)} className="text-xs px-2 py-1 rounded-full hover:bg-gray-100"><Eye className="w-4 h-4 inline" /></button>
                  {p.status !== "paid" && (
                    <>
                      <button
                        onClick={() => initiatePayment(p)}
                        data-testid={`initiate-payment-${p.id.slice(0,8)}`}
                        className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1 rounded-full"
                      >
                        Generate OTP
                      </button>
                      <button
                        onClick={() => markPaid(p)}
                        disabled={payingIds.has(p.id)}
                        data-testid={`mark-paid-${p.id.slice(0,8)}`}
                        className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-300 disabled:cursor-not-allowed text-white text-xs font-semibold px-3 py-1 rounded-full"
                      >
                        {payingIds.has(p.id) ? "Saving…" : "Mark paid"}
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {payouts.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-[var(--js-text-secondary)]">No payouts yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {detail && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-[var(--js-border)]">
              <h3 className="font-bold text-lg">Payout {detail.id.slice(0, 8)} — {detail.seller_name}</h3>
              <button onClick={() => setDetail(null)} className="p-2 hover:bg-gray-100 rounded-full"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><p className="text-xs text-[var(--js-text-secondary)]">Amount</p><p className="font-bold text-lg text-emerald-700">{formatPrice(detail.amount_usd, detail.exchange_rate_ssp || exchangeRate, currency)}</p></div>
                <div><p className="text-xs text-[var(--js-text-secondary)]">Commission deducted</p><p className="font-bold text-lg">{formatPrice(detail.commission_deducted_usd, detail.exchange_rate_ssp || exchangeRate, currency)}</p></div>
                <div><p className="text-xs text-[var(--js-text-secondary)]">Status</p><Pill value={detail.status} /></div>
                <div><p className="text-xs text-[var(--js-text-secondary)]">Paid at</p><p className="text-sm">{detail.paid_at || "—"}</p></div>
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-[var(--js-text-secondary)] mb-2">Splits in this payout</p>
                <ul className="space-y-1 text-sm">
                  {(detail.splits || []).map((s) => (
                    <li key={s.id} className="flex justify-between border-b py-1">
                      <span className="font-mono text-xs">{s.id.slice(0, 8)}</span>
                      <span>{s.customer_name}</span>
                      <span className="font-semibold">{formatPrice(s.seller_earning_usd, detail.exchange_rate_ssp || exchangeRate, currency)}</span>
                    </li>
                  ))}
                  {(detail.restaurant_orders || []).map((s) => (
                    <li key={s.id} className="flex justify-between border-b py-1">
                      <span className="font-mono text-xs">R {s.id.slice(0, 8)}</span>
                      <span>{s.customer_name}</span>
                      <span className="font-semibold">{formatPrice(s.seller_earning_usd, detail.exchange_rate_ssp || exchangeRate, currency)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* OTP Modal for seller collection */}
      {otpModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-lg">Seller Collection OTP</h3>
              <button 
                onClick={() => setOtpModal(null)} 
                disabled={otpModal.confirming}
                className="p-2 hover:bg-gray-100 rounded-full disabled:opacity-50"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="space-y-4">
              {/* Show OTP to admin */}
              {otpModal.otp && (
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
                  <p className="text-xs uppercase tracking-wider font-bold text-blue-800 mb-2">
                    Show this OTP to {otpModal.payout.seller_name}
                  </p>
                  <p className="text-5xl font-mono font-bold text-blue-700 tracking-widest mb-2">
                    {otpModal.otp}
                  </p>
                  <p className="text-xs text-blue-800">
                    Amount: {formatPrice(otpModal.payout.amount_usd, otpModal.payout.exchange_rate_ssp || exchangeRate, currency)}
                  </p>
                </div>
              )}

              {/* OTP input for verification */}
              <div>
                <label className="block text-sm font-semibold mb-2">
                  Enter OTP from seller
                </label>
                <input
                  type="text"
                  maxLength={4}
                  value={otpModal.inputOtp || ""}
                  onChange={(e) => setOtpModal(prev => ({ ...prev, inputOtp: e.target.value }))}
                  disabled={otpModal.confirming}
                  data-testid="otp-input"
                  placeholder="____"
                  className="w-full px-4 py-3 text-center text-2xl font-mono font-bold border-2 border-gray-300 rounded-lg focus:border-emerald-500 focus:outline-none disabled:bg-gray-100"
                />
              </div>

              {/* Action buttons */}
              <div className="flex gap-2">
                <button
                  onClick={() => setOtpModal(null)}
                  disabled={otpModal.confirming}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-full font-semibold hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmOTP}
                  disabled={otpModal.confirming || !otpModal.inputOtp || otpModal.inputOtp.length !== 4}
                  data-testid="confirm-otp-btn"
                  className="flex-1 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-300 disabled:cursor-not-allowed text-white font-semibold px-4 py-2 rounded-full"
                >
                  {otpModal.confirming ? "Confirming…" : "Confirm Payment"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------- DISPUTES ----------------
function DisputesPane() {
  const [list, setList] = useState([]);
  const [allSplits, setAllSplits] = useState([]);
  const { currency = "USD", exchangeRate = 600 } = useCart() || {};
  
  const load = useCallback(async () => {
    try {
      const r = await api.get("/admin/order-splits");
      setAllSplits(r.data || []);
      setList((r.data || []).filter((s) => s.dispute_status === "opened"));
    } catch (e) { toast.error(formatDetail(e.response?.data?.detail)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const openDispute = async () => {
    const splitId = prompt("Enter split ID (8-char prefix is OK):");
    if (!splitId) return;
    const reason = prompt("Dispute reason:");
    if (!reason) return;
    const full = allSplits.find((s) => s.id.startsWith(splitId));
    if (!full) { toast.error("Split not found"); return; }
    try {
      await api.post(`/admin/disputes/split/${full.id}/open`, { reason });
      toast.success("Dispute opened");
      load();
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };

  const resolve = async (s) => {
    if (!confirm("Resolve this dispute? Payout will be re-evaluated.")) return;
    try {
      await api.post(`/admin/disputes/split/${s.id}/resolve`);
      toast.success("Dispute resolved");
      load();
    } catch (err) { toast.error(formatDetail(err.response?.data?.detail)); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-[var(--js-text-secondary)]">{list.length} open dispute(s)</p>
        <button onClick={openDispute} className="bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-4 py-2 rounded-full">
          Open new dispute
        </button>
      </div>
      <div className="overflow-x-auto bg-white border border-[var(--js-border)] rounded-2xl">
        <table className="min-w-full text-sm">
          <thead className="bg-[var(--js-bg)] text-xs uppercase tracking-wide text-[var(--js-text-secondary)]">
            <tr>
              <th className="text-left px-3 py-3">Split</th>
              <th className="text-left px-3 py-3">Reason</th>
              <th className="text-left px-3 py-3">Shop</th>
              <th className="text-left px-3 py-3">Customer</th>
              <th className="text-left px-3 py-3">Amount</th>
              <th className="text-right px-3 py-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {list.map((s) => (
              <tr key={s.id} className="border-t border-[var(--js-border)]">
                <td className="px-3 py-2 font-mono text-xs">{s.id.slice(0, 8)}</td>
                <td className="px-3 py-2">{s.dispute_reason || "—"}</td>
                <td className="px-3 py-2">{s.shop_name}</td>
                <td className="px-3 py-2">{s.customer_name}</td>
                <td className="px-3 py-2 font-semibold">{formatPrice(s.order_total_usd, exchangeRate, currency)}</td>
                <td className="px-3 py-2 text-right">
                  <button onClick={() => resolve(s)} className="bg-emerald-600 text-white text-xs font-semibold px-3 py-1.5 rounded-full">Resolve</button>
                </td>
              </tr>
            ))}
            {list.length === 0 && <tr><td colSpan={6} className="text-center py-8 text-[var(--js-text-secondary)]">No open disputes.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
