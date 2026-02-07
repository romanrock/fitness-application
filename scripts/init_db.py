import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "fitness.db"
SCHEMA = ROOT / "database" / "schemas" / "schema.sql"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

with sqlite3.connect(DB_PATH) as conn:
    try:
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.OperationalError:
        pass
    conn.executescript(SCHEMA.read_text())

print(f"Initialized {DB_PATH}")
