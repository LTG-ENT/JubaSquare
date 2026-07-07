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
  Download,
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

// Line total = (base price + Σ side prices) × qty. Matches the backend
// `subtotal` computation in server.py:create_restaurant_order so what the
// kitchen sees adds up correctly, including any side-options the customer
// picked.
function lineTotalUSD(it) {
  if (typeof it.line_total_usd === "number") return it.line_total_usd;
  const sidesTotal = (it.sides || []).reduce((a, s) => a + (s.price_usd || 0), 0);
  return (it.price_usd + sidesTotal) * (it.quantity || 1);
}

// Kitchen prep timer — computes elapsed minutes since the order was placed
// and compares against the max `prep_time_minutes` across the items. Returns
// {elapsed, target, late} where `late === true` means the order is overdue.
// When no item defines prep_time_minutes we fall back to a 15-min soft target
// so the badge is still useful (turns red past 15m).
const DEFAULT_PREP_TARGET_MIN = 15;
function orderPrepStatus(order) {
  if (!order || !order.created_at) return { elapsed: 0, target: DEFAULT_PREP_TARGET_MIN, late: false };
  const elapsed = Math.floor((Date.now() - new Date(order.created_at).getTime()) / 60000);
  const items = order.items || order.items_secure || [];
  const explicit = items
    .map((it) => Number(it.prep_time_minutes))
    .filter((n) => Number.isFinite(n) && n > 0);
  const target = explicit.length ? Math.max(...explicit) : DEFAULT_PREP_TARGET_MIN;
  return { elapsed: Math.max(0, elapsed), target, late: elapsed > target };
}

