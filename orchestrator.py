import time
import json
import subprocess
import os
import re
from datetime import datetime, timezone, timedelta
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
from publisher.mongodb_client import update_blog_post as _mongo_update_post


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


def _record_updated_post(post_id, title, config, original_title=None, original_body=None, history=None):
    """Record a successfully updated post so it's skipped in future runs.

    original_title: the title before the update (same as title when preserve_title is used,
                    but stored explicitly so the recovery system can verify it).
    original_body:  the full TipTap body JSON string before the update.
                    Stored so content can be fully restored if the rewrite hurts rankings.
    history:        pass a pre-loaded history dict to avoid a redundant disk read when
                    recording multiple posts in the same run. The updated dict is returned.
    """
    if history is None:
        history = _load_update_history(config)
    entry = {
        "title": title,
        "updated_at": datetime.now().isoformat(),
    }
    if original_title:
        entry["original_title"] = original_title
    if original_body:
        entry["original_body"] = original_body
    history[str(post_id)] = entry
    _save_update_history(history, config)
    return history


def _is_already_updated(post_id, config):
    """Check if a post was already updated in a previous run."""
    history = _load_update_history(config)
    return str(post_id) in history


def _get_static_history_path(config):
    collection = config["mongodb"]["collection"]
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{collection}_static_history.json")


