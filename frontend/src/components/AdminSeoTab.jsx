/**
 * AdminSeoTab (Iter 33.6)
 * -----------------------
 * Admin-facing editor for the /api/admin/seo settings document.
 * Tabs: Basic · Per-page · Advanced · Website Status
 *
 * All fields listed in the spec are wired. Save is a single PUT to
 * /api/admin/seo — the SPA's SeoContext refreshes automatically on save.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Save, RefreshCw, ShieldCheck, ShieldAlert, ExternalLink, Search, Globe, Wrench, Activity } from "lucide-react";
import { useSeo } from "@/context/SeoContext";

const PAGE_KEYS = [
  { id: "home", label: "Home" },
  { id: "marketplace", label: "Marketplace" },
  { id: "shops", label: "Shops (index)" },
  { id: "restaurants", label: "Restaurants (index)" },
  { id: "product_detail", label: "Product detail" },
  { id: "shop_detail", label: "Shop detail" },
  { id: "restaurant_detail", label: "Restaurant detail" },
  { id: "cart", label: "Cart" },
  { id: "login", label: "Login" },
];

const emptyPage = { title: "", description: "", social_image_url: "", slug: "", canonical_url: "" };

function Field({ label, hint, children, testId }) {
  return (
    <label className="block mb-4" data-testid={testId ? `${testId}-wrapper` : undefined}>
      <span className="block text-xs font-bold uppercase tracking-wide text-[var(--js-text-secondary)] mb-1">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-[var(--js-text-secondary)] mt-1">{hint}</span>}
    </label>
  );
}

function TextInput({ value, onChange, placeholder, testId }) {
  return (
    <input
      type="text"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      data-testid={testId}
      className="w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-[var(--js-bg)] text-[var(--js-text)] text-sm"
    />
  );
}

function TextArea({ value, onChange, rows = 3, placeholder, testId }) {
  return (
    <textarea
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      rows={rows}
      placeholder={placeholder}
      data-testid={testId}
      className="w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-[var(--js-bg)] text-[var(--js-text)] text-sm font-mono"
    />
  );
}

export default function AdminSeoTab() {
  const { refresh: refreshPublicSeo } = useSeo();
  const [tab, setTab] = useState("basic");
  const [pageKey, setPageKey] = useState("home");
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get("/admin/seo");
      // Normalize pages to always contain the standard keys.
      const pages = { ...(r.data.pages || {}) };
      PAGE_KEYS.forEach((p) => { if (!pages[p.id]) pages[p.id] = { ...emptyPage }; });
      setData({ ...r.data, pages });
    } catch (e) {
      toast.error("Failed to load SEO settings");
    }
  }, []);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const r = await api.get("/admin/website-status");
      setStatus(r.data);
    } catch (e) {
      toast.error("Failed to load website status");
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (tab === "status") loadStatus(); }, [tab, loadStatus]);

  const patch = useCallback((partial) => {
    setData((prev) => (prev ? { ...prev, ...partial } : prev));
  }, []);

  const patchPage = useCallback((k, partial) => {
    setData((prev) => prev ? { ...prev, pages: { ...(prev.pages || {}), [k]: { ...(prev.pages?.[k] || emptyPage), ...partial } } } : prev);
  }, []);

  const save = useCallback(async () => {
    if (!data) return;
    setSaving(true);
    try {
      await api.put("/admin/seo", data);
      toast.success("SEO settings saved");
      refreshPublicSeo();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  }, [data, refreshPublicSeo]);

  const currentPage = useMemo(() => data?.pages?.[pageKey] || emptyPage, [data, pageKey]);

  if (!data) return <div className="p-6 text-[var(--js-text-secondary)]">Loading SEO settings…</div>;

  return (
    <div className="space-y-6" data-testid="admin-seo-tab">
      {/* Sub-tabs */}
      <div className="flex items-center gap-2 flex-wrap">
        {[
          { id: "basic", label: "Basic SEO", icon: Globe },
          { id: "pages", label: "Per-page SEO", icon: Search },
          { id: "advanced", label: "Advanced", icon: Wrench },
          { id: "status", label: "Website Status", icon: Activity },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            data-testid={`seo-subtab-${t.id}`}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold border ${
              tab === t.id ? "bg-[#1A1A1A] text-white border-[#1A1A1A]" : "bg-[var(--js-card)] text-[var(--js-text)] border-[var(--js-border)]"
            }`}
          >
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
        <div className="flex-1" />
        {tab !== "status" && (
          <button
            onClick={save}
            disabled={saving}
            data-testid="seo-save"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-bold text-white bg-[#C84B31] hover:bg-[#A83A23] disabled:opacity-60"
          >
            <Save className="w-4 h-4" /> {saving ? "Saving…" : "Save changes"}
          </button>
        )}
      </div>

      {tab === "basic" && (
        <div className="bg-[var(--js-card)] border border-[var(--js-border)] rounded-2xl p-6 grid grid-cols-1 md:grid-cols-2 gap-x-8">
          <Field label="Site title" testId="seo-basic-site-title">
            <TextInput value={data.site_title} onChange={(v) => patch({ site_title: v })} placeholder="JubaSquare — South Sudan's Marketplace" testId="seo-input-site-title" />
          </Field>
          <Field label="Meta description" testId="seo-basic-meta-description">
            <TextArea value={data.meta_description} onChange={(v) => patch({ meta_description: v })} rows={2} placeholder="Shop, dine and deliver in South Sudan…" testId="seo-input-meta-description" />
          </Field>
          <Field label="Default social image (Open Graph)" hint="1200×630px PNG/JPG works best">
            <TextInput value={data.default_social_image} onChange={(v) => patch({ default_social_image: v })} placeholder="https://…" testId="seo-input-social-image" />
          </Field>
          <Field label="Favicon URL">
            <TextInput value={data.favicon_url} onChange={(v) => patch({ favicon_url: v })} placeholder="https://…" testId="seo-input-favicon" />
          </Field>
          <Field label="Organization name">
            <TextInput value={data.organization_name} onChange={(v) => patch({ organization_name: v })} testId="seo-input-org-name" />
          </Field>
          <Field label="Contact email">
            <TextInput value={data.contact_email} onChange={(v) => patch({ contact_email: v })} placeholder="support@jubasquare.com" testId="seo-input-contact-email" />
          </Field>
          <Field label="Phone number">
            <TextInput value={data.phone_number} onChange={(v) => patch({ phone_number: v })} placeholder="+211 …" testId="seo-input-phone" />
          </Field>
          <Field label="Business address">
            <TextInput value={data.business_address} onChange={(v) => patch({ business_address: v })} placeholder="Juba, South Sudan" testId="seo-input-address" />
          </Field>
          <Field label="Facebook URL">
            <TextInput value={data.facebook_url} onChange={(v) => patch({ facebook_url: v })} placeholder="https://facebook.com/…" testId="seo-input-facebook" />
          </Field>
          <Field label="Instagram URL">
            <TextInput value={data.instagram_url} onChange={(v) => patch({ instagram_url: v })} placeholder="https://instagram.com/…" testId="seo-input-instagram" />
          </Field>
          <Field label="X (Twitter) URL">
            <TextInput value={data.twitter_url} onChange={(v) => patch({ twitter_url: v })} placeholder="https://x.com/…" testId="seo-input-twitter" />
          </Field>
          <Field label="LinkedIn URL (optional)">
            <TextInput value={data.linkedin_url} onChange={(v) => patch({ linkedin_url: v })} placeholder="https://linkedin.com/company/…" testId="seo-input-linkedin" />
          </Field>
        </div>
      )}

      {tab === "pages" && (
        <div className="bg-[var(--js-card)] border border-[var(--js-border)] rounded-2xl p-6">
          <div className="flex items-center gap-2 flex-wrap mb-5">
            {PAGE_KEYS.map((p) => (
              <button
                key={p.id}
                onClick={() => setPageKey(p.id)}
                data-testid={`seo-page-${p.id}`}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${
                  pageKey === p.id ? "bg-[#C84B31] text-white border-[#C84B31]" : "bg-[var(--js-bg)] text-[var(--js-text)] border-[var(--js-border)]"
                }`}
              >{p.label}</button>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
            <Field label="SEO Title">
              <TextInput value={currentPage.title} onChange={(v) => patchPage(pageKey, { title: v })} placeholder="Overrides default title on this page" testId={`seo-page-${pageKey}-title`} />
            </Field>
            <Field label="Meta description">
              <TextArea rows={2} value={currentPage.description} onChange={(v) => patchPage(pageKey, { description: v })} testId={`seo-page-${pageKey}-desc`} />
            </Field>
            <Field label="Social image URL">
              <TextInput value={currentPage.social_image_url} onChange={(v) => patchPage(pageKey, { social_image_url: v })} placeholder="https://…" testId={`seo-page-${pageKey}-image`} />
            </Field>
            <Field label="URL slug" hint="Used when generating the sitemap for this page.">
              <TextInput value={currentPage.slug} onChange={(v) => patchPage(pageKey, { slug: v })} placeholder="/marketplace" testId={`seo-page-${pageKey}-slug`} />
            </Field>
            <Field label="Canonical URL (auto-filled, editable)" hint="Leave blank to use the request URL on canonical host">
              <TextInput value={currentPage.canonical_url} onChange={(v) => patchPage(pageKey, { canonical_url: v })} placeholder="https://www.jubasquare.com/…" testId={`seo-page-${pageKey}-canonical`} />
            </Field>
          </div>
        </div>
      )}

      {tab === "advanced" && (
        <div className="bg-[var(--js-card)] border border-[var(--js-border)] rounded-2xl p-6 grid grid-cols-1 md:grid-cols-2 gap-x-8">
          <Field label="Google Search Console verification code" hint="Meta tag content only, no <meta> wrapper">
            <TextInput value={data.google_search_console_verification} onChange={(v) => patch({ google_search_console_verification: v })} placeholder="abcXYZ…" testId="seo-input-gsc" />
          </Field>
          <Field label="Bing Webmaster verification">
            <TextInput value={data.bing_webmaster_verification} onChange={(v) => patch({ bing_webmaster_verification: v })} placeholder="…" testId="seo-input-bing" />
          </Field>
          <Field label="Google Analytics Measurement ID" hint="GA4, e.g. G-XXXXXXX">
            <TextInput value={data.google_analytics_id} onChange={(v) => patch({ google_analytics_id: v })} placeholder="G-XXXXXXX" testId="seo-input-ga" />
          </Field>
          <Field label="Google Tag Manager ID">
            <TextInput value={data.google_tag_manager_id} onChange={(v) => patch({ google_tag_manager_id: v })} placeholder="GTM-XXXXXXX" testId="seo-input-gtm" />
          </Field>
          <Field label="Meta Pixel ID">
            <TextInput value={data.meta_pixel_id} onChange={(v) => patch({ meta_pixel_id: v })} placeholder="1234567890" testId="seo-input-pixel" />
          </Field>
          <div className="md:col-span-2">
            <Field label="robots.txt" hint="Leave blank to serve the sensible default (blocks /admin, /seller, /driver, /api). Sitemap is auto-appended.">
              <TextArea rows={7} value={data.robots_txt} onChange={(v) => patch({ robots_txt: v })} placeholder="User-agent: *&#10;Allow: /" testId="seo-input-robots" />
            </Field>
          </div>
          <div className="md:col-span-2">
            <Field label="Custom header scripts" hint="Raw HTML injected into <head>. Use for third-party verification tags, live-chat widgets, etc.">
              <TextArea rows={5} value={data.custom_header_scripts} onChange={(v) => patch({ custom_header_scripts: v })} placeholder="<script>…</script>" testId="seo-input-header-scripts" />
            </Field>
          </div>
          <div className="md:col-span-2">
            <Field label="Custom footer scripts" hint="Raw HTML injected before </body>.">
              <TextArea rows={5} value={data.custom_footer_scripts} onChange={(v) => patch({ custom_footer_scripts: v })} placeholder="<script>…</script>" testId="seo-input-footer-scripts" />
            </Field>
          </div>
        </div>
      )}

      {tab === "status" && (
        <div className="bg-[var(--js-card)] border border-[var(--js-border)] rounded-2xl p-6" data-testid="website-status-panel">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-lg text-[var(--js-text)]">Website Status</h3>
            <button
              onClick={loadStatus}
              disabled={statusLoading}
              data-testid="website-status-refresh"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold border border-[var(--js-border)] hover:bg-[var(--js-subtle)] disabled:opacity-60"
            >
              <RefreshCw className={`w-4 h-4 ${statusLoading ? "animate-spin" : ""}`} /> Refresh
            </button>
          </div>
          {status ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StatusRow label="HTTPS Enabled" ok={status.https_enabled} />
              <StatusRow label="SSL Certificate Status" info={status.ssl_certificate_status} ok={status.https_enabled} />
              <StatusRow label="HTTP → HTTPS Redirect" ok={status.http_to_https_redirect} />
              <StatusRow label="Canonical Domain" info={status.canonical_domain} ok={!!status.canonical_domain_match || status.canonical_domain} />
              <StatusRow label="Sitemap" info={status.sitemap_url} ok linkHref={status.sitemap_url} />
              <StatusRow label="robots.txt" info={`Serving ${status.robots_txt_status}`} ok linkHref={status.robots_url} />
              <StatusRow label="Mixed Content" info={status.mixed_content_status} ok />
              <StatusRow label="Detected Scheme / Host" info={`${status.detected_scheme}://${status.detected_host}`} ok={status.https_enabled} />
              <div className="md:col-span-2 mt-2 text-xs text-[var(--js-text-secondary)]">
                <p>Security headers active:</p>
                <ul className="mt-1 list-disc list-inside">
                  {Object.entries(status.security_headers || {}).map(([k, v]) => (
                    <li key={k}>{k.replaceAll("_", "-")} — {v ? "✓" : "✗"}</li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <div className="text-sm text-[var(--js-text-secondary)]">Loading status…</div>
          )}
          <p className="mt-6 text-xs text-[var(--js-text-secondary)] italic">
            This section is informational only. HTTPS is always enforced by the platform and cannot be disabled from here.
          </p>
        </div>
      )}
    </div>
  );
}

function StatusRow({ label, ok, info, linkHref }) {
  return (
    <div className={`p-4 rounded-xl border ${ok ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`} data-testid={`website-status-row-${label.replace(/\s+/g, "-").toLowerCase()}`}>
      <div className="flex items-start gap-3">
        {ok ? <ShieldCheck className="w-5 h-5 text-emerald-600 mt-0.5" /> : <ShieldAlert className="w-5 h-5 text-red-600 mt-0.5" />}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold text-[var(--js-text)]">{label}</p>
          {info && (
            <p className="text-xs text-[var(--js-text-secondary)] mt-0.5 break-all">
              {linkHref ? (
                <a href={linkHref} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:underline">
                  {info} <ExternalLink className="w-3 h-3" />
                </a>
              ) : info}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
