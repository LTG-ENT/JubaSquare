import LegalLayout from "@/pages/legal/LegalLayout";
import { Mail, Phone, MapPin } from "lucide-react";

export default function Contact() {
  return (
    <LegalLayout title="Contact us" subtitle="Support & enquiries">
      <p>We'd love to hear from you. Whether you have a question about an order, a shop, a delivery or something else — reach us through any of the channels below.</p>
      <div className="grid sm:grid-cols-3 gap-4 mt-6 not-prose">
        <div className="flex flex-col items-start gap-2 p-5 rounded-2xl border border-[var(--js-border)] bg-[var(--js-bg)]">
          <Mail className="w-5 h-5 text-[#C84B31]" />
          <p className="text-xs font-bold uppercase tracking-wider text-[var(--js-text-secondary)]">Email</p>
          <a href="mailto:ltg-general-trading@hotmail.com" className="text-sm font-semibold text-[var(--js-text)] break-all">ltg-general-trading@hotmail.com</a>
        </div>
        <div className="flex flex-col items-start gap-2 p-5 rounded-2xl border border-[var(--js-border)] bg-[var(--js-bg)]">
          <Phone className="w-5 h-5 text-[#C84B31]" />
          <p className="text-xs font-bold uppercase tracking-wider text-[var(--js-text-secondary)]">Phone</p>
          <p className="text-sm font-semibold text-[var(--js-text)]">+211 9XX XXX XXX</p>
        </div>
        <div className="flex flex-col items-start gap-2 p-5 rounded-2xl border border-[var(--js-border)] bg-[var(--js-bg)]">
          <MapPin className="w-5 h-5 text-[#C84B31]" />
          <p className="text-xs font-bold uppercase tracking-wider text-[var(--js-text-secondary)]">Location</p>
          <p className="text-sm font-semibold text-[var(--js-text)]">Juba, South Sudan</p>
        </div>
      </div>
      <h2 className="font-display font-bold text-xl mt-8 mb-2">Business hours</h2>
      <p>Mon–Sat: 8:00 AM – 8:00 PM<br/>Sunday: 10:00 AM – 6:00 PM</p>
      <h2 className="font-display font-bold text-xl mt-6 mb-2">Selling on JubaSquare</h2>
      <p>To open a shop, sign up with a seller account, create your shop profile and submit it for verification. We usually review new shops within 1–2 business days.</p>
    </LegalLayout>
  );
}
