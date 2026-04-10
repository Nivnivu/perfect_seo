import asyncio
import os
from fastapi import APIRouter, HTTPException
from api.config_manager import get_site, ROOT_DIR

router = APIRouter()

# ── OAuth Authorization ──────────────────────────────────────────────────────

@router.post("/{site_id}/authorize")
async def authorize_gsc(site_id: str):
    """
    Trigger the GSC OAuth flow for this site.
    Since this is a local tool, _get_gsc_service() opens the browser on the
    local machine and blocks until the user completes the authorization.
    Saves the token to gsc_token.json in the project root.
    """
    site = get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    gsc_config = _check_gsc(site)
    if not gsc_config:
        raise HTTPException(status_code=400, detail="Search Console is not configured for this site. Add a search_console block to its YAML config.")

    credentials_file = gsc_config.get("credentials_file", "")
    if not credentials_file or not os.path.exists(os.path.join(str(ROOT_DIR), credentials_file)):
        raise HTTPException(
            status_code=400,
            detail=f"OAuth credentials file not found: '{credentials_file}'. Download it from Google Cloud Console → APIs & Services → Credentials.",
        )

    def _do_auth():
        import sys
        sys.path.insert(0, str(ROOT_DIR))
        from tools.search_console import _get_gsc_service
        _get_gsc_service(site)  # opens browser, waits for consent, saves token

    try:
        await asyncio.to_thread(_do_auth)
        return {"status": "authorized", "message": "GSC connected successfully. Token saved."}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth failed: {e}")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _check_gsc(site: dict) -> dict | None:
    """Returns None if GSC is not configured, else the gsc config block."""
    gsc = site.get("search_console")
    if not gsc:
        return None
    return gsc


def _token_exists(gsc_config: dict) -> bool:
    token_file = gsc_config.get("token_file", "gsc_token.json")
    return os.path.exists(os.path.join(str(ROOT_DIR), token_file))


@router.get("/{site_id}")
async def get_gsc_summary(site_id: str, days: int = 28):
    """
    Returns: summary metrics, top pages by clicks, and SEO opportunities.
    Requires GSC to be configured and authenticated.
    """
    site = get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    gsc_config = _check_gsc(site)
    if not gsc_config:
        return {"configured": False, "authenticated": False, "data": None}

    if not _token_exists(gsc_config):
        return {"configured": True, "authenticated": False, "data": None,
                "message": "GSC token not found. Run the pipeline once to authorize."}

    def _fetch():
        import sys
        sys.path.insert(0, str(ROOT_DIR))
        from tools.search_console import fetch_gsc_performance

        perf = fetch_gsc_performance(site, days=days)
        if not perf:
            return {"configured": True, "authenticated": True, "data": {
                "summary": {"total_clicks": 0, "total_impressions": 0, "avg_position": 0, "avg_ctr_pct": 0},
                "top_pages": [],
                "opportunities": {"page2": [], "ctr": []},
            }}

        # Summary
        total_clicks = sum(v["clicks"] for v in perf.values())
        total_impressions = sum(v["impressions"] for v in perf.values())
        all_positions = [v["position"] for v in perf.values() if v.get("position")]
        all_ctrs = [v["ctr"] for v in perf.values()]
        avg_position = round(sum(all_positions) / len(all_positions), 1) if all_positions else 0
        avg_ctr_pct = round(sum(all_ctrs) / len(all_ctrs) * 100, 1) if all_ctrs else 0

        # Top pages
        top_pages = sorted(
            [
                {
                    "url": url,
                    "clicks": int(d["clicks"]),
                    "impressions": int(d["impressions"]),
                    "position": round(d["position"], 1),
                    "ctr_pct": round(d["ctr"] * 100, 1),
                }
                for url, d in perf.items()
            ],
            key=lambda x: x["clicks"],
            reverse=True,
        )[:20]

        # Opportunities
        page2 = []
        ctr_opps = []
        for url, d in perf.items():
            pos = d.get("position", 999)
            impr = d.get("impressions", 0)
            clicks = d.get("clicks", 0)
            ctr = d.get("ctr", 0)
            item = {
                "url": url,
                "clicks": int(clicks),
                "impressions": int(impr),
                "position": round(pos, 1),
                "ctr_pct": round(ctr * 100, 1),
            }
            if 11 <= pos <= 30 and impr >= 20:
                page2.append(item)
            elif pos <= 10 and ctr * 100 < 3.0 and impr >= 50:
                ctr_opps.append(item)

        page2.sort(key=lambda x: x["impressions"], reverse=True)
        ctr_opps.sort(key=lambda x: x["impressions"], reverse=True)

        return {
            "configured": True,
            "authenticated": True,
            "data": {
                "summary": {
                    "total_clicks": int(total_clicks),
                    "total_impressions": int(total_impressions),
                    "avg_position": avg_position,
                    "avg_ctr_pct": avg_ctr_pct,
                    "pages_tracked": len(perf),
                },
                "top_pages": top_pages,
                "opportunities": {
                    "page2": page2[:25],
                    "ctr": ctr_opps[:25],
                },
            },
        }

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{site_id}/pages")
async def get_gsc_pages(site_id: str, days: int = 28):
    """Returns all GSC page stats as a dict keyed by URL. Used for per-post hover stats."""
    site = get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    gsc_config = _check_gsc(site)
    if not gsc_config or not _token_exists(gsc_config):
        return {}

    def _fetch():
        import sys
        sys.path.insert(0, str(ROOT_DIR))
        from tools.search_console import fetch_gsc_performance
        perf = fetch_gsc_performance(site, days=days)
        if not perf:
            return {}
        return {
            url: {
                "clicks": int(d["clicks"]),
                "impressions": int(d["impressions"]),
                "position": round(d["position"], 1),
                "ctr_pct": round(d["ctr"] * 100, 1),
            }
            for url, d in perf.items()
        }

    try:
        return await asyncio.to_thread(_fetch)
    except Exception:
        return {}


@router.post("/{site_id}/request-indexing")
async def request_indexing(site_id: str):
    """Submit the site's sitemap to Google Search Console to request re-crawling of all pages."""
    site = get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    gsc_config = _check_gsc(site)
    if not gsc_config:
        raise HTTPException(status_code=400, detail="GSC not configured for this site.")
    if not _token_exists(gsc_config):
        raise HTTPException(status_code=400, detail="GSC not authorized. Connect GSC first.")

    def _ping():
        import sys
        sys.path.insert(0, str(ROOT_DIR))
        from tools.search_console import ping_sitemap
        return ping_sitemap(site)

    try:
        success = await asyncio.to_thread(_ping)
        if success:
            return {"status": "ok", "message": "Sitemap submitted to Google. Pages will be re-crawled within hours."}
        raise HTTPException(status_code=400, detail="Could not find sitemap at standard paths (sitemap.xml / sitemap_index.xml). Verify your sitemap is publicly accessible.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{site_id}/series")
async def get_gsc_series(site_id: str, weeks: int = 12):
    """Returns weekly click/impression trend data for charts."""
    site = get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    gsc_config = _check_gsc(site)
    if not gsc_config:
        return {"configured": False, "series": []}
    if not _token_exists(gsc_config):
        return {"configured": True, "authenticated": False, "series": []}

    def _fetch():
        import sys
        sys.path.insert(0, str(ROOT_DIR))
        from tools.search_console import fetch_gsc_weekly_trends
        return fetch_gsc_weekly_trends(site, weeks=weeks)

    try:
        series = await asyncio.to_thread(_fetch)
        return {"configured": True, "authenticated": True, "series": series}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
