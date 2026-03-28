"""
APScheduler integration for automated pipeline runs.
Schedules are persisted in SQLite and re-loaded on every API startup.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from api.db import get_conn

scheduler = AsyncIOScheduler(timezone="UTC")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cron_kwargs(expr: str) -> dict:
    """Parse '0 9 * * 1' -> kwargs for CronTrigger."""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Cron expression must have 5 fields, got: {expr!r}")
    minute, hour, day, month, day_of_week = parts
    return dict(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)


async def _execute_schedule(schedule_id: int) -> None:
    """Run a scheduled pipeline job as a subprocess and log output."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    if not row or not row["enabled"]:
        return

    schedule = dict(row)
    site_id = schedule["site_id"]
    mode = schedule["mode"]
    keywords: list[str] = json.loads(schedule.get("keywords") or "[]")

    from api.config_manager import get_site, ROOT_DIR  # local import avoids circular
    site = get_site(site_id)
    if not site:
        print(f"[scheduler] Site '{site_id}' not found for schedule {schedule_id}", flush=True)
        return

    config_file = site["_file"]
    started_at = datetime.now(timezone.utc).isoformat()

    log_dir = ROOT_DIR / "scheduled" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(log_dir / f"{site_id}-{mode}.log")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO schedule_runs (schedule_id, site_id, mode, started_at, log_path) VALUES (?,?,?,?,?)",
            (schedule_id, site_id, mode, started_at, log_path),
        )
        run_id = cur.lastrowid
        conn.execute("UPDATE schedules SET last_run_at=? WHERE id=?", (started_at, schedule_id))
        conn.commit()

    cmd = [sys.executable, "run.py", mode, "--config", config_file]
    if keywords:
        cmd += ["--keywords", ",".join(keywords)]

    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    exit_code = 1

    try:
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"\n[{started_at}] Starting {mode} for {site_id}\n")
            lf.write(f"  Config: {config_file}\n")
            lf.write("─" * 52 + "\n")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROOT_DIR),
            env=env,
        )

        with open(log_path, "a", encoding="utf-8") as lf:
            async for raw in process.stdout:
                lf.write(raw.decode("utf-8", errors="replace"))

        await process.wait()
        exit_code = process.returncode if process.returncode is not None else 1

    except Exception as exc:
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"[ERROR] {exc}\n")

    finished_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE schedule_runs SET finished_at=?, exit_code=? WHERE id=?",
            (finished_at, exit_code, run_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Public API used by routes/schedules.py
# ---------------------------------------------------------------------------

def load_all() -> None:
    """Called on startup — register every enabled schedule."""
    try:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM schedules WHERE enabled=1").fetchall()
        for row in rows:
            _register(dict(row))
    except Exception as exc:
        print(f"[scheduler] load_all failed: {exc}", flush=True)


def _register(schedule: dict) -> None:
    job_id = f"sched_{schedule['id']}"
    try:
        kwargs = _cron_kwargs(schedule["cron_expr"])
        scheduler.add_job(
            _execute_schedule,
            trigger=CronTrigger(**kwargs),
            id=job_id,
            args=[schedule["id"]],
            replace_existing=True,
            misfire_grace_time=3600,
        )
    except Exception as exc:
        print(f"[scheduler] Failed to register {job_id}: {exc}", flush=True)


def upsert_job(schedule: dict) -> None:
    """Add or update a job; remove if disabled."""
    if schedule.get("enabled"):
        _register(schedule)
    else:
        remove_job(schedule["id"])


def remove_job(schedule_id: int) -> None:
    job_id = f"sched_{schedule_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def next_run(schedule_id: int) -> str | None:
    job = scheduler.get_job(f"sched_{schedule_id}")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None
