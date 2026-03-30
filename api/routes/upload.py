"""File upload endpoints — logo, etc."""
from fastapi import APIRouter, UploadFile, File, HTTPException
from api.config_manager import ROOT_DIR

router = APIRouter()

LOGOS_DIR = ROOT_DIR / "logos"
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}. Use PNG, JPEG, WebP, or SVG.")

    data = await file.read()
    if len(data) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 2 MB.")

    LOGOS_DIR.mkdir(exist_ok=True)

    safe_name = "".join(c for c in (file.filename or "logo") if c.isalnum() or c in "._-")
    dest = LOGOS_DIR / safe_name

    with open(dest, "wb") as f:
        f.write(data)

    # Return relative path (relative to project root) — stored in config as site.logo
    return {"path": f"logos/{safe_name}", "filename": safe_name}
