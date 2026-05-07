# Default category seeds for JubaSquare. Loaded once on first startup
# (idempotent — never overwrites existing categories in the DB).
#
# Structure: { group: [ {name, image_url, children:[{name, image_url}]} ] }
# Groups: retail | wholesale | restaurant

CATEGORY_GROUPS = ["retail", "wholesale", "restaurant"]

CATEGORIES_DEFAULT = {
    "retail": [
        {
            "name": "Groceries",
            "image_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=400&q=80",
            "children": [],
        },
        {
            "name": "Clothing & Fashion",
            "image_url": "https://images.unsplash.com/photo-1757140447782-8503452b2204?w=400&q=80",
            "children": [],
        },
        {
            "name": "Shoes & Bags",
            "image_url": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=400&q=80",
            "children": [],
        },
        {
            "name": "Beauty & Cosmetics",
            "image_url": "https://images.unsplash.com/photo-1522335789203-aaa57d0aacae?w=400&q=80",
            "children": [],
        },
        {
            "name": "Electronics & Accessories",
            "image_url": "https://images.unsplash.com/photo-1761641466573-f240b6e446de?w=400&q=80",
            "children": [],
        },
        {
            "name": "Home Essentials",
            "image_url": "https://images.pexels.com/photos/15108276/pexels-photo-15108276.jpeg?auto=compress&w=400",
            "children": [],
        },
        {
            "name": "Health & Pharmacy",
            "image_url": "https://images.unsplash.com/photo-1646392206581-2527b1cae5cb?w=400&q=80",
            "children": [],
        },
        {
            "name": "Building & Materials",
            "image_url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=400&q=80",
            "children": [],
        },
        {
            "name": "Automotive",
            "image_url": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=400&q=80",
            "children": [],
        },
    ],
    "wholesale": [
        {"name": "Wholesale Food Supply", "image_url": "", "children": []},
        {"name": "Wholesale Electronics", "image_url": "", "children": []},
        {"name": "Wholesale Clothing", "image_url": "", "children": []},
        {"name": "Restaurant Supplies", "image_url": "", "children": []},
        {"name": "Construction Materials", "image_url": "", "children": []},
        {"name": "General Bulk Goods", "image_url": "", "children": []},
    ],
    "restaurant": [
        {
            "name": "Fast Food",
            "image_url": "",
            "children": [
                {"name": "Burgers", "image_url": ""},
                {"name": "Fried Chicken", "image_url": ""},
                {"name": "Fries", "image_url": ""},
                {"name": "Shawarma", "image_url": ""},
                {"name": "Sandwiches", "image_url": ""},
                {"name": "Pizza", "image_url": ""},
            ],
        },
        {
            "name": "Local Food",
            "image_url": "",
            "children": [
                {"name": "Kisra & Stews", "image_url": ""},
                {"name": "Asida", "image_url": ""},
                {"name": "Goat Meat Dishes", "image_url": ""},
                {"name": "Fish Dishes", "image_url": ""},
                {"name": "Rice Meals", "image_url": ""},
                {"name": "Grills & BBQ", "image_url": ""},
            ],
        },
        {
            "name": "Drinks",
            "image_url": "",
            "children": [
                {"name": "Coffee", "image_url": ""},
                {"name": "Tea", "image_url": ""},
                {"name": "Juice", "image_url": ""},
                {"name": "Smoothies", "image_url": ""},
                {"name": "Soft Drinks", "image_url": ""},
            ],
        },
        {
            "name": "Bakery",
            "image_url": "",
            "children": [
                {"name": "Cakes", "image_url": ""},
                {"name": "Bread", "image_url": ""},
                {"name": "Pastries", "image_url": ""},
                {"name": "Desserts", "image_url": ""},
                {"name": "Cookies", "image_url": ""},
            ],
        },
    ],
}
