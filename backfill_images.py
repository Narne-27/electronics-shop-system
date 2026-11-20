"""
Electrodesk - Studio Product Image Generator & Database Backfill
Generates 1200x1200px WebP studio product imagery (<200KB) for all 31 catalog products,
and updates the SQLite PRODUCT table with the correct static asset URLs.
"""

import os
import re
import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import db

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images', 'products')

def slugify(text):
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text).strip().lower()
    return re.sub(r'[\s_]+', '-', text)

def with_alpha(color, alpha):
    return (color[0], color[1], color[2], alpha)

def create_studio_canvas():
    # 1200x1200px transparent canvas
    return Image.new('RGBA', (1200, 1200), (255, 255, 255, 0))

def add_drop_shadow(canvas, box, radius=40, offset=(0, 45), opacity=70):
    shadow = Image.new('RGBA', (1200, 1200), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    x1, y1, x2, y2 = box
    ox, oy = offset
    s_draw.ellipse([x1 + ox - 40, y2 + oy - 30, x2 + ox + 40, y2 + oy + 50], fill=(10, 15, 30, opacity))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius))
    canvas.alpha_composite(shadow)

# Category-specific studio generators
def draw_smartphone(canvas, name, brand, color_theme):
    draw = ImageDraw.Draw(canvas)
    is_tablet = "ipad" in name.lower() or "tablet" in name.lower()
    
    if is_tablet:
        box = [240, 220, 960, 980]
        radius = 48
    else:
        box = [370, 150, 830, 1050]
        radius = 70
        
    add_drop_shadow(canvas, box, radius=50, offset=(0, 40), opacity=90)
    
    # Outer frame
    frame_color = color_theme.get('frame', (45, 52, 65, 255))
    accent_color = color_theme.get('accent', (100, 180, 255, 255))
    bg_gradient = color_theme.get('screen', (15, 23, 42, 255))
    
    draw.rounded_rectangle(box, radius=radius, fill=frame_color, outline=(200, 210, 225, 200), width=6)
    
    # Screen bezel
    s_box = [box[0] + 16, box[1] + 16, box[2] - 16, box[3] - 16]
    draw.rounded_rectangle(s_box, radius=radius - 12, fill=(10, 15, 25, 255))
    
    # Inner display with vibrant gradient wallpaper
    d_box = [s_box[0] + 8, s_box[1] + 8, s_box[2] - 8, s_box[3] - 8]
    draw.rounded_rectangle(d_box, radius=radius - 18, fill=bg_gradient)
    
    # Screen graphic accents
    cx = (d_box[0] + d_box[2]) // 2
    cy = (d_box[1] + d_box[3]) // 2
    for r in range(160, 20, -35):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=with_alpha(accent_color, 140), width=4)
        
    # Dynamic Island / Camera punch-hole
    if "iphone" in name.lower():
        # Dynamic Island pill
        draw.rounded_rectangle([cx - 55, d_box[1] + 20, cx + 55, d_box[1] + 52], radius=16, fill=(5, 5, 10, 255))
        draw.ellipse([cx + 25, d_box[1] + 28, cx + 41, d_box[1] + 44], fill=(20, 25, 40, 255))
    elif not is_tablet:
        # Central punch hole
        draw.ellipse([cx - 10, d_box[1] + 22, cx + 10, d_box[1] + 42], fill=(5, 5, 10, 255))
        draw.ellipse([cx - 4, d_box[1] + 28, cx + 4, d_box[1] + 36], fill=(40, 60, 100, 255))

    # Bottom gesture bar
    draw.rounded_rectangle([cx - 70, d_box[3] - 22, cx + 70, d_box[3] - 16], radius=3, fill=(255, 255, 255, 180))

