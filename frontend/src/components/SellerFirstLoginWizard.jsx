import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { X, ArrowRight, ArrowLeft, CheckCircle2, Sparkles } from "lucide-react";
import api from "@/lib/api";
import { SELLER_STEPS, WIZARD_STEP_IDS } from "@/lib/sellerSteps";

/**
 * First-login onboarding wizard for sellers.
 * Renders a 3-slide modal (Setup shop → Add first product → Configure delivery).
 * Auto-shows once when a seller has NOT dismissed the wizard AND has NOT
 * completed all 3 wizard steps. Persists the dismissal on the server.
 */
export default function SellerFirstLoginWizard() {
  const { t } = useTranslation();
  const [progress, setProgress] = useState(null);
  const [open, setOpen] = useState(false);
  const [idx, setIdx] = useState(0);

  const wizardSteps = WIZARD_STEP_IDS
    .map((id) => SELLER_STEPS.find((s) => s.id === id))
    .filter(Boolean);

  useEffect(() => {
    let cancelled = false;
    api.get("/seller/onboarding/progress")
      .then((r) => {
        if (cancelled) return;
        setProgress(r.data);
        const wizardComplete = WIZARD_STEP_IDS.every(
          (id) => r.data.steps.find((s) => s.id === id && s.done)
        );
        if (!r.data.wizard_dismissed && !wizardComplete) {
          setOpen(true);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const dismiss = async (permanent = true) => {
    setOpen(false);
    if (permanent) {
      try { await api.post("/seller/onboarding/dismiss-wizard"); } catch (_) { /* silent */ }
    }
  };

  if (!open || !progress) return null;

  const step = wizardSteps[idx];
  if (!step) { dismiss(true); return null; }
  const Icon = step.icon;
  const done = !!progress.steps.find((s) => s.id === step.id && s.done);

  return (
    <div
      className="fixed inset-0 z-[9998] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      data-testid="seller-wizard-overlay"
      onClick={() => dismiss(true)}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        data-testid="seller-wizard"
        className="w-full max-w-lg bg-white rounded-3xl shadow-2xl overflow-hidden"
      >
        <div className="relative p-6 sm:p-8 bg-gradient-to-br from-[#FFF6EE] via-white to-[#F0F7FF]">
          <button
            onClick={() => dismiss(true)}
            data-testid="seller-wizard-close"
            aria-label="Close"
            className="absolute top-3 right-3 w-9 h-9 rounded-full hover:bg-white/70 flex items-center justify-center text-[#5C5C5C]"
          >
            <X className="w-4 h-4" />
          </button>

          <div className="text-[10px] uppercase tracking-[0.2em] text-[#C84B31] font-bold flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" /> {t("wizard.welcomeEyebrow")}
          </div>
          <h2 className="font-display font-bold text-2xl sm:text-3xl text-[#1A1A1A] mt-2">
            {t("wizard.welcomeTitle")}
          </h2>
          <p className="text-sm text-[#5C5C5C] mt-1">
            {t("wizard.welcomeSubtitle")}
          </p>

          {/* Step dots */}
          <div className="mt-5 flex items-center gap-1.5">
            {wizardSteps.map((_, i) => (
              <div
                key={i}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  i === idx ? "bg-[#C84B31] w-8" : "bg-[#F0D5C7] w-1.5"
                }`}
              />
            ))}
          </div>
        </div>

        <div className="p-6 sm:p-8">
          <div className="flex items-start gap-4">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
              done ? "bg-[#2E7D32] text-white" : "bg-[#FFE4D3] text-[#C84B31]"
            }`}>
              {done ? <CheckCircle2 className="w-6 h-6" /> : <Icon className="w-6 h-6" />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold">
                {t("wizard.stepXofY", { current: idx + 1, total: wizardSteps.length })}
              </p>
              <h3 className="font-display font-bold text-xl text-[#1A1A1A] mt-1">
                {t(step.titleKey)}
              </h3>
              <p className="text-sm text-[#5C5C5C] mt-2 whitespace-pre-line">
                {t(step.descKey)}
              </p>
              <Link
                to={step.to}
                onClick={() => dismiss(true)}
                data-testid={`seller-wizard-step-${step.id}-cta`}
                className="mt-4 inline-flex items-center gap-1.5 bg-[#1A1A1A] hover:bg-black text-white text-sm font-semibold px-5 py-2.5 rounded-full"
              >
                {t(step.actionLabelKey)} <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>

        <div className="px-6 sm:px-8 pb-6 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setIdx((v) => Math.max(0, v - 1))}
            disabled={idx === 0}
            data-testid="seller-wizard-prev"
            className="inline-flex items-center gap-1.5 text-[#5C5C5C] hover:text-[#1A1A1A] text-sm font-semibold disabled:opacity-30"
          >
            <ArrowLeft className="w-4 h-4" /> {t("wizard.back")}
          </button>
          {idx < wizardSteps.length - 1 ? (
            <button
              type="button"
              onClick={() => setIdx((v) => v + 1)}
              data-testid="seller-wizard-next"
              className="inline-flex items-center gap-1.5 bg-[#C84B31] hover:bg-[#A83A24] text-white text-sm font-semibold px-5 py-2 rounded-full"
            >
              {t("wizard.next")} <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => dismiss(true)}
              data-testid="seller-wizard-finish"
              className="inline-flex items-center gap-1.5 bg-[#C84B31] hover:bg-[#A83A24] text-white text-sm font-semibold px-5 py-2 rounded-full"
            >
              {t("wizard.finish")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
