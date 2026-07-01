import { useEffect, useState } from "react";
import { Joyride, STATUS, EVENTS } from "react-joyride";
import { useTranslation } from "react-i18next";
import api from "@/lib/api";

/**
 * Interactive Seller Dashboard tour (react-joyride).
 * Controlled from the parent via the `run` prop; when the tour finishes or
 * the seller closes it we notify the backend so it isn't shown again on
 * subsequent visits (unless explicitly triggered from the guide card).
 */
export default function SellerDashboardTour({ run, onFinish }) {
  const { t } = useTranslation();
  const [ready, setReady] = useState(false);

  // Delay start slightly so DOM targets exist (tabs render after data load).
  useEffect(() => {
    if (!run) { setReady(false); return; }
    const timer = setTimeout(() => setReady(true), 250);
    return () => clearTimeout(timer);
  }, [run]);

  const steps = [
    {
      target: '[data-testid="seller-onboarding-card"]',
      content: t("tour.onboarding"),
      placement: "bottom",
      skipBeacon: true,
    },
    {
      target: '[data-testid="seller-tab-shops"]',
      content: t("tour.shopsTab"),
      placement: "bottom",
      skipBeacon: true,
    },
    {
      target: '[data-testid="seller-tab-products"]',
      content: t("tour.productsTab"),
      placement: "bottom",
      skipBeacon: true,
    },
    {
      target: '[data-testid="seller-tab-analytics"]',
      content: t("tour.analyticsTab"),
      placement: "bottom",
      skipBeacon: true,
    },
    {
      target: '[data-testid="seller-tab-wallet"]',
      content: t("tour.walletTab"),
      placement: "bottom",
      skipBeacon: true,
    },
    {
      target: '[data-testid="seller-tab-messages"]',
      content: t("tour.messagesTab"),
      placement: "bottom",
      skipBeacon: true,
    },
    {
      target: '[data-testid="seller-tab-settings"]',
      content: t("tour.settingsTab"),
      placement: "bottom",
      skipBeacon: true,
    },
  ];

  const handleCallback = async (data) => {
    const { status, type } = data;
    const done = [STATUS.FINISHED, STATUS.SKIPPED].includes(status);
    const closed = type === EVENTS.TOUR_END || done;
    if (closed) {
      try { await api.post("/seller/onboarding/complete-tour"); } catch (_) { /* silent */ }
      onFinish && onFinish();
    }
  };

  if (!ready) return null;

  return (
    <Joyride
      steps={steps}
      run={run}
      continuous
      showSkipButton
      showProgress
      disableScrolling={false}
      styles={{
        options: {
          primaryColor: "#C84B31",
          textColor: "#1A1A1A",
          backgroundColor: "#FFFFFF",
          arrowColor: "#FFFFFF",
          zIndex: 10001,
        },
        buttonNext: { borderRadius: 999, padding: "6px 16px", fontWeight: 600, fontSize: 13 },
        buttonBack: { color: "#5C5C5C", fontSize: 13 },
        buttonSkip: { color: "#5C5C5C", fontSize: 13 },
      }}
      locale={{
        back: t("tour.back"),
        close: t("tour.close"),
        last: t("tour.finish"),
        next: t("tour.next"),
        skip: t("tour.skip"),
      }}
      callback={handleCallback}
    />
  );
}
