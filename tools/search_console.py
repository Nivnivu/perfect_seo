"""Google Search Console API client — Service Account or OAuth2 auth, performance fetching, title protection & recovery."""
import os
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse


# ═══════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════

def _detect_credentials_type(credentials_file: str) -> str:
    """
    Read the JSON file and return 'service_account' or 'oauth2'.
    """
    try:
        with open(credentials_file) as f:
            data = json.load(f)
        return data.get("type", "oauth2")
    except Exception:
        return "oauth2"


def _get_gsc_service(config):
    """
    Build an authenticated GSC service.
    Auto-detects credentials type from the JSON file:
      - 'service_account' → uses service account key directly (no browser needed)
      - anything else     → OAuth2 flow (opens browser on first run, saves token)
    """
    from googleapiclient.discovery import build

    gsc_config = config.get("search_console", {})
    credentials_file = gsc_config.get("credentials_file", "gsc_credentials.json")
    token_file = gsc_config.get("token_file", "gsc_token.json")
    scopes = [
        "https://www.googleapis.com/auth/webmasters.readonly",
        "https://www.googleapis.com/auth/webmasters",
    ]

    if not os.path.exists(credentials_file):
        raise FileNotFoundError(
            f"[gsc] Credentials file not found: {credentials_file}\n"
            f"  Place the JSON file in the project root and update the config."
        )

    cred_type = _detect_credentials_type(credentials_file)

    if cred_type == "service_account":
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=scopes
        )
        print(f"  [gsc] Using service account: {creds.service_account_email}")
        return build("searchconsole", "v1", credentials=creds)

    # OAuth2 path
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None

    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, scopes)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
        creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        print(f"  [gsc] Token saved to {token_file}")

    return build("searchconsole", "v1", credentials=creds)


# ═══════════════════════════════════════════════
# Performance Fetching
# ═══════════════════════════════════════════════

def _get_site_url(config):
    """Get the GSC site URL from config, falling back to site.domain."""
    gsc_config = config.get("search_console", {})
    site_url = gsc_config.get("site_url", "")
    if not site_url:
        domain = config["site"]["domain"]
        site_url = f"https://{domain}/"
    return site_url


def fetch_gsc_performance(config, days=28):
    """
    Fetch page-level performance data from GSC for the given period.
    Returns: {url: {clicks, impressions, ctr, position}}
    """
    service = _get_gsc_service(config)
    site_url = _get_site_url(config)

    end_date = datetime.now() - timedelta(days=3)  # GSC data has ~3 day lag
    start_date = end_date - timedelta(days=days)

    request_body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": ["page"],
        "rowLimit": 5000,
    }

    print(f"  [gsc] Fetching performance data ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})...")

    response = service.searchanalytics().query(
        siteUrl=site_url, body=request_body
    ).execute()

    results = {}
    for row in response.get("rows", []):
        url = row["keys"][0]
        results[url] = {
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0),
            "position": row.get("position", 0),
        }

    print(f"  [gsc] Got performance data for {len(results)} pages")
    return results


def match_post_to_gsc_url(post_title, gsc_data, config):
    """
    Match a post title to its GSC URL.
    The CMS generates URLs from titles, so we look for URLs containing
    a slug-like version of the title, or match by blog URL pattern.
    """
    blog_url = config["site"].get("blog_url", f"https://{config['site']['domain']}/blog")
    blog_path = urlparse(blog_url).path.rstrip("/")

    # Filter to blog URLs only
    blog_urls = {url: data for url, data in gsc_data.items()
                 if blog_path in urlparse(url).path}

    if not blog_urls:
        return None, None

    # Try to find the best match by word overlap between title and URL slug
    title_words = set(post_title.lower().split())

    best_url = None
    best_score = 0
    best_data = None

    for url, data in blog_urls.items():
        # Extract slug from URL
        path = urlparse(url).path.rstrip("/")
        slug = path.split("/")[-1] if "/" in path else path
        # URL-decode and split by hyphens
        from urllib.parse import unquote
        slug_words = set(unquote(slug).lower().replace("-", " ").split())

        if not slug_words:
            continue

        overlap = len(title_words & slug_words)
        score = overlap / min(len(title_words), len(slug_words)) if min(len(title_words), len(slug_words)) > 0 else 0

        if score > best_score:
            best_score = score
            best_url = url
            best_data = data

    if best_score >= 0.4:
        return best_url, best_data

    return None, None


