import { useEffect, useState, useCallback } from "react";
import api, { formatUSD, formatPrice, formatDetail } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { useOptimizedPolling } from "@/hooks/useOptimizedPolling";
import { toast } from "sonner";
import {
  Wallet,
  Truck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Receipt,
  RotateCcw,
  Eye,
  X,
  KeyRound,
  PackageCheck,
} from "lucide-react";

const STATUS_PILL = {
  unassigned: "bg-gray-100 text-gray-700",
  assigned: "bg-blue-100 text-blue-700",
  pending_pickup: "bg-blue-100 text-blue-700",
  picked_up: "bg-amber-100 text-amber-700",
  out_for_delivery: "bg-amber-100 text-amber-800",
  delivered: "bg-emerald-100 text-emerald-700",
  delivery_failed: "bg-red-100 text-red-700",
  return_to_seller_pending: "bg-orange-100 text-orange-700",
  returned_to_seller: "bg-gray-100 text-gray-700",
  failed: "bg-red-100 text-red-700",
};

const PAYOUT_PILL = {
  not_ready: "bg-gray-100 text-gray-600",
  ready_for_payout: "bg-emerald-100 text-emerald-700",
  pending_payout: "bg-amber-100 text-amber-700",
  paid: "bg-emerald-200 text-emerald-800",
  paused: "bg-orange-100 text-orange-700",
  cancelled: "bg-red-100 text-red-700",
};

function StatCard({ icon: Icon, label, value, sub, tone = "default" }) {
  const tones = {
    default: "bg-white",
    good: "bg-emerald-50 border-emerald-200",
    warn: "bg-amber-50 border-amber-200",
    bad: "bg-red-50 border-red-200",
  };
  return (
    <div className={`rounded-2xl border border-[var(--js-border)] p-5 ${tones[tone] || tones.default}`}>
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">{label}</p>
        <Icon className="w-4 h-4 text-[var(--js-text-secondary)]" />
      </div>
      <p className="mt-2 text-2xl font-bold text-[var(--js-text)]">{value}</p>
      {sub && <p className="text-xs text-[var(--js-text-secondary)] mt-1">{sub}</p>}
    </div>
  );
}

function Pill({ value, mapping }) {
  const cls = mapping?.[value] || "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold ${cls}`}>
      {String(value || "—").replace(/_/g, " ")}
    </span>
  );
}

