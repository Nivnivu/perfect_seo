import asyncio
import os
import subprocess
import sys
import json
import re
import threading
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from api.models.pipeline import PipelineRunRequest
from api.config_manager import get_site, ROOT_DIR
from api.db import get_conn, init_db

router = APIRouter()

# In-memory process registry: run_id → subprocess.Popen
_active_runs: dict[int, subprocess.Popen] = {}

init_db()

# Modes that support manual review before publishing
_PREVIEW_SUPPORTED = {"new", "update", "recover"}


@router.post("/run")
async def run_pipeline(request: PipelineRunRequest):
    site = get_site(request.site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{request.site_id}' not found")

    config_file = site["_file"]
    site_name = site.get("site", {}).get("name", request.site_id)
    started_at = datetime.now(timezone.utc).isoformat()
    preview_mode = request.manual_publish and request.mode.value in _PREVIEW_SUPPORTED

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO pipeline_runs (site_id, site_name, mode, started_at) VALUES (?,?,?,?)",
            (request.site_id, site_name, request.mode.value, started_at),
        )
        run_id = cur.lastrowid
        conn.commit()

    async def stream():
        yield {"data": f"__RUN_ID__{run_id}"}
        yield {"data": f"▶ Starting {request.mode.value} pipeline — {site_name}"}
        if preview_mode:
            yield {"data": "  Mode: Manual review — content will appear in Reviews tab before publishing"}
        yield {"data": f"  Config: {config_file}"}
        yield {"data": "─" * 52}

        cmd = [sys.executable, "run.py", request.mode.value, "--config", config_file]
        if request.keywords:
            cmd += ["--keywords", ",".join(request.keywords)]

        env = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "PIPELINE_PREVIEW_MODE": "1" if preview_mode else "0",
        }
        log_tail: list[str] = []
        review_buffer = ""
        in_review_json = False
        exit_code_ref = [1]

        # Use a thread + asyncio.Queue so subprocess streaming works on Windows
        # (asyncio.create_subprocess_exec requires ProactorEventLoop on Windows,
        # but uvicorn creates the event loop before main.py is imported, so the
        # policy fix in main.py arrives too late)
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _run_subprocess():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(ROOT_DIR),
                    env=env,
                )
                _active_runs[run_id] = proc
                for raw in proc.stdout:
                    line = raw.decode("utf-8", errors="replace").rstrip()
                    if line:
                        loop.call_soon_threadsafe(queue.put_nowait, line)
                proc.wait()
                exit_code_ref[0] = proc.returncode if proc.returncode is not None else 1
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, f"[ERROR] Failed to start process: {e}")
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

        threading.Thread(target=_run_subprocess, daemon=True).start()

        try:
            while True:
                line = await queue.get()
                if line is None:
                    break

                # Detect start of review JSON block
                if "__REVIEW_JSON__" in line:
                    in_review_json = True
                    review_buffer = line
                    if "__REVIEW_END__" in line:
                        in_review_json = False
                        review_id = _save_review(review_buffer, request.site_id, request.mode.value)
                        if review_id:
                            yield {"data": f"__REVIEW_READY__{review_id}"}
                            yield {"data": f"  ✅ Review #{review_id} ready — open the Reviews tab to edit and publish"}
                        review_buffer = ""
                    continue

                if in_review_json:
                    review_buffer += "\n" + line
                    if "__REVIEW_END__" in line:
                        in_review_json = False
                        review_id = _save_review(review_buffer, request.site_id, request.mode.value)
                        if review_id:
                            yield {"data": f"__REVIEW_READY__{review_id}"}
                            yield {"data": f"  ✅ Review #{review_id} ready — open the Reviews tab to edit and publish"}
                        review_buffer = ""
                    continue

                log_tail.append(line)
                if len(log_tail) > 10:
                    log_tail.pop(0)
                yield {"data": line}

        finally:
            _active_runs.pop(run_id, None)
            finished_at = datetime.now(timezone.utc).isoformat()
            log_preview = "\n".join(log_tail)[:500]
            with get_conn() as conn:
                conn.execute(
                    "UPDATE pipeline_runs SET finished_at=?, exit_code=?, log_preview=? WHERE id=?",
                    (finished_at, exit_code_ref[0], log_preview, run_id),
                )
                conn.commit()

        yield {"data": f"__EXIT__{exit_code_ref[0]}"}

    return EventSourceResponse(stream())


def _save_review(raw: str, site_id: str, mode: str) -> int | None:
    """Parse __REVIEW_JSON__....__REVIEW_END__ block and write to pending_reviews."""
    try:
        match = re.search(r"__REVIEW_JSON__(.*?)__REVIEW_END__", raw, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(1).strip())

        from publisher.markdown_to_html import markdown_to_html
        body_markdown = data.get("body_markdown", "")
        body_html = markdown_to_html(body_markdown) if body_markdown else ""

        created_at = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO pending_reviews
                   (site_id, mode, status, title, subtitle, body_html, body_markdown,
                    image_base64, topic, post_id, original_title, original_body,
                    subtitle_only, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    site_id, mode, "pending",
                    data.get("title", ""),
                    data.get("subtitle", ""),
                    body_html,
                    body_markdown,
                    data.get("image_base64"),
                    data.get("topic", ""),
                    data.get("post_id"),
                    data.get("original_title"),
                    data.get("original_body"),
                    1 if data.get("subtitle_only") else 0,
                    created_at,
                ),
            )
            review_id = cur.lastrowid
            conn.commit()
        return review_id
    except Exception as e:
        print(f"[reviews] Failed to save review: {e}", flush=True)
        return None


@router.delete("/run/{run_id}")
async def abort_pipeline(run_id: int):
    process = _active_runs.pop(run_id, None)
    if not process:
        raise HTTPException(status_code=404, detail="No active pipeline with that ID")
    try:
        process.terminate()
    except Exception:
        pass
    finished_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE pipeline_runs SET finished_at=?, exit_code=-1 WHERE id=?",
            (finished_at, run_id),
        )
        conn.commit()
    return {"status": "aborted", "run_id": run_id}


@router.get("/history")
async def get_history(site_id: str | None = None, limit: int = 20):
    with get_conn() as conn:
        if site_id:
            rows = conn.execute(
                "SELECT * FROM pipeline_runs WHERE site_id=? ORDER BY id DESC LIMIT ?",
                (site_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]