def is_title_protected(post_title, gsc_data, config):
    """
    Check if a post's title should be protected from changes based on GSC performance.
    Returns: (is_protected: bool, reason: str, gsc_url: str | None)
    """
    gsc_config = config.get("search_console", {})
    thresholds = gsc_config.get("protection_thresholds", {})
    min_clicks = thresholds.get("min_clicks", 10)
    min_impressions = thresholds.get("min_impressions", 100)
    max_position = thresholds.get("max_position", 20.0)

    url, data = match_post_to_gsc_url(post_title, gsc_data, config)
    if not url or not data:
        return False, "no GSC data found", None

    clicks = data.get("clicks", 0)
    impressions = data.get("impressions", 0)
    position = data.get("position", 999)

    reasons = []
    if clicks >= min_clicks:
        reasons.append(f"clicks={clicks}>={min_clicks}")
    if impressions >= min_impressions:
        reasons.append(f"impressions={impressions}>={min_impressions}")
    if position <= max_position:
        reasons.append(f"position={position:.1f}<={max_position}")

    # Protected if ANY threshold is met (conservative — protect if performing on any metric)
    if reasons:
        return True, " + ".join(reasons), url

    return False, f"below thresholds (clicks={clicks}, impr={impressions}, pos={position:.1f})", url


# ═══════════════════════════════════════════════
# Query-level Data + Page Classification
# ═══════════════════════════════════════════════

def fetch_page_queries(config, days=90):
    """
    Fetch per-page, per-query performance data from GSC.
    Returns: {url: [{query, clicks, impressions, ctr_pct, position}]}
    Sorted by impressions descending so top queries come first.
    """
    service = _get_gsc_service(config)
    site_url = _get_site_url(config)

    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

    request_body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": ["page", "query"],
        "rowLimit": 25000,
    }

    print(f"  [gsc] Fetching page+query data ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})...")

    response = service.searchanalytics().query(
        siteUrl=site_url, body=request_body
    ).execute()

    results = {}
    for row in response.get("rows", []):
        url, query = row["keys"]
        if url not in results:
            results[url] = []
        results[url].append({
            "query": query,
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr_pct": round(row.get("ctr", 0) * 100, 1),
            "position": round(row.get("position", 0), 1),
        })

    for url in results:
        results[url].sort(key=lambda x: x["impressions"], reverse=True)

    print(f"  [gsc] Got query data for {len(results)} pages")
    return results


def classify_page_seo(url, gsc_perf, page_queries, config):
    """
    Classify a page's SEO status to decide update priority and strategy.

    Categories (in priority order for updates):
      page2_opportunity  — position 11-30, impressions >= 20  → HIGHEST PRIORITY, push to page 1
      ctr_opportunity    — position <= 10, CTR < 3%           → improve meta description
      low_performer      — has impressions but ranking poorly  → general content improvement
      not_indexed        — no GSC data at all                  → full rewrite OK
      top_performer      — clicks > threshold, position <= 10  → SKIP, it's already working

    Returns dict: {category, top_queries, metrics, update_priority}
    update_priority: 1 = highest, 5 = skip
    """
    thresholds = config.get("search_console", {}).get("protection_thresholds", {})
    min_clicks = thresholds.get("min_clicks", 10)

    metrics = gsc_perf.get(url, {})
    queries = page_queries.get(url, [])[:15]
    top_queries = [q["query"] for q in queries]

    if not metrics:
        return {
            "category": "not_indexed",
            "top_queries": [],
            "metrics": {},
            "update_priority": 4,
        }

    clicks = metrics.get("clicks", 0)
    impressions = metrics.get("impressions", 0)
    position = metrics.get("position", 999)
    ctr = metrics.get("ctr", 0)

    summary = {
        "clicks": int(clicks),
        "impressions": int(impressions),
        "position": round(position, 1),
        "ctr_pct": round(ctr * 100, 1),
    }

    if position <= 10 and clicks >= min_clicks:
        # Already performing well — highest risk to touch
        category = "top_performer"
        priority = 5  # skip
    elif 11 <= position <= 30 and impressions >= 20:
        # One improvement away from page 1 — best ROI
        category = "page2_opportunity"
        priority = 1
    elif position <= 10 and ctr * 100 < 3.0 and impressions >= 50:
        # Ranking well but users aren't clicking — meta desc issue
        category = "ctr_opportunity"
        priority = 2
    elif impressions >= 5:
        # Has some presence but not performing
        category = "low_performer"
        priority = 3
    else:
        category = "not_indexed"
        priority = 4

    return {
        "category": category,
        "top_queries": top_queries,
        "metrics": summary,
        "update_priority": priority,
    }


