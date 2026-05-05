import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api, { formatUSD } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Package, MapPin, Phone, Truck, CheckCircle2, Clock } from "lucide-react";

const STATUS_STYLES = {
  Pending: { bg: "bg-[#E9C46A]", text: "text-[#1A1A1A]", icon: Clock },
  "In Progress": { bg: "bg-[#2A9D8F]", text: "text-white", icon: Truck },
  Delivered: { bg: "bg-[#2D6A4F]", text: "text-white", icon: CheckCircle2 },
};

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [searchParams] = useSearchParams();
  const newId = searchParams.get("new");

  useEffect(() => {
    api.get("/orders/mine").then((r) => setOrders(r.data));
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">My orders</h1>
        <p className="text-sm text-[#5C5C5C] mt-1">{orders.length} order{orders.length !== 1 && "s"}</p>

        {orders.length === 0 ? (
          <div className="mt-12 text-center py-20 bg-white rounded-3xl border border-[#E2E2D9]" data-testid="empty-orders">
            <Package className="w-12 h-12 mx-auto text-[#A3A39E]" />
            <p className="font-display font-semibold text-xl text-[#1A1A1A] mt-4">No orders yet</p>
            <p className="text-sm text-[#5C5C5C] mt-1">When you place an order, it will appear here.</p>
          </div>
        ) : (
          <div className="mt-8 space-y-4">
            {orders.map((o) => {
              const s = STATUS_STYLES[o.status] || STATUS_STYLES.Pending;
              const Icon = s.icon;
              const isNew = o.id === newId;
              return (
                <div
                  key={o.id}
                  data-testid={`order-${o.id}`}
                  className={`bg-white border rounded-3xl p-5 sm:p-6 ${
                    isNew ? "border-[#C84B31] shadow-[0_8px_24px_rgba(200,75,49,0.15)]" : "border-[#E2E2D9]"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">{o.order_kind}</p>
                      <p className="font-display font-semibold text-lg text-[#1A1A1A]">Order #{o.id.slice(0, 8).toUpperCase()}</p>
                      <p className="text-xs text-[#5C5C5C] mt-0.5">{new Date(o.created_at).toLocaleString()}</p>
                    </div>
                    <span className={`inline-flex items-center gap-1.5 ${s.bg} ${s.text} font-bold text-xs px-3 py-1.5 rounded-full`} data-testid={`order-status-${o.id}`}>
                      <Icon className="w-3.5 h-3.5" /> {o.status}
                    </span>
                  </div>

                  <div className="space-y-2 mb-4">
                    {o.items.map((i, idx) => (
                      <div key={idx} className="flex items-center gap-3 text-sm">
                        <img src={i.image_url} alt={i.name} className="w-12 h-12 rounded-lg object-cover" />
                        <div className="flex-1 min-w-0 truncate">
                          <span className="font-semibold text-[#1A1A1A]">{i.name}</span>
                          <span className="text-[#5C5C5C]"> × {i.quantity}</span>
                        </div>
                        <span className="font-semibold text-[#1A1A1A] tabular-nums">{formatUSD(i.price_usd * i.quantity)}</span>
                      </div>
                    ))}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-[#E2E2D9]">
                    <div className="flex flex-wrap gap-3 text-xs text-[#5C5C5C]">
                      <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> {o.area}</span>
                      {o.phone && <span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" /> {o.phone}</span>}
                    </div>
                    <p className="font-display font-bold text-lg text-[#1A1A1A]">{formatUSD(o.subtotal_usd)}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
