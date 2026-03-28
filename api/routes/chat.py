"""
AI Chat with tool calling — exposes all SEO Blog Engine capabilities to an LLM.
Supports Anthropic, OpenAI (+ DeepSeek), and Gemini providers.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.config_manager import get_site, list_sites as _list_sites, ROOT_DIR
from api.db import get_conn

router = APIRouter()

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an SEO automation assistant with full control over the SEO Blog Engine.\n\n"
    "You have tools to:\n"
    "- List configured sites and their details\n"
    "- Run SEO content pipelines (new posts, updates, recovery, images, diagnostics, etc.)\n"
    "- Manage the content review queue (view, publish, or reject pending reviews)\n"
    "- Create and manage automated schedules for recurring pipeline runs\n"
    "- Fetch Google Search Console performance data and SEO opportunities\n"
    "- Browse posts and products from connected CMS platforms\n\n"
    "Guidelines:\n"
    "- Always prefer manual_publish=true when running content pipelines — let the user review before publishing\n"
    "- Be concise and specific; show key numbers when available\n"
    "- When creating schedules, always use a descriptive label and explain the cron timing clearly\n"
    "- If asked to delete or reject something, confirm the action in your response\n"
    "- If GSC is not configured or authenticated for a site, mention it"
)

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic input_schema format — converted per provider)
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "list_sites",
        "description": "List all configured sites with their platform, domain, language, and GSC status.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_pipeline",
        "description": (
            "Start an SEO pipeline for a site. Runs in the background and returns a run ID immediately.\n"
            "Modes:\n"
            "  new — generate a new blog post\n"
            "  update — rewrite existing posts based on GSC data\n"
            "  full — new + update in one run\n"
            "  recover — restore posts that lost rankings\n"
            "  images — scan all posts and fix/generate missing or low-quality images\n"
            "  diagnose — show site health statistics\n"
            "  dedupe — detect duplicate content\n"
            "  impact — content performance report\n"
            "  static — update static pages\n"
            "  products — update product descriptions\n"
            "  restore_titles — restore original post titles"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string", "description": "Site ID"},
                "mode": {
                    "type": "string",
                    "enum": ["new", "update", "full", "recover", "images", "diagnose",
                             "dedupe", "impact", "static", "products", "restore_titles"],
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional seed keywords (useful for new/update/full modes)",
                },
                "manual_publish": {
                    "type": "boolean",
                    "description": "Send generated content to the review queue before publishing. Strongly recommended: true.",
                },
            },
            "required": ["site_id", "mode"],
        },
    },
    {
        "name": "get_pipeline_history",
        "description": "Get recent pipeline run history with status and exit codes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string", "description": "Filter by site (optional)"},
                "limit": {"type": "integer", "description": "Number of runs (default 10)"},
            },
        },
    },
    {
        "name": "list_posts",
        "description": "List blog posts for a site from its connected CMS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string"},
                "limit": {"type": "integer", "description": "Default 20"},
            },
            "required": ["site_id"],
        },
    },
    {
        "name": "list_pending_reviews",
        "description": "List all pending content reviews waiting for human approval before publishing.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "publish_review",
        "description": "Publish a pending content review directly to the site CMS.",
        "input_schema": {
            "type": "object",
            "properties": {"review_id": {"type": "integer"}},
            "required": ["review_id"],
        },
    },
    {
        "name": "reject_review",
        "description": "Reject and permanently discard a pending content review.",
        "input_schema": {
            "type": "object",
            "properties": {"review_id": {"type": "integer"}},
            "required": ["review_id"],
        },
    },
    {
        "name": "list_schedules",
        "description": "List all automated pipeline schedules with cron expressions and next run times.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "create_schedule",
        "description": (
            "Create an automated schedule to run a pipeline on a cron schedule.\n"
            "Cron format (5 fields): minute hour day month weekday\n"
            "Examples: '0 9 * * 1' = Monday 9am, '0 9 * * *' = daily 9am, '0 9 1 * *' = 1st of month 9am"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string"},
                "mode": {"type": "string"},
                "cron_expr": {"type": "string", "description": "5-field cron expression"},
                "label": {"type": "string", "description": "Human-readable name"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "manual_publish": {"type": "boolean"},
            },
            "required": ["site_id", "mode", "cron_expr"],
        },
    },
    {
        "name": "delete_schedule",
        "description": "Permanently delete an automated schedule.",
        "input_schema": {
            "type": "object",
            "properties": {"schedule_id": {"type": "integer"}},
            "required": ["schedule_id"],
        },
    },
    {
        "name": "toggle_schedule",
        "description": "Enable or disable an existing schedule without deleting it.",
        "input_schema": {
            "type": "object",
            "properties": {"schedule_id": {"type": "integer"}},
            "required": ["schedule_id"],
        },
    },
    {
        "name": "get_gsc_summary",
        "description": (
            "Fetch Google Search Console performance data: total clicks, impressions, average position, "
            "and SEO opportunities (page-2 posts that can reach page 1, low-CTR posts)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string"},
                "days": {"type": "integer", "description": "Lookback window (default 28)"},
            },
            "required": ["site_id"],
        },
    },
]

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    site_id: Optional[str] = None       # use this site's LLM config
    provider: Optional[str] = None      # override provider
    api_key: Optional[str] = None       # override api key
    model: Optional[str] = None         # override model


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("")
async def chat(request: ChatRequest):
    try:
        config = _resolve_config(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    msgs = [{"role": m.role, "content": m.content} for m in request.messages]

    async def stream():
        try:
            async for event in _agentic_loop(msgs, config):
                yield {"data": json.dumps(event, ensure_ascii=False)}
        except Exception as exc:
            yield {"data": json.dumps({"type": "error", "message": str(exc)})}

    return EventSourceResponse(stream())


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4.1",
    "gemini": "gemini-2.5-flash",
    "mistral": "mistral-large-latest",
    "deepseek": "deepseek-chat",
}


def _resolve_config(request: ChatRequest) -> dict:
    if request.api_key and request.provider:
        return {
            "provider": request.provider,
            "api_key": request.api_key,
            "model": request.model or _DEFAULT_MODELS.get(request.provider, "gpt-4.1"),
        }

    if request.site_id:
        site = get_site(request.site_id)
        if site:
            for provider in ("anthropic", "openai", "gemini", "mistral", "deepseek"):
                if provider in site:
                    cfg = site[provider]
                    return {
                        "provider": provider,
                        "api_key": cfg.get("api_key", ""),
                        "model": cfg.get("model") or _DEFAULT_MODELS[provider],
                    }

    raise ValueError(
        "No LLM configuration found. Select a site or provide a provider + API key."
    )


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------


async def _agentic_loop(messages: list[dict], config: dict) -> AsyncGenerator:
    provider = config["provider"]
    # Each provider maintains its own conversation history format
    state: dict = {"messages": list(messages)}

    for _iteration in range(10):
        if provider == "anthropic":
            result = await asyncio.to_thread(_call_anthropic, state["messages"], config)
        elif provider in ("openai", "deepseek"):
            result = await asyncio.to_thread(_call_openai, state["messages"], config)
        elif provider == "gemini":
            result = await asyncio.to_thread(_call_gemini, state["messages"], config)
        else:
            yield {"type": "error", "message": f"Unsupported provider '{provider}'. Use anthropic, openai, gemini, or deepseek."}
            return

        if result.get("error"):
            yield {"type": "error", "message": result["error"]}
            return

        if result.get("has_tool_calls"):
            tool_calls: list[dict] = result["tool_calls"]
            tool_results: list[dict] = []

            for tc in tool_calls:
                yield {"type": "tool_start", "name": tc["name"], "args": tc["args"]}
                tr = await _execute_tool(tc["name"], tc["args"])
                yield {"type": "tool_done", "name": tc["name"], "result": tr}
                tool_results.append({"tc": tc, "result": tr})

            # Append provider-specific history entries
            if provider == "anthropic":
                state["messages"].append({"role": "assistant", "content": result["raw_content"]})
                state["messages"].append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tr["tc"]["id"],
                            "content": json.dumps(tr["result"], ensure_ascii=False, default=str),
                        }
                        for tr in tool_results
                    ],
                })

            elif provider in ("openai", "deepseek"):
                state["messages"].append(result["assistant_msg"])
                for tr in tool_results:
                    state["messages"].append({
                        "role": "tool",
                        "tool_call_id": tr["tc"]["id"],
                        "content": json.dumps(tr["result"], ensure_ascii=False, default=str),
                    })

            elif provider == "gemini":
                # Gemini: add model's function_call parts, then user's function_response parts
                state["messages"].append({"role": "model", "parts": result["model_parts"]})
                state["messages"].append({
                    "role": "user",
                    "parts": [
                        {
                            "_gemini_fn_response": True,
                            "name": tr["tc"]["name"],
                            "response": tr["result"],
                        }
                        for tr in tool_results
                    ],
                })

        else:
            # Final text — stream in small chunks
            text: str = result.get("text", "")
            chunk = 25
            for i in range(0, len(text), chunk):
                yield {"type": "text", "delta": text[i: i + chunk]}
                await asyncio.sleep(0.006)
            yield {"type": "done"}
            return

    yield {"type": "error", "message": "Reached maximum tool call depth (10 iterations)."}


# ---------------------------------------------------------------------------
# Provider call functions (synchronous — run via asyncio.to_thread)
# ---------------------------------------------------------------------------


def _anthropic_tools() -> list[dict]:
    return TOOLS  # already in Anthropic's format


def _openai_tools() -> list[dict]:
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in TOOLS
    ]


def _call_anthropic(messages: list[dict], config: dict) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config["api_key"])
        resp = client.messages.create(
            model=config["model"],
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=_anthropic_tools(),
            messages=messages,
        )
        if resp.stop_reason == "tool_use":
            tool_calls = [
                {"id": b.id, "name": b.name, "args": b.input}
                for b in resp.content if b.type == "tool_use"
            ]
            return {
                "has_tool_calls": True,
                "tool_calls": tool_calls,
                "raw_content": [b.model_dump() for b in resp.content],
            }
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return {"has_tool_calls": False, "text": text}
    except Exception as exc:
        return {"error": str(exc)}


def _call_openai(messages: list[dict], config: dict) -> dict:
    try:
        import openai
        kw = {"base_url": "https://api.deepseek.com/v1"} if config["provider"] == "deepseek" else {}
        client = openai.OpenAI(api_key=config["api_key"], **kw)
        resp = client.chat.completions.create(
            model=config["model"],
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=_openai_tools(),
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            tool_calls = [
                {"id": tc.id, "name": tc.function.name, "args": json.loads(tc.function.arguments)}
                for tc in msg.tool_calls
            ]
            return {
                "has_tool_calls": True,
                "tool_calls": tool_calls,
                "assistant_msg": {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                },
            }
        return {"has_tool_calls": False, "text": msg.content or ""}
    except Exception as exc:
        return {"error": str(exc)}


def _call_gemini(messages: list[dict], config: dict) -> dict:
    try:
        import google.generativeai as genai
        import google.generativeai.types as gtypes

        genai.configure(api_key=config["api_key"])

        # Build Gemini function declarations
        fn_decls = [
            gtypes.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters={k: v for k, v in t["input_schema"].items() if k != "required"},
            )
            for t in TOOLS
        ]
        gemini_tools = gtypes.Tool(function_declarations=fn_decls)

        model = genai.GenerativeModel(
            config["model"],
            tools=[gemini_tools],
            system_instruction=SYSTEM_PROMPT,
        )

        # Convert messages to Gemini Content format
        gemini_msgs = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            parts = msg.get("parts") or msg.get("content")

            if isinstance(parts, str):
                gemini_msgs.append({"role": role, "parts": [parts]})
            elif isinstance(parts, list):
                converted = []
                for part in parts:
                    if isinstance(part, str):
                        converted.append(part)
                    elif isinstance(part, dict) and part.get("_gemini_fn_response"):
                        converted.append(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=part["name"],
                                    response={"result": json.dumps(part["response"], default=str)},
                                )
                            )
                        )
                    else:
                        converted.append(str(part))
                gemini_msgs.append({"role": role, "parts": converted})

        resp = model.generate_content(gemini_msgs)

        # Check for function calls in response
        tool_calls = []
        model_parts = []
        for part in resp.candidates[0].content.parts:
            model_parts.append(part)
            if hasattr(part, "function_call") and part.function_call.name:
                args = {k: v for k, v in part.function_call.args.items()}
                tool_calls.append({
                    "id": part.function_call.name,
                    "name": part.function_call.name,
                    "args": args,
                })

        if tool_calls:
            return {"has_tool_calls": True, "tool_calls": tool_calls, "model_parts": model_parts}

        return {"has_tool_calls": False, "text": resp.text}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------


async def _execute_tool(name: str, args: dict) -> dict:
    try:
        if name == "list_sites":
            return {"sites": _list_sites()}
        elif name == "run_pipeline":
            return await _t_run_pipeline(**args)
        elif name == "get_pipeline_history":
            return _t_pipeline_history(args.get("site_id"), args.get("limit", 10))
        elif name == "list_posts":
            return await _t_list_posts(args["site_id"], args.get("limit", 20))
        elif name == "list_pending_reviews":
            return _t_list_reviews()
        elif name == "publish_review":
            return await _t_publish_review(args["review_id"])
        elif name == "reject_review":
            return _t_reject_review(args["review_id"])
        elif name == "list_schedules":
            return _t_list_schedules()
        elif name == "create_schedule":
            return _t_create_schedule(**args)
        elif name == "delete_schedule":
            return _t_delete_schedule(args["schedule_id"])
        elif name == "toggle_schedule":
            return _t_toggle_schedule(args["schedule_id"])
        elif name == "get_gsc_summary":
            return await _t_gsc_summary(args["site_id"], args.get("days", 28))
        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        return {"error": f"Tool '{name}' failed: {exc}"}


# -- Individual tool implementations --

async def _t_run_pipeline(site_id: str, mode: str, keywords: list = None, manual_publish: bool = True) -> dict:
    site = get_site(site_id)
    if not site:
        return {"error": f"Site '{site_id}' not found"}

    config_file = site["_file"]
    site_name = site.get("site", {}).get("name", site_id)
    started_at = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO pipeline_runs (site_id, site_name, mode, started_at) VALUES (?,?,?,?)",
            (site_id, site_name, mode, started_at),
        )
        run_id = cur.lastrowid
        conn.commit()

    cmd = [sys.executable, "run.py", mode, "--config", config_file]
    if keywords:
        cmd += ["--keywords", ",".join(keywords)]

    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PIPELINE_PREVIEW_MODE": "1" if manual_publish else "0",
    }

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=str(ROOT_DIR),
            env=env,
        )
        asyncio.ensure_future(_track_process(run_id, process))
        return {
            "run_id": run_id,
            "status": "started",
            "site": site_name,
            "mode": mode,
            "manual_publish": manual_publish,
            "note": "Content will appear in the Reviews queue when ready." if manual_publish else "Content will publish automatically.",
        }
    except Exception as exc:
        return {"error": f"Failed to start pipeline: {exc}"}


async def _track_process(run_id: int, process: asyncio.subprocess.Process) -> None:
    await process.wait()
    finished_at = datetime.now(timezone.utc).isoformat()
    exit_code = process.returncode if process.returncode is not None else 1
    with get_conn() as conn:
        conn.execute(
            "UPDATE pipeline_runs SET finished_at=?, exit_code=? WHERE id=?",
            (finished_at, exit_code, run_id),
        )
        conn.commit()


def _t_pipeline_history(site_id: str | None, limit: int) -> dict:
    with get_conn() as conn:
        if site_id:
            rows = conn.execute(
                "SELECT id,site_id,site_name,mode,started_at,finished_at,exit_code FROM pipeline_runs WHERE site_id=? ORDER BY id DESC LIMIT ?",
                (site_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id,site_id,site_name,mode,started_at,finished_at,exit_code FROM pipeline_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return {"runs": [dict(r) for r in rows]}


async def _t_list_posts(site_id: str, limit: int) -> dict:
    site = get_site(site_id)
    if not site:
        return {"error": f"Site '{site_id}' not found"}

    def _fetch():
        from publishers.factory import get_publisher
        posts = get_publisher(site).fetch_posts(limit=limit) or []
        return [
            {
                "id": str(p.get("id") or p.get("_id") or ""),
                "title": str(p.get("title", ""))[:120],
                "status": p.get("status", ""),
                "date": str(p.get("date") or p.get("createdAt", "")),
            }
            for p in posts
        ]

    try:
        posts = await asyncio.to_thread(_fetch)
        return {"posts": posts, "count": len(posts)}
    except Exception as exc:
        return {"error": str(exc)}


def _t_list_reviews() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,site_id,mode,title,topic,subtitle_only,created_at FROM pending_reviews WHERE status='pending' ORDER BY id DESC"
        ).fetchall()
    return {"reviews": [dict(r) for r in rows], "count": len(rows)}


async def _t_publish_review(review_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM pending_reviews WHERE id=? AND status='pending'", (review_id,)
        ).fetchone()
    if not row:
        return {"error": f"Review #{review_id} not found or already processed"}

    review = dict(row)
    site = get_site(review["site_id"])
    if not site:
        return {"error": f"Site '{review['site_id']}' not found"}

    def _publish():
        from publishers.factory import get_publisher
        pub = get_publisher(site)
        body = review.get("body_html") or ""
        if site.get("platform", "mongodb") == "mongodb":
            from api.routes.reviews import html_to_tiptap_json
            body = html_to_tiptap_json(body)
        if review.get("post_id"):
            return pub.update_post(review["post_id"], {"title": review["title"], "subtitle": review["subtitle"], "body": body})
        return pub.publish_post({"title": review["title"], "subtitle": review["subtitle"], "body": body, "image_base64": None})

    try:
        await asyncio.to_thread(_publish)
        with get_conn() as conn:
            conn.execute(
                "UPDATE pending_reviews SET status='published', published_at=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), review_id),
            )
            conn.commit()
        return {"published": True, "review_id": review_id, "title": review["title"]}
    except Exception as exc:
        return {"error": str(exc)}


def _t_reject_review(review_id: int) -> dict:
    with get_conn() as conn:
        if not conn.execute("SELECT id FROM pending_reviews WHERE id=?", (review_id,)).fetchone():
            return {"error": f"Review #{review_id} not found"}
        conn.execute("UPDATE pending_reviews SET status='rejected' WHERE id=?", (review_id,))
        conn.commit()
    return {"rejected": True, "review_id": review_id}


def _t_list_schedules() -> dict:
    from api.scheduler import next_run
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM schedules ORDER BY id DESC").fetchall()
    schedules = []
    for row in rows:
        d = dict(row)
        d["keywords"] = json.loads(d.get("keywords") or "[]")
        d["next_run_at"] = next_run(d["id"])
        schedules.append(d)
    return {"schedules": schedules, "count": len(schedules)}


def _t_create_schedule(site_id: str, mode: str, cron_expr: str, label: str = None, keywords: list = None, manual_publish: bool = False) -> dict:
    site = get_site(site_id)
    if not site:
        return {"error": f"Site '{site_id}' not found"}

    label = label or f"{mode} — {site_id}"
    created_at = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO schedules (site_id, mode, cron_expr, label, keywords, manual_publish, enabled, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (site_id, mode, cron_expr, label, json.dumps(keywords or []), 1 if manual_publish else 0, 1, created_at),
        )
        schedule_id = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()

    from api.scheduler import upsert_job
    upsert_job(dict(row))
    return {"created": True, "schedule_id": schedule_id, "label": label, "cron_expr": cron_expr}


def _t_delete_schedule(schedule_id: int) -> dict:
    with get_conn() as conn:
        if not conn.execute("SELECT id FROM schedules WHERE id=?", (schedule_id,)).fetchone():
            return {"error": f"Schedule #{schedule_id} not found"}
        conn.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
        conn.execute("DELETE FROM schedule_runs WHERE schedule_id=?", (schedule_id,))
        conn.commit()
    from api.scheduler import remove_job
    remove_job(schedule_id)
    return {"deleted": True, "schedule_id": schedule_id}


def _t_toggle_schedule(schedule_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
        if not row:
            return {"error": f"Schedule #{schedule_id} not found"}
        new_enabled = 0 if row["enabled"] else 1
        conn.execute("UPDATE schedules SET enabled=? WHERE id=?", (new_enabled, schedule_id))
        conn.commit()
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    from api.scheduler import upsert_job
    upsert_job(dict(row))
    return {"toggled": True, "schedule_id": schedule_id, "enabled": bool(new_enabled)}


async def _t_gsc_summary(site_id: str, days: int) -> dict:
    site = get_site(site_id)
    if not site:
        return {"error": f"Site '{site_id}' not found"}

    gsc = site.get("search_console")
    if not gsc:
        return {"configured": False, "message": "GSC not configured for this site"}

    token_file = gsc.get("token_file", "gsc_token.json")
    if not (ROOT_DIR / token_file).exists():
        return {"configured": True, "authenticated": False, "message": "GSC token not found — please authorize first"}

    def _fetch():
        sys.path.insert(0, str(ROOT_DIR))
        from tools.search_console import fetch_gsc_performance
        return fetch_gsc_performance(site, days=days)

    try:
        perf = await asyncio.to_thread(_fetch)
        if not perf:
            return {"configured": True, "authenticated": True, "data": None}

        total_clicks = int(sum(v["clicks"] for v in perf.values()))
        total_impr = int(sum(v["impressions"] for v in perf.values()))
        positions = [v["position"] for v in perf.values() if v.get("position")]
        avg_pos = round(sum(positions) / len(positions), 1) if positions else 0
        top10 = sorted(perf.items(), key=lambda x: x[1]["clicks"], reverse=True)[:10]
        page2 = [u for u, d in perf.items() if 11 <= d.get("position", 999) <= 30 and d.get("impressions", 0) >= 20][:15]
        low_ctr = [u for u, d in perf.items() if d.get("position", 999) <= 10 and d.get("ctr", 1) * 100 < 3 and d.get("impressions", 0) >= 50][:15]

        return {
            "configured": True,
            "authenticated": True,
            "data": {
                "summary": {"total_clicks": total_clicks, "total_impressions": total_impr, "avg_position": avg_pos, "pages_tracked": len(perf), "days": days},
                "top_pages": [{"url": u, "clicks": int(d["clicks"]), "position": round(d["position"], 1)} for u, d in top10],
                "opportunities": {"page2": page2, "low_ctr": low_ctr},
            },
        }
    except Exception as exc:
        return {"error": str(exc)}