def draw_laptop(canvas, name, brand, color_theme):
    draw = ImageDraw.Draw(canvas)
    add_drop_shadow(canvas, [180, 260, 1020, 940], radius=50, offset=(0, 45), opacity=100)
    
    frame_color = color_theme.get('frame', (35, 40, 50, 255))
    accent_color = color_theme.get('accent', (70, 160, 255, 255))
    
    # Screen lid
    screen_box = [240, 220, 960, 720]
    draw.rounded_rectangle(screen_box, radius=24, fill=(18, 22, 30, 255), outline=frame_color, width=8)
    
    # Display panel with ambient wallpaper
    disp_box = [screen_box[0] + 18, screen_box[1] + 18, screen_box[2] - 18, screen_box[3] - 24]
    draw.rounded_rectangle(disp_box, radius=12, fill=color_theme.get('screen', (12, 18, 32, 255)))
    
    cx = (disp_box[0] + disp_box[2]) // 2
    cy = (disp_box[1] + disp_box[3]) // 2
    draw.ellipse([cx - 140, cy - 80, cx + 140, cy + 80], fill=with_alpha(accent_color, 120))
    draw.ellipse([cx - 80, cy - 40, cx + 80, cy + 40], fill=(255, 255, 255, 160))
    
    # Webcam
    draw.ellipse([cx - 5, screen_box[1] + 6, cx + 5, screen_box[1] + 16], fill=(10, 10, 15, 255))
    
    # Hinge
    draw.rounded_rectangle([420, 715, 780, 735], radius=6, fill=(25, 30, 38, 255))
    
    # Keyboard base deck
    base_box = [160, 725, 1040, 940]
    draw.rounded_rectangle(base_box, radius=20, fill=frame_color, outline=(120, 130, 145, 180), width=4)
    
    # Trackpad
    draw.rounded_rectangle([470, 835, 730, 925], radius=8, outline=(100, 110, 125, 180), width=2, fill=(40, 46, 58, 255))
    
    # Keyboard grid indication
    kb_box = [230, 745, 970, 825]
    draw.rounded_rectangle(kb_box, radius=8, fill=(20, 24, 32, 255))
    for x in range(kb_box[0] + 15, kb_box[2] - 15, 48):
        draw.line([x, kb_box[1] + 8, x, kb_box[3] - 8], fill=(35, 42, 54, 255), width=2)
    for y in range(kb_box[1] + 16, kb_box[3], 18):
        draw.line([kb_box[0] + 10, y, kb_box[2] - 10, y], fill=(35, 42, 54, 255), width=2)

def draw_audio(canvas, name, brand, color_theme):
    draw = ImageDraw.Draw(canvas)
    cx, cy = 600, 580
    
    if "wh-1000xm5" in name.lower() or "headphone" in name.lower():
        # Over-ear headphones
        add_drop_shadow(canvas, [320, 260, 880, 920], radius=45, offset=(0, 40), opacity=80)
        # Headband arc
        draw.arc([360, 240, 840, 720], start=180, end=0, fill=(35, 40, 48, 255), width=36)
        draw.arc([390, 270, 810, 690], start=180, end=0, fill=(20, 24, 30, 255), width=20)
        # Earcups left and right
        draw.rounded_rectangle([320, 520, 460, 840], radius=55, fill=(40, 45, 54, 255), outline=(75, 85, 100, 255), width=6)
        draw.rounded_rectangle([740, 520, 880, 840], radius=55, fill=(40, 45, 54, 255), outline=(75, 85, 100, 255), width=6)
        # Soft ear cushions
        draw.rounded_rectangle([350, 550, 450, 810], radius=45, fill=(25, 30, 36, 255))
        draw.rounded_rectangle([750, 550, 850, 810], radius=45, fill=(25, 30, 36, 255))
    elif "speaker" in name.lower() or "flip" in name.lower() or "stanmore" in name.lower():
        # Premium Bluetooth Speaker
        add_drop_shadow(canvas, [260, 380, 940, 820], radius=50, offset=(0, 40), opacity=90)
        body_box = [280, 360, 920, 800]
        draw.rounded_rectangle(body_box, radius=40, fill=color_theme.get('frame', (28, 32, 40, 255)), outline=(65, 75, 90, 255), width=6)
        # Grille mesh
        mesh_box = [body_box[0] + 24, body_box[1] + 24, body_box[2] - 24, body_box[3] - 24]
        draw.rounded_rectangle(mesh_box, radius=24, fill=(16, 20, 26, 255))
        for gy in range(mesh_box[1] + 15, mesh_box[3], 18):
            draw.line([mesh_box[0] + 15, gy, mesh_box[2] - 15, gy], fill=(30, 36, 46, 255), width=3)
        # Brand badge
        draw.rounded_rectangle([cx - 90, cy - 25, cx + 90, cy + 25], radius=10, fill=(210, 160, 60, 255))
        draw.rounded_rectangle([cx - 86, cy - 21, cx + 86, cy + 21], radius=8, fill=(15, 18, 24, 255))
    else:
        # True Wireless Earbuds Case
        add_drop_shadow(canvas, [380, 360, 820, 820], radius=45, offset=(0, 35), opacity=85)
        case_box = [390, 350, 810, 790]
        draw.rounded_rectangle(case_box, radius=120, fill=color_theme.get('frame', (30, 35, 45, 255)), outline=(70, 80, 95, 255), width=8)
        # Seam
        draw.line([case_box[0], cy - 10, case_box[2], cy - 10], fill=(20, 24, 30, 255), width=6)
        # LED dot
        draw.ellipse([cx - 8, cy + 50, cx + 8, cy + 66], fill=(40, 230, 180, 255))

