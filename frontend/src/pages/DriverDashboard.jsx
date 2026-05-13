import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatUSD, formatDetail } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import SignaturePad from "@/components/SignaturePad";
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
  const [data, setData] = useState({ splits: [], restaurant_orders: [] });
  const [filter, setFilter] = useState(""); // delivery_status filter
  const [open, setOpen] = useState(null); // { ...row, _kind }
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(`/driver/assignments${filter ? `?status=${filter}` : ""}`);
      setData(r.data || { splits: [], restaurant_orders: [] });
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to load assignments");
    } finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const all = [
    ...(data.splits || []).map((s) => ({ ...s, _kind: "split" })),
    ...(data.restaurant_orders || []).map((r) => ({ ...r, _kind: "rest" })),
  ];

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
        <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-1">Driver Dashboard</p>
        <h1 className="font-display font-bold text-3xl text-[var(--js-text)]">My deliveries</h1>
        <p className="text-sm text-[var(--js-text-secondary)]">Hi {user?.name?.split(" ")?.[0]} — here are the orders assigned to you.</p>

        <div className="mt-6 flex gap-2 flex-wrap items-center">
          <select value={filter} onChange={(e) => setFilter(e.target.value)} data-testid="driver-filter" className="px-3 py-2 border border-[var(--js-border)] rounded-lg text-sm">
            <option value="">All my deliveries</option>
            <option value="assigned">Assigned (new)</option>
            <option value="picked_up">Picked up</option>
            <option value="out_for_delivery">Out for delivery</option>
            <option value="delivered">Delivered</option>
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
            {all.map((r) => (
              <button
                key={r.id}
                onClick={() => setOpen(r)}
                data-testid={`driver-card-${r.id.slice(0,8)}`}
                className="text-left bg-white hover:shadow-md transition border border-[var(--js-border)] rounded-2xl p-4"
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
                <p className="text-xs text-[var(--js-text-secondary)] flex items-center gap-1"><Phone className="w-3 h-3" /> {r.customer_phone || "—"}</p>
                <p className="text-xs text-[var(--js-text-secondary)] flex items-center gap-1"><MapPin className="w-3 h-3" /> {r.customer_area} — {r.customer_address}</p>
                <div className="mt-3 flex items-center justify-between">
                  <span className="text-lg font-bold text-[var(--js-text)]">{formatUSD(r.order_total_usd)}</span>
                  <div className="flex gap-1">
                    <Pill value={r.payment_status} />
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}

function DeliveryDetail({ row, reload, setOpen }) {
  const [r, setR] = useState(row);
  const [otp, setOtp] = useState("");
  const [signature, setSignature] = useState("");
  const [receiver, setReceiver] = useState("");
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
    post("deliver", { otp: otp.trim(), signature_b64: signature, receiver_name: receiver.trim() }).then(() => {
      setOtp(""); setSignature(""); setReceiver("");
    });
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
        <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)] mb-2">Deliver to customer</p>
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
              <span className="font-medium">{formatUSD(it.line_total_usd || (it.price_usd * it.quantity))}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3 pt-3 border-t border-[var(--js-border)] flex justify-between font-bold">
          <span>Total to collect (COD)</span>
          <span className="text-xl">{formatUSD(r.order_total_usd)}</span>
        </div>
      </section>

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
              <Coins className="w-4 h-4" /> I collected cash from customer ({formatUSD(r.order_total_usd)})
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
