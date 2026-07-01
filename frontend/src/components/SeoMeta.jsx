import { Helmet } from "react-helmet-async";

/**
 * Renders JSON-LD structured data + basic per-page meta.
 * Props:
 *   title       — page title (fallback to app default)
 *   description — meta description
 *   image       — social image URL
 *   canonical   — canonical URL
 *   type        — Open Graph type ("website" | "product" | "restaurant.restaurant")
 *   schema      — either a single JSON-LD object OR an array of them
 */
export default function SeoMeta({ title, description, image, canonical, type = "website", schema }) {
  const schemas = schema ? (Array.isArray(schema) ? schema : [schema]) : [];
  return (
    <Helmet>
      {title && <title>{title}</title>}
      {description && <meta name="description" content={description} />}
      {canonical && <link rel="canonical" href={canonical} />}
      {/* Open Graph */}
      <meta property="og:type" content={type} />
      {title && <meta property="og:title" content={title} />}
      {description && <meta property="og:description" content={description} />}
      {image && <meta property="og:image" content={image} />}
      {canonical && <meta property="og:url" content={canonical} />}
      <meta property="og:site_name" content="JubaSquare" />
      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      {title && <meta name="twitter:title" content={title} />}
      {description && <meta name="twitter:description" content={description} />}
      {image && <meta name="twitter:image" content={image} />}
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
