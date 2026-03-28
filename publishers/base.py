"""Abstract base class for all platform publishers."""
from abc import ABC, abstractmethod


class BasePlatformPublisher(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def fetch_posts(self, limit: int = 50) -> list[dict]:
        """
        Fetch recent posts/products.
        Returns list of dicts: {_id, title, subtitle, url, created_at, status, ...}
        """
        ...

    @abstractmethod
    def publish_post(self, post_data: dict) -> str:
        """Publish a new post. Returns the platform's post ID as a string."""
        ...

    @abstractmethod
    def update_post(self, post_id: str, update_data: dict) -> bool:
        """Update an existing post. Returns True on success."""
        ...

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Test the platform connection. Returns (success, message)."""
        ...

    def fetch_products(self, limit: int = 50) -> list[dict]:
        """Fetch e-commerce products. Override in store publishers (WooCommerce, Shopify).
        Returns list of dicts: {_id, title, subtitle, url, created_at, status, price, image1Url, ...}
        """
        return []
