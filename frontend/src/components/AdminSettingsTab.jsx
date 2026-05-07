import { useEffect, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { Percent, Save, RotateCcw, Info, Store, ArrowRight } from "lucide-react";
import { toast } from "sonner";

/**
 * AdminSettingsTab
 *
 * Central place for global platform settings. Right now the focus is the
 * commission rate (global default + list of shops that have a per-shop
 * override). More platform-level settings can be added to this tab later.
 */
export default function AdminSettingsTab({ onGoToShop }) {
  const [globalRate, setGlobalRate] = useState(0.10);
  const [rateDraft, setRateDraft] = useState("10"); // stored as percent string for the input
  const [shops, setShops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [s, sh] = await Promise.all([
        api.get("/admin/settings"),
        api.get("/shops?limit=200"),
      ]);
      const g = Number(s.data.commission_rate ?? 0.10);
      setGlobalRate(g);
      setRateDraft((g * 100).toFixed(1).replace(/\.0$/, ""));
      setShops(sh.data || []);
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const parsedDraftRate = (() => {
    const pct = parseFloat(rateDraft);
    if (Number.isNaN(pct)) return null;
    if (pct < 0 || pct > 100) return null;
    return Math.round(pct * 10) / 1000; // e.g. 10 → 0.10, 7.5 → 0.075
  })();

  const dirty = parsedDraftRate !== null && Math.abs(parsedDraftRate - globalRate) > 1e-6;

  const saveGlobalRate = async () => {
    if (parsedDraftRate === null) {
      toast.error("Enter a valid percentage between 0 and 100");
      return;
    }
    const confirmMsg = `Set the global commission rate to ${(parsedDraftRate * 100).toFixed(1)}%?\n\nThis will be applied to all shops that do NOT have their own custom rate. Pending/unpaid invoices will be regenerated with the new rate.`;
    if (!window.confirm(confirmMsg)) return;
    setSaving(true);
    try {
      await api.put("/admin/settings", { commission_rate: parsedDraftRate });
      toast.success(`Global commission rate set to ${(parsedDraftRate * 100).toFixed(1)}%`);
      // Regenerate invoices so shops without a custom rate pick up the new value
      try {
        await api.post("/admin/invoices/generate");
      } catch { /* non-critical */ }
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const resetShopCommission = async (shop) => {
    if (!window.confirm(`Remove the custom commission on ${shop.name}? It will fall back to the global rate (${(globalRate * 100).toFixed(1)}%).`)) return;
    try {
      await api.put(`/admin/shops/${shop.id}/commission`, { commission_rate: null });
      toast.success(`${shop.name} now uses the global rate`);
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed");
    }
  };

  if (loading) {
    return <p className="text-sm text-[var(--js-text-secondary)]">Loading settings…</p>;
  }

  const overrides = shops.filter((s) => s.commission_rate != null);
  const noOverrides = shops.filter((s) => s.commission_rate == null);

  return (
    <div className="space-y-6">
      {/* Global commission card */}
      <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 sm:p-6">
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-xl bg-[#C84B31]/10 text-[#C84B31] flex items-center justify-center flex-shrink-0">
            <Percent className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Platform</p>
            <h2 className="font-display font-bold text-lg text-[var(--js-text)] mt-0.5">Global commission rate</h2>
            <p className="text-xs text-[var(--js-text-secondary)] mt-1 leading-relaxed">
              This percentage is charged on every sale as JubaSquare's commission. It applies to <strong>every shop</strong> unless that shop has a custom rate set (see below).
            </p>

            <div className="mt-4 flex items-stretch gap-2 flex-wrap">
              <div className="relative">
                <input
                  type="number"
                  value={rateDraft}
                  onChange={(e) => setRateDraft(e.target.value)}
                  min="0"
                  max="100"
                  step="0.1"
                  data-testid="settings-global-rate-input"
                  className="w-40 bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl pl-3 pr-8 py-2.5 text-lg font-bold focus:outline-none focus:border-[#C84B31]"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)] font-bold">%</span>
              </div>
              <button
                type="button"
                onClick={saveGlobalRate}
                disabled={!dirty || saving}
                data-testid="settings-save-global-rate"
                className="inline-flex items-center gap-1.5 text-sm font-bold px-5 py-2.5 rounded-xl bg-[#C84B31] hover:bg-[#A83A23] text-white disabled:bg-[#A3A39E]"
              >
                <Save className="w-4 h-4" /> {saving ? "Saving…" : "Save rate"}
              </button>
              {dirty && (
                <button
                  type="button"
                  onClick={() => setRateDraft((globalRate * 100).toFixed(1).replace(/\.0$/, ""))}
                  data-testid="settings-reset-global-rate"
                  className="inline-flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-xl border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> Discard
                </button>
              )}
            </div>

            <div className="mt-3 text-xs text-[var(--js-text-secondary)]">
              <span className="font-semibold text-[var(--js-text)]">Currently saved:</span>{" "}
              <span data-testid="settings-global-rate-current" className="font-bold text-[#C84B31]">{(globalRate * 100).toFixed(1)}%</span>
              {parsedDraftRate === null && rateDraft !== "" && (
                <span className="ml-3 text-[#D90429] font-semibold">⚠ Must be between 0 and 100</span>
              )}
            </div>

            <div className="mt-4 flex gap-2 items-start p-3 bg-[#FFF7E0] border border-[#E9C46A]/40 rounded-xl text-xs text-[#7A5C12]">
              <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <strong>How commission is applied:</strong> when invoices are generated, each shop's effective rate is
                <code className="mx-1 px-1.5 py-0.5 bg-white rounded">shop.commission_rate ?? global_rate</code>.
                Changing the global rate triggers invoice regeneration so pending invoices pick up the new value.
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Per-shop overrides */}
      <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
          <div>
            <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Shop overrides</p>
            <h2 className="font-display font-bold text-lg text-[var(--js-text)] mt-0.5">Shops with a custom rate</h2>
            <p className="text-xs text-[var(--js-text-secondary)] mt-1">
              {overrides.length === 0
                ? `All ${shops.length} shop${shops.length === 1 ? "" : "s"} currently use the global rate.`
                : `${overrides.length} of ${shops.length} shops have a custom rate. The remaining ${noOverrides.length} use the global rate.`}
            </p>
          </div>
        </div>

        {overrides.length === 0 ? (
          <div className="p-6 bg-[var(--js-bg)] rounded-xl border border-[var(--js-border)] text-sm text-[var(--js-text-secondary)] text-center" data-testid="settings-no-overrides">
            No shop overrides yet. To set a custom rate for a shop, go to the <strong>Shops</strong> tab and open a shop.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="settings-overrides-table">
              <thead className="text-xs uppercase tracking-wider text-[var(--js-text-secondary)]">
                <tr>
                  <th className="text-left py-2 font-bold">Shop</th>
                  <th className="text-left py-2 font-bold">Custom rate</th>
                  <th className="text-left py-2 font-bold hidden sm:table-cell">Difference vs global</th>
                  <th className="text-right py-2 font-bold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {overrides.map((s) => {
                  const rate = Number(s.commission_rate);
                  const diff = rate - globalRate;
                  return (
                    <tr key={s.id} className="border-t border-[var(--js-border)]" data-testid={`settings-override-row-${s.id}`}>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <Store className="w-4 h-4 text-[var(--js-text-secondary)]" />
                          <span className="font-semibold text-[var(--js-text)]">{s.name}</span>
                        </div>
                      </td>
                      <td className="py-3">
                        <span className="font-bold text-[#C84B31]">{(rate * 100).toFixed(1)}%</span>
                      </td>
                      <td className="py-3 hidden sm:table-cell text-xs">
                        {diff === 0 ? (
                          <span className="text-[var(--js-text-secondary)]">= global</span>
                        ) : diff > 0 ? (
                          <span className="text-[#2D6A4F] font-semibold">+{(diff * 100).toFixed(1)}% higher</span>
                        ) : (
                          <span className="text-[#D90429] font-semibold">{(diff * 100).toFixed(1)}% lower</span>
                        )}
                      </td>
                      <td className="py-3 text-right">
                        <button
                          type="button"
                          onClick={() => resetShopCommission(s)}
                          data-testid={`settings-reset-shop-${s.id}`}
                          className="inline-flex items-center gap-1 text-[11px] font-bold px-3 py-1.5 rounded-full border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31] hover:text-[#C84B31]"
                        >
                          <RotateCcw className="w-3 h-3" /> Reset to global
                        </button>
                        {onGoToShop && (
                          <button
                            type="button"
                            onClick={() => onGoToShop(s.id)}
                            data-testid={`settings-edit-shop-${s.id}`}
                            className="ml-2 inline-flex items-center gap-1 text-[11px] font-bold px-3 py-1.5 rounded-full bg-[#1A1A1A] text-white hover:bg-[#C84B31]"
                          >
                            Edit <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-[11px] text-[var(--js-text-secondary)] mt-3">
          To set a custom rate on a shop, open its detail panel from the <strong>Shops</strong> tab.
        </p>
      </div>
    </div>
  );
}
