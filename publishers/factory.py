"""Publisher factory — returns the right BasePlatformPublisher for a site config."""
from publishers.base import BasePlatformPublisher


def get_publisher(config: dict) -> BasePlatformPublisher:
    platform = config.get("platform", "mongodb")

    if platform == "mongodb":
        from publishers.mongodb import MongoDBPublisher
        return MongoDBPublisher(config)
    elif platform == "wordpress":
        from publishers.wordpress import WordPressPublisher
        return WordPressPublisher(config)
    elif platform == "woocommerce":
        from publishers.woocommerce import WooCommercePublisher
        return WooCommercePublisher(config)
    elif platform == "shopify":
        from publishers.shopify import ShopifyPublisher
        return ShopifyPublisher(config)
    elif platform == "wix":
        from publishers.wix import WixPublisher
        return WixPublisher(config)
    else:
        raise ValueError(f"Unknown platform: {platform!r}")
