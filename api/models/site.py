from typing import Any, Optional
from pydantic import BaseModel
from enum import Enum


class PlatformType(str, Enum):
    MONGODB = "mongodb"
    WORDPRESS = "wordpress"
    WOOCOMMERCE = "woocommerce"
    SHOPIFY = "shopify"
    WIX = "wix"


class SiteSummary(BaseModel):
    id: str
    file: str
    name: str
    domain: str
    language: str
    platform: str
    has_gsc: bool


class CreateSiteRequest(BaseModel):
    site_id: str
    platform: PlatformType = PlatformType.MONGODB
    config: dict[str, Any]


class TestConnectionRequest(BaseModel):
    platform: PlatformType
    credentials: dict[str, Any]
