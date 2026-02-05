import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "fitness.db"


def test_pipeline_runs_table_exists_or_skip():
    if not DB_PATH.exists():
        return
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'")
        assert cur.fetchone() is not None


def test_metrics_weekly_view_exists_or_skip():
    if not DB_PATH.exists():
        return
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='metrics_weekly'")
        assert cur.fetchone() is not None
