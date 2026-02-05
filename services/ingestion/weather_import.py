"""Import weather JSON into SQLite (raw table)."""
from pathlib import Path
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from packages.config import DB_PATH, STRAVA_LOCAL_PATH

RAW_DIR = STRAVA_LOCAL_PATH / "data"
WEATHER_DIR = RAW_DIR / "weather"


def configure_sqlite(conn):
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
    except sqlite3.OperationalError:
        return


def import_weather(conn):
    if not WEATHER_DIR.exists():
        return 0
    count = 0
    cur = conn.cursor()
    cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise SystemExit("No users found. Run scripts/create_user.py first.")
    user_id = row[0]
    for p in WEATHER_DIR.glob("*.json"):
        activity_id = p.stem
        raw_json = p.read_text()
        cur.execute(
            "INSERT OR IGNORE INTO weather_raw(activity_id, raw_json, user_id) VALUES(?,?,?)",
            (activity_id, raw_json, user_id),
        )
        count += 1
    conn.commit()
    return count


def main():
    if not DB_PATH.exists():
        raise SystemExit("DB not initialized. Run scripts/init_db.py")
    with sqlite3.connect(DB_PATH) as conn:
        configure_sqlite(conn)
        c = import_weather(conn)
    print(f"Imported weather records: {c}")


if __name__ == "__main__":
    main()
