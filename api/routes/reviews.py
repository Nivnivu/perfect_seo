"""Pending reviews — generated content awaiting human approval before publishing."""
import asyncio
import json
import uuid
import html.parser
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.db import get_conn, init_db
from api.config_manager import get_site

router = APIRouter()
init_db()


# ── Pydantic models ──────────────────────────────────────────────────────────

class PublishPayload(BaseModel):
    title: str
    subtitle: str
    body_html: str


class RefinePayload(BaseModel):
    instruction: str
    body_html: str


# ── HTML → blog-poster TipTap JSON ───────────────────────────────────────────

def _uid() -> str:
    return f"_{uuid.uuid4().hex[:10]}"


class _HtmlToTipTap(html.parser.HTMLParser):
    """Convert simple HTML to blog-poster TipTap JSON (type/children schema)."""

    def __init__(self):
        super().__init__()
        self.nodes: list[dict] = []
        self._stack: list[dict] = []
        self._current_text: list[str] = []
        self._inline_marks: list[str] = []  # 'strong', 'em'
        self._pending_href: str | None = None

    def _flush_text(self):
        text = "".join(self._current_text).strip()
        self._current_text = []
        if not text:
            return None
        node = {"type": "text", "content": text}
        if "strong" in self._inline_marks and "em" in self._inline_marks:
            return {"type": "strong", "children": [{"type": "em", "children": [node]}]}
        if "strong" in self._inline_marks:
            return {"type": "strong", "children": [node]}
        if "em" in self._inline_marks:
            return {"type": "em", "children": [node]}
        return node

    def handle_starttag(self, tag: str, attrs):
        attr_dict = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "p", "li"):
            block = {"type": tag, "attributes": {"dir": "auto", "data-uid": _uid()}, "children": []}
            self._stack.append(block)
        elif tag == "ul":
            self._stack.append({"type": "ul", "attributes": {"data-uid": _uid()}, "children": []})
        elif tag == "ol":
            self._stack.append({"type": "ol", "attributes": {"data-uid": _uid()}, "children": []})
        elif tag == "strong" or tag == "b":
            self._inline_marks.append("strong")
        elif tag == "em" or tag == "i":
            self._inline_marks.append("em")
        elif tag == "a":
            self._pending_href = attr_dict.get("href", "#")
        elif tag == "br":
            if self._stack:
                t = self._flush_text()
                if t:
                    self._stack[-1]["children"].append(t)
                self._stack[-1]["children"].append({"type": "text", "content": "\n"})

    def handle_endtag(self, tag: str):
        if tag in ("strong", "b"):
            if "strong" in self._inline_marks:
                self._inline_marks.remove("strong")
        elif tag in ("em", "i"):
            if "em" in self._inline_marks:
                self._inline_marks.remove("em")
        elif tag == "a":
            text = "".join(self._current_text).strip()
            self._current_text = []
            if text and self._stack:
                self._stack[-1]["children"].append({
                    "type": "a",
                    "attributes": {"href": self._pending_href or "#"},
                    "children": [{"type": "text", "content": text}],
                })
            self._pending_href = None
        elif tag in ("h1", "h2", "h3", "h4", "p", "li"):
            t = self._flush_text()
            if t and self._stack:
                self._stack[-1]["children"].append(t)
            if self._stack:
                block = self._stack.pop()
                if self._stack and self._stack[-1]["type"] in ("ul", "ol"):
                    self._stack[-1]["children"].append(block)
                else:
                    self.nodes.append(block)
        elif tag in ("ul", "ol"):
            t = self._flush_text()
            if t and self._stack:
                self._stack[-1]["children"].append(t)
            if self._stack:
                block = self._stack.pop()
                self.nodes.append(block)

    def handle_data(self, data: str):
        self._current_text.append(data)

    def result(self) -> str:
        # Flush any remaining text
        if self._current_text:
            text = "".join(self._current_text).strip()
            if text:
                self.nodes.append({"type": "p", "attributes": {"dir": "auto", "data-uid": _uid()}, "children": [{"type": "text", "content": text}]})
        return json.dumps({"type": "body", "children": self.nodes}, ensure_ascii=False)


def html_to_tiptap_json(html_content: str) -> str:
    parser = _HtmlToTipTap()
    parser.feed(html_content or "")
    return parser.result()


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
def list_reviews(status: str = "pending", site_id: str | None = None):
    with get_conn() as conn:
        if site_id:
            rows = conn.execute(
                "SELECT id,site_id,mode,status,title,subtitle,topic,post_id,subtitle_only,created_at,published_at "
                "FROM pending_reviews WHERE status=? AND site_id=? ORDER BY id DESC",
                (status, site_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id,site_id,mode,status,title,subtitle,topic,post_id,subtitle_only,created_at,published_at "
                "FROM pending_reviews WHERE status=? ORDER BY id DESC",
                (status,),
            ).fetchall()
    return [dict(r) for r in rows]


@router.get("/count")
def pending_count():
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as n FROM pending_reviews WHERE status='pending'").fetchone()
    return {"count": row["n"] if row else 0}


@router.get("/{review_id}")
def get_review(review_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM pending_reviews WHERE id=?", (review_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    return dict(row)


@router.post("/{review_id}/publish")
async def publish_review(review_id: int, payload: PublishPayload):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM pending_reviews WHERE id=?", (review_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    review = dict(row)
    if review["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Review is already {review['status']}")

    site = get_site(review["site_id"])
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{review['site_id']}' not found")

    def _publish():
        from publishers.factory import get_publisher
        publisher = get_publisher(site)
        platform = site.get("platform", "mongodb")

        # Convert body_html to platform-appropriate format
        if platform == "mongodb":
            body_content = html_to_tiptap_json(payload.body_html)
        else:
            body_content = payload.body_html  # HTML works for WP, Shopify, WooCommerce, Wix

        post_data = {
            "title": payload.title,
            "subtitle": payload.subtitle,
            "body_html": payload.body_html,
            "body_content": body_content,  # platform-formatted body
            "platform": platform,
        }

        if review.get("post_id"):
            # Update existing post (update mode)
            update_data = {
                "title": payload.title,
                "subtitle": payload.subtitle,
            }
            if not review.get("subtitle_only"):
                update_data["body"] = body_content
            publisher.update_post(review["post_id"], update_data)
            return review["post_id"]
        else:
            # Publish new post
            return publisher.publish_post(post_data)

    try:
        post_id = await asyncio.to_thread(_publish)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    published_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE pending_reviews SET status='published', post_id=?, published_at=? WHERE id=?",
            (str(post_id), published_at, review_id),
        )
        conn.commit()

    return {"status": "published", "post_id": str(post_id)}


@router.post("/{review_id}/reject")
def reject_review(review_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM pending_reviews WHERE id=?", (review_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Review not found")
        conn.execute("UPDATE pending_reviews SET status='rejected' WHERE id=?", (review_id,))
        conn.commit()
    return {"status": "rejected"}


@router.post("/{review_id}/refine")
async def refine_review(review_id: int, payload: RefinePayload):
    with get_conn() as conn:
        row = conn.execute("SELECT site_id FROM pending_reviews WHERE id=?", (review_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")

    site = get_site(row["site_id"])
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    def _refine():
        from generator.refine import refine_content
        return refine_content(payload.body_html, payload.instruction, site)

    try:
        refined_html = await asyncio.to_thread(_refine)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refine failed: {e}")

    return {"body_html": refined_html}