# ═══════════════════════════════════════════════
# Sitemap Ping
# ═══════════════════════════════════════════════

def ping_sitemap(config):
    """
    Submit the site's sitemap to Google Search Console.
    Call this after every new post is published to speed up indexing.
    Google will re-crawl all URLs in the sitemap within hours instead of weeks.
    """
    service = _get_gsc_service(config)
    site_url = _get_site_url(config)
    domain = config["site"]["domain"]

    # Try common sitemap paths
    sitemap_urls = [
        f"https://{domain}/sitemap.xml",
        f"https://{domain}/sitemap_index.xml",
        f"https://www.{domain}/sitemap.xml",
    ]

    pinged = False
    for sitemap_url in sitemap_urls:
        try:
            service.sitemaps().submit(siteUrl=site_url, feedpath=sitemap_url).execute()
            print(f"  [gsc] Sitemap submitted: {sitemap_url}")
            pinged = True
            break
        except Exception as e:
            err_str = str(e)
            if "404" in err_str or "not found" in err_str.lower():
                continue  # try next sitemap path
            print(f"  [gsc] Sitemap ping failed for {sitemap_url}: {e}")
            break

    if not pinged:
        print(f"  [gsc] Could not find sitemap at standard paths for {domain}")
    return pinged


# ═══════════════════════════════════════════════
# URL Inspection — WHY is a page not indexed?
# ═══════════════════════════════════════════════

def inspect_url_indexing(config, url):
    """
    Use the GSC URL Inspection API to check the exact indexing status of a URL.
    Returns a dict with verdict, coverageState, indexingState, robotsTxtState,
    pageFetchState, googleCanonical, lastCrawlTime.

    This tells you EXACTLY why a page isn't indexed:
      - "Crawled - currently not indexed"  → Google saw it but chose not to index (quality issue)
      - "Discovered - currently not indexed" → Google knows about it but hasn't crawled yet
      - "Duplicate, Google chose different canonical than user" → canonical conflict
      - "Blocked by robots.txt"  → robots.txt is blocking Googlebot
      - "Page with redirect"     → redirect issue
      - "Not found (404)"        → page returns 404
    """
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    import os

    gsc_config = config.get("search_console", {})
    token_file = gsc_config.get("token_file", "gsc_token.json")
    credentials_file = gsc_config.get("credentials_file", "gsc_credentials.json")
    scopes = [
        "https://www.googleapis.com/auth/webmasters.readonly",
        "https://www.googleapis.com/auth/webmasters",
    ]

    creds = None
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, scopes)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
        creds = flow.run_local_server(port=0)

    service = build("searchconsole", "v1", credentials=creds)
    site_url = _get_site_url(config)

    try:
        response = service.urlInspection().index().inspect(body={
            "inspectionUrl": url,
            "siteUrl": site_url,
        }).execute()

        result = response.get("inspectionResult", {})
        index_result = result.get("indexStatusResult", {})

        return {
            "verdict": index_result.get("verdict", "UNKNOWN"),
            "coverageState": index_result.get("coverageState", "Unknown"),
            "indexingState": index_result.get("indexingState", ""),
            "robotsTxtState": index_result.get("robotsTxtState", ""),
            "pageFetchState": index_result.get("pageFetchState", ""),
            "googleCanonical": index_result.get("googleCanonical", ""),
            "userCanonical": index_result.get("userCanonical", ""),
            "lastCrawlTime": index_result.get("lastCrawlTime", ""),
            "crawledAs": index_result.get("crawledAs", ""),
            "error": None,
        }
    except Exception as e:
        return {"error": str(e), "coverageState": "Error", "verdict": "UNKNOWN"}


