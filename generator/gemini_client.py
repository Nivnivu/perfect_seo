import base64
from google import genai
from google.genai import types
from generator.prompts import build_blog_prompt, build_edit_prompt, build_rewrite_prompt, build_fix_prompt, build_static_page_prompt, build_image_prompt


def _get_client(config):
    return genai.Client(api_key=config["gemini"]["api_key"])


def generate_blog_post(topic_data, config, site_context=None):
    """Generate a new SEO-optimized Hebrew blog post using Gemini."""
    client = _get_client(config)
    prompt = build_blog_prompt(topic_data, config, site_context=site_context)

    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to generate blog post: {e}"


def suggest_post_edits(post_data, competitor_summary, all_keywords, config, site_context=None):
    """Generate edit suggestions for an existing blog post using Gemini."""
    client = _get_client(config)
    prompt = build_edit_prompt(post_data, competitor_summary, all_keywords, config, site_context=site_context)

    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to generate edit suggestions: {e}"


def rewrite_blog_post(post_data, competitor_summary, all_keywords, config, site_context=None):
    """Rewrite and expand an existing blog post using Gemini."""
    client = _get_client(config)
    prompt = build_rewrite_prompt(post_data, competitor_summary, all_keywords, config, site_context=site_context)

    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to rewrite blog post: {e}"


def apply_post_fixes(current_post, user_feedback, config):
    """Apply minor fixes to a blog post based on user feedback."""
    client = _get_client(config)
    prompt = build_fix_prompt(current_post, user_feedback, config)

    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to apply fixes: {e}"


def rewrite_static_page(page_title, page_id, current_text, config, site_context=None):
    """Rewrite and improve a static page using Gemini."""
    client = _get_client(config)
    prompt = build_static_page_prompt(page_title, page_id, current_text, config, site_context=site_context)

    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to rewrite static page: {e}"


def _translate_topic(topic, client, model):
    """Translate a Hebrew topic to English for Imagen prompts."""
    try:
        response = client.models.generate_content(
            model=model,
            contents=f"Translate the following Hebrew text to English. Return ONLY the English translation, nothing else.\n\n{topic}",
        )
        translated = response.text.strip().strip('"').strip("'")
        if translated:
            return translated
    except Exception as e:
        print(f"  [imagen] Translation failed, using original topic: {e}")
    return topic


def generate_blog_images(topic, title, config, site_context=None):
    """
    Generate desktop and mobile blog header images using Gemini Imagen.
    Returns dict: {"desktop": bytes, "mobile": bytes}
    """
    client = _get_client(config)
    image_model = config["gemini"].get("image_model", "imagen-4")
    text_model = config["gemini"]["model"]
    results = {}

    # Translate Hebrew topic to English for better Imagen results
    english_topic = _translate_topic(topic, client, text_model)
    print(f"  [imagen] Topic: '{topic}' → '{english_topic}'")

    for variant in ["desktop", "mobile"]:
        prompt = build_image_prompt(english_topic, title, variant, config=config, site_context=site_context)
        ratio = "4:3" if variant == "desktop" else "1:1"
        try:
            response = client.models.generate_images(
                model=image_model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=ratio,
                ),
            )
            if response.generated_images:
                img = response.generated_images[0]
                results[variant] = img.image.image_bytes
                print(f"  [imagen] Generated {variant} image ({len(img.image.image_bytes) // 1024}KB)")
            else:
                print(f"  [imagen] No image generated for {variant}")
                results[variant] = None
        except Exception as e:
            print(f"  [imagen] Error generating {variant} image: {e}")
            results[variant] = None

    return results
