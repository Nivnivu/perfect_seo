import requests
import time


def get_autocomplete(query, lang="he", user_agent=None):
    """Hit Google's free suggest endpoint. Returns list of suggestions."""
    url = "http://suggestqueries.google.com/complete/search"
    params = {"client": "firefox", "q": query, "hl": lang}
    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data[1] if len(data) > 1 else []
    except Exception as e:
        print(f"  [autocomplete] Error for '{query}': {e}")
        return []


def get_autocomplete_expanded(seed_keywords, lang="he", user_agent=None, delay=1):
    """
    Run autocomplete for multiple seed keywords.
    Returns dict: {keyword: [suggestions]}
    """
    results = {}
    for kw in seed_keywords:
        suggestions = get_autocomplete(kw, lang=lang, user_agent=user_agent)
        results[kw] = suggestions
        if len(seed_keywords) > 1:
            time.sleep(delay)
    return results
