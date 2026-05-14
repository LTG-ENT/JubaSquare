// Kitchen Dashboard — "Today's Restaurant Queue" focused on FOOD PREPARATION.
//
// Repurposed to use the new COD/order state machine. The kitchen only cares
// about seller_preparation_status: pending → accepted → preparing →
// ready_for_pickup → handed_to_driver. Payments, cash handover, driver
// commission, delivery details are all hidden here — they live in Wallet &
// Admin tabs.
//
// Privacy: customer phone / area / address are NEVER shown. Just the name.

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useOptimizedPolling } from "@/hooks/useOptimizedPolling";
import api, { formatUSD, formatDetail } from "@/lib/api";
import { toast } from "sonner";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import {
  ChefHat,
  Clock,
  Flame,
  PackageCheck,
  Truck,
  CheckCircle2,
  XCircle,
  Power,
  Printer,
  AlertTriangle,
  User,
  KeyRound,
  RotateCcw,
  ArrowLeft,
  StickyNote,
  ChevronDown,
  ChevronUp,
  History,
} from "lucide-react";

// Columns shown on the kitchen board, in left-to-right flow order.
const LANES = [
  { id: "pending", label: "New", icon: Clock, accent: "border-gray-300", text: "text-gray-700" },
  { id: "accepted", label: "Accepted", icon: CheckCircle2, accent: "border-blue-300", text: "text-blue-700" },
  { id: "preparing", label: "Preparing", icon: Flame, accent: "border-amber-300", text: "text-amber-700" },
  { id: "ready_for_pickup", label: "Ready for pickup", icon: PackageCheck, accent: "border-emerald-300", text: "text-emerald-700" },
  { id: "handed_to_driver", label: "Handed to driver", icon: Truck, accent: "border-slate-300", text: "text-slate-700" },
];

const PILL = {
  unassigned: "bg-gray-100 text-gray-700",
  assigned: "bg-blue-100 text-blue-700",
  pending_pickup: "bg-blue-100 text-blue-700",
  picked_up: "bg-amber-100 text-amber-800",
  out_for_delivery: "bg-amber-100 text-amber-800",
  delivered: "bg-emerald-100 text-emerald-700",
  delivery_failed: "bg-red-100 text-red-700",
  return_to_seller_pending: "bg-orange-100 text-orange-700",
};
function Pill({ value }) {
  if (!value) return null;
  const cls = PILL[value] || "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${cls}`}>
      {String(value).replace(/_/g, " ")}
    </span>
  );
}

