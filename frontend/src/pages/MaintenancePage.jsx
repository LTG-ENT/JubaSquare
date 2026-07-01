import { useEffect } from "react";
import { Helmet } from "react-helmet-async";
import "@/pages/MaintenancePage.css";

/**
 * Fullscreen JubaSquare-branded maintenance page — 100% HTML + CSS.
 *
 * No image dependencies for the artwork: the shopping-bag logo, "JS" mark,
 * wordmark, heading, subtitle, and animated orbits/particles are all rendered
 * with HTML + SVG so it scales pixel-perfect on any device (desktop, tablet,
 * mobile portrait/landscape, tiny phones).
 *
 * Rendered ONLY when settings.maintenance_mode === true AND the visitor is NOT
 * an admin AND the current path isn't allowlisted (login/admin/etc.). See
 * App.js → <MaintenanceGate>.
 *
 * - Pure CSS animations (no GIF/video)
 * - Respects prefers-reduced-motion
 * - <meta robots="noindex, nofollow"> so search engines skip it
 * - Fluid typography via clamp() so nothing is ever clipped or too small
 */
export default function MaintenancePage() {
  useEffect(() => {
    // Lock body scroll while the overlay is visible
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  // Small twinkling star particles scattered around the canvas
  const particles = [
    ["9%",  "18%", "0.0s", 0.8],
    ["16%", "72%", "1.4s", 0.55],
    ["23%", "36%", "2.5s", 0.75],
    ["31%", "82%", "0.6s", 0.5],
    ["39%", "12%", "1.8s", 0.7],
    ["48%", "88%", "2.8s", 0.55],
    ["57%", "22%", "0.9s", 0.7],
    ["66%", "81%", "2.2s", 0.5],
    ["74%", "35%", "1.1s", 0.75],
    ["84%", "82%", "2.9s", 0.55],
    ["91%", "24%", "0.4s", 0.8],
    ["88%", "58%", "1.9s", 0.5],
    ["5%",  "50%", "1.2s", 0.6],
    ["95%", "42%", "0.7s", 0.65],
    ["50%", "6%",  "2.1s", 0.7],
  ];

  return (
    <>
      <Helmet>
        <title>JubaSquare — Under Maintenance</title>
        <meta name="robots" content="noindex, nofollow" />
        <meta name="description" content="JubaSquare is temporarily under maintenance. Please check back shortly." />
        <meta name="theme-color" content="#061331" />
      </Helmet>

      <main className="jsm-page" aria-label="JubaSquare under maintenance" data-testid="maintenance-page">
        {/* -------- Ambient decorative layers -------- */}
        <div className="jsm-scene-bg" role="presentation" />
        <div className="jsm-soft-glow" role="presentation" />
        <div className="jsm-orbit" role="presentation" />
        <div className="jsm-orbit jsm-orbit--second" role="presentation" />
        <span className="jsm-dot jsm-dot--orange jsm-dot--one" aria-hidden="true" />
        <span className="jsm-dot jsm-dot--blue jsm-dot--two" aria-hidden="true" />
        <span className="jsm-dot jsm-dot--orange jsm-dot--three" aria-hidden="true" />
        {particles.map(([x, y, d, s], i) => (
          <span
            key={i}
            className="jsm-particle"
            style={{ "--x": x, "--y": y, "--d": d, "--s": s }}
            aria-hidden="true"
          />
        ))}
        <div className="jsm-bottom-wave" role="presentation" />
        <div className="jsm-light-sweep" role="presentation" />

        {/* -------- Center content -------- */}
        <div className="jsm-content">
          <div className="jsm-logo-wrap" aria-hidden="true">
            {/* Real JubaSquare logo — properly-centered 1024x1024 export
                (icon-512.png was offset to the upper-left corner, which
                made the shopping bag look squished/deformed in the square
                wrapper). This file letterboxes the source cleanly. */}
            <img
              src="/icons/jubasquare-logo.png"
              alt="JubaSquare"
              className="jsm-logo"
              draggable="false"
              decoding="async"
            />
          </div>

          <p className="jsm-wordmark">JubaSquare</p>

          <h1 className="jsm-headline" data-testid="maintenance-heading">
            <span className="jsm-headline-line">WE&apos;RE UNDER</span>
            <span className="jsm-headline-line jsm-headline-line--accent">MAINTENANCE</span>
          </h1>

          <p className="jsm-subtitle">
            We&apos;re making improvements and will be back soon.
          </p>

          <span className="jsm-pulse" aria-hidden="true">
            <span className="jsm-pulse-dot" />
            Working on it
          </span>
        </div>

        {/* Accessible textual fallback for AT / screen readers */}
        <div className="jsm-sr-only">
          JubaSquare is under maintenance. We&apos;ll be back shortly.
        </div>
      </main>
    </>
  );
}
