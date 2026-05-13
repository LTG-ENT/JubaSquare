import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { MessageCircle, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

/**
 * Trigger that opens the FloatingChat widget on a specific (order, seller) thread.
 * - If the order has exactly one seller, jumps straight into that thread.
 * - If multiple sellers, expands a small inline picker.
 */
export default function OrderChatButton({ orderId, className = "", label = "Chat about this order" }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(false);
  const [sellers, setSellers] = useState(null);

  const open = (sellerId) => {
    const params = new URLSearchParams(location.search);
    params.set("chat", `${orderId}:${sellerId}`);
    navigate({ pathname: location.pathname, search: `?${params.toString()}` });
    setSellers(null);
  };

  const onClick = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/orders/${orderId}/chat-sellers`);
      const list = Array.isArray(data) ? data : [];
      if (list.length === 0) {
        toast.error("No seller available to chat for this order");
        return;
      }
      if (list.length === 1) {
        open(list[0].seller_id);
      } else {
        setSellers(list);
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not open chat");
    } finally {
      setLoading(false);
    }
  };

  if (sellers) {
    return (
      <div className="relative inline-block" data-testid={`order-chat-sellers-${orderId}`}>
        <div className="absolute bottom-full right-0 mb-2 min-w-[200px] bg-white border border-[var(--js-border)] rounded-xl shadow-lg overflow-hidden z-30">
          <p className="px-3 py-2 text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)] border-b border-[var(--js-border)]">
            Chat with
          </p>
          {sellers.map((s) => (
            <button
              key={s.seller_id}
              type="button"
              onClick={() => open(s.seller_id)}
              data-testid={`chat-seller-pick-${s.seller_id}`}
              className="w-full text-left px-3 py-2 text-sm text-[var(--js-text)] hover:bg-[var(--js-subtle)] transition"
            >
              {s.name}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setSellers(null)}
          className={`inline-flex items-center gap-1.5 text-xs font-semibold text-[#C84B31] hover:text-white hover:bg-[#C84B31] border border-[#C84B31] px-3 py-1.5 rounded-full transition ${className}`}
        >
          <MessageCircle className="w-3.5 h-3.5" /> Pick a seller <ChevronDown className="w-3 h-3" />
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      data-testid={`order-chat-button-${orderId}`}
      className={`inline-flex items-center gap-1.5 text-xs font-semibold text-[#C84B31] hover:text-white hover:bg-[#C84B31] border border-[#C84B31] px-3 py-1.5 rounded-full transition disabled:opacity-60 ${className}`}
    >
      <MessageCircle className="w-3.5 h-3.5" /> {loading ? "Loading…" : label}
    </button>
  );
}
