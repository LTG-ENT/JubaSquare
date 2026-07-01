import { useEffect, useState } from "react";
import { AlertTriangle, X, Loader2 } from "lucide-react";
import api from "@/lib/api";

/**
 * Confirmation modal for hard-deleting a user (single or bulk).
 * - Fetches a `/delete-preview` for each target user to show a breakdown
 *   of what cascades (shops, products, restaurants, menu_items, reviews,
 *   invoices, payouts, notifications, favorites, messages).
 * - Requires the admin to type `DELETE` to enable the confirm button.
 *
 * Props:
 *   users:  array of {id, name, email, role}
 *   open:   boolean
 *   onCancel: () => void
 *   onConfirm: () => Promise<void>   (parent triggers the actual API call)
 */
export default function DeleteUserConfirmModal({ users, open, onCancel, onConfirm }) {
  const [previews, setPreviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const REQUIRED = "DELETE";

  useEffect(() => {
    if (!open || !users?.length) return;
    setConfirmText("");
    setLoading(true);
    Promise.all(
      users.map((u) =>
        api.get(`/admin/users/${u.id}/delete-preview`).then((r) => r.data).catch(() => null)
      )
    ).then((results) => {
      setPreviews(results.filter(Boolean));
      setLoading(false);
    });
  }, [open, users]);

  if (!open) return null;

  // Aggregate totals across all users
  const totals = previews.reduce((acc, p) => {
    Object.entries(p.counts || {}).forEach(([k, v]) => {
      acc[k] = (acc[k] || 0) + v;
    });
    return acc;
  }, {});

  const rows = [
    { key: "shops",             label: "Shops" },
    { key: "products",          label: "Products" },
    { key: "restaurants",       label: "Restaurants" },
    { key: "menu_items",        label: "Menu items" },
    { key: "reviews_received",  label: "Reviews on their listings" },
    { key: "reviews_written",   label: "Reviews they wrote" },
    { key: "invoices",          label: "Invoices" },
    { key: "payouts",           label: "Payout records" },
    { key: "messages_sent",     label: "Messages sent" },
    { key: "favorites",         label: "Favorites" },
    { key: "notifications",     label: "Notifications" },
  ].filter((r) => (totals[r.key] ?? 0) > 0);

  const canConfirm = confirmText === REQUIRED && !submitting && !loading;

  const handleConfirm = async () => {
    if (!canConfirm) return;
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      data-testid="delete-user-confirm-overlay"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        data-testid="delete-user-confirm-modal"
        className="w-full max-w-lg bg-white rounded-3xl shadow-2xl overflow-hidden"
      >
        <div className="relative p-6 sm:p-7 bg-gradient-to-br from-[#FEEDEA] via-white to-[#FFE9E9]">
          <button
            onClick={onCancel}
            data-testid="delete-user-confirm-close"
            aria-label="Close"
            className="absolute top-3 right-3 w-9 h-9 rounded-full hover:bg-white/70 flex items-center justify-center text-[#5C5C5C]"
          >
            <X className="w-4 h-4" />
          </button>
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-2xl bg-[#C84B31] text-white flex items-center justify-center shrink-0">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] uppercase tracking-[0.2em] text-[#C84B31] font-bold">
                Permanent action
              </p>
              <h2 className="font-display font-bold text-xl sm:text-2xl text-[#1A1A1A] mt-1">
                {users.length === 1
                  ? `Delete ${users[0].name || users[0].email}?`
                  : `Delete ${users.length} users?`}
              </h2>
              <p className="text-sm text-[#5C5C5C] mt-1">
                This cannot be undone. Orders are kept for accounting, but everything else below is gone forever.
              </p>
            </div>
          </div>
        </div>

        <div className="p-6 sm:p-7">
          {loading ? (
            <div className="flex items-center gap-2 text-[#5C5C5C] text-sm">
              <Loader2 className="w-4 h-4 animate-spin" /> Checking what will be deleted…
            </div>
          ) : rows.length === 0 ? (
            <p className="text-sm text-[#5C5C5C]" data-testid="delete-preview-empty">
              This user has no attached data. Only their account record will be removed.
            </p>
          ) : (
            <div className="rounded-xl border border-[#E2E2D9] overflow-hidden" data-testid="delete-preview-table">
              {rows.map((r, i) => (
                <div
                  key={r.key}
                  className={`flex items-center justify-between px-4 py-2.5 text-sm ${
                    i % 2 === 0 ? "bg-[#FAFAF6]" : "bg-white"
                  }`}
                >
                  <span className="text-[#5C5C5C]">{r.label}</span>
                  <span
                    className="font-mono font-bold text-[#C84B31]"
                    data-testid={`delete-preview-count-${r.key}`}
                  >
                    {totals[r.key]}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="mt-5">
            <label className="text-[11px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold">
              Type <span className="font-mono text-[#C84B31]">{REQUIRED}</span> to confirm
            </label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              autoFocus
              disabled={submitting}
              data-testid="delete-user-confirm-input"
              className="mt-1.5 w-full border border-[#E2E2D9] rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#C84B31] focus:ring-1 focus:ring-[#C84B31]"
              placeholder={REQUIRED}
            />
          </div>
        </div>

        <div className="px-6 sm:px-7 pb-6 flex flex-col-reverse sm:flex-row items-center gap-2 sm:gap-3 sm:justify-end border-t border-[#F0F0E8] pt-4">
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            data-testid="delete-user-confirm-cancel"
            className="w-full sm:w-auto px-5 py-2.5 rounded-full text-sm font-semibold text-[#1A1A1A] hover:bg-[#F5F5EE] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!canConfirm}
            data-testid="delete-user-confirm-submit"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-5 py-2.5 rounded-full text-sm font-semibold bg-[#C84B31] hover:bg-[#A83A24] text-white disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
            {users.length === 1 ? "Delete user" : `Delete ${users.length} users`}
          </button>
        </div>
      </div>
    </div>
  );
}
