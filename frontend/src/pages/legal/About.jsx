import DynamicLegalPage from "@/pages/legal/DynamicLegalPage";
import LegalLayout from "@/pages/legal/LegalLayout";

function AboutFallback() {
  return (
    <LegalLayout title="About JubaSquare" subtitle="Our story">
      <p>JubaSquare is South Sudan's online marketplace.</p>
    </LegalLayout>
  );
}

export default function About() {
  return <DynamicLegalPage slug="about" fallback={<AboutFallback />} />;
}
