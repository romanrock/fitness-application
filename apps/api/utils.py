import datetime
import json
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple

from packages.config import DB_PATH, LAST_UPDATE_PATH


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
    except sqlite3.OperationalError:
        pass
    return conn


def db_exists() -> bool:
    return DB_PATH.exists()


def dict_rows(cursor) -> Iterable[Dict[str, Any]]:
    cols = [c[0] for c in cursor.description]
    for row in cursor.fetchall():
        yield {cols[i]: row[i] for i in range(len(cols))}


def build_date_filter(start: str | None, end: str | None) -> Tuple[str, List[str]]:
    clause = ""
    params: List[str] = []
    if start:
        clause += " AND a.start_time >= ?"
        params.append(start)
    if end:
        clause += " AND a.start_time <= ?"
        params.append(end)
    return clause, params


def compute_vdot(distance_m: float, time_s: float) -> Optional[float]:
    if not distance_m or not time_s:
        return None
    v_m_min = (distance_m / time_s) * 60.0
    vo2 = -4.60 + 0.182258 * v_m_min + 0.000104 * (v_m_min ** 2)
    t_min = time_s / 60.0
    pct = 0.8 + 0.1894393 * (2.718281828 ** (-0.012778 * t_min)) + 0.2989558 * (2.718281828 ** (-0.1932605 * t_min))
    if pct == 0:
        return None
    return vo2 / pct


def linear_slope(values: List[float]) -> Optional[float]:
    n = len(values)
    if n < 2:
        return None
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    den = sum((x - x_mean) ** 2 for x in xs)
    return (num / den) if den else None


def decode_polyline(polyline: str) -> List[List[float]]:
    coords: List[List[float]] = []
    index = 0
    lat = 0
    lng = 0
    length = len(polyline)
    while index < length:
        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        delta_lat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += delta_lat

        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        delta_lng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += delta_lng

        coords.append([lat / 1e5, lng / 1e5])
    return coords


def get_last_update() -> Optional[str]:
    if not LAST_UPDATE_PATH.exists():
        return None
    try:
        return json.loads(LAST_UPDATE_PATH.read_text()).get("last_update")
    except json.JSONDecodeError:
        return None


def week_key(value: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return value[:10]
    monday = dt - datetime.timedelta(days=dt.weekday())
    return monday.date().isoformat()
