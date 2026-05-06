import LegalLayout from "@/pages/legal/LegalLayout";

export default function Terms() {
  return (
    <LegalLayout title="Terms of Service" subtitle="Legal">
      <p>These Terms govern your use of the JubaSquare platform, operated by L.T.G General Trading ("we", "us"). By using JubaSquare you agree to these Terms.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">1. Your account</h2>
      <p>You must be at least 18 years old to create an account. You are responsible for keeping your password secure and for all activity on your account. You must verify your email address before placing orders or selling.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">2. Role of JubaSquare</h2>
      <p>JubaSquare is a marketplace that connects customers with independent shops and restaurants. We are not the seller of items listed by third-party shops and we do not own their inventory. Each seller is responsible for accuracy of listings, quality of goods, and fulfilment.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">3. Orders and payment</h2>
      <p>All orders are currently paid via <strong>Cash on Delivery</strong>. When you place an order, you enter into a sales contract with the seller(s) of that item. JubaSquare charges sellers a commission on completed orders.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">4. Delivery</h2>
      <p>Delivery fees are set by each shop and shown at checkout before you confirm your order. Delivery times are estimates; actual delivery may be affected by traffic, weather and other factors.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">5. Seller obligations</h2>
      <p>Sellers must (a) only list goods they are authorised to sell, (b) describe items accurately, (c) keep stock information up to date, and (d) fulfil orders in a timely manner. JubaSquare reserves the right to suspend or remove sellers who violate these Terms.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">6. Prohibited items</h2>
      <p>You may not list, buy or facilitate the sale of illegal items, counterfeit goods, weapons, drugs, stolen property, or any item restricted by South Sudanese law.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">7. Refunds & returns</h2>
      <p>See our separate <a href="/returns" className="text-[#C84B31] font-semibold">Return Policy</a> for details.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">8. Limitation of liability</h2>
      <p>To the maximum extent permitted by law, JubaSquare is not liable for indirect, incidental or consequential damages arising from your use of the platform or purchases made through it.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">9. Changes</h2>
      <p>We may update these Terms from time to time. We will notify users of significant changes by email or on the platform.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">10. Contact</h2>
      <p>Questions? Reach us at <a href="mailto:ltg-general-trading@hotmail.com" className="text-[#C84B31] font-semibold">ltg-general-trading@hotmail.com</a>.</p>
    </LegalLayout>
  );
}
