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
            from requests.auth import HTTPBasicAuth
            url = creds.get("site_url", "").rstrip("/") + "/wp-json/wp/v2/users/me"
            r = req.get(url, auth=HTTPBasicAuth(creds.get("username", ""), creds.get("app_password", "")), timeout=10)
            if r.status_code == 200:
                name = r.json().get("name", "user")
                return {"success": True, "message": f"WordPress connected as: {name} ✓"}
            raise HTTPException(status_code=400, detail=f"WordPress auth failed (HTTP {r.status_code}). Check URL, username, and application password.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"WordPress error: {e}")

    elif platform == PlatformType.WOOCOMMERCE:
        try:
            import requests as req
            url = creds.get("site_url", "").rstrip("/") + "/wp-json/wc/v3/system_status"
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
