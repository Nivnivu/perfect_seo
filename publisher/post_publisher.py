"""Orchestrate the full publishing flow: parse output → upload images → insert/update post."""
from publisher.tiptap_converter import parse_gemini_output
from publisher.supabase_client import upload_image
from publisher.mongodb_client import get_master_user_id, insert_blog_post, update_blog_post


def publish_blog_post(gemini_output, desktop_image_bytes, mobile_image_bytes, config):
    """
    Full publishing pipeline:
    1. Parse Gemini output into title, subtitle, body
    2. Convert body markdown to TipTap JSON
    3. Get userId from MongoDB
    4. Upload images to Supabase
    5. Insert post to MongoDB
    Returns inserted post _id
    """
    # 1. Parse Gemini output
    print("  [publish] Parsing Gemini output...")
    parsed = parse_gemini_output(gemini_output)

    if not parsed["title"]:
        raise ValueError("Failed to parse title from Gemini output")
    if not parsed["body_tiptap"]:
        raise ValueError("Failed to parse/convert body from Gemini output")

    print(f"  [publish] Title: {parsed['title']}")
    print(f"  [publish] Subtitle: {parsed['subtitle'][:80]}...")

    # 2. Get userId (optional — some collections don't have users)
    user_id = get_master_user_id(config)
    if user_id:
        print(f"  [publish] Using userId: {user_id}")
    else:
        print("  [publish] No master user found, publishing without userId")

    # 3. Upload images to Supabase
    image1_url = ""
    image2_url = ""
    # Use storage_user_id from config if set (e.g. for projects without a master user),
    # then fall back to the actual master user_id, then collection name.
    upload_id = config.get("supabase", {}).get("storage_user_id") or user_id or config["mongodb"]["collection"]

    if desktop_image_bytes:
        print("  [publish] Uploading desktop image to Supabase...")
        image1_url = upload_image(desktop_image_bytes, upload_id, config)
        print(f"  [publish] Desktop image: {image1_url}")

    if mobile_image_bytes:
        print("  [publish] Uploading mobile image to Supabase...")
        image2_url = upload_image(mobile_image_bytes, upload_id, config)
        print(f"  [publish] Mobile image: {image2_url}")

    # 4. Insert to MongoDB
    print("  [publish] Inserting blog post to MongoDB...")
    post_data = {
        "title": parsed["title"],
        "subtitle": parsed["subtitle"],
        "body": parsed["body_tiptap"],
        "image1Url": image1_url,
        "image2Url": image2_url,
    }
    if user_id:
        post_data["userId"] = user_id

    post_id = insert_blog_post(post_data, config)
    print(f"  [publish] Post inserted with _id: {post_id}")

    # Ping GSC sitemap after every publish so Google indexes the new post faster
    if config.get("search_console"):
        try:
            from tools.search_console import ping_sitemap
            ping_sitemap(config)
        except Exception as e:
            print(f"  [publish] Sitemap ping failed (non-critical): {e}")

    return {
        "post_id": post_id,
        "title": parsed["title"],
        "subtitle": parsed["subtitle"],
        "slug": parsed["slug"],
    }


def update_post_images(post_id, desktop_image_bytes, mobile_image_bytes, config):
    """
    Upload images to Supabase and update only the image fields of a blog post.
    No content parsing — only touches image1Url / image2Url.
    """
    user_id = get_master_user_id(config)
    upload_id = config.get("supabase", {}).get("storage_user_id") or user_id or config["mongodb"]["collection"]

    update_fields = {}
    if desktop_image_bytes:
        print(f"  [images] Uploading desktop image...")
        update_fields["image1Url"] = upload_image(desktop_image_bytes, upload_id, config)
        print(f"  [images] Desktop image: {update_fields['image1Url']}")
    if mobile_image_bytes:
        print(f"  [images] Uploading mobile image...")
        update_fields["image2Url"] = upload_image(mobile_image_bytes, upload_id, config)
        print(f"  [images] Mobile image: {update_fields['image2Url']}")

    if update_fields:
        modified = update_blog_post(post_id, update_fields, config)
        print(f"  [images] Updated post {post_id}: {modified} document(s) modified")
    return update_fields


def update_existing_post(post_id, gemini_output, desktop_image_bytes, mobile_image_bytes, config, preserve_title=None, subtitle_only=False):
    """
    Update an existing blog post:
    1. Parse rewritten Gemini output
    2. Upload new images to Supabase (if provided)
    3. Update the post in MongoDB

    preserve_title: force this title regardless of what Gemini returned (prevents URL changes).
    subtitle_only: only update the meta description (subtitle), never touch body or images.
                   Used for ctr_opportunity posts that rank on page 1 but have low CTR.
    """
    print(f"  [update] Parsing rewritten output for post {post_id}...")
    parsed = parse_gemini_output(gemini_output)

    if not parsed["subtitle"]:
        raise ValueError("Failed to parse meta description from rewritten output")

    # subtitle_only mode: only update meta description, never touch body or images
    if subtitle_only:
        title = preserve_title or parsed["title"]
        print(f"  [update] SUBTITLE-ONLY mode — updating meta description for: {title}")
        print(f"  [update] New meta: {parsed['subtitle'][:100]}")
        modified = update_blog_post(post_id, {"subtitle": parsed["subtitle"]}, config)
        print(f"  [update] Updated subtitle for post {post_id}: {modified} document(s) modified")
        return {
            "post_id": post_id,
            "title": title,
            "modified": modified,
        }

    if not parsed["body_tiptap"]:
        raise ValueError("Failed to parse/convert body from rewritten output")

    # Safety net: ALWAYS preserve original title — title = URL slug in the CMS.
    # Changing the title changes the URL → 404 → loses all rankings.
    if preserve_title:
        print(f"  [update] PROTECTED title — keeping: {preserve_title}")
        parsed["title"] = preserve_title

    print(f"  [update] New title: {parsed['title']}")

    user_id = get_master_user_id(config)
    upload_id = config.get("supabase", {}).get("storage_user_id") or user_id or config["mongodb"]["collection"]

    update_fields = {
        "title": parsed["title"],
        "subtitle": parsed["subtitle"],
        "body": parsed["body_tiptap"],
    }

    if desktop_image_bytes:
        print("  [update] Uploading new desktop image...")
        update_fields["image1Url"] = upload_image(desktop_image_bytes, upload_id, config)
        print(f"  [update] Desktop image: {update_fields['image1Url']}")

    if mobile_image_bytes:
        print("  [update] Uploading new mobile image...")
        update_fields["image2Url"] = upload_image(mobile_image_bytes, upload_id, config)
        print(f"  [update] Mobile image: {update_fields['image2Url']}")

    modified = update_blog_post(post_id, update_fields, config)
    print(f"  [update] Updated post {post_id}: {modified} document(s) modified")

    return {
        "post_id": post_id,
        "title": parsed["title"],
        "modified": modified,
    }
