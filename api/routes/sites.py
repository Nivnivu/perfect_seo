from typing import Any
from fastapi import APIRouter, HTTPException
from api.config_manager import list_sites, get_site, save_site, delete_site
from api.models.site import SiteSummary, CreateSiteRequest, TestConnectionRequest, PlatformType

router = APIRouter()


@router.get("", response_model=list[SiteSummary])
def get_sites():
    return list_sites()


@router.get("/{site_id}")
def get_site_config(site_id: str):
    config = get_site(site_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return config


@router.post("", status_code=201)
def create_site(request: CreateSiteRequest):
    config_data: dict[str, Any] = dict(request.config)
    config_data["platform"] = request.platform.value
    path = save_site(request.site_id, config_data)
    return {"id": request.site_id, "file": path.name, "message": "Site created"}


@router.put("/{site_id}")
def update_site(site_id: str, config: dict[str, Any]):
    if not get_site(site_id):
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    path = save_site(site_id, config)
    return {"id": site_id, "file": path.name, "message": "Site updated"}


@router.delete("/{site_id}")
def remove_site(site_id: str):
    if not delete_site(site_id):
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return {"message": f"Site '{site_id}' deleted"}


@router.post("/test-connection")
def test_platform_connection(request: TestConnectionRequest):
    platform = request.platform
    creds = request.credentials

    if platform == PlatformType.MONGODB:
        try:
            from pymongo import MongoClient
            client = MongoClient(creds.get("uri", ""), serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            client.close()
            return {"success": True, "message": "MongoDB connection successful ✓"}
        except ImportError:
            raise HTTPException(status_code=400, detail="pymongo not installed. Run: pip install pymongo[srv]")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"MongoDB error: {e}")

    elif platform == PlatformType.WORDPRESS:
        try:
            import requests as req
            raw = creds.get("site_url", "").strip().rstrip("/")
            if raw and not raw.startswith(("http://", "https://")):
                raw = "https://" + raw
            base = raw
            url = base + "/wp-json/wp/v2/users/me"
            auth_method = creds.get("auth_method", "app_password")
            kw: dict = {"timeout": 10, "allow_redirects": True}
            if auth_method == "bearer":
                kw["headers"] = {"Authorization": f"Bearer {creds.get('token', '')}"}
            elif auth_method == "password":
                kw["auth"] = (creds.get("username", ""), creds.get("password", ""))
            else:  # app_password
                kw["auth"] = (creds.get("username", ""), creds.get("app_password", ""))

            r = req.get(url, **kw)
            snippet = r.text[:400].strip()

            if r.status_code == 200:
                try:
                    name = r.json().get("name", "user")
                    return {"success": True, "message": f"WordPress connected as: {name} ✓"}
                except Exception:
                    # 200 but not JSON — REST API reachable but returned unexpected content
                    preview = snippet[:120]
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"WordPress REST API returned HTTP 200 but the body is not JSON. "
                            f"Make sure pretty permalinks are enabled (Settings → Permalinks → save). "
                            f"Response preview: {preview!r}"
                        ),
                    )

            if r.status_code == 401:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Authentication failed (HTTP 401). "
                        + ("Check your username and application password. Generate one in Users → Profile → Application Passwords."
                           if auth_method == "app_password" else
                           "Check your username and password.")
                    ),
                )
            if r.status_code == 404:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"REST API not found at {url}. "
                        f"Ensure pretty permalinks are enabled and the site URL is the WordPress root (not a page or blog path)."
                    ),
                )
            if "<html" in snippet.lower():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"WordPress returned an HTML page (HTTP {r.status_code}) instead of JSON. "
                        f"The REST API may be blocked by a security plugin, firewall, or the URL is wrong. "
                        f"Preview: {snippet[:150]!r}"
                    ),
                )
            raise HTTPException(status_code=400, detail=f"WordPress error HTTP {r.status_code}: {snippet[:200]}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"WordPress connection error: {e}")

    elif platform == PlatformType.WOOCOMMERCE:
        try:
            import requests as req
            raw_wc = creds.get("site_url", "").strip().rstrip("/")
            if raw_wc and not raw_wc.startswith(("http://", "https://")):
                raw_wc = "https://" + raw_wc
            url = raw_wc + "/wp-json/wc/v3/system_status"
            r = req.get(url, auth=(creds.get("consumer_key", ""), creds.get("consumer_secret", "")), timeout=10)
            if r.status_code == 200:
                return {"success": True, "message": "WooCommerce connection successful ✓"}
            raise HTTPException(status_code=400, detail=f"WooCommerce auth failed (HTTP {r.status_code}). Check consumer key and secret.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"WooCommerce error: {e}")

    elif platform == PlatformType.SHOPIFY:
        try:
            import requests as req
            domain = creds.get("store_domain", "").strip().rstrip("/")
            if not domain.endswith(".myshopify.com"):
                domain = f"{domain}.myshopify.com"
            url = f"https://{domain}/admin/api/2024-01/shop.json"
            headers = {"X-Shopify-Access-Token": creds.get("admin_api_token", "")}
            r = req.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                shop_name = r.json().get("shop", {}).get("name", "store")
                return {"success": True, "message": f"Shopify connected: {shop_name} ✓"}
            raise HTTPException(status_code=400, detail=f"Shopify auth failed (HTTP {r.status_code}). Check store domain and access token.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Shopify error: {e}")

    elif platform == PlatformType.WIX:
        return {"success": True, "message": "Wix credentials saved — connection verified on first pipeline run."}

    raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
