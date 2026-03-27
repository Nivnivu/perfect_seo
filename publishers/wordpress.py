"""WordPress REST API v2 publisher."""
import requests
from publishers.base import BasePlatformPublisher


class WordPressPublisher(BasePlatformPublisher):
    def _auth(self):
        return (self.config["wordpress"]["username"], self.config["wordpress"]["app_password"])

    def _base(self):
        return self.config["wordpress"]["site_url"].rstrip("/")

    def fetch_posts(self, limit: int = 50) -> list[dict]:
        resp = requests.get(
            f"{self._base()}/wp-json/wp/v2/posts",
            auth=self._auth(),
            params={"per_page": min(limit, 100), "status": "publish"},
            timeout=20,
        )
        resp.raise_for_status()
        return [
            {
                "_id": str(p["id"]),
                "title": p.get("title", {}).get("rendered", ""),
                "subtitle": p.get("excerpt", {}).get("rendered", ""),
                "url": p.get("link", ""),
                "created_at": p.get("date", ""),
                "status": p.get("status", "publish"),
            }
            for p in resp.json()
        ]

    def publish_post(self, post_data: dict) -> str:
        resp = requests.post(
            f"{self._base()}/wp-json/wp/v2/posts",
            auth=self._auth(),
            json={
                "title": post_data.get("title", ""),
                "content": post_data.get("content", ""),
                "excerpt": post_data.get("subtitle", ""),
                "status": "publish",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return str(resp.json()["id"])

    def update_post(self, post_id: str, update_data: dict) -> bool:
        resp = requests.post(
            f"{self._base()}/wp-json/wp/v2/posts/{post_id}",
            auth=self._auth(),
            json=update_data,
            timeout=30,
        )
        return resp.ok

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = requests.get(
                f"{self._base()}/wp-json/wp/v2/users/me",
                auth=self._auth(),
                timeout=10,
            )
            if resp.ok:
                return True, f"Connected as {resp.json().get('name', 'user')}"
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            return False, str(e)
