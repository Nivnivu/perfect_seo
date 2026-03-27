"""Wix Blog API v3 publisher."""
import requests
from publishers.base import BasePlatformPublisher

_WIX_BASE = "https://www.wixapis.com"


class WixPublisher(BasePlatformPublisher):
    def _headers(self):
        return {
            "Authorization": self.config["wix"]["api_key"],
            "wix-site-id": self.config["wix"]["site_id"],
            "Content-Type": "application/json",
        }

    def fetch_posts(self, limit: int = 50) -> list[dict]:
        resp = requests.post(
            f"{_WIX_BASE}/blog/v3/posts/query",
            headers=self._headers(),
            json={"paging": {"limit": min(limit, 100)}},
            timeout=20,
        )
        resp.raise_for_status()
        posts = []
        for p in resp.json().get("posts", []):
            url_obj = p.get("url", {})
            posts.append({
                "_id": p.get("id", ""),
                "title": p.get("title", ""),
                "subtitle": p.get("excerpt", ""),
                "url": url_obj.get("base", "") + url_obj.get("path", ""),
                "created_at": p.get("firstPublishedDate", ""),
                "status": p.get("status", ""),
            })
        return posts

    def publish_post(self, post_data: dict) -> str:
        resp = requests.post(
            f"{_WIX_BASE}/blog/v3/posts",
            headers=self._headers(),
            json=post_data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["post"]["id"]

    def update_post(self, post_id: str, update_data: dict) -> bool:
        resp = requests.patch(
            f"{_WIX_BASE}/blog/v3/posts/{post_id}",
            headers=self._headers(),
            json=update_data,
            timeout=30,
        )
        return resp.ok

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = requests.post(
                f"{_WIX_BASE}/blog/v3/posts/query",
                headers=self._headers(),
                json={"paging": {"limit": 1}},
                timeout=10,
            )
            if resp.ok:
                return True, "Wix Blog API connected"
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            return False, str(e)
