import DynamicLegalPage from "@/pages/legal/DynamicLegalPage";
import LegalLayout from "@/pages/legal/LegalLayout";

function TermsFallback() {
  return (
    <LegalLayout title="Terms of Service" subtitle="Legal">
      <p>These Terms govern your use of the JubaSquare platform, operated by L.T.G General Trading ("we", "us"). By using JubaSquare you agree to these Terms.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">1. Your account</h2>
      <p>You must be at least 18 years old to create an account. You are responsible for keeping your password secure and for all activity on your account. You must verify your email address before placing orders or selling.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">2. Role of JubaSquare</h2>
      <p>JubaSquare is a marketplace that connects customers with independent shops and restaurants. We are not the seller of items listed by third-party shops and we do not own their inventory. Each seller is responsible for accuracy of listings, quality of goods, and fulfilment.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">3. Orders and payment</h2>
      <p>All orders are currently paid via <strong>Cash on Delivery</strong>. When you place an order, you enter into a sales contract with the seller(s) of that item. JubaSquare charges sellers a commission on completed orders.</p>
    </LegalLayout>
  );
}

export default function Terms() {
  return <DynamicLegalPage slug="terms" fallback={<TermsFallback />} />;
}
