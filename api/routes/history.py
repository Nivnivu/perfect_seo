import json
from fastapi import APIRouter, HTTPException
from api.config_manager import get_site, ROOT_DIR

router = APIRouter()


def _load_json(path) -> list:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else list(data.values())


@router.get("/{site_id}")
def get_update_history(site_id: str):
    site = get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    collection = site.get("mongodb", {}).get("collection", site_id)
    return _load_json(ROOT_DIR / "output" / f"{collection}_update_history.json")


@router.get("/{site_id}/recovery")
def get_recovery_history(site_id: str):
    site = get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    collection = site.get("mongodb", {}).get("collection", site_id)
    return _load_json(ROOT_DIR / "output" / f"{collection}_recovery_history.json")
