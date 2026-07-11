/**
 * SeoContext (Iter 33.6)
 * ----------------------
 * Loads /api/seo/public once on app boot and exposes:
 *   - settings (raw payload)
 *   - getPageSeo(pageKey, fallback?) — merges basic + per-page overrides
 *   - refresh() — force reload (used after admin save)
 *
 * Also installs GA4 / GTM / Meta Pixel snippets when their IDs are set.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const SeoContext = createContext(null);

const DEFAULTS = {
  site_title: "JubaSquare",
  meta_description: "",
  default_social_image: "",
  organization_name: "JubaSquare",
  canonical_origin: "https://www.jubasquare.com",
  pages: {},
};

/* ---------------- Analytics loaders (idempotent) ---------------------------- */

function loadGA4(id) {
  if (!id || window.__gaLoaded) return;
  window.__gaLoaded = true;
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${id}`;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  window.gtag("js", new Date());
  window.gtag("config", id);
}

function loadGTM(id) {
  if (!id || window.__gtmLoaded) return;
  window.__gtmLoaded = true;
  const s = document.createElement("script");
  s.innerHTML = `(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start': new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer','${id}');`;
  document.head.appendChild(s);
  const noscript = document.createElement("noscript");
  noscript.innerHTML = `<iframe src="https://www.googletagmanager.com/ns.html?id=${id}" height="0" width="0" style="display:none;visibility:hidden"></iframe>`;
  document.body.prepend(noscript);
}

function loadMetaPixel(id) {
  if (!id || window.__fbqLoaded) return;
  window.__fbqLoaded = true;
  /* eslint-disable */
  !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
  window.fbq('init', id);
  window.fbq('track', 'PageView');
  /* eslint-enable */
}

function injectRawScripts(html, tagAttr) {
  if (!html || typeof html !== "string") return;
  // Idempotent: use a data-attr as the identity key so re-renders don't
  // duplicate. Wipe our previously-injected block, then insert fresh.
  document.querySelectorAll(`[data-seo-injection="${tagAttr}"]`).forEach((n) => n.remove());
  const container = document.createElement("div");
  container.setAttribute("data-seo-injection", tagAttr);
  container.innerHTML = html;
  // Move each child (scripts + meta + link tags) so they actually execute.
  const target = tagAttr === "footer" ? document.body : document.head;
  Array.from(container.childNodes).forEach((child) => {
    if (child.tagName === "SCRIPT") {
      // Re-create <script> so it executes.
      const s = document.createElement("script");
      Array.from(child.attributes).forEach((a) => s.setAttribute(a.name, a.value));
      s.text = child.text || "";
      s.setAttribute("data-seo-injection", tagAttr);
      target.appendChild(s);
    } else {
      child.setAttribute?.("data-seo-injection", tagAttr);
      target.appendChild(child);
    }
  });
}

/* ---------------- Provider -------------------------------------------------- */

export function SeoProvider({ children }) {
  const [settings, setSettings] = useState(DEFAULTS);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get("/seo/public");
      setSettings({ ...DEFAULTS, ...r.data });
    } catch {
      /* keep DEFAULTS */
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Install analytics + custom scripts whenever settings change.
  useEffect(() => {
    if (!loaded) return;
    loadGA4(settings.google_analytics_id);
    loadGTM(settings.google_tag_manager_id);
    loadMetaPixel(settings.meta_pixel_id);
    injectRawScripts(settings.custom_header_scripts, "header");
    injectRawScripts(settings.custom_footer_scripts, "footer");
    // Favicon override
    if (settings.favicon_url) {
      let link = document.querySelector("link[rel~='icon']");
      if (!link) {
        link = document.createElement("link");
        link.rel = "icon";
        document.head.appendChild(link);
      }
      link.href = settings.favicon_url;
    }
    // Verification meta tags (Google Search Console + Bing)
    ["google_search_console_verification", "bing_webmaster_verification"].forEach((key) => {
      const content = settings[key];
      const name = key === "google_search_console_verification" ? "google-site-verification" : "msvalidate.01";
      let el = document.querySelector(`meta[name="${name}"]`);
      if (content) {
        if (!el) {
          el = document.createElement("meta");
          el.setAttribute("name", name);
          document.head.appendChild(el);
        }
        el.setAttribute("content", content);
      } else if (el) {
        el.remove();
      }
    });
  }, [settings, loaded]);

  const getPageSeo = useCallback((pageKey, fallback = {}) => {
    const p = (settings.pages || {})[pageKey] || {};
    return {
      title: p.title || fallback.title || settings.site_title,
      description: p.description || fallback.description || settings.meta_description,
      image: p.social_image_url || fallback.image || settings.default_social_image,
      canonical: p.canonical_url || `${settings.canonical_origin}${fallback.path || (typeof window !== "undefined" ? window.location.pathname : "/")}`,
    };
  }, [settings]);

  return (
    <SeoContext.Provider value={{ settings, loaded, refresh: load, getPageSeo }}>
      {children}
    </SeoContext.Provider>
  );
}

export function useSeo() {
  return useContext(SeoContext) || { settings: DEFAULTS, loaded: false, refresh: () => {}, getPageSeo: () => ({}) };
}
