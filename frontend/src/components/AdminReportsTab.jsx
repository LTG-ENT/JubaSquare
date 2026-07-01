import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Flag, CheckCircle2, XCircle, MessageSquare, Filter, RefreshCw } from "lucide-react";

const STATUS_TABS = [
  { id: "open", label: "Open" },
  { id: "reviewed", label: "Reviewed" },
  { id: "actioned", label: "Actioned" },
  { id: "dismissed", label: "Dismissed" },
  { id: "", label: "All" },
];

const STATUS_COLORS = {
  open: "bg-[#C84B31]/15 text-[#A83A23]",
  reviewed: "bg-[#E9C46A]/25 text-[#7A5C12]",
  actioned: "bg-[#2A9D8F]/15 text-[#1F7A6F]",
  dismissed: "bg-[var(--js-subtle)] text-[var(--js-text-secondary)]",
};

export default function AdminReportsTab() {
  const [filter, setFilter] = useState("open");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // {id, admin_notes}

  const load = async () => {
    setLoading(true);
    try {
      const q = filter ? `?status=${filter}` : "";
      const r = await api.get(`/admin/reports${q}`);
      setRows(r.data || []);
    } catch (e) {
      toast.error("Could not load reports");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const setStatus = async (id, status, admin_notes) => {
    try {
      await api.put(`/admin/reports/${id}`, { status, admin_notes });
      toast.success(`Marked as ${status}`);
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Update failed");
    }
  };

  return (
    <div className="space-y-4" data-testid="admin-reports-tab">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display font-bold text-xl text-[var(--js-text)] flex items-center gap-2">
            <Flag className="w-5 h-5 text-[#C84B31]" /> Reports
          </h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1">
            Community reports on shops, products, and reviews. Review, dismiss, or take action.
          </p>
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--js-text)] hover:bg-[var(--js-subtle)] px-3 py-1.5 rounded-full border border-[var(--js-border)]"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-2 flex-wrap">
        {STATUS_TABS.map((s) => (
          <button
            key={s.id || "all"}
            onClick={() => setFilter(s.id)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold ${filter === s.id ? "bg-[#0E1A2B] text-white" : "bg-[var(--js-subtle)] text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"}`}
            data-testid={`reports-filter-${s.id || "all"}`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-[var(--js-text-secondary)] italic">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-[var(--js-text-secondary)] italic py-8 text-center">No reports in this bucket.</p>
      ) : (
        <div className="space-y-3">
          {rows.map((r) => (
            <div key={r.id} className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[var(--js-border)] p-4 shadow-sm" data-testid={`report-row-${r.id}`}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${STATUS_COLORS[r.status] || STATUS_COLORS.open}`}>
                      {r.status}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">{r.target_type}</span>
                    <a
                      href={r.target_type === "shop" ? `/shop/${r.target_id}` : r.target_type === "product" ? `/product/${r.target_id}` : "#"}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-semibold text-[#C84B31] hover:underline truncate"
                    >
                      {r.target_snapshot?.name || r.target_id}
                    </a>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-[var(--js-text)]">{r.reason}</p>
                  {r.details && <p className="mt-1 text-xs text-[var(--js-text-secondary)]">{r.details}</p>}
                  <p className="mt-2 text-[10px] text-[var(--js-text-secondary)]">
                    Reported by <span className="font-semibold">{r.reporter_role || "user"}</span> · {new Date(r.created_at).toLocaleString()}
                  </p>
                  {r.admin_notes && (
                    <p className="mt-2 text-xs text-[var(--js-text)] bg-[var(--js-bg)] rounded-lg px-2 py-1">
                      <span className="font-bold">Admin note:</span> {r.admin_notes}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1 flex-wrap">
                  {r.status !== "reviewed" && (
                    <button onClick={() => setStatus(r.id, "reviewed", r.admin_notes || "")} className="inline-flex items-center gap-1 text-xs font-semibold text-[#7A5C12] bg-[#E9C46A]/20 hover:bg-[#E9C46A]/30 px-2 py-1 rounded-full">
                      <MessageSquare className="w-3 h-3" /> Reviewed
                    </button>
                  )}
                  {r.status !== "actioned" && (
                    <button onClick={() => setStatus(r.id, "actioned", r.admin_notes || "")} className="inline-flex items-center gap-1 text-xs font-semibold text-[#1F7A6F] bg-[#2A9D8F]/20 hover:bg-[#2A9D8F]/30 px-2 py-1 rounded-full">
                      <CheckCircle2 className="w-3 h-3" /> Actioned
                    </button>
                  )}
                  {r.status !== "dismissed" && (
                    <button onClick={() => setStatus(r.id, "dismissed", r.admin_notes || "")} className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--js-text-secondary)] bg-[var(--js-subtle)] hover:bg-[var(--js-border)] px-2 py-1 rounded-full">
                      <XCircle className="w-3 h-3" /> Dismiss
                    </button>
                  )}
                  <button onClick={() => setEditing({ id: r.id, admin_notes: r.admin_notes || "" })} className="text-xs text-[var(--js-text-secondary)] hover:text-[var(--js-text)] px-2 py-1">
                    Add note
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Notes modal */}
      {editing && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl w-full max-w-md p-5 shadow-2xl">
            <h3 className="font-display font-bold text-base text-[var(--js-text)] mb-3">Admin note</h3>
            <textarea
              value={editing.admin_notes}
              onChange={(e) => setEditing({ ...editing, admin_notes: e.target.value })}
              rows={4}
              maxLength={2000}
              className="w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-[var(--js-bg)] text-sm text-[var(--js-text)] resize-none"
              placeholder="Notes for other admins…"
            />
            <div className="flex justify-end gap-2 mt-3">
              <button onClick={() => setEditing(null)} className="px-4 py-1.5 rounded-full text-sm font-semibold text-[var(--js-text)] hover:bg-[var(--js-subtle)]">Cancel</button>
              <button
                onClick={async () => {
                  const row = rows.find((r) => r.id === editing.id);
                  await setStatus(editing.id, row?.status || "open", editing.admin_notes);
                }}
                className="bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-4 py-1.5 rounded-full"
              >
                Save note
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
