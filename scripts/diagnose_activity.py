import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages import db


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python3 scripts/diagnose_activity.py <activity_id>")
    activity_id = sys.argv[1]
    if not db.db_exists():
        raise SystemExit("DB not found. Run the pipeline first.")
    with db.connect() as conn:
        db.configure_connection(conn)
        cur = conn.cursor()
        cur.execute(
            "SELECT stream_type FROM streams_raw WHERE activity_id=? ORDER BY stream_type",
            (activity_id,),
        )
        streams = [row[0] for row in cur.fetchall()]
        print(f"Streams: {streams}")

        cur.execute(
            """
            SELECT distance_m, moving_s, avg_hr_norm, avg_hr_raw, flat_pace_sec, flat_pace_weather_sec,
                   cadence_avg, stride_len, hr_drift, decoupling
            FROM activities_calc
            WHERE activity_id=?
            """,
            (activity_id,),
        )
        row = cur.fetchone()
        if not row:
            print("No activities_calc row")
        else:
            keys = ["distance_m", "moving_s", "avg_hr_norm", "avg_hr_raw", "flat_pace_sec", "flat_pace_weather_sec", "cadence_avg", "stride_len", "hr_drift", "decoupling"]
            print("activities_calc:")
            for k, v in zip(keys, row):
                print(f"  {k}: {v}")

        cur.execute(
            "SELECT hr_norm_json, pace_smooth_json FROM activities_norm WHERE activity_id=?",
            (activity_id,),
        )
        norm = cur.fetchone()
        if not norm:
            print("No activities_norm row")
        else:
            hr_norm_json, pace_smooth_json = norm
            try:
                hr_norm = json.loads(hr_norm_json) if hr_norm_json else []
            except json.JSONDecodeError:
                hr_norm = []
            try:
                pace_smooth = json.loads(pace_smooth_json) if pace_smooth_json else []
            except json.JSONDecodeError:
                pace_smooth = []
            print(f"hr_norm points: {len(hr_norm)}")
            print(f"pace_smooth points: {len(pace_smooth)}")


if __name__ == "__main__":
    main()
