from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "fitness.db"


def test_db_exists_or_skip():
    if not DB_PATH.exists():
        return
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='metrics_weekly'")
        assert cur.fetchone() is not None


def test_schema_files_present():
    assert (ROOT / "database" / "schemas" / "schema.sql").exists()
    assert (ROOT / "database" / "migrations").exists()
