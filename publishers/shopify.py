"""Shopify Admin API 2024-01 publisher."""
import requests
from publishers.base import BasePlatformPublisher


class ShopifyPublisher(BasePlatformPublisher):
    def _headers(self):
        return {
            "X-Shopify-Access-Token": self.config["shopify"]["admin_api_token"],
            "Content-Type": "application/json",
        }

    def _base(self):
        domain = self.config["shopify"]["store_domain"].strip().lstrip("https://").lstrip("http://")
        return f"https://{domain}/admin/api/2024-01"

    def _default_blog_id(self) -> str:
        resp = requests.get(f"{self._base()}/blogs.json", headers=self._headers(), timeout=10)
        blogs = resp.json().get("blogs", [])
        return str(blogs[0]["id"]) if blogs else ""

    def fetch_posts(self, limit: int = 50) -> list[dict]:
        resp = requests.get(f"{self._base()}/blogs.json", headers=self._headers(), timeout=15)
        resp.raise_for_status()
        blogs = resp.json().get("blogs", [])
        articles = []
        for blog in blogs[:3]:
            r = requests.get(
                f"{self._base()}/blogs/{blog['id']}/articles.json",
                headers=self._headers(),
                params={"limit": min(limit, 250)},
                timeout=15,
            )
            if r.ok:
                for a in r.json().get("articles", []):
                    domain = self.config["shopify"]["store_domain"].strip().rstrip("/")
                    articles.append({
                        "_id": str(a["id"]),
                        "title": a.get("title", ""),
                        "subtitle": a.get("summary_html", ""),
                        "url": f"https://{domain}/blogs/{blog.get('handle', blog['id'])}/{a.get('handle', a['id'])}",
                        "created_at": a.get("created_at", ""),
                        "status": "published" if a.get("published_at") else "draft",
                        "blog_id": str(blog["id"]),
                    })
        return articles[:limit]

    def publish_post(self, post_data: dict) -> str:
        blog_id = post_data.pop("blog_id", self._default_blog_id())
        resp = requests.post(
            f"{self._base()}/blogs/{blog_id}/articles.json",
            headers=self._headers(),
            json={"article": post_data},
            timeout=30,
        )
        resp.raise_for_status()
        return str(resp.json()["article"]["id"])

    def update_post(self, post_id: str, update_data: dict) -> bool:
        blog_id = update_data.pop("blog_id", self._default_blog_id())
        resp = requests.put(
            f"{self._base()}/blogs/{blog_id}/articles/{post_id}.json",
            headers=self._headers(),
            json={"article": update_data},
            timeout=30,
        )
        return resp.ok

    def fetch_products(self, limit: int = 50) -> list[dict]:
        resp = requests.get(
            f"{self._base()}/products.json",
            headers=self._headers(),
            params={"limit": min(limit, 250), "status": "active"},
            timeout=20,
        )
        resp.raise_for_status()
        results = []
        domain = self.config["shopify"]["store_domain"].strip().rstrip("/")
        for p in resp.json().get("products", []):
            price = p.get("variants", [{}])[0].get("price", "") if p.get("variants") else ""
            results.append({
                "_id": str(p["id"]),
                "title": p.get("title", ""),
                "subtitle": p.get("body_html", ""),
                "image1Url": p.get("images", [{}])[0].get("src", "") if p.get("images") else "",
                "url": f"https://{domain}/products/{p.get('handle', p['id'])}",
                "created_at": p.get("created_at", ""),
                "status": p.get("status", "active"),
                "price": price,
            })
        return results

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = requests.get(f"{self._base()}/shop.json", headers=self._headers(), timeout=10)
            if resp.ok:
                shop = resp.json().get("shop", {})
                return True, f"Connected to {shop.get('name', 'Shopify store')}"
            return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)
