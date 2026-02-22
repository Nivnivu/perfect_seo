import time
import json
import subprocess
import os
import re
from datetime import datetime
from collections import Counter

from tools.autocomplete import get_autocomplete_expanded
from tools.trends import get_trends_data
from tools.serp_scraper import scrape_serp
from tools.competitor_analyzer import analyze_competitors, summarize_competitor_patterns
from tools.site_context import scrape_site_context
from generator.gemini_client import generate_blog_post, rewrite_blog_post, apply_post_fixes, rewrite_static_page, generate_blog_images
from publisher.post_publisher import publish_blog_post, update_existing_post, update_post_images
from publisher.mongodb_client import fetch_static_pages, update_static_page, fetch_posts_missing_images, fetch_all_blog_posts
from publisher.tiptap_converter import parse_gemini_output, extract_text_from_tiptap, markdown_to_static_tiptap


# ═══════════════════════════════════════════════
# Update History — prevent re-updating same posts
# ═══════════════════════════════════════════════

def _get_history_path(config):
    """Return path to the update history file for this site."""
    collection = config["mongodb"]["collection"]
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{collection}_update_history.json")


def _load_update_history(config):
    """Load set of previously updated post IDs."""
    path = _get_history_path(config)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_update_history(history, config):
    """Save update history to disk."""
    path = _get_history_path(config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _record_updated_post(post_id, title, config):
    """Record a successfully updated post so it's skipped in future runs."""
    history = _load_update_history(config)
    history[str(post_id)] = {
        "title": title,
        "updated_at": datetime.now().isoformat(),
    }
    _save_update_history(history, config)


def _is_already_updated(post_id, config):
    """Check if a post was already updated in a previous run."""
    history = _load_update_history(config)
    return str(post_id) in history


# ═══════════════════════════════════════════════
# MongoDB Post Analysis (replaces web scraping)
# ═══════════════════════════════════════════════

def _extract_headings(node, headings):
    """Walk TipTap JSON and collect h1/h2/h3 text."""
    if isinstance(node, dict):
        ntype = node.get("type", "")
        if ntype in ("h1", "h2", "h3"):
            text = extract_text_from_tiptap(node)
            if text.strip():
                headings[ntype].append(text.strip())
        for key in ("children", "content"):
            if key in node and isinstance(node[key], list):
                for child in node[key]:
                    _extract_headings(child, headings)
    elif isinstance(node, list):
        for item in node:
            _extract_headings(item, headings)


def _analyze_mongo_posts(mongo_posts):
    """Analyze posts fetched from MongoDB, extracting SEO data from TipTap body."""
    results = []
    for post in mongo_posts:
        body = post.get("body", "")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                body = {}

        content_text = extract_text_from_tiptap(body)

        headings = {"h1": [], "h2": [], "h3": []}
        _extract_headings(body, headings)

        words = re.findall(r"[\u0590-\u05FF]{2,}", content_text)
        word_counts = Counter(words)
        keywords_found = [w for w, c in word_counts.most_common(30)]

        results.append({
            "_id": post["_id"],
            "title": post.get("title", ""),
            "meta_description": post.get("subtitle", ""),
            "headings": headings,
            "word_count": len(content_text.split()),
            "content_text": content_text[:3000],
            "keywords_found": keywords_found,
            "keywords_missing": [],
            "image1Url": post.get("image1Url", ""),
            "image2Url": post.get("image2Url", ""),
        })
    return results


def send_whatsapp_message(message_text, config):
    """
    Send WhatsApp message and wait for reply via Node.js script.
    Returns: ("approved", None) | ("rejected", None) | ("feedback", "user text") | ("error", None)
    """
    phone = config.get("whatsapp", {}).get("phone_number", "")
    timeout = config.get("whatsapp", {}).get("approval_timeout", 1800)

    if not phone:
        print("  [whatsapp] No phone number configured, auto-approving")
        return ("approved", None)

    whatsapp_dir = os.path.join(os.path.dirname(__file__), "whatsapp")
    script_path = os.path.join(whatsapp_dir, "send_and_wait.js")

    try:
        result = subprocess.run(
            ["node", script_path, "--phone", phone, "--message", message_text, "--timeout", str(timeout)],
            capture_output=True,
            text=True,
            timeout=timeout + 60,
            cwd=whatsapp_dir,
        )
        stdout = result.stdout.strip()
        print(f"  [whatsapp] Result: {stdout[:100]}")

        if "APPROVED" in stdout:
            return ("approved", None)
        elif "REJECTED" in stdout:
            return ("rejected", None)
        elif stdout.startswith("FEEDBACK:"):
            feedback_text = stdout[len("FEEDBACK:"):].strip()
            return ("feedback", feedback_text)
        else:
            return ("error", None)
    except subprocess.TimeoutExpired:
        print("  [whatsapp] Timeout waiting for reply")
        return ("error", None)
    except Exception as e:
        print(f"  [whatsapp] Error: {e}")
        return ("error", None)


MAX_REVIEW_ROUNDS = 3


def _format_post_for_whatsapp(gemini_output, site_name, label="פוסט חדש"):
    """Format a Gemini blog post into a full WhatsApp review message."""
    parsed = parse_gemini_output(gemini_output)
    word_count = len(parsed["body_markdown"].split()) if parsed["body_markdown"] else 0

    return (
        f"📝 *{label} לבלוג {site_name}*\n\n"
        f"*כותרת:* {parsed['title']}\n"
        f"*תיאור:* {parsed['subtitle']}\n"
        f"*אורך:* ~{word_count} מילים\n\n"
        f"--- הפוסט המלא ---\n\n"
        f"{parsed['body_markdown']}"
    )


def _review_loop(gemini_output, config, site_name, label="פוסט חדש"):
    """
    Send post to WhatsApp for review. If user sends feedback, fix and re-send.
    Returns: (final_gemini_output, approved: bool)
    """
    current_output = gemini_output

    for attempt in range(1, MAX_REVIEW_ROUNDS + 1):
        round_label = label if attempt == 1 else f"{label} (תיקון #{attempt - 1})"
        preview = _format_post_for_whatsapp(current_output, site_name, label=round_label)

        print(f"\n  Sending post for review (round {attempt}/{MAX_REVIEW_ROUNDS})...")
        status, feedback = send_whatsapp_message(preview, config)

        if status == "approved":
            return (current_output, True)
        elif status == "rejected":
            return (current_output, False)
        elif status == "feedback":
            print(f"  User feedback: {feedback[:100]}...")
            print(f"  Applying fixes with Gemini...")
            fixed = apply_post_fixes(current_output, feedback, config)
            if fixed.startswith("[Gemini Error]"):
                print(f"  {fixed}")
                print(f"  Keeping previous version")
            else:
                current_output = fixed
                print(f"  Fixes applied, re-sending for review...")
        else:
            print(f"  WhatsApp error/timeout, auto-approving")
            return (current_output, True)

    # Exhausted review rounds — auto-approve
    print(f"  Max review rounds reached, auto-approving")
    return (current_output, True)


# ═══════════════════════════════════════════════
# Shared Research Phases (used by both modes)
# ═══════════════════════════════════════════════

def run_research(seed_keywords, config):
    """
    Phases 0-3: Site context, keyword expansion, SERP analysis, content audit.
    Returns a dict with all research data needed by both modes.
    """
    lang = config["site"]["language"]
    country = config["site"]["country"]
    domain = config["site"]["domain"]
    user_agent = config["scraping"]["user_agent"]
    delay = config["scraping"]["request_delay"]
    site_name = config["site"]["name"]

    # ────────────────────────────────────────────
    # Phase 0: Site Context
    # ────────────────────────────────────────────
    print(f"\n[Phase 0] Scraping {site_name} website for context...")

    site_context = scrape_site_context(config)

    # ────────────────────────────────────────────
    # Phase 1: Keyword Expansion
    # ────────────────────────────────────────────
    print("\n[Phase 1] Expanding keywords...")

    autocomplete_data = get_autocomplete_expanded(
        seed_keywords, lang=lang, user_agent=user_agent, delay=delay
    )
    all_keywords = set(seed_keywords)
    for suggestions in autocomplete_data.values():
        all_keywords.update(suggestions)

    print(f"  Autocomplete: {len(all_keywords)} unique keywords after expansion")

    print("\n  Fetching Google Trends data...")
    keyword_list = list(all_keywords)
    trends_data = get_trends_data(keyword_list[:10], geo=country.upper())

    for rising_list in trends_data.get("rising_queries", {}).values():
        all_keywords.update(rising_list)
    for top_list in trends_data.get("top_queries", {}).values():
        all_keywords.update(top_list)

    print(f"  Total keyword universe: {len(all_keywords)} keywords")

    interest = trends_data.get("interest_over_time", {})
    keyword_scores = {}
    for kw, data_points in interest.items():
        if isinstance(data_points, list) and data_points:
            keyword_scores[kw] = sum(p["value"] for p in data_points) / len(data_points)

    top_keywords = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
    if top_keywords:
        print("\n  Top keywords by trend interest:")
        for kw, score in top_keywords[:5]:
            print(f"    {kw}: {score:.0f}")

    target_keywords = [k for k, _ in top_keywords[:5]] if top_keywords else seed_keywords[:5]

    # ────────────────────────────────────────────
    # Phase 2: SERP + Competitor Analysis
    # ────────────────────────────────────────────
    print("\n[Phase 2] Analyzing SERPs and competitors...")

    serp_results = {}
    serp_competitor_urls = []
    for kw in target_keywords:
        print(f"  Scraping SERP for: '{kw}'")
        serp = scrape_serp(kw, lang=lang, country=country, user_agent=user_agent)
        serp_results[kw] = serp
        print(f"    Found {len(serp['organic_results'])} results, "
              f"{len(serp['people_also_ask'])} PAA, "
              f"{len(serp['related_searches'])} related")

        for result in serp.get("organic_results", [])[:3]:
            url = result.get("url", "")
            if domain not in url and url not in serp_competitor_urls:
                serp_competitor_urls.append(url)

        time.sleep(delay)

    # Start with known competitors from config, then add SERP-discovered ones
    known_competitors = config.get("competitors", [])
    competitor_urls = list(known_competitors)
    seen = set(competitor_urls)
    for url in serp_competitor_urls:
        if url not in seen:
            competitor_urls.append(url)
            seen.add(url)
    competitor_urls = competitor_urls[:12]

    if known_competitors:
        print(f"\n  Known competitors from config: {len(known_competitors)}")
        print(f"  Additional from SERP: {len(competitor_urls) - len(known_competitors)}")
    print(f"  Analyzing {len(competitor_urls)} competitor pages...")
    competitor_analyses = analyze_competitors(
        competitor_urls, user_agent=user_agent, delay=delay
    )
    competitor_summary = summarize_competitor_patterns(competitor_analyses)

    print(f"  Competitor avg word count: {competitor_summary['avg_word_count']}")

    all_paa = []
    all_related = []
    for serp in serp_results.values():
        all_paa.extend(serp.get("people_also_ask", []))
        all_related.extend(serp.get("related_searches", []))
    all_paa = list(dict.fromkeys(all_paa))
    all_related = list(dict.fromkeys(all_related))
    all_keywords.update(all_related)

    # ────────────────────────────────────────────
    # Phase 3: Own Content Audit (from MongoDB)
    # ────────────────────────────────────────────
    print(f"\n[Phase 3] Auditing existing {site_name} blog posts from MongoDB...")

    raw_posts = fetch_all_blog_posts(config)
    own_posts = _analyze_mongo_posts(raw_posts)

    covered_keywords = set()
    for post in own_posts:
        covered_keywords.update(post.get("keywords_found", []))

    uncovered_keywords = all_keywords - covered_keywords
    print(f"  {len(own_posts)} existing posts analyzed")
    print(f"  {len(uncovered_keywords)} keyword topics not yet covered")

    posts_needing_updates = []
    target_wc = competitor_summary.get("avg_word_count", 1500)
    for post in own_posts:
        reasons = []
        if post.get("word_count", 0) < target_wc * 0.6:
            reasons.append(f"word count too low ({post.get('word_count', 0)} vs target {target_wc})")

        post_title_words = set(post.get("title", "").split())
        post_found = set(post.get("keywords_found", []))
        missing = []
        for kw in all_keywords:
            kw_words = set(kw.split())
            if kw_words & post_title_words and kw not in post_found:
                missing.append(kw)
        if missing:
            reasons.append("missing keywords")
            post["keywords_missing"] = missing[:10]

        if reasons:
            post["update_reasons"] = reasons
            posts_needing_updates.append(post)

    print(f"  {len(posts_needing_updates)} posts need updating")

    return {
        "site_context": site_context,
        "all_keywords": all_keywords,
        "top_keywords": top_keywords,
        "uncovered_keywords": uncovered_keywords,
        "serp_results": serp_results,
        "competitor_analyses": competitor_analyses,
        "competitor_summary": competitor_summary,
        "all_paa": all_paa,
        "own_posts": own_posts,
        "posts_needing_updates": posts_needing_updates,
    }


# ═══════════════════════════════════════════════
# Mode 1: Create New Blog Post
# ═══════════════════════════════════════════════

def run_new_pipeline(seed_keywords, config):
    """Full pipeline: research → generate new post → images → approve → publish."""
    site_name = config["site"]["name"]
    print("=" * 60)
    print(f"  {site_name} SEO BLOG ENGINE — NEW POST")
    print("=" * 60)

    research = run_research(seed_keywords, config)

    site_context = research["site_context"]
    all_keywords = research["all_keywords"]
    top_keywords = research["top_keywords"]
    uncovered_keywords = research["uncovered_keywords"]
    serp_results = research["serp_results"]
    competitor_summary = research["competitor_summary"]
    all_paa = research["all_paa"]

    # ────────────────────────────────────────────
    # Phase 4: Generate New Blog Post
    # ────────────────────────────────────────────
    print("\n[Phase 4] Generating new blog post with Gemini...")

    best_new_topic = None
    for kw, _ in top_keywords:
        if kw in uncovered_keywords:
            best_new_topic = kw
            break
    if not best_new_topic and uncovered_keywords:
        best_new_topic = list(uncovered_keywords)[0]
    if not best_new_topic:
        best_new_topic = seed_keywords[0]

    topic_serp = serp_results.get(best_new_topic, {})
    topic_data = {
        "target_keyword": best_new_topic,
        "related_keywords": [k for k in all_keywords if k != best_new_topic][:15],
        "paa_questions": topic_serp.get("people_also_ask", all_paa[:10]),
        "competitor_summary": competitor_summary,
        "serp_titles": [r["title"] for r in topic_serp.get("organic_results", [])],
    }

    print(f"\n  Generating new blog post for: '{best_new_topic}'")
    blog_post = generate_blog_post(topic_data, config, site_context=site_context)

    # ────────────────────────────────────────────
    # Phase 5: Image Generation
    # ────────────────────────────────────────────
    print("\n[Phase 5] Generating blog images...")

    images = generate_blog_images(best_new_topic, "", config, site_context=site_context)
    desktop_image = images.get("desktop")
    mobile_image = images.get("mobile")

    if desktop_image:
        print(f"  Desktop image: {len(desktop_image) // 1024}KB")
    else:
        print("  Desktop image: generation failed (will publish without)")
    if mobile_image:
        print(f"  Mobile image: {len(mobile_image) // 1024}KB")
    else:
        print("  Mobile image: generation failed (will publish without)")

    # ────────────────────────────────────────────
    # Phase 6: WhatsApp Review (approve / feedback / reject)
    # ────────────────────────────────────────────
    print("\n[Phase 6] Sending post for WhatsApp review...")

    final_post, approved = _review_loop(blog_post, config, site_name, label="פוסט חדש")

    # ────────────────────────────────────────────
    # Phase 7: Publish
    # ────────────────────────────────────────────
    if approved:
        print("\n[Phase 7] Publishing to MongoDB + Supabase...")
        try:
            result = publish_blog_post(
                gemini_output=final_post,
                desktop_image_bytes=desktop_image,
                mobile_image_bytes=mobile_image,
                config=config,
            )
            print(f"\n  Published successfully!")
            print(f"  Post ID: {result['post_id']}")
            print(f"  Title: {result['title']}")
        except Exception as e:
            print(f"\n  [publish] Error: {e}")
    else:
        print("\n[Phase 7] Skipped - post not approved")
        draft_path = os.path.join(os.path.dirname(__file__), "output", f"draft_{best_new_topic[:30]}.txt")
        os.makedirs(os.path.dirname(draft_path), exist_ok=True)
        with open(draft_path, "w", encoding="utf-8") as f:
            f.write(final_post)
        print(f"  Draft saved to: {draft_path}")

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Site context: {len(site_context.get('all_internal_links', []))} internal links, {len(site_context.get('product_names', []))} products")
    print(f"  Total keyword universe: {len(all_keywords)}")
    print(f"  SERPs analyzed: {len(serp_results)}")
    print(f"  Own posts analyzed: {len(research['own_posts'])}")
    print(f"  New blog post topic: '{best_new_topic}'")
    print(f"  Published: {'Yes' if approved else 'No (draft saved)'}")
    print("=" * 60)


# ═══════════════════════════════════════════════
# Mode 2: Update Existing Blog Posts
# ═══════════════════════════════════════════════

def run_update_pipeline(seed_keywords, config):
    """Full pipeline: research → rewrite existing posts → images → approve → update."""
    site_name = config["site"]["name"]
    print("=" * 60)
    print(f"  {site_name} SEO BLOG ENGINE — UPDATE EXISTING POSTS")
    print("=" * 60)

    research = run_research(seed_keywords, config)

    site_context = research["site_context"]
    all_keywords = research["all_keywords"]
    competitor_summary = research["competitor_summary"]
    posts_needing_updates = research["posts_needing_updates"]

    if not posts_needing_updates:
        print("\n  No posts need updating! All posts look good.")
        return

    # ────────────────────────────────────────────
    # Phase 4: Rewrite Posts
    # ────────────────────────────────────────────
    print("\n[Phase 4] Rewriting posts that need improvement...")

    # Load update history to skip previously updated posts
    update_history = _load_update_history(config)
    if update_history:
        print(f"  Update history: {len(update_history)} posts previously updated")

    rewrite_queue = []
    skipped_count = 0
    max_rewrites = 3
    for post in posts_needing_updates:
        if len(rewrite_queue) >= max_rewrites:
            break
        title = post.get("title", "")
        post_id = post.get("_id")
        print(f"\n  {'─' * 40}")
        print(f"  Post: {title}")
        print(f"  MongoDB _id: {post_id}")
        print(f"  Reasons: {', '.join(post.get('update_reasons', []))}")

        # Skip if already updated in a previous run
        if str(post_id) in update_history:
            prev = update_history[str(post_id)]
            print(f"  [skip] Already updated on {prev.get('updated_at', '?')}")
            skipped_count += 1
            continue

        # Rewrite with Gemini (with site context)
        print(f"  Rewriting with Gemini...")
        rewritten = rewrite_blog_post(
            post, competitor_summary, list(all_keywords), config, site_context=site_context
        )

        if rewritten.startswith("[Gemini Error]"):
            print(f"  {rewritten}")
            continue

        needs_images = not post.get("image1Url") or not post.get("image2Url")

        rewrite_queue.append({
            "post_id": post_id,
            "original_title": title,
            "rewritten_output": rewritten,
            "needs_images": needs_images,
            "desktop_image": None,
            "mobile_image": None,
        })

        print(f"  Rewrite complete.")

    if not rewrite_queue:
        print("\n  No posts could be rewritten.")
        return

    # ────────────────────────────────────────────
    # Phase 5: Generate Images (for posts missing them)
    # ────────────────────────────────────────────
    print("\n[Phase 5] Generating images for posts that need them...")

    for item in rewrite_queue:
        if item["needs_images"]:
            print(f"  Generating images for: '{item['original_title'][:50]}...'")
            images = generate_blog_images(
                item["original_title"], "", config, site_context=site_context
            )
            item["desktop_image"] = images.get("desktop")
            item["mobile_image"] = images.get("mobile")
        else:
            print(f"  '{item['original_title'][:50]}...' — images exist, skipping")

    # ────────────────────────────────────────────
    # Phase 6: WhatsApp Review (per post — approve / feedback / reject)
    # ────────────────────────────────────────────
    print("\n[Phase 6] Sending posts for WhatsApp review...")

    approved_items = []
    rejected_items = []

    for item in rewrite_queue:
        short_title = item["original_title"][:50]
        print(f"\n  Reviewing: '{short_title}...'")

        final_output, approved = _review_loop(
            item["rewritten_output"], config, site_name,
            label=f"עדכון: {item['original_title'][:40]}"
        )
        item["rewritten_output"] = final_output

        if approved:
            approved_items.append(item)
        else:
            rejected_items.append(item)

    # ────────────────────────────────────────────
    # Phase 7: Apply Updates
    # ────────────────────────────────────────────
    if approved_items:
        print(f"\n[Phase 7] Applying {len(approved_items)} approved updates to MongoDB...")

        for item in approved_items:
            print(f"\n  Updating: '{item['original_title'][:50]}...'")
            try:
                result = update_existing_post(
                    post_id=item["post_id"],
                    gemini_output=item["rewritten_output"],
                    desktop_image_bytes=item["desktop_image"],
                    mobile_image_bytes=item["mobile_image"],
                    config=config,
                )
                print(f"  Updated successfully! New title: {result['title']}")
                # Record in history so it won't be re-updated next run
                _record_updated_post(item["post_id"], result["title"], config)
            except Exception as e:
                print(f"  [update] Error: {e}")

    if rejected_items:
        print(f"\n  {len(rejected_items)} posts rejected, saving drafts...")
        os.makedirs(os.path.join(os.path.dirname(__file__), "output"), exist_ok=True)
        for item in rejected_items:
            draft_path = os.path.join(
                os.path.dirname(__file__), "output",
                f"rewrite_{item['original_title'][:30]}.txt"
            )
            with open(draft_path, "w", encoding="utf-8") as f:
                f.write(item["rewritten_output"])
            print(f"  Draft saved: {draft_path}")

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Site context: {len(site_context.get('all_internal_links', []))} internal links, {len(site_context.get('product_names', []))} products")
    print(f"  Total keyword universe: {len(all_keywords)}")
    print(f"  Posts needing updates: {len(posts_needing_updates)}")
    print(f"  Skipped (already updated): {skipped_count}")
    print(f"  Posts rewritten: {len(rewrite_queue)}")
    print(f"  Approved & applied: {len(approved_items)}")
    print(f"  Rejected (drafts saved): {len(rejected_items)}")
    print("=" * 60)


# ═══════════════════════════════════════════════
# Mode 3: Rewrite Static Pages
# ═══════════════════════════════════════════════

def _parse_static_page_output(gemini_text):
    """
    Parse Gemini output for static pages.
    Format: TITLE: ...\n---\n[body markdown]\n---
    Returns (title, body_markdown).
    """
    lines = gemini_text.strip().split("\n")
    title = ""
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("TITLE:"):
            title = stripped[6:].strip()
            title = re.sub(r"\*{1,3}", "", title).strip()
        elif stripped == "---":
            body_start = i + 1
            break

    # Find end of body
    body_end = len(lines)
    for i in range(body_start, len(lines)):
        if lines[i].strip() == "---":
            body_end = i
            break

    body_markdown = "\n".join(lines[body_start:body_end]).strip()
    return title, body_markdown


def run_static_pipeline(config):
    """Fetch static pages from MongoDB, rewrite with Gemini, review, and update."""
    site_name = config["site"]["name"]
    print("=" * 60)
    print(f"  {site_name} SEO BLOG ENGINE — STATIC PAGES")
    print("=" * 60)

    # ────────────────────────────────────────────
    # Phase 0: Site Context
    # ────────────────────────────────────────────
    print(f"\n[Phase 0] Scraping {site_name} website for context...")
    site_context = scrape_site_context(config)

    # ────────────────────────────────────────────
    # Phase 1: Fetch Static Pages from MongoDB
    # ────────────────────────────────────────────
    print("\n[Phase 1] Fetching static pages from MongoDB...")
    pages = fetch_static_pages(config)
    print(f"  Found {len(pages)} static pages")

    if not pages:
        print("\n  No static pages found in this collection.")
        return

    for page in pages:
        print(f"  - {page.get('pageId', '?')}: {page.get('title', '?')}")

    # ────────────────────────────────────────────
    # Phase 2: Rewrite Each Page
    # ────────────────────────────────────────────
    print("\n[Phase 2] Rewriting static pages with Gemini...")

    rewrite_queue = []
    for page in pages:
        page_id = page.get("pageId", "unknown")
        page_title = page.get("title", "")
        content = page.get("content", {})

        # Skip policy pages — legal content shouldn't be AI-rewritten
        if page_id == "policy":
            print(f"\n  [{page_id}] Skipping policy/legal page")
            continue

        print(f"\n  {'─' * 40}")
        print(f"  Page: {page_title} ({page_id})")

        # Extract current text
        current_text = extract_text_from_tiptap(content)
        word_count = len(current_text.split())
        print(f"  Current length: ~{word_count} words")

        # Rewrite
        print(f"  Rewriting with Gemini...")
        rewritten = rewrite_static_page(page_title, page_id, current_text, config, site_context=site_context)

        if rewritten.startswith("[Gemini Error]"):
            print(f"  {rewritten}")
            continue

        new_title, body_markdown = _parse_static_page_output(rewritten)
        if not body_markdown:
            print(f"  Failed to parse Gemini output, skipping")
            continue

        new_word_count = len(body_markdown.split())
        print(f"  New length: ~{new_word_count} words ({new_word_count - word_count:+d})")

        rewrite_queue.append({
            "mongo_id": page["_id"],
            "page_id": page_id,
            "original_title": page_title,
            "new_title": new_title or page_title,
            "body_markdown": body_markdown,
            "gemini_output": rewritten,
        })

    if not rewrite_queue:
        print("\n  No pages were rewritten.")
        return

    # ────────────────────────────────────────────
    # Phase 3: WhatsApp Review
    # ────────────────────────────────────────────
    print("\n[Phase 3] Sending pages for WhatsApp review...")

    approved_items = []
    for item in rewrite_queue:
        preview = (
            f"📄 *עמוד סטטי: {item['page_id']}*\n\n"
            f"*כותרת:* {item['new_title']}\n"
            f"*אורך:* ~{len(item['body_markdown'].split())} מילים\n\n"
            f"--- התוכן המלא ---\n\n"
            f"{item['body_markdown']}"
        )

        final_output, approved = _review_loop(
            item["gemini_output"], config, site_name,
            label=f"עמוד: {item['page_id']}"
        )

        if approved:
            # Re-parse in case feedback changed the content
            new_title, new_body = _parse_static_page_output(final_output)
            item["new_title"] = new_title or item["new_title"]
            item["body_markdown"] = new_body or item["body_markdown"]
            approved_items.append(item)
        else:
            print(f"  [{item['page_id']}] Rejected")

    # ────────────────────────────────────────────
    # Phase 4: Apply Updates to MongoDB
    # ────────────────────────────────────────────
    if approved_items:
        print(f"\n[Phase 4] Applying {len(approved_items)} approved updates to MongoDB...")

        for item in approved_items:
            print(f"\n  Updating: {item['page_id']} — '{item['new_title'][:50]}'")
            try:
                tiptap_content = markdown_to_static_tiptap(item["body_markdown"])
                update_static_page(
                    page_id=item["mongo_id"],
                    title=item["new_title"],
                    content=tiptap_content,
                    config=config,
                )
                print(f"  Updated successfully!")
            except Exception as e:
                print(f"  [update] Error: {e}")
    else:
        print("\n[Phase 4] No pages approved for update.")

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Static pages found: {len(pages)}")
    print(f"  Pages rewritten: {len(rewrite_queue)}")
    print(f"  Approved & applied: {len(approved_items)}")
    print("=" * 60)


# ═══════════════════════════════════════════════
# Mode 4: Full Init — all actions in one run
# ═══════════════════════════════════════════════

MAX_NEW_POSTS = 5


def run_full_pipeline(seed_keywords, config):
    """
    Full first-run pipeline: research once, then:
      A) Create multiple new blog posts
      B) Update existing posts that need improvement
      C) Rewrite static pages
    """
    site_name = config["site"]["name"]
    print("=" * 60)
    print(f"  {site_name} SEO BLOG ENGINE — FULL INIT")
    print("=" * 60)

    # ════════════════════════════════════════════
    # PART 0: Shared Research (runs once)
    # ════════════════════════════════════════════
    research = run_research(seed_keywords, config)

    site_context = research["site_context"]
    all_keywords = research["all_keywords"]
    top_keywords = research["top_keywords"]
    uncovered_keywords = research["uncovered_keywords"]
    serp_results = research["serp_results"]
    competitor_summary = research["competitor_summary"]
    all_paa = research["all_paa"]
    posts_needing_updates = research["posts_needing_updates"]

    # Track totals for final summary
    total_new_published = 0
    total_updates_applied = 0
    total_static_applied = 0

    # ════════════════════════════════════════════
    # PART A: Create Multiple New Blog Posts
    # ════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  PART A: CREATING NEW BLOG POSTS")
    print("▓" * 60)

    # Pick up to MAX_NEW_POSTS uncovered topics
    new_topics = []
    used = set()
    for kw, _ in top_keywords:
        if kw in uncovered_keywords and kw not in used:
            new_topics.append(kw)
            used.add(kw)
        if len(new_topics) >= MAX_NEW_POSTS:
            break
    # Fill remaining slots from uncovered keywords
    for kw in uncovered_keywords:
        if kw not in used:
            new_topics.append(kw)
            used.add(kw)
        if len(new_topics) >= MAX_NEW_POSTS:
            break

    if not new_topics:
        print("\n  All topics already covered! No new posts needed.")
    else:
        print(f"\n  Creating {len(new_topics)} new blog posts...")

    for idx, topic in enumerate(new_topics, 1):
        print(f"\n  {'━' * 50}")
        print(f"  NEW POST {idx}/{len(new_topics)}: '{topic}'")
        print(f"  {'━' * 50}")

        topic_serp = serp_results.get(topic, {})
        topic_data = {
            "target_keyword": topic,
            "related_keywords": [k for k in all_keywords if k != topic][:15],
            "paa_questions": topic_serp.get("people_also_ask", all_paa[:10]),
            "competitor_summary": competitor_summary,
            "serp_titles": [r["title"] for r in topic_serp.get("organic_results", [])],
        }

        # Generate post
        print(f"  Generating blog post with Gemini...")
        blog_post = generate_blog_post(topic_data, config, site_context=site_context)

        if blog_post.startswith("[Gemini Error]"):
            print(f"  {blog_post}")
            continue

        # Generate images
        print(f"  Generating images...")
        images = generate_blog_images(topic, "", config, site_context=site_context)
        desktop_image = images.get("desktop")
        mobile_image = images.get("mobile")

        # WhatsApp review
        final_post, approved = _review_loop(
            blog_post, config, site_name,
            label=f"פוסט חדש {idx}/{len(new_topics)}"
        )

        if approved:
            try:
                result = publish_blog_post(
                    gemini_output=final_post,
                    desktop_image_bytes=desktop_image,
                    mobile_image_bytes=mobile_image,
                    config=config,
                )
                print(f"  Published! ID: {result['post_id']} — {result['title']}")
                total_new_published += 1
            except Exception as e:
                print(f"  [publish] Error: {e}")
        else:
            print(f"  Rejected, saving draft...")
            os.makedirs(os.path.join(os.path.dirname(__file__), "output"), exist_ok=True)
            draft_path = os.path.join(os.path.dirname(__file__), "output", f"draft_{topic[:30]}.txt")
            with open(draft_path, "w", encoding="utf-8") as f:
                f.write(final_post)

    # ════════════════════════════════════════════
    # PART B: Update Existing Posts
    # ════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  PART B: UPDATING EXISTING POSTS")
    print("▓" * 60)

    update_history = _load_update_history(config)
    if update_history:
        print(f"\n  Update history: {len(update_history)} posts previously updated")

    if not posts_needing_updates:
        print("\n  No posts need updating!")
    else:
        rewrite_queue = []
        max_rewrites = 3
        for post in posts_needing_updates:
            if len(rewrite_queue) >= max_rewrites:
                break
            title = post.get("title", "")
            post_id = post.get("_id")
            if str(post_id) in update_history:
                continue

            print(f"\n  Rewriting: {title[:60]}")
            rewritten = rewrite_blog_post(
                post, competitor_summary, list(all_keywords), config, site_context=site_context
            )
            if rewritten.startswith("[Gemini Error]"):
                print(f"  {rewritten}")
                continue

            needs_images = not post.get("image1Url") or not post.get("image2Url")
            desktop_img, mobile_img = None, None
            if needs_images:
                images = generate_blog_images(title, "", config, site_context=site_context)
                desktop_img = images.get("desktop")
                mobile_img = images.get("mobile")

            final_output, approved = _review_loop(
                rewritten, config, site_name,
                label=f"עדכון: {title[:40]}"
            )

            if approved:
                try:
                    result = update_existing_post(
                        post_id=post_id,
                        gemini_output=final_output,
                        desktop_image_bytes=desktop_img,
                        mobile_image_bytes=mobile_img,
                        config=config,
                    )
                    print(f"  Updated! {result['title']}")
                    _record_updated_post(post_id, result["title"], config)
                    total_updates_applied += 1
                except Exception as e:
                    print(f"  [update] Error: {e}")

    # ════════════════════════════════════════════
    # PART C: Rewrite Static Pages
    # ════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  PART C: REWRITING STATIC PAGES")
    print("▓" * 60)

    pages = fetch_static_pages(config)
    if not pages:
        print("\n  No static pages found.")
    else:
        print(f"\n  Found {len(pages)} static pages")
        for page in pages:
            page_id = page.get("pageId", "unknown")
            page_title = page.get("title", "")
            content = page.get("content", {})

            if page_id == "policy":
                print(f"  [{page_id}] Skipping policy/legal page")
                continue

            print(f"\n  Rewriting: {page_title} ({page_id})")
            current_text = extract_text_from_tiptap(content)
            rewritten = rewrite_static_page(page_title, page_id, current_text, config, site_context=site_context)

            if rewritten.startswith("[Gemini Error]"):
                print(f"  {rewritten}")
                continue

            new_title, body_markdown = _parse_static_page_output(rewritten)
            if not body_markdown:
                print(f"  Failed to parse output, skipping")
                continue

            final_output, approved = _review_loop(
                rewritten, config, site_name,
                label=f"עמוד: {page_id}"
            )

            if approved:
                final_title, final_body = _parse_static_page_output(final_output)
                try:
                    tiptap_content = markdown_to_static_tiptap(final_body or body_markdown)
                    update_static_page(
                        page_id=page["_id"],
                        title=final_title or new_title or page_title,
                        content=tiptap_content,
                        config=config,
                    )
                    print(f"  Updated!")
                    total_static_applied += 1
                except Exception as e:
                    print(f"  [update] Error: {e}")

    # ════════════════════════════════════════════
    # FINAL SUMMARY
    # ════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  FULL INIT SUMMARY")
    print("=" * 60)
    print(f"  Site: {site_name}")
    print(f"  Keywords discovered: {len(all_keywords)}")
    print(f"  New posts published: {total_new_published}/{len(new_topics)}")
    print(f"  Existing posts updated: {total_updates_applied}")
    print(f"  Static pages updated: {total_static_applied}")
    print("=" * 60)


# ═══════════════════════════════════════════════
# Mode 5: Generate Images for Posts Missing Them
# ═══════════════════════════════════════════════

def run_images_pipeline(config):
    """Find all posts with empty images, generate new ones, and upload — no content changes."""
    site_name = config["site"]["name"]
    print("=" * 60)
    print(f"  {site_name} SEO BLOG ENGINE — IMAGES ONLY")
    print("=" * 60)

    # ────────────────────────────────────────────
    # Phase 1: Site Context (needed for image prompts)
    # ────────────────────────────────────────────
    print(f"\n[Phase 1] Scraping {site_name} website for context...")
    site_context = scrape_site_context(config)

    # ────────────────────────────────────────────
    # Phase 2: Find posts with missing images
    # ────────────────────────────────────────────
    print("\n[Phase 2] Querying MongoDB for posts with missing images...")
    posts = fetch_posts_missing_images(config)
    print(f"  Found {len(posts)} posts with missing images")

    if not posts:
        print("\n  All posts already have images! Nothing to do.")
        return

    for p in posts:
        img1 = "yes" if p.get("image1Url") else "MISSING"
        img2 = "yes" if p.get("image2Url") else "MISSING"
        print(f"  - {p['title'][:60]}  [desktop: {img1}, mobile: {img2}]")

    # ────────────────────────────────────────────
    # Phase 3: Generate & upload images
    # ────────────────────────────────────────────
    print("\n[Phase 3] Generating and uploading images...")

    success_count = 0
    fail_count = 0

    for idx, post in enumerate(posts, 1):
        title = post["title"]
        post_id = post["_id"]
        print(f"\n  {'─' * 40}")
        print(f"  [{idx}/{len(posts)}] {title[:60]}")

        # Generate images
        images = generate_blog_images(title, "", config, site_context=site_context)
        desktop = images.get("desktop")
        mobile = images.get("mobile")

        if not desktop and not mobile:
            print(f"  Failed to generate any images, skipping")
            fail_count += 1
            continue

        # Upload & update only image fields
        try:
            update_post_images(post_id, desktop, mobile, config)
            success_count += 1
        except Exception as e:
            print(f"  [images] Error: {e}")
            fail_count += 1

    # ────────────────────────────────────────────
    # Summary
    # ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Site: {site_name}")
    print(f"  Posts with missing images: {len(posts)}")
    print(f"  Successfully updated: {success_count}")
    print(f"  Failed: {fail_count}")
    print("=" * 60)
