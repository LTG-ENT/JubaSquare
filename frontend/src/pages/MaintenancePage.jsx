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
            {/* Shopping-bag JS mark rendered as SVG (crisp at any size) */}
            <svg viewBox="0 0 120 120" className="jsm-logo" role="img" aria-label="JubaSquare logo">
              <defs>
                <linearGradient id="jsm-bag-grad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%"  stopColor="#f4a261" />
                  <stop offset="55%" stopColor="#e07a2a" />
                  <stop offset="100%" stopColor="#b64a12" />
                </linearGradient>
                <linearGradient id="jsm-hand-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"  stopColor="#3aa0ff" />
                  <stop offset="100%" stopColor="#1a63b3" />
                </linearGradient>
                <filter id="jsm-logo-glow" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur stdDeviation="2.4" result="b" />
                  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
              </defs>

              {/* Handle */}
              <path
                d="M45 40 Q 45 22 60 22 Q 75 22 75 40"
                fill="none"
                stroke="url(#jsm-hand-grad)"
                strokeWidth="5"
                strokeLinecap="round"
                filter="url(#jsm-logo-glow)"
              />
              {/* Bag */}
              <path
                d="M30 42 L90 42 L96 100 Q96 106 90 106 L30 106 Q24 106 24 100 Z"
                fill="url(#jsm-bag-grad)"
                stroke="#2a1206"
                strokeWidth="1"
                filter="url(#jsm-logo-glow)"
              />
              {/* JS lettering */}
              <text
                x="60" y="82"
                textAnchor="middle"
                fontFamily="Georgia, 'Times New Roman', serif"
                fontWeight="700"
                fontSize="34"
                fill="#fff5e8"
                style={{ paintOrder: "stroke" }}
                stroke="#3a1a08"
                strokeWidth="0.6"
              >JS</text>
            </svg>
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
