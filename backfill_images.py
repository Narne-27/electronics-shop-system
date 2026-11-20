"""
Electrodesk - Idempotent Product Image Wire-Up & Database Backfill
Idempotently verifies and wires up real product images and thumbnails for all products in the database.
Generates 128px thumbnails where missing and ensures fallback support without hardcoded products.
"""

import os
import re
from PIL import Image
import db

STATIC_IMG_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images', 'products')

def slugify(text):
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', str(text)).strip().lower()
    return re.sub(r'[\s_]+', '-', text)

def ensure_thumbnail(slug):
    full_path = os.path.join(STATIC_IMG_DIR, f"{slug}.webp")
    thumb_path = os.path.join(STATIC_IMG_DIR, f"{slug}_thumb.webp")
    
    if os.path.exists(full_path):
        if not os.path.exists(thumb_path):
            try:
                img = Image.open(full_path)
                thumb = img.resize((128, 128), Image.Resampling.LANCZOS)
                thumb.save(thumb_path, 'WEBP', quality=85)
                print(f"Created thumb for {slug}")
            except Exception as e:
                print(f"Failed thumb generation for {slug}: {e}")
        return f"/static/images/products/{slug}.webp"
    return "/static/images/logo.svg"

def main():
    os.makedirs(STATIC_IMG_DIR, exist_ok=True)
    products = db.query("""
        SELECT p.product_id, p.product_name, p.image_url, c.category_name 
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        ORDER BY p.product_id ASC
    """)
    print(f"Checking images for {len(products)} products in database...")
    
    updated_count = 0
    for p in products:
        slug = slugify(p['product_name'])
        image_url = ensure_thumbnail(slug)
        
        if p.get('image_url') != image_url:
            db.execute("UPDATE PRODUCT SET image_url = %s WHERE product_id = %s", (image_url, p['product_id']))
            updated_count += 1
            print(f"Updated {p['product_name']} -> {image_url}")
        else:
            print(f"Verified {p['product_name']} -> {image_url}")
            
    print(f"\nAll {len(products)} products verified. Updated {updated_count} URLs.")

if __name__ == '__main__':
    main()
