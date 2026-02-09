import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from packages import db
from packages.config import STRAVA_LOCAL_PATH


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
    with db.connect() as conn:
        db.configure_connection(conn)
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
