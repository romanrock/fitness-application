import json
import os
import time
from datetime import datetime, timezone
from urllib import parse, request
import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.config import (
    DB_PATH,
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
    STRAVA_REFRESH_TOKEN,
    STRAVA_ACCESS_TOKEN,
    STRAVA_EXPIRES_AT,
)

STRAVA_API_BASE = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"
STREAM_KEYS = "time,distance,heartrate,cadence,altitude,velocity_smooth,latlng"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_to_epoch(value: str | None) -> int | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return int(dt.timestamp())


def _http_json(url: str, headers: dict[str, str], params: dict | None = None) -> dict:
    if params:
        url = f"{url}?{parse.urlencode(params)}"
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=30) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def _post_form(url: str, data: dict) -> dict:
    body = parse.urlencode(data).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    with request.urlopen(req, timeout=30) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def _ensure_source(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO sources(name) VALUES(?)", ("strava",))
    cur.execute("SELECT id FROM sources WHERE name=?", ("strava",))
    return cur.fetchone()[0]


def _default_user_id(conn: sqlite3.Connection) -> int:
    override = os.getenv("FITNESS_STRAVA_USER_ID")
    if override:
        try:
            return int(override)
        except ValueError:
            raise RuntimeError("FITNESS_STRAVA_USER_ID must be an integer.")
    cur = conn.cursor()
    cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("No users found; create a user before syncing Strava API.")
    return row[0]


def _load_sync_state(conn: sqlite3.Connection, source_id: int, user_id: int) -> dict:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT last_activity_time, access_token, refresh_token, expires_at
        FROM source_sync_state
        WHERE source_id=? AND user_id=?
        """,
        (source_id, user_id),
    )
    row = cur.fetchone()
    if row:
        return {
            "last_activity_time": row[0],
            "access_token": row[1],
            "refresh_token": row[2],
            "expires_at": row[3],
        }
    cur.execute(
        "INSERT INTO source_sync_state(source_id, user_id, last_activity_time) VALUES(?, ?, ?)",
        (source_id, user_id, None),
    )
    conn.commit()
    return {"last_activity_time": None, "access_token": None, "refresh_token": None, "expires_at": None}


def _update_sync_state(conn: sqlite3.Connection, source_id: int, user_id: int, fields: dict) -> None:
    keys = ["last_activity_time", "access_token", "refresh_token", "expires_at"]
    updates = {k: fields.get(k) for k in keys}
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE source_sync_state
        SET last_activity_time=?,
            access_token=?,
            refresh_token=?,
            expires_at=?,
            updated_at=?
        WHERE source_id=? AND user_id=?
        """,
        (
            updates["last_activity_time"],
            updates["access_token"],
            updates["refresh_token"],
            updates["expires_at"],
            _utc_now().isoformat(),
            source_id,
            user_id,
        ),
    )
    conn.commit()


def _resolve_last_activity_time(conn: sqlite3.Connection, source_id: int, user_id: int, state: dict) -> int:
    if state.get("last_activity_time"):
        return int(state["last_activity_time"])
    cur = conn.cursor()
    cur.execute(
        """
        SELECT start_time FROM activities_raw
        WHERE source_id=? AND user_id=? AND start_time IS NOT NULL
        ORDER BY start_time DESC LIMIT 1
        """,
        (source_id, user_id),
    )
    row = cur.fetchone()
    last = _parse_iso_to_epoch(row[0]) if row else None
    return last or 0


