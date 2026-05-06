import DynamicLegalPage from "@/pages/legal/DynamicLegalPage";
import LegalLayout from "@/pages/legal/LegalLayout";

function ContactFallback() {
  return (
    <LegalLayout title="Contact us" subtitle="Support & enquiries">
      <p>Email us at <a href="mailto:ltg-general-trading@hotmail.com" className="text-[#C84B31] font-semibold">ltg-general-trading@hotmail.com</a>.</p>
    </LegalLayout>
  );
}

export default function Contact() {
  return <DynamicLegalPage slug="contact" fallback={<ContactFallback />} />;
}
