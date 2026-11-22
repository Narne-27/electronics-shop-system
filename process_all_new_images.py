"""
Electrodesk - Real-time Product Images Processor
Processes studio renders and high-res product photos into 1000x1000 transparent WebP assets and thumbnails.
"""

import os
from PIL import Image
import numpy as np

STATIC_PRODUCTS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images', 'products')
os.makedirs(STATIC_PRODUCTS_DIR, exist_ok=True)

def process_product_image(src_path, dest_slug, bg_threshold=28.0):
    print(f"Processing {dest_slug} from {src_path}...")
    img = Image.open(src_path)

    # Convert to RGBA
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        img_rgba = img.convert('RGBA')
        alpha_channel = np.array(img_rgba)[:, :, 3]
        if np.any(alpha_channel < 250):
            proc_img = img_rgba
        else:
            proc_img = None
    else:
        proc_img = None

    if proc_img is None:
        img_rgba = img.convert('RGBA')
        # Downscale huge images for fast processing
        img_rgba.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        arr = np.array(img_rgba, dtype=np.float32)
        h, w, _ = arr.shape

        # Sample corners
        corner_samples = np.concatenate([
            arr[:30, :30, :3].reshape(-1, 3),
            arr[:30, -30:, :3].reshape(-1, 3),
            arr[-30:, :30, :3].reshape(-1, 3),
            arr[-30:, -30:, :3].reshape(-1, 3)
        ])
        bg_color = np.median(corner_samples, axis=0)

        color_dist = np.linalg.norm(arr[:, :, :3] - bg_color, axis=2)
        whiteness_diff = np.max(255.0 - arr[:, :, :3], axis=2)
        bg_lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]

        if bg_lum > 190:
            is_bg = (color_dist < bg_threshold) | (whiteness_diff < 14.0)
            alpha = np.ones((h, w), dtype=np.float32) * 255.0
            alpha[is_bg] = np.clip((color_dist[is_bg] - 10.0) / 18.0 * 255.0, 0, 255)
            alpha[whiteness_diff < 8.0] = 0.0
        else:
            # Non-white background (e.g. neutral studio gray)
            is_bg = color_dist < bg_threshold
            alpha = np.ones((h, w), dtype=np.float32) * 255.0
            alpha[is_bg] = np.clip((color_dist[is_bg] - 12.0) / 16.0 * 255.0, 0, 255)

        res_arr = np.array(img_rgba)
        res_arr[:, :, 3] = alpha.astype(np.uint8)
        proc_img = Image.fromarray(res_arr)

    # Crop to bounding box of content (opaque pixels)
    bbox = proc_img.getbbox()
    if bbox:
        cropped = proc_img.crop(bbox)
    else:
        cropped = proc_img

    # Place in 1000x1000 square with 8% margin
    canvas_size = (1000, 1000)
    canvas = Image.new('RGBA', canvas_size, (0, 0, 0, 0))

    max_w, max_h = 840, 840
    orig_w, orig_h = cropped.size
    ratio = min(max_w / orig_w, max_h / orig_h)
    new_w, new_h = max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio))

    resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
    pos_x = (canvas_size[0] - new_w) // 2
    pos_y = (canvas_size[1] - new_h) // 2
    canvas.paste(resized, (pos_x, pos_y), resized)

    # Save full WebP
    dest_path = os.path.join(STATIC_PRODUCTS_DIR, f"{dest_slug}.webp")
    canvas.save(dest_path, 'WEBP', quality=90)

    # Save 128x128 thumbnail
    thumb_path = os.path.join(STATIC_PRODUCTS_DIR, f"{dest_slug}_thumb.webp")
    thumb = canvas.resize((128, 128), Image.Resampling.LANCZOS)
    thumb.save(thumb_path, 'WEBP', quality=85)

    print(f"SUCCESS: {dest_slug}.webp ({os.path.getsize(dest_path)} bytes) & thumbnail created.")
    return dest_path

def main():
    brain_dir = r"C:\Users\narne\.gemini\antigravity\brain\2911eaab-ccbd-49fd-8257-78536781a9ea"
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp_test')

    tasks = [
        # 1. Xiaomi Redmi Note 13 Pro+ 5G
        (os.path.join(brain_dir, "redmi_note_13_pro_plus_1795321823421.jpg"), "xiaomi-redmi-note-13-pro-5g", 30.0),
        # 2. Mi TV 43" 4K Google TV
        (os.path.join(brain_dir, "mi_tv_43_inch_4k_1795321841906.jpg"), "mi-tv-43-4k-google-tv", 30.0),
        # 3. LG 55" OLED 4K Smart Cinema TV
        (os.path.join(brain_dir, "lg_55_inch_oled_tv_1795321861350.jpg"), "lg-55-oled-4k-smart-cinema-tv", 30.0),
        # 4. Samsung 65" Neo QLED 4K TV
        (os.path.join(brain_dir, "samsung_neo_qled_tv_1795321835020.jpg"), "samsung-65-neo-qled-4k-tv", 30.0),
        # 5. Sony Bravia 55" 4K Google TV
        (os.path.join(brain_dir, "sony_bravia_55_tv_1795321855176.jpg"), "sony-bravia-55-4k-google-tv", 30.0),
        # 6. Anker 65W GaN Fast Charger
        (os.path.join(brain_dir, "anker_65w_gan_charger_1795321874701.jpg"), "anker-65w-gan-fast-charger", 30.0),
        # 7. Apple iPad Air 11" M2 128GB
        (os.path.join(temp_dir, "ipad_air_4.png"), "apple-ipad-air-11-m2-128gb", 30.0),
        # 8. Nintendo Switch OLED Model
        (os.path.join(temp_dir, "switch_oled.png"), "nintendo-switch-oled-model", 30.0),
        # 9. Dyson V12 Detect Slim Vacuum
        (os.path.join(temp_dir, "dyson_v10.jpg"), "dyson-v12-detect-slim-vacuum", 32.0),
        # 10. TP-Link Archer AX73 WiFi 6
        (os.path.join(temp_dir, "tplink_ax.jpg"), "tp-link-archer-ax73-wifi-6", 30.0),
    ]

    for src, slug, threshold in tasks:
        if os.path.exists(src):
            process_product_image(src, slug, threshold)
        else:
            print(f"WARNING: File not found {src}")

if __name__ == '__main__':
    main()
