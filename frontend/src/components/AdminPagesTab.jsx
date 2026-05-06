import { useEffect, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { Save, Eye, Code, FileText, RotateCcw, ExternalLink } from "lucide-react";
import { toast } from "sonner";

const PAGE_META = [
  { slug: "terms", label: "Terms of Service", route: "/terms" },
  { slug: "privacy", label: "Privacy Policy", route: "/privacy" },
  { slug: "returns", label: "Return Policy", route: "/returns" },
  { slug: "about", label: "About", route: "/about" },
  { slug: "contact", label: "Contact", route: "/contact" },
];

export default function AdminPagesTab() {
  const [pages, setPages] = useState([]); // [{slug,title,subtitle,body_html,...}]
  const [activeSlug, setActiveSlug] = useState("terms");
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [view, setView] = useState("edit"); // "edit" | "preview"
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/pages");
      setPages(data);
      const active = data.find((p) => p.slug === activeSlug) || data[0];
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

  const currentPage = (slug = activeSlug) => pages.find((p) => p.slug === slug);

  const onChange = (key, val) => setDraft((d) => ({ ...d, [key]: val }));

  const onSave = async () => {
    if (!draft) return;
    if (!draft.title.trim()) {
      toast.error("Title is required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        title: draft.title,
        subtitle: draft.subtitle || "",
        body_html: draft.body_html || "",
      };
      if (activeSlug === "contact") {
        payload.contact_email = draft.contact_email || "";
        payload.contact_phone = draft.contact_phone || "";
        payload.contact_location = draft.contact_location || "";
        payload.business_hours = draft.business_hours || "";
      }
      const { data } = await api.put(`/pages/${activeSlug}`, payload);
      // Replace in pages array
      setPages((arr) => arr.map((p) => (p.slug === activeSlug ? data : p)));
      setDraft(toDraft(data));
      toast.success("Page saved");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const onReset = () => {
    const p = currentPage();
    if (!p) return;
    if (!window.confirm("Discard your changes and reload the saved version?")) return;
    setDraft(toDraft(p));
  };

  if (loading) {
    return <p className="text-sm text-[var(--js-text-secondary)]">Loading pages…</p>;
  }
  if (!draft) {
    return <p className="text-sm text-[var(--js-text-secondary)]">No pages found.</p>;
  }

  const dirty = isDirty(draft, currentPage());

  return (
    <div>
      <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
        <div>
          <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Public pages</p>
          <h2 className="font-display font-bold text-xl text-[var(--js-text)] mt-1">Edit Legal & Info pages</h2>
          <p className="text-xs text-[var(--js-text-secondary)] mt-1">Changes go live immediately on jubasquare.com once saved.</p>
        </div>
        <a
          href={PAGE_META.find((p) => p.slug === activeSlug)?.route || "/"}
          target="_blank"
          rel="noreferrer"
          data-testid="page-open-public"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-[#C84B31] hover:underline"
        >
          <ExternalLink className="w-3.5 h-3.5" /> Open public page
        </a>
      </div>

      {/* Page slug tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        {PAGE_META.map((p) => {
          const active = activeSlug === p.slug;
          return (
            <button
              key={p.slug}
              type="button"
              onClick={() => onTabChange(p.slug)}
              data-testid={`page-tab-${p.slug}`}
              className={`text-xs font-bold px-3 py-2 rounded-full border transition inline-flex items-center gap-1.5 ${
                active
                  ? "bg-[#1A1A1A] text-white border-[#1A1A1A]"
                  : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#1A1A1A]"
              }`}
            >
              <FileText className="w-3.5 h-3.5" /> {p.label}
            </button>
          );
        })}
      </div>

      <div className="bg-white border border-[var(--js-border)] rounded-2xl p-4 sm:p-6">
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
            <button
              type="button"
              onClick={() => setView("edit")}
              data-testid="page-view-edit"
              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full transition ${view === "edit" ? "bg-white shadow text-[var(--js-text)]" : "text-[var(--js-text-secondary)]"}`}
            >
              <Code className="w-3.5 h-3.5" /> Edit
            </button>
            <button
              type="button"
              onClick={() => setView("preview")}
              data-testid="page-view-preview"
              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full transition ${view === "preview" ? "bg-white shadow text-[var(--js-text)]" : "text-[var(--js-text-secondary)]"}`}
            >
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
          <button
            type="button"
            onClick={onReset}
            disabled={!dirty || saving}
            data-testid="page-reset-btn"
            className="inline-flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-full border border-[var(--js-border)] text-[var(--js-text)] disabled:opacity-50 hover:border-[#1A1A1A]"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Discard changes
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={!dirty || saving}
            data-testid="page-save-btn"
            className="inline-flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-full bg-[#C84B31] hover:bg-[#A83A23] text-white disabled:bg-[#A3A39E]"
          >
            <Save className="w-3.5 h-3.5" /> {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
        {currentPage()?.last_updated && (
          <p className="text-[10px] text-[var(--js-text-secondary)] mt-2 text-right">
            Last saved: {new Date(currentPage().last_updated).toLocaleString()}
          </p>
        )}
      </div>
    </div>
  );
}

function ContactField({ label, value, onChange, placeholder, testId }) {
  return (
    <div>
      <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">{label}</label>
      <input
        type="text"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        data-testid={testId}
        className="mt-1 w-full bg-white border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
      />
    </div>
  );
}

function toDraft(p) {
  return {
    title: p.title || "",
    subtitle: p.subtitle || "",
    body_html: p.body_html || "",
    contact_email: p.contact_email || "",
    contact_phone: p.contact_phone || "",
    contact_location: p.contact_location || "",
    business_hours: p.business_hours || "",
  };
}

function isDirty(draft, page) {
  if (!page) return true;
  const keys = ["title", "subtitle", "body_html", "contact_email", "contact_phone", "contact_location", "business_hours"];
  return keys.some((k) => (draft[k] || "") !== (page[k] || ""));
}
