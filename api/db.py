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
        conn.commit()
