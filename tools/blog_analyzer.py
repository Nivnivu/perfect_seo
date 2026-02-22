import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET


def discover_blog_posts(blog_url, domain, user_agent=None):
    """
    Discover blog post URLs by crawling the blog index page
    and falling back to sitemap.xml.
    Uses the blog_url path dynamically (works for /blog, /programs, etc.).
    """
    headers = {
        "User-Agent": user_agent or "Mozilla/5.0",
        "Accept-Language": "he,en;q=0.5",
    }
    post_urls = set()

    # Extract the blog path from blog_url (e.g. "/blog", "/programs")
    blog_path = urlparse(blog_url).path.rstrip("/")

    # Try sitemap.xml first
    sitemap_url = f"https://{domain}/sitemap.xml"
    try:
        resp = requests.get(sitemap_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for url_el in root.findall(".//ns:url/ns:loc", ns):
                loc = url_el.text
                if loc and blog_path in loc and loc != blog_url and loc != blog_url + "/":
                    post_urls.add(loc)
    except Exception as e:
        print(f"  [blog] Sitemap parse warning: {e}")

    # Also crawl the blog index page for links
    try:
        resp = requests.get(blog_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = urljoin(blog_url, a["href"])
                parsed = urlparse(href)
                if (domain in parsed.netloc
                        and blog_path in parsed.path
                        and href != blog_url
                        and href != blog_url + "/"
                        and not parsed.path.rstrip("/") == blog_path):
                    post_urls.add(href.rstrip("/"))
    except Exception as e:
        print(f"  [blog] Blog index crawl warning: {e}")

    return list(post_urls)


def analyze_blog_post(url, user_agent=None):
    """
    Analyze a single blog post for SEO signals.
    """
    headers = {
        "User-Agent": user_agent or "Mozilla/5.0",
        "Accept-Language": "he,en;q=0.5",
    }

    result = {
        "url": url,
        "title": "",
        "meta_description": "",
        "headings": {"h1": [], "h2": [], "h3": []},
        "word_count": 0,
        "keywords_found": [],
        "keywords_missing": [],
        "has_internal_links": False,
        "has_images": False,
        "images_with_alt": 0,
        "content_text": "",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

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

        # Body content
        body = soup.find("article") or soup.find("main") or soup.find("body")
        if body:
            text = body.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            result["word_count"] = len(text.split())
            result["content_text"] = text[:3000]

            # Extract Hebrew words as found keywords
            words = re.findall(r"[\u0590-\u05FF]{2,}", text)
            from collections import Counter
            word_counts = Counter(words)
            result["keywords_found"] = [w for w, c in word_counts.most_common(30)]

        # Links & images
        result["has_internal_links"] = bool(soup.find("a", href=True))
        images = soup.find_all("img")
        result["has_images"] = len(images) > 0
        result["images_with_alt"] = sum(1 for img in images if img.get("alt", "").strip())

    except Exception as e:
        print(f"  [blog] Error analyzing {url}: {e}")

    return result


def analyze_all_posts(blog_url, domain, user_agent=None, delay=2):
    """Discover and analyze all blog posts."""
    urls = discover_blog_posts(blog_url, domain, user_agent=user_agent)
    print(f"  [blog] Discovered {len(urls)} blog posts")

    results = []
    for url in urls:
        analysis = analyze_blog_post(url, user_agent=user_agent)
        results.append(analysis)
        if len(urls) > 1:
            time.sleep(delay)

    return results
