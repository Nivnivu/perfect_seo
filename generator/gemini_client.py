import base64
from google import genai
from google.genai import types
from generator.prompts import build_blog_prompt, build_edit_prompt, build_rewrite_prompt, build_fix_prompt, build_static_page_prompt, build_image_prompt, build_recovery_rewrite_prompt, build_product_prompt, build_differentiation_prompt, build_subtitle_only_prompt


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


def generate_blog_subtitle(post_data, config, site_context=None):
    """Generate only a new meta description for a ctr_opportunity post (subtitle_only mode).
    Far cheaper than a full rewrite — sends a short prompt and returns parse_gemini_output-compatible output."""
    client = _get_client(config)
    prompt = build_subtitle_only_prompt(post_data, config, site_context=site_context)
    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to generate meta description: {e}"


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


def generate_recovery_rewrite(post_data, ranking_queries, config, site_context=None):
    """
    Generate a recovery rewrite for a post that lost rankings after being updated.
    Uses the GSC queries the page ranked for to reverse-engineer what Google expected.
    """
    client = _get_client(config)
    prompt = build_recovery_rewrite_prompt(post_data, ranking_queries, config, site_context=site_context)

    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to generate recovery rewrite: {e}"


def rewrite_static_page(page_title, page_id, current_text, config, site_context=None, gsc_context=None):
    """Rewrite and improve a static page using Gemini."""
    client = _get_client(config)
    prompt = build_static_page_prompt(page_title, page_id, current_text, config, site_context=site_context, gsc_context=gsc_context)

    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to rewrite static page: {e}"


def classify_cannibalization(winner_title, loser_title, shared_query, config):
    """
    Ask Gemini whether two posts are truly duplicate (same topic/intent)
    or just related (different topics that share a keyword).

    Returns: "duplicate" | "related" | "unknown"
    """
    client = _get_client(config)
    prompt = f"""You are an SEO expert. Two blog posts are both ranking for the same search query.
Decide if they are TRUE DUPLICATES (same topic, same user intent) or just RELATED (different topics that share a keyword).

Shared query: "{shared_query}"
Post A (winner): "{winner_title}"
Post B (loser):  "{loser_title}"

Rules:
- TRUE DUPLICATE: both posts answer the exact same question / target the same course/service/topic
- RELATED: each post covers a distinct topic that naturally mentions the shared keyword

Reply with ONLY one word: DUPLICATE or RELATED"""

    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        answer = response.text.strip().upper()
        if "DUPLICATE" in answer:
            return "duplicate"
        if "RELATED" in answer:
            return "related"
        return "unknown"
    except Exception:
        return "unknown"


def rewrite_for_differentiation(post, winner_post, cluster_query, config):
    """
    Rewrite a cannibalized loser post to target a different sub-keyword than the winner.
    Eliminates keyword cannibalization by giving each post a unique focus.
    """
    client = _get_client(config)
    prompt = build_differentiation_prompt(post, winner_post, cluster_query, config)
    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to generate differentiation rewrite: {e}"


def rewrite_product(product_data, gsc_context, config, site_context=None):
    """Generate SEO-optimized content for a product page."""
    client = _get_client(config)
    prompt = build_product_prompt(product_data, gsc_context, config, site_context=site_context)
    try:
        response = client.models.generate_content(
            model=config["gemini"]["model"],
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Gemini Error] Failed to rewrite product: {e}"


def _topic_to_visual_concept(topic, client, model):
    """
    Convert a Hebrew blog topic to a concise English visual concept for Imagen.

    Instead of a literal translation (which can cause Imagen to render brand names or
    course titles as text overlays), this produces a short scene description like
    "professional person studying at desk with books and laptop" that Imagen
    can render as pure photography with no text.
    """
    try:
        response = client.models.generate_content(
            model=model,
            contents=(
                "Convert this Hebrew blog post topic into a SHORT English visual scene description "
                "for a stock photo prompt (max 15 words). "
                "Describe WHAT YOU WOULD SEE IN A PHOTO — people, objects, setting, actions. "
                "Do NOT include any brand names, course names, company names, or text that could appear in an image. "
                "Do NOT translate literally. Focus on the visual scene only.\n\n"
                f"Topic: {topic}\n\n"
                "Visual scene (English only, max 15 words):"
            ),
        )
        concept = response.text.strip().strip('"').strip("'").strip(".")
        if concept:
            return concept
    except Exception as e:
        print(f"  [imagen] Concept generation failed, using fallback: {e}")
    # Fallback: simple translation without brand names
    return "professional person working in modern office environment"


def generate_blog_images(topic, title, config, site_context=None):
    """
    Generate a single square (1:1) blog post image using Gemini Imagen.
    Returns dict: {"desktop": bytes, "mobile": bytes} — both keys hold the same image bytes.

    Using one image for both avoids the desktop generation failure issue and
    a 1:1 square works cleanly in both blog post header and mobile card layouts.
    """
    client = _get_client(config)
    image_model = config["gemini"].get("image_model", "imagen-4.0-fast-generate-001")
    text_model = config["gemini"]["model"]

    # Convert topic to a visual concept (prevents brand names rendering as text in image)
    visual_concept = _topic_to_visual_concept(topic, client, text_model)
    print(f"  [imagen] Topic: '{topic}' → visual concept: '{visual_concept}'")

    prompt = build_image_prompt(visual_concept, config=config, site_context=site_context)

    try:
        response = client.models.generate_images(
            model=image_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
            ),
        )
        if response.generated_images:
            img_bytes = response.generated_images[0].image.image_bytes
            print(f"  [imagen] Generated image ({len(img_bytes) // 1024}KB) — used for both desktop and mobile")
            return {"desktop": img_bytes, "mobile": img_bytes}
        else:
            print(f"  [imagen] No image generated")
            return {"desktop": None, "mobile": None}
    except Exception as e:
        print(f"  [imagen] Error generating image: {e}")
        return {"desktop": None, "mobile": None}
