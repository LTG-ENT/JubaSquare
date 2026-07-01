import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Flag, X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";

const REASONS = [
  "Fake or counterfeit products",
  "Fraud / scam",
  "Prohibited items",
  "Offensive content",
  "Misleading information",
  "Spam",
  "Other",
];

/**
 * Small "Report" button that opens a modal. Files a report against a shop / product / review.
 * Requires authentication — redirects to /login if not signed in.
 *
 * Props:
 *   targetType: "shop" | "product" | "review"
 *   targetId:   string
 *   label?:     optional custom label (defaults to "Report")
 *   compact?:   render a small icon-only button
 */
export default function ReportButton({ targetType, targetId, label = "Report", compact = false }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState(REASONS[0]);
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);

  const onOpen = () => {
    if (!user) {
      toast.error("Please log in to report");
      navigate("/login");
      return;
    }
    setOpen(true);
  };

  const submit = async () => {
    setBusy(true);
    try {
      await api.post("/reports", { target_type: targetType, target_id: targetId, reason, details });
      toast.success("Report submitted. Our team will review it.");
      setOpen(false);
      setDetails("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not submit report");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        onClick={onOpen}
        className={compact
          ? "p-1.5 rounded-full text-[var(--js-text-secondary)] hover:text-[#C84B31] hover:bg-[#C84B31]/10"
          : "inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--js-text-secondary)] hover:text-[#C84B31] px-2 py-1 rounded-full"}
        title={label}
        data-testid={`report-${targetType}-btn`}
      >
        <Flag className={compact ? "w-3.5 h-3.5" : "w-3.5 h-3.5"} />
        {!compact && <span>{label}</span>}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" data-testid="report-modal">
          <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between p-4 border-b border-[var(--js-border)]">
              <h3 className="font-display font-bold text-base text-[var(--js-text)] flex items-center gap-2">
                <Flag className="w-4 h-4 text-[#C84B31]" /> Report this {targetType}
              </h3>
              <button onClick={() => setOpen(false)} className="p-1 rounded-full hover:bg-[var(--js-subtle)]">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="text-[10px] uppercase tracking-wide font-bold text-[var(--js-text-secondary)]">Reason</label>
                <select
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-bg)] text-[var(--js-text)] text-sm"
                  data-testid="report-reason-select"
                >
                  {REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wide font-bold text-[var(--js-text-secondary)]">Details (optional)</label>
                <textarea
                  value={details}
                  onChange={(e) => setDetails(e.target.value)}
                  rows={3}
                  maxLength={2000}
                  placeholder="Tell us more so we can act quickly."
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-bg)] text-[var(--js-text)] text-sm resize-none"
                  data-testid="report-details-input"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 p-3 border-t border-[var(--js-border)]">
              <button onClick={() => setOpen(false)} className="px-4 py-1.5 rounded-full text-sm font-semibold text-[var(--js-text)] hover:bg-[var(--js-subtle)]">
                Cancel
              </button>
              <button
                onClick={submit}
                disabled={busy}
                className="inline-flex items-center gap-1.5 bg-[#C84B31] hover:bg-[#A83A23] disabled:opacity-50 text-white text-sm font-semibold px-4 py-1.5 rounded-full"
                data-testid="report-submit-btn"
              >
                <Flag className="w-3.5 h-3.5" /> {busy ? "Submitting…" : "Submit"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
