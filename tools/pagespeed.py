"""
PageSpeed Insights integration — free API, no authentication required.
Fetches Core Web Vitals and performance scores per URL.

Core Web Vitals (Google ranking factors since 2021):
  LCP  — Largest Contentful Paint  (loading)   good: <2.5s, poor: >4s
  INP  — Interaction to Next Paint (interactivity) good: <200ms, poor: >500ms
  CLS  — Cumulative Layout Shift   (stability)  good: <0.1, poor: >0.25
  FCP  — First Contentful Paint    (perceived load)
"""
import requests
import time


_PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

_THRESHOLDS = {
    "lcp":  {"good": 2500,  "poor": 4000,  "unit": "ms",  "label": "LCP  (Largest Contentful Paint)"},
    "inp":  {"good": 200,   "poor": 500,   "unit": "ms",  "label": "INP  (Interaction to Next Paint)"},
    "cls":  {"good": 0.1,   "poor": 0.25,  "unit": "",    "label": "CLS  (Cumulative Layout Shift)"},
    "fcp":  {"good": 1800,  "poor": 3000,  "unit": "ms",  "label": "FCP  (First Contentful Paint)"},
    "ttfb": {"good": 800,   "poor": 1800,  "unit": "ms",  "label": "TTFB (Time to First Byte)"},
}


def _rating(value, thresholds):
    if value is None:
        return "N/A"
    good = thresholds["good"]
    poor = thresholds["poor"]
    if value <= good:
        return "GOOD"
    if value <= poor:
        return "NEEDS IMPROVEMENT"
    return "POOR"


def _extract_cwv(data):
    """Extract Core Web Vitals from a PSI API response dict."""
    result = {
        "score": None,
        "lcp": None, "inp": None, "cls": None, "fcp": None, "ttfb": None,
        "ratings": {},
        "error": None,
    }

    try:
        cats = data.get("lighthouseResult", {}).get("categories", {})
        perf = cats.get("performance", {})
        result["score"] = round((perf.get("score") or 0) * 100)

        audits = data.get("lighthouseResult", {}).get("audits", {})

        # LCP
        lcp_audit = audits.get("largest-contentful-paint", {})
        lcp_raw = lcp_audit.get("numericValue")
        if lcp_raw is not None:
            result["lcp"] = round(lcp_raw)

        # CLS
        cls_audit = audits.get("cumulative-layout-shift", {})
        cls_raw = cls_audit.get("numericValue")
        if cls_raw is not None:
            result["cls"] = round(cls_raw, 3)

        # FCP
        fcp_audit = audits.get("first-contentful-paint", {})
        fcp_raw = fcp_audit.get("numericValue")
        if fcp_raw is not None:
            result["fcp"] = round(fcp_raw)

        # TTFB
        ttfb_audit = audits.get("server-response-time", {})
        ttfb_raw = ttfb_audit.get("numericValue")
        if ttfb_raw is not None:
            result["ttfb"] = round(ttfb_raw)

        # INP — from field data (CrUX) since Lighthouse doesn't measure INP
        field = data.get("loadingExperience", {}).get("metrics", {})
        inp_data = field.get("INTERACTION_TO_NEXT_PAINT", {})
        inp_p75 = inp_data.get("percentile")
        if inp_p75 is not None:
            result["inp"] = inp_p75

        # Ratings
        for metric, thresholds in _THRESHOLDS.items():
            val = result.get(metric)
            if val is not None:
                result["ratings"][metric] = _rating(val, thresholds)

    except Exception as e:
        result["error"] = str(e)

    return result


def check_page_speed(url, strategy="mobile", api_key=None):
    """
    Check Core Web Vitals for a single URL using PageSpeed Insights API.
    No API key needed for basic usage (rate limited to ~25 req/100s).

    strategy: "mobile" or "desktop"
    Returns dict with score, lcp, inp, cls, fcp, ttfb, ratings, error.
    """
    params = {"url": url, "strategy": strategy}
    if api_key:
        params["key"] = api_key

    try:
        resp = requests.get(_PSI_URL, params=params, timeout=45)
        if resp.status_code == 429:
            return {"error": "rate_limited", "score": None}
        resp.raise_for_status()
        return _extract_cwv(resp.json())
    except requests.Timeout:
        return {"error": "timeout", "score": None}
    except Exception as e:
        return {"error": str(e), "score": None}


def check_pages_speed(urls, strategy="mobile", api_key=None, delay=4.0, max_pages=10):
    """
    Check Core Web Vitals for multiple URLs.
    Respects rate limits with a delay between requests.
    Returns: {url: cwv_dict}
    """
    results = {}
    checked = 0
    for url in urls[:max_pages]:
        print(f"  [pagespeed] Checking {strategy}: {url[:80]}...")
        result = check_page_speed(url, strategy=strategy, api_key=api_key)
        results[url] = result
        checked += 1

        if result.get("error") == "rate_limited":
            print(f"  [pagespeed] Rate limited — stopping after {checked} pages")
            break

        if checked < len(urls[:max_pages]):
            time.sleep(delay)

    return results


def format_cwv_summary(url, cwv, prefix="  "):
    """Format a Core Web Vitals result as a readable string."""
    if not cwv or cwv.get("error"):
        msg = cwv.get("error", "not checked (rate limited)") if cwv else "not checked (rate limited)"
        short_url = url.rstrip("/").split("/")[-1] or url.split("/")[-2] or url
        return f"{prefix}{short_url[:50]:50s} — {msg}"

    score_str = f"Score: {cwv.get('score', 'N/A')}/100" if cwv.get("score") is not None else "Score: N/A"
    parts = [score_str]

    ratings = cwv.get("ratings", {})
    metric_strs = []
    for metric, thresholds in _THRESHOLDS.items():
        val = cwv.get(metric)
        if val is None:
            continue
        unit = thresholds["unit"]
        rating = ratings.get(metric, "")
        flag = "OK" if rating == "GOOD" else ("!!" if rating == "POOR" else "~")
        if metric == "cls":
            metric_strs.append(f"{metric.upper()}={val}{unit}[{flag}]")
        else:
            val_s = f"{val}ms" if unit == "ms" else str(val)
            metric_strs.append(f"{metric.upper()}={val_s}[{flag}]")

    parts.extend(metric_strs)
    short_url = url.split("/")[-1] or url.split("/")[-2] or url
    return f"{prefix}{short_url[:50]:50s} {' | '.join(parts)}"
