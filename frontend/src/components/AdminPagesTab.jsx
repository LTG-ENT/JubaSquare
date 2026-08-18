import { useEffect, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { Save, Eye, Code, FileText, RotateCcw, ExternalLink, Plus, Trash2, Lock, X } from "lucide-react";
import { toast } from "sonner";

// Public route for a page: core pages keep their pretty URL, custom pages live under /pages/*
const routeFor = (p) => (!p ? "/" : p.core ? `/${p.slug}` : `/pages/${p.slug}`);

export default function AdminPagesTab() {
  const [pages, setPages] = useState([]); // [{slug,title,subtitle,body_html,nav_group,is_published,core,...}]
  const [activeSlug, setActiveSlug] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [view, setView] = useState("edit"); // "edit" | "preview"
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = async (preferSlug) => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/pages");
      setPages(data);
      const active = data.find((p) => p.slug === (preferSlug || activeSlug)) || data[0];
      if (active) {
        setDraft(toDraft(active));
        setActiveSlug(active.slug);
      }
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to load pages");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line

  const currentPage = (slug = activeSlug) => pages.find((p) => p.slug === slug);

  const onTabChange = (slug) => {
    if (slug === activeSlug) return;
    if (draft && isDirty(draft, currentPage(activeSlug))) {
      if (!window.confirm("You have unsaved changes on the current page. Discard them?")) return;
    }
    setActiveSlug(slug);
    const p = pages.find((x) => x.slug === slug);
    if (p) setDraft(toDraft(p));
    setView("edit");
  };

  const onChange = (key, val) => setDraft((d) => ({ ...d, [key]: val }));

  const buildPayload = (d) => {
    const payload = {
      title: d.title,
      subtitle: d.subtitle || "",
      body_html: d.body_html || "",
      nav_group: d.nav_group || "Info",
      is_published: !!d.is_published,
    };
    if (activeSlug === "contact") {
      payload.contact_email = d.contact_email || "";
      payload.contact_phone = d.contact_phone || "";
      payload.contact_location = d.contact_location || "";
      payload.business_hours = d.business_hours || "";
    }
    return payload;
  };

  const onSave = async () => {
    if (!draft) return;
    if (!draft.title.trim()) { toast.error("Title is required"); return; }
    setSaving(true);
    try {
      const { data } = await api.put(`/pages/${activeSlug}`, buildPayload(draft));
      setPages((arr) => arr.map((p) => (p.slug === activeSlug ? data : p)));
      setDraft(toDraft(data));
      toast.success("Page saved");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const onTogglePublish = async () => {
    const p = currentPage();
    if (!p) return;
    setSaving(true);
    try {
      const { data } = await api.put(`/pages/${activeSlug}`, { ...buildPayload(draft), is_published: !p.is_published });
      setPages((arr) => arr.map((x) => (x.slug === activeSlug ? data : x)));
      setDraft(toDraft(data));
      toast.success(data.is_published ? "Page is now live" : "Page unpublished (hidden from site)");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    const p = currentPage();
    if (!p || p.core) return;
    if (!window.confirm(`Delete the page "${p.title}"? This can't be undone.`)) return;
    try {
      await api.delete(`/pages/${p.slug}`);
      toast.success("Page deleted");
      const remaining = pages.filter((x) => x.slug !== p.slug);
      setPages(remaining);
      const next = remaining[0];
      setActiveSlug(next ? next.slug : null);
      setDraft(next ? toDraft(next) : null);
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to delete");
    }
  };

  const onReset = () => {
    const p = currentPage();
    if (!p) return;
    if (!window.confirm("Discard your changes and reload the saved version?")) return;
    setDraft(toDraft(p));
  };

  const onCreated = async (newSlug) => {
    setShowCreate(false);
    await load(newSlug);
    setView("edit");
  };

  if (loading) return <p className="text-sm text-[var(--js-text-secondary)]">Loading pages…</p>;

  const active = currentPage();
  const dirty = draft && isDirty(draft, active);

  return (
    <div>
      <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
        <div>
          <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Public pages</p>
          <h2 className="font-display font-bold text-xl text-[var(--js-text)] mt-1">Legal & Info pages</h2>
          <p className="text-xs text-[var(--js-text-secondary)] mt-1">Edit, add, publish or remove the pages on jubasquare.com. Changes go live immediately once saved.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            data-testid="page-new-btn"
            className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-2 rounded-full bg-[#1A1A1A] text-white hover:bg-black transition"
          >
            <Plus className="w-3.5 h-3.5" /> New page
          </button>
          {active && (
            <a
              href={routeFor(active)}
              target="_blank"
              rel="noreferrer"
              data-testid="page-open-public"
              className="inline-flex items-center gap-1.5 text-xs font-bold text-[#C84B31] hover:underline"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Open public page
            </a>
          )}
        </div>
      </div>

      {/* Page tabs */}
      <div className="mb-4 flex flex-wrap gap-2" data-testid="page-tabs">
        {pages.map((p) => {
          const isActive = activeSlug === p.slug;
          return (
            <button
              key={p.slug}
              type="button"
              onClick={() => onTabChange(p.slug)}
              data-testid={`page-tab-${p.slug}`}
              title={p.core ? "Standard page (can't be deleted)" : "Custom page"}
              className={`text-xs font-bold px-3 py-2 rounded-full border transition inline-flex items-center gap-1.5 ${
                isActive
                  ? "bg-[#1A1A1A] text-white border-[#1A1A1A]"
                  : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#1A1A1A]"
              } ${p.is_published ? "" : "opacity-60"}`}
            >
              {p.core ? <Lock className="w-3 h-3" /> : <FileText className="w-3.5 h-3.5" />}
              {p.title || p.slug}
              {!p.is_published && <span className="text-[9px] uppercase tracking-wide">· hidden</span>}
            </button>
          );
        })}
      </div>

      {!draft ? (
        <p className="text-sm text-[var(--js-text-secondary)]">No pages yet. Click “New page” to create one.</p>
      ) : (
      <div className="bg-white border border-[var(--js-border)] rounded-2xl p-4 sm:p-6">
        {/* Meta row: slug + group + publish + delete */}
        <div className="flex flex-wrap items-center gap-2 mb-4 pb-4 border-b border-[var(--js-border)]">
          <span className="text-[11px] font-mono px-2 py-1 rounded-md bg-[var(--js-subtle)] text-[var(--js-text-secondary)]" data-testid="page-slug-badge">
            {active?.core ? `/${draft.slug}` : `/pages/${draft.slug}`}
          </span>
          {active?.core && (
            <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded-md bg-amber-50 text-amber-700 border border-amber-200">
              <Lock className="w-3 h-3" /> Standard page
            </span>
          )}
          <button
            type="button"
            onClick={onTogglePublish}
            disabled={saving}
            data-testid="page-publish-toggle"
            className={`text-xs font-bold px-3 py-1.5 rounded-full border transition ${
              active?.is_published
                ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100"
                : "bg-gray-100 text-gray-600 border-gray-300 hover:bg-gray-200"
            }`}
          >
            {active?.is_published ? "● Published" : "○ Hidden"}
          </button>
          <div className="ml-auto flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <label className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Group</label>
              <input
                type="text"
                value={draft.nav_group || ""}
                onChange={(e) => onChange("nav_group", e.target.value)}
                data-testid="page-navgroup-input"
                placeholder="Legal / Info"
                className="w-28 bg-[var(--js-bg)] border border-[var(--js-border)] rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-[#C84B31]"
              />
            </div>
            {!active?.core && (
              <button
                type="button"
                onClick={onDelete}
                data-testid="page-delete-btn"
                className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full border border-red-200 text-red-600 hover:bg-red-50 transition"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete
              </button>
            )}
          </div>
        </div>

        {/* Title / Subtitle */}
        <div className="grid sm:grid-cols-2 gap-3 mb-3">
          <div>
            <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Title</label>
            <input
              type="text"
              value={draft.title}
              onChange={(e) => onChange("title", e.target.value)}
              data-testid="page-title-input"
              className="mt-1 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
            />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Subtitle</label>
            <input
              type="text"
              value={draft.subtitle || ""}
              onChange={(e) => onChange("subtitle", e.target.value)}
              data-testid="page-subtitle-input"
              className="mt-1 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
            />
          </div>
        </div>

        {/* Contact-only structured fields */}
        {activeSlug === "contact" && (
          <div className="grid sm:grid-cols-2 gap-3 mb-3 p-3 rounded-xl bg-[var(--js-bg)] border border-[var(--js-border)]">
            <ContactField label="Contact email" testId="page-contact-email" value={draft.contact_email} onChange={(v) => onChange("contact_email", v)} placeholder="hello@example.com" />
            <ContactField label="Contact phone" testId="page-contact-phone" value={draft.contact_phone} onChange={(v) => onChange("contact_phone", v)} placeholder="+211 ..." />
            <ContactField label="Location" testId="page-contact-location" value={draft.contact_location} onChange={(v) => onChange("contact_location", v)} placeholder="Juba, South Sudan" />
            <div>
              <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Business hours</label>
              <textarea
                rows={2}
                value={draft.business_hours || ""}
                onChange={(e) => onChange("business_hours", e.target.value)}
                data-testid="page-business-hours"
                className="mt-1 w-full bg-white border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
                placeholder={"Mon–Sat: 8AM – 8PM\nSunday: 10AM – 6PM"}
              />
            </div>
          </div>
        )}

        {/* Edit / Preview toggle */}
        <div className="flex items-center justify-between mb-2 mt-4">
          <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Body content (HTML)</label>
          <div className="inline-flex bg-[var(--js-subtle)] rounded-full p-1 text-xs font-bold">
            <button type="button" onClick={() => setView("edit")} data-testid="page-view-edit"
              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full transition ${view === "edit" ? "bg-white shadow text-[var(--js-text)]" : "text-[var(--js-text-secondary)]"}`}>
              <Code className="w-3.5 h-3.5" /> Edit
            </button>
            <button type="button" onClick={() => setView("preview")} data-testid="page-view-preview"
              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full transition ${view === "preview" ? "bg-white shadow text-[var(--js-text)]" : "text-[var(--js-text-secondary)]"}`}>
              <Eye className="w-3.5 h-3.5" /> Preview
            </button>
          </div>
        </div>

        {view === "edit" ? (
          <textarea
            rows={20}
            value={draft.body_html || ""}
            onChange={(e) => onChange("body_html", e.target.value)}
            data-testid="page-body-input"
            spellCheck={false}
            className="w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-[#C84B31] leading-relaxed"
            placeholder="<p>Your page content in HTML…</p>"
          />
        ) : (
          <div
            data-testid="page-body-preview"
            className="legal-body bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl p-4"
            style={{ minHeight: 240 }}
            dangerouslySetInnerHTML={{ __html: draft.body_html || "<p class='text-gray-400'>(empty)</p>" }}
          />
        )}

        <p className="text-[10px] text-[var(--js-text-secondary)] mt-2">
          Supported tags: <code>&lt;h2&gt;</code>, <code>&lt;p&gt;</code>, <code>&lt;ul&gt;&lt;li&gt;</code>, <code>&lt;ol&gt;&lt;li&gt;</code>, <code>&lt;a href&gt;</code>, <code>&lt;strong&gt;</code>, <code>&lt;em&gt;</code>, <code>&lt;br&gt;</code>.
        </p>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 mt-4">
          <button type="button" onClick={onReset} disabled={!dirty || saving} data-testid="page-reset-btn"
            className="inline-flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-full border border-[var(--js-border)] text-[var(--js-text)] disabled:opacity-50 hover:border-[#1A1A1A]">
            <RotateCcw className="w-3.5 h-3.5" /> Discard changes
          </button>
          <button type="button" onClick={onSave} disabled={!dirty || saving} data-testid="page-save-btn"
            className="inline-flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-full bg-[#C84B31] hover:bg-[#A83A23] text-white disabled:bg-[#A3A39E]">
            <Save className="w-3.5 h-3.5" /> {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
        {active?.last_updated && (
          <p className="text-[10px] text-[var(--js-text-secondary)] mt-2 text-right">
            Last saved: {new Date(active.last_updated).toLocaleString()}
          </p>
        )}
      </div>
      )}

      {showCreate && (
        <CreatePageModal
          existingSlugs={pages.map((p) => p.slug)}
          onClose={() => setShowCreate(false)}
          onCreated={onCreated}
        />
      )}
    </div>
  );
}

function CreatePageModal({ onClose, onCreated, existingSlugs }) {
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [navGroup, setNavGroup] = useState("Info");
  const [busy, setBusy] = useState(false);
  const [touchedSlug, setTouchedSlug] = useState(false);

  const slugify = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const effectiveSlug = touchedSlug ? slugify(slug) : slugify(title);

  const submit = async () => {
    if (!title.trim()) { toast.error("Title is required"); return; }
    if (!effectiveSlug) { toast.error("Enter a valid slug"); return; }
    if (existingSlugs.includes(effectiveSlug)) { toast.error("A page with this URL already exists"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/admin/pages", {
        title: title.trim(),
        slug: effectiveSlug,
        nav_group: navGroup || "Info",
        subtitle: navGroup || "",
        body_html: "<p>Start writing your page content here…</p>",
      });
      toast.success("Page created");
      onCreated(data.slug);
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to create page");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose} data-testid="page-create-modal">
      <div className="bg-white rounded-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-lg text-[var(--js-text)]">Create a new page</h3>
          <button onClick={onClose} className="text-[var(--js-text-secondary)] hover:text-[var(--js-text)]" data-testid="page-create-close"><X className="w-5 h-5" /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Title</label>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus data-testid="page-create-title"
              placeholder="e.g. Shipping & Customs" className="mt-1 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">URL (slug)</label>
            <div className="mt-1 flex items-center gap-1">
              <span className="text-sm text-[var(--js-text-secondary)] font-mono">/pages/</span>
              <input type="text" value={touchedSlug ? slug : effectiveSlug}
                onChange={(e) => { setTouchedSlug(true); setSlug(e.target.value); }}
                data-testid="page-create-slug"
                className="flex-1 bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#C84B31]" />
            </div>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Group</label>
            <input type="text" value={navGroup} onChange={(e) => setNavGroup(e.target.value)} data-testid="page-create-group"
              placeholder="Legal / Info" className="mt-1 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]" />
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 mt-6">
          <button type="button" onClick={onClose} className="text-xs font-bold px-4 py-2 rounded-full border border-[var(--js-border)] hover:border-[#1A1A1A]">Cancel</button>
          <button type="button" onClick={submit} disabled={busy} data-testid="page-create-submit"
            className="inline-flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-full bg-[#C84B31] hover:bg-[#A83A23] text-white disabled:opacity-50">
            <Plus className="w-3.5 h-3.5" /> {busy ? "Creating…" : "Create page"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ContactField({ label, value, onChange, placeholder, testId }) {
  return (
    <div>
      <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">{label}</label>
      <input type="text" value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} data-testid={testId}
        className="mt-1 w-full bg-white border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]" />
    </div>
  );
}

function toDraft(p) {
  return {
    slug: p.slug || "",
    title: p.title || "",
    subtitle: p.subtitle || "",
    body_html: p.body_html || "",
    nav_group: p.nav_group || "Info",
    is_published: p.is_published !== false,
    core: !!p.core,
    contact_email: p.contact_email || "",
    contact_phone: p.contact_phone || "",
    contact_location: p.contact_location || "",
    business_hours: p.business_hours || "",
  };
}

function isDirty(draft, page) {
  if (!page) return true;
  const keys = ["title", "subtitle", "body_html", "nav_group", "contact_email", "contact_phone", "contact_location", "business_hours"];
  if ((draft.is_published !== false) !== (page.is_published !== false)) return true;
  return keys.some((k) => (draft[k] || "") !== (page[k] || ""));
}
