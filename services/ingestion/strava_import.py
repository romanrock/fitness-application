"""Import Strava JSONL + streams into SQLite (raw tables)."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from packages import db
from packages.config import STRAVA_LOCAL_PATH

RAW_DIR = STRAVA_LOCAL_PATH / "data"
ACTIVITIES = RAW_DIR / "activities.jsonl"
STREAMS_DIR = RAW_DIR / "streams"

SOURCE_NAME = "strava"


def ensure_source(conn):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sources(name) VALUES(?) ON CONFLICT(name) DO NOTHING",
        (SOURCE_NAME,),
    )
    cur.execute("SELECT id FROM sources WHERE name=?", (SOURCE_NAME,))
    return cur.fetchone()[0]


def get_default_user_id(conn):
    cur = conn.cursor()
    cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise SystemExit("No users found. Run scripts/create_user.py first.")
    return row[0]


def import_activities(conn, source_id, user_id):
    if not ACTIVITIES.exists():
        return 0
    count = 0
    cur = conn.cursor()
    for line in ACTIVITIES.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        activity_id = str(row.get("id"))
        start_time = row.get("start_date")
        raw_json = json.dumps(row)
        cur.execute(
            """
            INSERT INTO activities_raw(source_id, activity_id, start_time, raw_json, user_id)
            VALUES(?,?,?,?,?)
            ON CONFLICT(source_id, activity_id) DO UPDATE SET
              start_time=excluded.start_time,
              raw_json=excluded.raw_json,
              user_id=excluded.user_id
            """,
            (source_id, activity_id, start_time, raw_json, user_id),
        )
        count += 1
    conn.commit()
    return count


def import_streams(conn, source_id, user_id):
    if not STREAMS_DIR.exists():
        return 0
    count = 0
    cur = conn.cursor()
    for p in STREAMS_DIR.glob("*.json"):
        activity_id = p.stem
        data = json.loads(p.read_text())
        for key, payload in data.items():
            raw_json = json.dumps(payload)
            cur.execute(
                """
                INSERT INTO streams_raw(source_id, activity_id, stream_type, raw_json, user_id)
                VALUES(?,?,?,?,?)
                ON CONFLICT(source_id, activity_id, stream_type) DO UPDATE SET
                  raw_json=excluded.raw_json,
                  user_id=excluded.user_id
                """,
                (source_id, activity_id, key, raw_json, user_id),
            )
            count += 1
    conn.commit()
    return count


def main():
    if not db.db_exists():
        raise SystemExit("DB not initialized. Run scripts/init_db.py")
    with db.connect() as conn:
        db.configure_connection(conn)
        source_id = ensure_source(conn)
        user_id = get_default_user_id(conn)
        a = import_activities(conn, source_id, user_id)
        s = import_streams(conn, source_id, user_id)
    print(f"Imported activities: {a}")
    print(f"Imported streams: {s}")


if __name__ == "__main__":
    main()