def draw_tv(canvas, name, brand, color_theme):
    draw = ImageDraw.Draw(canvas)
    add_drop_shadow(canvas, [160, 250, 1040, 830], radius=50, offset=(0, 45), opacity=100)
    
    tv_box = [180, 220, 1020, 770]
    draw.rounded_rectangle(tv_box, radius=14, fill=(20, 24, 32, 255), outline=(90, 100, 115, 255), width=5)
    
    screen_box = [tv_box[0] + 12, tv_box[1] + 12, tv_box[2] - 12, tv_box[3] - 12]
    draw.rounded_rectangle(screen_box, radius=6, fill=color_theme.get('screen', (10, 16, 28, 255)))
    
    # Cinematic HDR landscape glow on display
    cx, cy = 600, 495
    accent = color_theme.get('accent', (255, 110, 60, 255))
    draw.ellipse([cx - 240, cy - 120, cx + 240, cy + 120], fill=with_alpha(accent, 160))
    draw.ellipse([cx - 140, cy - 60, cx + 140, cy + 60], fill=(255, 215, 120, 220))
    
    # Slim metallic TV stand feet
    draw.polygon([(290, 770), (250, 850), (280, 850), (310, 770)], fill=(70, 75, 85, 255))
    draw.polygon([(910, 770), (950, 850), (920, 850), (890, 770)], fill=(70, 75, 85, 255))

def draw_console(canvas, name, brand, color_theme):
    draw = ImageDraw.Draw(canvas)
    add_drop_shadow(canvas, [340, 220, 860, 960], radius=55, offset=(0, 45), opacity=95)
    
    if "playstation" in name.lower() or "ps5" in name.lower():
        # PS5 Slim Aerodynamic Curved White Fins
        draw.rounded_rectangle([420, 190, 780, 930], radius=35, fill=(18, 22, 30, 255))
        # Left white curved plate
        draw.polygon([(390, 170), (490, 170), (470, 940), (370, 940)], fill=(245, 248, 255, 255))
        # Right white curved plate
        draw.polygon([(710, 170), (810, 170), (830, 940), (730, 940)], fill=(245, 248, 255, 255))
        # Blue LED accent vent
        draw.line([495, 220, 475, 900], fill=(40, 130, 255, 255), width=6)
    elif "switch" in name.lower():
        # Nintendo Switch OLED
        # Center tablet
        draw.rounded_rectangle([360, 360, 840, 760], radius=16, fill=(15, 20, 28, 255), outline=(50, 60, 75, 255), width=4)
        draw.rounded_rectangle([390, 385, 810, 735], radius=8, fill=(8, 12, 18, 255))
        draw.ellipse([540, 500, 660, 620], fill=(240, 50, 50, 200))
        # Joy-Con Left
        draw.rounded_rectangle([250, 360, 360, 760], radius=40, fill=(240, 245, 250, 255), outline=(180, 190, 205, 255), width=4)
        draw.ellipse([285, 420, 325, 460], fill=(30, 35, 45, 255))
        # Joy-Con Right
        draw.rounded_rectangle([840, 360, 950, 760], radius=40, fill=(240, 245, 250, 255), outline=(180, 190, 205, 255), width=4)
        draw.ellipse([875, 520, 915, 560], fill=(30, 35, 45, 255))
    else:
        # Xbox Series X Monolith
        draw.rounded_rectangle([390, 220, 810, 920], radius=24, fill=(24, 28, 34, 255), outline=(60, 70, 80, 255), width=6)
        # Top concave green vents
        draw.ellipse([450, 210, 750, 270], fill=(20, 24, 30, 255))
        for gx in range(480, 720, 24):
            draw.ellipse([gx - 6, 230, gx + 6, 250], fill=(16, 185, 129, 255))
        # Slot & power button
        draw.ellipse([440, 310, 464, 334], fill=(255, 255, 255, 240))
        draw.line([445, 420, 445, 620], fill=(10, 12, 16, 255), width=6)

