import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Activity, Database, RefreshCw, CheckCircle2, XCircle, Server, Bell } from "lucide-react";

function pill(ok) {
  return ok
    ? <span className="inline-flex items-center gap-1 text-[10px] font-bold text-green-700 bg-green-50 px-2 py-0.5 rounded-full"><CheckCircle2 className="w-3 h-3" /> OK</span>
    : <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#C84B31] bg-[#C84B31]/10 px-2 py-0.5 rounded-full"><XCircle className="w-3 h-3" /> OFF</span>;
}

export default function AdminPerformanceSection() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const r = await api.get("/admin/health");
      setData(r.data);
    } catch (e) { /* silent */ }
  };

  useEffect(() => {
    let alive = true;
    (async () => { await load(); if (alive) setLoading(false); })();
    return () => { alive = false; };
  }, []);

  const doRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (loading) return <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 text-sm text-[var(--js-text-secondary)]">Loading performance…</div>;
  if (!data) return null;

  const mongoOk = data.mongo?.status === "ok";
  const collections = data.mongo?.collections || {};

  return (
    <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 sm:p-6" data-testid="admin-performance-section">
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-xl bg-[#2A9D8F]/10 text-[#2A9D8F] flex items-center justify-center flex-shrink-0">
          <Activity className="w-5 h-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between flex-wrap gap-2">
            <div>
              <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Platform Status</p>
              <h2 className="font-display font-bold text-lg text-[var(--js-text)] mt-0.5">Performance & Health</h2>
              <p className="text-xs text-[var(--js-text-secondary)] mt-1">Last checked: {new Date(data.checked_at).toLocaleTimeString()}</p>
            </div>
            <button
              onClick={doRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--js-text)] hover:bg-[var(--js-subtle)] px-3 py-1.5 rounded-full border border-[var(--js-border)] disabled:opacity-50"
              data-testid="performance-refresh-btn"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} /> Refresh
            </button>
          </div>

          {/* Status grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
            {/* Backend */}
            <div className="rounded-xl bg-[var(--js-bg)] p-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-bold text-[var(--js-text-secondary)] flex items-center gap-1"><Server className="w-3.5 h-3.5" /> Backend</p>
                {pill(data.backend?.status === "ok")}
              </div>
              <p className="text-sm text-[var(--js-text)]">FastAPI up</p>
            </div>
            {/* Mongo */}
            <div className="rounded-xl bg-[var(--js-bg)] p-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-bold text-[var(--js-text-secondary)] flex items-center gap-1"><Database className="w-3.5 h-3.5" /> MongoDB</p>
                {pill(mongoOk)}
              </div>
              <p className="text-sm text-[var(--js-text)]">
                {mongoOk ? (
                  <>Ping <span className="font-bold">{data.mongo?.ping_ms} ms</span></>
                ) : (
                  <span className="text-[#C84B31]">{data.mongo?.error || "Unreachable"}</span>
                )}
              </p>
            </div>
            {/* Web Push */}
            <div className="rounded-xl bg-[var(--js-bg)] p-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-bold text-[var(--js-text-secondary)] flex items-center gap-1"><Bell className="w-3.5 h-3.5" /> Web Push</p>
                {pill(!!data.integrations?.web_push)}
              </div>
              <p className="text-sm text-[var(--js-text)]">
                {collections.push_subscriptions ?? 0} subscribers
              </p>
            </div>
          </div>

          {/* Integrations */}
          <div className="grid grid-cols-2 gap-2 mt-3">
            <div className="flex items-center justify-between text-xs bg-[var(--js-bg)] rounded-lg px-3 py-2">
              <span className="text-[var(--js-text-secondary)]">Email (Resend)</span>
              {pill(!!data.integrations?.resend_email)}
            </div>
            <div className="flex items-center justify-between text-xs bg-[var(--js-bg)] rounded-lg px-3 py-2">
              <span className="text-[var(--js-text-secondary)]">Odoo Webhook</span>
              {pill(!!data.integrations?.odoo_webhook)}
            </div>
          </div>

          {/* Collections */}
          <div className="mt-4">
            <p className="text-xs font-bold uppercase tracking-wider text-[var(--js-text-secondary)] mb-2">Collections</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(collections).map(([k, v]) => (
                <div key={k} className="rounded-lg bg-[var(--js-bg)] px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-[var(--js-text-secondary)]">{k}</p>
                  <p className="font-display font-bold text-[var(--js-text)]">{v ?? "—"}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Odoo */}
          {data.integrations?.odoo_webhook && (
            <div className="mt-4 rounded-xl bg-[var(--js-bg)] p-3">
              <p className="text-xs font-bold text-[var(--js-text-secondary)] mb-1">Odoo events (24h)</p>
              <p className="text-sm text-[var(--js-text)]">
                <span className="font-bold">{data.odoo?.recent_events || 0}</span> events ·
                {" "}Last: {data.odoo?.last_event_at ? new Date(data.odoo.last_event_at).toLocaleString() : "—"}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
