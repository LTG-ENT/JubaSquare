import { useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { X, Send, MessageCircle } from "lucide-react";
import { toast } from "sonner";

export default function ContactSellerModal({ shop, onClose }) {
  const { user } = useAuth();
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);

  const onSend = async (e) => {
    e.preventDefault();
    if (body.trim().length < 2) {
      toast.error("Please write a message");
      return;
    }
    setSending(true);
    try {
      await api.post(`/shops/${shop.id}/messages`, {
        subject: subject.trim(),
        body: body.trim(),
      });
      toast.success(`Message sent to ${shop.name}`);
      onClose();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to send");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-3xl w-full max-w-lg shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        data-testid="contact-seller-modal"
      >
        <div className="flex items-start justify-between p-5 border-b border-[var(--js-border)]">
          <div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-[#C84B31]/10 text-[#C84B31] flex items-center justify-center">
                <MessageCircle className="w-4 h-4" />
              </div>
              <h2 className="font-display font-bold text-lg text-[var(--js-text)]">Contact Seller</h2>
            </div>
            <p className="text-xs text-[var(--js-text-secondary)] mt-1">
              Send a message to <span className="font-semibold text-[var(--js-text)]">{shop.name}</span>. The shop owner will see it in their dashboard.
            </p>
          </div>
          <button onClick={onClose} aria-label="Close" className="p-1.5 hover:bg-[var(--js-subtle)] rounded-full">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={onSend} className="p-5 space-y-3">
          {user && (
            <div className="text-[11px] text-[var(--js-text-secondary)] bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl p-2.5">
              Sending as <strong className="text-[var(--js-text)]">{user.name}</strong> · {user.email}
            </div>
          )}
          <div>
            <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Subject (optional)</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              maxLength={120}
              placeholder="e.g. Question about a product"
              data-testid="contact-subject"
              className="mt-1 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
            />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Message <span className="text-[#D90429]">*</span></label>
            <textarea
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              maxLength={2000}
              placeholder="Write your message here…"
              data-testid="contact-body"
              className="mt-1 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
            />
            <p className="text-[10px] text-[var(--js-text-secondary)] mt-1 text-right">{body.length}/2000</p>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="text-xs font-bold px-4 py-2 rounded-full border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={sending || body.trim().length < 2}
              data-testid="contact-send-btn"
              className="inline-flex items-center gap-1.5 text-sm font-bold px-5 py-2 rounded-full bg-[#C84B31] hover:bg-[#A83A23] text-white disabled:bg-[#A3A39E]"
            >
              <Send className="w-4 h-4" /> {sending ? "Sending…" : "Send message"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