def draw_wearable(canvas, name, brand, color_theme):
    draw = ImageDraw.Draw(canvas)
    add_drop_shadow(canvas, [380, 240, 820, 960], radius=50, offset=(0, 40), opacity=90)
    
    # Watch bands top and bottom
    band_color = color_theme.get('band', (35, 42, 54, 255))
    draw.rounded_rectangle([470, 140, 730, 450], radius=24, fill=band_color)
    draw.rounded_rectangle([470, 680, 730, 1060], radius=24, fill=band_color)
    
    # Watch Case
    case_box = [390, 320, 810, 800]
    draw.rounded_rectangle(case_box, radius=95, fill=color_theme.get('frame', (28, 34, 46, 255)), outline=(180, 190, 205, 255), width=8)
    
    # Digital Crown button
    draw.rounded_rectangle([805, 450, 835, 550], radius=8, fill=(150, 160, 175, 255))
    
    # OLED Display
    oled_box = [case_box[0] + 24, case_box[1] + 24, case_box[2] - 24, case_box[3] - 24]
    draw.rounded_rectangle(oled_box, radius=75, fill=(6, 10, 18, 255))
    
    # Watchface aesthetic rings / complications
    cx, cy = 600, 560
    accent = color_theme.get('accent', (245, 99, 0, 255))
    draw.arc([cx - 120, cy - 120, cx + 120, cy + 120], start=45, end=315, fill=accent, width=12)
    draw.arc([cx - 90, cy - 90, cx + 90, cy + 90], start=120, end=360, fill=(30, 215, 96, 255), width=10)
    draw.arc([cx - 60, cy - 60, cx + 60, cy + 60], start=0, end=240, fill=(0, 195, 255, 255), width=8)

def draw_smart_home(canvas, name, brand, color_theme):
    draw = ImageDraw.Draw(canvas)
    cx, cy = 600, 580
    
    if "vacuum" in name.lower() or "dyson" in name.lower():
        # High-tech cordless stick vacuum
        add_drop_shadow(canvas, [320, 300, 880, 880], radius=45, offset=(0, 35), opacity=80)
        # Motor housing
        draw.rounded_rectangle([420, 300, 780, 560], radius=60, fill=(210, 18, 60, 255), outline=(60, 65, 75, 255), width=6)
        # Clear dust bin
        draw.rounded_rectangle([460, 540, 740, 780], radius=30, fill=(40, 50, 70, 180), outline=(120, 130, 150, 200), width=4)
        # Wand pipe
        draw.rounded_rectangle([560, 760, 640, 1020], radius=12, fill=(215, 160, 25, 255))
    elif "router" in name.lower() or "wifi" in name.lower():
        # High-speed WiFi 6 Router
        add_drop_shadow(canvas, [240, 480, 960, 840], radius=50, offset=(0, 40), opacity=90)
        # Router body
        draw.rounded_rectangle([260, 460, 940, 800], radius=30, fill=(24, 28, 36, 255), outline=(65, 75, 90, 255), width=6)
        # 6 Antennas
        for ax in [290, 410, 530, 670, 790, 910]:
            draw.polygon([(ax - 12, 470), (ax + 12, 470), (ax + 18, 180), (ax - 18, 180)], fill=(32, 38, 48, 255))
        # Top geometric diamond vents
        draw.polygon([(cx, 510), (cx + 120, 610), (cx, 710), (cx - 120, 610)], fill=(15, 18, 24, 255), outline=(40, 160, 255, 255), width=3)
    elif "echo" in name.lower():
        # Echo Dot Sphere
        add_drop_shadow(canvas, [340, 340, 860, 860], radius=55, offset=(0, 45), opacity=95)
        draw.ellipse([350, 320, 850, 820], fill=color_theme.get('frame', (65, 75, 90, 255)), outline=(100, 115, 135, 255), width=6)
        # Glowing base ring
        draw.ellipse([420, 770, 780, 835], fill=(30, 220, 255, 255))
        # Clock display
        draw.rounded_rectangle([cx - 90, cy - 25, cx + 90, cy + 25], radius=10, fill=(25, 30, 40, 200))
    else:
        # Smart Plug / GaN Charger
        add_drop_shadow(canvas, [380, 360, 820, 820], radius=45, offset=(0, 40), opacity=85)
        draw.rounded_rectangle([400, 340, 800, 780], radius=50, fill=(245, 248, 252, 255), outline=(190, 200, 215, 255), width=6)
        # Ports or indicator
        draw.rounded_rectangle([470, 460, 730, 500], radius=10, fill=(30, 35, 45, 255))
        draw.rounded_rectangle([470, 540, 730, 580], radius=10, fill=(30, 35, 45, 255))
        draw.ellipse([cx - 12, 640, cx + 12, 664], fill=(16, 185, 129, 255))