def _ensure_token(state: dict) -> dict:
    access_token = state.get("access_token") or STRAVA_ACCESS_TOKEN
    refresh_token = state.get("refresh_token") or STRAVA_REFRESH_TOKEN
    expires_at = state.get("expires_at")
    if STRAVA_EXPIRES_AT and not expires_at:
        try:
            expires_at = int(STRAVA_EXPIRES_AT)
        except ValueError:
            expires_at = None
    now = int(time.time())
    needs_refresh = not access_token or not expires_at or expires_at <= now + 60
    if not needs_refresh:
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
        }
    if not (STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET and refresh_token):
        raise RuntimeError("Strava API credentials missing; cannot refresh token.")
    token_payload = _post_form(
        TOKEN_URL,
        {
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    return {
        "access_token": token_payload["access_token"],
        "refresh_token": token_payload.get("refresh_token", refresh_token),
        "expires_at": int(token_payload.get("expires_at", now + 3600)),
    }


def _upsert_activity(conn: sqlite3.Connection, source_id: int, user_id: int, activity: dict) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO activities_raw(source_id, activity_id, start_time, raw_json, user_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_id, activity_id) DO UPDATE SET
          start_time=excluded.start_time,
          raw_json=excluded.raw_json,
          user_id=excluded.user_id
        """,
        (
            source_id,
            str(activity.get("id")),
            activity.get("start_date"),
            json.dumps(activity),
            user_id,
        ),
    )


def _stream_exists(conn: sqlite3.Connection, source_id: int, activity_id: str, stream_type: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM streams_raw
        WHERE source_id=? AND activity_id=? AND stream_type=? LIMIT 1
        """,
        (source_id, activity_id, stream_type),
    )
    return cur.fetchone() is not None


def _upsert_stream(conn: sqlite3.Connection, source_id: int, user_id: int, activity_id: str, stream_type: str, stream: dict) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO streams_raw(source_id, activity_id, stream_type, raw_json, user_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_id, activity_id, stream_type) DO UPDATE SET
          raw_json=excluded.raw_json,
          user_id=excluded.user_id
        """,
        (
            source_id,
            activity_id,
            stream_type,
            json.dumps(stream),
            user_id,
        ),
    )


def _fetch_streams(access_token: str, activity_id: str) -> dict:
    return _http_json(
        f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"keys": STREAM_KEYS, "key_by_type": "true"},
    )


def _fetch_activities(access_token: str, after_epoch: int) -> list[dict]:
    activities: list[dict] = []
    page = 1
    while True:
        payload = _http_json(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"after": max(after_epoch - 60, 0), "per_page": 200, "page": page},
        )
        if not payload:
            break
        activities.extend(payload)
        if len(payload) < 200:
            break
        page += 1
    return activities


def main() -> None:
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET or not STRAVA_REFRESH_TOKEN:
        raise RuntimeError("Strava API not configured. Set STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN.")
    with sqlite3.connect(DB_PATH) as conn:
        source_id = _ensure_source(conn)
        user_id = _default_user_id(conn)
        state = _load_sync_state(conn, source_id, user_id)
        last_time = _resolve_last_activity_time(conn, source_id, user_id, state)
        token_state = _ensure_token(state)
        access_token = token_state["access_token"]
        activities = _fetch_activities(access_token, last_time)
        newest_time = last_time
        new_activity_ids: list[str] = []
        for activity in activities:
            _upsert_activity(conn, source_id, user_id, activity)
            act_id = str(activity.get("id"))
            new_activity_ids.append(act_id)
            start_epoch = _parse_iso_to_epoch(activity.get("start_date")) or 0
            newest_time = max(newest_time, start_epoch)
        for act_id in new_activity_ids:
            streams_payload = _fetch_streams(access_token, act_id)
            for stream_type, stream in streams_payload.items():
                if stream_type == "original_size":
                    continue
                if _stream_exists(conn, source_id, act_id, stream_type):
                    continue
                _upsert_stream(conn, source_id, user_id, act_id, stream_type, stream)
        _update_sync_state(
            conn,
            source_id,
            user_id,
            {
                "last_activity_time": newest_time,
                "access_token": token_state["access_token"],
                "refresh_token": token_state["refresh_token"],
                "expires_at": token_state["expires_at"],
            },
        )
        conn.commit()
    print(f"Strava API sync complete. Activities fetched: {len(activities)}")


if __name__ == "__main__":
    main()