def _load_static_history(config):
    path = _get_static_history_path(config)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _record_static_page(page_id, title, config, history=None):
    if history is None:
        history = _load_static_history(config)
    history[page_id] = {"title": title, "updated_at": datetime.now().isoformat()}
    path = _get_static_history_path(config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return history


# ═══════════════════════════════════════════════
# Recovery History — prevent re-suggesting same URLs
# ═══════════════════════════════════════════════

def _get_recovery_history_path(config):
    """Return path to the recovery history file for this site."""
    collection = config["mongodb"]["collection"]
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{collection}_recovery_history.json")


def _load_recovery_history(config):
    """Load set of previously processed recovery URLs."""
    path = _get_recovery_history_path(config)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_recovery_history(history, config):
    """Save recovery history to disk."""
    path = _get_recovery_history_path(config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _record_recovery_decision(url, decision, page, config, history=None):
    """Record the decision (approved/rejected/skipped) for a recovery candidate URL.

    history: pass the pre-loaded recovery history dict to avoid redundant disk reads
             when processing multiple candidates in the same run. Returns the updated dict.
    """
    if history is None:
        history = _load_recovery_history(config)
    history[url] = {
        "decision": decision,
        "processed_at": datetime.now().isoformat(),
        "original_title": page.get("original_title", ""),
        "current_title": page.get("current_title", ""),
        "drop_pct": page.get("drop_pct", 0),
        "cause": page.get("cause", ""),
    }
    _save_recovery_history(history, config)
    return history


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
    Auto-approves all posts — WhatsApp review is disabled.
    Returns: ("approved", None)
    """
    print("  [auto-approve] Publishing without review")
    return ("approved", None)

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
    received_feedback = False  # track if user already gave feedback

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
            received_feedback = True
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
            if received_feedback:
                # User already engaged — don't auto-approve the revision without their sign-off
                print(f"  WhatsApp timeout after feedback — saving as draft (not auto-approving)")
                return (current_output, False)
            else:
                # No response at all (scheduled/unattended run) — auto-approve
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

    # ────────────────────────────────────────────
    # Phase 3b: GSC Intelligence (optional)
    # ────────────────────────────────────────────
    gsc_data = {}
    gsc_failed = False  # True if GSC was configured but failed — blocks updates as a safety measure
    if config.get("search_console"):
        print(f"\n[Phase 3b] Fetching Google Search Console data...")
        try:
            from tools.search_console import (
                fetch_gsc_performance, fetch_page_queries,
                classify_page_seo, match_post_to_gsc_url,
            )
            gsc_data = fetch_gsc_performance(config, days=90)
            page_queries = fetch_page_queries(config, days=90)

            # Classify ALL own posts (not just update candidates)
            _no_gsc = {"category": "not_indexed", "top_queries": [], "metrics": {}, "update_priority": 4}
            for post in own_posts:
                url, _ = match_post_to_gsc_url(post.get("title", ""), gsc_data, config)
                post["gsc_url"] = url
                post["gsc_context"] = classify_page_seo(url or "", gsc_data, page_queries, config) if url else dict(_no_gsc)
                # Title is protected if the page appears anywhere in GSC (any impressions = has a URL)
                post["gsc_protection"] = url is not None

            # Show classification breakdown
            cats = {}
            for post in own_posts:
                cats[post["gsc_context"]["category"]] = cats.get(post["gsc_context"]["category"], 0) + 1
            for cat, count in sorted(cats.items()):
                print(f"  [gsc] {cat}: {count} posts")

            # Add page2 candidates to update queue (highest ROI — push from pos 11-30 to page 1)
            for post in own_posts:
                if (post["gsc_context"]["category"] == "page2_opportunity"
                        and post not in posts_needing_updates):
                    post.setdefault("update_reasons", [])
                    pos = post["gsc_context"]["metrics"].get("position", "?")
                    post["update_reasons"].append(f"page2 opportunity (position {pos})")
                    posts_needing_updates.append(post)

            # Add not_indexed posts — Google has never crawled/indexed them.
            # Most common cause: thin, promotional, or B2B content that doesn't match searcher intent.
            # These need a content quality rewrite more than any other category.
            for post in own_posts:
                if (post["gsc_context"]["category"] == "not_indexed"
                        and post not in posts_needing_updates):
                    post.setdefault("update_reasons", [])
                    post["update_reasons"].append("never indexed by Google — content quality rewrite needed")
                    posts_needing_updates.append(post)

            # Skip top_performer posts — they're ranking well, don't risk breaking them
            before = len(posts_needing_updates)
            posts_needing_updates = [
                p for p in posts_needing_updates
                if p.get("gsc_context", {}).get("category") != "top_performer"
            ]
            skipped_top = before - len(posts_needing_updates)
            if skipped_top:
                print(f"  [gsc] Skipping {skipped_top} top-performing posts (already on page 1 with clicks)")

            # ── Cannibalization detection ────────────────────────
            # Posts competing for the same queries hurt each other — updating one without
            # fixing the overlap just reshuffles the split, it doesn't resolve it.
            # Tag cannibalizing posts so update mode can skip/warn about them.
            from tools.search_console import find_cannibalization
            blog_path = ""
            try:
                from urllib.parse import urlparse
                blog_path = urlparse(config["site"].get("blog_url", "")).path.rstrip("/")
            except Exception:
                pass
            cannibalization = find_cannibalization(page_queries, blog_path=blog_path)
            cannibalizing_urls = set()
            for cluster in cannibalization:
                if len(cluster["urls"]) >= 2:
                    for entry in cluster["urls"]:
                        cannibalizing_urls.add(entry["url"])
            # Tag each post with its cannibalization clusters
            for post in own_posts:
                url = post.get("gsc_url", "")
                clusters = [c for c in cannibalization if any(e["url"] == url for e in c["urls"])]
                post["cannibalizing_queries"] = [c["query"] for c in clusters] if clusters else []
            if cannibalization:
                print(f"  [gsc] Cannibalization: {len(cannibalization)} queries with competing URLs")

            # ── Load impact verdicts from last impact run ────────
            # Posts marked "hurt" in the last impact analysis should not be retouched —
            # let Google re-evaluate naturally before we change the content again.
            impact_verdicts = {}
            impact_json = os.path.join(
                os.path.dirname(__file__), "output",
                f"{config['mongodb']['collection']}_impact_verdicts.json"
            )
            if os.path.exists(impact_json):
                try:
                    with open(impact_json, "r", encoding="utf-8") as f:
                        impact_verdicts = json.load(f)
                    hurt_count = sum(1 for v in impact_verdicts.values() if v.get("status") == "hurt")
                    print(f"  [impact] Loaded verdicts: {hurt_count} posts marked 'hurt' — will be skipped")
                except Exception:
                    pass
            for post in own_posts:
                title = post.get("title", "")
                verdict = impact_verdicts.get(title, {})
                post["impact_status"] = verdict.get("status", "unknown")

            # Sort update queue: page2 first, then by priority
            posts_needing_updates.sort(key=lambda p: p.get("gsc_context", {}).get("update_priority", 4))
            print(f"  [gsc] {len(posts_needing_updates)} posts in update queue (after GSC prioritization)")

        except FileNotFoundError as e:
            # Credentials file missing — user needs to set up GSC. Block updates to prevent blind rewrites.
            print(f"\n  [gsc] ⚠️  BLOCKING UPDATES — GSC credentials not found: {e}")
            print(f"  [gsc] Cannot safely update posts without knowing which ones are ranking.")
            print(f"  [gsc] Fix: download OAuth credentials from Google Cloud Console and set credentials_file in config.")
            gsc_failed = True
            for post in own_posts:
                post["gsc_protection"] = True  # assume all are protected when we can't check
                post["gsc_context"] = {"category": "unknown", "top_queries": [], "metrics": {}, "update_priority": 3}
        except Exception as e:
            # Any GSC API error — block updates as a safety measure
            print(f"\n  [gsc] ⚠️  BLOCKING UPDATES — GSC fetch failed: {e}")
            print(f"  [gsc] Cannot safely update posts without knowing which ones are ranking.")
            print(f"  [gsc] Fix the GSC connection and re-run. Posts with existing rankings could be damaged.")
            import traceback; traceback.print_exc()
            gsc_failed = True
            for post in own_posts:
                post["gsc_protection"] = True  # assume all are protected when we can't check
                post["gsc_context"] = {"category": "unknown", "top_queries": [], "metrics": {}, "update_priority": 3}
    else:
        _no_gsc = {"category": "not_indexed", "top_queries": [], "metrics": {}, "update_priority": 4}
        for post in own_posts:
            post["gsc_protection"] = False
            post["gsc_context"] = dict(_no_gsc)

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
        "gsc_data": gsc_data,
        "gsc_failed": gsc_failed,
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

    # Safety: if GSC was configured but failed, skip all updates to protect existing rankings
    if research.get("gsc_failed"):
        print("\n  ⚠️  GSC connection failed — update mode BLOCKED to protect existing rankings.")
        print("  Fix the GSC credentials and re-run.")
        return

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
        gsc_category = post.get("gsc_context", {}).get("category", "unknown")
        print(f"\n  {'─' * 40}")
        print(f"  Post: {title}")
        print(f"  MongoDB _id: {post_id}")
        print(f"  GSC category: {gsc_category}")
        print(f"  Reasons: {', '.join(post.get('update_reasons', []))}")

        # Skip if already updated in a previous run, with per-category cooldowns:
        #   not_indexed  →  7 days  (never ranked, safe to retry quickly)
        #   ctr_opportunity → 14 days  (meta-only change, low risk)
        #   all others   → 30 days  (protect rankings, give Google time to process)
        if str(post_id) in update_history:
            prev = update_history[str(post_id)]
            cooldown_days = {
                "not_indexed": 7,
                "ctr_opportunity": 14,
                "page2_opportunity": 21,  # quick-wins close to page 1 — iterate faster
            }.get(gsc_category, 30)
            last_updated = prev.get("updated_at", "")
            try:
                last_dt = datetime.fromisoformat(last_updated).replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_dt).days
            except Exception:
                days_since = 999
            if days_since < cooldown_days:
                print(f"  [skip] Cooldown ({gsc_category}): updated {days_since}d ago, retry after {cooldown_days}d")
                skipped_count += 1
                continue
            print(f"  [retry] {gsc_category}: last updated {days_since}d ago — eligible for another pass")

        # Skip posts that got hurt in the last impact run — let Google re-evaluate first.
        # Exception: not_indexed posts are never in GSC so impact can't measure them → always retry.
        impact_status = post.get("impact_status", "unknown")
        if impact_status == "hurt" and gsc_category != "not_indexed":
            print(f"  [skip] Last update HURT this post (position dropped) — letting Google recover before retouching")
            skipped_count += 1
            continue

        # Skip posts in active cannibalization clusters — rewriting one cannibalizing post
        # doesn't help, it just reshuffles the split. The fix is to merge/redirect, not rewrite.
        cannibalizing_queries = post.get("cannibalizing_queries", [])
        if cannibalizing_queries and gsc_category != "not_indexed":
            print(f"  [skip] Cannibalization: competes with other posts on {len(cannibalizing_queries)} queries: {', '.join(cannibalizing_queries[:3])}")
            print(f"         Fix: merge or redirect the weaker duplicate posts, then re-run update.")
            skipped_count += 1
            continue

        # ctr_opportunity: page ranks on page 1 but low CTR — only update meta description, never touch body
        subtitle_only = (gsc_category == "ctr_opportunity")

        # not_indexed: title CAN be changed — no URL rankings at risk (page was never indexed by Google)
        allow_title_change = (gsc_category == "not_indexed")

        # Rewrite with Gemini (with site context)
        if subtitle_only:
            print(f"  [ctr_opportunity] Generating improved meta description only (body untouched)...")
        elif allow_title_change:
            print(f"  [not_indexed] Content quality rewrite — new title allowed...")
        else:
            print(f"  Rewriting with Gemini...")
        rewritten = rewrite_blog_post(
            post, competitor_summary, list(all_keywords), config, site_context=site_context
        )

        if rewritten.startswith("[Gemini Error]"):
            print(f"  {rewritten}")
            continue

        # not_indexed posts always get new images — complete rewrite with new title means old image is stale.
        # All other posts: only generate if images are missing (existing images are fine to keep).
        if allow_title_change:
            needs_images = True
        else:
            needs_images = not post.get("image1Url") or not post.get("image2Url")
        # subtitle_only posts never need image generation (body is untouched)
        if subtitle_only:
            needs_images = False

        # Capture body before update for recovery backup
        original_body = post.get("body", "")

        rewrite_queue.append({
            "post_id": post_id,
            "original_title": title,
            "original_body": original_body,
            "rewritten_output": rewritten,
            "needs_images": needs_images,
            "subtitle_only": subtitle_only,
            "allow_title_change": allow_title_change,
            "desktop_image": None,
            "mobile_image": None,
        })

        if subtitle_only:
            print(f"  Meta description generated. (body PROTECTED — ctr_opportunity mode)")
        elif allow_title_change:
            print(f"  Content quality rewrite complete. (not_indexed — new title will be applied)")
        else:
            print(f"  Rewrite complete. (title will be preserved on publish)")

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
                # Preserve title unless this post was never indexed (no rankings at risk).
                # For not_indexed posts, the new title targets real search queries.
                # For all other posts: title = URL slug in the CMS — changing it = 404 = lost rankings.
                preserve_title = None if item.get("allow_title_change") else item["original_title"]
                result = update_existing_post(
                    post_id=item["post_id"],
                    gemini_output=item["rewritten_output"],
                    desktop_image_bytes=item["desktop_image"],
                    mobile_image_bytes=item["mobile_image"],
                    config=config,
                    preserve_title=preserve_title,
                    subtitle_only=item.get("subtitle_only", False),
                )
                if item.get("subtitle_only"):
                    print(f"  Meta description updated! Title & body unchanged: {result['title']}")
                elif item.get("allow_title_change"):
                    print(f"  Content quality rewrite applied! New title: {result['title']}")
                else:
                    print(f"  Updated successfully! Title preserved: {result['title']}")
                # Save original_body so recovery can fully restore content if rankings drop
                update_history = _record_updated_post(
                    item["post_id"], result["title"], config,
                    original_title=item["original_title"],
                    original_body=item.get("original_body"),
                    history=update_history,
                )
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
    # Phase 1b: GSC Intelligence
    # ────────────────────────────────────────────
    gsc_data = {}
    page_queries = {}
    gsc_failed = False
    domain = config["site"]["domain"]

    if config.get("search_console"):
        print(f"\n[Phase 1b] Fetching Google Search Console data...")
        try:
            from tools.search_console import (
                fetch_gsc_performance, fetch_page_queries,
                classify_page_seo,
            )
            gsc_data = fetch_gsc_performance(config, days=90)
            page_queries = fetch_page_queries(config, days=90)

            # Classify each static page by its URL
            for page in pages:
                page_id = page.get("pageId", "")
                if page_id == "home":
                    url = f"https://{domain}/"
                else:
                    url = f"https://{domain}/{page_id}"
                # Try both with and without trailing slash
                gsc_context = classify_page_seo(url, gsc_data, page_queries, config)
                if gsc_context.get("category") == "not_indexed":
                    gsc_context = classify_page_seo(url.rstrip("/"), gsc_data, page_queries, config)
                page["gsc_url"] = url
                page["gsc_context"] = gsc_context

            cats = {}
            for page in pages:
                cat = page.get("gsc_context", {}).get("category", "unknown")
                cats[cat] = cats.get(cat, 0) + 1
            for cat, count in sorted(cats.items()):
                print(f"  [gsc] {cat}: {count} pages")

        except FileNotFoundError as e:
            print(f"\n  [gsc] ⚠️  BLOCKING STATIC REWRITES — GSC credentials not found: {e}")
            gsc_failed = True
        except Exception as e:
            print(f"\n  [gsc] ⚠️  BLOCKING STATIC REWRITES — GSC fetch failed: {e}")
            gsc_failed = True

    if gsc_failed:
        print("  Fix the GSC credentials and re-run.")
        return

    # ────────────────────────────────────────────
    # Phase 2: Rewrite Each Page
    # ────────────────────────────────────────────
    print("\n[Phase 2] Rewriting static pages with Gemini...")

    static_history = _load_static_history(config)
    STATIC_COOLDOWN_DAYS = 30

    rewrite_queue = []
    for page in pages:
        page_id = page.get("pageId", "unknown")
        page_title = page.get("title", "")
        content = page.get("content", {})

        # Skip policy pages — legal content shouldn't be AI-rewritten
        if page_id == "policy":
            print(f"\n  [{page_id}] Skipping policy/legal page")
            continue

        gsc_context = page.get("gsc_context", {})
        gsc_category = gsc_context.get("category", "unknown")

        # Skip top_performer pages — they're ranking well, don't risk breaking them
        if gsc_category == "top_performer":
            print(f"\n  [{page_id}] Skipping — top_performer (ranking well, protecting)")
            continue

        # Skip if updated recently — 30-day cooldown.
        # Exception: not_indexed pages retry after 7 days (same as update mode).
        cooldown = 7 if gsc_category == "not_indexed" else STATIC_COOLDOWN_DAYS
        if page_id in static_history:
            last_updated = static_history[page_id].get("updated_at", "")
            try:
                last_dt = datetime.fromisoformat(last_updated).replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_dt).days
            except Exception:
                days_since = 999
            if days_since < cooldown:
                print(f"\n  [{page_id}] Skipping — updated {days_since}d ago (cooldown: {cooldown}d, category: {gsc_category})")
                continue

        print(f"\n  {'─' * 40}")
        print(f"  Page: {page_title} ({page_id})")
        print(f"  GSC category: {gsc_category}")

        # Extract current text
        current_text = extract_text_from_tiptap(content)
        word_count = len(current_text.split())
        print(f"  Current length: ~{word_count} words")

        # Rewrite — pass GSC context so prompt preserves ranking queries
        print(f"  Rewriting with Gemini...")
        rewritten = rewrite_static_page(page_title, page_id, current_text, config, site_context=site_context, gsc_context=gsc_context)

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
                static_history = _record_static_page(item["page_id"], item["new_title"], config, history=static_history)
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

    # Safety: if GSC was configured but failed, skip all updates to protect existing rankings
    if research.get("gsc_failed"):
        print("\n  ⚠️  GSC connection failed — update mode BLOCKED to protect existing rankings.")
        print("  Fix the GSC credentials and re-run. Continuing with new post creation only.")
        posts_needing_updates = []  # clear so the block below is skipped

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
            gsc_category = post.get("gsc_context", {}).get("category", "unknown")
            # Per-category cooldowns: not_indexed=7d, ctr_opportunity=14d, others=30d
            if str(post_id) in update_history:
                cooldown_days = {"not_indexed": 7, "ctr_opportunity": 14, "page2_opportunity": 21}.get(gsc_category, 30)
                prev = update_history[str(post_id)]
                last_updated = prev.get("updated_at", "")
                try:
                    last_dt = datetime.fromisoformat(last_updated).replace(tzinfo=timezone.utc)
                    days_since = (datetime.now(timezone.utc) - last_dt).days
                except Exception:
                    days_since = 999
                if days_since < cooldown_days:
                    continue

            # ctr_opportunity: only update meta description, never touch body
            subtitle_only = (gsc_category == "ctr_opportunity")

            # not_indexed: title CAN be changed — no rankings at risk (page was never indexed)
            allow_title_change = (gsc_category == "not_indexed")

            if subtitle_only:
                print(f"\n  [ctr_opportunity] Meta description only: {title[:60]}")
            elif allow_title_change:
                print(f"\n  [not_indexed] Content quality rewrite — new title allowed: {title[:60]}")
            else:
                print(f"\n  Rewriting: {title[:60]}")
            rewritten = rewrite_blog_post(
                post, competitor_summary, list(all_keywords), config, site_context=site_context
            )
            if rewritten.startswith("[Gemini Error]"):
                print(f"  {rewritten}")
                continue

            # not_indexed posts always get new images — complete rewrite means old image is stale.
            if allow_title_change:
                needs_images = True
            else:
                needs_images = not post.get("image1Url") or not post.get("image2Url")
            # subtitle_only posts: never regenerate images (body untouched)
            if subtitle_only:
                needs_images = False

            desktop_img, mobile_img = None, None
            if needs_images:
                images = generate_blog_images(title, "", config, site_context=site_context)
                desktop_img = images.get("desktop")
                mobile_img = images.get("mobile")

            # Capture body before update for recovery backup
            original_body = post.get("body", "")

            final_output, approved = _review_loop(
                rewritten, config, site_name,
                label=f"{'עדכון מטא' if subtitle_only else 'עדכון'}: {title[:40]}"
            )

            if approved:
                try:
                    # Preserve title unless the post was never indexed (no rankings at risk).
                    # For not_indexed: new title targets real queries.
                    # For all others: title = URL slug — changing it = 404 = lost rankings.
                    preserve_title = None if allow_title_change else title
                    result = update_existing_post(
                        post_id=post_id,
                        gemini_output=final_output,
                        desktop_image_bytes=desktop_img,
                        mobile_image_bytes=mobile_img,
                        config=config,
                        preserve_title=preserve_title,
                        subtitle_only=subtitle_only,
                    )
                    if subtitle_only:
                        print(f"  Meta description updated! Body unchanged: {result['title']}")
                    elif allow_title_change:
                        print(f"  Content quality rewrite applied! New title: {result['title']}")
                    else:
                        print(f"  Updated! Title preserved: {result['title']}")
                    # Save original_body so recovery can fully restore content if rankings drop
                    update_history = _record_updated_post(
                        post_id, result["title"], config,
                        original_title=title,
                        original_body=original_body,
                        history=update_history,
                    )
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


# ═══════════════════════════════════════════════
# Mode 6: Recover — Restore Titles That Lost Rankings
# ═══════════════════════════════════════════════

def run_recover_pipeline(config):
    """
    Find pages that lost GSC performance after updates by our engine.
    Offer to restore the original title AND body content via WhatsApp approval.
    Already-processed URLs are remembered so they won't be shown again.
    """
    site_name = config["site"]["name"]
    print("=" * 60)
    print(f"  {site_name} SEO BLOG ENGINE — RECOVER TITLES")
    print("=" * 60)

    if not config.get("search_console"):
        print("\n  [error] search_console section not found in config.")
        print("  Add search_console config to use the recover feature.")
        return

    # ────────────────────────────────────────────
    # Phase 1: Find Lost Pages
    # ────────────────────────────────────────────
    print("\n[Phase 1] Analyzing GSC performance drops...")

    # Anchor the "recent" window to the actual first update date from history,
    # not a fixed 28-day window. A fixed window dilutes the signal by including
    # pre-incident traffic days. We want: recent = from first update → today.
    history = _load_update_history(config)
    recent_days = 28  # default
    if history:
        try:
            first_update = min(
                datetime.fromisoformat(v["updated_at"]).replace(tzinfo=None)
                for v in history.values() if v.get("updated_at")
            )
            days_since_first = (datetime.now() - first_update).days
            if 10 <= days_since_first <= 120:
                recent_days = days_since_first
                print(f"  [recover] Anchoring window to first update: {first_update.strftime('%Y-%m-%d')} ({recent_days}d ago)")
        except Exception:
            pass

    try:
        from tools.search_console import (
            find_lost_pages, fetch_page_queries,
            fetch_gsc_period_by_page, classify_page_seo, fetch_page_queries as _fpq,
        )
        lost_pages = find_lost_pages(config, recent_days=recent_days)
    except FileNotFoundError as e:
        print(f"\n  {e}")
        return
    except Exception as e:
        print(f"\n  [error] Failed to fetch GSC data: {e}")
        return

    # Fetch current GSC performance (last 14 days) to detect recovering pages.
    # If a page is trending UP (last 7d better than previous 7d), skip it —
    # it's recovering on its own and touching it would reset that recovery.
    print("\n  Checking recovery trend for each candidate (last 14 days)...")
    try:
        now = datetime.now()
        gsc_lag = timedelta(days=3)
        trend_end   = now - gsc_lag
        trend_mid   = trend_end - timedelta(days=7)
        trend_start = trend_end - timedelta(days=14)
        recent_7  = fetch_gsc_period_by_page(config, trend_mid,   trend_end)
        prev_7    = fetch_gsc_period_by_page(config, trend_start, trend_mid)

        recovering_urls = set()
        for page in lost_pages:
            url = page["url"]
            r7  = recent_7.get(url, {}).get("clicks", 0)
            p7  = prev_7.get(url, {}).get("clicks", 0)
            r7_pos = recent_7.get(url, {}).get("position", 999)
            p7_pos = prev_7.get(url,  {}).get("position", 999)
            # Recovering: clicks going up OR position improving (lower number)
            if (r7 > p7 and r7 > 0) or (p7_pos > r7_pos + 2 and r7_pos < 50):
                recovering_urls.add(url)
                print(f"  [skip-recovering] {url[-50:]} — clicks {p7}→{r7}, pos {p7_pos:.1f}→{r7_pos:.1f}")
    except Exception as e:
        print(f"  [warn] Could not fetch trend data: {e}")
        recovering_urls = set()

    # Also skip posts currently classified as top_performer — they've bounced back
    thresholds = config.get("search_console", {}).get("protection_thresholds", {})
    min_clicks_tp = thresholds.get("min_clicks", 10)
    top_performer_urls = set()
    for url, data in recent_7.items():
        if data.get("position", 999) <= 10 and data.get("clicks", 0) >= min_clicks_tp:
            top_performer_urls.add(url)

    lost_pages_filtered = []
    for p in lost_pages:
        if p["url"] in recovering_urls:
            print(f"  [skip-recovering] Skipping — page is actively recovering: {p['url'][-50:]}")
        elif p["url"] in top_performer_urls:
            print(f"  [skip-top_performer] Skipping — page is now a top performer: {p['url'][-50:]}")
        else:
            lost_pages_filtered.append(p)

    skipped_recovering = len(lost_pages) - len(lost_pages_filtered)
    if skipped_recovering:
        print(f"\n  {skipped_recovering} candidate(s) skipped — recovering or performing well. Leave them alone.")

    lost_pages = lost_pages_filtered

    # Fetch per-page query data so we can generate targeted recovery rewrites
    page_queries = {}
    try:
        print("\n  Fetching query-level GSC data for recovery rewrites...")
        page_queries = fetch_page_queries(config, days=90)
    except Exception as e:
        print(f"  [gsc] Could not fetch query data (recovery rewrites will be skipped): {e}")

    if not lost_pages:
        print("\n  No pages need recovery (drops detected but all are recovering or performing well).")
        return

    # ────────────────────────────────────────────
    # Phase 2: Filter already-processed URLs
    # ────────────────────────────────────────────
    recovery_history = _load_recovery_history(config)
    already_done = recovery_history

    new_pages = [p for p in lost_pages if p["url"] not in already_done]
    skipped_count = len(lost_pages) - len(new_pages)

    if skipped_count:
        print(f"\n  [recovery] Skipping {skipped_count} already-processed URL(s) from previous runs.")
        for url, entry in already_done.items():
            if any(p["url"] == url for p in lost_pages):
                print(f"    - {url} (decision: {entry['decision']}, processed: {entry['processed_at'][:10]})")

    if not new_pages:
        print("\n  All detected drops have already been reviewed in previous runs.")
        print("  Nothing new to process.")
        return

    # ────────────────────────────────────────────
    # Phase 3: Review & Restore
    # ────────────────────────────────────────────
    print(f"\n[Phase 3] Reviewing {len(new_pages)} new recovery candidate(s):")

    restored_count = 0

    for idx, page in enumerate(new_pages, 1):
        cause = page.get("cause", "unknown")
        has_original_body = bool(page.get("original_body"))

        if cause == "title_changed_url_broken":
            cause_label = "⚠️ כתובת URL שבורה (שינוי כותרת)"
        elif cause == "content_rewrite_drop":
            cause_label = "📉 ירידה בביצועי תוכן"
        else:
            cause_label = "❓ עדכון ידוע — כותרת מקורית לא נשמרה"

        print(f"\n  {'━' * 50}")
        print(f"  [{idx}/{len(new_pages)}] {cause_label}")
        print(f"  URL:            {page['url']}")
        print(f"  כותרת נוכחית:  {page['current_title']}")
        if page.get("original_title"):
            print(f"  כותרת מקורית:  {page['original_title']}")
        else:
            print(f"  כותרת מקורית:  [לא נשמרה — עדכון ישן]")
        print(f"  גיבוי תוכן:    {'✅ זמין' if has_original_body else '❌ לא קיים (עדכון ישן)'}")
        print(f"  ירידה:          {page['drop_pct']}%")
        print(f"  לפני: {page['old_metrics']['clicks']} קליקים, {page['old_metrics']['impressions']} חשיפות, מיקום {page['old_metrics']['position']}")
        print(f"  אחרי: {page['new_metrics'].get('clicks', 0)} קליקים, {page['new_metrics'].get('impressions', 0)} חשיפות")

        # For old entries with no original_title, we can't restore — just flag & record
        if cause == "updated_no_history" or not page.get("original_title"):
            print(f"  [!] כותרת מקורית אינה ידועה — לא ניתן לשחזר אוטומטית.")
            print(f"      יש לבדוק ידנית: {page['url']}")
            message = (
                f"❓ *עמוד עם ירידה — {site_name}*\n\n"
                f"{cause_label}\n"
                f"URL: {page['url']}\n\n"
                f"*כותרת נוכחית:* {page['current_title']}\n"
                f"הכותרת המקורית לא נשמרה (עדכון ישן).\n\n"
                f"📉 *ירידה:* {page['drop_pct']}%\n"
                f"לפני: {page['old_metrics']['clicks']} קליקים | {page['old_metrics']['impressions']} חשיפות | מיקום {page['old_metrics']['position']}\n"
                f"אחרי:  {page['new_metrics'].get('clicks', 0)} קליקים | {page['new_metrics'].get('impressions', 0)} חשיפות\n\n"
                f"יש לבדוק ידנית. הודעה זו לא תחזור שוב."
            )
            send_whatsapp_message(message, config)
            recovery_history = _record_recovery_decision(page["url"], "flagged_no_history", page, config, history=recovery_history)
            continue

        # Gather GSC queries for this URL (used for recovery rewrites)
        url_queries = page_queries.get(page["url"], [])
        top_queries_str = ", ".join(f'"{q["query"]}"' for q in url_queries[:5]) if url_queries else "לא נמצאו"

        if cause == "title_changed_url_broken":
            action_desc = "שחזור הכותרת המקורית יחזיר את ה-URL המקורי ויתקן את ה-404."
            restore_options = "להחזיר את הכותרת המקורית?"
        elif has_original_body:
            action_desc = "גיבוי מלא זמין — ניתן לשחזר כותרת + תוכן מקוריים."
            restore_options = "להחזיר כותרת + תוכן מקוריים? (גיבוי מלא זמין)"
        elif url_queries:
            action_desc = (
                f"אין גיבוי תוכן. ניתן לשכתב מחדש עם מיקוד בשאילתות שגוגל שיוך לעמוד:\n"
                f"{top_queries_str}"
            )
            restore_options = "לשכתב מחדש עם מיקוד בשאילתות האלה? (ישלח לאישור לפני פרסום)"
        else:
            action_desc = "הכותרת נשמרה, אך ביצועי התוכן ירדו אחרי העדכון. אין גיבוי ואין נתוני שאילתות."
            restore_options = "לסמן כטופל ידנית?"

        message = (
            f"🔄 *שחזור עמוד — {site_name}*\n\n"
            f"{cause_label}\n"
            f"URL: {page['url']}\n\n"
            f"*כותרת:* {page['original_title']}\n"
            f"*גיבוי תוכן:* {'✅ מלא' if has_original_body else '❌ לא קיים'}\n\n"
            f"📉 *ירידה בביצועים:* {page['drop_pct']}%\n"
            f"לפני: {page['old_metrics']['clicks']} קליקים | {page['old_metrics']['impressions']} חשיפות | מיקום {page['old_metrics']['position']}\n"
            f"אחרי:  {page['new_metrics'].get('clicks', 0)} קליקים | {page['new_metrics'].get('impressions', 0)} חשיפות\n\n"
            f"{action_desc}\n\n"
            f"{restore_options}"
        )

        status, _ = send_whatsapp_message(message, config)

        if status == "approved":
            if cause == "title_changed_url_broken" or has_original_body:
                # ── Path A: restore from backup (title ± body) ──
                try:
                    restore_fields = {"title": page["original_title"]}
                    if has_original_body:
                        restore_fields["body"] = page["original_body"]
                        print(f"  Restoring original title + body...")
                    else:
                        print(f"  Restoring original title only...")

                    modified = _mongo_update_post(page["post_id"], restore_fields, config)
                    if modified:
                        desc = "כותרת + תוכן" if has_original_body else "כותרת"
                        print(f"  Restored {desc}: '{page['original_title']}'")
                        restored_count += 1
                        recovery_history = _record_recovery_decision(page["url"], "approved", page, config, history=recovery_history)
                    else:
                        print(f"  [warning] No document modified — post may have been deleted")
                        recovery_history = _record_recovery_decision(page["url"], "approved_not_found", page, config, history=recovery_history)
                except Exception as e:
                    print(f"  [error] Failed to restore: {e}")

            elif url_queries:
                # ── Path B: no backup — generate a targeted recovery rewrite using GSC queries ──
                print(f"  Generating recovery rewrite using {len(url_queries)} GSC queries...")
                try:
                    from generator.gemini_client import generate_recovery_rewrite
                    from publisher.mongodb_client import fetch_post_by_id
                    from publisher.tiptap_converter import extract_text_from_tiptap

                    # Fetch current post content so the rewrite has context
                    current_post = fetch_post_by_id(page["post_id"], config)
                    if current_post:
                        body_text = extract_text_from_tiptap(
                            current_post.get("body", "")
                            if isinstance(current_post.get("body"), dict)
                            else json.loads(current_post.get("body", "{}") or "{}")
                        )
                        post_data_for_rewrite = {
                            "title": page["original_title"],
                            "content_text": body_text[:3000],
                            "old_clicks": page["old_metrics"].get("clicks", 0),
                            "old_impressions": page["old_metrics"].get("impressions", 0),
                            "old_position": page["old_metrics"].get("position", "?"),
                        }
                    else:
                        post_data_for_rewrite = {
                            "title": page["original_title"],
                            "content_text": "",
                            "old_clicks": page["old_metrics"].get("clicks", 0),
                            "old_impressions": page["old_metrics"].get("impressions", 0),
                            "old_position": page["old_metrics"].get("position", "?"),
                        }

                    rewritten = generate_recovery_rewrite(post_data_for_rewrite, url_queries, config)

                    if rewritten.startswith("[Gemini Error]"):
                        print(f"  {rewritten}")
                        recovery_history = _record_recovery_decision(page["url"], "rewrite_failed", page, config, history=recovery_history)
                    else:
                        # Send the rewrite for WhatsApp review before publishing
                        final_output, rewrite_approved = _review_loop(
                            rewritten, config, site_name,
                            label=f"שחזור: {page['original_title'][:40]}"
                        )

                        if rewrite_approved:
                            from publisher.post_publisher import update_existing_post
                            result = update_existing_post(
                                post_id=page["post_id"],
                                gemini_output=final_output,
                                desktop_image_bytes=None,
                                mobile_image_bytes=None,
                                config=config,
                                preserve_title=page["original_title"],
                            )
                            print(f"  Recovery rewrite published: '{result['title']}'")
                            restored_count += 1
                            recovery_history = _record_recovery_decision(page["url"], "rewrite_approved", page, config, history=recovery_history)
                        else:
                            print(f"  Recovery rewrite rejected")
                            recovery_history = _record_recovery_decision(page["url"], "rewrite_rejected", page, config, history=recovery_history)

                except Exception as e:
                    print(f"  [error] Recovery rewrite failed: {e}")
                    recovery_history = _record_recovery_decision(page["url"], "rewrite_error", page, config, history=recovery_history)
            else:
                # No backup, no queries — just flag it
                recovery_history = _record_recovery_decision(page["url"], "approved_manual", page, config, history=recovery_history)
                print(f"  Marked as manually handled")

        elif status == "rejected":
            print(f"  Skipped (rejected)")
            recovery_history = _record_recovery_decision(page["url"], "rejected", page, config, history=recovery_history)
        else:
            print(f"  Skipped (no response / error)")
            recovery_history = _record_recovery_decision(page["url"], "skipped_no_response", page, config, history=recovery_history)

    # ────────────────────────────────────────────
    # Summary
    # ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RECOVERY SUMMARY")
    print("=" * 60)
    print(f"  Site: {site_name}")
    print(f"  New candidates reviewed: {len(new_pages)}")
    print(f"  Previously processed (skipped): {skipped_count}")
    print(f"  Pages restored: {restored_count}")
    print("=" * 60)


# ═══════════════════════════════════════════════
# Mode 7: Diagnose — Deep SEO Analysis
# ═══════════════════════════════════════════════

def run_diagnose_pipeline(config):
    """
    Deep SEO diagnosis: pulls every available signal from GSC + PageSpeed API,
    cross-references with MongoDB content, and produces an actionable report.

    Sections:
      1. Indexing Coverage   — which posts Google has/hasn't indexed
      2. Position Distribution — how posts are spread across ranking positions
      3. Traffic Trend       — weekly clicks/impressions over 12 weeks
      4. Mobile vs Desktop   — ranking gap by device
      5. Cannibalization     — queries where multiple posts compete
      6. CTR Opportunities   — high-impression queries with very low CTR
      7. Core Web Vitals     — PageSpeed scores for top pages (free API)
      8. Zero-Click Pages    — ranked but never clicked
      9. Quick Wins          — page-2 posts closest to page 1
     10. Recommendations     — prioritized action list
    """
    from tools.search_console import (
        fetch_gsc_performance, fetch_page_queries,
        fetch_gsc_by_device, fetch_gsc_weekly_trends,
        find_cannibalization, find_coverage_gaps,
        classify_page_seo, ping_sitemap, inspect_urls_batch,
        match_post_to_gsc_url,
    )
    from tools.pagespeed import check_pages_speed, format_cwv_summary
    from publisher.mongodb_client import fetch_all_blog_posts, fetch_static_pages
    from urllib.parse import unquote, urlparse

    site_name = config["site"]["name"]
    domain = config["site"]["domain"]
    blog_path = config["site"].get("blog_url", f"https://{domain}/blog")
    blog_url_path = urlparse(blog_path).path.rstrip("/")

    print("=" * 60)
    print(f"  {site_name} — DEEP SEO DIAGNOSIS")
    print("=" * 60)

    if not config.get("search_console"):
        print("\n  [error] search_console config missing. Cannot run diagnosis.")
        print("\n  Add the following to your config.yaml:")
        print("    search_console:")
        print("      credentials_file: \"client_secret_....json\"")
        print("      token_file: \"gsc_token.json\"")
        print(f"      site_url: \"sc-domain:{domain}\"")
        print("      protection_thresholds:")
        print("        min_clicks: 10")
        print("        min_impressions: 100")
        print("        max_position: 20.0")
        print("\n  Or use a config that already has it:")
        print("    python run.py diagnose --config config.pawly.yaml")
        return

    report_lines = []
    report_lines.append(f"SEO DIAGNOSIS — {site_name} ({domain})")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append("=" * 60)

    def section(title):
        report_lines.append("")
        report_lines.append(f"[{title}]")
        report_lines.append("-" * 50)

    def line(text=""):
        report_lines.append(text)
        print(f"  {text}")

    # ── Fetch all data ──
    print("\n[Fetching GSC data...]")
    try:
        gsc_perf = fetch_gsc_performance(config, days=90)
        page_queries = fetch_page_queries(config, days=90)
    except Exception as e:
        print(f"  [error] GSC fetch failed: {e}")
        return

    try:
        device_data = fetch_gsc_by_device(config, days=90)
    except Exception as e:
        print(f"  [gsc] Device data unavailable: {e}")
        device_data = {}

    try:
        weekly_trends = fetch_gsc_weekly_trends(config, weeks=12)
    except Exception as e:
        print(f"  [gsc] Weekly trends unavailable: {e}")
        weekly_trends = []

    blog_posts = fetch_all_blog_posts(config)
    print(f"  MongoDB: {len(blog_posts)} posts, GSC: {len(gsc_perf)} pages tracked")

    # ────────────────────────────────────────────
    # Section 1: Indexing Coverage
    # ────────────────────────────────────────────
    section("1. INDEXING COVERAGE")
    coverage = find_coverage_gaps(gsc_perf, blog_posts, config)
    total = coverage["total_posts"]
    indexed_n = coverage["indexed_count"]
    not_indexed_n = len(coverage["not_indexed"])
    zero_clicks_n = len(coverage["zero_clicks"])

    line(f"Total blog posts in MongoDB : {total}")
    line(f"Posts found in GSC          : {indexed_n}  ({coverage['coverage_pct']}%)")
    line(f"Posts NOT in GSC (unindexed?): {not_indexed_n}")
    line(f"Posts ranked but 0 clicks   : {zero_clicks_n}")

    # Duplicate title detection — same topic published twice = both may get deindexed
    title_prefixes = Counter()
    for p in blog_posts:
        title = p.get("title", "")
        # First 15 chars is enough to detect near-duplicates
        prefix = title[:20].strip()
        if prefix:
            title_prefixes[prefix] += 1
    duplicate_titles = [(prefix, count) for prefix, count in title_prefixes.items() if count > 1]
    if duplicate_titles:
        line("")
        line(f"DUPLICATE CONTENT WARNING — {len(duplicate_titles)} topic(s) published multiple times:")
        for prefix, count in sorted(duplicate_titles, key=lambda x: -x[1]):
            line(f"  {count}x posts starting with: \"{prefix}...\"")
        line("  Action: merge or redirect duplicates — Google may deindex ALL versions")

    # Submit sitemap now to speed up indexing of missing posts
    if not_indexed_n > 0:
        line("")
        line("Submitting sitemap to GSC to speed up indexing...")
        try:
            pinged = ping_sitemap(config)
            if pinged:
                line("Sitemap submitted successfully — Google will re-crawl within hours")
        except Exception as e:
            line(f"Sitemap ping failed: {e}")

    # URL Inspection — discover live post URLs then inspect each one via GSC API
    if coverage["not_indexed"] and not_indexed_n > 0:
        line("")
        line("Posts with NO GSC impressions:")
        for p in coverage["not_indexed"][:15]:
            line(f"  - {p.get('title', '?')[:70]}")
        if not_indexed_n > 15:
            line(f"  ... and {not_indexed_n - 15} more")

        line("")
        line("Discovering live post URLs by crawling sitemap + blog index...")
        try:
            from tools.blog_analyzer import discover_blog_posts
            user_agent = config.get("scraping", {}).get("user_agent")
            live_urls = discover_blog_posts(blog_path, domain, user_agent=user_agent)
            live_urls_gsc_known = set(gsc_perf.keys())
            # URLs present on site but NOT in GSC at all
            truly_unindexed_urls = [u for u in live_urls if u not in live_urls_gsc_known]
            line(f"Live URLs on site: {len(live_urls)}  |  Not in GSC: {len(truly_unindexed_urls)}")

            if truly_unindexed_urls:
                inspect_count = min(len(truly_unindexed_urls), 20)
                line(f"")
                line(f"Running GSC URL Inspection on {inspect_count} unindexed URLs (~{inspect_count * 1.5:.0f}s)...")
                inspection_results = inspect_urls_batch(config, truly_unindexed_urls[:inspect_count])

                # Group by coverage state
                by_state = {}
                for url, res in inspection_results.items():
                    state = res.get("coverageState", "Unknown")
                    if state not in by_state:
                        by_state[state] = []
                    slug = unquote(url.rstrip("/").split("/")[-1])
                    by_state[state].append((slug, url, res))

                line("")
                line("Indexing status breakdown:")
                for state, entries in sorted(by_state.items(), key=lambda x: -len(x[1])):
                    line(f"  [{state}] — {len(entries)} URLs")
                    for slug, url, res in entries[:5]:
                        robots = res.get("robotsTxtState", "")
                        fetch = res.get("pageFetchState", "")
                        extras = " | ".join(x for x in [robots, fetch] if x and x not in ("ALLOWED", "SUCCESSFUL"))
                        line(f"    {slug[:60]}{('  →  ' + extras) if extras else ''}")
                    if len(entries) > 5:
                        line(f"    ... and {len(entries)-5} more")

                # Explain each state in plain English
                explanations = {
                    "Crawled - currently not indexed": "Google crawled these but decided NOT to index them. Usually means thin content, duplicate content, or low-quality signal. Fix: improve content quality, merge near-duplicates.",
                    "Discovered - currently not indexed": "Google knows about these URLs but hasn't crawled them yet. Fix: sitemap submitted (done), build internal links pointing to these posts.",
                    "Duplicate, Google chose different canonical than user": "Google sees this as a duplicate of another page. Fix: add a canonical tag pointing to the preferred URL.",
                    "Page with redirect": "Page redirects to another URL. Fix: check if the post URL changed.",
                    "Not found (404)": "Page returns 404 — not published or wrong URL. Fix: check that the post is live.",
                    "Blocked by robots.txt": "Googlebot is blocked from crawling. Fix: check robots.txt rules.",
                    "Alternate page with proper canonical tag": "Page exists but Google is indexing the canonical version. Likely OK.",
                }
                line("")
                line("What each status means and how to fix it:")
                for state in by_state:
                    if state in explanations:
                        line(f"  '{state}':")
                        line(f"    {explanations[state]}")
            else:
                line("All live URLs appear in GSC — coverage looks good")
        except Exception as e:
            line(f"URL discovery/inspection failed: {e}")
            line("Manual check: open GSC → Coverage → see which pages are 'Excluded'")

    # ────────────────────────────────────────────
    # Section 2: Position Distribution
    # ────────────────────────────────────────────
    section("2. POSITION DISTRIBUTION (last 90 days)")
    pos_buckets = {"top3": [], "page1": [], "page2": [], "deep": [], "no_data": []}
    for post in blog_posts:
        title = post.get("title", "")
        url, data = match_post_to_gsc_url(title, gsc_perf, config)
        if not data:
            pos_buckets["no_data"].append(title)
            continue
        pos = data.get("position", 999)
        if pos <= 3:
            pos_buckets["top3"].append((title, pos))
        elif pos <= 10:
            pos_buckets["page1"].append((title, pos))
        elif pos <= 30:
            pos_buckets["page2"].append((title, pos))
        else:
            pos_buckets["deep"].append((title, pos))

    for label, key, emoji in [
        ("Top 3  (pos 1-3)  ",  "top3",    "BEST"),
        ("Page 1 (pos 4-10) ",  "page1",   "GOOD"),
        ("Page 2 (pos 11-30)",  "page2",   "OPPORTUNITY"),
        ("Deep   (pos 31+)  ",  "deep",    "WEAK"),
        ("Not in GSC        ",  "no_data", "UNINDEXED?"),
    ]:
        count = len(pos_buckets[key])
        pct = round(count / total * 100) if total else 0
        bar = "#" * (count * 30 // max(total, 1))
        line(f"  {label}: {count:3d} posts ({pct:2d}%)  [{emoji}]")

    # ────────────────────────────────────────────
    # Section 3: Traffic Trend
    # ────────────────────────────────────────────
    section("3. WEEKLY TRAFFIC TREND (last 12 weeks)")
    if weekly_trends and len(weekly_trends) >= 3:
        # Show each week
        for w in weekly_trends:
            bar_len = min(w["clicks"] * 40 // max(t["clicks"] for t in weekly_trends if t["clicks"]) if any(t["clicks"] for t in weekly_trends) else 1, 40)
            bar = "#" * bar_len
            line(f"  {w['week_start']}  {w['clicks']:5d} clicks  {w['impressions']:7d} impr  pos {w['avg_position']:5.1f}  {bar}")

        # Trend detection: compare last 3 weeks vs first 3 weeks
        first3 = weekly_trends[:3]
        last3 = weekly_trends[-3:]
        avg_first = sum(w["clicks"] for w in first3) / 3
        avg_last = sum(w["clicks"] for w in last3) / 3
        if avg_first > 0:
            trend_pct = round((avg_last - avg_first) / avg_first * 100)
            trend_label = f"+{trend_pct}% (GROWING)" if trend_pct > 10 else (
                f"{trend_pct}% (DECLINING)" if trend_pct < -10 else f"{trend_pct}% (STABLE)"
            )
            line("")
            line(f"  Overall trend: {trend_label}")
    else:
        line("  Not enough data for trend analysis")

    # ────────────────────────────────────────────
    # Section 4: Mobile vs Desktop Gap
    # ────────────────────────────────────────────
    section("4. MOBILE vs DESKTOP RANKING GAP")
    if device_data:
        gaps = []
        for url, devices in device_data.items():
            if blog_url_path not in url:
                continue
            mob = devices.get("MOBILE", {})
            desk = devices.get("DESKTOP", {})
            mob_pos = mob.get("position", 0)
            desk_pos = desk.get("position", 0)
            if mob_pos > 0 and desk_pos > 0:
                gap = mob_pos - desk_pos
                if gap > 3:  # mobile ranks significantly worse
                    gaps.append({
                        "url": url,
                        "mobile_pos": mob_pos,
                        "desktop_pos": desk_pos,
                        "gap": gap,
                        "mobile_clicks": mob.get("clicks", 0),
                    })

        gaps.sort(key=lambda x: x["gap"], reverse=True)

        blog_device_urls = {u: d for u, d in device_data.items() if blog_url_path in u}
        mob_positions = [d.get("MOBILE", {}).get("position", 0) for d in blog_device_urls.values() if d.get("MOBILE", {}).get("position", 0) > 0]
        desk_positions = [d.get("DESKTOP", {}).get("position", 0) for d in blog_device_urls.values() if d.get("DESKTOP", {}).get("position", 0) > 0]

        if mob_positions and desk_positions:
            avg_mob = round(sum(mob_positions) / len(mob_positions), 1)
            avg_desk = round(sum(desk_positions) / len(desk_positions), 1)
            overall_gap = round(avg_mob - avg_desk, 1)
            line(f"  Average desktop position : {avg_desk}")
            line(f"  Average mobile  position : {avg_mob}")
            line(f"  Mobile penalty (avg)     : +{overall_gap} positions worse" if overall_gap > 0 else f"  Mobile advantage: {overall_gap}")
            if overall_gap > 5:
                line(f"  WARNING: Large mobile gap suggests Core Web Vitals or mobile UX issues")
            line("")

        if gaps:
            line(f"  Pages with largest mobile gap (mobile ranks >3 positions worse):")
            for g in gaps[:10]:
                slug = g["url"].rstrip("/").split("/")[-1]
                line(f"  {slug[:50]:50s}  desk={g['desktop_pos']:.0f}  mob={g['mobile_pos']:.0f}  gap=+{g['gap']:.1f}")
        else:
            line("  No significant mobile/desktop gap detected")
    else:
        line("  Device data unavailable")

    # ────────────────────────────────────────────
    # Section 5: Keyword Cannibalization
    # ────────────────────────────────────────────
    section("5. KEYWORD CANNIBALIZATION")
    cannibalized = find_cannibalization(page_queries, blog_path=blog_url_path, min_impressions=10, min_urls=2)
    if cannibalized:
        line(f"  {len(cannibalized)} queries where multiple posts compete (splitting ranking signals):")
        line("")
        for c in cannibalized[:20]:
            line(f"  Query: \"{c['query']}\"  ({c['url_count']} URLs, {c['total_impressions']} impr, best pos {c['best_position']})")
            for entry in c["urls"][:3]:
                slug = entry["url"].rstrip("/").split("/")[-1]
                line(f"    pos {entry['position']:5.1f}  {entry['clicks']}c  {entry['impressions']}i  {slug[:50]}")
    else:
        line("  No cannibalization detected (each query has a clear winning page)")

    # ────────────────────────────────────────────
    # Section 6: CTR Opportunities
    # ────────────────────────────────────────────
    section("6. CTR OPPORTUNITIES (ranking well, not getting clicked)")
    # Expected CTR benchmarks by position
    expected_ctr = {1: 0.28, 2: 0.15, 3: 0.11, 4: 0.08, 5: 0.07,
                    6: 0.06, 7: 0.05, 8: 0.04, 9: 0.04, 10: 0.03}

    ctr_opps = []
    for url, data in gsc_perf.items():
        if blog_url_path not in url:
            continue
        pos = data.get("position", 0)
        ctr = data.get("ctr", 0)
        impressions = data.get("impressions", 0)
        if pos < 1 or pos > 10 or impressions < 50:
            continue
        pos_int = max(1, min(10, round(pos)))
        expected = expected_ctr.get(pos_int, 0.03)
        if ctr < expected * 0.5:  # CTR less than half of expected
            ctr_opps.append({
                "url": url,
                "position": pos,
                "ctr_pct": round(ctr * 100, 1),
                "expected_pct": round(expected * 100, 1),
                "impressions": impressions,
                "missed_clicks": round(impressions * (expected - ctr)),
            })

    ctr_opps.sort(key=lambda x: x["missed_clicks"], reverse=True)

    if ctr_opps:
        line(f"  {len(ctr_opps)} pages ranking in top 10 but CTR far below expected:")
        line(f"  (Fix: improve title/meta description to be more compelling)")
        line("")
        for c in ctr_opps[:15]:
            slug = c["url"].rstrip("/").split("/")[-1]
            line(f"  pos {c['position']:4.1f}  CTR {c['ctr_pct']:4.1f}% (expected ~{c['expected_pct']}%)  -{c['missed_clicks']} clicks/day lost  {slug[:45]}")
    else:
        line("  No major CTR issues detected")

    # ────────────────────────────────────────────
    # Section 7: Core Web Vitals (PageSpeed)
    # ────────────────────────────────────────────
    section("7. CORE WEB VITALS — MOBILE (PageSpeed Insights)")
    # Check top pages by impressions (most important to fix first)
    top_urls_for_cwv = sorted(
        [u for u in gsc_perf if blog_url_path in u],
        key=lambda u: gsc_perf[u].get("impressions", 0),
        reverse=True
    )[:5]

    if top_urls_for_cwv:
        line(f"  Checking {len(top_urls_for_cwv)} top pages (by impressions)...")
        line("")
        psi_api_key = config.get("pagespeed", {}).get("api_key")
        cwv_results = check_pages_speed(top_urls_for_cwv, strategy="mobile", api_key=psi_api_key, max_pages=5)

        failed_cwv = 0
        checked_cwv = 0
        for url in top_urls_for_cwv:
            cwv = cwv_results.get(url, {})
            # Decode Hebrew URL slugs for readable output
            decoded_url = unquote(url)
            summary = format_cwv_summary(decoded_url, cwv, prefix="  ")
            line(summary)
            if cwv and not cwv.get("error"):
                checked_cwv += 1
                for metric in ["lcp", "cls", "inp"]:
                    if cwv.get("ratings", {}).get(metric) == "POOR":
                        failed_cwv += 1
                        break

        line("")
        if checked_cwv == 0:
            line(f"  All {len(top_urls_for_cwv)} requests were rate-limited by PageSpeed API.")
            line(f"  Add a free API key to config: pagespeed.api_key (console.cloud.google.com)")
            line(f"  Or check manually: https://pagespeed.web.dev/")
        elif failed_cwv > 0:
            line(f"  {failed_cwv}/{checked_cwv} pages have POOR Core Web Vitals")
            line(f"  Core Web Vitals are a Google ranking factor — fixing them directly improves rankings")
        else:
            line(f"  Core Web Vitals look healthy on {checked_cwv} tested pages")
    else:
        line("  No pages found to test")

    # ────────────────────────────────────────────
    # Section 8: Zero-Click Pages (ranked but never clicked)
    # ────────────────────────────────────────────
    section("8. ZERO-CLICK PAGES (impressions but 0 clicks)")
    zero_click_pages = [
        (url, data) for url, data in gsc_perf.items()
        if blog_url_path in url and data.get("clicks", 0) == 0 and data.get("impressions", 0) >= 20
    ]
    zero_click_pages.sort(key=lambda x: x[1].get("impressions", 0), reverse=True)

    if zero_click_pages:
        line(f"  {len(zero_click_pages)} pages Google shows but nobody clicks:")
        line(f"  (Fix: improve title + meta description for these pages)")
        line("")
        for url, data in zero_click_pages[:15]:
            slug = url.rstrip("/").split("/")[-1]
            line(f"  pos {data.get('position', 0):5.1f}  {data.get('impressions', 0):5d} impr  0 clicks  {slug[:50]}")
    else:
        line("  No zero-click pages with significant impressions")

    # ────────────────────────────────────────────
    # Section 9: Quick Wins — Closest to Page 1
    # ────────────────────────────────────────────
    section("9. QUICK WINS — Pages Closest to Page 1 (pos 11-20)")
    quick_wins = [
        (url, data) for url, data in gsc_perf.items()
        if blog_url_path in url and 11 <= data.get("position", 0) <= 20 and data.get("impressions", 0) >= 20
    ]
    quick_wins.sort(key=lambda x: (x[1].get("position", 999), -x[1].get("impressions", 0)))

    if quick_wins:
        line(f"  {len(quick_wins)} pages on page 2 that a content update could push to page 1:")
        line("")
        for url, data in quick_wins[:15]:
            slug = url.rstrip("/").split("/")[-1]
            line(f"  pos {data.get('position', 0):5.1f}  {data.get('clicks', 0):4d}c  {data.get('impressions', 0):6d}i  {slug[:50]}")
        # Find the queries for each quick win
        line("")
        line("  Top queries for these pages:")
        for url, data in quick_wins[:5]:
            slug = url.rstrip("/").split("/")[-1]
            queries = page_queries.get(url, [])[:3]
            if queries:
                q_str = " | ".join(f'"{q["query"]}"' for q in queries)
                line(f"  {slug[:35]:35s} → {q_str}")
    else:
        line("  No pages in position 11-20 with significant impressions")

    # ────────────────────────────────────────────
    # Section 10: Prioritized Recommendations
    # ────────────────────────────────────────────
    section("10. PRIORITIZED RECOMMENDATIONS")

    recommendations = []

    if not_indexed_n > 0:
        recommendations.append((1, f"REWRITE {not_indexed_n} UNINDEXED POSTS (content quality)",
            f"{not_indexed_n} posts have zero GSC impressions — Google has never indexed them. "
            "Most likely cause: thin, promotional, or B2B content that doesn't match searcher intent. "
            "Run: python run.py update — the engine now detects not_indexed posts, rewrites them to target "
            "real consumer queries, and allows new titles. Sitemap was already submitted this run."))

    if cannibalized:
        top_cannib = cannibalized[0]
        recommendations.append((2, f"FIX {len(cannibalized)} CANNIBALIZED QUERIES",
            f"Multiple posts compete for the same queries (e.g. '{top_cannib['query']}'). "
            "Merge the weaker post into the stronger one, or clearly differentiate their target keywords. "
            "Cannibalization splits your ranking signal — fixing it can double positions overnight."))

    if quick_wins:
        recommendations.append((3, f"CONTENT UPDATE: {len(quick_wins)} PAGE-2 POSTS",
            f"Run: python run.py update — these posts are already on page 2 and one solid content expansion "
            "is often enough to push to page 1. The engine will prioritize them (page2_opportunity category)."))

    if ctr_opps:
        total_missed = sum(c["missed_clicks"] for c in ctr_opps)
        recommendations.append((4, f"FIX {len(ctr_opps)} LOW-CTR TITLES (est. ~{total_missed} missed clicks)",
            "Pages rank in top 10 but their title/meta description isn't compelling enough. "
            "Run: python run.py update — the engine detects ctr_opportunity and updates only the meta description. "
            "No body changes = no ranking risk."))

    mobile_gap_bad = device_data and any(
        d.get("MOBILE", {}).get("position", 0) - d.get("DESKTOP", {}).get("position", 0) > 5
        for d in device_data.values()
        if d.get("MOBILE", {}).get("position", 0) > 0 and d.get("DESKTOP", {}).get("position", 0) > 0
    )
    if mobile_gap_bad:
        recommendations.append((5, "FIX MOBILE PERFORMANCE (Core Web Vitals)",
            "Large mobile/desktop ranking gap detected. Main causes: slow LCP (images too large), "
            "CLS (layout shifts from ads/images), slow TTFB (server response). "
            "Fix: compress images, add explicit width/height to all img tags, optimize server response time."))

    recommendations.sort(key=lambda x: x[0])
    for priority, title, detail in recommendations:
        line(f"  Priority {priority}: {title}")
        # Wrap detail text
        words = detail.split()
        current_line = "    "
        for word in words:
            if len(current_line) + len(word) + 1 > 70:
                line(current_line)
                current_line = "    " + word
            else:
                current_line += (" " if current_line.strip() else "") + word
        if current_line.strip():
            line(current_line)
        line("")

    # ────────────────────────────────────────────
    # Section 11: Static Pages
    # ────────────────────────────────────────────
    static_pages = []
    try:
        static_pages = fetch_static_pages(config)
    except Exception as e:
        pass

    if static_pages:
        section("11. STATIC PAGES")
        static_history = _load_static_history(config)
        in_gsc = 0
        not_in_gsc = 0
        poor_ranking = 0

        for page in static_pages:
            title = page.get("title", page.get("pageId", "?"))
            url, metrics = match_post_to_gsc_url(title, gsc_perf, config)
            if url and metrics:
                in_gsc += 1
                pos = metrics.get("position", 0)
                clicks = metrics.get("clicks", 0)
                impressions = metrics.get("impressions", 0)
                flag = ""
                if pos > 30:
                    poor_ranking += 1
                    flag = "  [!] דירוג גרוע (>30)"
                hist_entry = static_history.get(page.get("_id", ""), static_history.get(page.get("pageId", ""), {}))
                last_updated = hist_entry.get("updated_at", "לא עודכן")[:10] if hist_entry else "לא עודכן"
                line(f"  {title[:45]:45s}  pos={pos:5.1f}  {clicks}c  {impressions}i  עודכן:{last_updated}{flag}")
            else:
                not_in_gsc += 1
                hist_entry = static_history.get(page.get("_id", ""), static_history.get(page.get("pageId", ""), {}))
                last_updated = hist_entry.get("updated_at", "לא עודכן")[:10] if hist_entry else "לא עודכן"
                line(f"  {title[:45]:45s}  [לא מאונדקס]  עודכן:{last_updated}")

        line("")
        line(f"  סה\"כ עמודים סטטיים : {len(static_pages)}")
        line(f"  נמצאו ב-GSC        : {in_gsc}")
        line(f"  לא מאונדקסים       : {not_in_gsc}")
        if poor_ranking:
            line(f"  דירוג גרוע (>30)   : {poor_ranking}  [!] שקול לשכתב")

    # ────────────────────────────────────────────
    # Section 12: Product Pages
    # ────────────────────────────────────────────
    has_products = bool(config.get("mongodb", {}).get("products_database"))
    if has_products:
        section("12. PRODUCT PAGES")
        try:
            from publisher.mongodb_client import fetch_all_products
            from tools.product_pipeline import get_product_gsc_context, load_product_history
            products = fetch_all_products(config)
            product_history = load_product_history(config)

            total_products = len(products)
            prod_in_gsc = 0
            prod_not_indexed = 0
            pos_buckets = {"top10": [], "p2": [], "p3plus": []}
            prod_by_impressions = []

            for product in products:
                prod_url, gsc_ctx = get_product_gsc_context(product, gsc_perf, page_queries, config)
                cat = gsc_ctx.get("category", "not_indexed")
                metrics = gsc_ctx.get("metrics", {})
                impressions = metrics.get("impressions", 0)
                pos = metrics.get("position", 0)
                clicks = metrics.get("clicks", 0)

                if prod_url:
                    prod_in_gsc += 1
                    if pos <= 10:
                        pos_buckets["top10"].append(product)
                    elif pos <= 30:
                        pos_buckets["p2"].append(product)
                    else:
                        pos_buckets["p3plus"].append(product)
                    prod_by_impressions.append((product, impressions, pos, clicks))
                else:
                    prod_not_indexed += 1
                    prod_by_impressions.append((product, 0, 0, 0))

            line(f"  סה\"כ מוצרים        : {total_products}")
            line(f"  נמצאו ב-GSC        : {prod_in_gsc}")
            line(f"  לא מאונדקסים       : {prod_not_indexed}")
            line(f"  מוצרים מדודכנים    : {len(product_history)}")
            line("")
            line(f"  התפלגות דירוגים:")
            line(f"    עמוד 1 (1-10)  : {len(pos_buckets['top10'])} מוצרים")
            line(f"    עמוד 2 (11-30) : {len(pos_buckets['p2'])} מוצרים")
            line(f"    עמוד 3+ (31+)  : {len(pos_buckets['p3plus'])} מוצרים")
            line("")

            prod_by_impressions.sort(key=lambda x: x[1], reverse=True)
            top5 = prod_by_impressions[:5]
            bottom5 = [p for p in prod_by_impressions if p[1] == 0][:5]

            if top5:
                line("  טופ 5 מוצרים לפי חשיפות:")
                for product, impressions, pos, clicks in top5:
                    title = product.get("title", "")[:45]
                    line(f"    {title:45s}  pos={pos:5.1f}  {clicks}c  {impressions}i")

            if bottom5:
                line("")
                line("  מוצרים לא מאונדקסים (5 ראשונים):")
                for product, impressions, pos, clicks in bottom5:
                    title = product.get("title", "")[:45]
                    line(f"    {title:45s}  [לא מאונדקס]")

        except Exception as e:
            line(f"  [שגיאה בטעינת מוצרים] {e}")

    # ────────────────────────────────────────────
    # Save report to file
    # ────────────────────────────────────────────
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    collection = config["mongodb"]["collection"]
    report_path = os.path.join(output_dir, f"{collection}_diagnosis_{date_str}.txt")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n{'=' * 60}")
    print(f"  Report saved: {report_path}")
    print(f"{'=' * 60}")


# ═══════════════════════════════════════════════
# Mode 8: Products — SEO + branded images for wordpress_products
# ═══════════════════════════════════════════════

def _parse_product_output(gemini_output):
    """Parse Gemini product output into meta_description and html_content."""
    meta = ""
    html = ""
    lines = gemini_output.strip().splitlines()

    for i, line in enumerate(lines):
        if line.startswith("META_DESCRIPTION:"):
            meta = line[len("META_DESCRIPTION:"):].strip()
            break

    # HTML is between the two --- separators
    parts = re.split(r"^---\s*$", gemini_output, flags=re.MULTILINE)
    if len(parts) >= 3:
        html = parts[1].strip()
    elif len(parts) == 2:
        html = parts[1].strip()

    return meta, html


def run_products_pipeline(config):
    """
    SEO-optimize Pawly product pages:
    1. Fetch all products from wordpress_products collection
    2. Match each to GSC and classify (same logic as update mode)
    3. Rewrite content with Gemini (consumer-focused, preserves specs)
    4. Download real product image → apply Pawly branding → upload to Supabase
    5. WhatsApp review
    6. Apply updates to MongoDB (content, metaDescription, pawlyImageUrl)
    Processes 3 products per run. Skips top_performers and recently updated.
    """
    import re
    from publisher.mongodb_client import fetch_all_products, update_product, get_master_user_id
    from publisher.supabase_client import upload_image
    from generator.gemini_client import rewrite_product
    from tools.product_pipeline import (
        load_product_history, record_product_update,
        match_product_to_gsc, get_product_gsc_context,
        download_image, brand_product_image,
        strip_external_images, html_to_text,
    )

    site_name = config["site"]["name"]
    print("=" * 60)
    print(f"  {site_name} SEO — PRODUCT PAGES")
    print("=" * 60)

    # ── Phase 0: Site context ────────────────────────────────
    print(f"\n[Phase 0] Scraping {site_name} website for context...")
    site_context = scrape_site_context(config)

    # ── Phase 1: Fetch products ──────────────────────────────
    print("\n[Phase 1] Fetching products from MongoDB...")
    products = fetch_all_products(config)
    print(f"  {len(products)} products found")

    # ── Phase 2: GSC intelligence ────────────────────────────
    gsc_data = {}
    page_queries = {}
    gsc_failed = False

    if config.get("search_console"):
        print("\n[Phase 2] Fetching Google Search Console data...")
        try:
            from tools.search_console import fetch_gsc_performance, fetch_page_queries
            gsc_data = fetch_gsc_performance(config, days=90)
            page_queries = fetch_page_queries(config, days=90)

            # Classify each product
            cats = {}
            for product in products:
                gsc_url, gsc_ctx = get_product_gsc_context(product, gsc_data, page_queries, config)
                product["gsc_url"] = gsc_url
                product["gsc_context"] = gsc_ctx
                cat = gsc_ctx.get("category", "unknown")
                cats[cat] = cats.get(cat, 0) + 1

            for cat, count in sorted(cats.items()):
                print(f"  [gsc] {cat}: {count} products")

        except FileNotFoundError as e:
            print(f"\n  [gsc] ⚠️  BLOCKING UPDATES — GSC credentials not found: {e}")
            print("  Cannot safely update products without knowing which ones are ranking.")
            gsc_failed = True
            for product in products:
                product["gsc_url"] = None
                product["gsc_context"] = {"category": "unknown", "top_queries": [], "metrics": {}, "update_priority": 3}
        except Exception as e:
            print(f"\n  [gsc] ⚠️  BLOCKING UPDATES — GSC fetch failed: {e}")
            print("  Cannot safely update products without knowing which ones are ranking.")
            gsc_failed = True
            for product in products:
                product["gsc_url"] = None
                product["gsc_context"] = {"category": "unknown", "top_queries": [], "metrics": {}, "update_priority": 3}
    else:
        for product in products:
            product["gsc_url"] = None
            product["gsc_context"] = {"category": "not_indexed", "top_queries": [], "metrics": {}, "update_priority": 4}

    # Safety: if GSC was configured but failed, block all updates
    if gsc_failed:
        print("\n  ⚠️  GSC connection failed — products update BLOCKED to protect existing rankings.")
        print("  Fix the GSC credentials and re-run.")
        return

    # ── Phase 3: Build queue ─────────────────────────────────
    print("\n[Phase 3] Building rewrite queue...")
    history = load_product_history(config)
    COOLDOWN_BY_CATEGORY = {
        "not_indexed": 7,
        "ctr_opportunity": 14,
        "page2_opportunity": 21,
    }
    DEFAULT_COOLDOWN = 30
    MAX_PER_RUN = 10

    queue = []
    skipped = 0

    # Sort: indexed products first (higher ROI), then not_indexed
    products.sort(key=lambda p: p.get("gsc_context", {}).get("update_priority", 4))

    for product in products:
        if len(queue) >= MAX_PER_RUN:
            break

        pid = str(product["_id"])
        title = product.get("title", "")
        gsc_ctx = product.get("gsc_context", {})
        gsc_category = gsc_ctx.get("category", "unknown")

        # Skip top_performers — they're ranking well
        if gsc_category == "top_performer":
            print(f"  [skip] top_performer: {title[:55]}")
            skipped += 1
            continue

        # Check cooldown
        if pid in history:
            last_updated = history[pid].get("updated_at", "")
            try:
                last_dt = datetime.fromisoformat(last_updated).replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_dt).days
            except Exception:
                days_since = 999
            cooldown = COOLDOWN_BY_CATEGORY.get(gsc_category, DEFAULT_COOLDOWN)
            if days_since < cooldown:
                print(f"  [skip] cooldown ({gsc_category}) {days_since}d/{cooldown}d: {title[:50]}")
                skipped += 1
                continue

        queue.append(product)

    print(f"  Queue: {len(queue)} products  |  Skipped: {skipped}")

    if not queue:
        print("\n  No products to process this run.")
        return

    # ── Phase 4: Rewrite content ─────────────────────────────
    print("\n[Phase 4] Rewriting product content with Gemini...")
    rewrite_results = []

    for product in queue:
        title = product.get("title", "")
        gsc_ctx = product.get("gsc_context", {})
        gsc_category = gsc_ctx.get("category", "unknown")
        print(f"\n  {'─' * 40}")
        print(f"  Product: {title[:60]}")
        print(f"  GSC: {gsc_category}  |  URL: {product.get('gsc_url') or 'not found'}")

        # Clean current content for Gemini (strip external images)
        raw_html = product.get("content", "")
        clean_html = strip_external_images(raw_html)
        content_text = html_to_text(clean_html)
        product["content_text"] = content_text
        product["slug"] = product.get("slug", "")

        rewritten = rewrite_product(product, gsc_ctx, config, site_context=site_context)
        if rewritten.startswith("[Gemini Error]"):
            print(f"  {rewritten}")
            continue

        rewrite_results.append({
            "product": product,
            "rewritten": rewritten,
            "gsc_category": gsc_category,
        })
        print(f"  Rewrite complete.")

    if not rewrite_results:
        print("\n  No products could be rewritten.")
        return

    # ── Phase 5: Download + brand images ─────────────────────
    print("\n[Phase 5] Processing product images...")
    upload_id = get_master_user_id(config)
    if not upload_id:
        print("  [ERROR] Could not find master user ID — cannot upload images")
        return

    for item in rewrite_results:
        product = item["product"]
        media_url = product.get("mediaUrl", "")
        print(f"  Downloading: {media_url[:70]}...")
        raw_bytes = download_image(media_url)
        if raw_bytes:
            branded = brand_product_image(raw_bytes, config)
            item["image_bytes"] = branded
            print(f"  Branded image ready ({len(branded)//1024}KB)")
        else:
            item["image_bytes"] = None
            print(f"  Image download failed — will update content only")

    # ── Phase 6: WhatsApp review ─────────────────────────────
    print("\n[Phase 6] Sending products for WhatsApp review...")
    approved = []

    for item in rewrite_results:
        product = item["product"]
        title = product.get("title", "")
        meta, html_preview = _parse_product_output(item["rewritten"])

        final_output, ok = _review_loop(
            item["rewritten"], config, site_name,
            label=f"מוצר: {title[:40]}"
        )
        item["rewritten"] = final_output
        if ok:
            approved.append(item)
        else:
            print(f"  Rejected: {title[:50]}")

    # ── Phase 7: Apply updates ───────────────────────────────
    if not approved:
        print("\n[Phase 7] No products approved.")
        return

    print(f"\n[Phase 7] Applying {len(approved)} approved updates...")

    for item in approved:
        product = item["product"]
        pid = product["_id"]
        title = product.get("title", "")
        print(f"\n  Updating: {title[:55]}")

        meta, html_content = _parse_product_output(item["rewritten"])
        if not html_content:
            print(f"  Could not parse HTML from Gemini output — skipping")
            continue

        update_fields = {
            "content": html_content,
            "seoUpdatedAt": datetime.now(timezone.utc).isoformat(),
        }
        if meta:
            update_fields["metaDescription"] = meta
            print(f"  Meta: {meta[:80]}")

        # Upload branded image if available
        if item.get("image_bytes"):
            try:
                # skip_logo=True — brand_product_image already composited the watermark
                # return_full_url=True — mediaUrl must be a full URL (not just filename)
                full_url = upload_image(item["image_bytes"], upload_id, config, skip_logo=True, return_full_url=True)
                # Replace mediaUrl with Supabase-hosted branded image.
                # Keep originalMediaUrl as backup to re-download if needed.
                update_fields["mediaUrl"] = full_url
                update_fields["originalMediaUrl"] = item["product"].get("mediaUrl", "")
                print(f"  New mediaUrl: {full_url}")
            except Exception as e:
                print(f"  Image upload failed: {e}")

        try:
            modified = update_product(pid, update_fields, config)
            print(f"  Updated: {modified} document(s) modified")
            record_product_update(pid, title, config)
        except Exception as e:
            print(f"  Update error: {e}")

    # ── Summary ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SUMMARY — PRODUCTS")
    print("=" * 60)
    print(f"  Total products: {len(products)}")
    print(f"  Skipped (cooldown/top_performer): {skipped}")
    print(f"  Processed this run: {len(rewrite_results)}")
    print(f"  Approved & applied: {len(approved)}")
    print("=" * 60)


def run_impact_pipeline(config):
    """
    Measure the SEO impact of our content updates using GSC data.

    For each updated post in history:
      - Fetches GSC performance in the 30 days BEFORE the update
      - Fetches GSC performance in the days AFTER the update (up to today minus 3-day lag)
      - Shows position change, click change, direction (improved / hurt / no data yet)

    Also shows a daily site-wide trend with a marker at the update date,
    so you can visually see whether overall traffic is recovering.
    """
    import sys

    from tools.search_console import fetch_gsc_period_by_page, fetch_gsc_daily_site, match_post_to_gsc_url

    site_name = config["site"]["name"]
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{config['mongodb']['collection']}_impact_{datetime.now().strftime('%Y-%m-%d')}.txt")

    class _Tee:
        """Write to both stdout and a file simultaneously."""
        def __init__(self, stream, path):
            self._stream = stream
            self._file = open(path, "w", encoding="utf-8")
        def write(self, data):
            self._stream.write(data)
            self._file.write(data)
        def flush(self):
            self._stream.flush()
            self._file.flush()
        def close(self):
            self._file.close()

    _real_stdout = sys.stdout
    tee = _Tee(sys.stdout, output_path)
    sys.stdout = tee

    print("=" * 60)
    print(f"  {site_name} — UPDATE IMPACT REPORT")
    print("=" * 60)

    # ── Load update history ──────────────────────────────────
    def _done():
        sys.stdout = _real_stdout
        tee.close()
        print(f"\n  Report saved to: {output_path}")

    history = _load_update_history(config)
    if not history:
        print("\n  No update history found — nothing to measure.")
        _done(); return

    # Find the earliest and latest update dates
    update_dates = []
    for entry in history.values():
        try:
            update_dates.append(datetime.fromisoformat(entry["updated_at"]))
        except Exception:
            pass

    if not update_dates:
        print("\n  No valid update dates in history.")
        _done(); return

    earliest_update = min(update_dates)
    latest_update = max(update_dates)
    gsc_lag = timedelta(days=3)
    now = datetime.now(tz=earliest_update.tzinfo)
    after_end = datetime.now() - gsc_lag  # GSC data available up to here

    print(f"\n  Updates tracked : {len(history)} posts")
    print(f"  First update    : {earliest_update.strftime('%Y-%m-%d')}")
    print(f"  Last update     : {latest_update.strftime('%Y-%m-%d')}")
    print(f"  GSC data up to  : {after_end.strftime('%Y-%m-%d')} (3-day lag)")

    # ── Fetch GSC data for both windows ─────────────────────
    # Before: 30 days before earliest update
    before_start = earliest_update - timedelta(days=30)
    before_end = earliest_update

    # After: from earliest update to most recent GSC data
    after_start = earliest_update
    after_days = (after_end - earliest_update).days

    if after_days < 3:
        print("\n  Not enough time has passed since the update for GSC data to reflect changes.")
        print("  GSC needs at least 3-5 days to show impact. Check back later.")
        _done(); return

    print(f"\n  Before window   : {before_start.strftime('%Y-%m-%d')} → {before_end.strftime('%Y-%m-%d')} (30 days)")
    print(f"  After window    : {after_start.strftime('%Y-%m-%d')} → {after_end.strftime('%Y-%m-%d')} ({after_days} days)\n")

    try:
        before_data = fetch_gsc_period_by_page(config, before_start, before_end)
        after_data = fetch_gsc_period_by_page(config, after_start, after_end)
    except Exception as e:
        print(f"  [ERROR] Could not fetch GSC data: {e}")
        _done(); return

    # Normalize after clicks to 30-day equivalent for fair comparison
    after_ratio = 30 / max(after_days, 1)

    # ── Per-post impact table ────────────────────────────────
    print("\n[PER-POST IMPACT]")
    print("-" * 60)
    print(f"  {'Title':<45} {'Pos Δ':>7}  {'Clicks Δ':>9}  Status")
    print(f"  {'-'*45} {'-'*7}  {'-'*9}  ------")

    improved, hurt, unchanged, no_data = 0, 0, 0, 0
    post_results = []

    for post_id, entry in history.items():
        title = entry.get("title", "")
        before_url, before_metrics = match_post_to_gsc_url(title, before_data, config)
        after_url, after_metrics = match_post_to_gsc_url(title, after_data, config)

        # Try original title for URL matching (title may have changed)
        original_title = entry.get("original_title", title)
        if not before_url and original_title != title:
            before_url, before_metrics = match_post_to_gsc_url(original_title, before_data, config)

        if not before_metrics and not after_metrics:
            no_data += 1
            post_results.append((title, None, None, None, None, "no_data"))
            continue

        pos_before = before_metrics["position"] if before_metrics else None
        pos_after = after_metrics["position"] if after_metrics else None
        clicks_before = before_metrics["clicks"] if before_metrics else 0
        clicks_after = round((after_metrics["clicks"] if after_metrics else 0) * after_ratio)

        pos_delta = None
        clicks_delta = None
        status = "no_data"

        if pos_before and pos_after:
            pos_delta = pos_after - pos_before  # negative = improved (lower position = higher rank)
            clicks_delta = clicks_after - clicks_before
            if pos_delta < -1:
                status = "improved"
                improved += 1
            elif pos_delta > 2:
                status = "hurt"
                hurt += 1
            else:
                status = "unchanged"
                unchanged += 1
        elif pos_after and not pos_before:
            # Newly appearing in GSC after update
            status = "new_data"
            improved += 1
        else:
            no_data += 1
            status = "no_data"

        post_results.append((title, pos_before, pos_after, pos_delta, clicks_delta, status))

    # Sort: improved first, then hurt, then unchanged, then no_data
    order = {"improved": 0, "new_data": 1, "hurt": 2, "unchanged": 3, "no_data": 4}
    post_results.sort(key=lambda x: (order.get(x[5], 9), x[3] if x[3] is not None else 999))

    for title, pos_before, pos_after, pos_delta, clicks_delta, status in post_results:
        short_title = (title[:44] + "…") if len(title) > 45 else title
        if pos_delta is not None:
            delta_str = f"{pos_delta:+.1f}"
            arrow = "↑" if pos_delta < -1 else ("↓" if pos_delta > 2 else "→")
            clicks_str = f"{clicks_delta:+d}" if clicks_delta is not None else "  n/a"
            print(f"  {short_title:<45} {delta_str:>7}  {clicks_str:>9}  {arrow} {status}")
        elif status == "new_data":
            print(f"  {short_title:<45} {'new':>7}  {'?':>9}  ★ appeared in GSC")
        else:
            print(f"  {short_title:<45} {'n/a':>7}  {'n/a':>9}  — no GSC data")

    print(f"\n  Summary: {improved} improved  |  {hurt} hurt  |  {unchanged} unchanged  |  {no_data} no data")

    # ── Save per-post impact verdict to JSON (used by update to protect hurt posts) ──
    impact_json_path = os.path.join(
        os.path.dirname(__file__), "output",
        f"{config['mongodb']['collection']}_impact_verdicts.json"
    )
    impact_verdicts = {}
    for title, pos_before, pos_after, pos_delta, clicks_delta, status in post_results:
        impact_verdicts[title] = {
            "status": status,
            "pos_before": pos_before,
            "pos_after": pos_after,
            "pos_delta": pos_delta,
            "recorded_at": datetime.now().isoformat(),
        }
    with open(impact_json_path, "w", encoding="utf-8") as f:
        json.dump(impact_verdicts, f, ensure_ascii=False, indent=2)

    # ── Static pages impact ──────────────────────────────────
    static_history = _load_static_history(config)
    if static_history:
        print("\n[STATIC PAGES IMPACT]")
        print("-" * 60)
        print(f"  {'Title':<45} {'Pos Δ':>7}  {'Clicks Δ':>9}  Status")
        print(f"  {'-'*45} {'-'*7}  {'-'*9}  ------")

        static_improved, static_hurt, static_unchanged, static_no_data = 0, 0, 0, 0
        static_results = []

        for page_id, entry in static_history.items():
            title = entry.get("title", page_id)
            before_url, before_metrics = match_post_to_gsc_url(title, before_data, config)
            after_url, after_metrics = match_post_to_gsc_url(title, after_data, config)

            if not before_metrics and not after_metrics:
                static_no_data += 1
                static_results.append((title, None, None, None, None, "no_data"))
                continue

            pos_before = before_metrics["position"] if before_metrics else None
            pos_after = after_metrics["position"] if after_metrics else None
            clicks_before = before_metrics["clicks"] if before_metrics else 0
            clicks_after = round((after_metrics["clicks"] if after_metrics else 0) * after_ratio)

            pos_delta = None
            clicks_delta = None
            status = "no_data"

            if pos_before and pos_after:
                pos_delta = pos_after - pos_before
                clicks_delta = clicks_after - clicks_before
                if pos_delta < -1:
                    status = "improved"
                    static_improved += 1
                elif pos_delta > 2:
                    status = "hurt"
                    static_hurt += 1
                else:
                    status = "unchanged"
                    static_unchanged += 1
            elif pos_after and not pos_before:
                status = "new_data"
                static_improved += 1
            else:
                static_no_data += 1
                status = "no_data"

            static_results.append((title, pos_before, pos_after, pos_delta, clicks_delta, status))

        order = {"improved": 0, "new_data": 1, "hurt": 2, "unchanged": 3, "no_data": 4}
        static_results.sort(key=lambda x: (order.get(x[5], 9), x[3] if x[3] is not None else 999))

        for title, pos_before, pos_after, pos_delta, clicks_delta, status in static_results:
            short_title = (title[:44] + "…") if len(title) > 45 else title
            if pos_delta is not None:
                delta_str = f"{pos_delta:+.1f}"
                arrow = "↑" if pos_delta < -1 else ("↓" if pos_delta > 2 else "→")
                clicks_str = f"{clicks_delta:+d}" if clicks_delta is not None else "  n/a"
                print(f"  {short_title:<45} {delta_str:>7}  {clicks_str:>9}  {arrow} {status}")
            elif status == "new_data":
                print(f"  {short_title:<45} {'new':>7}  {'?':>9}  ★ appeared in GSC")
            else:
                print(f"  {short_title:<45} {'n/a':>7}  {'n/a':>9}  — no GSC data")

        print(f"\n  Static summary: {static_improved} improved  |  {static_hurt} hurt  |  {static_unchanged} unchanged  |  {static_no_data} no data")

        # Save static impact verdicts
        static_verdicts_path = os.path.join(
            os.path.dirname(__file__), "output",
            f"{config['mongodb']['collection']}_static_impact_verdicts.json"
        )
        static_verdicts = {}
        for title, pos_before, pos_after, pos_delta, clicks_delta, status in static_results:
            static_verdicts[title] = {
                "status": status,
                "pos_before": pos_before,
                "pos_after": pos_after,
                "pos_delta": pos_delta,
                "recorded_at": datetime.now().isoformat(),
            }
        with open(static_verdicts_path, "w", encoding="utf-8") as f:
            json.dump(static_verdicts, f, ensure_ascii=False, indent=2)

        improved += static_improved
        hurt += static_hurt
        unchanged += static_unchanged
        no_data += static_no_data

    # ── Product pages impact ─────────────────────────────────
    try:
        from tools.product_pipeline import load_product_history, match_product_to_gsc
        product_history = load_product_history(config)
    except Exception:
        product_history = {}

    if product_history:
        try:
            from publisher.mongodb_client import fetch_all_products
            all_products = fetch_all_products(config)
            products_by_id = {str(p["_id"]): p for p in all_products}
        except Exception:
            all_products = []
            products_by_id = {}

        print("\n[PRODUCT PAGES IMPACT]")
        print("-" * 60)
        print(f"  {'Title':<45} {'Pos Δ':>7}  {'Clicks Δ':>9}  Status")
        print(f"  {'-'*45} {'-'*7}  {'-'*9}  ------")

        prod_improved, prod_hurt, prod_unchanged, prod_no_data = 0, 0, 0, 0
        prod_results = []

        for prod_id, entry in product_history.items():
            title = entry.get("title", prod_id)
            product = products_by_id.get(str(prod_id))

            if product:
                before_url, before_metrics = match_product_to_gsc(product, before_data, config)
                after_url, after_metrics = match_product_to_gsc(product, after_data, config)
            else:
                before_url, before_metrics = None, None
                after_url, after_metrics = None, None

            if not before_metrics and not after_metrics:
                prod_no_data += 1
                prod_results.append((title, None, None, None, None, "no_data"))
                continue

            pos_before = before_metrics["position"] if before_metrics else None
            pos_after = after_metrics["position"] if after_metrics else None
            clicks_before = before_metrics["clicks"] if before_metrics else 0
            clicks_after = round((after_metrics["clicks"] if after_metrics else 0) * after_ratio)

            pos_delta = None
            clicks_delta = None
            status = "no_data"

            if pos_before and pos_after:
                pos_delta = pos_after - pos_before
                clicks_delta = clicks_after - clicks_before
                if pos_delta < -1:
                    status = "improved"
                    prod_improved += 1
                elif pos_delta > 2:
                    status = "hurt"
                    prod_hurt += 1
                else:
                    status = "unchanged"
                    prod_unchanged += 1
            elif pos_after and not pos_before:
                status = "new_data"
                prod_improved += 1
            else:
                prod_no_data += 1
                status = "no_data"

            prod_results.append((title, pos_before, pos_after, pos_delta, clicks_delta, status))

        order = {"improved": 0, "new_data": 1, "hurt": 2, "unchanged": 3, "no_data": 4}
        prod_results.sort(key=lambda x: (order.get(x[5], 9), x[3] if x[3] is not None else 999))

        for title, pos_before, pos_after, pos_delta, clicks_delta, status in prod_results:
            short_title = (title[:44] + "…") if len(title) > 45 else title
            if pos_delta is not None:
                delta_str = f"{pos_delta:+.1f}"
                arrow = "↑" if pos_delta < -1 else ("↓" if pos_delta > 2 else "→")
                clicks_str = f"{clicks_delta:+d}" if clicks_delta is not None else "  n/a"
                print(f"  {short_title:<45} {delta_str:>7}  {clicks_str:>9}  {arrow} {status}")
            elif status == "new_data":
                print(f"  {short_title:<45} {'new':>7}  {'?':>9}  ★ appeared in GSC")
            else:
                print(f"  {short_title:<45} {'n/a':>7}  {'n/a':>9}  — no GSC data")

        print(f"\n  Products summary: {prod_improved} improved  |  {prod_hurt} hurt  |  {prod_unchanged} unchanged  |  {prod_no_data} no data")

        # Save products impact verdicts
        prod_verdicts_path = os.path.join(
            os.path.dirname(__file__), "output",
            f"{config['mongodb']['collection']}_products_impact_verdicts.json"
        )
        prod_verdicts = {}
        for title, pos_before, pos_after, pos_delta, clicks_delta, status in prod_results:
            prod_verdicts[title] = {
                "status": status,
                "pos_before": pos_before,
                "pos_after": pos_after,
                "pos_delta": pos_delta,
                "recorded_at": datetime.now().isoformat(),
            }
        with open(prod_verdicts_path, "w", encoding="utf-8") as f:
            json.dump(prod_verdicts, f, ensure_ascii=False, indent=2)

        improved += prod_improved
        hurt += prod_hurt
        unchanged += prod_unchanged
        no_data += prod_no_data

    # ── Daily site-wide trend ────────────────────────────────
    print("\n[DAILY SITE TREND — last 45 days]")
    print("-" * 60)
    try:
        daily = fetch_gsc_daily_site(config, days=45)
    except Exception as e:
        print(f"  [ERROR] Could not fetch daily trend: {e}")
        _done(); return

    update_marker = earliest_update.strftime("%Y-%m-%d")
    max_clicks = max((d["clicks"] for d in daily), default=1) or 1
    bar_width = 35

    for d in daily:
        bar_len = int(d["clicks"] / max_clicks * bar_width)
        bar = "#" * bar_len
        marker = " ◄ UPDATE" if d["date"] == update_marker else ""
        print(f"  {d['date']}  {d['clicks']:>4}c  {d['avg_position']:>5.1f}pos  {bar}{marker}")

    print()

    # Summary trend: average position before vs after update
    before_rows = [d for d in daily if d["date"] < update_marker and d["avg_position"] > 0]
    after_rows = [d for d in daily if d["date"] >= update_marker and d["avg_position"] > 0]

    if before_rows and after_rows:
        avg_pos_before = sum(d["avg_position"] for d in before_rows) / len(before_rows)
        avg_pos_after = sum(d["avg_position"] for d in after_rows) / len(after_rows)
        avg_clicks_before = sum(d["clicks"] for d in before_rows) / len(before_rows)
        avg_clicks_after = sum(d["clicks"] for d in after_rows) / len(after_rows)
        pos_change = avg_pos_after - avg_pos_before
        clicks_change_pct = ((avg_clicks_after - avg_clicks_before) / max(avg_clicks_before, 1)) * 100

        print(f"  Avg position before update : {avg_pos_before:.1f}")
        print(f"  Avg position after update  : {avg_pos_after:.1f}  ({pos_change:+.1f})")
        print(f"  Avg daily clicks before    : {avg_clicks_before:.1f}")
        print(f"  Avg daily clicks after     : {avg_clicks_after:.1f}  ({clicks_change_pct:+.0f}%)")

        if pos_change < -2 and clicks_change_pct > 0:
            verdict = "RECOVERING — positions improving AND clicks growing"
        elif pos_change < -2:
            verdict = "POSITIONS IMPROVING — clicks still catching up (normal ~2-4 week lag)"
        elif clicks_change_pct > 10:
            verdict = "CLICKS GROWING — traffic recovering"
        elif pos_change > 3:
            verdict = "CAUTION — average position dropped after updates"
        else:
            verdict = "STABLE — no clear signal yet (check again in a few days)"

        print(f"\n  Verdict: {verdict}")

    print("=" * 60)
    _done()


# ═══════════════════════════════════════════════
# Mode 10: Dedupe — Fix keyword cannibalization
# ═══════════════════════════════════════════════

def run_dedupe_pipeline(config):
    """
    Detect and fix keyword cannibalization:
    1. Fetch GSC data and find queries where multiple posts compete
    2. For each cluster: identify winner (lowest position) and losers
    3. Check indexing status of each loser via GSC URL Inspection API
    4. Group losers: safe_delete / needs_differentiation / keep_for_now
    5. Terminal approval loop for each action
    6. Execute: delete safe losers / rewrite losers to target different sub-keywords
    """
    from tools.search_console import (
        fetch_gsc_performance, fetch_page_queries,
        find_cannibalization, match_post_to_gsc_url,
        inspect_url_indexing,
    )
    from publisher.mongodb_client import fetch_all_blog_posts, delete_blog_post
    from publisher.post_publisher import update_existing_post
    from generator.gemini_client import rewrite_for_differentiation
    from publisher.tiptap_converter import parse_gemini_output

    site_name = config["site"]["name"]
    domain = config["site"]["domain"]
    blog_path = config["site"].get("blog_url", f"https://{domain}/blog")
    from urllib.parse import urlparse
    blog_url_path = urlparse(blog_path).path.rstrip("/")

    print("=" * 60)
    print(f"  {site_name} — DEDUPE: קניבליזציה")
    print("=" * 60)

    if not config.get("search_console"):
        print("\n  [שגיאה] search_console לא מוגדר. לא ניתן להריץ dedupe.")
        return

    # ── Phase 1: Fetch GSC data ──────────────────────────────
    print("\n[שלב 1] מביא נתוני GSC...")
    try:
        gsc_perf = fetch_gsc_performance(config, days=90)
        page_queries = fetch_page_queries(config, days=90)
    except Exception as e:
        print(f"  [שגיאה] GSC fetch נכשל: {e}")
        return

    blog_posts = fetch_all_blog_posts(config)
    posts_by_title = {p.get("title", ""): p for p in blog_posts}

    print(f"  GSC: {len(gsc_perf)} עמודים | MongoDB: {len(blog_posts)} פוסטים")

    # ── Phase 2: Find cannibalization clusters ───────────────
    print("\n[שלב 2] מחפש קניבליזציה...")
    clusters = find_cannibalization(page_queries, blog_path=blog_url_path, min_impressions=10, min_urls=2)

    if not clusters:
        print("  לא נמצאה קניבליזציה! כל שאילתה מוצמדת לעמוד אחד בלבד.")
        return

    # Filter out brand/generic clusters — if a query appears across >4 URLs it's
    # a sitewide term (brand name, category) not true keyword cannibalization.
    # Also filter out queries that match configured brand_terms.
    brand_terms = config.get("search_console", {}).get("brand_terms", [])
    # Auto-add site name and domain root as brand terms
    site_name_lower = config["site"]["name"].lower()
    domain_root = config["site"]["domain"].split(".")[0].lower()
    auto_brand = {site_name_lower, domain_root}

    def _is_brand_query(query, urls):
        q_lower = query.lower()
        # Explicit brand terms from config
        for term in brand_terms:
            if term.lower() in q_lower:
                return True
        # Auto-detected brand terms (site name / domain root)
        for term in auto_brand:
            if term in q_lower:
                return True
        # Sitewide generic: appears on more than 4 distinct URLs = brand/category signal
        if len(urls) > 4:
            return True
        return False

    filtered_clusters = [c for c in clusters if not _is_brand_query(c["query"], c["urls"])]
    brand_skipped = len(clusters) - len(filtered_clusters)
    if brand_skipped:
        print(f"  [דילג] {brand_skipped} אשכולות מסוננים — שאילתות מותג/כלליות (מופיעות על >4 עמודים)")
    clusters = filtered_clusters

    if not clusters:
        print("  לא נמצאה קניבליזציה אמיתית לאחר סינון שאילתות מותג.")
        return

    print(f"  נמצאו {len(clusters)} אשכולות קניבליזציה")

    # ── Phase 3 & 4: For each cluster, identify winner/losers and check indexing ──
    action_plan = []

    for cluster in clusters:
        query = cluster["query"]
        urls = cluster["urls"]  # already sorted by position (best first)

        winner_entry = urls[0]
        loser_entries = urls[1:]

        # Match winner to a MongoDB post
        winner_url = winner_entry["url"]
        winner_post = None
        for post in blog_posts:
            title = post.get("title", "")
            matched_url, _ = match_post_to_gsc_url(title, {winner_url: gsc_perf.get(winner_url, {})}, config)
            if matched_url:
                winner_post = post
                break

        losers = []
        for loser_entry in loser_entries:
            loser_url = loser_entry["url"]
            loser_post = None
            for post in blog_posts:
                title = post.get("title", "")
                matched_url, _ = match_post_to_gsc_url(title, {loser_url: gsc_perf.get(loser_url, {})}, config)
                if matched_url:
                    loser_post = post
                    break

            # Phase 3: Check indexing status
            print(f"  בודק אינדוקס: {loser_url[:70]}...")
            try:
                index_result = inspect_url_indexing(config, loser_url)
            except Exception as e:
                index_result = {"verdict": "UNKNOWN", "coverageState": f"Error: {e}"}

            verdict = index_result.get("verdict", "UNKNOWN")
            coverage = index_result.get("coverageState", "")
            is_indexed = (verdict == "PASS" or "Indexed" in coverage)

            # Phase 4: Classify loser
            loser_pos = loser_entry.get("position", 999)
            loser_clicks = loser_entry.get("clicks", 0)

            if not is_indexed:
                group = "safe_delete"
            elif loser_pos > 50 or loser_clicks == 0:
                group = "needs_differentiation"
            else:
                group = "keep_for_now"

            losers.append({
                "url": loser_url,
                "post": loser_post,
                "position": loser_pos,
                "clicks": loser_clicks,
                "is_indexed": is_indexed,
                "coverage_state": coverage,
                "group": group,
            })

        action_plan.append({
            "query": query,
            "winner_entry": winner_entry,
            "winner_post": winner_post,
            "losers": losers,
            "total_impressions": cluster["total_impressions"],
        })

    # ── Phase 5: AI-powered auto-decision ────────────────────
    # Gemini classifies each cluster as DUPLICATE (same topic → act) or
    # RELATED (different topics sharing a keyword → skip automatically).
    print("\n" + "=" * 60)
    print("  שלב החלטה — AI מנתח כל אשכול")
    print("=" * 60)

    from generator.gemini_client import classify_cannibalization

    approved_deletes = []   # list of post dicts to delete
    approved_rewrites = []  # list of (post, winner_post, cluster_query)

    for cluster_info in action_plan:
        query = cluster_info["query"]
        winner_entry = cluster_info["winner_entry"]
        winner_post = cluster_info["winner_post"]
        losers = cluster_info["losers"]
        total_impr = cluster_info["total_impressions"]

        actionable_losers = [l for l in losers if l["group"] != "keep_for_now"]
        if not actionable_losers:
            continue

        print(f"\n{'─'*60}")
        winner_title = winner_post.get("title", winner_entry["url"]) if winner_post else winner_entry["url"]
        print(f"CANNIBALIZATION CLUSTER: \"{query}\" ({len(losers)+1} URLs מתחרות, {total_impr} חשיפות)")
        print(f"  מנצח: pos {winner_entry['position']:.1f} | {winner_entry['clicks']} קליקים | {winner_title[:55]}")

        for i, loser in enumerate(losers, 1):
            loser_title = loser["post"].get("title", loser["url"]) if loser["post"] else loser["url"]

            if loser["group"] == "keep_for_now":
                print(f"  מפסיד {i}: [דילוג — יש תנועה] {loser_title[:55]}")
                continue

            # Ask Gemini: are these truly the same topic or just related?
            print(f"  מפסיד {i}: מנתח עם AI... '{loser_title[:50]}'")
            classification = classify_cannibalization(winner_title, loser_title, query, config)

            if classification == "related":
                print(f"    [AI: נושאים שונים — דילוג אוטומטי]")
                continue

            # Truly duplicate — take action based on indexing status
            if loser["group"] == "safe_delete":
                print(f"    [AI: כפול + לא מאונדקס → מוחק]")
                if loser["post"]:
                    approved_deletes.append(loser["post"])
            elif loser["group"] == "needs_differentiation":
                print(f"    [AI: כפול + מאונדקס → משכתב לדיפרנציאציה]")
                if loser["post"]:
                    approved_rewrites.append((loser["post"], winner_post, query))
            else:
                print(f"    [AI: כפול — שומר (יש תנועה)]")

    # ── Phase 6: Execute approved actions ────────────────────
    print("\n" + "=" * 60)
    print("  מבצע פעולות מאושרות")
    print("=" * 60)

    # Deletions — deduplicate by post ID (same post can appear in multiple clusters)
    seen_delete_ids = set()
    unique_deletes = []
    for post in approved_deletes:
        pid = str(post.get("_id", ""))
        if pid and pid not in seen_delete_ids:
            seen_delete_ids.add(pid)
            unique_deletes.append(post)
    approved_deletes = unique_deletes

    if approved_deletes:
        print(f"\n[מחיקות] {len(approved_deletes)} פוסטים:")
        for post in approved_deletes:
            title = post.get("title", "")
            post_id = post.get("_id", "")
            print(f"  מוחק: {title[:55]}")
            try:
                deleted = delete_blog_post(post_id, config)
                if deleted:
                    print(f"    נמחק בהצלחה (id={post_id})")
                else:
                    print(f"    לא נמצא במסד הנתונים (id={post_id})")
            except Exception as e:
                print(f"    שגיאת מחיקה: {e}")
    else:
        print("\n  אין מחיקות.")

    # Differentiation rewrites — deduplicate by post ID (same post in multiple clusters)
    seen_rewrite_ids = set()
    unique_rewrites = []
    for post, winner_post_obj, cluster_query in approved_rewrites:
        pid = str(post.get("_id", ""))
        if pid and pid not in seen_rewrite_ids:
            seen_rewrite_ids.add(pid)
            unique_rewrites.append((post, winner_post_obj, cluster_query))
    approved_rewrites = unique_rewrites

    if approved_rewrites:
        print(f"\n[שכתובי דיפרנציאציה] {len(approved_rewrites)} פוסטים:")
        for post, winner_post_obj, cluster_query in approved_rewrites:
            title = post.get("title", "")
            print(f"\n  משכתב: {title[:55]}")
            print(f"  שאילתה: \"{cluster_query}\"")

            # Add content text to post for prompt
            from publisher.tiptap_converter import extract_text_from_tiptap
            body = post.get("body", "")
            if body:
                try:
                    body_dict = json.loads(body) if isinstance(body, str) else body
                    post["content_text"] = extract_text_from_tiptap(body_dict)
                except Exception:
                    post["content_text"] = ""

            try:
                gemini_output = rewrite_for_differentiation(post, winner_post_obj or {}, cluster_query, config)
                print(f"  Gemini שלח פלט ({len(gemini_output)} תווים)")
            except Exception as e:
                print(f"  שגיאת Gemini: {e}")
                continue

            if gemini_output.startswith("[Gemini Error]"):
                print(f"  {gemini_output}")
                continue

            # Parse and apply the rewrite
            try:
                post_id = post.get("_id", "")
                original_title = post.get("title", "")

                result = update_existing_post(
                    post_id=post_id,
                    gemini_output=gemini_output,
                    desktop_image_bytes=None,
                    mobile_image_bytes=None,
                    config=config,
                    preserve_title=original_title,
                )
                print(f"  עודכן: {result}")
                parsed = parse_gemini_output(gemini_output)
                _record_updated_post(post_id, parsed.get("title", original_title), config,
                                     original_title=original_title, original_body=body)
            except Exception as e:
                print(f"  שגיאת עדכון: {e}")
    else:
        print("\n  אין שכתובים.")

    # ── Summary ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  סיכום — DEDUPE")
    print("=" * 60)
    print(f"  אשכולות קניבליזציה שנמצאו : {len(clusters)}")
    print(f"  פוסטים שנמחקו             : {len(approved_deletes)}")
    print(f"  פוסטים ששוכתבו            : {len(approved_rewrites)}")
    print("=" * 60)