def generate_product_image(p):
    name = p['product_name']
    brand = p['brand']
    cat = p.get('category_name', '')
    
    canvas = create_studio_canvas()
    slug = slugify(name)
    filepath = os.path.join(OUTPUT_DIR, f"{slug}.webp")
    
    # Custom color themes per brand/product
    if "samsung" in brand.lower():
        theme = {'frame': (40, 45, 55, 255), 'accent': (75, 130, 255, 255), 'screen': (12, 20, 38, 255)}
    elif "apple" in brand.lower():
        theme = {'frame': (50, 52, 58, 255), 'accent': (245, 100, 30, 255), 'screen': (15, 18, 24, 255), 'band': (28, 30, 34, 255)}
    elif "sony" in brand.lower():
        theme = {'frame': (32, 36, 44, 255), 'accent': (190, 160, 100, 255), 'screen': (10, 14, 22, 255)}
    elif "oneplus" in brand.lower():
        theme = {'frame': (38, 44, 40, 255), 'accent': (30, 180, 130, 255), 'screen': (14, 30, 24, 255)}
    elif "rog" in name.lower() or "asus" in brand.lower():
        theme = {'frame': (24, 26, 32, 255), 'accent': (255, 45, 85, 255), 'screen': (10, 12, 18, 255)}
    else:
        theme = {'frame': (38, 44, 54, 255), 'accent': (45, 140, 255, 255), 'screen': (14, 20, 32, 255)}
        
    cat_lower = cat.lower()
    if "smartphone" in cat_lower or "tablet" in cat_lower:
        draw_smartphone(canvas, name, brand, theme)
    elif "laptop" in cat_lower or "computer" in cat_lower:
        if "keyboard" in name.lower():
            draw_audio(canvas, name, brand, theme) # keyboard styling
        else:
            draw_laptop(canvas, name, brand, theme)
    elif "audio" in cat_lower or "sound" in cat_lower:
        draw_audio(canvas, name, brand, theme)
    elif "tv" in cat_lower or "display" in cat_lower:
        draw_tv(canvas, name, brand, theme)
    elif "gaming" in cat_lower or "console" in cat_lower:
        draw_console(canvas, name, brand, theme)
    elif "wearable" in cat_lower or "fitness" in cat_lower:
        draw_wearable(canvas, name, brand, theme)
    else:
        draw_smart_home(canvas, name, brand, theme)
        
    # Save optimized WebP image (<200KB, clean studio quality)
    canvas.save(filepath, format='WEBP', quality=90, method=6)
    size_kb = os.path.getsize(filepath) / 1024
    rel_url = f"/static/images/products/{slug}.webp"
    print(f"Generated: {slug}.webp ({size_kb:.1f} KB) -> {rel_url}")
    return rel_url

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    products = db.query("""
        SELECT p.*, c.category_name 
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        ORDER BY p.product_id ASC
    """)
    print(f"Found {len(products)} products in database.")
    
    updated_count = 0
    for p in products:
        rel_url = generate_product_image(p)
        db.execute("UPDATE PRODUCT SET image_url = %s WHERE product_id = %s", (rel_url, p['product_id']))
        updated_count += 1
        
    print(f"\nSuccessfully backfilled and linked {updated_count} product images!")

if __name__ == '__main__':
    main()
