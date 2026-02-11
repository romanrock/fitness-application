import argparse
import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages import db
from packages.config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN
from services.ingestion import strava_api_import as api


def _iter_missing_streams(conn, after: str | None, before: str | None, limit: int | None):
    where = ["(t.activity_id IS NULL OR d.activity_id IS NULL)"]
    params: list = []
    if after:
        where.append("a.start_time >= ?")
        params.append(after)
    if before:
        where.append("a.start_time <= ?")
        params.append(before)
    sql = [
        "SELECT a.activity_id, a.start_time, a.raw_json, a.user_id",
        "FROM activities_raw a",
        "LEFT JOIN streams_raw t ON t.activity_id = a.activity_id AND t.stream_type='time'",
        "LEFT JOIN streams_raw d ON d.activity_id = a.activity_id AND d.stream_type='distance'",
        "WHERE " + " AND ".join(where),
        "ORDER BY a.start_time DESC",
    ]
    if limit:
        sql.append("LIMIT ?")
        params.append(limit)
    query = "\n".join(sql)
    return conn.execute(query, tuple(params)).fetchall()


def _is_run(raw_json: str) -> bool:
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError:
        return False
    sport = str(raw.get("sport_type") or raw.get("type") or "").lower()
    return sport == "run"


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Strava streams for activities missing time/distance.")
    parser.add_argument("--limit", type=int, default=None, help="Max activities to process.")
    parser.add_argument("--sleep", type=float, default=0.5, help="Seconds to sleep between API calls.")
    parser.add_argument("--after", type=str, default=None, help="Only activities at/after ISO timestamp.")
    parser.add_argument("--before", type=str, default=None, help="Only activities at/before ISO timestamp.")
    parser.add_argument("--include-non-runs", action="store_true", help="Also backfill non-run activities.")
    parser.add_argument("--refresh", action="store_true", help="Refetch streams even if present.")
    args = parser.parse_args()

    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET or not STRAVA_REFRESH_TOKEN:
        raise SystemExit("Strava API not configured. Set STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN.")

    processed = 0
    with db.connect() as conn:
        db.configure_connection(conn)
        source_id = api._ensure_source(conn)
        user_id = api._default_user_id(conn)
        state = api._load_sync_state(conn, source_id, user_id)
        token_state = api._ensure_token(state)
        access_token = token_state["access_token"]

        rows = _iter_missing_streams(conn, args.after, args.before, args.limit)
        for activity_id, start_time, raw_json, row_user_id in rows:
            if not args.include_non_runs and not _is_run(raw_json):
                continue
            try:
                streams_payload = api._fetch_streams(access_token, activity_id)
            except Exception as exc:
                print(f"Stream fetch failed for {activity_id}: {exc}")
                continue
            for stream_type, stream in streams_payload.items():
                if stream_type == "original_size":
                    continue
                if not args.refresh and api._stream_exists(conn, source_id, activity_id, stream_type):
                    continue
                api._upsert_stream(conn, source_id, row_user_id, activity_id, stream_type, stream)
            conn.commit()
            processed += 1
            if processed % 25 == 0:
                print(f"Streams fetched: {processed}")
            if args.sleep:
                time.sleep(args.sleep)

        # Keep tokens fresh without changing last_activity_time.
        api._update_sync_state(
            conn,
            source_id,
            user_id,
            {
                "last_activity_time": state.get("last_activity_time"),
                "access_token": token_state.get("access_token"),
                "refresh_token": token_state.get("refresh_token"),
                "expires_at": token_state.get("expires_at"),
            },
        )
        conn.commit()

    print(f"Streams backfill complete: {processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
