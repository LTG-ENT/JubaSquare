import { useEffect, useState } from "react";
import api from "@/lib/api";
import { TrendingUp, ShoppingBag, Package, AlertTriangle, DollarSign } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart } from "recharts";

function fmtUSD(v) {
  const n = Number(v || 0);
  return "$" + n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function StatCard({ icon: Icon, label, value, sub, accent = "#C84B31" }) {
  return (
    <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[var(--js-border)] p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-[var(--js-text-secondary)]">{label}</p>
          <p className="mt-1 font-display font-bold text-2xl text-[var(--js-text)]">{value}</p>
          {sub && <p className="mt-1 text-xs text-[var(--js-text-secondary)]">{sub}</p>}
        </div>
        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${accent}22`, color: accent }}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

export default function SellerAnalyticsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState(30); // 7 or 30

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.get("/seller/analytics")
      .then((r) => { if (alive) setData(r.data); })
      .catch(() => {/* silent */})
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  if (loading) return <div className="p-6 text-[var(--js-text-secondary)]">Loading analytics…</div>;
  if (!data) return <div className="p-6 text-[var(--js-text-secondary)]">Could not load analytics.</div>;

  const series = (data.revenue_series || []).slice(-range);
  const totals = data.totals || {};

  return (
    <div className="space-y-6" data-testid="seller-analytics-tab">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display font-bold text-xl text-[var(--js-text)] flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-[#C84B31]" /> Sales Analytics
          </h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1">
            Snapshot of your business — revenue, best-sellers, low performers, and low stock.
          </p>
        </div>
        <div className="inline-flex bg-[var(--js-subtle)] rounded-full p-1">
          {[7, 30].map((n) => (
            <button
              key={n}
              onClick={() => setRange(n)}
              className={`px-3 py-1 rounded-full text-xs font-semibold ${range === n ? "bg-[#0E1A2B] text-white" : "text-[var(--js-text-secondary)]"}`}
              data-testid={`range-${n}d`}
            >{n}d</button>
          ))}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={DollarSign} label="Today" value={fmtUSD(totals.today?.revenue)} sub={`${totals.today?.orders || 0} orders`} accent="#C84B31" />
        <StatCard icon={DollarSign} label="Last 7 days" value={fmtUSD(totals.week?.revenue)} sub={`${totals.week?.orders || 0} orders`} accent="#E9C46A" />
        <StatCard icon={DollarSign} label="Last 30 days" value={fmtUSD(totals.month?.revenue)} sub={`${totals.month?.orders || 0} orders`} accent="#2A9D8F" />
        <StatCard icon={ShoppingBag} label="All time" value={fmtUSD(totals.all_time?.revenue)} sub={`${totals.all_time?.orders || 0} orders`} accent="#0E1A2B" />
      </div>

      {/* Revenue chart */}
      <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[var(--js-border)] p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-[var(--js-text)]">Revenue (USD)</h3>
          <p className="text-xs text-[var(--js-text-secondary)]">Last {range} days</p>
        </div>
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <AreaChart data={series} margin={{ top: 5, right: 10, left: -8, bottom: 0 }}>
              <defs>
                <linearGradient id="rev-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#C84B31" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#C84B31" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis
                dataKey="date"
                tickFormatter={(d) => (d ? d.slice(5) : "")}
                fontSize={11}
              />
              <YAxis fontSize={11} tickFormatter={(v) => "$" + v} />
              <Tooltip
                formatter={(v, name) => (name === "revenue" ? [fmtUSD(v), "Revenue"] : [v, "Orders"])}
                labelFormatter={(l) => `Date: ${l}`}
              />
              <Area type="monotone" dataKey="revenue" stroke="#C84B31" strokeWidth={2} fill="url(#rev-grad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Two-column: Top products + Low performers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[var(--js-border)] p-4 shadow-sm">
          <h3 className="font-bold text-[var(--js-text)] flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-[#2A9D8F]" /> Top 5 products (revenue)
          </h3>
          {data.top_products?.length ? (
            <ul className="space-y-2">
              {data.top_products.map((p) => (
                <li key={p.id} className="flex items-center gap-3 p-2 rounded-lg bg-[var(--js-bg)]">
                  {p.image_url ? (
                    <img src={p.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                  ) : (
                    <div className="w-10 h-10 rounded-lg bg-[var(--js-subtle)] flex items-center justify-center">
                      <Package className="w-4 h-4 text-[var(--js-text-secondary)]" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[var(--js-text)] truncate">{p.name}</p>
                    <p className="text-xs text-[var(--js-text-secondary)]">{p.quantity} sold</p>
                  </div>
                  <p className="font-bold text-sm text-[#C84B31] whitespace-nowrap">{fmtUSD(p.revenue)}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[var(--js-text-secondary)] italic py-4">No sales yet.</p>
          )}
        </div>

        <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[var(--js-border)] p-4 shadow-sm">
          <h3 className="font-bold text-[var(--js-text)] flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-[#E9C46A]" /> Low performers (last 30 days)
          </h3>
          {data.low_performers?.length ? (
            <ul className="space-y-2">
              {data.low_performers.map((p) => (
                <li key={p.id} className="flex items-center gap-3 p-2 rounded-lg bg-[var(--js-bg)]">
                  {p.image_url ? (
                    <img src={p.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                  ) : (
                    <div className="w-10 h-10 rounded-lg bg-[var(--js-subtle)] flex items-center justify-center">
                      <Package className="w-4 h-4 text-[var(--js-text-secondary)]" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[var(--js-text)] truncate">{p.name}</p>
                    <p className="text-xs text-[var(--js-text-secondary)]">{p.quantity} sold in 30d — consider a promo</p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[var(--js-text-secondary)] italic py-4">Every product is doing well 👏</p>
          )}
        </div>
      </div>

      {/* Low stock */}
      {data.low_stock?.length > 0 && (
        <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[#C84B31] p-4 shadow-sm">
          <h3 className="font-bold text-[#C84B31] flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4" /> Low stock ({data.low_stock.length})
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {data.low_stock.map((p) => (
              <div key={p.id} className="flex items-center justify-between p-2 rounded-lg bg-[var(--js-bg)]">
                <p className="text-sm text-[var(--js-text)] truncate">{p.name}</p>
                <span className="text-xs font-bold text-[#C84B31]">{p.stock} left</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
