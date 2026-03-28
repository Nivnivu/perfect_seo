"""MongoDB publisher — wraps the existing publisher/post_publisher.py."""
from publishers.base import BasePlatformPublisher


class MongoDBPublisher(BasePlatformPublisher):
    def fetch_posts(self, limit: int = 50) -> list[dict]:
        from publisher.mongodb_client import _get_client, get_master_user_id
        client = _get_client(self.config)
        db = client[self.config["mongodb"]["database"]]
        col = db[self.config["mongodb"]["collection"]]
        posts = list(
            col.find(
                {"type": "blogPost"},
                {"title": 1, "subtitle": 1, "image1Url": 1, "createdAt": 1},
            ).sort("createdAt", -1).limit(limit)
        )

        # Resolve upload_id once — same fallback chain as post_publisher.py
        upload_id = (
            self.config.get("supabase", {}).get("storage_user_id")
            or get_master_user_id(self.config)
            or self.config["mongodb"]["collection"]
        )

        # Use blog_url as URL base — that's where posts live.
        # Never use sc-domain: style GSC site_url as a URL prefix.
        blog_url = self.config.get("site", {}).get("blog_url", "")
        domain = self.config.get("site", {}).get("domain", "")
        site_base = (blog_url or f"https://{domain}").rstrip("/")

        result = []
        for p in posts:
            created = p.get("createdAt")
            title = p.get("title", "")
            result.append({
                "_id": str(p["_id"]),
                "title": title,
                "subtitle": p.get("subtitle", ""),
                "image1Url": self._resolve_image_url(p.get("image1Url", ""), upload_id),
                "url": f"{site_base}/{title}" if site_base and title else "",
                "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
                "status": "published",
            })
        return result

    def _resolve_image_url(self, value: str, upload_id: str) -> str:
        """Return a full URL. If value is already a URL, return as-is.
        Otherwise it's a bare filename — build the Supabase public URL."""
        if not value or value.startswith("http"):
            return value
        supabase = self.config.get("supabase", {})
        base = supabase.get("url", "").rstrip("/")
        bucket = supabase.get("bucket", "blog-poster")
        return f"{base}/storage/v1/object/public/{bucket}/{upload_id}/{value}"

    def publish_post(self, post_data: dict) -> str:
        from publisher.post_publisher import publish_blog_post
        result = publish_blog_post(
            post_data["gemini_output"],
            post_data.get("desktop_image"),
            post_data.get("mobile_image"),
            self.config,
        )
        return result["post_id"]

    def update_post(self, post_id: str, update_data: dict) -> bool:
        from publisher.mongodb_client import update_blog_post
        return update_blog_post(post_id, update_data, self.config) > 0

    def fetch_products(self, limit: int = 50) -> list[dict]:
        """Fetch from the wordpress_products collection (separate products database)."""
        products_db_name = self.config.get("mongodb", {}).get("products_database")
        if not products_db_name:
            return []

        from publisher.mongodb_client import _get_client
        client = _get_client(self.config)
        db = client[products_db_name]
        col = db["wordpress_products"]
        docs = list(col.find({}, {"title": 1, "slug": 1, "mediaUrl": 1, "price": 1, "status": 1}).limit(limit))

        domain = self.config.get("site", {}).get("domain", "")

        result = []
        for p in docs:
            slug = p.get("slug", "")
            url = f"https://{domain}/products/{slug}" if domain and slug else ""
            result.append({
                "_id": str(p["_id"]),
                "title": p.get("title", ""),
                "subtitle": "",
                "image1Url": p.get("mediaUrl", ""),
                "url": url,
                "created_at": "",
                "status": p.get("status", "published"),
                "price": p.get("price", ""),
            })
        return result

    def test_connection(self) -> tuple[bool, str]:
        try:
            from pymongo import MongoClient
            client = MongoClient(self.config["mongodb"]["uri"], serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            return True, "MongoDB connected"
        except Exception as e:
            return False, str(e)
