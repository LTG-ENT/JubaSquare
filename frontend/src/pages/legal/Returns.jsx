import LegalLayout from "@/pages/legal/LegalLayout";

export default function Returns() {
  return (
    <LegalLayout title="Return & Refund Policy" subtitle="Legal">
      <p>We want you to love what you get on JubaSquare. Here's what to do if something goes wrong with an order.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">At the point of delivery</h2>
      <p>Inspect your order when it arrives. If an item is damaged, incorrect, or missing, reject the item and contact the shop or JubaSquare support immediately before paying.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Returns window</h2>
      <p>Most items can be returned within <strong>7 days</strong> of delivery if they are unused, in original packaging and in re-sellable condition. Some categories are non-returnable (see below).</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Non-returnable items</h2>
      <ul className="list-disc pl-5 space-y-1">
        <li>Perishable food and restaurant meals</li>
        <li>Cosmetics and personal care items once opened</li>
        <li>Custom-made or personalised items</li>
        <li>Underwear, swimwear</li>
      </ul>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">How to request a return</h2>
      <ol className="list-decimal pl-5 space-y-1">
        <li>Open the order in your Orders page.</li>
        <li>Contact the shop directly, or email support with the order ID.</li>
        <li>Arrange pickup/drop-off with the shop.</li>
        <li>Once the shop confirms the return, refunds are processed within 5 business days (typically as cash, since payment is Cash on Delivery).</li>
      </ol>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Damaged or defective items</h2>
      <p>If you receive a damaged or defective item, you are entitled to a replacement or full refund. Contact us within 48 hours of delivery with photos of the issue.</p>

      <h2 className="font-display font-bold text-xl mt-6 mb-2">Contact</h2>
      <p>Return issues? Email <a href="mailto:ltg-general-trading@hotmail.com" className="text-[#C84B31] font-semibold">ltg-general-trading@hotmail.com</a> with your order ID.</p>
    </LegalLayout>
  );
}
