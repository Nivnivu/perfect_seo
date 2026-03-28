import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "pipeline_runs.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id     TEXT    NOT NULL,
                site_name   TEXT,
                mode        TEXT    NOT NULL,
                started_at  TEXT    NOT NULL,
                finished_at TEXT,
                exit_code   INTEGER,
                log_preview TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_reviews (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id       TEXT    NOT NULL,
                mode          TEXT    NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'pending',
                title         TEXT,
                subtitle      TEXT,
                body_html     TEXT,
                body_markdown TEXT,
                gemini_output TEXT,
                image_base64  TEXT,
                topic         TEXT,
                post_id       TEXT,
                original_title TEXT,
                original_body  TEXT,
                subtitle_only  INTEGER DEFAULT 0,
                created_at    TEXT    NOT NULL,
                published_at  TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id        TEXT    NOT NULL,
                mode           TEXT    NOT NULL,
                cron_expr      TEXT    NOT NULL,
                label          TEXT,
                keywords       TEXT    DEFAULT '[]',
                manual_publish INTEGER DEFAULT 0,
                enabled        INTEGER DEFAULT 1,
                created_at     TEXT    NOT NULL,
                last_run_at    TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                site_id     TEXT    NOT NULL,
                mode        TEXT    NOT NULL,
                started_at  TEXT    NOT NULL,
                finished_at TEXT,
                exit_code   INTEGER,
                log_path    TEXT
            )
        """)
        conn.commit()
