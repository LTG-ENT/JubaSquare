import { useEffect, useMemo, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { toast } from "sonner";
import { Receipt, RefreshCw, CheckCircle2, Loader2, Search as SearchIcon } from "lucide-react";

const STATUS_TABS = [
  { id: "Unpaid", label: "Unpaid" },
  { id: "Paid", label: "Paid" },
  { id: "Overdue", label: "Overdue" },
  { id: "all", label: "All" },
];

function money(n) {
  return `$${(Number(n) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function ConfirmPaymentModal({ invoice, kind, onClose, onConfirmed }) {
  const [reference, setReference] = useState("");
  const [method, setMethod] = useState("cash");
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setSaving(true);
    try {
      const base = kind === "restaurant" ? "/admin/restaurant-invoices" : "/admin/invoices";
      await api.put(`${base}/${invoice.id}/status`, {
        status: "Paid",
        payment_reference: reference.trim(),
        payment_method: method,
      });
      toast.success("Commission payment confirmed");
      onConfirmed();
      onClose();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to confirm payment");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()} data-testid="confirm-payment-modal">
        <h3 className="font-display font-bold text-lg text-[var(--js-text)]">Confirm commission payment</h3>
        <p className="text-sm text-[var(--js-text-secondary)] mt-1">
          {invoice.shop_name || invoice.restaurant_name} · {invoice.week_label} · commission <b>{money(invoice.commission ?? invoice.amount_owed)}</b>
        </p>
        <label className="block text-xs font-semibold text-[var(--js-text-secondary)] mt-4 mb-1">Payment method</label>
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          data-testid="confirm-payment-method"
          className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl text-sm focus:outline-none focus:border-[#2D6A4F]"
        >
          <option value="cash">Cash</option>
          <option value="bank">Bank transfer</option>
          <option value="mobile_money">Mobile money</option>
          <option value="other">Other</option>
        </select>
        <label className="block text-xs font-semibold text-[var(--js-text-secondary)] mt-3 mb-1">Payment reference (optional)</label>
        <input
          type="text"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          placeholder="e.g. receipt no, txn id"
          data-testid="confirm-payment-reference"
          className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl text-sm focus:outline-none focus:border-[#2D6A4F]"
        />
        <div className="flex gap-2 mt-5">
          <button
            onClick={submit}
            disabled={saving}
            data-testid="confirm-payment-submit"
            className="flex-1 inline-flex items-center justify-center gap-2 bg-[#2D6A4F] hover:bg-[#245a41] text-white text-sm font-bold py-2.5 rounded-xl disabled:bg-[#A3A39E]"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />} Confirm paid
          </button>
          <button onClick={onClose} className="px-4 py-2.5 rounded-xl border border-[var(--js-border)] text-sm font-semibold">Cancel</button>
        </div>
      </div>
    </div>
  );
}

export default function AdminInvoicesTab() {
  const [statusTab, setStatusTab] = useState("Unpaid");
  const [marketplace, setMarketplace] = useState([]);
  const [restaurant, setRestaurant] = useState([]);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [search, setSearch] = useState("");
  const [confirmTarget, setConfirmTarget] = useState(null); // {invoice, kind}

  const load = async () => {
    setLoading(true);
    try {
      const [m, r] = await Promise.all([
        api.get("/admin/invoices"),
        api.get("/admin/restaurant-invoices"),
      ]);
      setMarketplace((m.data || []).map((x) => ({ ...x, _kind: "shop" })));
      setRestaurant((r.data || []).map((x) => ({ ...x, _kind: "restaurant" })));
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to load invoices");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const regenerate = async () => {
    setRegenerating(true);
    try {
      await Promise.all([
        api.post("/admin/invoices/generate"),
        api.post("/admin/restaurant-invoices/generate"),
      ]);
      toast.success("Invoices regenerated from delivered sales");
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to regenerate");
    } finally {
      setRegenerating(false);
    }
  };

  const rows = useMemo(() => {
    let all = [...marketplace, ...restaurant];
    if (statusTab !== "all") all = all.filter((i) => (i.status || "Unpaid") === statusTab);
    if (search.trim()) {
      const q = search.toLowerCase();
      all = all.filter((i) => (i.shop_name || i.restaurant_name || "").toLowerCase().includes(q));
    }
    return all.sort((a, b) => (b.week_start || "").localeCompare(a.week_start || ""));
  }, [marketplace, restaurant, statusTab, search]);

  const totals = useMemo(() => {
    const all = [...marketplace, ...restaurant];
    const unpaid = all.filter((i) => (i.status || "Unpaid") !== "Paid");
    return {
      owed: unpaid.reduce((s, i) => s + (Number(i.commission ?? i.amount_owed) || 0), 0),
      count: unpaid.length,
      sales: all.reduce((s, i) => s + (Number(i.total_sales) || 0), 0),
    };
  }, [marketplace, restaurant]);

  return (
    <div data-testid="admin-invoices-tab">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-5">
        <div>
          <h2 className="font-display font-bold text-2xl text-[var(--js-text)] flex items-center gap-2">
            <Receipt className="w-6 h-6" /> Commission Invoices
          </h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1 max-w-2xl">
            Commission JubaSquare is owed on <b>delivered</b> sales. When a seller collects the cash and pays you their commission, confirm it here — the payment reference &amp; date are recorded for your records.
          </p>
        </div>
        <button
          onClick={regenerate}
          disabled={regenerating}
          data-testid="regenerate-invoices-btn"
          className="inline-flex items-center gap-2 bg-[#1A1A1A] hover:bg-[#C84B31] text-white text-sm font-semibold px-4 py-2.5 rounded-xl disabled:opacity-60"
        >
          {regenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Regenerate
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-white border border-[var(--js-border)] rounded-2xl p-4">
          <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Outstanding commission</p>
          <p className="font-display font-bold text-2xl text-[#D90429] mt-1" data-testid="invoices-owed-total">{money(totals.owed)}</p>
        </div>
        <div className="bg-white border border-[var(--js-border)] rounded-2xl p-4">
          <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Unpaid invoices</p>
          <p className="font-display font-bold text-2xl text-[var(--js-text)] mt-1">{totals.count}</p>
        </div>
        <div className="bg-white border border-[var(--js-border)] rounded-2xl p-4">
          <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Delivered sales (total)</p>
          <p className="font-display font-bold text-2xl text-[#2D6A4F] mt-1">{money(totals.sales)}</p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="relative flex-1">
          <SearchIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)]" />
          <input
            type="text"
            placeholder="Search by shop / restaurant name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 border border-[var(--js-border)] rounded-xl text-sm focus:outline-none focus:border-[#C84B31]"
          />
        </div>
        <div className="inline-flex bg-white border border-[var(--js-border)] rounded-xl p-1">
          {STATUS_TABS.map((s) => (
            <button
              key={s.id}
              onClick={() => setStatusTab(s.id)}
              data-testid={`invoices-status-${s.id}`}
              className={`px-3 py-2 text-xs font-semibold rounded-lg transition ${statusTab === s.id ? "bg-[#C84B31] text-white" : "text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"}`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-[var(--js-text-secondary)]"><Loader2 className="w-6 h-6 animate-spin" /></div>
        ) : rows.length === 0 ? (
          <div className="text-center py-16 text-[var(--js-text-secondary)]" data-testid="invoices-empty">No invoices in this view.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--js-bg)] text-[var(--js-text-secondary)] text-xs uppercase tracking-wider">
                <tr>
                  <th className="text-left p-4">Seller / Shop</th>
                  <th className="text-left p-4 hidden md:table-cell">Period</th>
                  <th className="text-right p-4">Sales</th>
                  <th className="text-right p-4">Commission</th>
                  <th className="text-left p-4">Status</th>
                  <th className="text-right p-4">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--js-border)]">
                {rows.map((i) => (
                  <tr key={`${i._kind}-${i.id}`} data-testid={`invoice-row-${i.id}`}>
                    <td className="p-4">
                      <div className="font-semibold text-[var(--js-text)]">{i.shop_name || i.restaurant_name || "—"}</div>
                      <div className="text-[11px] text-[var(--js-text-secondary)]">
                        {i._kind === "restaurant" ? "Restaurant" : "Shop"} · {i.order_count || 0} order(s)
                        {i.payment_reference ? ` · ref ${i.payment_reference}` : ""}
                      </div>
                    </td>
                    <td className="p-4 hidden md:table-cell text-[var(--js-text-secondary)]">{i.week_label || "—"}</td>
                    <td className="p-4 text-right">{money(i.total_sales)}</td>
                    <td className="p-4 text-right font-bold">{money(i.commission ?? i.amount_owed)}</td>
                    <td className="p-4">
                      <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                        i.status === "Paid" ? "bg-[#2D6A4F]/10 text-[#2D6A4F]"
                        : i.status === "Overdue" ? "bg-[#D90429]/10 text-[#D90429]"
                        : "bg-[#E9C46A]/30 text-[#7A5C12]"}`}>
                        {i.status || "Unpaid"}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      {i.status === "Paid" ? (
                        <span className="text-xs text-[var(--js-text-secondary)]">
                          {i.paid_at ? new Date(i.paid_at).toLocaleDateString() : "Paid"}
                        </span>
                      ) : (
                        <button
                          onClick={() => setConfirmTarget({ invoice: i, kind: i._kind })}
                          data-testid={`confirm-payment-${i.id}`}
                          className="inline-flex items-center gap-1.5 bg-[#2D6A4F] hover:bg-[#245a41] text-white text-xs font-bold px-3 py-2 rounded-lg"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" /> Confirm payment
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {confirmTarget && (
        <ConfirmPaymentModal
          invoice={confirmTarget.invoice}
          kind={confirmTarget.kind}
          onClose={() => setConfirmTarget(null)}
          onConfirmed={load}
        />
      )}
    </div>
  );
}
