import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from packages.config import DB_PATH, STRAVA_LOCAL_PATH


def configure_sqlite(conn):
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
    except sqlite3.OperationalError:
        return


def load_segments():
    path = STRAVA_LOCAL_PATH / "data" / "segments_best.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def main():
    payload = load_segments()
    if not payload:
        print("No segments_best.json found or empty.")
        return
    segments_dir = STRAVA_LOCAL_PATH / "data" / "segments"
    with sqlite3.connect(DB_PATH) as conn:
        configure_sqlite(conn)
        cur = conn.cursor()
        for scope, segments in payload.items():
            if not isinstance(segments, dict):
                continue
            cur.execute("DELETE FROM segments_best WHERE scope=?", (scope,))
            for distance, meta in segments.items():
                try:
                    distance_m = int(distance)
                except ValueError:
                    continue
                if not isinstance(meta, dict):
                    continue
                time_s = meta.get("time_s")
                activity_id = meta.get("id")
                date = meta.get("date")
                cur.execute(
                    """
                    INSERT INTO segments_best(distance_m, time_s, activity_id, scope, date)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (distance_m, time_s, activity_id, scope, date),
                )

        if segments_dir.exists():
            cur.execute("DELETE FROM segments_best WHERE scope='activity'")
            for path in segments_dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text())
                except json.JSONDecodeError:
                    continue
                activity_id = data.get("id")
                date = data.get("date")
                best = data.get("best", {})
                if not activity_id or not isinstance(best, dict):
                    continue
                for distance, time_s in best.items():
                    try:
                        distance_m = int(distance)
                    except ValueError:
                        continue
                    cur.execute(
                        """
                        INSERT INTO segments_best(distance_m, time_s, activity_id, scope, date)
                        VALUES (?, ?, ?, 'activity', ?)
                        """,
                        (distance_m, time_s, activity_id, date),
                    )
        conn.commit()
    print("Imported segments_best.")


if __name__ == "__main__":
    main()
