import { useEffect, useState } from "react";
import api from "@/lib/api";
import ImageUpload from "@/components/ImageUpload";
import { toast } from "sonner";
import { Save, Plus, Trash2, Image as ImageIcon, Type, Megaphone } from "lucide-react";

const EMPTY_SLIDE = { label: "", key: "slideRetail", image_url: "" };

const SLIDE_KEY_PRESETS = [
  { key: "slideRetail", label: "Retail (translated)" },
  { key: "slideWholesale", label: "Wholesale (translated)" },
  { key: "slideFood", label: "Food (translated)" },
  { key: "", label: "Custom label (no translation)" },
];

export default function AdminHomepageTab() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [slides, setSlides] = useState([]);
  const [heroTagline, setHeroTagline] = useState("");
  const [heroTitle, setHeroTitle] = useState("");
  const [heroSubtitle, setHeroSubtitle] = useState("");
  const [announcement, setAnnouncement] = useState({ enabled: false, text: "", link: "" });

  useEffect(() => {
    api.get("/homepage")
      .then((r) => {
        const d = r.data || {};
        setSlides(Array.isArray(d.hero_slides) ? d.hero_slides : []);
        setHeroTagline(d.hero_tagline || "");
        setHeroTitle(d.hero_title || "");
        setHeroSubtitle(d.hero_subtitle || "");
        setAnnouncement(d.announcement_bar || { enabled: false, text: "", link: "" });
      })
      .catch(() => toast.error("Failed to load homepage config"))
      .finally(() => setLoading(false));
  }, []);

  const updateSlide = (idx, field, value) => {
    setSlides((prev) => prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)));
  };

  const addSlide = () => {
    if (slides.length >= 6) {
      toast.error("Maximum 6 slides");
      return;
    }
    setSlides((prev) => [...prev, { ...EMPTY_SLIDE, label: `Slide ${prev.length + 1}` }]);
  };

  const removeSlide = (idx) => setSlides((prev) => prev.filter((_, i) => i !== idx));

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        hero_slides: slides.filter((s) => s.image_url),
        hero_tagline: heroTagline,
        hero_title: heroTitle,
        hero_subtitle: heroSubtitle,
        announcement_bar: announcement,
      };
      await api.put("/admin/homepage", payload);
      toast.success("Homepage saved");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-6 text-[var(--js-text-secondary)]">Loading…</div>;

  return (
    <div className="space-y-6" data-testid="admin-homepage-tab">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold text-[var(--js-text)] flex items-center gap-2">
            <ImageIcon className="w-5 h-5 text-[#C84B31]" /> Homepage Customization
          </h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1">
            Customize hero background images, headline text, and the announcement bar.
          </p>
        </div>
        <button
          onClick={save}
          disabled={saving}
          data-testid="save-homepage-btn"
          className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-4 py-2 rounded-full disabled:opacity-50"
        >
          <Save className="w-4 h-4" /> {saving ? "Saving…" : "Save Changes"}
        </button>
      </div>

      {/* Hero text */}
      <section className="bg-white dark:bg-[var(--js-panel)] border border-[var(--js-border)] rounded-2xl p-5 shadow-sm">
        <h3 className="font-bold text-[var(--js-text)] flex items-center gap-2 mb-4">
          <Type className="w-4 h-4 text-[#C84B31]" /> Hero Text (leave blank to use translated defaults)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs uppercase tracking-wide font-bold text-[var(--js-text-secondary)]">Tagline (small caps)</label>
            <input
              type="text"
              value={heroTagline}
              onChange={(e) => setHeroTagline(e.target.value)}
              placeholder="Juba's trusted marketplace"
              className="mt-1 w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-bg)] text-[var(--js-text)]"
              data-testid="hero-tagline-input"
            />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wide font-bold text-[var(--js-text-secondary)]">Title (main headline)</label>
            <input
              type="text"
              value={heroTitle}
              onChange={(e) => setHeroTitle(e.target.value)}
              placeholder="Shop Everything in Juba —"
              className="mt-1 w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-bg)] text-[var(--js-text)]"
              data-testid="hero-title-input"
            />
          </div>
          <div className="md:col-span-2">
            <label className="text-xs uppercase tracking-wide font-bold text-[var(--js-text-secondary)]">Subtitle</label>
            <textarea
              value={heroSubtitle}
              onChange={(e) => setHeroSubtitle(e.target.value)}
              placeholder="From groceries to electronics to food — buy from trusted local shops, warehouses, and restaurants."
              rows={2}
              className="mt-1 w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-bg)] text-[var(--js-text)]"
              data-testid="hero-subtitle-input"
            />
          </div>
        </div>
      </section>

      {/* Hero slides */}
      <section className="bg-white dark:bg-[var(--js-panel)] border border-[var(--js-border)] rounded-2xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h3 className="font-bold text-[var(--js-text)] flex items-center gap-2">
            <ImageIcon className="w-4 h-4 text-[#C84B31]" /> Hero Background Slides ({slides.length}/6)
          </h3>
          <button
            onClick={addSlide}
            className="inline-flex items-center gap-2 bg-[#0E1A2B] text-white text-xs font-semibold px-3 py-1.5 rounded-full hover:bg-[#1E3A5F]"
            data-testid="add-slide-btn"
          >
            <Plus className="w-3.5 h-3.5" /> Add Slide
          </button>
        </div>
        {slides.length === 0 && (
          <p className="text-sm text-[var(--js-text-secondary)] italic">No slides yet. Add one to override the default rotation.</p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {slides.map((s, i) => (
            <div key={i} className="rounded-xl border border-[var(--js-border)] p-3 bg-[var(--js-bg)]" data-testid={`slide-editor-${i}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[var(--js-text-secondary)]">Slide #{i + 1}</span>
                <button onClick={() => removeSlide(i)} className="text-[#C84B31] hover:opacity-80" data-testid={`remove-slide-${i}`}>
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <ImageUpload
                value={s.image_url}
                onChange={(url) => updateSlide(i, "image_url", url)}
                label="Background Image"
                testId={`slide-image-${i}`}
              />
              <div className="mt-3 space-y-2">
                <div>
                  <label className="text-[10px] uppercase font-bold text-[var(--js-text-secondary)]">Label</label>
                  <input
                    type="text"
                    value={s.label || ""}
                    onChange={(e) => updateSlide(i, "label", e.target.value)}
                    placeholder="Retail / Wholesale / Food"
                    className="mt-1 w-full px-2 py-1.5 text-sm rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-panel)] text-[var(--js-text)]"
                    data-testid={`slide-label-${i}`}
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase font-bold text-[var(--js-text-secondary)]">Translation key (optional)</label>
                  <select
                    value={s.key || ""}
                    onChange={(e) => updateSlide(i, "key", e.target.value)}
                    className="mt-1 w-full px-2 py-1.5 text-sm rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-panel)] text-[var(--js-text)]"
                    data-testid={`slide-key-${i}`}
                  >
                    {SLIDE_KEY_PRESETS.map((p) => (
                      <option key={p.key || "custom"} value={p.key}>{p.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Announcement bar */}
      <section className="bg-white dark:bg-[var(--js-panel)] border border-[var(--js-border)] rounded-2xl p-5 shadow-sm">
        <h3 className="font-bold text-[var(--js-text)] flex items-center gap-2 mb-4">
          <Megaphone className="w-4 h-4 text-[#C84B31]" /> Announcement Bar (top of site)
        </h3>
        <label className="flex items-center gap-2 mb-3 cursor-pointer">
          <input
            type="checkbox"
            checked={!!announcement.enabled}
            onChange={(e) => setAnnouncement((p) => ({ ...p, enabled: e.target.checked }))}
            className="w-4 h-4"
            data-testid="announcement-enabled"
          />
          <span className="text-sm font-medium text-[var(--js-text)]">Enable announcement bar</span>
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs uppercase font-bold text-[var(--js-text-secondary)]">Message</label>
            <input
              type="text"
              value={announcement.text || ""}
              onChange={(e) => setAnnouncement((p) => ({ ...p, text: e.target.value }))}
              placeholder="🎉 Free delivery on orders over 5000 SSP"
              className="mt-1 w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-bg)] text-[var(--js-text)]"
              data-testid="announcement-text"
            />
          </div>
          <div>
            <label className="text-xs uppercase font-bold text-[var(--js-text-secondary)]">Link (optional)</label>
            <input
              type="text"
              value={announcement.link || ""}
              onChange={(e) => setAnnouncement((p) => ({ ...p, link: e.target.value }))}
              placeholder="/marketplace"
              className="mt-1 w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-bg)] text-[var(--js-text)]"
              data-testid="announcement-link"
            />
          </div>
        </div>
      </section>
    </div>
  );
}
