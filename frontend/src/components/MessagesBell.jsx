import { useState, useEffect } from "react";
import { MessageCircle, X } from "lucide-react";
import api, { formatDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export default function MessagesBell() {
  const { user } = useAuth();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  // Only show for customers
  if (!user || user.role !== "customer") {
    return null;
  }

  const loadUnread = async () => {
    try {
      const { data } = await api.get("/messages/customer/unread-count");
      setUnread(data?.count || 0);
    } catch (e) {
      console.error("Failed to load unread messages count:", e);
    }
  };

  const loadMessages = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/messages/customer?limit=50");
      setMessages(data || []);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to load messages");
    } finally {
      setLoading(false);
    }
  };

  const markReplyRead = async (msgId) => {
    try {
      await api.put(`/messages/${msgId}/mark-reply-read`);
      setMessages((prev) =>
        prev.map((m) => (m.id === msgId ? { ...m, reply_read_by_customer: true } : m))
      );
      loadUnread();
    } catch (e) {
      toast.error("Failed to mark as read");
    }
  };

  useEffect(() => {
    loadUnread();
    const interval = setInterval(loadUnread, 15000); // Poll every 15 seconds
    return () => clearInterval(interval);
    // eslint-disable-next-line
  }, []);

  useEffect(() => {
    if (open) {
      loadMessages();
    }
    // eslint-disable-next-line
  }, [open]);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        data-testid="messages-bell-button"
        className="relative p-2.5 rounded-full hover:bg-white/10 transition"
        title="Messages"
      >
        <MessageCircle className="w-5 h-5 text-white" />
        {unread > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 bg-[#2D6A4F] text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center"
            data-testid="messages-unread-badge"
          >
            {unread}
          </span>
        )}
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />

          {/* Messages Panel */}
          <div className="fixed right-2 top-20 w-96 max-w-[calc(100vw-1rem)] max-h-[80vh] bg-white rounded-2xl shadow-2xl border border-[var(--js-border)] z-50 overflow-hidden flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-[var(--js-border)] bg-[var(--js-bg)]">
              <div className="flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-[#C84B31]" />
                <h3 className="font-display font-bold text-lg text-[var(--js-text)]">Messages</h3>
                {unread > 0 && (
                  <span className="bg-[#2D6A4F] text-white text-xs font-bold px-2 py-0.5 rounded-full">
                    {unread} new
                  </span>
                )}
              </div>
              <button
                onClick={() => setOpen(false)}
                className="p-1 hover:bg-white/50 rounded-full"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Messages List */}
            <div className="flex-1 overflow-y-auto p-3">
              {loading ? (
                <p className="text-sm text-[var(--js-text-secondary)] text-center py-8">
                  Loading...
                </p>
              ) : messages.length === 0 ? (
                <div className="text-center py-8">
                  <MessageCircle className="w-12 h-12 text-[var(--js-text-secondary)] mx-auto mb-3 opacity-30" />
                  <p className="text-sm text-[var(--js-text-secondary)]">No messages yet</p>
                  <p className="text-xs text-[var(--js-text-secondary)] mt-1">
                    Messages from shops will appear here
                  </p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {messages.map((msg) => {
                    const hasReply = msg.conversation_status === "replied" && msg.reply_body;
                    const replyUnread = hasReply && !msg.reply_read_by_customer;

                    return (
                      <li
                        key={msg.id}
                        className={`border rounded-xl p-3 ${
                          replyUnread
                            ? "border-[#2D6A4F] bg-[#E9F5E9]"
                            : "border-[var(--js-border)] bg-white"
                        }`}
                      >
                        {/* Shop Name */}
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-xs font-bold text-[var(--js-text)]">
                            {msg.shop_name}
                          </p>
                          {replyUnread && (
                            <span className="text-[10px] uppercase tracking-wider font-bold text-[#2D6A4F]">
                              ● NEW REPLY
                            </span>
                          )}
                        </div>

                        {/* Original Message */}
                        {msg.subject && (
                          <p className="text-xs font-semibold text-[var(--js-text)] mb-1">
                            {msg.subject}
                          </p>
                        )}
                        <p className="text-xs text-[var(--js-text-secondary)] mb-2 line-clamp-2">
                          You: {msg.body}
                        </p>
                        <p className="text-[10px] text-[var(--js-text-secondary)]">
                          {new Date(msg.created_at).toLocaleString()}
                        </p>

                        {/* Seller Reply */}
                        {hasReply && (
                          <div className="mt-2 pt-2 border-t border-[var(--js-border)]">
                            <p className="text-[10px] uppercase tracking-wider font-bold text-[#2D6A4F] mb-1">
                              Seller replied:
                            </p>
                            <p className="text-xs text-[var(--js-text)] whitespace-pre-wrap line-clamp-3">
                              {msg.reply_body}
                            </p>
                            <div className="mt-2 flex items-center justify-between">
                              <p className="text-[10px] text-[var(--js-text-secondary)]">
                                {new Date(msg.replied_at).toLocaleString()}
                              </p>
                              {replyUnread && (
                                <button
                                  onClick={() => markReplyRead(msg.id)}
                                  className="text-[10px] font-semibold text-[#2D6A4F] hover:underline"
                                >
                                  Mark as read
                                </button>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Status */}
                        {!hasReply && (
                          <p className="text-[10px] text-[var(--js-text-secondary)] mt-2">
                            Waiting for reply...
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Footer */}
            <div className="p-3 border-t border-[var(--js-border)] bg-[var(--js-bg)]">
              <p className="text-xs text-[var(--js-text-secondary)] text-center">
                Contact shops from their pages to send messages
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
