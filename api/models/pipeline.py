from typing import Optional
from pydantic import BaseModel
from enum import Enum


class PipelineMode(str, Enum):
    NEW = "new"
    UPDATE = "update"
    STATIC = "static"
    FULL = "full"
    IMAGES = "images"
    RECOVER = "recover"
    DIAGNOSE = "diagnose"
    PRODUCTS = "products"
    IMPACT = "impact"
    DEDUPE = "dedupe"
    RESTORE_TITLES = "restore_titles"


class PipelineRunRequest(BaseModel):
    site_id: str
    mode: PipelineMode
    keywords: Optional[list[str]] = None
    manual_publish: bool = False
