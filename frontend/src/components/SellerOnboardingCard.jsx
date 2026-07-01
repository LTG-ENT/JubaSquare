import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Circle, ArrowRight, X, GraduationCap, Sparkles } from "lucide-react";
import api from "@/lib/api";
import { SELLER_STEPS } from "@/lib/sellerSteps";

/**
 * Compact onboarding progress card shown at the top of the Seller Dashboard.
 * - Progress bar (X of 9 steps)
 * - Next 3 pending steps as quick CTAs
 * - "Open full guide" link → /seller/guide
 * - Dismissable (per-seller, persists via backend `wizard_dismissed` flag —
 *   but the card itself is shown as long as progress < 100%; we hide it
 *   only when the seller reaches 100% or explicitly closes it locally)
 */
export default function SellerOnboardingCard({ onStartTour }) {
  const { t } = useTranslation();
  const [progress, setProgress] = useState(null);
  const [locallyHidden, setLocallyHidden] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.get("/seller/onboarding/progress")
      .then((r) => { if (!cancelled) setProgress(r.data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!progress) return null;
  // Auto-hide once the seller has finished everything.
  if (progress.percent >= 100) return null;
  if (locallyHidden) return null;

  const pendingSteps = SELLER_STEPS
    .filter((s) => !progress.steps.find((ps) => ps.id === s.id && ps.done))
    .slice(0, 3);

  return (
    <div
      data-testid="seller-onboarding-card"
      className="mt-6 rounded-2xl border border-[#E2E2D9] bg-white overflow-hidden"
    >
      {/* Header */}
      <div className="p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center gap-4 bg-gradient-to-r from-[#FFF6EE] via-white to-[#F0F7FF]">
        <div className="w-12 h-12 rounded-2xl bg-[#C84B31] text-white flex items-center justify-center shrink-0">
          <GraduationCap className="w-6 h-6" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] uppercase tracking-[0.2em] text-[#C84B31] font-bold">
            {t("guide.card.eyebrow")}
          </p>
          <h3 className="font-display font-bold text-lg text-[#1A1A1A]">
            {t("guide.card.title")}
          </h3>
          <p className="text-xs text-[#5C5C5C] mt-0.5">
            {t("guide.card.subtitle", { done: progress.completed_count, total: progress.total_count })}
          </p>
        </div>
        <button
          onClick={() => setLocallyHidden(true)}
          data-testid="seller-onboarding-close"
          aria-label="Close"
          className="w-8 h-8 rounded-full hover:bg-[#F5F5EE] flex items-center justify-center text-[#5C5C5C]"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Progress bar */}
      <div className="px-5 sm:px-6">
        <div className="h-2 w-full bg-[#F0F0E8] rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-[#C84B31] to-[#E9873C] transition-all duration-700"
            style={{ width: `${progress.percent}%` }}
            data-testid="seller-onboarding-progress-bar"
          />
        </div>
        <div className="flex items-center justify-between mt-1.5 text-[11px] text-[#5C5C5C] font-semibold">
          <span data-testid="seller-onboarding-percent">{progress.percent}%</span>
          {progress.badge_earned && (
            <span className="inline-flex items-center gap-1 text-[#2E7D32]" data-testid="seller-onboarding-badge-earned">
              <Sparkles className="w-3.5 h-3.5" /> {t("guide.card.badgeEarned")}
            </span>
          )}
        </div>
      </div>

      {/* Next 3 pending steps */}
      <div className="p-5 sm:p-6 pt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
        {pendingSteps.map((s) => {
          const Icon = s.icon;
          return (
            <Link
              key={s.id}
              to={s.to}
              data-testid={`seller-onboarding-step-${s.id}`}
              className="group border border-[#E2E2D9] rounded-xl p-3.5 hover:border-[#C84B31] hover:shadow-sm transition"
            >
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-[#FFF3E9] flex items-center justify-center text-[#C84B31] shrink-0">
                  <Icon className="w-4.5 h-4.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-display font-bold text-sm text-[#1A1A1A] truncate">
                    {t(s.titleKey)}
                  </p>
                  <p className="text-[11px] text-[#5C5C5C] line-clamp-2 mt-0.5">
                    {t(s.descKey)}
                  </p>
                </div>
                <ArrowRight className="w-4 h-4 text-[#5C5C5C] group-hover:text-[#C84B31] shrink-0 mt-1" />
              </div>
            </Link>
          );
        })}
      </div>

      {/* Actions */}
      <div className="px-5 sm:px-6 py-4 border-t border-[#F0F0E8] flex flex-wrap gap-2 items-center bg-[#FAFAF6]">
        <Link
          to="/seller/guide"
          data-testid="seller-onboarding-open-guide"
          className="bg-[#1A1A1A] hover:bg-black text-white text-xs font-semibold px-4 py-2 rounded-full inline-flex items-center gap-1.5"
        >
          {t("guide.card.openGuide")} <ArrowRight className="w-3.5 h-3.5" />
        </Link>
        <button
          type="button"
          onClick={onStartTour}
          data-testid="seller-onboarding-start-tour"
          className="text-[#C84B31] hover:text-[#A83A24] text-xs font-semibold px-4 py-2 rounded-full inline-flex items-center gap-1.5"
        >
          {t("guide.card.showAround")}
        </button>
      </div>
    </div>
  );
}
