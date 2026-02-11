import argparse
import json
import os
import time
from datetime import datetime, timezone
from urllib import parse, request
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages import db

WEATHER_API_BASE = "https://archive-api.open-meteo.com/v1/archive"


def _parse_start_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fetch_weather(lat: float, lon: float, date: str, hour_utc: int | None) -> dict | None:
    params = {
        "latitude": str(lat),
        "longitude": str(lon),
        "start_date": date,
        "end_date": date,
        "hourly": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "wind_speed_10m",
                "wind_gusts_10m",
                "precipitation",
                "weather_code",
            ]
        ),
        "timezone": "UTC",
    }
    url = f"{WEATHER_API_BASE}?{parse.urlencode(params)}"
    req = request.Request(url)
    with request.urlopen(req, timeout=30) as resp:
        payload = resp.read().decode("utf-8")
    data = json.loads(payload)
    hourly = data.get("hourly") or {}
    times = hourly.get("time")
    if not times:
        return None

    idx = -1
    if hour_utc is not None:
        target = f"{date}T{str(hour_utc).zfill(2)}:00"
        for i, t in enumerate(times):
            if t == target:
                idx = i
                break

    def pick(arr):
        if idx >= 0 and isinstance(arr, list) and idx < len(arr):
            return arr[idx]
        return None

    def avg(arr):
        if not isinstance(arr, list):
            return None
        nums = [v for v in arr if v is not None]
        if not nums:
            return None
        return sum(nums) / len(nums)

    return {
        "date": date,
        "hour_utc": hour_utc,
        "temp_c": pick(hourly.get("temperature_2m")),
        "humidity": pick(hourly.get("relative_humidity_2m")),
        "wind_kmh": pick(hourly.get("wind_speed_10m")),
        "gust_kmh": pick(hourly.get("wind_gusts_10m")),
        "precip_mm": pick(hourly.get("precipitation")),
        "weather_code": pick(hourly.get("weather_code")),
        "avg_temp_c": avg(hourly.get("temperature_2m")),
        "avg_wind_kmh": avg(hourly.get("wind_speed_10m")),
        "avg_humidity": avg(hourly.get("relative_humidity_2m")),
        "avg_precip_mm": avg(hourly.get("precipitation")),
    }


def _iter_activities(conn, refresh: bool, limit: int | None, after: str | None, before: str | None):
    where = []
    params: list = []
    if not refresh:
        where.append("w.activity_id IS NULL")
    if after:
        where.append("a.start_time >= ?")
        params.append(after)
    if before:
        where.append("a.start_time <= ?")
        params.append(before)

    sql = [
        "SELECT a.activity_id, a.start_time, a.raw_json, a.user_id",
        "FROM activities_raw a",
        "LEFT JOIN weather_raw w ON w.activity_id = a.activity_id AND w.user_id = a.user_id",
    ]
    if where:
        sql.append("WHERE " + " AND ".join(where))
    sql.append("ORDER BY a.start_time DESC")
    if limit:
        sql.append("LIMIT ?")
        params.append(limit)
    query = "\n".join(sql)
    return conn.execute(query, tuple(params)).fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Open-Meteo archive weather for activities.")
    parser.add_argument("--refresh", action="store_true", help="Refetch weather even if already present.")
    parser.add_argument("--limit", type=int, default=None, help="Max activities to process.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between requests.")
    parser.add_argument("--after", type=str, default=None, help="Only activities at/after ISO timestamp.")
    parser.add_argument("--before", type=str, default=None, help="Only activities at/before ISO timestamp.")
    parser.add_argument("--dry-run", action="store_true", help="List activities that would be processed.")
    args = parser.parse_args()
    if args.limit is None:
        env_limit = os.getenv("FITNESS_WEATHER_API_LIMIT")
        if env_limit:
            try:
                args.limit = int(env_limit)
            except ValueError:
                pass
    env_sleep = os.getenv("FITNESS_WEATHER_API_SLEEP")
    if env_sleep:
        try:
            args.sleep = float(env_sleep)
        except ValueError:
            pass

    processed = 0
    with db.connect() as conn:
        db.configure_connection(conn)
        rows = _iter_activities(conn, args.refresh, args.limit, args.after, args.before)
        if args.dry_run:
            print(f"weather backfill candidates: {len(rows)}")
            return 0
        for activity_id, start_time, raw_json, user_id in rows:
            try:
                raw = json.loads(raw_json)
            except json.JSONDecodeError:
                continue
            latlng = raw.get("start_latlng") or raw.get("start_latlngs")
            if not latlng or len(latlng) < 2:
                continue
            dt = _parse_start_dt(raw.get("start_date") or start_time)
            if not dt:
                continue
            lat = float(latlng[0])
            lon = float(latlng[1])
            date = dt.date().isoformat()
            hour_utc = dt.hour
            try:
                weather = _fetch_weather(lat, lon, date, hour_utc)
            except Exception as exc:
                print(f"Weather fetch failed for {activity_id}: {exc}")
                continue
            if not weather:
                continue
            conn.execute(
                """
                INSERT INTO weather_raw(activity_id, raw_json, user_id)
                VALUES(?, ?, ?)
                ON CONFLICT(user_id, activity_id) DO UPDATE SET
                    raw_json=excluded.raw_json
                """,
                (activity_id, json.dumps(weather), user_id),
            )
            conn.commit()
            processed += 1
            if processed % 25 == 0:
                print(f"Weather fetched: {processed}")
            if args.sleep:
                time.sleep(args.sleep)
    print(f"Weather records written: {processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
