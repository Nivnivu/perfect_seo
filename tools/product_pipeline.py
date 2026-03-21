"""
Product pipeline utilities:
- Download product images from external URLs
- Match products to GSC performance data
- History tracking (skip already-processed products)
"""
import os
import re
import json
from datetime import datetime, timezone
from urllib.parse import unquote


# ─── History ──────────────────────────────────────────────────────────────────

def _get_product_history_path(config):
    collection = config["mongodb"]["collection"]
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{collection}_products_history.json")


def load_product_history(config):
    path = _get_product_history_path(config)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def record_product_update(product_id, title, config):
    history = load_product_history(config)
    history[str(product_id)] = {
        "title": title,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path = _get_product_history_path(config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ─── GSC Matching ─────────────────────────────────────────────────────────────

def _title_to_slug(title):
    """Convert a Hebrew product title to a URL slug (spaces → hyphens, lowercase)."""
    slug = title.strip().lower()
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"[^\u0590-\u05FF\w\-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def match_product_to_gsc(product, gsc_data, config):
    """
    Find the GSC URL for a product.
    Strategy:
      1. Reconstruct slug from title (more reliable than truncated MongoDB slug)
      2. Try with and without www, with /products/ prefix
    Returns (url, metrics_dict) or (None, None).
    """
    domain = config["site"]["domain"]
    title = product.get("title", "")
    slug = _title_to_slug(title)

    candidates = [
        f"https://www.{domain}/products/{slug}",
        f"https://{domain}/products/{slug}",
        f"https://www.{domain}/products/{slug}/",
        f"https://{domain}/products/{slug}/",
    ]

    # Also try the stored MongoDB slug (URL-decoded) as a prefix match
    raw_slug = unquote(product.get("slug", ""))
    if raw_slug:
        for url, metrics in gsc_data.items():
            if f"/products/{raw_slug}" in url or url.rstrip("/").endswith(raw_slug):
                return url, metrics

    for url in candidates:
        if url in gsc_data:
            return url, gsc_data[url]

    return None, None


def get_product_gsc_context(product, gsc_data, page_queries, config):
    """
    Classify a product page using the same GSC categories as blog posts.
    Returns a gsc_context dict (category, top_queries, metrics).
    """
    from tools.search_console import classify_page_seo
    url, _ = match_product_to_gsc(product, gsc_data, config)
    if url:
        return url, classify_page_seo(url, gsc_data, page_queries, config)
    return None, {"category": "not_indexed", "top_queries": [], "metrics": {}, "update_priority": 4}


# ─── Image Download + Branding ────────────────────────────────────────────────

def download_image(url, timeout=20):
    """Download an image from a URL and return raw bytes. Returns None on failure."""
    import requests
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"  [product-img] Failed to download {url[:80]}: {e}")
        return None


def brand_product_image(image_bytes, config):
    """
    Apply Pawly branding to a product image:
    - Resize to square (1:1) padding with white background
    - Add thin brand-color border
    - Composite Pawly logo watermark (bottom-right)
    Returns branded JPEG bytes.
    """
    import io
    from PIL import Image, ImageDraw

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    # Make square with white background (don't crop — pad)
    size = max(img.width, img.height)
    square = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    offset_x = (size - img.width) // 2
    offset_y = (size - img.height) // 2
    square.paste(img, (offset_x, offset_y), img if img.mode == "RGBA" else None)

    # Thin brand-color border (Pawly green-ish brown: #7B5E3A)
    border = max(4, size // 120)
    draw = ImageDraw.Draw(square)
    draw.rectangle([0, 0, size - 1, size - 1], outline=(123, 94, 58), width=border)

    # Convert to RGB for JPEG
    bg = Image.new("RGB", square.size, (255, 255, 255))
    bg.paste(square, mask=square.split()[3])
    branded = bg

    # Composite logo
    logo_rel = config.get("site", {}).get("logo", "")
    base_dir = os.path.dirname(os.path.dirname(__file__))
    logo_path = os.path.join(base_dir, logo_rel) if logo_rel else None

    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            target_w = int(branded.width * 0.15)
            scale = target_w / logo.width
            target_h = int(logo.height * scale)
            logo = logo.resize((target_w, target_h), Image.LANCZOS)
            r, g, b, a = logo.split()
            a = a.point(lambda x: int(x * 0.75))
            logo = Image.merge("RGBA", (r, g, b, a))
            branded = branded.convert("RGBA")
            padding = int(branded.width * 0.025)
            x = branded.width - target_w - padding
            y = branded.height - target_h - padding
            branded.paste(logo, (x, y), logo)
            branded = branded.convert("RGB")
            print(f"  [product-img] Logo composited")
        except Exception as e:
            print(f"  [product-img] Logo error: {e}")

    # Compress to JPEG ≤500KB
    quality = 90
    while quality >= 20:
        buf = io.BytesIO()
        branded.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() / 1024 <= 500:
            return buf.getvalue()
        quality -= 10

    buf = io.BytesIO()
    branded.save(buf, format="JPEG", quality=20, optimize=True)
    return buf.getvalue()


# ─── Content Helpers ──────────────────────────────────────────────────────────

def strip_external_images(html):
    """Remove <img> tags that point to external domains (zoostore, etc.) from HTML."""
    # Remove entire <img ...> or <p><img ...></p> blocks
    html = re.sub(r'<img[^>]*>', '', html, flags=re.IGNORECASE)
    # Clean up empty <p></p> left behind
    html = re.sub(r'<p>\s*</p>', '', html, flags=re.IGNORECASE)
    return html.strip()


def html_to_text(html):
    """Strip HTML tags to get plain text for display/analysis."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