def inspect_urls_batch(config, urls, max_urls=25, delay=1.2):
    """
    Inspect indexing status for a batch of URLs.
    Rate-limited to 1 request/1.2s to stay under GSC quota (2000/day).
    Returns {url: inspect_result_dict}
    """
    import time as _time
    results = {}
    for i, url in enumerate(urls[:max_urls]):
        print(f"  [gsc-inspect] ({i+1}/{min(len(urls), max_urls)}) {url[:80]}...")
        results[url] = inspect_url_indexing(config, url)
        if i < len(urls[:max_urls]) - 1:
            _time.sleep(delay)
    return results


# ═══════════════════════════════════════════════
# Device Breakdown
# ═══════════════════════════════════════════════

def fetch_gsc_by_device(config, days=90):
    """
    Fetch page performance split by device (DESKTOP / MOBILE / TABLET).
    Returns: {url: {"DESKTOP": {clicks,impressions,ctr,position}, "MOBILE": {...}, ...}}
    Useful for detecting mobile ranking gaps.
    """
    service = _get_gsc_service(config)
    site_url = _get_site_url(config)

    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

    request_body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": ["page", "device"],
        "rowLimit": 25000,
    }

    print(f"  [gsc] Fetching device breakdown ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})...")
    response = service.searchanalytics().query(siteUrl=site_url, body=request_body).execute()

    results = {}
    for row in response.get("rows", []):
        url, device = row["keys"]
        if url not in results:
            results[url] = {}
        results[url][device] = {
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0),
            "position": round(row.get("position", 0), 1),
        }

    print(f"  [gsc] Got device data for {len(results)} pages")
    return results


# ═══════════════════════════════════════════════
# Weekly Trend Analysis
# ═══════════════════════════════════════════════

def fetch_gsc_weekly_trends(config, weeks=12):
    """
    Fetch site-wide weekly click/impression/position trends.
    Returns: list of {week_start, clicks, impressions, avg_position} sorted oldest first.
    Used to detect whether traffic is growing, plateauing, or declining.
    """
    service = _get_gsc_service(config)
    site_url = _get_site_url(config)

    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(weeks=weeks)

    request_body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": ["date"],
        "rowLimit": 5000,
    }

    print(f"  [gsc] Fetching daily trends ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})...")
    response = service.searchanalytics().query(siteUrl=site_url, body=request_body).execute()

    # Aggregate daily into weekly buckets
    from collections import defaultdict
    weekly = defaultdict(lambda: {"clicks": 0, "impressions": 0, "positions": [], "days": 0})

    for row in response.get("rows", []):
        date_str = row["keys"][0]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        # ISO week start (Monday)
        week_start = (date_obj - timedelta(days=date_obj.weekday())).strftime("%Y-%m-%d")
        weekly[week_start]["clicks"] += row.get("clicks", 0)
        weekly[week_start]["impressions"] += row.get("impressions", 0)
        pos = row.get("position", 0)
        if pos > 0:
            weekly[week_start]["positions"].append(pos)
        weekly[week_start]["days"] += 1

    result = []
    for week_start in sorted(weekly.keys()):
        w = weekly[week_start]
        positions = w["positions"]
        result.append({
            "week_start": week_start,
            "clicks": int(w["clicks"]),
            "impressions": int(w["impressions"]),
            "avg_position": round(sum(positions) / len(positions), 1) if positions else 0,
            "days": w["days"],
        })

    print(f"  [gsc] Got {len(result)} weeks of trend data")
    return result


# ═══════════════════════════════════════════════
# Query Cannibalization Detection
# ═══════════════════════════════════════════════

