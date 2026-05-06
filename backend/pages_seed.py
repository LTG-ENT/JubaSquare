"""
Default content for editable CMS pages: Terms, Privacy, Returns, About, Contact.

This is used by `seed_production()` on first startup ONLY — once a page
exists in the `pages` collection, the default is NEVER reapplied.
"""

PAGES_DEFAULT = {
    # ----- Terms of Service -----
    "terms": {
        "slug": "terms",
        "title": "Terms of Service",
        "subtitle": "Legal",
        "body_html": """<p>These Terms govern your use of the JubaSquare platform, operated by L.T.G General Trading ("we", "us"). By using JubaSquare you agree to these Terms.</p>

<h2>1. Your account</h2>
<p>You must be at least 18 years old to create an account. You are responsible for keeping your password secure and for all activity on your account. You must verify your email address before placing orders or selling.</p>

<h2>2. Role of JubaSquare</h2>
<p>JubaSquare is a marketplace that connects customers with independent shops and restaurants. We are not the seller of items listed by third-party shops and we do not own their inventory. Each seller is responsible for accuracy of listings, quality of goods, and fulfilment.</p>

<h2>3. Orders and payment</h2>
<p>All orders are currently paid via <strong>Cash on Delivery</strong>. When you place an order, you enter into a sales contract with the seller(s) of that item. JubaSquare charges sellers a commission on completed orders.</p>

<h2>4. Delivery</h2>
<p>Delivery fees are set by each shop and shown at checkout before you confirm your order. Delivery times are estimates; actual delivery may be affected by traffic, weather and other factors.</p>

<h2>5. Seller obligations</h2>
<p>Sellers must (a) only list goods they are authorised to sell, (b) describe items accurately, (c) keep stock information up to date, and (d) fulfil orders in a timely manner. JubaSquare reserves the right to suspend or remove sellers who violate these Terms.</p>

<h2>6. Prohibited items</h2>
<p>You may not list, buy or facilitate the sale of illegal items, counterfeit goods, weapons, drugs, stolen property, or any item restricted by South Sudanese law.</p>

<h2>7. Refunds &amp; returns</h2>
<p>See our separate <a href="/returns">Return Policy</a> for details.</p>

<h2>8. Limitation of liability</h2>
<p>To the maximum extent permitted by law, JubaSquare is not liable for indirect, incidental or consequential damages arising from your use of the platform or purchases made through it.</p>

<h2>9. Changes</h2>
<p>We may update these Terms from time to time. We will notify users of significant changes by email or on the platform.</p>

<h2>10. Contact</h2>
<p>Questions? Reach us at <a href="mailto:ltg-general-trading@hotmail.com">ltg-general-trading@hotmail.com</a>.</p>""",
    },

    # ----- Privacy Policy -----
    "privacy": {
        "slug": "privacy",
        "title": "Privacy Policy",
        "subtitle": "Legal",
        "body_html": """<p>This policy explains what data JubaSquare collects, why, and how we protect it.</p>

<h2>What we collect</h2>
<ul>
  <li><strong>Account info:</strong> name, email, phone, password (stored as a secure hash).</li>
  <li><strong>Order info:</strong> items ordered, delivery address and area, phone number, order notes.</li>
  <li><strong>Shop info (sellers):</strong> shop name, description, images, delivery settings.</li>
  <li><strong>Usage data:</strong> pages visited, device information, for analytics and security.</li>
</ul>

<h2>How we use it</h2>
<ul>
  <li>To operate the marketplace — showing shops, processing orders, notifying sellers.</li>
  <li>To send transactional emails (verification, password reset, order confirmations).</li>
  <li>To improve the platform and investigate fraud or abuse.</li>
</ul>

<h2>Who we share data with</h2>
<p>We share your order delivery details (name, phone, address) with the seller fulfilling your order, so they can prepare and deliver it. We do not sell your personal data to advertisers.</p>

<h2>Email</h2>
<p>We use Resend (a third-party email provider) to send transactional emails. By using JubaSquare you consent to receiving these emails.</p>

<h2>Data retention</h2>
<p>We keep your account data while your account is active. You can request deletion by emailing us. We may keep some order records for legal and accounting purposes.</p>

<h2>Your rights</h2>
<p>You can view and update your profile in Settings. To request data export or deletion, contact <a href="mailto:ltg-general-trading@hotmail.com">ltg-general-trading@hotmail.com</a>.</p>

<h2>Security</h2>
<p>We use industry-standard practices: HTTPS everywhere, hashed passwords (bcrypt), access-controlled databases. No online service is 100% secure, so use a strong unique password.</p>

<h2>Contact</h2>
<p>Questions about privacy? Email <a href="mailto:ltg-general-trading@hotmail.com">ltg-general-trading@hotmail.com</a>.</p>""",
    },

    # ----- Return & Refund Policy -----
    "returns": {
        "slug": "returns",
        "title": "Return & Refund Policy",
        "subtitle": "Legal",
        "body_html": """<p>We want you to love what you get on JubaSquare. Here's what to do if something goes wrong with an order.</p>

<h2>At the point of delivery</h2>
<p>Inspect your order when it arrives. If an item is damaged, incorrect, or missing, reject the item and contact the shop or JubaSquare support immediately before paying.</p>

<h2>Returns window</h2>
<p>Most items can be returned within <strong>7 days</strong> of delivery if they are unused, in original packaging and in re-sellable condition. Some categories are non-returnable (see below).</p>

<h2>Non-returnable items</h2>
<ul>
  <li>Perishable food and restaurant meals</li>
  <li>Cosmetics and personal care items once opened</li>
  <li>Custom-made or personalised items</li>
  <li>Underwear, swimwear</li>
</ul>

<h2>How to request a return</h2>
<ol>
  <li>Open the order in your Orders page.</li>
  <li>Contact the shop directly, or email support with the order ID.</li>
  <li>Arrange pickup/drop-off with the shop.</li>
  <li>Once the shop confirms the return, refunds are processed within 5 business days (typically as cash, since payment is Cash on Delivery).</li>
</ol>

<h2>Damaged or defective items</h2>
<p>If you receive a damaged or defective item, you are entitled to a replacement or full refund. Contact us within 48 hours of delivery with photos of the issue.</p>

<h2>Contact</h2>
<p>Return issues? Email <a href="mailto:ltg-general-trading@hotmail.com">ltg-general-trading@hotmail.com</a> with your order ID.</p>""",
    },

    # ----- About -----
    "about": {
        "slug": "about",
        "title": "About JubaSquare",
        "subtitle": "Our story",
        "body_html": """<p>JubaSquare is South Sudan's online marketplace — a single place where shoppers in Juba can buy groceries, electronics, clothing and more from verified local shops, order food from their favourite restaurants, and find bulk wholesale deals — all with local delivery.</p>

<h2>Built for Juba 🇸🇸</h2>
<p>We built JubaSquare to make it easier to support local businesses, shop securely, and get what you need without having to travel across town. Every shop on JubaSquare is reviewed by our team before going live.</p>

<h2>About L.T.G Enterprise</h2>
<p>JubaSquare is a product of <strong>L.T.G General Trading</strong> — a South Sudanese company focused on building modern digital commerce infrastructure for the region.</p>

<h2>What you'll find here</h2>
<ul>
  <li><strong>Retail marketplace</strong> — groceries, fashion, electronics, health &amp; more</li>
  <li><strong>Wholesale bulk deals</strong> — for shop owners, restaurants and businesses</li>
  <li><strong>Food &amp; Restaurants</strong> — order meals for delivery across Juba</li>
  <li><strong>Seller tools</strong> — dashboards, orders, per-shop delivery pricing</li>
</ul>

<p>Want to sell on JubaSquare? <a href="/signup">Create a seller account</a>.</p>""",
    },

    # ----- Contact -----
    "contact": {
        "slug": "contact",
        "title": "Contact us",
        "subtitle": "Support & enquiries",
        "body_html": """<p>We'd love to hear from you. Whether you have a question about an order, a shop, a delivery or something else — reach us through any of the channels above.</p>

<h2>Selling on JubaSquare</h2>
<p>To open a shop, sign up with a seller account, create your shop profile and submit it for verification. We usually review new shops within 1–2 business days.</p>""",
        # structured contact fields (rendered as cards)
        "contact_email": "ltg-general-trading@hotmail.com",
        "contact_phone": "+211 9XX XXX XXX",
        "contact_location": "Juba, South Sudan",
        "business_hours": "Mon–Sat: 8:00 AM – 8:00 PM\nSunday: 10:00 AM – 6:00 PM",
    },
}


PAGE_SLUGS = list(PAGES_DEFAULT.keys())
