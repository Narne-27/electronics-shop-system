import os, re, json, csv, urllib.request, urllib.parse, sqlite3
import numpy as np
from PIL import Image

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_IMG_DIR = os.path.join(BASE_DIR, 'static', 'images', 'products')
RAW_DIR = os.path.join(BASE_DIR, 'temp_raw_images')
os.makedirs(STATIC_IMG_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

# Product configuration
MAPPINGS = {
    # 1. Generated studio photos via built-in image engine
    6: {
        'slug': 'hp-pavilion-15-core-i7-16gb',
        'source': 'generated',
        'local_file': r'C:\Users\narne\.gemini\antigravity\brain\2911eaab-ccbd-49fd-8257-78536781a9ea\hp_pavilion_15_1795180859898.jpg',
        'license': 'Proprietary Studio Render',
        'artist': 'Antigravity Studio Engine',
        'url': 'local://generated'
    },
    7: {
        'slug': 'dell-inspiron-15-16gb-ssd',
        'source': 'generated',
        'local_file': r'C:\Users\narne\.gemini\antigravity\brain\2911eaab-ccbd-49fd-8257-78536781a9ea\dell_inspiron_15_1795180844426.jpg',
        'license': 'Proprietary Studio Render',
        'artist': 'Antigravity Studio Engine',
        'url': 'local://generated'
    },
    8: {
        'slug': 'apple-macbook-air-13-m2',
        'source': 'generated',
        'local_file': r'C:\Users\narne\.gemini\antigravity\brain\2911eaab-ccbd-49fd-8257-78536781a9ea\macbook_air_m2_1795180821444.jpg',
        'license': 'Proprietary Studio Render',
        'artist': 'Antigravity Studio Engine',
        'url': 'local://generated'
    },
    9: {
        'slug': 'asus-rog-zephyrus-g16',
        'source': 'generated',
        'local_file': r'C:\Users\narne\.gemini\antigravity\brain\2911eaab-ccbd-49fd-8257-78536781a9ea\asus_rog_zephyrus_g16_1795180831590.jpg',
        'license': 'Proprietary Studio Render',
        'artist': 'Antigravity Studio Engine',
        'url': 'local://generated'
    },
    15: {
        'slug': 'sony-wh-1000xm5-headphones',
        'source': 'generated',
        'local_file': r'C:\Users\narne\.gemini\antigravity\brain\2911eaab-ccbd-49fd-8257-78536781a9ea\test_sony_1795180363086.jpg',
        'license': 'Proprietary Studio Render',
        'artist': 'Antigravity Studio Engine',
        'url': 'local://generated'
    },
    28: {
        'slug': 'microsoft-xbox-series-x-1tb',
        'source': 'generated',
        'local_file': r'C:\Users\narne\.gemini\antigravity\brain\2911eaab-ccbd-49fd-8257-78536781a9ea\xbox_series_x_1795180809453.jpg',
        'license': 'Proprietary Studio Render',
        'artist': 'Antigravity Studio Engine',
        'url': 'local://generated'
    },

    # 2. Wikimedia Commons CC-licensed photos
    1: {'slug': 'samsung-galaxy-s24-ultra-512gb', 'wiki_title': 'File:SAMSUNG Galaxy S24 Ultra (6).jpg'},
    2: {'slug': 'apple-iphone-15-pro-max-256gb', 'wiki_title': 'File:Apple iPhone 15 Pro.jpg'},
    3: {'slug': 'xiaomi-redmi-note-13-pro-5g', 'wiki_title': 'File:Redmi Note 11 back.jpg'},
    4: {'slug': 'oneplus-12-5g-256gb', 'wiki_title': 'File:OnePlus 6 Front1.jpg'},
    5: {'slug': 'apple-ipad-air-11-m2-128gb', 'wiki_title': 'File:IPad Air.png'},
    10: {'slug': 'lenovo-ideapad-slim-3-15', 'wiki_title': 'File:Lenovo IdeaPad 320.jpg'},
    11: {'slug': 'logitech-mx-keys-wireless-keyboard', 'wiki_title': 'File:Logitech MK240 CJK Keyboard.jpg'},
    12: {'slug': 'sandisk-extreme-1tb-portable-ssd', 'wiki_title': 'File:SanDisk Extreme Portable SSD 1 TB - front view.jpg'},
    13: {'slug': 'boat-airdopes-141-anc-earbuds', 'wiki_title': 'File:ActiveSound wireless earbuds by Hykker (POJM200483).jpg'},
    14: {'slug': 'jbl-flip-6-waterproof-speaker', 'wiki_title': 'File:Głośnik JBL Flip 3.jpg'},
    16: {'slug': 'boat-stone-1200-bluetooth-speaker', 'wiki_title': 'File:JBL Flip 3 bluetooth speaker (DSCF2653).jpg'},
    17: {'slug': 'marshall-stanmore-iii-speaker', 'wiki_title': 'File:Marshall Speaker.jpg'},
    18: {'slug': 'mi-tv-43-4k-google-tv', 'wiki_title': 'File:A Flat Screen Television.jpg'},
    19: {'slug': 'lg-55-oled-4k-smart-cinema-tv', 'wiki_title': 'File:IFA 2012 LG전자 OLED TV (1).jpg'},
    20: {'slug': 'samsung-65-neo-qled-4k-tv', 'wiki_title': 'File:Samsung TV UE55F9000 with Sonos soundbar.jpg'},
    21: {'slug': 'sony-bravia-55-4k-google-tv', 'wiki_title': 'File:Sony Bravia 3D on display at CES 20110106.jpg'},
    22: {'slug': 'amazon-echo-dot-5th-gen-clock', 'wiki_title': 'File:Amazon Echo Dot (RS03QR) - cover removed-0547.jpg'},
    23: {'slug': 'dyson-v12-detect-slim-vacuum', 'wiki_title': 'File:Dyson DC19 vacuum cleaner.jpg'},
    24: {'slug': 'tp-link-archer-ax73-wifi-6', 'wiki_title': 'File:TP-Link TL-WR740N router HS1 transparent.png'},
    25: {'slug': 'wipro-16a-smart-wifi-plug', 'wiki_title': 'File:Smart plug adapter front view with power button.jpg'},
    26: {'slug': 'anker-65w-gan-fast-charger', 'wiki_title': 'File:Samsung Travel Adapter 3.jpg'},
    27: {'slug': 'sony-playstation-5-slim-1tb', 'wiki_title': 'File:PlayStation 5 and DualSense.jpg'},
    29: {'slug': 'nintendo-switch-oled-model', 'wiki_title': 'File:Nintendo-Switch-Console-Docked-wJoyConRB.jpg'},
    30: {'slug': 'apple-watch-series-9-gps-45mm', 'wiki_title': 'File:Apple Watch Series 4 40mm space gray Aluminum.jpg'},
    31: {'slug': 'noise-colorfit-pro-5-smartwatch', 'wiki_title': 'File:Samsung Galaxy Fit.jpg'}
}

def get_wikimedia_info(title):
    url = f'https://commons.wikimedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=imageinfo&iiprop=url|size|extmetadata|mime&format=json'
    req = urllib.request.Request(url, headers={'User-Agent': 'ElectrodeskApp/1.0 (contact@electrodesk.local)'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            pages = data.get('query', {}).get('pages', {})
            for pid, page in pages.items():
                infos = page.get('imageinfo', [])
                if infos:
                    info = infos[0]
                    meta = info.get('extmetadata', {})
                    lic = meta.get('LicenseShortName', {}).get('value', 'CC BY-SA')
                    artist = meta.get('Artist', {}).get('value', 'Wikimedia Commons')
                    artist = re.sub('<[^<]+?>', '', artist).strip() or 'Wikimedia Contributor'
                    return info.get('url'), lic, artist, info.get('descriptionurl', '')
    except Exception as e:
        print(f'Error fetching wikimedia info for {title}: {e}')
    return None, None, None, None

def process_and_save(src_image_path, slug):
    try:
        img = Image.open(src_image_path).convert('RGBA')
        # Fast thumbnail downscale for very large images
        img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
        
        arr = np.array(img)
        r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
        
        # Check if already transparent
        if not (a < 50).any():
            # Flood corners & remove white/near-white
            corners = [arr[0,0][:3], arr[0,-1][:3], arr[-1,0][:3], arr[-1,-1][:3]]
            bg_mean = np.mean(corners, axis=0)
            
            # Distance from background
            dist = np.sqrt(np.sum((arr[:,:,:3] - bg_mean)**2, axis=2))
            
            # Mask pure white or close to corners
            is_white = (r > 238) & (g > 238) & (b > 238)
            is_corner_bg = (dist < 25) & (r > 215) & (g > 215) & (b > 215)
            mask = is_white | is_corner_bg
            arr[mask, 3] = 0
            
            # Soft feather near boundary
            feather_mask = (dist < 40) & (r > 200) & (g > 200) & (b > 200) & ~mask
            if feather_mask.any():
                factor = (dist[feather_mask] - 25) / 15.0
                arr[feather_mask, 3] = np.clip(factor * 255, 0, 255).astype(np.uint8)

        out_img = Image.fromarray(arr)
        
        # Trim transparent borders
        bbox = out_img.split()[-1].getbbox()
        trimmed = out_img.crop(bbox) if bbox else out_img
        
        # Pad 8% into 1000x1000 square
        tw, th = trimmed.size
        max_dim = max(tw, th)
        target_size = int(1000 * 0.84) # 84% width/height = 8% padding on each side
        scale = target_size / max_dim
        nw, nh = max(1, int(tw * scale)), max(1, int(th * scale))
        resized = trimmed.resize((nw, nh), Image.Resampling.LANCZOS)
        
        final_square = Image.new('RGBA', (1000, 1000), (0, 0, 0, 0))
        final_square.paste(resized, ((1000 - nw)//2, (1000 - nh)//2), resized)
        
        # Save full WebP (<150KB)
        full_dest = os.path.join(STATIC_IMG_DIR, f'{slug}.webp')
        final_square.save(full_dest, 'WEBP', quality=88, method=6)
        
        # Save 128px thumbnail
        thumb_dest = os.path.join(STATIC_IMG_DIR, f'{slug}_thumb.webp')
        thumb_img = final_square.resize((128, 128), Image.Resampling.LANCZOS)
        thumb_img.save(thumb_dest, 'WEBP', quality=85)
        
        full_kb = os.path.getsize(full_dest) / 1024
        thumb_kb = os.path.getsize(thumb_dest) / 1024
        return True, full_kb, thumb_kb
    except Exception as e:
        print(f'Error processing {slug}: {e}')
        return False, 0, 0

conn = sqlite3.connect('electrodesk.db')
cur = conn.cursor()
cur.execute('SELECT p.product_id, p.product_name, p.brand, p.model, p.product_code, c.category_name FROM product p JOIN category c ON p.category_id=c.category_id ORDER BY p.product_id')
products = cur.fetchall()

credits_rows = []
manifest_rows = []

for pid, name, brand, model, code, category in products:
    cfg = MAPPINGS.get(pid, {})
    slug = cfg.get('slug', name.lower().replace(' ', '-'))
    src_type = cfg.get('source', 'wikimedia')
    
    print(f'[{pid}/31] {name} ({src_type})...')
    
    raw_path = None
    title_or_id = None
    lic = None
    artist = None
    url = None
    
    if src_type == 'generated':
        raw_path = cfg['local_file']
        title_or_id = os.path.basename(raw_path)
        lic = cfg['license']
        artist = cfg['artist']
        url = cfg['url']
    elif src_type == 'wikimedia':
        title_or_id = cfg.get('wiki_title', '')
        # Check if already downloaded
        raw_candidates = [
            os.path.join(RAW_DIR, f'{slug}.jpg'),
            os.path.join(RAW_DIR, f'{slug}.png'),
            os.path.join(RAW_DIR, f'{slug}.webp')
        ]
        existing_raw = next((p for p in raw_candidates if os.path.exists(p)), None)
        
        if existing_raw:
            raw_path = existing_raw
            lic = 'CC BY-SA'
            artist = 'Wikimedia Contributor'
            url = f'https://commons.wikimedia.org/wiki/{title_or_id}'
        else:
            img_url, lic, artist, desc_url = get_wikimedia_info(title_or_id)
            if img_url:
                ext = os.path.splitext(img_url.split('?')[0])[1] or '.jpg'
                raw_path = os.path.join(RAW_DIR, f'{slug}{ext}')
                try:
                    req = urllib.request.Request(img_url, headers={'User-Agent': 'ElectrodeskApp/1.0 (contact@electrodesk.local)'})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        with open(raw_path, 'wb') as f:
                            f.write(resp.read())
                    url = desc_url or f'https://commons.wikimedia.org/wiki/{title_or_id}'
                except Exception as e:
                    print(f'Failed to download {title_or_id}: {e}')
                    raw_path = None
    
    if raw_path and os.path.exists(raw_path):
        ok, f_kb, t_kb = process_and_save(raw_path, slug)
        if ok:
            print(f'  -> OK: {slug}.webp ({f_kb:.1f} KB), thumb ({t_kb:.1f} KB)')
            credits_rows.append([pid, name, src_type.capitalize(), title_or_id, lic, artist, url])
            manifest_rows.append([name, brand, model, code, category, 'real', f'/static/images/products/{slug}.webp', src_type])
            # Update DB image_url
            cur.execute('UPDATE product SET image_url=? WHERE product_id=?', (f'/static/images/products/{slug}.webp', pid))
            continue

    print(f'  -> MISSING IMAGE FOR {name}')
    manifest_rows.append([name, brand, model, code, category, 'missing', '/static/images/logo.svg', 'none'])

conn.commit()

# Write image_credits.csv
with open('image_credits.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['product_id', 'product_name', 'source', 'title_or_id', 'license', 'artist', 'url'])
    writer.writerows(credits_rows)
print('Wrote image_credits.csv with', len(credits_rows), 'entries')

# Write products_manifest.csv
with open('products_manifest.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['name', 'brand', 'model', 'sku', 'category', 'status', 'current_image_url', 'source'])
    writer.writerows(manifest_rows)
print('Wrote products_manifest.csv with', len(manifest_rows), 'entries')
