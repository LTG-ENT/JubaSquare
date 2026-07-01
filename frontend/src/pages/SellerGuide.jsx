import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CheckCircle2, Circle, ArrowRight, ArrowLeft, Sparkles, GraduationCap } from "lucide-react";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import api from "@/lib/api";
import { SELLER_STEPS } from "@/lib/sellerSteps";

/**
 * Full-page seller onboarding guide.
 * Shows all 9 steps with title, description, CTA button, and a check button
 * for steps that need to be manually marked complete.
 */
export default function SellerGuide() {
  const { t } = useTranslation();
  const [progress, setProgress] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const r = await api.get("/seller/onboarding/progress");
      setProgress(r.data);
    } catch (_) { /* silent */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const stepStatus = useCallback((id) => {
    if (!progress) return { done: false, auto: false };
    return progress.steps.find((s) => s.id === id) || { done: false, auto: false };
  }, [progress]);

  const toggle = async (step) => {
    const st = stepStatus(step.id);
    if (st.auto) {
      // Auto-detected steps can't be toggled manually — they update when
      // the seller does the real action (add product, create shop, ...).
      toast.info(t("guide.autoInfo"));
      return;
    }
    try {
      const url = st.done
        ? "/seller/onboarding/uncheck-step"
        : "/seller/onboarding/complete-step";
      const r = await api.post(url, { step_id: step.id });
      setProgress(r.data);
      toast.success(st.done ? t("guide.marked.pending") : t("guide.marked.done"));
    } catch (_) {
      toast.error(t("guide.markFailed"));
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F9F9F6]">
      <Header />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <Link
          to="/seller"
          className="inline-flex items-center gap-1.5 text-[#5C5C5C] hover:text-[#1A1A1A] text-sm mb-4"
          data-testid="seller-guide-back"
        >
          <ArrowLeft className="w-4 h-4" /> {t("guide.backToDashboard")}
        </Link>

        {/* Hero */}
        <div className="rounded-3xl bg-white border border-[#E2E2D9] overflow-hidden">
          <div className="p-6 sm:p-10 bg-gradient-to-br from-[#FFF6EE] via-white to-[#F0F7FF]">
            <div className="inline-flex items-center gap-2 rounded-full bg-[#1A1A1A] text-white text-[10px] uppercase tracking-[0.2em] font-bold px-3 py-1.5">
              <GraduationCap className="w-3.5 h-3.5" /> {t("guide.hero.eyebrow")}
            </div>
            <h1 className="font-display font-bold text-3xl sm:text-5xl text-[#1A1A1A] mt-3 leading-tight" data-testid="seller-guide-title">
              {t("guide.hero.title")}
            </h1>
            <p className="text-[#5C5C5C] mt-3 max-w-2xl text-sm sm:text-base">
              {t("guide.hero.subtitle")}
            </p>

            {progress && (
              <div className="mt-6 max-w-md">
                <div className="flex items-center justify-between text-xs font-semibold text-[#1A1A1A] mb-1.5">
                  <span data-testid="seller-guide-progress-text">
                    {t("guide.progress.count", { done: progress.completed_count, total: progress.total_count })}
                  </span>
                  <span>{progress.percent}%</span>
                </div>
                <div className="h-2.5 w-full bg-[#F0F0E8] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[#C84B31] to-[#E9873C] transition-all duration-700"
                    style={{ width: `${progress.percent}%` }}
                    data-testid="seller-guide-progress-bar"
                  />
                </div>
                {progress.badge_earned && (
                  <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-[#E8F5E9] border border-[#C8E6C9] text-[#2E7D32] text-xs font-bold px-3 py-1.5" data-testid="seller-guide-badge">
                    <Sparkles className="w-3.5 h-3.5" /> {t("guide.hero.badgeEarned")}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Steps */}
        <div className="mt-8 space-y-4">
          {SELLER_STEPS.map((step, idx) => {
            const Icon = step.icon;
            const st = stepStatus(step.id);
            return (
              <div
                key={step.id}
                data-testid={`guide-step-${step.id}`}
                className={`rounded-2xl border p-5 sm:p-6 bg-white transition ${
                  st.done ? "border-[#C8E6C9] bg-[#F5FBF5]" : "border-[#E2E2D9]"
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                  <button
                    type="button"
                    onClick={() => toggle(step)}
                    data-testid={`guide-step-${step.id}-toggle`}
                    aria-label={st.done ? "Mark as pending" : "Mark as done"}
                    className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 transition ${
                      st.done
                        ? "bg-[#2E7D32] text-white"
                        : "bg-[#F0F0E8] text-[#5C5C5C] hover:bg-[#FFE4D3] hover:text-[#C84B31]"
                    }`}
                  >
                    {st.done ? <CheckCircle2 className="w-5 h-5" /> : <Circle className="w-5 h-5" />}
                  </button>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold">
                        {t("guide.stepLabel", { n: idx + 1 })}
                      </span>
                      {step.core && (
                        <span className="text-[9px] uppercase tracking-[0.15em] bg-[#C84B31] text-white px-2 py-0.5 rounded-full font-bold">
                          {t("guide.core")}
                        </span>
                      )}
                      {st.auto && (
                        <span className="text-[9px] uppercase tracking-[0.15em] bg-[#F0F0E8] text-[#5C5C5C] px-2 py-0.5 rounded-full font-bold">
                          {t("guide.autoBadge")}
                        </span>
                      )}
                    </div>
                    <div className="flex items-start gap-2 mt-1">
                      <Icon className="w-5 h-5 text-[#C84B31] shrink-0 mt-0.5" />
                      <h3 className="font-display font-bold text-lg sm:text-xl text-[#1A1A1A]">
                        {t(step.titleKey)}
                      </h3>
                    </div>
                    <p className="text-sm text-[#5C5C5C] mt-2 whitespace-pre-line">
                      {t(step.descKey)}
                    </p>
                    <div className="mt-3">
                      <Link
                        to={step.to}
                        data-testid={`guide-step-${step.id}-cta`}
                        className="inline-flex items-center gap-1.5 text-[#C84B31] hover:text-[#A83A24] text-sm font-semibold"
                      >
                        {t(step.actionLabelKey)} <ArrowRight className="w-4 h-4" />
                      </Link>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer note */}
        <div className="mt-10 rounded-2xl bg-white border border-[#E2E2D9] p-6 text-center">
          <p className="text-sm text-[#5C5C5C]">
            {t("guide.footerHelp")}
          </p>
          <Link
            to="/contact"
            className="mt-2 inline-flex items-center gap-1.5 text-[#C84B31] hover:text-[#A83A24] text-sm font-semibold"
          >
            {t("guide.footerContact")} <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
      <Footer />
    </div>
  );
}
