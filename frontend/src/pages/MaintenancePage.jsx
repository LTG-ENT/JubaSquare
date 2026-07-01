import { useEffect } from "react";
import { Helmet } from "react-helmet-async";
import "@/pages/MaintenancePage.css";

/**
 * Fullscreen JubaSquare-branded maintenance page.
 * Rendered only when settings.maintenance_mode === true AND the visitor is NOT an admin
 * AND the current path is not in the allowlist (login/admin/etc.). See App.js for gating.
 *
 * The design is a React port of /public/jubasquare-maintenance.webp + the provided CSS
 * assets. Pure CSS animations — no GIF/video. Respects prefers-reduced-motion.
 * Adds noindex meta tags so search engines skip it while the site is down.
 */
export default function MaintenancePage() {
  useEffect(() => {
    // Prevent scroll on the page under the fixed overlay
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  // Particle definitions matching the provided design
  const particles = [
    ["9%", "77%", "0.0s", 0.8],
    ["16%", "28%", "1.4s", 0.55],
    ["23%", "69%", "2.5s", 0.75],
    ["31%", "19%", "0.6s", 0.5],
    ["39%", "82%", "1.8s", 0.7],
    ["48%", "22%", "2.8s", 0.55],
    ["57%", "78%", "0.9s", 0.7],
    ["66%", "31%", "2.2s", 0.5],
    ["74%", "71%", "1.1s", 0.75],
    ["84%", "22%", "2.9s", 0.55],
    ["91%", "76%", "0.4s", 0.8],
    ["88%", "48%", "1.9s", 0.5],
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
        <div
          className="jsm-background"
          role="presentation"
          style={{ backgroundImage: 'url("/jubasquare-maintenance.webp")' }}
        />
        <div className="jsm-soft-glow" />
        <div className="jsm-orbit" />
        <div className="jsm-orbit jsm-orbit--second" />
        <span className="jsm-dot jsm-dot--one" />
        <span className="jsm-dot jsm-dot--blue jsm-dot--two" />
        <span className="jsm-dot jsm-dot--three" />
        {particles.map(([x, y, d, s], i) => (
          <span
            key={i}
            className="jsm-particle"
            style={{ "--x": x, "--y": y, "--d": d, "--s": s }}
          />
        ))}
        <div className="jsm-bottom-wave" />
        <div className="jsm-light-sweep" />

        {/* Accessible textual fallback (visually hidden for AT users) */}
        <div className="jsm-sr-only">
          JubaSquare is under maintenance. We&apos;ll be back shortly.
        </div>
      </main>
    </>
  );
}
