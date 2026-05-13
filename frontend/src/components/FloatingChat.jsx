import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { MessageCircle, X, Send, ChevronLeft } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const POLL_OPEN_MS = 12_000;
const POLL_CLOSED_MS = 30_000;

function formatTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export default function FloatingChat() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [threads, setThreads] = useState([]);
  const [active, setActive] = useState(null); // {order_id, seller_id, counterparty_name, order_short_id}
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const bodyRef = useRef(null);

  // Open a specific thread when URL has ?chat=<orderId>:<sellerId>
  useEffect(() => {
    if (!user) return;
    const params = new URLSearchParams(location.search);
    const tag = params.get("chat");
    if (!tag) return;
    const [orderId, sellerId] = tag.split(":");
    if (!orderId || !sellerId) return;
    openThread({ order_id: orderId, seller_id: sellerId, counterparty_name: "", order_short_id: orderId.slice(0, 8) });
    // Strip the query param so it doesn't reopen on re-render
    params.delete("chat");
    navigate({ pathname: location.pathname, search: params.toString() ? `?${params.toString()}` : "" }, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search, user]);

  // Poll unread count
  useEffect(() => {
    if (!user) return;
    let timer;
    const tick = async () => {
      try {
        const r = await api.get("/chats/unread-count");
        setUnread(r.data?.count || 0);
      } catch {}
      timer = setTimeout(tick, open ? POLL_OPEN_MS : POLL_CLOSED_MS);
    };
    tick();
    return () => clearTimeout(timer);
  }, [user, open]);

  // Load threads when widget opens (and refresh on poll while open)
  useEffect(() => {
    if (!user || !open || active) return;
    let timer;
    const tick = async () => {
      try {
        const r = await api.get("/chats");
        setThreads(r.data || []);
      } catch {}
      timer = setTimeout(tick, POLL_OPEN_MS);
    };
    tick();
    return () => clearTimeout(timer);
  }, [user, open, active]);

  // Poll messages while a thread is open
  useEffect(() => {
    if (!user || !active) return;
    let timer;
    const tick = async () => {
      try {
        const r = await api.get(`/orders/${active.order_id}/chat`, { params: { seller_id: active.seller_id } });
        setMessages(r.data || []);
      } catch {}
      timer = setTimeout(tick, POLL_OPEN_MS);
    };
    tick();
    return () => clearTimeout(timer);
  }, [user, active]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [messages]);

  const openThread = async (t) => {
    setActive(t);
    setOpen(true);
    setMessages([]);
    setDraft("");
  };

  const send = async (e) => {
    e?.preventDefault?.();
    if (!active || !draft.trim() || sending) return;
    setSending(true);
    try {
      await api.post(`/orders/${active.order_id}/chat`, {
        seller_id: active.seller_id,
        body: draft.trim(),
      });
      setDraft("");
      const r = await api.get(`/orders/${active.order_id}/chat`, { params: { seller_id: active.seller_id } });
      setMessages(r.data || []);
    } catch (err) {
      // surface error inline as a system bubble
      setMessages((prev) => [...prev, { id: `err-${Date.now()}`, body: err?.response?.data?.detail || "Failed to send", sender_role: "system", created_at: new Date().toISOString() }]);
    } finally {
      setSending(false);
    }
  };

  if (!user) return null;

  // Closed state — small FAB above the dark-mode toggle
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="chat-fab"
        aria-label="Open messages"
        className="fixed bottom-24 right-6 z-[60] w-12 h-12 rounded-full flex items-center justify-center bg-[#C84B31] text-white shadow-[0_8px_24px_rgba(0,0,0,0.25)] hover:scale-105 active:scale-95 transition"
      >
        <MessageCircle className="w-5 h-5" />
        {unread > 0 && (
          <span
            data-testid="chat-fab-badge"
            className="absolute -top-1 -right-1 min-w-[20px] h-5 px-1 rounded-full bg-[#1A1A1A] text-white text-[10px] font-bold flex items-center justify-center border-2 border-white"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
    );
  }

  // Open state — panel
  return (
    <div
      data-testid="chat-panel"
      className="fixed bottom-24 right-6 z-[60] w-[min(380px,calc(100vw-2rem))] h-[min(560px,calc(100vh-8rem))] bg-[var(--js-paper)] border border-[var(--js-border)] rounded-3xl shadow-[0_24px_48px_rgba(0,0,0,0.25)] flex flex-col overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--js-border)] bg-[var(--js-subtle)]">
        {active ? (
          <button
            type="button"
            onClick={() => { setActive(null); setMessages([]); }}
            data-testid="chat-back-button"
            className="p-1 rounded-full hover:bg-white/40"
            aria-label="Back to conversations"
          >
            <ChevronLeft className="w-4 h-4 text-[var(--js-text)]" />
          </button>
        ) : (
          <MessageCircle className="w-4 h-4 text-[var(--js-text)]" />
        )}
        <div className="flex-1 min-w-0">
          <p className="font-display font-bold text-sm text-[var(--js-text)] truncate">
            {active ? (active.counterparty_name || "Conversation") : "Messages"}
          </p>
          {active && (
            <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)] truncate">
              Order #{active.order_short_id}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          data-testid="chat-close-button"
          className="p-1 rounded-full hover:bg-white/40"
          aria-label="Close messages"
        >
          <X className="w-4 h-4 text-[var(--js-text)]" />
        </button>
      </div>

      {/* Body */}
      {!active ? (
        <div ref={bodyRef} className="flex-1 overflow-y-auto">
          {threads.length === 0 ? (
            <div className="p-6 text-center text-sm text-[var(--js-text-secondary)]">
              <MessageCircle className="w-8 h-8 mx-auto mb-3 opacity-40" />
              <p className="font-semibold text-[var(--js-text)] mb-1">No conversations yet</p>
              <p className="text-xs">
                Open one of your orders and tap <strong>Chat about this order</strong> to start.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-[var(--js-border)]">
              {threads.map((t) => (
                <li key={`${t.order_id}:${t.seller_id}`}>
                  <button
                    type="button"
                    onClick={() => openThread(t)}
                    data-testid={`chat-thread-${t.order_id}`}
                    className="w-full text-left px-4 py-3 hover:bg-[var(--js-subtle)] transition flex items-start gap-3"
                  >
                    <div className="w-9 h-9 rounded-full bg-[#C84B31]/15 text-[#C84B31] flex items-center justify-center flex-shrink-0 font-bold text-sm">
                      {(t.counterparty_name || "?").charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-semibold text-sm text-[var(--js-text)] truncate">
                          {t.counterparty_name || "Conversation"}
                        </p>
                        {t.unread > 0 && (
                          <span className="bg-[#C84B31] text-white text-[10px] font-bold rounded-full px-2 py-0.5">
                            {t.unread}
                          </span>
                        )}
                      </div>
                      <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">
                        Order #{t.order_short_id}
                      </p>
                      <p className="text-xs text-[var(--js-text-secondary)] truncate mt-0.5">
                        {t.last_role === "seller" ? "" : "You: "}{t.last_message}
                      </p>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <>
          <div ref={bodyRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-2 bg-[var(--js-bg)]">
            {messages.length === 0 ? (
              <p className="text-center text-xs text-[var(--js-text-secondary)] pt-6">
                Say hi 👋 — this conversation is private between you and the {user.role === "seller" ? "customer" : "seller"}.
              </p>
            ) : (
              messages.map((m) => {
                const mine = m.sender_id === user.id;
                const isSystem = m.sender_role === "system";
                return (
                  <div
                    key={m.id}
                    data-testid={`chat-message-${m.id}`}
                    className={`flex ${isSystem ? "justify-center" : mine ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                        isSystem
                          ? "bg-[#D90429]/10 text-[#D90429] text-xs"
                          : mine
                          ? "bg-[#C84B31] text-white rounded-br-sm"
                          : "bg-[var(--js-paper)] border border-[var(--js-border)] text-[var(--js-text)] rounded-bl-sm"
                      }`}
                    >
                      <p className="whitespace-pre-wrap break-words">{m.body}</p>
                      {!isSystem && (
                        <p className={`text-[10px] mt-1 ${mine ? "text-white/70" : "text-[var(--js-text-secondary)]"}`}>
                          {formatTime(m.created_at)}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
          <form onSubmit={send} className="flex items-center gap-2 px-3 py-3 border-t border-[var(--js-border)] bg-[var(--js-paper)]">
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type a message…"
              maxLength={2000}
              data-testid="chat-input"
              className="flex-1 bg-[var(--js-subtle)] border border-[var(--js-border)] rounded-full px-4 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
            />
            <button
              type="submit"
              disabled={!draft.trim() || sending}
              data-testid="chat-send-button"
              className="w-10 h-10 rounded-full bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] text-white flex items-center justify-center transition"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </>
      )}
    </div>
  );
}
