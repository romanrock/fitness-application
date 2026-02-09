"""Import weather JSON into SQLite (raw table)."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from packages import db
from packages.config import STRAVA_LOCAL_PATH

RAW_DIR = STRAVA_LOCAL_PATH / "data"
WEATHER_DIR = RAW_DIR / "weather"


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
            """
            INSERT INTO weather_raw(activity_id, raw_json, user_id)
            VALUES(?,?,?)
            ON CONFLICT(user_id, activity_id) DO UPDATE SET
              raw_json=excluded.raw_json
            """,
            (activity_id, raw_json, user_id),
        )
        count += 1
    conn.commit()
    return count


def main():
    if not db.db_exists():
        raise SystemExit("DB not initialized. Run scripts/init_db.py")
    with db.connect() as conn:
        db.configure_connection(conn)
        c = import_weather(conn)
    print(f"Imported weather records: {c}")


if __name__ == "__main__":
    main()
