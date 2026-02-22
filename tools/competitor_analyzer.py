import requests
from bs4 import BeautifulSoup
from collections import Counter
import re
import time


def analyze_page(url, user_agent=None):
    """
    Fetch and analyze a single page for SEO content signals.
    Returns dict with headings, word count, keyword density, etc.
    """
    headers = {
        "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "he,en;q=0.5",
    }

    result = {
        "url": url,
        "title": "",
        "meta_description": "",
        "headings": {"h1": [], "h2": [], "h3": []},
        "word_count": 0,
        "internal_links": 0,
        "external_links": 0,
        "images_count": 0,
        "images_with_alt": 0,
        "keyword_density": {},
        "content_text": "",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Title
        title_tag = soup.find("title")
        if title_tag:
            result["title"] = title_tag.get_text(strip=True)

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            result["meta_description"] = meta_desc.get("content", "")

        # Headings
        for level in ["h1", "h2", "h3"]:
            result["headings"][level] = [
                h.get_text(strip=True) for h in soup.find_all(level)
            ]

        # Body text
        body = soup.find("article") or soup.find("main") or soup.find("body")
        if body:
            text = body.get_text(separator=" ", strip=True)
            # Clean up whitespace
            text = re.sub(r"\s+", " ", text).strip()
            result["word_count"] = len(text.split())
            result["content_text"] = text[:3000]

            # Keyword density (Hebrew words, 2+ chars)
            words = re.findall(r"[\u0590-\u05FF]{2,}", text)
            word_counts = Counter(words)
            result["keyword_density"] = dict(word_counts.most_common(20))

        # Links
        from urllib.parse import urlparse
        page_domain = urlparse(url).netloc
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http"):
                link_domain = urlparse(href).netloc
                if link_domain == page_domain:
                    result["internal_links"] += 1
                else:
                    result["external_links"] += 1

        # Images
        images = soup.find_all("img")
        result["images_count"] = len(images)
        result["images_with_alt"] = sum(1 for img in images if img.get("alt", "").strip())

    except Exception as e:
        print(f"  [competitor] Error analyzing {url}: {e}")

    return result


def analyze_competitors(urls, user_agent=None, delay=2):
    """Analyze multiple competitor pages. Returns list of analysis dicts."""
    results = []
    for url in urls:
        analysis = analyze_page(url, user_agent=user_agent)
        results.append(analysis)
        if len(urls) > 1:
            time.sleep(delay)
    return results


def summarize_competitor_patterns(analyses):
    """
    Summarize patterns across all analyzed competitor pages.
    Returns dict with averages and common elements.
    """
    if not analyses:
        return {
            "avg_word_count": 1500,
            "common_headings": [],
            "common_keywords": [],
            "avg_images": 5,
        }

    valid = [a for a in analyses if a["word_count"] > 0]
    if not valid:
        valid = analyses

    # Average word count
    avg_wc = sum(a["word_count"] for a in valid) // len(valid) if valid else 1500

    # Collect all headings
    all_h2 = []
    for a in valid:
        all_h2.extend(a["headings"].get("h2", []))

    # Common keywords across all pages
    all_keywords = Counter()
    for a in valid:
        all_keywords.update(a.get("keyword_density", {}))

    # Average images
    avg_imgs = sum(a["images_count"] for a in valid) // len(valid) if valid else 5

    return {
        "avg_word_count": avg_wc,
        "common_headings": [h for h, _ in Counter(all_h2).most_common(15)],
        "common_keywords": [kw for kw, _ in all_keywords.most_common(30)],
        "avg_images": avg_imgs,
    }
