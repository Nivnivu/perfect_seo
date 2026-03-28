from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
import json
from pathlib import Path

from api.db import get_conn
from api.config_manager import get_site

router = APIRouter()

_VALID_MODES = {
    "new", "update", "full", "static", "recover",
    "diagnose", "dedupe", "impact", "images", "products", "restore_titles",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ScheduleCreate(BaseModel):
    site_id: str
    mode: str
    cron_expr: str
    label: Optional[str] = None
    keywords: Optional[list[str]] = None
    manual_publish: bool = False
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    mode: Optional[str] = None
    cron_expr: Optional[str] = None
    label: Optional[str] = None
    keywords: Optional[list[str]] = None
    manual_publish: Optional[bool] = None
    enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_cron(expr: str) -> None:
    parts = expr.strip().split()
    if len(parts) != 5:
        raise HTTPException(
            status_code=400,
            detail="Cron expression must have exactly 5 fields: minute hour day month weekday",
        )


def _row_to_dict(row, include_next_run: bool = True) -> dict:
    from api.scheduler import next_run
    d = dict(row)
    d["keywords"] = json.loads(d.get("keywords") or "[]")
    d["next_run_at"] = next_run(d["id"]) if include_next_run else None
    return d


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
async def list_schedules():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM schedules ORDER BY id DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.post("")
async def create_schedule(body: ScheduleCreate):
    if not get_site(body.site_id):
        raise HTTPException(status_code=404, detail=f"Site '{body.site_id}' not found")
    if body.mode not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Unknown mode '{body.mode}'")
    _validate_cron(body.cron_expr)

    label = body.label or f"{body.mode} — {body.site_id}"
    created_at = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO schedules
               (site_id, mode, cron_expr, label, keywords, manual_publish, enabled, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                body.site_id, body.mode, body.cron_expr, label,
                json.dumps(body.keywords or []),
                1 if body.manual_publish else 0,
                1 if body.enabled else 0,
                created_at,
            ),
        )
        schedule_id = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()

    schedule = _row_to_dict(row, include_next_run=False)

    from api.scheduler import upsert_job
    upsert_job({**schedule, "enabled": body.enabled})
    schedule["next_run_at"] = _row_to_dict(row)["next_run_at"]
    return schedule


@router.put("/{schedule_id}")
async def update_schedule(schedule_id: int, body: ScheduleUpdate):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _row_to_dict(row)

    if "mode" in updates and updates["mode"] not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Unknown mode '{updates['mode']}'")
    if "cron_expr" in updates:
        _validate_cron(updates["cron_expr"])
    if "keywords" in updates:
        updates["keywords"] = json.dumps(updates["keywords"])
    for bool_field in ("manual_publish", "enabled"):
        if bool_field in updates:
            updates[bool_field] = 1 if updates[bool_field] else 0

    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE schedules SET {set_clause} WHERE id=?",
            (*updates.values(), schedule_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()

    schedule = _row_to_dict(row, include_next_run=False)
    from api.scheduler import upsert_job
    upsert_job(schedule)
    schedule["next_run_at"] = _row_to_dict(row)["next_run_at"]
    return schedule


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: int):
    with get_conn() as conn:
        if not conn.execute("SELECT id FROM schedules WHERE id=?", (schedule_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Schedule not found")
        conn.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
        conn.execute("DELETE FROM schedule_runs WHERE schedule_id=?", (schedule_id,))
        conn.commit()

    from api.scheduler import remove_job
    remove_job(schedule_id)
    return {"deleted": schedule_id}


@router.post("/{schedule_id}/toggle")
async def toggle_schedule(schedule_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    new_enabled = 0 if row["enabled"] else 1
    with get_conn() as conn:
        conn.execute("UPDATE schedules SET enabled=? WHERE id=?", (new_enabled, schedule_id))
        conn.commit()
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()

    schedule = _row_to_dict(row, include_next_run=False)
    from api.scheduler import upsert_job
    upsert_job(schedule)
    schedule["next_run_at"] = _row_to_dict(row)["next_run_at"]
    return schedule


@router.get("/{schedule_id}/runs")
async def get_runs(schedule_id: int, limit: int = 20):
    with get_conn() as conn:
        if not conn.execute("SELECT id FROM schedules WHERE id=?", (schedule_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Schedule not found")
        rows = conn.execute(
            "SELECT * FROM schedule_runs WHERE schedule_id=? ORDER BY id DESC LIMIT ?",
            (schedule_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{schedule_id}/runs/{run_id}/log")
async def get_run_log(schedule_id: int, run_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT log_path FROM schedule_runs WHERE id=? AND schedule_id=?",
            (run_id, schedule_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        content = Path(row["log_path"]).read_text(encoding="utf-8", errors="replace") if row["log_path"] else ""
    except (FileNotFoundError, TypeError):
        content = ""
    return {"content": content}
