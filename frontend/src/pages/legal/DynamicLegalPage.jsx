import { useEffect, useState } from "react";
import api from "@/lib/api";
import LegalLayout from "@/pages/legal/LegalLayout";
import { Mail, Phone, MapPin, Clock } from "lucide-react";

/**
 * DynamicLegalPage
 * Fetches /api/pages/{slug} and renders its content inside LegalLayout.
 * If `fallback` is provided, it is rendered when the request fails (offline / 404).
 *
 * For slug="contact" it ALSO renders structured contact cards from
 * `contact_email / contact_phone / contact_location / business_hours` fields.
 */
export default function DynamicLegalPage({ slug, fallback }) {
  const [page, setPage] = useState(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    api.get(`/pages/${slug}`)
      .then((r) => { if (!cancelled) setPage(r.data); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [slug]);

  if (loading) {
    return (
      <LegalLayout title="Loading…" subtitle="Please wait">
        <p className="text-[var(--js-text-secondary)] text-sm">Fetching content…</p>
      </LegalLayout>
    );
  }

  // If the API failed and we have a static fallback, render it
  if ((error || !page) && fallback) {
    return fallback;
  }

  // Last resort
  if (!page) {
    return (
      <LegalLayout title="Page not available" subtitle="Sorry">
        <p>This page is currently unavailable. Please try again shortly.</p>
      </LegalLayout>
    );
  }

  const lastUpdatedDate = page.last_updated
    ? new Date(page.last_updated).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })
    : null;

  return (
    <LegalLayout title={page.title} subtitle={page.subtitle} lastUpdated={lastUpdatedDate}>
      {slug === "contact" && (
        <ContactCards
          email={page.contact_email}
          phone={page.contact_phone}
          location={page.contact_location}
          hours={page.business_hours}
        />
      )}
      <div className="legal-body" data-testid={`page-body-${slug}`} dangerouslySetInnerHTML={{ __html: page.body_html || "" }} />
    </LegalLayout>
  );
}

function ContactCards({ email, phone, location, hours }) {
  const items = [
    email && { icon: Mail, label: "Email", value: email, href: `mailto:${email}` },
    phone && { icon: Phone, label: "Phone", value: phone },
    location && { icon: MapPin, label: "Location", value: location },
    hours && { icon: Clock, label: "Business hours", value: hours, multiline: true },
  ].filter(Boolean);

  if (items.length === 0) return null;

  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-2 mb-6 not-prose" data-testid="contact-cards">
      {items.map((it) => {
        const Icon = it.icon;
        const inner = (
          <>
            <Icon className="w-5 h-5 text-[#C84B31]" />
            <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--js-text-secondary)] mt-2">{it.label}</p>
            <p className={`text-sm font-semibold text-[var(--js-text)] break-words mt-1 ${it.multiline ? "whitespace-pre-line" : ""}`}>
              {it.value}
            </p>
          </>
        );
        return it.href ? (
          <a key={it.label} href={it.href} className="flex flex-col items-start p-5 rounded-2xl border border-[var(--js-border)] bg-[var(--js-bg)] hover:border-[#C84B31] transition">
            {inner}
          </a>
        ) : (
          <div key={it.label} className="flex flex-col items-start p-5 rounded-2xl border border-[var(--js-border)] bg-[var(--js-bg)]">
            {inner}
          </div>
        );
      })}
    </div>
  );
}
