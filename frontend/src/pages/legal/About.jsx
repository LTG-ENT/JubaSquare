import LegalLayout from "@/pages/legal/LegalLayout";

export default function About() {
  return (
    <LegalLayout title="About JubaSquare" subtitle="Our story">
      <p>JubaSquare is South Sudan's online marketplace — a single place where shoppers in Juba can buy groceries, electronics, clothing and more from verified local shops, order food from their favourite restaurants, and find bulk wholesale deals — all with local delivery.</p>
      <h2 className="font-display font-bold text-xl mt-6 mb-2">Built for Juba 🇸🇸</h2>
      <p>We built JubaSquare to make it easier to support local businesses, shop securely, and get what you need without having to travel across town. Every shop on JubaSquare is reviewed by our team before going live.</p>
      <h2 className="font-display font-bold text-xl mt-6 mb-2">About L.T.G Enterprise</h2>
      <p>JubaSquare is a product of <strong>L.T.G General Trading</strong> — a South Sudanese company focused on building modern digital commerce infrastructure for the region.</p>
      <h2 className="font-display font-bold text-xl mt-6 mb-2">What you'll find here</h2>
      <ul className="list-disc pl-5 space-y-1">
        <li><strong>Retail marketplace</strong> — groceries, fashion, electronics, health & more</li>
        <li><strong>Wholesale bulk deals</strong> — for shop owners, restaurants and businesses</li>
        <li><strong>Food & Restaurants</strong> — order meals for delivery across Juba</li>
        <li><strong>Seller tools</strong> — dashboards, orders, per-shop delivery pricing</li>
      </ul>
      <p className="mt-6">Want to sell on JubaSquare? <a href="/signup" className="text-[#C84B31] font-semibold hover:underline">Create a seller account</a>.</p>
    </LegalLayout>
  );
}
