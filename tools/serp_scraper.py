"""
SERP scraper — uses Playwright (headless Chrome) with playwright-stealth.

To enable SERP scraping:
    pip install playwright playwright-stealth
    playwright install chromium

If Playwright is not installed, SERP calls return empty results gracefully
and the pipeline continues without SERP data.
"""
import os
import time


_SESSION_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "google_session.json")


def _load_session():
    """Load saved Google session state if available."""
    if os.path.exists(_SESSION_PATH):
        import json
        with open(_SESSION_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _scrape_with_playwright(query, lang="he", country="il", num_results=10, user_agent=None):
    """Scrape Google via headless Chromium with playwright-stealth + saved session."""
    from playwright.sync_api import sync_playwright
    from urllib.parse import unquote, urlencode

    results = {
        "query": query,
        "organic_results": [],
        "people_also_ask": [],
        "related_searches": [],
    }

    ua = user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    params = urlencode({"q": query, "hl": lang, "gl": country, "num": num_results})
    google_url = f"https://www.google.co.il/search?{params}"

    session = _load_session()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-background-networking",
            ],
        )
        ctx_kwargs = dict(
            user_agent=ua,
            locale=f"{lang}-{country.upper()}",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={
                "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        if session:
            ctx_kwargs["storage_state"] = session
        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()

        # Apply playwright-stealth (must be before navigation)
        try:
            from playwright_stealth import stealth_sync
            stealth_sync(page)
        except ImportError:
            pass

        try:
            page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass

        # Dismiss Google consent dialog if present (common in IL/EU)
        try:
            for selector in [
                "button[id='L2AGLb']",          # "Accept all" button (English)
                "button[aria-label*='Accept']",
                "button[aria-label*='אישור']",
                "form[action*='consent'] button",
                "#W0wltc",                       # another consent button variant
            ]:
                btn = page.query_selector(selector)
                if btn:
                    btn.click()
                    page.wait_for_timeout(1500)
                    break
        except Exception:
            pass

        # Wait for results
        try:
            page.wait_for_selector("div#search, div#rso, div.g", timeout=12000)
        except Exception:
            pass

        # ── Organic results ──────────────────────────────────────────────
        seen_urls = set()
        position = 1

        # Strategy 1: anchors with h3 (standard Google result structure)
        anchors = page.query_selector_all("div#rso a[href], div#search a[href]")
        for a in anchors:
            if position > num_results:
                break
            try:
                href = a.get_attribute("href") or ""
                # Handle /url?q= redirect URLs
                if "/url?q=" in href:
                    href = unquote(href.split("/url?q=")[1].split("&")[0])
                if not href.startswith("http"):
                    continue
                host = href.split("/")[2] if len(href.split("/")) > 2 else ""
                if "google." in host:
                    continue
                if href in seen_urls:
                    continue
                h3 = a.query_selector("h3")
                if not h3:
                    continue
                title = h3.inner_text().strip()
                if not title:
                    continue

                # Snippet
                snippet = ""
                try:
                    snippet = a.evaluate(
                        """el => {
                            const block = el.closest('div[data-hveid], div.g, li.b_algo');
                            if (!block) return '';
                            const s = block.querySelector(
                                '.VwiC3b, [data-sncf="1"], .lEBKkf, .st, .IsZvec'
                            );
                            return s ? s.innerText.trim() : '';
                        }"""
                    )
                except Exception:
                    pass

                seen_urls.add(href)
                results["organic_results"].append({
                    "position": position,
                    "title": title,
                    "url": href,
                    "snippet": snippet or "",
                })
                position += 1
            except Exception:
                continue

        # ── People Also Ask ──────────────────────────────────────────────
        try:
            paa_elements = page.query_selector_all(
                "[data-q], .related-question-pair span, .kno-ftr span"
            )
            for el in paa_elements:
                q = el.get_attribute("data-q") or el.inner_text()
                q = q.strip()
                if q and len(q) > 5:
                    results["people_also_ask"].append(q)
            results["people_also_ask"] = list(dict.fromkeys(results["people_also_ask"]))
        except Exception:
            pass

        # ── Related searches ─────────────────────────────────────────────
        try:
            rs_anchors = page.query_selector_all(
                "#botstuff a, #brs a, .related-searches a, [data-xbu] a"
            )
            for a in rs_anchors:
                text = a.inner_text().strip()
                if text and len(text) > 3 and text != query:
                    results["related_searches"].append(text)
            results["related_searches"] = list(dict.fromkeys(results["related_searches"]))
        except Exception:
            pass

        # Debug: if still no results, save a screenshot so we can see what Google returned
        if not results["organic_results"]:
            try:
                debug_path = os.path.join(os.path.dirname(__file__), "..", "output", "serp_debug.png")
                page.screenshot(path=debug_path, full_page=True)
                title = page.title()
                print(f"  [serp-debug] 0 results — page title: '{title}' | screenshot: output/serp_debug.png")
            except Exception:
                pass

        browser.close()

    return results


def scrape_serp(query, lang="he", country="il", num_results=10, user_agent=None):
    """
    Scrape search results for a query.
    Uses Playwright (headless Chrome) if installed, otherwise returns empty results.

    To enable: pip install playwright playwright-stealth && playwright install chromium
    """
    try:
        import playwright  # noqa — just check it's installed
        return _scrape_with_playwright(query, lang=lang, country=country,
                                       num_results=num_results, user_agent=user_agent)
    except ImportError:
        return {
            "query": query,
            "organic_results": [],
            "people_also_ask": [],
            "related_searches": [],
            "_skipped": "playwright_not_installed",
        }
    except Exception as e:
        print(f"  [serp] Error scraping '{query}': {e}")
        return {
            "query": query,
            "organic_results": [],
            "people_also_ask": [],
            "related_searches": [],
        }


def scrape_serps_batch(queries, lang="he", country="il", user_agent=None, delay=2):
    """Scrape SERPs for multiple queries with delay between requests."""
    try:
        import playwright  # noqa
        playwright_available = True
    except ImportError:
        playwright_available = False
        if queries:
            print("  [serp] Playwright not installed — skipping SERP scraping.")
            print("         To enable: pip install playwright playwright-stealth && playwright install chromium")

    results = {}
    for query in queries:
        results[query] = scrape_serp(query, lang=lang, country=country, user_agent=user_agent)
        if playwright_available and len(queries) > 1:
            time.sleep(delay)
    return results