def find_cannibalization(page_queries, blog_path="", min_impressions=10, min_urls=2, brand_terms=None):
    """
    Detect keyword cannibalization: multiple blog URLs ranking for the same query.
    When two posts compete for the same query, Google splits the ranking signal
    between them — neither reaches its potential.

    page_queries: output of fetch_page_queries()
    blog_path: optional URL path filter (e.g. "/blog") to only check blog posts
    brand_terms: list of brand name strings (e.g. ["אוורסט"]) — queries containing
                 any of these terms are excluded (navigational brand queries are not
                 real cannibalization; all posts naturally appear for brand searches)
    Returns: list of {query, urls, total_impressions, best_position} sorted by severity
    """
    from collections import defaultdict

    brand_terms_lower = [t.lower() for t in (brand_terms or [])]

    query_to_urls = defaultdict(list)

    for url, queries in page_queries.items():
        # Filter to blog URLs only if blog_path specified
        if blog_path and blog_path not in url:
            continue
        for q in queries:
            if q["impressions"] < min_impressions:
                continue
            # Skip brand/navigational queries — appearing on many pages for your own brand
            # name is not cannibalization, it's normal brand visibility.
            if brand_terms_lower and any(term in q["query"].lower() for term in brand_terms_lower):
                continue
            query_to_urls[q["query"]].append({
                "url": url,
                "impressions": q["impressions"],
                "clicks": q["clicks"],
                "position": q["position"],
            })

    # Keep only queries with multiple ranking URLs
    cannibalized = []
    for query, url_entries in query_to_urls.items():
        if len(url_entries) < min_urls:
            continue
        total_impressions = sum(e["impressions"] for e in url_entries)
        best_position = min(e["position"] for e in url_entries)
        url_entries_sorted = sorted(url_entries, key=lambda x: x["position"])
        cannibalized.append({
            "query": query,
            "urls": url_entries_sorted,
            "url_count": len(url_entries),
            "total_impressions": total_impressions,
            "best_position": best_position,
        })

    # Sort by total impressions (most impactful first)
    cannibalized.sort(key=lambda x: x["total_impressions"], reverse=True)
    return cannibalized


# ═══════════════════════════════════════════════
# Indexing Coverage
# ═══════════════════════════════════════════════

def find_coverage_gaps(gsc_perf, blog_posts, config):
    """
    Compare blog posts in MongoDB vs pages with GSC impressions.
    Identifies posts that Google may not have indexed yet.

    gsc_perf: output of fetch_gsc_performance()
    blog_posts: list of post dicts from MongoDB (need 'title' field)
    Returns: {
        "indexed": [posts with GSC data],
        "not_indexed": [posts with NO GSC data],
        "zero_clicks": [posts with impressions but 0 clicks],
        "total_posts": int,
        "coverage_pct": float,
    }
    """
    indexed = []
    not_indexed = []
    zero_clicks = []

    for post in blog_posts:
        title = post.get("title", "")
        url, data = match_post_to_gsc_url(title, gsc_perf, config)

        if url and data:
            post_with_gsc = {**post, "gsc_url": url, "gsc_data": data}
            indexed.append(post_with_gsc)
            if data.get("clicks", 0) == 0 and data.get("impressions", 0) > 0:
                zero_clicks.append(post_with_gsc)
        else:
            not_indexed.append(post)

    total = len(blog_posts)
    coverage_pct = round(len(indexed) / total * 100, 1) if total > 0 else 0

    return {
        "indexed": indexed,
        "not_indexed": not_indexed,
        "zero_clicks": zero_clicks,
        "total_posts": total,
        "indexed_count": len(indexed),
        "coverage_pct": coverage_pct,
    }


# ═══════════════════════════════════════════════
# Recovery — Find Lost Pages
# ═══════════════════════════════════════════════

def _fetch_gsc_period(service, site_url, start_date, end_date):
    """Fetch GSC performance for a specific date range."""
    request_body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": ["page"],
        "rowLimit": 5000,
    }
    response = service.searchanalytics().query(
        siteUrl=site_url, body=request_body
    ).execute()

    results = {}
    for row in response.get("rows", []):
        url = row["keys"][0]
        results[url] = {
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0),
            "position": row.get("position", 0),
        }
    return results


