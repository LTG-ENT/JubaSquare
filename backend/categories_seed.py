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
            "children": [
                {"name": "Fresh Produce", "image_url": ""},
                {"name": "Dairy & Eggs", "image_url": ""},
                {"name": "Meat & Poultry", "image_url": ""},
                {"name": "Packaged Foods", "image_url": ""},
                {"name": "Beverages", "image_url": ""},
                {"name": "Snacks", "image_url": ""},
            ],
        },
        {
            "name": "Clothing & Fashion",
            "image_url": "https://images.unsplash.com/photo-1757140447782-8503452b2204?w=400&q=80",
            "children": [
                {"name": "Men's Clothing", "image_url": ""},
                {"name": "Women's Clothing", "image_url": ""},
                {"name": "Kids Clothing", "image_url": ""},
                {"name": "Accessories", "image_url": ""},
                {"name": "Traditional Wear", "image_url": ""},
            ],
        },
        {
            "name": "Shoes & Bags",
            "image_url": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=400&q=80",
            "children": [
                {"name": "Men's Shoes", "image_url": ""},
                {"name": "Women's Shoes", "image_url": ""},
                {"name": "Kids Shoes", "image_url": ""},
                {"name": "Handbags", "image_url": ""},
                {"name": "Backpacks", "image_url": ""},
            ],
        },
        {
            "name": "Beauty & Cosmetics",
            "image_url": "https://images.unsplash.com/photo-1522335789203-aaa57d0aacae?w=400&q=80",
            "children": [
                {"name": "Skincare", "image_url": ""},
                {"name": "Makeup", "image_url": ""},
                {"name": "Hair Care", "image_url": ""},
                {"name": "Fragrances", "image_url": ""},
                {"name": "Personal Care", "image_url": ""},
            ],
        },
        {
            "name": "Electronics & Accessories",
            "image_url": "https://images.unsplash.com/photo-1761641466573-f240b6e446de?w=400&q=80",
            "children": [
                {"name": "Mobile Phones", "image_url": ""},
                {"name": "Computers & Laptops", "image_url": ""},
                {"name": "Audio & Video", "image_url": ""},
                {"name": "Phone Accessories", "image_url": ""},
                {"name": "Gaming", "image_url": ""},
            ],
        },
        {
            "name": "Home Essentials",
            "image_url": "https://images.pexels.com/photos/15108276/pexels-photo-15108276.jpeg?auto=compress&w=400",
            "children": [
                {"name": "Furniture", "image_url": ""},
                {"name": "Kitchen Items", "image_url": ""},
                {"name": "Bedding", "image_url": ""},
                {"name": "Home Decor", "image_url": ""},
                {"name": "Cleaning Supplies", "image_url": ""},
            ],
        },
        {
            "name": "Health & Pharmacy",
            "image_url": "https://images.unsplash.com/photo-1646392206581-2527b1cae5cb?w=400&q=80",
            "children": [
                {"name": "Medicines", "image_url": ""},
                {"name": "Vitamins & Supplements", "image_url": ""},
                {"name": "First Aid", "image_url": ""},
                {"name": "Medical Equipment", "image_url": ""},
            ],
        },
        {
            "name": "Building & Materials",
            "image_url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=400&q=80",
            "children": [
                {"name": "Cement & Concrete", "image_url": ""},
                {"name": "Timber & Wood", "image_url": ""},
                {"name": "Paints & Coatings", "image_url": ""},
                {"name": "Tools & Hardware", "image_url": ""},
                {"name": "Plumbing", "image_url": ""},
            ],
        },
        {
            "name": "Automotive",
            "image_url": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=400&q=80",
            "children": [
                {"name": "Car Parts", "image_url": ""},
                {"name": "Tires & Wheels", "image_url": ""},
                {"name": "Car Accessories", "image_url": ""},
                {"name": "Motor Oil & Fluids", "image_url": ""},
            ],
        },
    ],
    "wholesale": [
        {
            "name": "Wholesale Food Supply",
            "image_url": "",
            "children": [
                {"name": "Bulk Grains & Rice", "image_url": ""},
                {"name": "Cooking Oil", "image_url": ""},
                {"name": "Canned Goods", "image_url": ""},
                {"name": "Spices & Seasonings", "image_url": ""},
            ],
        },
        {
            "name": "Wholesale Electronics",
            "image_url": "",
            "children": [
                {"name": "Bulk Mobile Devices", "image_url": ""},
                {"name": "Accessories in Bulk", "image_url": ""},
                {"name": "Electronics Components", "image_url": ""},
            ],
        },
        {
            "name": "Wholesale Clothing",
            "image_url": "",
            "children": [
                {"name": "Bulk T-Shirts", "image_url": ""},
                {"name": "Bulk Uniforms", "image_url": ""},
                {"name": "Bulk Fabrics", "image_url": ""},
            ],
        },
        {
            "name": "Restaurant Supplies",
            "image_url": "",
            "children": [
                {"name": "Commercial Kitchen Equipment", "image_url": ""},
                {"name": "Disposable Items", "image_url": ""},
                {"name": "Bulk Ingredients", "image_url": ""},
            ],
        },
        {
            "name": "Construction Materials",
            "image_url": "",
            "children": [
                {"name": "Bulk Cement", "image_url": ""},
                {"name": "Steel & Rebar", "image_url": ""},
                {"name": "Bricks & Blocks", "image_url": ""},
            ],
        },
        {
            "name": "General Bulk Goods",
            "image_url": "",
            "children": [
                {"name": "Packaging Materials", "image_url": ""},
                {"name": "Office Supplies", "image_url": ""},
                {"name": "Cleaning Products", "image_url": ""},
            ],
        },
    ],
    "restaurant": [
        {"name": "Fast Food", "image_url": "", "children": []},
        {"name": "Local Food", "image_url": "", "children": []},
        {"name": "Café", "image_url": "", "children": []},
        {"name": "Grill & BBQ", "image_url": "", "children": []},
        {"name": "Bakery", "image_url": "", "children": []},
        {"name": "Drinks & Juice", "image_url": "", "children": []},
    ],
}
