import { useEffect, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { Mail, KeyRound, Send, Save, Loader2, ExternalLink, AlertTriangle, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export default function AdminIntegrations() {
  const [cfg, setCfg] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [testTo, setTestTo] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [lastTest, setLastTest] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/integrations");
      setCfg(data);
      setFromEmail(data.resend?.from_email || "");
      // Don't pre-fill apiKey — the user must re-enter it to change it (we only store masked).
      setApiKey("");
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail || e.message));
    }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      const body = {};
      if (apiKey !== "") body.resend_api_key = apiKey; // empty string clears
      if (fromEmail !== (cfg?.resend?.from_email || "")) body.resend_from_email = fromEmail;
      if (Object.keys(body).length === 0) {
        toast.info("No changes to save");
        return;
      }
      await api.post("/admin/integrations", body);
      toast.success("Saved");
      setApiKey("");
      await load();
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };

  const sendTest = async () => {
    if (!testTo) { toast.error("Enter a recipient email"); return; }
    setTesting(true);
    setLastTest(null);
    try {
      const { data } = await api.post("/admin/integrations/test-email", { to: testTo });
      setLastTest(data);
      if (data.ok) toast.success("Test email sent");
      else toast.error("Send failed — see details below");
    } catch (e) {
      setLastTest({ ok: false, error: formatDetail(e.response?.data?.detail || e.message) });
      toast.error("Send failed");
    } finally {
      setTesting(false);
    }
  };

  if (!cfg) return <div className="py-12 text-center text-sm text-[var(--js-text-secondary)]">Loading…</div>;

  const source = cfg.resend?.source;
  const isSet = cfg.resend?.api_key_set;
  const usingTestSender = (cfg.resend?.from_email || "").includes("resend.dev");

  return (
    <div className="space-y-8 max-w-3xl" data-testid="admin-integrations">
      {/* Status banner */}
      <div
        className={`rounded-2xl border p-5 flex items-start gap-3 ${
          isSet ? "bg-[#2D6A4F]/5 border-[#2D6A4F]/30" : "bg-[#C84B31]/5 border-[#C84B31]/30"
        }`}
      >
        {isSet ? (
          <CheckCircle2 className="w-5 h-5 text-[#2D6A4F] shrink-0 mt-0.5" />
        ) : (
          <AlertTriangle className="w-5 h-5 text-[#C84B31] shrink-0 mt-0.5" />
        )}
        <div className="text-sm">
          <p className="font-bold text-[var(--js-text)] mb-1">
            Resend email {isSet ? "is configured" : "is NOT configured"}
            <span className="text-xs font-normal text-[var(--js-text-secondary)] ml-2">
              ({source === "db" ? "from admin UI" : source === "env" ? "from server .env" : "none"})
            </span>
          </p>
          {!isSet && (
            <p className="text-[var(--js-text-secondary)]">
              Signup verification, password reset, and order emails will not be delivered until you set an API key below.
            </p>
          )}
          {isSet && usingTestSender && (
            <p className="text-[var(--js-text-secondary)]">
              <strong>Heads up:</strong> sender is <code className="bg-white px-1.5 py-0.5 rounded text-xs">onboarding@resend.dev</code> — Resend's test mode only delivers to the email on your Resend account. To send to everyone, verify your own domain at{" "}
              <a href={cfg.hints?.verify_domain_url} target="_blank" rel="noreferrer" className="text-[#C84B31] font-semibold underline inline-flex items-center gap-0.5">
                resend.com/domains <ExternalLink className="w-3 h-3" />
              </a>, then change the sender email below.
            </p>
          )}
        </div>
      </div>

      {/* Config form */}
      <div className="bg-white border border-[var(--js-border)] rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Mail className="w-5 h-5 text-[#C84B31]" />
          <h3 className="font-display font-bold text-lg text-[var(--js-text)]">Resend email configuration</h3>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider flex items-center gap-2">
              <KeyRound className="w-3.5 h-3.5" /> API key
            </label>
            <input
              type="password"
              placeholder={isSet ? `Current: ${cfg.resend.api_key_masked} — leave blank to keep` : "re_..."}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              data-testid="integrations-api-key"
              className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]"
            />
            <p className="text-[11px] text-[var(--js-text-secondary)] mt-1">
              Get one at <a href="https://resend.com/api-keys" target="_blank" rel="noreferrer" className="text-[#C84B31] font-semibold underline">resend.com/api-keys</a>.
              {isSet && <> Enter a new key to replace, or leave blank to keep the current one.</>}
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">From email</label>
            <input
              type="email"
              value={fromEmail}
              onChange={(e) => setFromEmail(e.target.value)}
              placeholder="noreply@yourdomain.com"
              data-testid="integrations-from-email"
              className="mt-1.5 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]"
            />
            <p className="text-[11px] text-[var(--js-text-secondary)] mt-1">
              Must be on a domain you've verified at resend.com/domains — except <code className="bg-[var(--js-bg)] px-1 rounded">onboarding@resend.dev</code>, which only delivers to your Resend account email.
            </p>
          </div>

          <button
            onClick={save}
            disabled={saving}
            data-testid="integrations-save"
            className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-5 py-2.5 rounded-xl text-sm disabled:opacity-60"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save changes
          </button>
        </div>
      </div>

      {/* Test email */}
      <div className="bg-white border border-[var(--js-border)] rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Send className="w-5 h-5 text-[#2D6A4F]" />
          <h3 className="font-display font-bold text-lg text-[var(--js-text)]">Send a test email</h3>
        </div>
        <p className="text-sm text-[var(--js-text-secondary)] mb-4">
          Send a test message to verify the integration. Uses the currently saved API key + sender email.
        </p>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="email"
            value={testTo}
            onChange={(e) => setTestTo(e.target.value)}
            placeholder="recipient@example.com"
            data-testid="integrations-test-to"
            className="flex-1 bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#1A1A1A]"
          />
          <button
            onClick={sendTest}
            disabled={testing || !isSet}
            data-testid="integrations-test-send"
            className="inline-flex items-center justify-center gap-2 bg-[#2D6A4F] hover:bg-[#245239] text-white font-semibold px-5 py-2.5 rounded-xl text-sm disabled:opacity-50"
          >
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Send test
          </button>
        </div>

        {lastTest && (
          <div
            className={`mt-4 rounded-xl border p-4 text-sm ${
              lastTest.ok ? "bg-[#2D6A4F]/5 border-[#2D6A4F]/30 text-[#1A1A1A]" : "bg-[#C84B31]/5 border-[#C84B31]/30 text-[#1A1A1A]"
            }`}
          >
            <p className="font-semibold mb-1">
              {lastTest.ok ? "✅ Sent successfully" : "❌ Send failed"}
            </p>
            <pre className="text-xs whitespace-pre-wrap break-all text-[var(--js-text-secondary)]">
              {lastTest.ok ? `Resend id: ${lastTest.id}` : lastTest.error}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
