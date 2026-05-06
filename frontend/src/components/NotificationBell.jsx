import { useEffect, useRef, useState, useCallback } from "react";
import { Bell, Package, AlertTriangle, Receipt, X, Check } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { useNavigate } from "react-router-dom";

const ICONS = {
  order: Package,
  commission: Receipt,
  alert: AlertTriangle,
};

const TYPE_COLORS = {
  order: "bg-[#2A9D8F]/15 text-[#1F7A6F]",
  commission: "bg-[#E9C46A]/25 text-[#7A5C12]",
  alert: "bg-[#C84B31]/15 text-[#A83A23]",
};

function timeAgo(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function NotificationBell() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const wrapRef = useRef(null);

  const load = useCallback(async () => {
    if (!user) return;
    try {
      const { data } = await api.get("/notifications");
      setItems(data.items || []);
      setUnread(data.unread_count || 0);
    } catch (_) {
      /* silent */
    }
  }, [user]);

  useEffect(() => {
    if (!user) {
      setItems([]); setUnread(0); return;
    }
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [user, load]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const markRead = async (n) => {
    if (!n.is_read) {
      try {
        await api.put(`/notifications/${n.id}/read`);
      } catch (_) { /* silent */ }
    }
    // update local state
    setItems((prev) => prev.map((it) => (it.id === n.id ? { ...it, is_read: true } : it)));
    setUnread((c) => Math.max(0, c - (n.is_read ? 0 : 1)));

    // navigate based on type + role
    setOpen(false);
    if (n.type === "order") {
      if (user?.role === "customer") navigate("/orders");
      else navigate("/seller?tab=orders");
    } else if (n.type === "commission") {
      if (user?.role === "admin") navigate("/admin?tab=invoices");
      else navigate("/seller?tab=invoices");
    }
  };

  const markAll = async () => {
    try {
      await api.put("/notifications/read-all");
      setItems((prev) => prev.map((it) => ({ ...it, is_read: true })));
      setUnread(0);
    } catch (_) { /* silent */ }
  };

  if (!user) return null;

  return (
    <div className="relative" ref={wrapRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        data-testid="notification-bell"
        aria-label="Notifications"
        className="relative p-2.5 rounded-full hover:bg-white/10 transition"
      >
        <Bell className="w-5 h-5 text-white" />
        {unread > 0 && (
          <span
            data-testid="notification-unread-count"
            className="absolute -top-0.5 -right-0.5 bg-[#C84B31] text-white text-[10px] font-bold rounded-full min-w-[20px] h-5 px-1 flex items-center justify-center"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          data-testid="notification-dropdown"
          className="absolute right-0 mt-2 w-[360px] max-w-[92vw] bg-white border border-[#E2E2D9] rounded-2xl shadow-[0_18px_42px_rgba(0,0,0,0.18)] overflow-hidden z-50"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#E2E2D9] bg-[#F8F5F0]">
            <div>
              <p className="font-display font-semibold text-sm text-[#1A1A1A]">Notifications</p>
              <p className="text-[11px] text-[#5C5C5C]">{unread} unread</p>
            </div>
            <div className="flex items-center gap-1">
              {items.some((n) => !n.is_read) && (
                <button
                  onClick={markAll}
                  data-testid="notification-mark-all-read"
                  className="text-[11px] font-semibold text-[#C84B31] hover:underline px-2 py-1 inline-flex items-center gap-1"
                >
                  <Check className="w-3 h-3" /> Mark all read
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="p-1 rounded-full hover:bg-black/5"
              >
                <X className="w-4 h-4 text-[#5C5C5C]" />
              </button>
            </div>
          </div>

          <div className="max-h-[420px] overflow-y-auto">
            {items.length === 0 ? (
              <div className="py-12 text-center">
                <Bell className="w-8 h-8 text-[#A3A39E] mx-auto mb-2" />
                <p className="text-sm text-[#5C5C5C]">You're all caught up.</p>
              </div>
            ) : (
              items.map((n) => {
                const Icon = ICONS[n.type] || Bell;
                return (
                  <button
                    key={n.id}
                    onClick={() => markRead(n)}
                    data-testid={`notification-item-${n.id}`}
                    className={`w-full text-left flex items-start gap-3 px-4 py-3 border-b border-[#F0EDE5] last:border-b-0 transition ${
                      n.is_read ? "bg-white hover:bg-[#FAFAF7]" : "bg-[#FFF8EE] hover:bg-[#FFF1D7]"
                    }`}
                  >
                    <span className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center ${TYPE_COLORS[n.type] || TYPE_COLORS.alert}`}>
                      <Icon className="w-4 h-4" />
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm ${n.is_read ? "text-[#1A1A1A]" : "font-semibold text-[#1A1A1A]"}`}>
                        {n.message}
                      </p>
                      <p className="text-[11px] text-[#5C5C5C] mt-0.5">{timeAgo(n.created_at)}</p>
                    </div>
                    {!n.is_read && <span className="shrink-0 w-2 h-2 rounded-full bg-[#C84B31] mt-2" />}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
