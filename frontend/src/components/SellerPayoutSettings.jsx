import { useEffect, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { toast } from "sonner";
import { Banknote, Landmark, Loader2, Globe2 } from "lucide-react";

const FIELDS = [
  { key: "account_name", label: "Account holder name", required: true },
  { key: "bank_name", label: "Bank name", required: true },
  { key: "account_number", label: "Account number", required: true },
  { key: "swift_iban", label: "SWIFT / IBAN", intlRequired: true },
  { key: "bank_country", label: "Bank country" },
];

const MethodOption = ({ id, icon: Icon, title, sub, active, disabled, onClick }) => (
  <button
    type="button"
    disabled={disabled}
    onClick={onClick}
    data-testid={`payout-method-${id}`}
    className={`flex-1 text-left rounded-2xl border-2 p-4 transition-colors ${active ? "border-[#2D6A4F] bg-emerald-50 dark:bg-emerald-900/20" : "border-[var(--js-border)] bg-white dark:bg-[var(--js-card)]"} ${disabled ? "opacity-40 cursor-not-allowed" : "hover:border-[#2D6A4F]"}`}
  >
    <Icon className="w-5 h-5 text-[#2D6A4F] mb-2" />
    <p className="font-bold text-sm text-[var(--js-text)]">{title}</p>
    <p className="text-xs text-[var(--js-text-secondary)] mt-0.5">{sub}</p>
  </button>
);

export const SellerPayoutSettings = () => {
  const [data, setData] = useState(null);
  const [method, setMethod] = useState("cash");
  const [bank, setBank] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/seller/payout-settings").then((r) => {
      setData(r.data);
      setMethod(r.data.method);
      setBank(r.data.bank || {});
    }).catch(() => toast.error("Could not load payout settings"));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put("/seller/payout-settings", { method, ...bank });
      setData(r.data);
      toast.success("Payout method saved");
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (!data) return <p className="text-sm text-[var(--js-text-secondary)] py-10 text-center">Loading…</p>;
  const intl = data.is_international;

  return (
    <div className="max-w-2xl space-y-5" data-testid="payout-settings">
      {intl && (
        <div className="flex gap-3 rounded-2xl border border-blue-200 bg-blue-50 dark:bg-blue-900/20 p-4 text-sm text-blue-900 dark:text-blue-200" data-testid="payout-intl-note">
          <Globe2 className="w-5 h-5 flex-shrink-0" />
          <p>Your shop is outside South Sudan, so payouts are made by <strong>bank transfer</strong>. Earnings become available after the holding period following delivery, provided there is no open dispute.</p>
        </div>
      )}
      <div className="flex gap-3 flex-col sm:flex-row">
        <MethodOption id="cash" icon={Banknote} title="Cash" sub="Collect your payout in cash from JubaSquare (South Sudan only)" active={method === "cash"} disabled={intl} onClick={() => setMethod("cash")} />
        <MethodOption id="bank" icon={Landmark} title="Bank transfer" sub="Paid directly to your bank account" active={method === "bank"} onClick={() => setMethod("bank")} />
      </div>
      {method === "bank" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-2xl border border-[var(--js-border)] bg-white dark:bg-[var(--js-card)] p-5">
          {FIELDS.map((f) => (
            <label key={f.key} className="block">
              <span className="text-xs font-semibold text-[var(--js-text-secondary)]">
                {f.label}{(f.required || (f.intlRequired && intl)) && " *"}
              </span>
              <input
                value={bank[f.key] || ""}
                onChange={(e) => setBank({ ...bank, [f.key]: e.target.value })}
                data-testid={`payout-bank-${f.key}`}
                className="mt-1 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-[#2D6A4F]"
              />
            </label>
          ))}
        </div>
      )}
      <button
        onClick={save}
        disabled={saving}
        data-testid="payout-settings-save"
        className="inline-flex items-center gap-2 bg-[#2D6A4F] hover:bg-[#245A42] text-white text-sm font-semibold px-6 py-2.5 rounded-full disabled:opacity-60 transition-colors"
      >
        {saving && <Loader2 className="w-4 h-4 animate-spin" />} Save payout method
      </button>
    </div>
  );
};
