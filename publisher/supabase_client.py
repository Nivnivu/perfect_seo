"""Upload images to Supabase storage matching blog-poster's bucket structure."""
import uuid
import io
import os
from PIL import Image

# Module-level logo path, set by upload_image from config
_logo_path = None


def _get_logo_path(config=None):
    """Get logo path from config or fall back to default."""
    if config:
        logo_rel = config.get("site", {}).get("logo", "")
        if logo_rel:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            path = os.path.join(base_dir, logo_rel)
            if os.path.exists(path):
                print(f"  [logo] Using logo: {path}")
                return path
            else:
                print(f"  [logo] WARNING: Logo not found at {path}")
    # Fallback to default
    default = os.path.join(os.path.dirname(__file__), "..", "companies_logos", "pawlyLogo.png")
    if os.path.exists(default):
        print(f"  [logo] Using default logo: {default}")
        return default
    print("  [logo] WARNING: No logo file found")
    return None


def _composite_logo(img, logo_path):
    """Overlay logo onto bottom-right corner of the image."""
    if not logo_path or not os.path.exists(logo_path):
        print("  [logo] Skipping logo composite — no logo path")
        return img

    try:
        logo = Image.open(logo_path).convert("RGBA")
    except Exception as e:
        print(f"  [logo] ERROR: Failed to open logo {logo_path}: {e}")
        return img

    try:
        # Scale logo to ~12% of image width
        target_w = int(img.width * 0.12)
        scale = target_w / logo.width
        target_h = int(logo.height * scale)
        logo = logo.resize((target_w, target_h), Image.LANCZOS)

        # Apply semi-transparency
        r, g, b, a = logo.split()
        a = a.point(lambda x: int(x * 0.7))  # ~70% opacity
        logo = Image.merge("RGBA", (r, g, b, a))

        # Ensure base image has alpha channel for compositing
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Position: bottom-right with padding
        padding = int(img.width * 0.02)
        x = img.width - target_w - padding
        y = img.height - target_h - padding

        img.paste(logo, (x, y), logo)
        print(f"  [logo] Logo composited successfully")
    except Exception as e:
        print(f"  [logo] ERROR during compositing: {e}")

    return img


def _compress_image(image_bytes, logo_path=None, max_size_kb=500, format="JPEG"):
    """Compress image to stay under max_size_kb, with logo composited."""
    img = Image.open(io.BytesIO(image_bytes))

    # Composite logo onto image
    if logo_path:
        img = _composite_logo(img, logo_path)

    # Convert RGBA to RGB for JPEG
    if img.mode == "RGBA" and format == "JPEG":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg

    quality = 90
    while quality >= 20:
        buffer = io.BytesIO()
        img.save(buffer, format=format, quality=quality, optimize=True)
        size_kb = buffer.tell() / 1024
        if size_kb <= max_size_kb:
            return buffer.getvalue()
        quality -= 10

    # Return best effort
    buffer = io.BytesIO()
    img.save(buffer, format=format, quality=20, optimize=True)
    return buffer.getvalue()


def upload_image(image_bytes, user_id, config):
    """
    Upload image bytes to Supabase storage.
    Returns the filename (not full URL) - matching how blog-poster stores image references.
    """
    from supabase import create_client

    supabase_url = config["supabase"]["url"]
    supabase_key = config["supabase"]["key"]
    bucket = config["supabase"]["bucket"]

    client = create_client(supabase_url, supabase_key)

    # Get logo path from config
    logo_path = _get_logo_path(config)

    # Compress image + add logo
    compressed = _compress_image(image_bytes, logo_path=logo_path)

    # Generate UUID filename
    filename = f"{uuid.uuid4()}.jpg"
    storage_path = f"{user_id}/{filename}"

    # Upload
    client.storage.from_(bucket).upload(
        path=storage_path,
        file=compressed,
        file_options={"content-type": "image/jpeg"},
    )

    # Return just the filename (blog-poster stores filename, not full URL)
    return filename
