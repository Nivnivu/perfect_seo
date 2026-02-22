import requests
from bs4 import BeautifulSoup
import time


def scrape_serp(query, lang="he", country="il", num_results=10, user_agent=None):
    """
    Scrape Google search results for a query.
    Returns dict with organic_results, people_also_ask, related_searches.
    """
    url = f"https://www.google.co.il/search"
    params = {
        "q": query,
        "hl": lang,
        "gl": country,
        "num": num_results,
    }
    headers = {
        "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": f"{lang},en;q=0.5",
    }

    result = {
        "query": query,
        "organic_results": [],
        "people_also_ask": [],
        "related_searches": [],
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Organic results
        position = 1
        for g in soup.select("div.g"):
            title_el = g.select_one("h3")
            link_el = g.select_one("a[href]")
            snippet_el = g.select_one("div[data-sncf]") or g.select_one(".VwiC3b")

            if title_el and link_el:
                href = link_el.get("href", "")
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[1].split("&")[0]
                if href.startswith("http"):
                    result["organic_results"].append({
                        "position": position,
                        "title": title_el.get_text(strip=True),
                        "url": href,
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                    })
                    position += 1

        # People Also Ask
        for paa in soup.select("[data-sgrd] [data-q]"):
            question = paa.get("data-q", "").strip()
            if question:
                result["people_also_ask"].append(question)

        # Fallback: look for PAA in expandable sections
        if not result["people_also_ask"]:
            for paa in soup.select(".related-question-pair span"):
                text = paa.get_text(strip=True)
                if text and "?" in text:
                    result["people_also_ask"].append(text)

        # Related searches
        for rs in soup.select("#botstuff a"):
            text = rs.get_text(strip=True)
            if text and text != query and len(text) > 3:
                result["related_searches"].append(text)

        # Deduplicate
        result["people_also_ask"] = list(dict.fromkeys(result["people_also_ask"]))
        result["related_searches"] = list(dict.fromkeys(result["related_searches"]))

    except Exception as e:
        print(f"  [serp] Error scraping '{query}': {e}")

    return result


def scrape_serps_batch(queries, lang="he", country="il", user_agent=None, delay=2):
    """Scrape SERPs for multiple queries with delay between requests."""
    results = {}
    for query in queries:
        results[query] = scrape_serp(query, lang=lang, country=country, user_agent=user_agent)
        if len(queries) > 1:
            time.sleep(delay)
    return results