// How long has this order been in the queue? Returns "12m" / "1h 5m" / "now".
function ago(iso) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const diff = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (diff < 60) return "now";
  const m = Math.floor(diff / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export default function KitchenDashboard() {
  const { restaurantId } = useParams();
  const navigate = useNavigate();
  const [restaurant, setRestaurant] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [cancelReason, setCancelReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyOrders, setHistoryOrders] = useState([]);

  const loadRestaurant = useCallback(async () => {
    try {
      const { data } = await api.get(`/restaurants/${restaurantId}`);
      setRestaurant(data);
    } catch (e) {
      toast.error("Failed to load restaurant");
    }
  }, [restaurantId]);

  const loadOrders = useCallback(async () => {
    try {
      const { data } = await api.get(`/restaurant-orders/restaurant/${restaurantId}`);
      setOrders(data || []);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [restaurantId]);

  const loadHistory = useCallback(async () => {
    try {
      const { data } = await api.get(`/restaurant-orders/restaurant/${restaurantId}?include_history=true`);
      // Filter to only include historical orders (handed to driver, cancelled, returned)
      const historical = (data || []).filter(o => {
        const isHandedToDriver = o.seller_preparation_status === "handed_to_driver";
        const isCancelled = ["cancelled", "cancel_approved", "completed"].includes(o.status);
        const isReturned = o.delivery_status === "returned_to_seller" || o.return_status === "returned";
        return isHandedToDriver || isCancelled || isReturned;
      });
      setHistoryOrders(historical);
    } catch (e) {
      // Silently fail for history, main orders are more important
      console.error("Failed to load history:", e);
    }
  }, [restaurantId]);

  useEffect(() => {
    loadRestaurant();
    loadOrders();
    loadHistory();
  }, [loadRestaurant, loadOrders, loadHistory]);

  // Optimized polling with visibility detection
  useOptimizedPolling(
    useCallback(async () => {
      await Promise.all([loadOrders(), loadHistory()]);
    }, [loadOrders, loadHistory]),
    15000,
    { runOnMount: false } // Already run on mount above
  );

  const toggleOpen = async () => {
    if (!restaurant) return;
    try {
      const { data } = await api.put(`/restaurants/${restaurantId}/toggle-open`);
      setRestaurant({ ...restaurant, is_open: data.is_open });
      toast.success(data.is_open ? "Restaurant is now OPEN" : "Restaurant is now CLOSED");
    } catch (e) {
      toast.error("Failed to update status");
    }
  };

  const move = async (order, action) => {
    setBusy(true);
    try {
      await api.post(`/seller/restaurant-orders/${order.id}/${action}`);
      toast.success("Updated");
      // optimistic local refresh
      await loadOrders();
      if (selected?.id === order.id) {
        const fresh = (await api.get(`/restaurant-orders/${order.id}`)).data;
        setSelected(fresh);
      }
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const cancelOrder = async (order) => {
    if (!confirm(`Cancel this order?\n\nCustomer: ${order.customer_name}\nReason (optional): ${cancelReason || "(none)"}`)) return;
    setBusy(true);
    try {
      await api.post(`/seller/restaurant-orders/${order.id}/cancel`, { reason: cancelReason });
      toast.success("Order cancelled");
      setCancelReason("");
      await loadOrders();
      setSelected(null);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Cannot cancel");
    } finally {
      setBusy(false);
    }
  };

  const printTicket = (order) => {
    if (!order) return;
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(`<!doctype html><html><head><title>Ticket ${order.id.slice(0,8)}</title>
<style>body{font-family:monospace;width:300px;margin:20px auto;font-size:13px}h1{text-align:center;font-size:18px;margin:0}.hr{border-top:2px dashed #000;margin:8px 0}.row{display:flex;justify-content:space-between;margin:3px 0}.big{font-size:16px;font-weight:700}.center{text-align:center}</style>
</head><body>
<h1>${restaurant?.name || "Restaurant"}</h1>
<div class="center">Ticket #${order.id.slice(0,8)}</div>
<div class="center">${new Date(order.created_at).toLocaleString()}</div>
<div class="hr"></div>
<div><strong>Customer:</strong> ${order.customer_name || "—"}</div>
<div><strong>Type:</strong> ${order.delivery_type === "delivery" ? "Delivery" : "Pickup"}</div>
<div class="hr"></div>
<strong>ITEMS</strong>
${(order.items || order.items_secure || []).map(it => `
  <div class="row"><span>${it.quantity}× ${it.name}</span><span>${formatUSD(it.line_total_usd || it.price_usd * it.quantity)}</span></div>
  ${(it.sides || []).map(s => `<div class="row" style="margin-left:12px;font-size:11px"><span>+ ${s.name}</span><span></span></div>`).join('')}
`).join('')}
<div class="hr"></div>
<div class="row big"><span>TOTAL</span><span>${formatUSD(order.order_total_usd || order.total)}</span></div>
${order.note ? `<div class="hr"></div><div><strong>Note:</strong> ${order.note}</div>` : ""}
</body></html>`);
    w.document.close();
    setTimeout(() => w.print(), 300);
  };

  // Bucket by prep status (the new state machine). Anything past
  // handed_to_driver is hidden from the kitchen board (delivery / cash /
  // payout is admin/driver concern).
  const byLane = useMemo(() => {
    const m = Object.fromEntries(LANES.map(l => [l.id, []]));
    for (const o of orders) {
      // Anything that's cancelled or returned should NOT clutter the live lanes
      const cancelled = o.status === "cancelled" || o.status === "cancel_approved";
      const returned = o.return_status === "returned" || o.return_status === "pending_return";
      if (cancelled || returned) continue;
      const s = o.seller_preparation_status || (o.status === "cancelled" ? "cancelled" : "pending");
      if (m[s]) m[s].push(o);
    }
    return m;
  }, [orders]);

  // History: cancelled, returned, or delivered orders — kept in a collapsible
  // panel so the kitchen has visibility into what happened after handover
  // without cluttering the live lanes. Fetched separately with include_history=true.
  const history = useMemo(() => {
    return historyOrders.sort((a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at));
  }, [historyOrders]);

  const totals = useMemo(() => ({
    inFlight: orders.filter(o => ["pending","accepted","preparing","ready_for_pickup"].includes(o.seller_preparation_status)).length,
    handed: orders.filter(o => o.seller_preparation_status === "handed_to_driver").length,
  }), [orders]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--js-background)]">
        <Header />
        <div className="max-w-7xl mx-auto px-4 py-20 text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-gray-200 border-t-[#C84B31]" />
          <p className="mt-4 text-[var(--js-text-secondary)]">Loading kitchen…</p>
        </div>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[var(--js-background)]">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 w-full flex-1">
        <button
          onClick={() => navigate("/seller")}
          data-testid="kitchen-back-btn"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--js-text-secondary)] hover:text-[var(--js-text)] mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back to dashboard
        </button>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-[var(--js-text-secondary)]">Today's Restaurant Queue</p>
            <h1 className="font-display font-bold text-2xl flex items-center gap-2">
              <ChefHat className="w-7 h-7 text-[#C84B31]" />
              {restaurant?.name || "Kitchen"}
            </h1>
            <p className="text-xs text-[var(--js-text-secondary)]">
              {totals.inFlight} active · {totals.handed} handed to driver
            </p>
          </div>
          <button
            onClick={toggleOpen}
            data-testid="kitchen-toggle-open"
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold ${
              restaurant?.is_open
                ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-200"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            <Power className="w-4 h-4" />
            {restaurant?.is_open ? "OPEN" : "CLOSED"} — click to toggle
          </button>
        </div>

        {/* Lanes */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
          {LANES.map((lane) => {
            const Icon = lane.icon;
            const rows = byLane[lane.id] || [];
            return (
              <div key={lane.id} className={`bg-white border-t-4 ${lane.accent} rounded-2xl p-3 min-h-[200px] flex flex-col`}>                <div className="flex items-center justify-between mb-3 pb-2 border-b border-[var(--js-border)]">
                  <h2 className={`font-bold text-sm flex items-center gap-1.5 ${lane.text}`}>
                    <Icon className="w-4 h-4" /> {lane.label}
                  </h2>
                  <span className="text-xs font-bold bg-gray-100 rounded-full px-2 py-0.5">{rows.length}</span>
                </div>

                <div className="space-y-2 flex-1">
                  {rows.length === 0 && (
                    <p className="text-xs text-[var(--js-text-secondary)] text-center py-6">Empty</p>
                  )}
                  {rows.map((o) => (
                    <button
                      key={o.id}
                      onClick={() => setSelected(o)}
                      data-testid={`kitchen-card-${o.id.slice(0,8)}`}
                      className="w-full text-left bg-[var(--js-bg)] hover:bg-white hover:shadow-sm border border-[var(--js-border)] rounded-xl p-3 transition"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-[10px] text-[var(--js-text-secondary)]">#{o.id.slice(0,8)}</span>
                        <span className="text-[10px] text-[var(--js-text-secondary)]">{ago(o.created_at)}</span>
                      </div>
                      <p className="font-semibold text-sm flex items-center gap-1 truncate">
                        <User className="w-3 h-3 shrink-0" /> {o.customer_name || "—"}
                      </p>
                      <p className="text-xs text-[var(--js-text-secondary)] mt-1">
                        {(o.items || o.items_secure || []).slice(0,2).map(it => `${it.quantity}× ${it.name}`).join(" · ")}
                        {(o.items || []).length > 2 ? ` +${(o.items || []).length - 2}` : ""}
                      </p>
                      {o.note && (
                        <div
                          data-testid={`kitchen-card-note-${o.id.slice(0,8)}`}
                          className="mt-2 flex items-start gap-1 bg-amber-50 border border-amber-200 rounded-md px-2 py-1"
                        >
                          <StickyNote className="w-3 h-3 mt-0.5 shrink-0 text-amber-700" />
                          <p className="text-[11px] text-amber-900 leading-snug line-clamp-2">{o.note}</p>
                        </div>
                      )}
                      <div className="flex items-center justify-between mt-2">
                        <div className="flex flex-wrap gap-1">
                          {o.driver_name && (
                            <span className="text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full flex items-center gap-1">
                              <Truck className="w-2.5 h-2.5" /> {o.driver_name.split(" ")[0]}
                            </span>
                          )}
                          {o.pickup_status && o.pickup_status !== "not_assigned" && (
                            <Pill value={o.pickup_status} />
                          )}
                        </div>
                        <span className="text-sm font-bold">{formatUSD(o.order_total_usd || o.total)}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* History collapsible — cancelled, returned, delivered */}
        <div className="mt-6">
          <button
            type="button"
            onClick={() => setHistoryOpen((v) => !v)}
            data-testid="kitchen-history-toggle"
            className="w-full bg-white border border-[var(--js-border)] rounded-2xl px-4 py-3 flex items-center justify-between hover:bg-[var(--js-bg)] transition"
          >
            <span className="flex items-center gap-2 font-semibold text-[var(--js-text)]">
              <History className="w-4 h-4 text-[var(--js-text-secondary)]" />
              History
              <span className="text-xs font-bold bg-gray-100 text-gray-700 rounded-full px-2 py-0.5">
                {history.length}
              </span>
              <span className="text-[10px] text-[var(--js-text-secondary)] font-normal">
                Cancelled · Returned · Delivered
              </span>
            </span>
            {historyOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {historyOpen && (
            <div
              data-testid="kitchen-history-panel"
              className="mt-2 bg-white border border-[var(--js-border)] rounded-2xl divide-y divide-[var(--js-border)]"
            >
              {history.length === 0 ? (
                <p className="text-center text-sm text-[var(--js-text-secondary)] py-8">No past orders yet.</p>
              ) : (
                history.map((o) => {
                  const cancelled = o.status === "cancelled" || o.status === "cancel_approved";
                  const returned = o.return_status === "returned" || o.return_status === "pending_return";
                  const delivered = o.delivery_status === "delivered";
                  const tagBg = cancelled
                    ? "bg-red-100 text-red-700"
                    : returned
                    ? "bg-orange-100 text-orange-700"
                    : delivered
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-gray-100 text-gray-700";
                  const tagLabel = cancelled
                    ? "Cancelled"
                    : o.return_status === "pending_return"
                    ? "Return pending"
                    : returned
                    ? "Returned to seller"
                    : "Delivered";
                  return (
                    <button
                      key={o.id}
                      type="button"
                      onClick={() => setSelected(o)}
                      data-testid={`kitchen-history-row-${o.id.slice(0,8)}`}
                      className="w-full text-left px-4 py-3 hover:bg-[var(--js-bg)] flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-1 rounded-full ${tagBg}`}>
                          {tagLabel}
                        </span>
                        <div className="min-w-0">
                          <p className="font-semibold text-sm truncate flex items-center gap-1">
                            <User className="w-3 h-3 shrink-0" /> {o.customer_name || "—"}
                          </p>
                          <p className="text-[11px] text-[var(--js-text-secondary)] truncate">
                            #{o.id.slice(0, 8)} · {(o.items || o.items_secure || []).slice(0, 2).map((it) => `${it.quantity}× ${it.name}`).join(" · ")}
                          </p>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-sm font-bold">{formatUSD(o.order_total_usd || o.total)}</p>
                        <p className="text-[10px] text-[var(--js-text-secondary)]">{ago(o.updated_at || o.created_at)}</p>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>

      {/* DETAIL MODAL */}
      {selected && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-[var(--js-border)]">
              <h3 className="font-bold text-lg">Order #{selected.id.slice(0,8)}</h3>
              <button onClick={() => setSelected(null)} className="p-2 hover:bg-gray-100 rounded-full">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-[var(--js-text-secondary)]">Customer</p>
                  <p className="font-semibold flex items-center gap-1"><User className="w-3 h-3" /> {selected.customer_name || "—"}</p>
                  <p className="text-[10px] text-[var(--js-text-secondary)] italic">Phone & address hidden — driver has them.</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--js-text-secondary)]">Type</p>
                  <p className="font-semibold capitalize">{selected.delivery_type}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--js-text-secondary)]">Driver</p>
                  <p className="font-semibold flex items-center gap-1"><Truck className="w-3 h-3" /> {selected.driver_name || "Not assigned yet"}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--js-text-secondary)]">Pickup status</p>
                  <Pill value={selected.pickup_status || "not_assigned"} />
                </div>
              </div>

              {/* Items */}
              <div className="border-t pt-3">
                <p className="text-xs font-bold uppercase tracking-wider text-[var(--js-text-secondary)] mb-2">Items</p>
                <ul className="space-y-1 text-sm">
                  {(selected.items || selected.items_secure || []).map((it, i) => (
                    <li key={i}>
                      <div className="flex justify-between">
                        <span><strong>{it.quantity}×</strong> {it.name}</span>
                        <span className="font-medium">{formatUSD(it.line_total_usd || it.price_usd * it.quantity)}</span>
                      </div>
                      {(it.sides || []).map((s, j) => (
                        <div key={j} className="text-xs text-[var(--js-text-secondary)] ml-4">+ {s.name}</div>
                      ))}
                    </li>
                  ))}
                </ul>
                {selected.note && (
                  <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-2 text-xs">
                    <strong>Note:</strong> {selected.note}
                  </div>
                )}
              </div>

              {/* Pickup OTP — visible once ready_for_pickup */}
              {["ready_for_pickup", "handed_to_driver"].includes(selected.seller_preparation_status) && selected.seller_pickup_otp && (
                <div className="border border-emerald-200 bg-emerald-50 rounded-xl p-3">
                  <p className="text-xs uppercase tracking-wider font-bold text-emerald-800 flex items-center gap-1">
                    <KeyRound className="w-3 h-3" /> Driver pickup OTP
                  </p>
                  <p className="text-3xl font-mono font-bold text-emerald-700 tracking-widest">{selected.seller_pickup_otp}</p>
                  <p className="text-[10px] text-emerald-800">Give this to the driver to confirm pickup.</p>
                </div>
              )}

              {/* Return banner */}
              {selected.return_status === "return_to_seller_pending" && (
                <div className="border border-orange-300 bg-orange-50 rounded-xl p-3">
                  <p className="text-xs uppercase font-bold text-orange-800 flex items-center gap-1">
                    <RotateCcw className="w-3 h-3" /> Driver returning item
                  </p>
                  <p className="text-xs text-orange-800">Ask the driver for the return OTP and confirm it under <strong>Wallet → Active Orders</strong>.</p>
                </div>
              )}

              {/* Actions — strictly the new state machine */}
              <div className="flex flex-wrap gap-2 pt-3 border-t">
                {selected.seller_preparation_status === "pending" && (
                  <button onClick={() => move(selected, "accept")} disabled={busy} className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-full">Accept order</button>
                )}
                {["pending","accepted"].includes(selected.seller_preparation_status) && (
                  <button onClick={() => move(selected, "preparing")} disabled={busy} className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-4 py-2 rounded-full">Mark preparing</button>
                )}
                {["pending","accepted","preparing"].includes(selected.seller_preparation_status) && (
                  <button onClick={() => move(selected, "ready-for-pickup")} disabled={busy} className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-full">Ready for pickup</button>
                )}
                {selected.pickup_status === "picked_up" && selected.seller_handover_status !== "handed_to_driver" && (
                  <button onClick={() => move(selected, "handed-to-driver")} disabled={busy} className="bg-[#1A1A1A] hover:bg-black text-white text-xs font-semibold px-4 py-2 rounded-full">Confirm I handed it to driver</button>
                )}
                <button onClick={() => printTicket(selected)} className="ml-auto inline-flex items-center gap-1 bg-gray-100 hover:bg-gray-200 text-[var(--js-text)] text-xs font-semibold px-4 py-2 rounded-full">
                  <Printer className="w-3 h-3" /> Print ticket
                </button>
              </div>

              {/* Cancel — only when still cancellable */}
              {["pending","accepted","preparing"].includes(selected.seller_preparation_status) ? (
                <div className="border-t pt-3 space-y-2">
                  <p className="text-xs font-bold uppercase tracking-wider text-red-700 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> Cancel this order
                  </p>
                  <input
                    type="text"
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    placeholder="Reason (optional)"
                    data-testid="kitchen-cancel-reason"
                    className="w-full px-3 py-2 border border-red-200 rounded-lg text-sm"
                  />
                  <button
                    onClick={() => cancelOrder(selected)}
                    disabled={busy}
                    data-testid="kitchen-cancel-btn"
                    className="bg-red-600 hover:bg-red-700 text-white text-xs font-semibold px-4 py-2 rounded-full"
                  >
                    Cancel order
                  </button>
                </div>
              ) : (
                <p className="text-[11px] text-[var(--js-text-secondary)] italic border-t pt-3">
                  This order is past <strong>ready for pickup</strong> — only admin can cancel it now.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}
