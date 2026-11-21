"""
Electrodesk - Professional Product Image Studio Processor
Converts white studio product photos into transparent antialiased 1000x1000 WebP assets and 128x128 thumbnails.
"""

import os
import glob
from PIL import Image
import numpy as np

STATIC_PRODUCTS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images', 'products')

def convert_studio_to_transparent_webp(src_path, dest_slug, target_dir=STATIC_PRODUCTS_DIR):
    os.makedirs(target_dir, exist_ok=True)
    img = Image.open(src_path)

    # If the image already has a transparent alpha channel, preserve it
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        img_rgba = img.convert('RGBA')
        alpha_channel = np.array(img_rgba)[:, :, 3]
        # Check if it actually contains transparent pixels
        if np.any(alpha_channel < 250):
            proc_img = img_rgba
        else:
            proc_img = None
    else:
        proc_img = None

    if proc_img is None:
        img_rgba = img.convert('RGBA')
        arr = np.array(img_rgba, dtype=np.float32)

        # Sample corners to determine background luminance
        h, w, _ = arr.shape
        corner_samples = np.concatenate([
            arr[:40, :40, :3].reshape(-1, 3),
            arr[:40, -40:, :3].reshape(-1, 3),
            arr[-40:, :40, :3].reshape(-1, 3),
            arr[-40:, -40:, :3].reshape(-1, 3)
        ])
        bg_color = np.median(corner_samples, axis=0)

        # Distance of each pixel from the corner background color
        color_dist = np.linalg.norm(arr[:, :, :3] - bg_color, axis=2)
        whiteness_diff = np.max(255.0 - arr[:, :, :3], axis=2)
        bg_lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]

        if bg_lum > 200:
            is_bg = (color_dist < 32.0) | (whiteness_diff < 16.0)
            alpha = np.ones((h, w), dtype=np.float32) * 255.0
            alpha[is_bg] = np.clip((color_dist[is_bg] - 12.0) / 20.0 * 255.0, 0, 255)
            alpha[whiteness_diff < 10.0] = 0.0
        else:
            alpha = np.clip((whiteness_diff - 10.0) / 25.0 * 255.0, 0, 255)

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

    # Scale proportionally to fit within 840x840
    max_w, max_h = 840, 840
    orig_w, orig_h = cropped.size
    ratio = min(max_w / orig_w, max_h / orig_h)
    new_w, new_h = max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio))

    resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
    pos_x = (canvas_size[0] - new_w) // 2
    pos_y = (canvas_size[1] - new_h) // 2
    canvas.paste(resized, (pos_x, pos_y), resized)

    # Save full WebP
    dest_path = os.path.join(target_dir, f"{dest_slug}.webp")
    canvas.save(dest_path, 'WEBP', quality=90)

    # Save 128x128 thumbnail
    thumb_path = os.path.join(target_dir, f"{dest_slug}_thumb.webp")
    thumb = canvas.resize((128, 128), Image.Resampling.LANCZOS)
    thumb.save(thumb_path, 'WEBP', quality=85)

    print(f"Processed: {src_path} -> {dest_path} ({os.path.getsize(dest_path)} bytes)")
    return dest_path

if __name__ == '__main__':
    # Test on already generated images
    brain_dir = r"C:\Users\narne\.gemini\antigravity\brain\2911eaab-ccbd-49fd-8257-78536781a9ea"
    mapping = {
        'asus-rog-zephyrus-g16': 'asus_rog_zephyrus_g16_*.jpg',
        'dell-inspiron-15-16gb-ssd': 'dell_inspiron_15_*.jpg',
        'hp-pavilion-15-core-i7-16gb': 'hp_pavilion_15_*.jpg',
        'apple-macbook-air-13-m2': 'macbook_air_m2_*.jpg',
        'sony-wh-1000xm5-headphones': 'test_sony_*.jpg',
        'microsoft-xbox-series-x-1tb': 'xbox_series_x_*.jpg',
        'oneplus-12-5g-256gb': 'oneplus_12_*.jpg',
    }

    for slug, pattern in mapping.items():
        matches = glob.glob(os.path.join(brain_dir, pattern))
        if matches:
            latest = sorted(matches)[-1]
            convert_studio_to_transparent_webp(latest, slug)
