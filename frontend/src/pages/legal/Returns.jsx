import DynamicLegalPage from "@/pages/legal/DynamicLegalPage";
import LegalLayout from "@/pages/legal/LegalLayout";

function ReturnsFallback() {
  return (
    <LegalLayout title="Return & Refund Policy" subtitle="Legal">
      <p>We want you to love what you get on JubaSquare. Here's what to do if something goes wrong with an order.</p>
      <h2 className="font-display font-bold text-xl mt-6 mb-2">Contact</h2>
      <p>Return issues? Email <a href="mailto:ltg-general-trading@hotmail.com" className="text-[#C84B31] font-semibold">ltg-general-trading@hotmail.com</a> with your order ID.</p>
    </LegalLayout>
  );
}

export default function Returns() {
  return <DynamicLegalPage slug="returns" fallback={<ReturnsFallback />} />;
}
