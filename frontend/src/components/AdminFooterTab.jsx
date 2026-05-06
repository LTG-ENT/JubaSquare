import { useEffect, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { Save, RotateCcw, Plus, Trash2, GripVertical, ExternalLink, Facebook, Mail, Phone, MapPin, Info } from "lucide-react";
import { toast } from "sonner";

const COLUMN_KEYS = [
  { key: "shop", titleField: "shop_title", linksField: "shop_links", label: "Shop" },
  { key: "company", titleField: "company_title", linksField: "company_links", label: "Company" },
  { key: "legal", titleField: "legal_title", linksField: "legal_links", label: "Legal" },
];

export default function AdminFooterTab() {
  const [draft, setDraft] = useState(null);
  const [saved, setSaved] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/site-config/footer");
      setSaved(data);
      setDraft(JSON.parse(JSON.stringify(data)));
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to load footer");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const set = (key, val) => setDraft((d) => ({ ...d, [key]: val }));

  const setLink = (linksField, idx, key, val) => {
    setDraft((d) => {
      const arr = [...(d[linksField] || [])];
      arr[idx] = { ...arr[idx], [key]: val };
      return { ...d, [linksField]: arr };
    });
  };
  const addLink = (linksField) => {
    setDraft((d) => ({ ...d, [linksField]: [...(d[linksField] || []), { label: "", url: "" }] }));
  };
  const removeLink = (linksField, idx) => {
    setDraft((d) => ({ ...d, [linksField]: (d[linksField] || []).filter((_, i) => i !== idx) }));
  };
  const moveLink = (linksField, idx, dir) => {
    setDraft((d) => {
      const arr = [...(d[linksField] || [])];
      const j = idx + dir;
      if (j < 0 || j >= arr.length) return d;
      [arr[idx], arr[j]] = [arr[j], arr[idx]];
      return { ...d, [linksField]: arr };
    });
  };

  const isDirty = JSON.stringify(saved || {}) !== JSON.stringify(draft || {});

  const onSave = async () => {
    setSaving(true);
    try {
      // Strip empty link rows before saving
      const payload = { ...draft };
      for (const k of ["shop_links", "company_links", "legal_links"]) {
        payload[k] = (payload[k] || []).filter((l) => (l.label || "").trim() && (l.url || "").trim());
      }
      const { data } = await api.put("/admin/site-config/footer", payload);
      setSaved(data);
      setDraft(JSON.parse(JSON.stringify(data)));
      toast.success("Footer saved — live on every page");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const onReset = () => {
    if (!window.confirm("Discard changes and reload the saved version?")) return;
    setDraft(JSON.parse(JSON.stringify(saved)));
  };

  if (loading || !draft) {
    return <p className="text-sm text-[var(--js-text-secondary)]">Loading footer…</p>;
  }

  return (
    <div className="space-y-6 pb-20">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Site footer</p>
          <h2 className="font-display font-bold text-xl text-[var(--js-text)] mt-1">Edit footer</h2>
          <p className="text-xs text-[var(--js-text-secondary)] mt-1">Changes go live on every page as soon as you save. Use absolute URLs (https://…) for external links and paths like <code>/about</code> for internal pages.</p>
        </div>
        <a href="/" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-xs font-bold text-[#C84B31] hover:underline">
          <ExternalLink className="w-3.5 h-3.5" /> Open homepage
        </a>
      </div>

      {/* Brand block */}
      <Card title="Brand">
        <Field label="Tagline (under the logo)" testId="footer-edit-tagline">
          <textarea
            rows={2}
            value={draft.tagline || ""}
            onChange={(e) => set("tagline", e.target.value)}
            data-testid="footer-edit-tagline"
            className="w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
          />
        </Field>
        <div className="grid sm:grid-cols-1 gap-3 mt-3">
          <SocialField icon={Facebook} label="Facebook URL" value={draft.social_facebook} onChange={(v) => set("social_facebook", v)} testId="footer-edit-facebook" />
        </div>
        <p className="text-[11px] text-[var(--js-text-secondary)] mt-2 flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5" /> Leave the Facebook URL empty to hide the icon from the footer.
        </p>
      </Card>

      {/* Link columns */}
      {COLUMN_KEYS.map((col) => (
        <Card key={col.key} title={`${col.label} column`}>
          <Field label="Section title">
            <input
              type="text"
              value={draft[col.titleField] || ""}
              onChange={(e) => set(col.titleField, e.target.value)}
              data-testid={`footer-edit-${col.key}-title`}
              className="w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
            />
          </Field>

          <div className="mt-3">
            <div className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)] mb-2">Links</div>
            <div className="space-y-2" data-testid={`footer-edit-${col.key}-links`}>
              {(draft[col.linksField] || []).map((link, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => moveLink(col.linksField, idx, -1)}
                    disabled={idx === 0}
                    className="text-[var(--js-text-secondary)] hover:text-[var(--js-text)] disabled:opacity-30 px-1"
                    aria-label="Move up"
                  >
                    <GripVertical className="w-4 h-4" />
                  </button>
                  <input
                    type="text"
                    value={link.label}
                    placeholder="Label (e.g. About)"
                    onChange={(e) => setLink(col.linksField, idx, "label", e.target.value)}
                    data-testid={`footer-edit-${col.key}-label-${idx}`}
                    className="flex-1 min-w-0 bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
                  />
                  <input
                    type="text"
                    value={link.url}
                    placeholder="/about or https://…"
                    onChange={(e) => setLink(col.linksField, idx, "url", e.target.value)}
                    data-testid={`footer-edit-${col.key}-url-${idx}`}
                    className="flex-[1.4] min-w-0 bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-[#C84B31]"
                  />
                  <button
                    type="button"
                    onClick={() => removeLink(col.linksField, idx)}
                    data-testid={`footer-edit-${col.key}-remove-${idx}`}
                    className="p-2 hover:bg-[#D90429]/10 rounded-full text-[#D90429]"
                    aria-label="Remove"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => addLink(col.linksField)}
              data-testid={`footer-edit-${col.key}-add`}
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31] hover:text-[#C84B31]"
            >
              <Plus className="w-3.5 h-3.5" /> Add link
            </button>
          </div>
        </Card>
      ))}

      {/* Get in touch column */}
      <Card title="Contact column">
        <Field label="Section title">
          <input
            type="text"
            value={draft.contact_title || ""}
            onChange={(e) => set("contact_title", e.target.value)}
            data-testid="footer-edit-contact-title"
            className="w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
          />
        </Field>
        <div className="grid sm:grid-cols-3 gap-3 mt-3">
          <IconField icon={Mail} label="Email" value={draft.contact_email} onChange={(v) => set("contact_email", v)} placeholder="hello@example.com" testId="footer-edit-email" />
          <IconField icon={Phone} label="Phone" value={draft.contact_phone} onChange={(v) => set("contact_phone", v)} placeholder="+211 ..." testId="footer-edit-phone" />
          <IconField icon={MapPin} label="Location" value={draft.contact_location} onChange={(v) => set("contact_location", v)} placeholder="Juba, South Sudan 🇸🇸" testId="footer-edit-location" />
        </div>
      </Card>

      {/* Bottom bar */}
      <Card title="Bottom bar">
        <Field label="Copyright text (use {year} for the current year)">
          <input
            type="text"
            value={draft.copyright_text || ""}
            onChange={(e) => set("copyright_text", e.target.value)}
            data-testid="footer-edit-copyright"
            className="w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
          />
        </Field>
        <Field label="Bottom tagline" className="mt-3">
          <input
            type="text"
            value={draft.tagline_bottom || ""}
            onChange={(e) => set("tagline_bottom", e.target.value)}
            data-testid="footer-edit-tagline-bottom"
            className="w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
          />
        </Field>
      </Card>

      {/* Sticky save bar */}
      <div className="sticky bottom-4 z-20 flex items-center justify-end gap-2 bg-white border border-[var(--js-border)] rounded-2xl shadow-lg px-4 py-3">
        <p className="text-xs text-[var(--js-text-secondary)] mr-auto">
          {isDirty ? <span className="text-[#9F6B00] font-semibold">⚠ Unsaved changes</span> : "All changes saved"}
        </p>
        <button
          type="button"
          onClick={onReset}
          disabled={!isDirty || saving}
          data-testid="footer-reset-btn"
          className="inline-flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-full border border-[var(--js-border)] text-[var(--js-text)] disabled:opacity-50 hover:border-[#1A1A1A]"
        >
          <RotateCcw className="w-3.5 h-3.5" /> Discard
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={!isDirty || saving}
          data-testid="footer-save-btn"
          className="inline-flex items-center gap-1.5 text-sm font-bold px-5 py-2 rounded-full bg-[#C84B31] hover:bg-[#A83A23] text-white disabled:bg-[#A3A39E]"
        >
          <Save className="w-4 h-4" /> {saving ? "Saving…" : "Save footer"}
        </button>
      </div>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5">
      <h3 className="font-display font-bold text-base text-[var(--js-text)] mb-3">{title}</h3>
      {children}
    </div>
  );
}

function Field({ label, children, className = "" }) {
  return (
    <div className={className}>
      <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function SocialField({ icon: Icon, label, value, onChange, testId }) {
  return (
    <div>
      <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)] flex items-center gap-1">
        <Icon className="w-3.5 h-3.5" /> {label}
      </label>
      <input
        type="text"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder="https://…"
        data-testid={testId}
        className="mt-1 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
      />
    </div>
  );
}

function IconField({ icon: Icon, label, value, onChange, placeholder, testId }) {
  return (
    <div>
      <label className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)] flex items-center gap-1">
        <Icon className="w-3.5 h-3.5" /> {label}
      </label>
      <input
        type="text"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        data-testid={testId}
        className="mt-1 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#C84B31]"
      />
    </div>
  );
}