def _slug_title_overlap(url, title):
    """
    Score how well a URL slug matches a title by word overlap.
    Returns 0.0–1.0. Used to match old GSC URLs to original post titles.
    """
    from urllib.parse import unquote, urlparse
    path = urlparse(url).path.rstrip("/")
    slug = path.split("/")[-1] if "/" in path else path
    slug_words = set(unquote(slug).lower().replace("-", " ").replace("_", " ").split())
    title_words = set(title.lower().split())
    if not slug_words or not title_words:
        return 0.0
    overlap = len(slug_words & title_words)
    return overlap / min(len(slug_words), len(title_words))


def find_lost_pages(config, recent_days=28, baseline_days=90):
    """
    Find pages that lost GSC traffic after being updated by our engine.

    The core bug this replaces: the old code tried to match dropped URLs to MongoDB
    posts by their CURRENT title — but if the title changed (causing a new URL/slug),
    the old URL slug wouldn't match the new title → recovery was silently missed.

    New approach:
      1. Load update_history to get {post_id → original_title, current_title}
      2. Fetch GSC baseline vs recent data, find all URLs with >50% drops
      3. For each dropped URL, match against ORIGINAL titles from history
         (original_title generated the original slug → high overlap expected)
      4. Fallback: also try matching against MongoDB current title
      5. Return sorted by severity (worst drops first)

    Returns: list of {url, post_id, original_title, current_title, old_metrics, new_metrics, drop_pct, cause}
    """
    from orchestrator import _get_history_path
    from publisher.mongodb_client import find_post_by_url  # noqa

    # ── Load update history ──
    history_path = _get_history_path(config)
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            full_history = json.load(f)
    except (json.JSONDecodeError, IOError, FileNotFoundError):
        full_history = {}

    if not full_history:
        print("  [gsc] No update history found — nothing to cross-reference")
        return []

    # Build lookup of posts where we recorded a title change
    title_changes = {}  # post_id → {original_title, current_title}
    for post_id, entry in full_history.items():
        original = entry.get("original_title", "")
        current = entry.get("title", "")
        if original and original != current:
            title_changes[post_id] = {"original_title": original, "current_title": current}

    print(f"  [gsc] Update history: {len(full_history)} posts updated, {len(title_changes)} with title changes")

    # ── Fetch GSC data for both periods ──
    service = _get_gsc_service(config)
    site_url = _get_site_url(config)
    now = datetime.now()
    gsc_lag = timedelta(days=3)

    recent_end = now - gsc_lag
    recent_start = recent_end - timedelta(days=recent_days)
    baseline_end = recent_start
    baseline_start = now - gsc_lag - timedelta(days=baseline_days)

    print(f"  [gsc] Recent:   {recent_start.strftime('%Y-%m-%d')} → {recent_end.strftime('%Y-%m-%d')}")
    print(f"  [gsc] Baseline: {baseline_start.strftime('%Y-%m-%d')} → {baseline_end.strftime('%Y-%m-%d')}")

    recent_data = _fetch_gsc_period(service, site_url, recent_start, recent_end)
    baseline_data = _fetch_gsc_period(service, site_url, baseline_start, baseline_end)

    # Normalize baseline to same period length
    baseline_ratio = recent_days / max((baseline_end - baseline_start).days, 1)

    # ── Find all URLs with significant traffic drops ──
    dropped_urls = {}
    for url, bm in baseline_data.items():
        baseline_clicks = bm["clicks"] * baseline_ratio
        recent_clicks = recent_data.get(url, {}).get("clicks", 0)

        if baseline_clicks < 5:
            continue

        drop_pct = ((baseline_clicks - recent_clicks) / baseline_clicks) * 100
        if drop_pct > 50:
            dropped_urls[url] = {
                "old_metrics": {
                    "clicks": round(baseline_clicks, 1),
                    "impressions": round(bm["impressions"] * baseline_ratio, 1),
                    "position": round(bm["position"], 1),
                },
                "new_metrics": recent_data.get(url, {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}),
                "drop_pct": round(drop_pct, 1),
            }

    print(f"  [gsc] {len(dropped_urls)} URLs with >50% traffic drop")
    if not dropped_urls:
        return []

    # ── Match dropped URLs to update history ──
    lost_pages = []
    matched_post_ids = set()

    for url, drop_info in dropped_urls.items():
        found = None

        # Strategy A: Match URL slug against ORIGINAL titles (the key fix)
        # When title changed → URL changed. The dropped URL matches the ORIGINAL title, not the new one.
        if title_changes:
            best_score = 0
            best_post_id = None
            for post_id, titles in title_changes.items():
                if post_id in matched_post_ids:
                    continue
                score = _slug_title_overlap(url, titles["original_title"])
                if score > best_score:
                    best_score = score
                    best_post_id = post_id

            if best_score >= 0.4 and best_post_id:
                found = {
                    "post_id": best_post_id,
                    "original_title": title_changes[best_post_id]["original_title"],
                    "current_title": title_changes[best_post_id]["current_title"],
                    "cause": "title_changed_url_broken",
                }

        # Strategy B: Fallback — match against current MongoDB title, then check history
        if not found:
            post = find_post_by_url(url, config)
            if post:
                post_id = post["_id"]
                if post_id not in matched_post_ids and post_id in full_history:
                    entry = full_history[post_id]
                    original = entry.get("original_title", "")
                    current = post.get("title", "")
                    if not original:
                        # Old history entry — we don't know the original title
                        cause = "updated_no_history"
                    elif original == current:
                        cause = "content_rewrite_drop"
                    else:
                        cause = "title_changed_url_broken"
                    found = {
                        "post_id": post_id,
                        "original_title": original,
                        "current_title": current,
                        "cause": cause,
                    }

        if found:
            matched_post_ids.add(found["post_id"])
            # Attach original_body from history so recovery can restore full content, not just title
            post_id_str = str(found["post_id"])
            if post_id_str in full_history:
                found["original_body"] = full_history[post_id_str].get("original_body", "")
            else:
                found["original_body"] = ""
            lost_pages.append({
                "url": url,
                **found,
                **drop_info,
            })

    # Sort by severity — worst drops first
    lost_pages.sort(key=lambda x: x["drop_pct"], reverse=True)

    title_broken = sum(1 for p in lost_pages if p["cause"] == "title_changed_url_broken")
    content_drop = sum(1 for p in lost_pages if p["cause"] == "content_rewrite_drop")
    no_history = sum(1 for p in lost_pages if p["cause"] == "updated_no_history")
    print(f"  [gsc] {len(lost_pages)} recovery candidates: {title_broken} broken URLs, {content_drop} content drops, {no_history} unknown (no title history)")
    return lost_pages


# ═══════════════════════════════════════════════
# Impact Analysis — Before vs After Update
# ═══════════════════════════════════════════════

def fetch_gsc_period_by_page(config, start_date, end_date):
    """
    Fetch page-level GSC performance for an explicit date range.
    Returns: {url: {clicks, impressions, ctr, position}}
    """
    service = _get_gsc_service(config)
    site_url = _get_site_url(config)
    return _fetch_gsc_period(service, site_url, start_date, end_date)


def fetch_gsc_daily_site(config, days=45):
    """
    Fetch daily site-wide clicks/impressions/position for trend charting.
    Returns: list of {date, clicks, impressions, avg_position} sorted oldest→newest.
    """
    service = _get_gsc_service(config)
    site_url = _get_site_url(config)

    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

    request_body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": ["date"],
        "rowLimit": 5000,
    }

    print(f"  [gsc] Fetching daily site trend ({start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')})...")
    response = service.searchanalytics().query(siteUrl=site_url, body=request_body).execute()

    rows = []
    for row in response.get("rows", []):
        rows.append({
            "date": row["keys"][0],
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "avg_position": round(row.get("position", 0), 1),
        })

    rows.sort(key=lambda x: x["date"])
    return rows
