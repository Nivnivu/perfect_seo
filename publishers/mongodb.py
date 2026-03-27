"""MongoDB publisher — wraps the existing publisher/post_publisher.py."""
from publishers.base import BasePlatformPublisher


class MongoDBPublisher(BasePlatformPublisher):
    def fetch_posts(self, limit: int = 50) -> list[dict]:
        from publisher.mongodb_client import _get_client
        client = _get_client(self.config)
        db = client[self.config["mongodb"]["database"]]
        col = db[self.config["mongodb"]["collection"]]
        posts = list(
            col.find(
                {"type": "blogPost"},
                {"title": 1, "subtitle": 1, "image1Url": 1, "createdAt": 1},
            ).sort("createdAt", -1).limit(limit)
        )
        result = []
        for p in posts:
            created = p.get("createdAt")
            result.append({
                "_id": str(p["_id"]),
                "title": p.get("title", ""),
                "subtitle": p.get("subtitle", ""),
                "image1Url": p.get("image1Url", ""),
                "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
                "status": "published",
            })
        return result

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

    def test_connection(self) -> tuple[bool, str]:
        try:
            from pymongo import MongoClient
            client = MongoClient(self.config["mongodb"]["uri"], serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            return True, "MongoDB connected"
        except Exception as e:
            return False, str(e)
