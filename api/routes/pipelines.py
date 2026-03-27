import asyncio
import os
import sys
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from api.models.pipeline import PipelineRunRequest
from api.config_manager import get_site, ROOT_DIR
from api.db import get_conn, init_db

router = APIRouter()

# In-memory process registry: run_id → asyncio subprocess
_active_runs: dict[int, asyncio.subprocess.Process] = {}

init_db()


@router.post("/run")
async def run_pipeline(request: PipelineRunRequest):
    site = get_site(request.site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{request.site_id}' not found")

    config_file = site["_file"]
    site_name = site.get("site", {}).get("name", request.site_id)
    started_at = datetime.now(timezone.utc).isoformat()

    # Create DB record first so we get a run_id before streaming begins
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
        yield {"data": f"  Config: {config_file}"}
        yield {"data": "─" * 52}

        cmd = [sys.executable, "run.py", request.mode.value, "--config", config_file]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        exit_code = 1
        log_tail: list[str] = []

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(ROOT_DIR),
                env=env,
            )
            _active_runs[run_id] = process

            async for raw_line in process.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                if line:
                    log_tail.append(line)
                    if len(log_tail) > 10:
                        log_tail.pop(0)
                    yield {"data": line}

            await process.wait()
            exit_code = process.returncode if process.returncode is not None else 1

        except Exception as e:
            yield {"data": f"[ERROR] Failed to start process: {e}"}
            exit_code = 1
        finally:
            _active_runs.pop(run_id, None)
            finished_at = datetime.now(timezone.utc).isoformat()
            log_preview = "\n".join(log_tail)[:500]
            with get_conn() as conn:
                conn.execute(
                    "UPDATE pipeline_runs SET finished_at=?, exit_code=?, log_preview=? WHERE id=?",
                    (finished_at, exit_code, log_preview, run_id),
                )
                conn.commit()

        yield {"data": f"__EXIT__{exit_code}"}

    return EventSourceResponse(stream())


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
