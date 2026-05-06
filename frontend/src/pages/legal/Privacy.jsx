import DynamicLegalPage from "@/pages/legal/DynamicLegalPage";
import LegalLayout from "@/pages/legal/LegalLayout";

function PrivacyFallback() {
  return (
    <LegalLayout title="Privacy Policy" subtitle="Legal">
      <p>This policy explains what data JubaSquare collects, why, and how we protect it.</p>
      <h2 className="font-display font-bold text-xl mt-6 mb-2">Contact</h2>
      <p>Questions about privacy? Email <a href="mailto:ltg-general-trading@hotmail.com" className="text-[#C84B31] font-semibold">ltg-general-trading@hotmail.com</a>.</p>
    </LegalLayout>
  );
}

export default function Privacy() {
  return <DynamicLegalPage slug="privacy" fallback={<PrivacyFallback />} />;
}
