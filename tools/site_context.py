"""
Scrape configured website URLs to extract brand/product context for Gemini.

Extracts:
- Internal links (URL + anchor text) → for deep linking in blog posts
- Product names/descriptions → for product mentions in content
- Page structure → for understanding the site hierarchy
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import re
import random


def _scrape_page(url, user_agent, domain):
    """Scrape a single page and extract structured context."""
    headers = {
        "User-Agent": user_agent,
        "Accept-Language": "he,en;q=0.5",
    }

    result = {
        "url": url,
        "title": "",
        "meta_description": "",
        "text_preview": "",
        "internal_links": [],
        "images": [],
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        # Title
        title_tag = soup.find("title")
        if title_tag:
            result["title"] = title_tag.get_text(strip=True)

        # Meta description
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            result["meta_description"] = meta.get("content", "")

        # Internal links with anchor text
        seen_urls = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            parsed = urlparse(href)

            # Only internal links
            if domain not in parsed.netloc:
                continue

            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            anchor = a.get_text(strip=True)
            if anchor and len(anchor) > 1 and len(anchor) < 200:
                result["internal_links"].append({
                    "url": clean_url,
                    "anchor": anchor,
                })

        # Images with alt text
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if not src:
                continue
            full_src = urljoin(url, src)
            alt = img.get("alt", "").strip()
            if alt:
                result["images"].append({
                    "url": full_src,
                    "alt": alt,
                })

        # Text preview (main content area)
        body = soup.find("main") or soup.find("article") or soup.find("body")
        if body:
            text = body.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            result["text_preview"] = text[:2000]

    except Exception as e:
        print(f"  [context] Error scraping {url}: {e}")

    return result


def scrape_site_context(config):
    """
    Scrape all configured context URLs and return structured site data.

    Returns:
    {
        "pages": [{"url", "type", "title", "text_preview", "internal_links", "images"}],
        "all_internal_links": [{"url", "anchor"}],  # deduplicated
        "product_names": ["Natural Greatness 2kg ...", ...],
        "brand_info": {"brand_voice": "...", "usps": [...], "brands": [...]},
    }
    """
    context_config = config.get("context", {})
    context_urls = context_config.get("urls", [])

    if not context_urls:
        print("  [context] No context URLs configured, skipping")
        return _empty_context(config)

    domain = config["site"]["domain"]
    user_agent = config["scraping"]["user_agent"]
    delay = config["scraping"]["request_delay"]

    pages = []
    all_links = {}
    all_products = []

    for entry in context_urls:
        url = entry["url"]
        page_type = entry.get("type", "page")
        print(f"  [context] Scraping {page_type}: {url}")

        page_data = _scrape_page(url, user_agent, domain)
        page_data["type"] = page_type
        pages.append(page_data)

        # Collect all internal links (deduplicate by URL)
        for link in page_data["internal_links"]:
            link_url = link["url"]
            if link_url not in all_links:
                all_links[link_url] = link

        # Extract product-like names from product pages
        if page_type == "products":
            _extract_products(page_data, all_products)

        time.sleep(delay)

    # Build brand info from static config
    brand_info = {
        "brand_voice": context_config.get("brand_voice", ""),
        "usps": context_config.get("unique_selling_points", []),
        "brands": context_config.get("brands", []),
    }

    # Smart dedup: remove short names that are substrings of longer ones
    unique_products = list(dict.fromkeys(all_products))
    deduped_products = []
    for p in unique_products:
        # Skip if this is a short name fully contained in a longer product already kept
        is_substring = False
        for other in unique_products:
            if other != p and len(other) > len(p) and p.lower() in other.lower():
                is_substring = True
                break
        if not is_substring:
            deduped_products.append(p)

    # Shuffle for variety (each run gets a different order in prompts)
    random.shuffle(deduped_products)

    # Shuffle links too so prompts get different deep links each run
    shuffled_links = list(all_links.values())
    random.shuffle(shuffled_links)

    result = {
        "pages": pages,
        "all_internal_links": shuffled_links,
        "product_names": deduped_products,
        "brand_info": brand_info,
    }

    print(f"  [context] Scraped {len(pages)} pages, "
          f"{len(result['all_internal_links'])} internal links, "
          f"{len(result['product_names'])} products")

    return result


def _extract_products(page_data, product_list):
    """Extract product names from a product page's text and links."""
    # Product names often appear in link anchors on product listing pages
    skip_words = [
        "בלוג", "צור קשר", "אודות", "ראשי", "כניסה", "התחבר",
        "מוצרים", "מותגים", "יצירת קשר", "נקודות מכירה", "פרטים נוספים",
        "עלינו", "חנות", "קטגוריה", "דף הבית", "menu", "home", "contact",
        "login", "cart", "checkout", "מוצרים לכלבים", "מוצרים לחתולים",
        "מזון וציוד לכלבים", "מזון וציוד לחתולים",
    ]
    for link in page_data["internal_links"]:
        anchor = link["anchor"]
        # Filter out navigation items, keep product-like names
        if len(anchor) > 8 and len(anchor) < 100:
            if not any(w == anchor.strip() for w in skip_words):
                product_list.append(anchor)

    # Also extract from image alt texts (skip logos, icons, decorative)
    img_skip = ["logo", "לוגו", "icon", "whatsapp", "facebook", "instagram", "arrow", "banner"]
    for img in page_data["images"]:
        alt = img["alt"]
        if len(alt) > 8 and len(alt) < 100:
            if not any(w in alt.lower() for w in img_skip):
                product_list.append(alt)


def _empty_context(config):
    """Return minimal context from static config when no URLs are configured."""
    context_config = config.get("context", {})
    return {
        "pages": [],
        "all_internal_links": [],
        "product_names": [],
        "brand_info": {
            "brand_voice": context_config.get("brand_voice", ""),
            "usps": context_config.get("unique_selling_points", []),
            "brands": context_config.get("brands", []),
        },
    }


def format_context_for_prompt(site_context, topic=""):
    """
    Format the scraped site context into a string block for injection into Gemini prompts.
    Optionally filters products by topic relevance.
    """
    brand_info = site_context.get("brand_info", {})
    sections = []

    # Brand voice
    voice = brand_info.get("brand_voice", "").strip()
    if voice:
        sections.append(f"=== קול המותג ===\n{voice}")

    # USPs
    usps = brand_info.get("usps", [])
    if usps:
        usp_text = "\n".join(f"- {u}" for u in usps)
        sections.append(f"=== יתרונות ייחודיים ===\n{usp_text}")

    # Brands
    brands = brand_info.get("brands", [])
    if brands:
        brand_text = "\n".join(f"- {b['name']}: {b.get('description', '')}" for b in brands)
        sections.append(f"=== מותגים ===\n{brand_text}")

    # Products (filtered by topic if provided, limited to 20)
    products = site_context.get("product_names", [])
    if products:
        if topic:
            topic_words = set(topic.lower().split())
            relevant = [p for p in products if any(w in p.lower() for w in topic_words)]
            if not relevant:
                relevant = products[:20]
        else:
            relevant = products[:20]
        prod_text = "\n".join(f"- {p}" for p in relevant[:20])
        sections.append(f"=== מוצרים רלוונטיים באתר ===\n{prod_text}")

    # Internal links for deep linking (limited to 30)
    links = site_context.get("all_internal_links", [])
    if links:
        link_text = "\n".join(f"- {l['anchor']} → {l['url']}" for l in links[:30])
        sections.append(
            f"=== דפים באתר לקישור פנימי (השתמש בקישורים האלה בפוסט) ===\n{link_text}"
        )

    return "\n\n".join(sections)