// Items subtotal — sum of `lineTotalUSD` across all items. This is the
// number the kitchen ticket cares about; delivery fee is handled by the
// driver/admin flow and should NOT appear on the kitchen ticket.
function itemsSubtotalUSD(order) {
  if (typeof order.subtotal === "number") return order.subtotal;
  return (order.items || order.items_secure || []).reduce((s, it) => s + lineTotalUSD(it), 0);
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
  // PWA install prompt — captured from window's beforeinstallprompt event.
  // Kitchen Dashboard is the ONLY page that surfaces this so restaurant staff
  // can install the app on a tablet at the pass without cluttering other UIs.
  const [installPrompt, setInstallPrompt] = useState(null);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    // Detect if we're already running as an installed PWA
    const isStandalone = window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;
    setInstalled(isStandalone);

    const onBeforeInstall = (e) => {
      e.preventDefault();
      setInstallPrompt(e);
    };
    const onInstalled = () => {
      setInstalled(true);
      setInstallPrompt(null);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const doInstall = async () => {
    if (!installPrompt) {
      toast.info("Install prompt not available — use your browser menu → 'Install app'");
      return;
    }
    try {
      installPrompt.prompt();
      const choice = await installPrompt.userChoice;
      if (choice.outcome === "accepted") {
        toast.success("App installing…");
        setInstalled(true);
      }
      setInstallPrompt(null);
    } catch (e) {
      toast.error("Install failed — try your browser menu");
    }
  };

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

  // Seller-as-driver flow — only enabled when the restaurant explicitly
  // opts into seller-managed delivery. The seller's OWN external driver
  // handles the trip; the platform does not track OTPs, signatures, or GPS
  // for these deliveries. The seller confirms completion when the driver
  // returns with the cash — one click.
  const sellerIsDriver = restaurant?.delivery_managed_by === "seller";

  const completeSelfDeliver = async (order) => {
    if (!window.confirm("Confirm order delivered and cash received from your driver?")) return;
    setBusy(true);
    try {
      await api.post(`/seller/restaurant-orders/${order.id}/self-deliver-complete`, {});
      toast.success("Order completed. Cash recorded.");
      await loadOrders();
      const fresh = (await api.get(`/restaurant-orders/${order.id}`)).data;
      setSelected(fresh);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Could not complete order");
    } finally {
      setBusy(false);
    }
  };

  const handToDriver = async (order) => {
    setBusy(true);
    try {
      await api.post(`/seller/restaurant-orders/${order.id}/self-deliver-start`);
      toast.success("Marked as handed to your driver.");
      await loadOrders();
      const fresh = (await api.get(`/restaurant-orders/${order.id}`)).data;
      setSelected(fresh);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Could not hand off");
    } finally {
      setBusy(false);
    }
  };

  // Customer receipt (separate from the kitchen ticket). Printable slip that
  // goes with the order to the customer — full breakdown, delivery address,
  // total, thank-you note. `curr` = 'USD' or 'SSP' — the seller picks when
  // they hit the Print button; SSP conversion uses the order's own
  // exchange_rate_ssp so the amount matches what the customer actually paid.
  const printCustomerReceipt = (order, curr = "USD") => {
    if (!order) return;
    const w = window.open("", "_blank");
    if (!w) return;
    const dt = new Date(order.created_at || Date.now());
    const rate = Number(order.exchange_rate_ssp) || 600;
    const fmt = (usd) => {
      const n = Number(usd) || 0;
      if (curr === "SSP") {
        return `SSP ${(n * rate).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
      }
      return formatUSD(n);
    };
    const dtStr = dt.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: true });
    const orderShort = `JS-${dt.toISOString().slice(2,10).replaceAll("-","")}-${order.id.slice(0,5).toUpperCase()}`;
    const restShort = `O-${dt.toISOString().slice(2,10).replaceAll("-","")}-${order.id.slice(-5).toUpperCase()}`;
    const paymentLabel = { cash_on_delivery: "Cash on Delivery", card: "Card", wallet: "Wallet" }[order.payment_method] || (order.payment_method || "Cash on Delivery").replaceAll("_", " ");
    const deliveryType = order.delivery_type === "delivery" ? "DELIVERY ORDER" : "PICKUP ORDER";
    const items = (order.items || order.items_secure || []);
    const rows = items.map((it, idx) => `
      <tr>
        <td class="num">${idx + 1}</td>
        <td class="itm">${it.name}${(it.sides || []).length ? '<div class="sides">' + it.sides.map(s => `+ ${s.name}${curr && s.price_usd ? ` (${fmt(s.price_usd)})` : ""}`).join("<br>") + "</div>" : ""}</td>
        <td class="qty">${it.quantity}</td>
      </tr>
    `).join("");

    // Monochrome inline SVG icons (stroke=#111) — printer-friendly, no emoji.
    const ICON_STORE = `<svg viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l1.5-4.5h15L21 9"/><path d="M4 9v11h16V9"/><path d="M9 20v-6h6v6"/></svg>`;
    const ICON_CLIPBOARD = `<svg viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="7" y="4" width="10" height="4" rx="1"/><path d="M5 6h2m10 0h2v14H5V6"/></svg>`;
    const ICON_CLOCK = `<svg viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`;
    const ICON_USER = `<svg viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>`;
    const ICON_PHONE = `<svg viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4l2 5-2.5 1.5a12 12 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 3 5a1 1 0 0 1 1-1z"/></svg>`;
    const ICON_PIN = `<svg viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s7-7 7-12a7 7 0 1 0-14 0c0 5 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>`;
    const ICON_CASH = `<svg viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="12" rx="1.5"/><circle cx="12" cy="13" r="2.5"/><path d="M5 10v6M19 10v6"/></svg>`;
    const ICON_NOTE = `<svg viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="18" rx="1.5"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>`;
    const ICON_BAG = `<svg viewBox="0 0 24 24" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="22" height="22"><path d="M5 8h14l-1 12H6L5 8z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/><circle cx="10" cy="13" r=".8" fill="#111"/><circle cx="14" cy="13" r=".8" fill="#111"/><path d="M9.5 15.5c.7.7 1.7 1 2.5 1s1.8-.3 2.5-1"/></svg>`;

    w.document.write(`<!doctype html><html><head><title>Customer Receipt ${order.id.slice(0,8)}</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: 'Helvetica Neue', Arial, sans-serif; width: 380px; margin: 20px auto; color: #111; font-size: 12px; line-height: 1.5; }
  .receipt { border: 1px dotted #888; padding: 22px; }
  h1 { text-align: center; font-size: 26px; letter-spacing: 4px; margin: 0 0 4px; font-weight: 800; }
  .dots { text-align: center; letter-spacing: 6px; color: #333; margin: 0 0 8px; font-size: 14px; }
  .badge { display: block; margin: 0 auto 14px; padding: 6px 22px; background: #111; color: #fff; text-align: center; font-weight: 700; letter-spacing: 3px; font-size: 12px; width: fit-content; }
  .divider { border-top: 1.5px dashed #888; margin: 12px 0; }
  .from { background: #f0f0f0; padding: 10px 14px; border-radius: 3px; font-weight: 700; margin-bottom: 12px; font-size: 13px; letter-spacing: 1px; display: flex; align-items: center; gap: 10px; }
  .from .r { font-size: 15px; letter-spacing: 0; text-transform: none; }
  .meta { display: table; width: 100%; margin-bottom: 8px; }
  .col { display: table-cell; width: 50%; vertical-align: top; padding: 0 10px; font-size: 11px; }
  .col + .col { border-left: 1px solid #999; }
  .row { margin: 8px 0; display: flex; align-items: flex-start; gap: 8px; }
  .ico { flex: 0 0 14px; margin-top: 2px; }
  .ico svg { width: 14px; height: 14px; display: block; }
  .lbl { font-weight: 700; letter-spacing: 1px; text-transform: uppercase; font-size: 10px; display: block; }
  .val { display: block; padding-top: 2px; }
  table.items { width: 100%; border-collapse: collapse; margin: 14px 0 8px; }
  table.items thead th { background: #111; color: #fff; padding: 8px 6px; text-align: left; font-size: 11px; letter-spacing: 2px; }
  table.items thead th.qty, table.items thead th.num { text-align: center; }
  table.items thead th.qty { text-align: right; }
  table.items tbody td { padding: 8px 6px; border-bottom: 1px dashed #bbb; }
  table.items tbody tr:last-child td { border-bottom: 1.5px solid #111; }
  td.num { width: 30px; text-align: center; color: #555; }
  td.qty { width: 40px; text-align: right; font-weight: 700; }
  .sides { color: #666; font-size: 10px; margin-top: 2px; }
  .foot-box { display: table; width: 100%; border: 1px solid #333; border-radius: 8px; margin: 14px 0 6px; }
  .foot-col { display: table-cell; width: 50%; padding: 12px 14px; vertical-align: top; font-size: 11px; }
  .foot-col + .foot-col { border-left: 1px dashed #999; }
  .foot-head { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
  .foot-head .lbl { display: inline; margin: 0; }
  .totals { text-align: right; padding: 6px 6px 4px; font-size: 12px; }
  .totals .big { font-size: 16px; font-weight: 800; margin-top: 4px; }
  .thanks { text-align: center; font-family: 'Brush Script MT', 'Lucida Handwriting', cursive; font-size: 26px; margin: 14px 0 6px; }
  .footer { text-align: center; font-size: 11px; margin-top: 4px; }
  .brand { display: flex; align-items: center; justify-content: center; gap: 8px; font-weight: 800; font-size: 18px; letter-spacing: 1px; margin-top: 4px; }
  .brand .bar { flex: 0 0 40px; height: 1px; background: #111; }
  .bottom-dots { text-align: center; letter-spacing: 4px; margin-top: 10px; color: #999; }
  @media print { body { margin: 0; } .receipt { border: none; } }
</style></head><body>
<div class="receipt">
  <h1>CUSTOMER RECEIPT</h1>
  <div class="dots">• • •</div>
  ${restaurant?.receipt_show_logo && (restaurant?.receipt_logo_url || restaurant?.image_url)
    ? `<div style="text-align:center;margin:8px 0 12px"><img src="${restaurant.receipt_logo_url || restaurant.image_url}" alt="${restaurant?.name || 'Logo'}" style="max-height:70px;max-width:220px;object-fit:contain"/></div>`
    : ""}
  <div class="badge">${deliveryType}</div>
  <div class="divider"></div>
  <div class="from">
    <span class="ico">${ICON_STORE}</span>
    <span>FROM ${order.delivery_type === "delivery" ? "RESTAURANT" : "PICKUP"}:</span>
    <span class="r">${restaurant?.name || "Restaurant"}</span>
  </div>
  <div class="divider"></div>

  <div class="meta">
    <div class="col">
      <div class="row"><span class="ico">${ICON_CLIPBOARD}</span><span><span class="lbl">Order ID</span><span class="val">${orderShort}</span></span></div>
      <div class="row"><span class="ico">${ICON_CLOCK}</span><span><span class="lbl">Order Time</span><span class="val">${dtStr}</span></span></div>
      <div class="row"><span class="ico">${ICON_STORE}</span><span><span class="lbl">Restaurant Order No.</span><span class="val">${restShort}</span></span></div>
    </div>
    <div class="col">
      <div class="row"><span class="ico">${ICON_USER}</span><span><span class="lbl">Customer</span><span class="val">${order.customer_name || "—"}</span></span></div>
      <div class="row"><span class="ico">${ICON_PHONE}</span><span><span class="lbl">Phone</span><span class="val">${order.customer_phone || "—"}</span></span></div>
      ${order.customer_address ? `<div class="row"><span class="ico">${ICON_PIN}</span><span><span class="lbl">Address</span><span class="val">${order.customer_address}${order.customer_area ? ", " + order.customer_area : ""}</span></span></div>` : ""}
    </div>
  </div>

  <table class="items">
    <thead><tr><th class="num">#</th><th>ITEMS</th><th class="qty">QTY</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>

  <div class="totals">
    <div>Subtotal: <strong>${fmt(itemsSubtotalUSD(order))}</strong></div>
    ${Number(order.delivery_fee || order.delivery_fee_usd || 0) > 0 ? `<div>Delivery: <strong>${fmt(Number(order.delivery_fee || order.delivery_fee_usd || 0))}</strong></div>` : ""}
    <div class="big">TOTAL: ${fmt(itemsSubtotalUSD(order) + Number(order.delivery_fee || order.delivery_fee_usd || 0))}</div>
    ${curr === "SSP" ? `<div style="font-size:10px;color:#666">Rate: 1 USD = SSP ${rate.toLocaleString()}</div>` : ""}
  </div>

  <div class="foot-box">
    <div class="foot-col">
      <div class="foot-head"><span class="ico">${ICON_CASH}</span><span class="lbl">Payment Method</span></div>
      ${paymentLabel}
    </div>
    <div class="foot-col">
      <div class="foot-head"><span class="ico">${ICON_NOTE}</span><span class="lbl">Note to Driver</span></div>
      ${order.note ? order.note : "Please collect the full amount from the customer. Thank you!"}
    </div>
  </div>

  <div class="thanks">Thank You!</div>
  <div class="footer">This order is placed on</div>
  <div class="brand"><span class="bar"></span>${ICON_BAG}<span>JubaSquare</span><span class="bar"></span></div>
  <div class="bottom-dots">• • • • • • • • • • • • • • •</div>
</div>
</body></html>`);
    w.document.close();
    setTimeout(() => w.print(), 300);
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
    // Kitchen ticket shows ITEMS TOTAL only (base prices + sides). Delivery
    // fee is intentionally excluded — kitchen doesn't handle delivery, and
    // showing it would confuse pack-out.
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
  <div class="row"><span>${it.quantity}× ${it.name}</span><span>${formatUSD(lineTotalUSD(it))}</span></div>
  ${(it.sides || []).map(s => `<div class="row" style="margin-left:12px;font-size:11px"><span>+ ${s.name}</span><span>${formatUSD((s.price_usd || 0) * (it.quantity || 1))}</span></div>`).join('')}
`).join('')}
<div class="hr"></div>
<div class="row big"><span>ITEMS TOTAL</span><span>${formatUSD(itemsSubtotalUSD(order))}</span></div>
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
          <div className="flex items-center gap-2 flex-wrap">
            {!installed && (
              <button
                onClick={doInstall}
                data-testid="kitchen-install-pwa"
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-[#0E1A2B] hover:bg-black text-white"
                title={installPrompt ? "Install this dashboard as an app on this device" : "Open your browser menu to install"}
              >
                <Download className="w-3.5 h-3.5" />
                {installPrompt ? "Install App" : "Install (browser menu)"}
              </button>
            )}
            {installed && (
              <span
                data-testid="kitchen-install-installed"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800"
              >
                <CheckCircle2 className="w-3.5 h-3.5" /> Installed
              </span>
            )}
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
                      <div className="flex items-center justify-between mb-1 gap-2">
                        <span
                          className="font-mono text-[10px] font-bold text-[var(--js-text)] bg-slate-100 rounded px-1.5 py-0.5"
                          data-testid={`kitchen-order-no-${o.id.slice(0,8)}`}
                          title="Restaurant order number"
                        >
                          O-{(o.created_at || "").slice(2,10).replaceAll("-","")}-{o.id.slice(-5).toUpperCase()}
                        </span>
                        {(() => {
                          const ps = orderPrepStatus(o);
                          return (
                            <span
                              data-testid={`prep-timer-${o.id.slice(0,8)}`}
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                ps.late ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"
                              }`}
                              title={`${ps.elapsed} min elapsed · ${ps.target} min target`}
                            >
                              {ps.elapsed}m / {ps.target}m
                            </span>
                          );
                        })()}
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
                        <span className="text-sm font-bold">{formatUSD(itemsSubtotalUSD(o))}</span>
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
                        <p className="text-sm font-bold">{formatUSD(itemsSubtotalUSD(o))}</p>
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
              <div>
                <h3 className="font-bold text-lg">Order #{selected.id.slice(0,8)}</h3>
                <p
                  className="font-mono text-[11px] font-bold text-[var(--js-text)] mt-0.5"
                  data-testid={`kitchen-detail-order-no-${selected.id.slice(0,8)}`}
                >
                  Restaurant Order No.: O-{(selected.created_at || "").slice(2,10).replaceAll("-","")}-{selected.id.slice(-5).toUpperCase()}
                </p>
              </div>
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
                        <span className="font-medium">{formatUSD(lineTotalUSD(it))}</span>
                      </div>
                      {(it.sides || []).map((s, j) => (
                        <div key={j} className="text-xs text-[var(--js-text-secondary)] ml-4 flex justify-between">
                          <span>+ {s.name}</span>
                          <span>{formatUSD((s.price_usd || 0) * (it.quantity || 1))}</span>
                        </div>
                      ))}
                    </li>
                  ))}
                </ul>
                {/* Items subtotal — matches ticket. Delivery fee is intentionally NOT
                    shown; the kitchen doesn't handle delivery. */}
                <div className="mt-3 pt-3 border-t flex justify-between items-center text-sm font-bold">
                  <span>Items total</span>
                  <span>{formatUSD(itemsSubtotalUSD(selected))}</span>
                </div>
                {selected.note && (
                  <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-2 text-xs">
                    <strong>Note:</strong> {selected.note}
                  </div>
                )}
              </div>

              {/* Pickup OTP — only useful when a platform driver picks up.
                  Hidden entirely when the seller manages delivery (their own
                  external driver doesn't verify against the platform). */}
              {!sellerIsDriver && ["ready_for_pickup", "handed_to_driver"].includes(selected.seller_preparation_status) && selected.seller_pickup_otp && (
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

              {/* Seller-as-driver: quick reminder that the seller's own external driver handles delivery.
                  Customer contact info is visible because delivery is seller-managed (already handled
                  by backend redaction). */}
              {sellerIsDriver && ["ready_for_pickup", "handed_to_driver"].includes(selected.seller_preparation_status) && selected.delivery_status !== "delivered" && (
                <div className="border border-[#C84B31]/30 bg-[#C84B31]/5 rounded-xl p-3 space-y-1" data-testid="seller-driver-info">
                  <p className="text-xs uppercase tracking-wider font-bold text-[#C84B31]">🛵 Hand off to your driver</p>
                  <div className="text-sm space-y-0.5">
                    <p><strong>To:</strong> {selected.customer_name || "—"}</p>
                    <p><strong>Phone:</strong> {selected.customer_phone ? <a className="text-[#C84B31] underline" href={`tel:${selected.customer_phone}`}>{selected.customer_phone}</a> : "—"}</p>
                    <p><strong>Address:</strong> {selected.customer_address || "—"}</p>
                    <p><strong>Area:</strong> {selected.customer_area || "—"}</p>
                  </div>
                  <p className="text-[10px] text-[var(--js-text-secondary)] pt-1">Print the customer receipt below and hand it to your driver along with the order.</p>
                </div>
              )}

              {/* Actions — strictly the new state machine */}
              <div className="flex flex-wrap gap-2 pt-3 border-t">
                {selected.seller_preparation_status === "pending" && (
                  <button onClick={() => move(selected, "accept")} disabled={busy} data-testid="kitchen-accept-btn" className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-full">Accept order</button>
                )}
                {["pending","accepted"].includes(selected.seller_preparation_status) && (
                  <button onClick={() => move(selected, "preparing")} disabled={busy} data-testid="kitchen-preparing-btn" className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-4 py-2 rounded-full">Mark preparing</button>
                )}
                {["pending","accepted","preparing"].includes(selected.seller_preparation_status) && (
                  <button onClick={() => move(selected, "ready-for-pickup")} disabled={busy} data-testid="kitchen-ready-btn" className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-full">Ready for pickup</button>
                )}

                {/* Seller-as-driver: 2-step flow (matches user's mental model)
                    ready_for_pickup → hand-to-driver
                    handed_to_driver → confirm delivery (cash received) */}
                {sellerIsDriver && selected.seller_preparation_status === "ready_for_pickup" && selected.delivery_status !== "delivered" && (
                  <button
                    onClick={() => handToDriver(selected)}
                    disabled={busy}
                    data-testid="self-deliver-start"
                    className="bg-[#1A1A1A] hover:bg-black text-white text-xs font-semibold px-4 py-2 rounded-full"
                  >
                    🛵 Hand to driver
                  </button>
                )}
                {sellerIsDriver && selected.seller_preparation_status === "handed_to_driver" && selected.delivery_status !== "delivered" && (
                  <button
                    onClick={() => completeSelfDeliver(selected)}
                    disabled={busy}
                    data-testid="self-deliver-complete"
                    className="bg-[#C84B31] hover:bg-[#A83A23] text-white text-xs font-semibold px-4 py-2 rounded-full"
                  >
                    ✓ Confirm delivery (cash received)
                  </button>
                )}

                {/* Separate-driver path: only show handover button when NOT self-delivering */}
                {!sellerIsDriver && selected.pickup_status === "picked_up" && selected.seller_handover_status !== "handed_to_driver" && (
                  <button onClick={() => move(selected, "handed-to-driver")} disabled={busy} className="bg-[#1A1A1A] hover:bg-black text-white text-xs font-semibold px-4 py-2 rounded-full">Confirm I handed it to driver</button>
                )}

                {/* Customer receipt with currency picker (USD / SSP).
                    Available from ready_for_pickup onward. */}
                {["ready_for_pickup", "handed_to_driver"].includes(selected.seller_preparation_status) && (
                  <div className="inline-flex items-center gap-0.5 border border-[var(--js-border)] rounded-full overflow-hidden">
                    <button
                      onClick={() => printCustomerReceipt(selected, "USD")}
                      data-testid="print-customer-receipt-usd"
                      className="inline-flex items-center gap-1 bg-white hover:bg-[var(--js-subtle)] text-[var(--js-text)] text-xs font-semibold px-3 py-2"
                      title="Print customer receipt in USD"
                    >
                      <Printer className="w-3 h-3" /> Receipt USD
                    </button>
                    <span className="w-px h-4 bg-[var(--js-border)]" />
                    <button
                      onClick={() => printCustomerReceipt(selected, "SSP")}
                      data-testid="print-customer-receipt-ssp"
                      className="inline-flex items-center gap-1 bg-white hover:bg-[var(--js-subtle)] text-[var(--js-text)] text-xs font-semibold px-3 py-2"
                      title="Print customer receipt in SSP (converted at the order's exchange rate)"
                    >
                      <Printer className="w-3 h-3" /> SSP
                    </button>
                  </div>
                )}

                <button onClick={() => printTicket(selected)} className="ml-auto inline-flex items-center gap-1 bg-gray-100 hover:bg-gray-200 text-[var(--js-text)] text-xs font-semibold px-4 py-2 rounded-full">
                  <Printer className="w-3 h-3" /> Kitchen ticket
                </button>
              </div>

              {/* Cancel — cancellable while preparing; also while at
                  ready_for_pickup when the seller manages delivery (their own
                  driver hasn't picked up from the platform's perspective). */}
              {(["pending","accepted","preparing"].includes(selected.seller_preparation_status)
                || (sellerIsDriver && selected.seller_preparation_status === "ready_for_pickup" && selected.delivery_status !== "delivered")) ? (
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
                  This order is past cancellation — only admin can cancel it now.
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
