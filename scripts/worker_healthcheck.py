import datetime
from packages import db
from packages.config import REFRESH_SECONDS


def main() -> int:
    if not db.db_exists():
        print("DB missing")
        return 1
    with db.connect() as conn:
        db.configure_connection(conn)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT finished_at, status
            FROM pipeline_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            print("No pipeline runs")
            return 1
        finished_at, status = row
        if status != "ok":
            print(f"Last pipeline status: {status}")
            return 1
        try:
            if isinstance(finished_at, datetime.datetime):
                finished_dt = finished_at
            else:
                finished_dt = datetime.datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
        except Exception:
            print("Invalid finished_at")
            return 1
        max_age = datetime.timedelta(seconds=REFRESH_SECONDS * 2)
        if datetime.datetime.now(datetime.timezone.utc) - finished_dt > max_age:
            print("Pipeline too old")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
