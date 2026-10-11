import { formatPrice } from "@/lib/api";

const ROWS = [
  { key: "total_sales", label: "Total sales (delivered)" },
  { key: "commission", label: "JubaSquare commission", neg: true },
  { key: "refunds", label: "Refunds / returns", neg: true },
  { key: "fees", label: "Transfer fees", neg: true },
];
const BALANCES = [
  { key: "on_hold", label: "On hold", tone: "text-blue-700" },
  { key: "available", label: "Available", tone: "text-emerald-700" },
  { key: "pending", label: "Payout in progress", tone: "text-amber-700" },
  { key: "paid", label: "Paid out", tone: "text-[var(--js-text)]" },
];

export const SellerBalanceBreakdown = ({ wallet, rate, currency }) => {
  const b = wallet?.balance;
  if (!b) return null;
  const fmt = (v) => formatPrice(v || 0, rate, currency);
  return (
    <div className="mt-6 rounded-2xl border border-[var(--js-border)] bg-white dark:bg-[var(--js-card)] p-5" data-testid="wallet-balance-breakdown">
      <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)] mb-3">Balance breakdown</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-2 text-sm">
          {ROWS.map((r) => (
            <div key={r.key} className="flex justify-between" data-testid={`balance-${r.key}`}>
              <span className="text-[var(--js-text-secondary)]">{r.label}</span>
              <span className={`font-semibold tabular-nums ${r.neg ? "text-red-700" : "text-[var(--js-text)]"}`}>{r.neg && b[r.key] > 0 ? "− " : ""}{fmt(b[r.key])}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3">
          {BALANCES.map((r) => (
            <div key={r.key} className="rounded-xl bg-[var(--js-bg)] p-3" data-testid={`balance-${r.key}`}>
              <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">{r.label}</p>
              <p className={`text-lg font-bold tabular-nums ${r.tone}`}>{fmt(b[r.key])}</p>
            </div>
          ))}
        </div>
      </div>
      {wallet.is_international && b.on_hold > 0 && (
        <p className="text-xs text-[var(--js-text-secondary)] mt-3" data-testid="balance-hold-note">
          International earnings are held {wallet.hold_days} days after delivery.
          {wallet.next_hold_release && <> Next release: <strong>{wallet.next_hold_release.slice(0, 10)}</strong>.</>}
        </p>
      )}
    </div>
  );
};
