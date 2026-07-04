import { Package, ChefHat, Truck, CheckCircle2, XCircle, Clock } from "lucide-react";

/**
 * Compact horizontal status timeline for orders.
 *
 * Props:
 *  - kind: "marketplace" | "restaurant"
 *  - status: parent order status string
 *  - deliveryStatus: optional driver-side status (out_for_delivery, picked_up, delivered, …)
 *  - cancelled: boolean — overrides everything with a cancelled state
 */
export default function OrderStatusTimeline({ kind, status, deliveryStatus, preparationStatus, cancelled }) {
  // Build the 4 steps we want the customer to see.
  const steps =
    kind === "restaurant"
      ? [
          { key: "placed", label: "Order placed", icon: Package },
          { key: "preparing", label: "Preparing", icon: ChefHat },
          { key: "out_for_delivery", label: "Out for delivery", icon: Truck },
          { key: "delivered", label: "Delivered", icon: CheckCircle2 },
        ]
      : [
          { key: "placed", label: "Placed", icon: Package },
          { key: "preparing", label: "Seller preparing", icon: ChefHat },
          { key: "out_for_delivery", label: "Out for delivery", icon: Truck },
          { key: "delivered", label: "Delivered", icon: CheckCircle2 },
        ];

  // Determine which step we're currently on.
  let activeIndex = 0;
  if (cancelled) {
    activeIndex = -1;
  } else if (kind === "restaurant") {
    const s = (status || "").toLowerCase();
    const d = (deliveryStatus || "").toLowerCase();
    const p = (preparationStatus || "").toLowerCase();
    if (d === "delivered" || s === "completed") activeIndex = 3;
    else if (d === "out_for_delivery") activeIndex = 2;
    else if (s === "ready" || d === "picked_up" || p === "ready_for_pickup" || p === "handed_to_driver") activeIndex = 2;
    else if (s === "accepted" || s === "cooking" || p === "accepted" || p === "preparing") activeIndex = 1;
    else if (s === "pending") activeIndex = 0;
    else activeIndex = 0;
  } else {
    // marketplace parent status. Prefer split-level signals (delivery_status
    // + seller_preparation_status from the sub-order) because the parent
    // db.orders.status stays "Pending" for the whole lifetime — sellers
    // update the SPLIT, not the parent.
    const s = (status || "").toLowerCase();
    const d = (deliveryStatus || "").toLowerCase();
    const p = (preparationStatus || "").toLowerCase();
    if (s === "delivered" || d === "delivered") activeIndex = 3;
    else if (d === "out_for_delivery") activeIndex = 2;
    else if (p === "ready_for_pickup" || p === "handed_to_driver" || d === "picked_up") activeIndex = 2;
    else if (p === "accepted" || p === "preparing" || s === "in progress") activeIndex = 1;
    else activeIndex = 0;
  }

  if (cancelled) {
    return (
      <div
        data-testid="order-timeline-cancelled"
        className="flex items-center gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
      >
        <XCircle className="w-4 h-4" />
        <span className="font-semibold">Order cancelled</span>
      </div>
    );
  }

  return (
    <div
      data-testid="order-timeline"
      className="rounded-2xl border border-[#E2E2D9] bg-[#FAF7F2] dark:bg-[var(--js-subtle)] dark:border-[var(--js-border)] px-3 py-3"
    >
      <div className="flex items-start justify-between gap-1 sm:gap-2">
        {steps.map((step, i) => {
          const Icon = step.icon;
          const done = i < activeIndex;
          const active = i === activeIndex;
          const upcoming = i > activeIndex;
          const circleCls = done
            ? "bg-[#2D6A4F] text-white"
            : active
            ? "bg-[#C84B31] text-white ring-4 ring-[#C84B31]/20 animate-pulse"
            : "bg-white border border-[#E2E2D9] text-[#A3A39E]";
          const lineCls = i < activeIndex ? "bg-[#2D6A4F]" : "bg-[#E2E2D9]";
          return (
            <div key={step.key} className="flex-1 flex flex-col items-center min-w-0">
              <div className="flex items-center w-full">
                {i > 0 && <div className={`flex-1 h-[2px] ${lineCls}`} />}
                <div
                  data-testid={`timeline-step-${step.key}`}
                  data-active={active ? "true" : "false"}
                  className={`rounded-full w-8 h-8 flex items-center justify-center flex-shrink-0 ${circleCls}`}
                >
                  {done ? <CheckCircle2 className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                </div>
                {i < steps.length - 1 && <div className={`flex-1 h-[2px] ${i < activeIndex ? "bg-[#2D6A4F]" : "bg-[#E2E2D9]"}`} />}
              </div>
              <p
                className={`mt-1.5 text-[10px] sm:text-[11px] leading-tight text-center font-semibold ${
                  upcoming ? "text-[#A3A39E]" : "text-[#1A1A1A] dark:text-[var(--js-text)]"
                }`}
              >
                {step.label}
              </p>
              {active && (
                <span className="inline-flex items-center gap-1 mt-0.5 text-[9px] text-[#C84B31] font-bold uppercase tracking-wider">
                  <Clock className="w-2.5 h-2.5" /> Now
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
