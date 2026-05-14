import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { useCart } from "@/context/CartContext";
import { useTranslation } from "react-i18next";
import api, { formatUSD, formatPrice, formatDetail } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import SignaturePad from "@/components/SignaturePad";
import OrderChatButton from "@/components/OrderChatButton";
import { toast } from "sonner";
import {
  Truck,
  Package,
  Phone,
  MapPin,
  KeyRound,
  CheckCircle2,
  XCircle,
  Coins,
  RotateCcw,
  ArrowLeft,
} from "lucide-react";

const PILL = {
  unassigned: "bg-gray-100 text-gray-700",
  offered: "bg-purple-100 text-purple-800",
  assigned: "bg-blue-100 text-blue-700",
  pending_pickup: "bg-blue-100 text-blue-700",
  picked_up: "bg-amber-100 text-amber-700",
  out_for_delivery: "bg-amber-100 text-amber-800",
  delivered: "bg-emerald-100 text-emerald-700",
  delivery_failed: "bg-red-100 text-red-700",
  return_to_seller_pending: "bg-orange-100 text-orange-700",
  returned_to_seller: "bg-gray-100 text-gray-700",
  pending_collection: "bg-gray-100 text-gray-700",
  collected_by_driver: "bg-amber-100 text-amber-700",
  received_by_admin: "bg-emerald-100 text-emerald-700",
  pending: "bg-amber-100 text-amber-700",
  not_required: "bg-gray-100 text-gray-600",
  pending_return: "bg-orange-100 text-orange-700",
  returned: "bg-gray-100 text-gray-700",
  ready_for_pickup: "bg-emerald-100 text-emerald-700",
  accepted: "bg-blue-100 text-blue-700",
  preparing: "bg-amber-100 text-amber-700",
  handed_to_driver: "bg-emerald-200 text-emerald-800",
};

function Pill({ value }) {
  const cls = PILL[value] || "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold ${cls}`}>
      {String(value || "—").replace(/_/g, " ")}
    </span>
  );
}

const FAILURE_REASONS = [
  ["customer_not_available", "Customer not available"],
  ["customer_refused_to_pay", "Customer refused to pay"],
  ["customer_phone_unreachable", "Customer phone unreachable"],
  ["wrong_address", "Wrong address"],
  ["customer_cancelled_at_delivery", "Customer cancelled at delivery"],
  ["product_damaged", "Product damaged"],
  ["driver_problem", "Driver problem"],
  ["seller_gave_wrong_item", "Seller gave wrong item"],
  ["other", "Other"],
];

