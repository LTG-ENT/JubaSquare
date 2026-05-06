import LegalLayout from "@/pages/legal/LegalLayout";

export default function Privacy() {
  return (
    <LegalLayout title="Privacy Policy" subtitle="Legal">
      <p>This policy explains what data JubaSquare collects, why, and how we protect it.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">What we collect</h2>
      <ul className="list-disc pl-5 space-y-1">
        <li><strong>Account info:</strong> name, email, phone, password (stored as a secure hash).</li>
        <li><strong>Order info:</strong> items ordered, delivery address and area, phone number, order notes.</li>
        <li><strong>Shop info (sellers):</strong> shop name, description, images, delivery settings.</li>
        <li><strong>Usage data:</strong> pages visited, device information, for analytics and security.</li>
      </ul>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">How we use it</h2>
      <ul className="list-disc pl-5 space-y-1">
        <li>To operate the marketplace — showing shops, processing orders, notifying sellers.</li>
        <li>To send transactional emails (verification, password reset, order confirmations).</li>
        <li>To improve the platform and investigate fraud or abuse.</li>
      </ul>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Who we share data with</h2>
      <p>We share your order delivery details (name, phone, address) with the seller fulfilling your order, so they can prepare and deliver it. We do not sell your personal data to advertisers.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Email</h2>
      <p>We use Resend (a third-party email provider) to send transactional emails. By using JubaSquare you consent to receiving these emails.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Data retention</h2>
      <p>We keep your account data while your account is active. You can request deletion by emailing us. We may keep some order records for legal and accounting purposes.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Your rights</h2>
      <p>You can view and update your profile in Settings. To request data export or deletion, contact <a href="mailto:ltg-general-trading@hotmail.com" className="text-[#C84B31] font-semibold">ltg-general-trading@hotmail.com</a>.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Security</h2>
      <p>We use industry-standard practices: HTTPS everywhere, hashed passwords (bcrypt), access-controlled databases. No online service is 100% secure, so use a strong unique password.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Contact</h2>
      <p>Questions about privacy? Email <a href="mailto:ltg-general-trading@hotmail.com" className="text-[#C84B31] font-semibold">ltg-general-trading@hotmail.com</a>.</p>
    </LegalLayout>
  );
}