export default function SellerWalletTab() {
  const [wallet, setWallet] = useState(null);
  const [splits, setSplits] = useState([]);
  const [restOrders, setRestOrders] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [detail, setDetail] = useState(null);
  const [returnOtp, setReturnOtp] = useState("");
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("overview"); // overview | splits | payouts
  
  // Get currency and exchange rate from CartContext with defaults
  const { currency = "USD", exchangeRate = 1 } = useCart() || {};

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [w, s, r, p] = await Promise.all([
        api.get("/seller/wallet"),
        api.get("/seller/splits"),
        api.get("/seller/restaurant-orders-cod"),
        api.get("/seller/payouts"),
      ]);
      setWallet(w.data);
      setSplits(s.data || []);
      setRestOrders(r.data || []);
      setPayouts(p.data || []);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to load wallet");
    } finally {
      setLoading(false);
    }
  }, []);

  // Silent refresh without loading spinner
  const silentRefresh = useCallback(async () => {
    try {
      const [w, s, r, p] = await Promise.all([
        api.get("/seller/wallet"),
        api.get("/seller/splits"),
        api.get("/seller/restaurant-orders-cod"),
        api.get("/seller/payouts"),
      ]);
      setWallet(w.data);
      setSplits(s.data || []);
      setRestOrders(r.data || []);
      setPayouts(p.data || []);
    } catch (e) {
      // Silent failure - don't show error toast on background refresh
      console.error("Silent refresh failed:", e);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Optimized auto-refresh with visibility detection
  useOptimizedPolling(silentRefresh, 12000, { runOnMount: false });

  const act = async (split, action) => {
    const isRest = split._kind === "rest";
    const base = isRest ? `/seller/restaurant-orders/${split.id}` : `/seller/splits/${split.id}`;
    try {
      await api.post(`${base}/${action}`);
      toast.success("Updated");
      load(); // Immediately refresh after seller action
      // If detail modal is open, update it from the refreshed seller data
      if (detail?.id === split.id) {
        // Wait a bit for backend to update, then refresh
        setTimeout(async () => {
          try {
            const [s, r] = await Promise.all([
              api.get("/seller/splits"),
              api.get("/seller/restaurant-orders-cod"),
            ]);
            const allItems = [
              ...(s.data || []).map((x) => ({ ...x, _kind: "split" })),
              ...(r.data || []).map((x) => ({ ...x, _kind: "rest" })),
            ];
            const updated = allItems.find((x) => x.id === split.id);
            if (updated) setDetail(updated);
          } catch (e) {
            console.error("Failed to refresh detail:", e);
          }
        }, 500);
      }
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Action failed");
    }
  };

  const confirmReturn = async (split) => {
    if (!returnOtp.trim()) {
      toast.error("Enter return OTP from driver");
      return;
    }
    const isRest = split._kind === "rest";
    const base = isRest ? `/seller/restaurant-orders/${split.id}` : `/seller/splits/${split.id}`;
    try {
      await api.post(`${base}/return-received`, { otp: returnOtp.trim() });
      toast.success("Return confirmed");
      setReturnOtp("");
      load();
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Wrong OTP");
    }
  };

  // Active orders excludes anything already paid out OR cancelled OR delivered.
  // Delivered orders live in the new "Completed" tab so sellers see a clean
  // active board (nothing they can act on) once cash has been collected.
  const allItems = [
    ...splits.map((s) => ({ ...s, _kind: "split" })),
    ...restOrders.map((r) => ({ ...r, _kind: "rest" })),
  ].filter((row) => 
    row.payout_status !== "paid" && 
    row.seller_preparation_status !== "cancelled" &&
    !["cancel_approved", "cancelled"].includes(row.status) &&
    row.delivery_status !== "delivered"
  );

  // Completed orders — delivered (cash collected) but not yet paid out.
  // Sit here until admin generates & pays the payout, at which point they
  // graduate to "Payout History".
  const completedItems = [
    ...splits.map((s) => ({ ...s, _kind: "split" })),
    ...restOrders.map((r) => ({ ...r, _kind: "rest" })),
  ].filter((row) =>
    row.delivery_status === "delivered" &&
    row.payout_status !== "paid" &&
    row.seller_preparation_status !== "cancelled"
  );

  // Cancelled orders
  const cancelledItems = [
    ...splits.map((s) => ({ ...s, _kind: "split" })),
    ...restOrders.map((r) => ({ ...r, _kind: "rest" })),
  ].filter((row) => 
    row.seller_preparation_status === "cancelled" ||
    ["cancel_approved", "cancelled"].includes(row.status)
  );

  if (loading) {
    return (
      <div className="text-center py-20 text-[var(--js-text-secondary)]">Loading wallet…</div>
    );
  }

  return (
    <div>
      {/* sub-tabs */}
      <div className="flex gap-2 mb-6 border-b border-[var(--js-border)]">
        {[
          { id: "overview", label: "Overview" },
          { id: "splits", label: "Active Orders" },
          { id: "completed", label: "Completed" },
          { id: "cancelled", label: "Cancelled Orders" },
          { id: "payouts", label: "Payout History" },
        ].map((s) => (
          <button
            key={s.id}
            onClick={() => setView(s.id)}
            data-testid={`wallet-sub-${s.id}`}
            className={`px-4 py-2 text-sm font-semibold border-b-2 ${
              view === s.id
                ? "border-[#C84B31] text-[#C84B31]"
                : "border-transparent text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {view === "overview" && wallet && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon={Clock}
            label="Pending cash collection"
            value={formatPrice(wallet.pending_cash_collection, exchangeRate, currency)}
            sub="Orders out for delivery"
          />
          <StatCard
            icon={Truck}
            label="Cash with driver"
            value={formatPrice(wallet.cash_with_driver, exchangeRate, currency)}
            sub="Driver hasn’t handed to admin yet"
            tone="warn"
          />
          <StatCard
            icon={Wallet}
            label="Ready for payout"
            value={formatPrice(wallet.ready_for_payout, exchangeRate, currency)}
            sub="Awaiting admin to generate payout"
            tone="good"
          />
          <StatCard
            icon={Receipt}
            label="Pending payout"
            value={formatPrice(wallet.pending_payout, exchangeRate, currency)}
            sub="Payout generated, not yet paid"
            tone="warn"
          />
          <StatCard
            icon={CheckCircle2}
            label="Paid total"
            value={formatPrice(wallet.paid_total, exchangeRate, currency)}
            sub="Lifetime"
            tone="good"
          />
          <StatCard
            icon={AlertTriangle}
            label="Commission deducted"
            value={formatPrice(wallet.commission_deducted, exchangeRate, currency)}
            sub="Platform fee on delivered orders"
          />
          <StatCard
            icon={RotateCcw}
            label="Returned / failed"
            value={formatPrice(wallet.returned_or_failed, exchangeRate, currency)}
            sub="Not eligible for payout"
            tone="bad"
          />
          <StatCard
            icon={PackageCheck}
            label="Ready orders"
            value={(wallet.counts?.ready_splits || 0) + (wallet.counts?.ready_restaurant_orders || 0)}
            sub="Splits + restaurant orders ready"
          />
        </div>
      )}

      {view === "splits" && (
        <div>
          {allItems.length === 0 ? (
            <div className="text-center py-12 text-[var(--js-text-secondary)] border border-dashed border-[var(--js-border)] rounded-2xl">
              No active orders yet.
            </div>
          ) : (
            <div className="overflow-x-auto border border-[var(--js-border)] rounded-2xl bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-[var(--js-bg)] text-xs uppercase tracking-wide text-[var(--js-text-secondary)]">
                  <tr>
                    <th className="text-left px-3 py-3">Order</th>
                    <th className="text-left px-3 py-3">Customer</th>
                    <th className="text-left px-3 py-3">Total</th>
                    <th className="text-left px-3 py-3">Prep</th>
                    <th className="text-left px-3 py-3">Pickup</th>
                    <th className="text-left px-3 py-3">Delivery</th>
                    <th className="text-left px-3 py-3">Payout</th>
                    <th className="text-right px-3 py-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {allItems.map((s) => (
                    <tr key={s.id} className="border-t border-[var(--js-border)]">
                      <td className="px-3 py-2 font-mono text-xs">
                        {s._kind === "rest" ? "R:" : ""}
                        {s.id.slice(0, 8)}
                      </td>
                      <td className="px-3 py-2">
                        <div className="font-medium">{s.customer_name}</div>
                      </td>
                      <td className="px-3 py-2 font-semibold">{formatPrice(s.order_total_usd, s.exchange_rate_ssp || exchangeRate, currency)}</td>
                      <td className="px-3 py-2">
                        <Pill value={s.seller_preparation_status} mapping={{
                          pending: "bg-gray-100 text-gray-700",
                          accepted: "bg-blue-100 text-blue-700",
                          preparing: "bg-amber-100 text-amber-700",
                          ready_for_pickup: "bg-emerald-100 text-emerald-700",
                          handed_to_driver: "bg-emerald-200 text-emerald-800",
                          cancelled: "bg-red-100 text-red-700",
                        }} />
                      </td>
                      <td className="px-3 py-2"><Pill value={s.pickup_status} mapping={STATUS_PILL} /></td>
                      <td className="px-3 py-2"><Pill value={s.delivery_status} mapping={STATUS_PILL} /></td>
                      <td className="px-3 py-2"><Pill value={s.payout_status} mapping={PAYOUT_PILL} /></td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => { setDetail(s); setReturnOtp(""); }}
                          data-testid={`open-split-${s.id.slice(0,8)}`}
                          className="inline-flex items-center gap-1 text-xs bg-[#1A1A1A] hover:bg-black text-white font-semibold px-3 py-1.5 rounded-full"
                        >
                          <Eye className="w-3 h-3" /> Open
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {view === "completed" && (
        <div data-testid="wallet-completed-view">
          {completedItems.length === 0 ? (
            <div className="text-center py-12 text-[var(--js-text-secondary)] border border-dashed border-[var(--js-border)] rounded-2xl">
              No completed orders yet.
            </div>
          ) : (
            <div className="overflow-x-auto border border-[var(--js-border)] rounded-2xl bg-white dark:bg-[var(--js-panel)]">
              <table className="min-w-full text-sm">
                <thead className="bg-[var(--js-bg)] text-xs uppercase tracking-wide text-[var(--js-text-secondary)]">
                  <tr>
                    <th className="text-left px-3 py-3">Order</th>
                    <th className="text-left px-3 py-3">Customer</th>
                    <th className="text-left px-3 py-3">Total</th>
                    <th className="text-left px-3 py-3">Your earning</th>
                    <th className="text-left px-3 py-3">Delivered</th>
                    <th className="text-left px-3 py-3">Payout</th>
                    <th className="text-right px-3 py-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {completedItems.map((s) => (
                    <tr key={s.id} className="border-t border-[var(--js-border)]">
                      <td className="px-3 py-2 font-mono text-xs text-[var(--js-text)]">
                        {s._kind === "rest" ? "R:" : ""}{s.id.slice(0, 8)}
                      </td>
                      <td className="px-3 py-2">
                        <div className="font-medium text-[var(--js-text)]">{s.customer_name}</div>
                      </td>
                      <td className="px-3 py-2 font-semibold text-[var(--js-text)]">{formatPrice(s.order_total_usd, s.exchange_rate_ssp || exchangeRate, currency)}</td>
                      <td className="px-3 py-2 font-semibold text-emerald-700 dark:text-emerald-400">{formatPrice(s.seller_earning_usd, s.exchange_rate_ssp || exchangeRate, currency)}</td>
                      <td className="px-3 py-2 text-xs text-[var(--js-text-secondary)]">{s.delivered_at ? s.delivered_at.slice(0, 16).replace("T", " ") : "—"}</td>
                      <td className="px-3 py-2"><Pill value={s.payout_status || "not_ready"} mapping={PAYOUT_PILL} /></td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => setDetail(s)}
                          data-testid={`open-completed-${s.id.slice(0,8)}`}
                          className="inline-flex items-center gap-1 text-xs bg-[#1A1A1A] hover:bg-black text-white font-semibold px-3 py-1.5 rounded-full"
                        >
                          <Eye className="w-3 h-3" /> View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {view === "cancelled" && (
        <div>
          {cancelledItems.length === 0 ? (
            <div className="text-center py-12 text-[var(--js-text-secondary)] border border-dashed border-[var(--js-border)] rounded-2xl">
              No cancelled orders.
            </div>
          ) : (
            <div className="overflow-x-auto border border-[var(--js-border)] rounded-2xl bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-[var(--js-bg)] text-xs uppercase tracking-wide text-[var(--js-text-secondary)]">
                  <tr>
                    <th className="text-left px-3 py-3">Order</th>
                    <th className="text-left px-3 py-3">Customer</th>
                    <th className="text-left px-3 py-3">Total</th>
                    <th className="text-left px-3 py-3">Status</th>
                    <th className="text-left px-3 py-3">Cancelled At</th>
                    <th className="text-right px-3 py-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {cancelledItems.map((s) => (
                    <tr key={s.id} className="border-t border-[var(--js-border)]">
                      <td className="px-3 py-2 font-mono text-xs">
                        {s._kind === "rest" ? "R:" : ""}
                        {s.id.slice(0, 8)}
                      </td>
                      <td className="px-3 py-2">
                        <div className="font-medium">{s.customer_name}</div>
                      </td>
                      <td className="px-3 py-2 font-semibold">{formatPrice(s.order_total_usd, s.exchange_rate_ssp || exchangeRate, currency)}</td>
                      <td className="px-3 py-2">
                        <Pill value={s.status} mapping={{
                          cancel_approved: "bg-red-100 text-red-700",
                          cancelled: "bg-red-100 text-red-700",
                        }} />
                      </td>
                      <td className="px-3 py-2 text-xs">{s.updated_at ? s.updated_at.slice(0, 16).replace("T", " ") : "—"}</td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => setDetail(s)}
                          className="text-xs text-[#C84B31] hover:text-[#A13B25] font-semibold"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {view === "payouts" && (
        <div>
          {payouts.length === 0 ? (
            <div className="text-center py-12 text-[var(--js-text-secondary)] border border-dashed border-[var(--js-border)] rounded-2xl">
              No payouts yet.
            </div>
          ) : (
            <div className="overflow-x-auto border border-[var(--js-border)] rounded-2xl bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-[var(--js-bg)] text-xs uppercase tracking-wide text-[var(--js-text-secondary)]">
                  <tr>
                    <th className="text-left px-3 py-3">Payout ID</th>
                    <th className="text-left px-3 py-3">Created</th>
                    <th className="text-left px-3 py-3">Splits</th>
                    <th className="text-left px-3 py-3">Amount</th>
                    <th className="text-left px-3 py-3">Commission</th>
                    <th className="text-left px-3 py-3">Status</th>
                    <th className="text-left px-3 py-3">Paid at</th>
                  </tr>
                </thead>
                <tbody>
                  {payouts.map((p) => {
                    // Use seller's exchange rate from payout, fallback to global rate
                    const payoutRate = p.exchange_rate_ssp || exchangeRate;
                    return (
                    <tr key={p.id} className="border-t border-[var(--js-border)]">
                      <td className="px-3 py-2 font-mono text-xs">{p.id.slice(0, 8)}</td>
                      <td className="px-3 py-2 text-xs">{(p.created_at || "").slice(0, 16).replace("T", " ")}</td>
                      <td className="px-3 py-2">{(p.split_ids?.length || 0) + (p.restaurant_order_ids?.length || 0)}</td>
                      <td className="px-3 py-2 font-semibold">{formatPrice(p.amount_usd, payoutRate, currency)}</td>
                      <td className="px-3 py-2">{formatPrice(p.commission_deducted_usd, payoutRate, currency)}</td>
                      <td className="px-3 py-2"><Pill value={p.status} mapping={PAYOUT_PILL} /></td>
                      <td className="px-3 py-2 text-xs">{p.paid_at ? p.paid_at.slice(0, 16).replace("T", " ") : "—"}</td>
                    </tr>
                  );})}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* DETAIL MODAL */}
      {detail && (() => {
        // Seller-managed delivery? Split now carries `delivery_managed_by`
        // resolved at creation (marketplace) or the restaurant's own flag.
        const sellerIsDriver = (detail._kind === "rest"
          ? (detail.delivery_managed_by === "seller" || detail.self_delivered_by_seller)
          : (detail.delivery_managed_by === "seller" || detail.self_delivered_by_seller));
        // Seller-managed self-deliver endpoints:
        const selfBase = detail._kind === "rest"
          ? `/seller/restaurant-orders/${detail.id}`
          : `/seller/splits/${detail.id}`;
        const callSelfDeliver = async (action) => {
          try {
            await api.post(`${selfBase}/${action}`);
            toast.success(action === "self-deliver-complete" ? "Order completed" : "Sent for delivery");
            load();
            // refresh detail
            setTimeout(async () => {
              try {
                const [s, r] = await Promise.all([
                  api.get("/seller/splits"),
                  api.get("/seller/restaurant-orders-cod"),
                ]);
                const allItems = [
                  ...(s.data || []).map((x) => ({ ...x, _kind: "split" })),
                  ...(r.data || []).map((x) => ({ ...x, _kind: "rest" })),
                ];
                const updated = allItems.find((x) => x.id === detail.id);
                if (updated) setDetail(updated);
                else setDetail(null);  // was completed & filtered out
              } catch (e) { /* silent */ }
            }, 500);
          } catch (e) {
            toast.error(formatDetail(e.response?.data?.detail) || "Action failed");
          }
        };
        return (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-[var(--js-border)]">
              <h3 className="font-bold text-lg text-[var(--js-text)]">
                {detail._kind === "rest" ? "Restaurant Order" : "Order Split"} {detail.id.slice(0, 8)}
              </h3>
              <button onClick={() => setDetail(null)} className="p-2 hover:bg-gray-100 dark:hover:bg-white/10 rounded-full text-[var(--js-text)]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-[var(--js-text-secondary)]">Customer</p>
                  <p className="font-semibold text-[var(--js-text)]">{detail.customer_name}</p>
                  <p className="text-[10px] text-[var(--js-text-secondary)] italic">
                    {sellerIsDriver ? "Contact visible on delivery card." : "Phone & address hidden — driver has them."}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[var(--js-text-secondary)]">Driver</p>
                  <p className="font-semibold text-[var(--js-text)]">
                    {sellerIsDriver
                      ? (detail.seller_driver_name || "Your driver")
                      : (detail.driver_name || "Not assigned")}
                  </p>
                  {sellerIsDriver && detail.seller_driver_phone && (
                    <p className="text-[10px] text-[var(--js-text-secondary)]">{detail.seller_driver_phone}</p>
                  )}
                </div>
                <div>
                  <p className="text-xs text-[var(--js-text-secondary)]">Order total</p>
                  <p className="font-semibold text-[var(--js-text)]">{formatPrice(detail.order_total_usd, detail.exchange_rate_ssp || exchangeRate, currency)}</p>
                  <p className="text-[10px] text-[var(--js-text-secondary)]">
                    Items {formatPrice(detail.product_subtotal_usd || 0, detail.exchange_rate_ssp || exchangeRate, currency)}
                    {(detail.delivery_fee_usd || 0) > 0 && <> · Delivery {formatPrice(detail.delivery_fee_usd, detail.exchange_rate_ssp || exchangeRate, currency)}</>}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[var(--js-text-secondary)]">Your earning</p>
                  <p className="font-semibold text-emerald-700 dark:text-emerald-400">{formatPrice(detail.seller_earning_usd, detail.exchange_rate_ssp || exchangeRate, currency)}</p>
                  <p className="text-[10px] text-[var(--js-text-secondary)]">
                    Commission {Math.round((detail.commission_rate || 0) * 100)}%
                    {(detail.seller_earning_usd || 0) > ((detail.product_subtotal_usd || 0) - (detail.platform_commission_usd || 0)) + 0.005 && (
                      <> · incl. delivery you earned</>
                    )}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 text-xs">
                <Pill value={detail.seller_preparation_status} mapping={{ pending: "bg-gray-100 text-gray-700", accepted: "bg-blue-100 text-blue-700", preparing: "bg-amber-100 text-amber-700", ready_for_pickup: "bg-emerald-100 text-emerald-700", handed_to_driver: "bg-emerald-200 text-emerald-800" }} />
                <Pill value={detail.pickup_status} mapping={STATUS_PILL} />
                <Pill value={detail.delivery_status} mapping={STATUS_PILL} />
                <Pill value={detail.payout_status} mapping={PAYOUT_PILL} />
              </div>

              {/* Items */}
              <div className="border-t border-[var(--js-border)] pt-3">
                <p className="text-xs font-bold uppercase tracking-wide text-[var(--js-text-secondary)] mb-2">Items</p>
                <ul className="space-y-1 text-sm">
                  {(detail.items || detail.items_secure || []).map((it, i) => (
                    <li key={i} className="flex justify-between text-[var(--js-text)]">
                      <span>{it.name} × {it.quantity}</span>
                      <span className="font-medium">{formatPrice(
                        it.line_total_usd != null ? it.line_total_usd : ((it.price_usd || 0) * (it.quantity || 0)),
                        detail.exchange_rate_ssp || exchangeRate,
                        currency
                      )}</span>
                    </li>
                  ))}
                </ul>
                {detail.note && (
                  <div
                    data-testid="seller-wallet-customer-note"
                    className="mt-3 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs"
                  >
                    <p className="font-bold text-amber-900 uppercase tracking-wide mb-0.5">Customer note</p>
                    <p className="text-amber-900 leading-snug">{detail.note}</p>
                  </div>
                )}
              </div>

              {/* Driver Pickup OTP — ONLY when platform (admin) driver is used.
                  For seller-managed delivery, the seller IS the delivery so
                  no OTP handshake is needed. */}
              {!sellerIsDriver && ["ready_for_pickup", "handed_to_driver"].includes(detail.seller_preparation_status) && detail.seller_pickup_otp && (
                <div className="border border-emerald-200 bg-emerald-50 rounded-xl p-3">
                  <p className="text-xs uppercase tracking-wide text-emerald-800 font-bold flex items-center gap-1">
                    <KeyRound className="w-3 h-3" /> Driver Pickup OTP
                  </p>
                  <p className="text-3xl font-mono font-bold text-emerald-700 tracking-widest">
                    {detail.seller_pickup_otp}
                  </p>
                  <p className="text-[11px] text-emerald-800">Give this to the driver to confirm pickup.</p>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex flex-wrap gap-2 pt-3 border-t border-[var(--js-border)]">
                {detail.seller_preparation_status === "pending" && (
                  <button onClick={() => act(detail, "accept")} data-testid="wallet-accept" className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-full">Accept order</button>
                )}
                {["pending", "accepted"].includes(detail.seller_preparation_status) && (
                  <button onClick={() => act(detail, "preparing")} data-testid="wallet-preparing" className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-4 py-2 rounded-full">Mark preparing</button>
                )}
                {["pending", "accepted", "preparing"].includes(detail.seller_preparation_status) && (
                  <button onClick={() => act(detail, "ready-for-pickup")} data-testid="wallet-ready" className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-full">Ready for pickup</button>
                )}
                {/* Seller-managed delivery: "Send for delivery" → out_for_delivery,
                    then "Cash collected from driver" → delivered + completed. No OTP. */}
                {sellerIsDriver && detail.seller_preparation_status === "ready_for_pickup" && detail.delivery_status !== "out_for_delivery" && detail.delivery_status !== "delivered" && (
                  <button
                    onClick={() => callSelfDeliver("self-deliver-start")}
                    data-testid="wallet-self-deliver-start"
                    className="bg-blue-700 hover:bg-blue-800 text-white text-xs font-semibold px-4 py-2 rounded-full"
                  >Send for delivery</button>
                )}
                {sellerIsDriver && detail.delivery_status !== "delivered" && ["ready_for_pickup", "handed_to_driver"].includes(detail.seller_preparation_status) && (
                  <button
                    onClick={() => callSelfDeliver("self-deliver-complete")}
                    data-testid="wallet-self-deliver-complete"
                    className="bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold px-4 py-2 rounded-full"
                  >Cash collected from driver</button>
                )}
                {/* Admin-driver flow: legacy "handed to driver" only for platform drivers */}
                {!sellerIsDriver && detail.pickup_status === "picked_up" && detail.seller_handover_status !== "handed_to_driver" && (
                  <button onClick={() => act(detail, "handed-to-driver")} className="bg-[#1A1A1A] hover:bg-black text-white text-xs font-semibold px-4 py-2 rounded-full">Confirm I handed it to driver</button>
                )}
              </div>

              {/* Cancel — only while still cancellable (pending/accepted/preparing) */}
              {["pending", "accepted", "preparing"].includes(detail.seller_preparation_status) ? (
                <div className="border-t pt-3">
                  <button
                    onClick={async () => {
                      const reason = prompt("Cancel reason (optional):", "");
                      if (reason === null) return;
                      try {
                        const base = detail._kind === "rest" ? `/seller/restaurant-orders/${detail.id}` : `/seller/splits/${detail.id}`;
                        await api.post(`${base}/cancel`, { reason });
                        toast.success("Order cancelled");
                        setDetail(null);
                        load();
                      } catch (e) {
                        toast.error(formatDetail(e.response?.data?.detail) || "Cannot cancel");
                      }
                    }}
                    data-testid="seller-cancel-order"
                    className="text-xs text-red-700 hover:text-red-900 underline"
                  >
                    Cancel this order
                  </button>
                  <p className="text-[10px] text-[var(--js-text-secondary)] mt-1">You can cancel until you mark the order ready for pickup.</p>
                </div>
              ) : detail.seller_preparation_status !== "cancelled" && (
                <p className="text-[11px] text-[var(--js-text-secondary)] italic border-t pt-3">
                  Order is past <strong>ready for pickup</strong>. Contact admin to cancel.
                </p>
              )}

              {/* Return flow */}
              {detail.return_status === "return_to_seller_pending" && (
                <div className="border border-orange-300 bg-orange-50 rounded-xl p-3">
                  <p className="text-xs uppercase tracking-wide text-orange-800 font-bold flex items-center gap-1">
                    <RotateCcw className="w-3 h-3" /> Returned item from failed delivery
                  </p>
                  <p className="text-xs text-orange-800 mb-2">Driver will give you the return OTP — enter it to confirm you received the item back.</p>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={returnOtp}
                      onChange={(e) => setReturnOtp(e.target.value)}
                      placeholder="Return OTP"
                      data-testid="return-otp-input"
                      className="flex-1 px-3 py-2 border border-orange-300 rounded-lg font-mono"
                    />
                    <button onClick={() => confirmReturn(detail)} className="bg-orange-600 text-white text-xs font-semibold px-4 py-2 rounded-full">Confirm return</button>
                  </div>
                </div>
              )}

              {detail.failure_reason && (
                <div className="text-xs bg-red-50 border border-red-200 rounded-lg p-2">
                  <p className="font-bold text-red-800">Failed delivery</p>
                  <p>Reason: {detail.failure_reason.replace(/_/g, " ")}</p>
                  {detail.failure_note && <p>Note: {detail.failure_note}</p>}
                </div>
              )}
            </div>
          </div>
        </div>
        );
      })()}
    </div>
  );
}