export default function DriverDashboard() {
  const { user } = useAuth();
  const { currency = "USD", exchangeRate = 1 } = useCart() || {}; // Get currency and exchange rate with defaults
  const { t: tr } = useTranslation();
  const [data, setData] = useState({ splits: [], restaurant_orders: [] });
  const [requests, setRequests] = useState({ splits: [], restaurant_orders: [] });
  const [cashSummary, setCashSummary] = useState({ pending_total_usd: 0, pending_count: 0, received_today_count: 0, items: [] });
  const [filter, setFilter] = useState(""); // delivery_status filter
  const [open, setOpen] = useState(null); // { ...row, _kind }
  const [loading, setLoading] = useState(true);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [actingRequestIds, setActingRequestIds] = useState(new Set());
  // Driver's current area (for "near me" sorting of new delivery requests)
  const [driverArea, setDriverArea] = useState(() => localStorage.getItem("driver_current_area") || "");
  const [areas, setAreas] = useState([]);
  const [reqIndex, setReqIndex] = useState(0); // shows one request at a time

  // Persist driver area
  useEffect(() => {
    if (driverArea) localStorage.setItem("driver_current_area", driverArea);
  }, [driverArea]);

  // Load admin-defined area list
  useEffect(() => {
    api.get("/meta/areas")
      .then((r) => setAreas(Array.isArray(r.data) ? r.data : []))
      .catch(() => setAreas([]));
  }, []);

  // Load accepted assignments
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(`/driver/assignments${filter ? `?status=${filter}` : ""}`);
      setData(r.data || { splits: [], restaurant_orders: [] });
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to load assignments");
    } finally { setLoading(false); }
  }, [filter]);

  // Load pending delivery requests
  const loadRequests = useCallback(async () => {
    setRequestsLoading(true);
    try {
      const r = await api.get("/driver/delivery-requests");
      setRequests(r.data || { splits: [], restaurant_orders: [] });
    } catch (e) {
      console.error("Failed to load delivery requests:", e);
    } finally { setRequestsLoading(false); }
  }, []);

  // Load cash summary (pending handover totals)
  const loadCashSummary = useCallback(async () => {
    try {
      const r = await api.get("/driver/cash-summary");
      setCashSummary(r.data || { pending_total_usd: 0, pending_count: 0, received_today_count: 0, items: [] });
    } catch (e) {
      // silent
    }
  }, []);

  useEffect(() => {
    load();
    loadRequests();
    loadCashSummary();
  }, [load, loadRequests, loadCashSummary]);

  // Auto-refresh everything every 15 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      load();
      loadRequests();
      loadCashSummary();
    }, 15000);
    return () => clearInterval(interval);
  }, [load, loadRequests, loadCashSummary]);

  const all = [
    ...(data.splits || []).map((s) => ({ ...s, _kind: "split" })),
    ...(data.restaurant_orders || []).map((r) => ({ ...r, _kind: "rest" })),
  ].filter((item) => {
    // Filter out cancelled orders
    if (item.seller_preparation_status === "cancelled" || item.delivery_status === "failed") {
      return false;
    }
    
    // Handle "completed" filter - show only items where admin received cash
    if (filter === "completed") {
      return item.cash_handover_status === "received";
    }
    
    // Hide completed deliveries (cash received by admin) from default "Active deliveries" view
    // Show them only when "completed" filter is explicitly selected
    if (!filter) {
      // In default view, hide items where admin has already received cash
      return item.cash_handover_status !== "received";
    }
    
    // For other filters, show all matching items
    return true;
  });

  const allRequests = [
    ...(requests.splits || []).map((s) => ({ ...s, _kind: "split" })),
    ...(requests.restaurant_orders || []).map((r) => ({ ...r, _kind: "rest" })),
  ];

  // Sort: exact pickup area match (driver's current area) first, then others.
  const sortedRequests = (() => {
    if (!driverArea) return allRequests;
    const a = driverArea.toLowerCase();
    const isMatch = (r) => {
      const pickup = (r.pickup_area || r.seller_area || r.shop_area || r.restaurant_area || "").toLowerCase();
      return pickup === a;
    };
    return [...allRequests].sort((x, y) => Number(isMatch(y)) - Number(isMatch(x)));
  })();

  // Clamp request index when list size changes
  useEffect(() => {
    if (reqIndex >= sortedRequests.length) setReqIndex(0);
  }, [sortedRequests.length, reqIndex]);

  const currentReq = sortedRequests[reqIndex] || null;
  const isReqNearMe = currentReq && driverArea
    ? (currentReq.pickup_area || currentReq.seller_area || currentReq.shop_area || currentReq.restaurant_area || "").toLowerCase() === driverArea.toLowerCase()
    : false;

  // Handle accept/reject (duplicate-action protected)
  const handleAcceptReject = async (item, action, rejectReason = null) => {
    if (actingRequestIds.has(item.id)) return; // already in-flight — prevent double click
    setActingRequestIds((prev) => { const n = new Set(prev); n.add(item.id); return n; });
    const endpoint = item._kind === "rest"
      ? `/driver/restaurant-orders/${item.id}/${action === "accept" ? "accept-offer" : "decline-offer"}`
      : `/driver/splits/${item.id}/${action === "accept" ? "accept-offer" : "decline-offer"}`;

    try {
      const body = action === "reject" && rejectReason ? { action: "reject", reject_reason: rejectReason } : {};
      await api.post(endpoint, body);
      toast.success(action === "accept" ? "Delivery accepted!" : "Delivery rejected");
      
      // Immediately remove this request from UI
      setRequests((prev) => ({
        splits: (prev.splits || []).filter((s) => s.id !== item.id),
        restaurant_orders: (prev.restaurant_orders || []).filter((r) => r.id !== item.id),
      }));
      
      // Reset index if we removed the last item or went beyond the new length
      const newLength = (requests.splits?.length || 0) + (requests.restaurant_orders?.length || 0) - 1;
      if (reqIndex >= newLength && newLength > 0) {
        setReqIndex(0);
      }
      
      loadRequests(); // Refresh requests from backend
      load(); // Refresh assignments
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || `Failed to ${action}`);
    } finally {
      setActingRequestIds((prev) => { const n = new Set(prev); n.delete(item.id); return n; });
    }
  };

  if (open) {
    return (
      <div className="min-h-screen flex flex-col bg-[var(--js-bg)]">
        <Header />
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 w-full flex-1">
          <button onClick={() => { setOpen(null); load(); }} className="flex items-center gap-1 text-sm text-[var(--js-text-secondary)] hover:text-[var(--js-text)] mb-4">
            <ArrowLeft className="w-4 h-4" /> Back to my deliveries
          </button>
          <DeliveryDetail row={open} reload={load} setOpen={setOpen} />
        </div>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[var(--js-bg)]">
      <Header />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 w-full flex-1">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-1">{tr("dashboard")}</p>
        <h1 className="font-display font-bold text-3xl text-[var(--js-text)]">{tr("myDeliveries")}</h1>
        <p className="text-sm text-[var(--js-text-secondary)]">Hi {user?.name?.split(" ")?.[0]} — here are the orders assigned to you.</p>

        {/* Cash to hand over summary */}
        <div
          data-testid="driver-cash-summary"
          className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3"
        >
          <div className="rounded-2xl border border-[#E9C46A]/40 bg-gradient-to-br from-[#E9C46A]/15 to-white p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] font-bold text-[var(--js-text-secondary)] flex items-center gap-1">
              <Coins className="w-3 h-3" /> Cash to hand over
            </p>
            <p
              data-testid="cash-pending-total"
              className="font-display font-bold text-2xl mt-1 text-[var(--js-text)]"
            >
              {formatPrice(cashSummary.pending_total_usd || 0, exchangeRate, currency)}
            </p>
            <p className="text-xs text-[var(--js-text-secondary)] mt-0.5">
              From {cashSummary.pending_count || 0} order{cashSummary.pending_count === 1 ? "" : "s"}
            </p>
          </div>
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] font-bold text-[var(--js-text-secondary)]">Handed over today</p>
            <p
              data-testid="cash-received-today"
              className="font-display font-bold text-2xl mt-1 text-emerald-700"
            >
              {cashSummary.received_today_count || 0}
            </p>
            <p className="text-xs text-[var(--js-text-secondary)] mt-0.5">Cash receipts received by admin</p>
          </div>
          <div className="rounded-2xl border border-[var(--js-border)] bg-[var(--js-subtle)] p-4 flex items-center justify-center text-center">
            <p className="text-xs text-[var(--js-text-secondary)] leading-snug">
              Hand over cash to admin to clear this list. Amounts shown in your selected currency.
            </p>
          </div>
        </div>

        {/* New Delivery Requests Section */}
        {sortedRequests.length > 0 && currentReq && (
          <div className="mt-6 bg-gradient-to-r from-[#C84B31] to-[#E9C46A] p-[2px] rounded-2xl">
            <div className="bg-white rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                <div>
                  <h2 className="font-bold text-lg text-[var(--js-text)] flex items-center gap-2">
                    <Package className="w-5 h-5 text-[#C84B31]" />
                    New Delivery Requests
                  </h2>
                  <p className="text-sm text-[var(--js-text-secondary)]">
                    Showing {reqIndex + 1} of {sortedRequests.length}
                  </p>
                </div>
                {/* Driver current-area dropdown */}
                <div className="flex items-center gap-2">
                  <label htmlFor="driver-area-select" className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">
                    <MapPin className="w-3.5 h-3.5 inline mr-1" /> My area
                  </label>
                  <select
                    id="driver-area-select"
                    data-testid="driver-current-area"
                    value={driverArea}
                    onChange={(e) => { setDriverArea(e.target.value); setReqIndex(0); }}
                    className="px-3 py-1.5 border border-[var(--js-border)] rounded-full text-sm bg-white"
                  >
                    <option value="">— Select area —</option>
                    {areas.map((a) => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Single request card */}
              <div
                key={currentReq.id}
                data-testid={`driver-request-card-${currentReq.id}`}
                className={`border-2 rounded-xl p-4 ${isReqNearMe ? "border-[#2A9D8F] bg-emerald-50" : "border-[#E9C46A] bg-[#FFF9F0]"}`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="font-mono text-xs text-[var(--js-text-secondary)] mb-1">
                      {currentReq._kind === "rest" ? "🍽️ RESTAURANT" : "🛒 MARKETPLACE"}
                      {isReqNearMe && (
                        <span data-testid="near-me-badge" className="ml-2 inline-flex items-center gap-1 bg-[#2A9D8F] text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                          Near you
                        </span>
                      )}
                    </p>
                    <p className="font-bold text-[var(--js-text)]">{currentReq.shop_name || currentReq.restaurant_name}</p>
                  </div>
                  <Pill value="offered" />
                </div>

                <div className="space-y-2 text-sm mb-4">
                  <div className="flex items-center gap-2 text-[var(--js-text-secondary)]">
                    <MapPin className="w-4 h-4 text-[#C84B31]" />
                    <span className="font-medium">Pickup:</span> {currentReq.pickup_area || currentReq.seller_area || currentReq.shop_area || currentReq.restaurant_area || "N/A"}
                  </div>
                  <div className="flex items-center gap-2 text-[var(--js-text-secondary)]">
                    <MapPin className="w-4 h-4 text-[#2A9D8F]" />
                    <span className="font-medium">Deliver to:</span> {currentReq.delivery_area || currentReq.customer_area || "N/A"}
                  </div>
                  <div className="flex items-center gap-2 text-[var(--js-text-secondary)]">
                    <Coins className="w-4 h-4 text-[#E9C46A]" />
                    <span className="font-medium">Order subtotal:</span> {formatPrice(currentReq.product_subtotal_usd || ((currentReq.order_total_usd || currentReq.total || 0) - (currentReq.delivery_fee_usd || 0)), currentReq.exchange_rate_ssp || exchangeRate, currency)}
                  </div>
                  {currentReq.delivery_fee_usd > 0 && (
                    <div className="flex items-center gap-2 text-[var(--js-text-secondary)]">
                      <Truck className="w-4 h-4 text-[#264653]" />
                      <span className="font-medium">Delivery fee:</span> {formatPrice(currentReq.delivery_fee_usd, currentReq.exchange_rate_ssp || exchangeRate, currency)}
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => handleAcceptReject(currentReq, "accept")}
                    disabled={actingRequestIds.has(currentReq.id)}
                    data-testid={`request-accept-${currentReq.id}`}
                    className="flex-1 bg-[#2A9D8F] hover:bg-[#238276] disabled:bg-[#2A9D8F]/50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg transition flex items-center justify-center gap-1"
                  >
                    <CheckCircle2 className="w-4 h-4" /> {actingRequestIds.has(currentReq.id) ? "Accepting…" : "Accept"}
                  </button>
                  <button
                    onClick={() => {
                      const reason = prompt("Reason for rejecting (optional):");
                      if (reason !== null) handleAcceptReject(currentReq, "reject", reason);
                    }}
                    disabled={actingRequestIds.has(currentReq.id)}
                    data-testid={`request-reject-${currentReq.id}`}
                    className="flex-1 bg-white hover:bg-gray-50 disabled:bg-gray-50 disabled:cursor-not-allowed text-[#D90429] border-2 border-[#D90429] font-semibold py-2.5 rounded-lg transition flex items-center justify-center gap-1"
                  >
                    <XCircle className="w-4 h-4" /> Reject
                  </button>
                </div>
              </div>

              {/* Prev / Next nav (only when multiple requests) */}
              {sortedRequests.length > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <button
                    onClick={() => setReqIndex((i) => (i - 1 + sortedRequests.length) % sortedRequests.length)}
                    data-testid="request-prev-btn"
                    className="px-4 py-2 text-sm font-semibold bg-[var(--js-subtle)] hover:bg-[var(--js-border)] rounded-full"
                  >
                    ← Previous
                  </button>
                  <div className="flex gap-1">
                    {sortedRequests.map((_, i) => (
                      <button
                        key={i}
                        onClick={() => setReqIndex(i)}
                        data-testid={`request-dot-${i}`}
                        className={`w-2 h-2 rounded-full transition ${i === reqIndex ? "bg-[#C84B31] w-6" : "bg-[var(--js-border)]"}`}
                        aria-label={`Go to request ${i + 1}`}
                      />
                    ))}
                  </div>
                  <button
                    onClick={() => setReqIndex((i) => (i + 1) % sortedRequests.length)}
                    data-testid="request-next-btn"
                    className="px-4 py-2 text-sm font-semibold bg-[var(--js-subtle)] hover:bg-[var(--js-border)] rounded-full"
                  >
                    Next →
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* My Assignments Section Header */}
        <div className="mt-8">
          <h2 className="font-bold text-xl text-[var(--js-text)] mb-4">{tr("myAcceptedDeliveries")}</h2>
        </div>

        <div className="flex gap-2 flex-wrap items-center">
          <select value={filter} onChange={(e) => setFilter(e.target.value)} data-testid="driver-filter" className="px-3 py-2 border border-[var(--js-border)] rounded-lg text-sm">
            <option value="">Active deliveries</option>
            <option value="offered">Offered (action needed)</option>
            <option value="assigned">Assigned (new)</option>
            <option value="picked_up">Picked up</option>
            <option value="out_for_delivery">Out for delivery</option>
            <option value="delivered">Delivered</option>
            <option value="completed">Completed (history)</option>
            <option value="delivery_failed">Failed</option>
          </select>
          <p className="text-sm text-[var(--js-text-secondary)] ml-auto">{all.length} delivery(ies)</p>
        </div>

        {loading ? (
          <p className="text-center py-12 text-[var(--js-text-secondary)]">Loading…</p>
        ) : all.length === 0 ? (
          <div className="text-center py-16 mt-6 border border-dashed border-[var(--js-border)] rounded-2xl">
            <Truck className="w-12 h-12 mx-auto text-[var(--js-text-secondary)] mb-3" />
            <p className="text-[var(--js-text-secondary)]">Nothing to deliver right now. Admin will assign new orders here.</p>
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            {all.map((r) => {
              const isOffered = r.delivery_status === "offered";
              return (
              <div key={r.id} className="text-left bg-white hover:shadow-md transition border border-[var(--js-border)] rounded-2xl p-4">
                <button
                  onClick={() => setOpen(r)}
                  data-testid={`driver-card-${r.id.slice(0,8)}`}
                  className="w-full text-left"
                >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs text-[var(--js-text-secondary)]">
                    {r._kind === "rest" ? "RESTAURANT" : "MARKETPLACE"} • {r.id.slice(0, 8)}
                  </span>
                  <Pill value={r.delivery_status} />
                </div>
                <p className="font-bold text-[var(--js-text)] flex items-center gap-2"><Package className="w-4 h-4" /> {r.shop_name || r.restaurant_name}</p>
                <p className="text-xs text-[var(--js-text-secondary)] flex items-center gap-1 mt-1"><MapPin className="w-3 h-3" /> Pickup: {r.shop_area || "—"}</p>
                <hr className="my-3 border-[var(--js-border)]" />
                <p className="font-semibold">{r.customer_name}</p>
                {!isOffered && (
                  <>
                    <p className="text-xs text-[var(--js-text-secondary)] flex items-center gap-1"><Phone className="w-3 h-3" /> {r.customer_phone || "—"}</p>
                    <p className="text-xs text-[var(--js-text-secondary)] flex items-center gap-1"><MapPin className="w-3 h-3" /> {r.customer_area} — {r.customer_address}</p>
                  </>
                )}
                <div className="mt-3 flex items-center justify-between">
                  <div>
                    <span className="text-lg font-bold text-[var(--js-text)]">{formatPrice(r.product_subtotal_usd || ((r.order_total_usd || 0) - (r.delivery_fee_usd || 0)), r.exchange_rate_ssp || exchangeRate, currency)}</span>
                    {r.delivery_fee_usd > 0 && (
                      <p className="text-xs text-[var(--js-text-secondary)]">+ {formatPrice(r.delivery_fee_usd, r.exchange_rate_ssp || exchangeRate, currency)} delivery</p>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Pill value={r.payment_status} />
                  </div>
                </div>
                </button>
                {isOffered && r._kind === "rest" && (
                  <DriverOfferActions row={r} reload={load} />
                )}
              </div>
            );})}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}

function DeliveryDetail({ row, reload, setOpen }) {
  const { currency = "USD", exchangeRate = 1 } = useCart() || {};
  const [r, setR] = useState(row);
  const [otp, setOtp] = useState("");
  const [signature, setSignature] = useState("");
  const [receiver, setReceiver] = useState("");
  const [proofPhoto, setProofPhoto] = useState(""); // base64 data URL — optional
  const [failReason, setFailReason] = useState("customer_not_available");
  const [failNote, setFailNote] = useState("");
  const [busy, setBusy] = useState(false);

  const isRest = r._kind === "rest";
  const base = isRest ? `/driver/restaurant-orders/${r.id}` : `/driver/splits/${r.id}`;
  const detailBase = isRest ? `/driver/assignments/restaurant-order/${r.id}` : `/driver/assignments/split/${r.id}`;

  const refresh = async () => {
    try {
      const resp = await api.get(detailBase);
      setR({ ...resp.data, _kind: r._kind });
    } catch {
      /* ignore */
    }
  };
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  const post = async (action, body) => {
    setBusy(true);
    try {
      await api.post(`${base}/${action}`, body || {});
      toast.success("Done");
      await refresh();
      reload();
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Action failed");
    } finally { setBusy(false); }
  };

  const submitPickup = (e) => {
    e?.preventDefault?.();
    if (!otp.trim()) { toast.error("Ask the seller for the pickup OTP"); return; }
    post("pickup", { otp: otp.trim() }).then(() => setOtp(""));
  };

  const submitDeliver = (e) => {
    e?.preventDefault?.();
    if (!otp.trim() || !signature || !receiver.trim()) {
      toast.error("OTP, signature and receiver name are all required");
      return;
    }
    post("deliver", {
      otp: otp.trim(),
      signature_b64: signature,
      receiver_name: receiver.trim(),
      picture_b64: proofPhoto || null,
    }).then(() => {
      setOtp(""); setSignature(""); setReceiver(""); setProofPhoto("");
    });
  };

  const onPhotoPick = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 4 * 1024 * 1024) {
      toast.error("Photo is too large (max 4MB)");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setProofPhoto(String(reader.result || ""));
    reader.onerror = () => toast.error("Could not read photo");
    reader.readAsDataURL(f);
  };

  const submitFail = (e) => {
    e?.preventDefault?.();
    post("delivery-failed", { reason: failReason, note: failNote });
  };

  return (
    <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="font-bold text-lg">{r.shop_name || r.restaurant_name} → {r.customer_name}</h2>
        <span className="font-mono text-xs text-[var(--js-text-secondary)]">{r.id.slice(0, 8)}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Pill value={r.delivery_status} />
        <Pill value={r.pickup_status} />
        <Pill value={r.seller_handover_status} />
        <Pill value={r.payment_status} />
        <Pill value={r.return_status} />
      </div>

      {/* Pickup info */}
      <section className="border border-[var(--js-border)] rounded-xl p-4 bg-[var(--js-bg)]">
        <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)] mb-2">Pickup from seller</p>
        <p className="font-semibold">{r.shop_name || r.restaurant_name}</p>
        <p className="text-xs flex items-center gap-1"><MapPin className="w-3 h-3" /> {r.shop_area || "—"}</p>
        {r.seller_phone && <p className="text-xs flex items-center gap-1"><Phone className="w-3 h-3" /> {r.seller_phone}</p>}
      </section>

      {/* Customer info */}
      <section className="border border-[var(--js-border)] rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Deliver to customer</p>
          <OrderChatButton orderId={r.order_id} label="Contact Customer" />
        </div>
        <p className="font-semibold">{r.customer_name}</p>
        <p className="text-xs flex items-center gap-1"><Phone className="w-3 h-3" /> {r.customer_phone || "—"}</p>
        <p className="text-xs flex items-center gap-1"><MapPin className="w-3 h-3" /> {r.customer_area} — {r.customer_address}</p>
      </section>

      {/* Items */}
      <section className="border border-[var(--js-border)] rounded-xl p-4">
        <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)] mb-2">Items to collect</p>
        <ul className="text-sm space-y-1">
          {(r.items || r.items_secure || []).map((it, i) => (
            <li key={i} className="flex justify-between">
              <span>{it.name} × {it.quantity}</span>
              <span className="font-medium">{formatPrice(it.line_total_usd || (it.price_usd * it.quantity), it.exchange_rate_ssp || r.exchange_rate_ssp || exchangeRate, currency)}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3 pt-3 border-t border-[var(--js-border)] flex justify-between font-bold">
          <span>Total to collect (COD)</span>
          <span className="text-xl">{formatPrice(r.order_total_usd, r.exchange_rate_ssp || exchangeRate, currency)}</span>
        </div>
      </section>

      {/* OFFERED step — driver must Accept or Decline first */}
      {r.delivery_status === "offered" && (
        <div className="border-2 border-purple-300 bg-purple-50 rounded-xl p-4 space-y-3">
          <div>
            <p className="text-sm font-semibold text-purple-900">New delivery offered</p>
            <p className="text-xs text-purple-800">
              Auto-assigned to you. Accept to commit, or decline so the next driver can pick it up.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={async () => { await post("decline-offer"); setOpen?.(null); }}
              disabled={busy}
              data-testid="detail-decline-offer"
              className="flex-1 inline-flex items-center justify-center gap-1 bg-white hover:bg-red-50 disabled:opacity-50 border border-red-300 text-red-700 text-sm font-semibold py-2 rounded-full"
            >
              <XCircle className="w-4 h-4" /> Decline
            </button>
            <button
              type="button"
              onClick={async () => { await post("accept-offer"); setOpen?.(null); }}
              disabled={busy}
              data-testid="detail-accept-offer"
              className="flex-1 inline-flex items-center justify-center gap-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-semibold py-2 rounded-full"
            >
              <CheckCircle2 className="w-4 h-4" /> Accept
            </button>
          </div>
        </div>
      )}

      {/* PICKUP step */}
      {r.delivery_status === "assigned" && (
        <form onSubmit={submitPickup} className="border-2 border-blue-200 bg-blue-50 rounded-xl p-4 space-y-3">
          <p className="text-sm font-semibold text-blue-900 flex items-center gap-2"><KeyRound className="w-4 h-4" /> Seller will give you a 4-digit pickup OTP</p>
          {r.seller_preparation_status !== "ready_for_pickup" && (
            <p className="text-xs text-blue-800">Wait — the seller hasn’t marked the order ready yet (current: {r.seller_preparation_status}).</p>
          )}
          <input type="text" inputMode="numeric" value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="Pickup OTP" data-testid="pickup-otp" className="w-full px-4 py-3 text-2xl font-mono tracking-widest text-center border border-blue-300 rounded-lg" />
          <button type="submit" disabled={busy || r.seller_preparation_status !== "ready_for_pickup"} className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold py-3 rounded-full">Confirm pickup</button>
        </form>
      )}

      {/* OUT FOR DELIVERY step */}
      {r.delivery_status === "picked_up" && (
        <div className="border-2 border-amber-200 bg-amber-50 rounded-xl p-4 space-y-2">
          {r.seller_handover_status !== "handed_to_driver" ? (
            <p className="text-xs text-amber-800">Waiting for the seller to confirm they handed the item to you. Once they confirm, you can start delivery.</p>
          ) : (
            <button onClick={() => post("out-for-delivery")} disabled={busy} className="w-full bg-amber-600 hover:bg-amber-700 text-white font-semibold py-3 rounded-full">Start delivery — I’m on my way</button>
          )}
        </div>
      )}

      {/* DELIVER step */}
      {r.delivery_status === "out_for_delivery" && (
        <form onSubmit={submitDeliver} className="border-2 border-emerald-200 bg-emerald-50 rounded-xl p-4 space-y-3">
          <p className="text-sm font-semibold text-emerald-900">Proof of delivery</p>
          <input value={receiver} onChange={(e) => setReceiver(e.target.value)} required placeholder="Receiver full name" data-testid="receiver-name" className="w-full px-3 py-2 border border-emerald-300 rounded-lg" />
          <input type="text" inputMode="numeric" value={otp} onChange={(e) => setOtp(e.target.value)} required placeholder="Customer delivery OTP" data-testid="delivery-otp" className="w-full px-4 py-3 text-2xl font-mono tracking-widest text-center border border-emerald-300 rounded-lg" />
          <SignaturePad onChange={setSignature} />

          {/* Optional photo proof */}
          <div className="bg-white border border-emerald-200 rounded-lg p-3">
            <label className="block text-xs font-semibold text-emerald-900 mb-2">
              Photo of handover (optional)
            </label>
            {proofPhoto ? (
              <div className="space-y-2">
                <img
                  src={proofPhoto}
                  alt="Delivery proof"
                  data-testid="delivery-proof-photo-preview"
                  className="w-full max-h-40 object-cover rounded-md border border-emerald-200"
                />
                <button
                  type="button"
                  onClick={() => setProofPhoto("")}
                  data-testid="delivery-proof-photo-clear"
                  className="text-xs text-red-700 hover:underline"
                >
                  Remove photo
                </button>
              </div>
            ) : (
              <label className="flex items-center justify-center gap-2 cursor-pointer border-2 border-dashed border-emerald-300 hover:border-emerald-500 rounded-md py-3 text-sm font-semibold text-emerald-800">
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  data-testid="delivery-proof-photo-input"
                  className="hidden"
                  onChange={onPhotoPick}
                />
                📷 Take or upload photo
              </label>
            )}
            <p className="text-[10px] text-emerald-700 mt-1">
              Optional — proof if customer disputes delivery. Max 4 MB.
            </p>
          </div>

          <button type="submit" disabled={busy || !signature} className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-300 text-white font-semibold py-3 rounded-full flex items-center justify-center gap-2">
            <CheckCircle2 className="w-4 h-4" /> Mark delivered
          </button>
          <details className="mt-2">
            <summary className="text-xs text-red-700 cursor-pointer">Delivery failed? Report it</summary>
            <div className="mt-2 space-y-2">
              <select value={failReason} onChange={(e) => setFailReason(e.target.value)} className="w-full px-3 py-2 border border-red-300 rounded-lg text-sm">
                {FAILURE_REASONS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
              <textarea value={failNote} onChange={(e) => setFailNote(e.target.value)} placeholder="Optional note" rows={2} className="w-full px-3 py-2 border border-red-300 rounded-lg text-sm" />
              <button type="button" onClick={submitFail} disabled={busy} className="w-full bg-red-600 hover:bg-red-700 text-white text-sm font-semibold py-2 rounded-full flex items-center justify-center gap-2">
                <XCircle className="w-4 h-4" /> Mark delivery failed
              </button>
            </div>
          </details>
        </form>
      )}

      {/* CASH step */}
      {r.delivery_status === "delivered" && r.payment_status !== "received_by_admin" && (
        <div className="border-2 border-yellow-200 bg-yellow-50 rounded-xl p-4 space-y-2">
          {r.payment_status === "pending_collection" ? (
            <button onClick={() => post("cash-collected")} disabled={busy} className="w-full bg-yellow-600 hover:bg-yellow-700 text-white font-semibold py-3 rounded-full flex items-center justify-center gap-2">
              <Coins className="w-4 h-4" /> I collected cash from customer ({formatPrice(r.order_total_usd, r.exchange_rate_ssp || exchangeRate, currency)})
            </button>
          ) : (
            <p className="text-sm text-yellow-900">Cash collected — please hand it to admin. They’ll mark it received in the system.</p>
          )}
        </div>
      )}

      {/* FAILED → RETURN step */}
      {r.delivery_status === "delivery_failed" && r.return_status === "pending_return" && (
        <div className="border-2 border-orange-300 bg-orange-50 rounded-xl p-4 space-y-2">
          <p className="text-sm font-semibold text-orange-900 flex items-center gap-2"><RotateCcw className="w-4 h-4" /> Return the item to the seller</p>
          <p className="text-xs text-orange-800">When you hand the item back, give the seller this OTP so they can confirm receipt:</p>
          <p className="text-3xl font-mono font-bold text-orange-700 tracking-widest text-center">{r.return_otp}</p>
          <button onClick={() => post("return-to-seller")} disabled={busy} className="w-full bg-orange-600 hover:bg-orange-700 text-white font-semibold py-2 rounded-full">I’m returning it now</button>
        </div>
      )}

      {r.return_status === "return_to_seller_pending" && (
        <div className="border-2 border-orange-300 bg-orange-50 rounded-xl p-4 space-y-2">
          <p className="text-sm font-semibold text-orange-900">Waiting for seller to confirm they received the returned item.</p>
          <p className="text-xs text-orange-800">Return OTP to give the seller:</p>
          <p className="text-3xl font-mono font-bold text-orange-700 tracking-widest text-center">{r.return_otp}</p>
        </div>
      )}

      {r.delivery_status === "returned_to_seller" && (
        <p className="text-sm text-center text-[var(--js-text-secondary)] py-4">Item returned. Closed.</p>
      )}
      {r.delivery_status === "delivered" && r.payment_status === "received_by_admin" && (
        <p className="text-sm text-center text-emerald-700 font-semibold py-4 flex items-center justify-center gap-2">
          <CheckCircle2 className="w-4 h-4" /> Delivered & cash settled. Great job!
        </p>
      )}
    </div>
  );
}

function DriverOfferActions({ row, reload }) {
  const [busy, setBusy] = useState(false);
  const base = row._kind === "rest" ? `/driver/restaurant-orders/${row.id}` : `/driver/splits/${row.id}`;

  const accept = async (e) => {
    e.stopPropagation();
    setBusy(true);
    try {
      await api.post(`${base}/accept-offer`);
      toast.success("Order accepted — head to the pickup location.");
      reload();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Could not accept");
    } finally {
      setBusy(false);
    }
  };

  const decline = async (e) => {
    e.stopPropagation();
    setBusy(true);
    try {
      await api.post(`${base}/decline-offer`);
      toast.success("Declined — order has been re-offered to another driver.");
      reload();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Could not decline");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-testid={`driver-offer-actions-${row.id.slice(0,8)}`}
      className="mt-3 pt-3 border-t border-[var(--js-border)] flex gap-2"
    >
      <button
        type="button"
        onClick={decline}
        disabled={busy}
        data-testid={`driver-decline-${row.id.slice(0,8)}`}
        className="flex-1 inline-flex items-center justify-center gap-1 bg-white hover:bg-red-50 disabled:opacity-50 border border-red-300 text-red-700 text-sm font-semibold py-2 rounded-full transition"
      >
        <XCircle className="w-4 h-4" /> Decline
      </button>
      <button
        type="button"
        onClick={accept}
        disabled={busy}
        data-testid={`driver-accept-${row.id.slice(0,8)}`}
        className="flex-1 inline-flex items-center justify-center gap-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-semibold py-2 rounded-full transition"
      >
        <CheckCircle2 className="w-4 h-4" /> Accept
      </button>
    </div>
  );
}
