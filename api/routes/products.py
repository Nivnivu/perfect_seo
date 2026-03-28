import asyncio
from fastapi import APIRouter, HTTPException
from api.config_manager import get_site

router = APIRouter()


@router.get("/{site_id}")
async def get_products(site_id: str, limit: int = 50):
    site = get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    def _fetch():
        from publishers.factory import get_publisher
        return get_publisher(site).fetch_products(limit=limit)

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
