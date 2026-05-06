"""
Default content for site-wide editable config (currently: footer).
Used by `seed_production()` on first startup ONLY.
"""

FOOTER_DEFAULT = {
    "id": "footer",

    # Brand block (left column)
    "tagline": "Juba's marketplace for retail, wholesale and food delivery — built for South Sudan.",

    # Social links (empty string = hide the icon)
    "social_facebook": "https://facebook.com/",
    "social_instagram": "https://instagram.com/",
    "social_twitter": "https://twitter.com/",

    # Shop column
    "shop_title": "Shop",
    "shop_links": [
        {"label": "Marketplace", "url": "/marketplace"},
        {"label": "All Shops", "url": "/shops"},
        {"label": "Wholesale", "url": "/marketplace?view=wholesale"},
        {"label": "Food & Restaurants", "url": "/restaurants"},
    ],

    # Company column
    "company_title": "Company",
    "company_links": [
        {"label": "About", "url": "/about"},
        {"label": "Contact", "url": "/contact"},
        {"label": "Become a seller", "url": "/signup"},
    ],

    # Legal column (rendered just under company column)
    "legal_title": "Legal",
    "legal_links": [
        {"label": "Terms of Service", "url": "/terms"},
        {"label": "Privacy Policy", "url": "/privacy"},
        {"label": "Return Policy", "url": "/returns"},
    ],

    # Contact column
    "contact_title": "Get in touch",
    "contact_email": "ltg-general-trading@hotmail.com",
    "contact_phone": "+211 9XX XXX XXX",
    "contact_location": "Juba, South Sudan 🇸🇸",

    # Bottom bar
    "copyright_text": "© {year} L.T.G General Trading. All rights reserved.",
    "tagline_bottom": "Built with ❤ for Juba — Cash on Delivery supported.",
}
