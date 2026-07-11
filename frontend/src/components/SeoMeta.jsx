import { Helmet } from "react-helmet-async";
import { useSeo } from "@/context/SeoContext";

/**
 * Renders JSON-LD structured data + basic per-page meta.
 * Props:
 *   pageKey     — Iter 33.6 — matches an admin per-page override
 *                 ("home" | "marketplace" | "shops" | "restaurants" |
 *                  "product_detail" | "shop_detail" | "restaurant_detail" |
 *                  "cart" | "login" | ...). Admin values ALWAYS win over
 *                 the caller-provided props below.
 *   title       — page title (fallback to app default)
 *   description — meta description
 *   image       — social image URL
 *   canonical   — canonical URL
 *   type        — Open Graph type ("website" | "product" | "restaurant.restaurant")
 *   schema      — either a single JSON-LD object OR an array of them
 */
export default function SeoMeta({ pageKey, title, description, image, canonical, type = "website", schema }) {
  const { settings, getPageSeo } = useSeo();
  const admin = pageKey ? getPageSeo(pageKey, {}) : {};
  const perPage = pageKey ? (settings?.pages || {})[pageKey] || {} : {};

  // Iter 33.10 — Precedence order:
  //   1. Per-page admin override (highest — admin picks a specific page)
  //   2. Admin's site-wide setting (Basic tab) — overrides caller-provided
  //      defaults so an admin edit ALWAYS takes effect, even on pages that
  //      hard-code their own defaults.
  //   3. Caller-provided prop (page's built-in default).
  // Title keeps the caller prop preferred (pages know their own title) but
  // still lets a per-page admin override + fall through to site_title.
  const finalTitle = perPage.title || title || settings?.site_title;
  const finalDescription = perPage.description || settings?.meta_description || description;
  const finalImage = perPage.social_image_url || settings?.default_social_image || image;
  const finalCanonical = perPage.canonical_url || canonical || admin.canonical;

  const schemas = schema ? (Array.isArray(schema) ? schema : [schema]) : [];
  const org = settings?.organization_name || "JubaSquare";

  return (
    <Helmet prioritizeSeoTags>
      {finalTitle && <title>{finalTitle}</title>}
      {finalDescription && <meta name="description" content={finalDescription} />}
      {finalCanonical && <link rel="canonical" href={finalCanonical} />}
      {/* Open Graph */}
      <meta property="og:type" content={type} />
      {finalTitle && <meta property="og:title" content={finalTitle} />}
      {finalDescription && <meta property="og:description" content={finalDescription} />}
      {finalImage && <meta property="og:image" content={finalImage} />}
      {finalCanonical && <meta property="og:url" content={finalCanonical} />}
      <meta property="og:site_name" content={org} />
      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      {finalTitle && <meta name="twitter:title" content={finalTitle} />}
      {finalDescription && <meta name="twitter:description" content={finalDescription} />}
      {finalImage && <meta name="twitter:image" content={finalImage} />}
      {/* JSON-LD */}
      {schemas.map((s, i) => (
        <script key={i} type="application/ld+json">
          {JSON.stringify(s)}
        </script>
      ))}
    </Helmet>
  );
}

/* --------- Schema builders --------- */

export function organizationSchema(origin) {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "JubaSquare",
    url: origin,
    logo: origin + "/icons/icon-512.png",
    sameAs: [],
    contactPoint: [{
      "@type": "ContactPoint",
      contactType: "customer support",
      email: "support@jubasquare.com",
      areaServed: "SS",
      availableLanguage: ["English", "Arabic", "French"],
    }],
  };
}

export function websiteSchema(origin) {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "JubaSquare",
    url: origin,
    potentialAction: {
      "@type": "SearchAction",
      target: `${origin}/marketplace?search={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  };
}

export function productSchema({ product, origin, shop }) {
  const url = `${origin}/product/${product.id}`;
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.description || undefined,
    image: product.image_url || undefined,
    sku: product.id,
    brand: shop?.name ? { "@type": "Brand", name: shop.name } : undefined,
    offers: {
      "@type": "Offer",
      url,
      priceCurrency: "USD",
      price: Number(product.price_usd || 0).toFixed(2),
      availability: (product.stock ?? 0) > 0
        ? "https://schema.org/InStock"
        : "https://schema.org/OutOfStock",
    },
  };
}

export function shopSchema({ shop, origin }) {
  return {
    "@context": "https://schema.org",
    "@type": "Store",
    name: shop.name,
    url: `${origin}/shop/${shop.id}`,
    image: shop.image_url || undefined,
    description: shop.description || undefined,
    address: shop.address ? {
      "@type": "PostalAddress",
      addressLocality: shop.city || "Juba",
      addressCountry: "SS",
      streetAddress: shop.address,
    } : undefined,
  };
}

export function restaurantSchema({ restaurant, origin }) {
  return {
    "@context": "https://schema.org",
    "@type": "Restaurant",
    name: restaurant.name,
    url: `${origin}/shop/${restaurant.id}`,
    image: restaurant.image_url || undefined,
    servesCuisine: restaurant.cuisine || undefined,
    address: {
      "@type": "PostalAddress",
      addressLocality: restaurant.city || "Juba",
      addressCountry: "SS",
    },
  };
}
