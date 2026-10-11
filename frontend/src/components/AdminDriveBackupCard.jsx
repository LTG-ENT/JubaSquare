import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api, { formatDetail } from "@/lib/api";
import { toast } from "sonner";
import { Cloud, CloudUpload, Loader2, Unlink, CheckCircle2, XCircle, Clock, ExternalLink } from "lucide-react";

const STATUS = {
  success: { icon: CheckCircle2, cls: "text-emerald-700", label: "Success" },
  failed: { icon: XCircle, cls: "text-red-700", label: "Failed" },
  running: { icon: Loader2, cls: "text-blue-700 animate-spin", label: "Running" },
};

const fmtSize = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round((b || 0) / 1024))} KB`);
const fmtDate = (s) => (s ? s.slice(0, 16).replace("T", " ") : "—");

const RunRow = ({ r }) => {
  const st = STATUS[r.status] || STATUS.running;
  const Icon = st.icon;
  return (
    <tr className="border-t border-[var(--js-border)]" data-testid={`drive-run-${r.id.slice(0, 8)}`}>
      <td className="px-3 py-2 text-xs">{fmtDate(r.started_at)}</td>
      <td className="px-3 py-2 text-xs capitalize">{r.trigger}</td>
      <td className={`px-3 py-2 text-xs font-semibold ${st.cls.replace(" animate-spin", "")}`}>
        <span className="inline-flex items-center gap-1"><Icon className={`w-3.5 h-3.5 ${st.cls}`} /> {st.label}</span>
        {r.error && <div className="text-[10px] font-normal text-red-700 max-w-xs truncate" title={r.error}>{r.error}</div>}
      </td>
      <td className="px-3 py-2 text-xs">{r.size_bytes ? fmtSize(r.size_bytes) : "—"}</td>
      <td className="px-3 py-2 text-xs">
        {r.web_link ? <a href={r.web_link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[#264653] font-semibold hover:underline">Open <ExternalLink className="w-3 h-3" /></a> : "—"}
      </td>
    </tr>
  );
};

export const AdminDriveBackupCard = () => {
  const [st, setSt] = useState(null);
  const [busy, setBusy] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();

  const load = useCallback(async () => {
    try {
      const r = await api.get("/admin/drive-backup/status");
      setSt(r.data);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Could not load Drive backup status");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const d = searchParams.get("drive");
    if (!d) return;
    if (d === "connected") toast.success("Google Drive connected");
    else if (d === "scope") toast.error("Drive permission was not granted. Click Connect again and make sure the Google Drive checkbox is ticked on the Google screen.", { duration: 8000 });
    else toast.error("Google Drive connection failed. Please try again.");
    searchParams.delete("drive");
    setSearchParams(searchParams, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (!st?.runs?.some((r) => r.status === "running")) return undefined;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [st, load]);

  const call = async (key, fn, okMsg) => {
    setBusy(key);
    try {
      await fn();
      if (okMsg) toast.success(okMsg);
      await load();
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Action failed");
    } finally {
      setBusy("");
    }
  };

  const connect = () => call("connect", async () => {
    const r = await api.post("/admin/drive-backup/connect", { origin: window.location.origin });
    window.location.href = r.data.authorization_url;
  });
  const disconnect = () => {
    if (!window.confirm("Disconnect Google Drive? Automatic backups will stop. Existing files on Drive are kept.")) return;
    call("disconnect", () => api.post("/admin/drive-backup/disconnect"), "Google Drive disconnected");
  };
  const saveSchedule = (enabled, frequency) =>
    call("schedule", () => api.put("/admin/drive-backup/schedule", { enabled, frequency }), "Backup schedule saved");
  const runNow = () => call("run", () => api.post("/admin/drive-backup/run"), "Backup started — this may take a minute");

  if (!st) return null;

  return (
    <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 sm:p-6" data-testid="settings-drive-backup-card">
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-xl bg-[#264653]/10 text-[#264653] flex items-center justify-center flex-shrink-0">
          <Cloud className="w-5 h-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Safety</p>
          <h2 className="font-display font-bold text-lg text-[var(--js-text)] mt-0.5">Automatic backup to Google Drive</h2>
          <p className="text-xs text-[var(--js-text-secondary)] mt-1 leading-relaxed">
            Full backups are saved to the <b>{st.folder_name}</b> folder in your Google Drive. The last {st.keep_last} are kept and older ones are deleted automatically. Any backup file can be restored with <b>Restore</b> above.
          </p>

          {!st.configured ? (
            <p className="mt-4 text-sm text-red-700" data-testid="drive-not-configured">Google Drive credentials are not configured on the server.</p>
          ) : !st.connected ? (
            <button onClick={connect} disabled={busy === "connect"} data-testid="drive-connect-btn"
              className="mt-4 inline-flex items-center gap-2 text-sm font-bold px-5 py-2.5 rounded-xl bg-[#264653] hover:bg-[#1d3640] text-white disabled:opacity-60 transition-colors">
              {busy === "connect" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Cloud className="w-4 h-4" />} Connect Google Drive
            </button>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-700" data-testid="drive-connected-account">
                  <CheckCircle2 className="w-4 h-4" /> Connected{st.account_email ? ` as ${st.account_email}` : ""}
                </span>
                <button onClick={disconnect} disabled={!!busy} data-testid="drive-disconnect-btn"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-[#D90429] hover:underline">
                  <Unlink className="w-3.5 h-3.5" /> Disconnect
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <label className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--js-text)] cursor-pointer">
                  <input type="checkbox" checked={st.enabled} disabled={!!busy} data-testid="drive-auto-toggle"
                    onChange={(e) => saveSchedule(e.target.checked, st.frequency)} className="w-4 h-4 accent-[#264653]" />
                  Automatic backups
                </label>
                <select value={st.frequency} disabled={!!busy} data-testid="drive-frequency-select"
                  onChange={(e) => saveSchedule(st.enabled, e.target.value)}
                  className="bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm font-semibold focus:outline-none focus:border-[#264653]">
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </select>
                <button onClick={runNow} disabled={!!busy || st.runs?.some((r) => r.status === "running")} data-testid="drive-run-now-btn"
                  className="inline-flex items-center gap-1.5 text-sm font-bold px-5 py-2.5 rounded-xl border border-[#264653] text-[#264653] hover:bg-[#264653] hover:text-white disabled:opacity-50 transition-colors">
                  {busy === "run" ? <Loader2 className="w-4 h-4 animate-spin" /> : <CloudUpload className="w-4 h-4" />} Back up now
                </button>
              </div>
              <p className="text-xs text-[var(--js-text-secondary)] inline-flex items-center gap-1" data-testid="drive-last-success">
                <Clock className="w-3.5 h-3.5" /> Last successful backup: {fmtDate(st.last_success_at)} (UTC)
              </p>
            </div>
          )}

          {st.runs?.length > 0 && (
            <div className="mt-5 overflow-x-auto border border-[var(--js-border)] rounded-xl" data-testid="drive-run-history">
              <table className="min-w-full text-sm">
                <thead className="bg-[var(--js-bg)] text-[10px] uppercase tracking-wider text-[var(--js-text-secondary)]">
                  <tr>
                    <th className="text-left px-3 py-2">Started (UTC)</th>
                    <th className="text-left px-3 py-2">Trigger</th>
                    <th className="text-left px-3 py-2">Status</th>
                    <th className="text-left px-3 py-2">Size</th>
                    <th className="text-left px-3 py-2">File</th>
                  </tr>
                </thead>
                <tbody>{st.runs.map((r) => <RunRow key={r.id} r={r} />)}</tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
