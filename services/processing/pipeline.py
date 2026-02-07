"""Process raw Strava data into normalized, calculated, and view layers in SQLite."""
from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from packages.config import DB_PATH, LAST_UPDATE_PATH, HR_MAX, HR_REST, HR_ZONE_METHOD


@dataclass
class FlatPaceResult:
    flat_pace_sec_per_km: float
    flat_time: float
    dist: float


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def configure_sqlite(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.OperationalError:
        return


def week_start_iso(dt: datetime) -> str:
    dt_utc = dt.astimezone(timezone.utc)
    monday = dt_utc - timedelta(days=(dt_utc.isoweekday() - 1))
    monday = datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)
    return monday.date().isoformat()


def normalize_activity_type(value: str) -> str:
    raw = (value or "").strip().lower()
    if raw in {"run", "trail run", "virtual run"}:
        return "run"
    if raw in {"walk", "hike", "walk/run"}:
        return "walk"
    if raw in {"golf"}:
        return "golf"
    return raw or "unknown"


def median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    return s[len(s) // 2]


def rolling_average(values: List[Optional[float]], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    queue: List[Optional[float]] = []
    total = 0.0
    for v in values:
        queue.append(v)
        if v is not None:
            total += v
        if len(queue) > window:
            removed = queue.pop(0)
            if removed is not None:
                total -= removed
        denom = sum(1 for x in queue if x is not None)
        out.append((total / denom) if denom else None)
    return out


def mean(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def drop_initial_zeros(values: List[Optional[float]]) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    seen = False
    for v in values:
        if v is None:
            out.append(None)
            continue
        if not seen and v == 0:
            out.append(None)
            continue
        seen = True
        out.append(v)
    return out


def clamp_values(values: List[Optional[float]], min_val: Optional[float], max_val: Optional[float]) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for v in values:
        if v is None:
            out.append(None)
            continue
        if min_val is not None and v < min_val:
            out.append(None)
            continue
        if max_val is not None and v > max_val:
            out.append(None)
            continue
        out.append(v)
    return out


def hampel_filter(values: List[Optional[float]], window: int = 5, t0: float = 3.0) -> List[Optional[float]]:
    out: List[Optional[float]] = values[:]
    n = len(values)
    for i in range(n):
        lo = max(0, i - window)
        hi = min(n, i + window + 1)
        window_vals = [v for v in values[lo:hi] if v is not None]
        if not window_vals or values[i] is None:
            continue
        med = median(window_vals)
        if med is None:
            continue
        mad = median([abs(v - med) for v in window_vals]) or 0.0
        scale = 1.4826 * mad
        if scale == 0:
            continue
        if abs(values[i] - med) > t0 * scale:
            out[i] = med
    return out


def ema(values: List[Optional[float]], alpha: float = 0.2) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    prev: Optional[float] = None
    for v in values:
        if v is None:
            out.append(prev)
            continue
        prev = v if prev is None else (alpha * v + (1 - alpha) * prev)
        out.append(prev)
    return out


def rolling_mean(values: List[Optional[float]], window: int = 5) -> List[Optional[float]]:
    if window <= 1:
        return values
    n = len(values)
    out: List[Optional[float]] = [None] * n
    half = window // 2
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        window_vals = [v for v in values[lo:hi] if v is not None]
        if not window_vals:
            out[i] = values[i]
            continue
        out[i] = sum(window_vals) / len(window_vals)
    return out


def compute_pace_series(time: List[float], dist: List[float]) -> List[Optional[float]]:
    n = min(len(time), len(dist))
    pace: List[Optional[float]] = [None] * n
    for i in range(1, n):
        dt = time[i] - time[i - 1]
        dd = dist[i] - dist[i - 1]
        if dt <= 0 or dd <= 0:
            continue
        pace[i] = dt / (dd / 1000)
    return pace


def smooth_pace(time: List[float], dist: List[float]) -> Tuple[List[Optional[float]], Optional[float]]:
    pace = compute_pace_series(time, dist)
    pace = clamp_values(pace, 150, 900)
    pace = hampel_filter(pace, window=7, t0=3.0)
    pace = ema(pace, alpha=0.12)
    pace = rolling_mean(pace, window=5)
    pace = clamp_values(pace, 150, 900)
    return pace, mean(pace)


def smooth_cadence(cadence: List[Optional[float]]) -> Tuple[List[Optional[float]], Optional[float]]:
    cadence = drop_initial_zeros(cadence)
    cadence = clamp_values(cadence, 50, 200)
    cadence = hampel_filter(cadence, window=7, t0=3.0)
    med = median([v for v in cadence if v is not None]) or 0
    if med and med < 120:
        cadence = [v * 2 if v is not None else None for v in cadence]
    cadence = clamp_values(cadence, 120, 240)
    cadence = ema(cadence, alpha=0.2)
    return cadence, mean(cadence)


def smooth_hr(hr: List[Optional[float]]) -> Tuple[List[Optional[float]], Optional[float]]:
    hr = drop_initial_zeros(hr)
    hr = clamp_values(hr, 60, 210)
    hr = hampel_filter(hr, window=7, t0=3.0)
    hr = ema(hr, alpha=0.2)
    return hr, mean(hr)


def load_streams(conn: sqlite3.Connection, activity_id: str) -> Dict[str, dict]:
    rows = conn.execute(
        "SELECT stream_type, raw_json FROM streams_raw WHERE activity_id=?",
        (activity_id,),
    ).fetchall()
    out: Dict[str, dict] = {}
    for stream_type, raw_json in rows:
        try:
            out[stream_type] = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
    return out


def stream_data(streams: Dict[str, dict], key: str) -> Optional[List[float]]:
    payload = streams.get(key)
    if not payload:
        return None
    data = payload.get("data")
    if not isinstance(data, list):
        return None
    return data


def compute_flat_pace(streams: Dict[str, dict]) -> Optional[FlatPaceResult]:
    time = stream_data(streams, "time")
    dist = stream_data(streams, "distance")
    alt = stream_data(streams, "altitude")
    if not time or not dist or len(time) != len(dist):
        return None
    n = len(time)
    has_alt = alt and len(alt) == n
    total_dist = 0.0
    flat_time = 0.0
    for i in range(1, n):
        dt = time[i] - time[i - 1]
        dd = dist[i] - dist[i - 1]
        if dt <= 0 or dd <= 0:
            continue
        grade = 0.0
        if has_alt:
            da = alt[i] - alt[i - 1]
            grade = da / dd
            if grade > 0.1:
                grade = 0.1
            if grade < -0.1:
                grade = -0.1
        # Grade-adjusted cost curve to estimate flat-equivalent pace.
        cost = 1 + 0.045 * grade + 0.35 * grade * grade
        pace_sec_per_m = dt / dd
        flat_sec_per_m = pace_sec_per_m * cost
        flat_time += flat_sec_per_m * dd
        total_dist += dd
    if total_dist <= 0:
        return None
    return FlatPaceResult(
        flat_pace_sec_per_km=(flat_time / total_dist) * 1000,
        flat_time=flat_time,
        dist=total_dist,
    )


def adjust_pace_for_weather(pace_sec: Optional[float], weather: Optional[dict]) -> Optional[float]:
    if pace_sec is None or not weather:
        return pace_sec
    temp = weather.get("temp_c", weather.get("avg_temp_c"))
    wind = weather.get("wind_kmh", weather.get("avg_wind_kmh"))
    factor = 1.0
    if temp is not None:
        if temp > 18:
            factor += (temp - 18) * 0.005
        if temp < 5:
            factor += (5 - temp) * 0.003
    if wind is not None and wind > 10:
        factor += (wind - 10) * 0.003
    return pace_sec * factor


def compute_cadence(streams: Dict[str, dict]) -> Optional[float]:
    cadence = stream_data(streams, "cadence")
    time = stream_data(streams, "time")
    if not cadence or not time or len(cadence) != len(time):
        return None
    vals = [v for v in cadence if v is not None]
    if not vals:
        return None
    avg = sum(vals) / len(vals)
    return avg * 2 if avg < 120 else avg


def normalize_hr(streams: Dict[str, dict]) -> Tuple[Optional[float], List[Optional[float]], bool]:
    time = stream_data(streams, "time")
    hr = stream_data(streams, "heartrate")
    dist = stream_data(streams, "distance")
    if not time or not hr or len(time) != len(hr):
        return None, [], False
    n = len(time)
    d = dist if dist and len(dist) == n else None

    cutoff = 120.0
    early_limit_sec = 900
    early_limit_dist = 1200
    peak_hr = -math.inf
    peak_idx = -1
    for i in range(n):
        if time[i] > early_limit_sec:
            break
        if d and d[i] > early_limit_dist:
            break
        if hr[i] > peak_hr:
            peak_hr = hr[i]
            peak_idx = i
    if peak_idx >= 0:
        drop_threshold = peak_hr - 22
        drop_window_sec = 120
        drop_window_dist = 400
        for i in range(peak_idx + 1, n):
            if time[i] - time[peak_idx] > drop_window_sec:
                break
            if d and (d[i] - d[peak_idx]) > drop_window_dist:
                break
            if hr[i] <= drop_threshold:
                cutoff = max(cutoff, time[i])
                break

    baseline_vals = [hr[i] for i in range(n) if time[i] <= 30 and hr[i] is not None]
    baseline = median(baseline_vals) if baseline_vals else min(hr)

    target_vals = [
        hr[i]
        for i in range(n)
        if (cutoff + 30) <= time[i] <= (cutoff + 120) and hr[i] is not None
    ]
    target = median(target_vals) if target_vals else baseline

    cutoff_dist = None
    if d:
        for i in range(n):
            if time[i] >= cutoff:
                cutoff_dist = d[i]
                break
    tau = 0.5 * (cutoff_dist or 1)

    hr_norm: List[Optional[float]] = [None] * n
    cleaned: List[float] = []
    anomaly = False
    window = 15

    for i in range(n):
        if time[i] < cutoff:
            if d and cutoff_dist:
                x = max(0.0, d[i])
                pred = baseline + (target - baseline) * (1 - math.exp(-x / tau))
                pred = min(pred, target)
                hr_norm[i] = pred
                cleaned.append(pred)
            continue
        lo = max(0, i - window)
        hi = min(n, i + window + 1)
        slice_vals = [v for v in hr[lo:hi] if v is not None]
        if not slice_vals:
            continue
        med = median(slice_vals)
        if med is None:
            continue
        if abs(hr[i] - med) >= 20:
            anomaly = True
            continue
        hr_norm[i] = hr[i]
        cleaned.append(hr[i])

    if not cleaned:
        return None, hr_norm, anomaly
    avg = sum(cleaned) / len(cleaned)
    return avg, hr_norm, anomaly


def compute_run_drift(streams: Dict[str, dict], hr_norm: Optional[List[Optional[float]]]) -> Tuple[Optional[float], Optional[float]]:
    time = stream_data(streams, "time")
    dist = stream_data(streams, "distance")
    if not time or not dist or len(time) != len(dist):
        return None, None
    n = len(time)
    hr_raw = stream_data(streams, "heartrate")
    hr = hr_norm if hr_norm and len(hr_norm) == n else hr_raw
    if not hr or len(hr) != n:
        return None, None
    total_dist = dist[-1]
    if not total_dist or total_dist <= 0:
        return None, None
    half_dist = total_dist / 2

    def trimmed_mean(values: List[float], trim: float = 0.1) -> Optional[float]:
        vals = [v for v in values if v is not None]
        if not vals:
            return None
        vals.sort()
        n_vals = len(vals)
        if n_vals < 5:
            return sum(vals) / n_vals
        k = int(n_vals * trim)
        if k * 2 >= n_vals:
            return sum(vals) / n_vals
        trimmed = vals[k:n_vals - k]
        return sum(trimmed) / len(trimmed)

    pace1_samples: List[float] = []
    pace2_samples: List[float] = []
    hr1_samples: List[float] = []
    hr2_samples: List[float] = []
    for i in range(1, n):
        dt = time[i] - time[i - 1]
        dd = dist[i] - dist[i - 1]
        if dt <= 0 or dd <= 0:
            continue
        pace_sec = dt / (dd / 1000)
        if dist[i] <= half_dist:
            pace1_samples.append(pace_sec)
            if hr[i] is not None:
                hr1_samples.append(hr[i])
        else:
            pace2_samples.append(pace_sec)
            if hr[i] is not None:
                hr2_samples.append(hr[i])

    pace1 = trimmed_mean(pace1_samples)
    pace2 = trimmed_mean(pace2_samples)
    hr1 = trimmed_mean(hr1_samples)
    hr2 = trimmed_mean(hr2_samples)
    if not pace1 or not pace2 or not hr1 or not hr2:
        return None, None
    if hr1 <= 0 or hr2 <= 0:
        return None, None

    hr_drift = hr2 - hr1
    decoupling = ((pace2 / pace1) / (hr2 / hr1) - 1) * 100
    if decoupling > 50:
        decoupling = 50
    if decoupling < -50:
        decoupling = -50
    return hr_drift, decoupling


def compute_hr_zones(
    time: List[float],
    hr: List[Optional[float]],
    hr_rest: float,
    hr_max: float,
) -> Optional[Dict[str, float]]:
    if not time or not hr:
        return None
    n = min(len(time), len(hr))
    if n < 2:
        return None
    if hr_max <= hr_rest:
        return None
    hrr = hr_max - hr_rest
    # HRR bands
    z1_lo = hr_rest + 0.50 * hrr
    z2_lo = hr_rest + 0.60 * hrr
    z3_lo = hr_rest + 0.70 * hrr
    z4_lo = hr_rest + 0.80 * hrr
    z5_lo = hr_rest + 0.90 * hrr

    z1 = z2 = z3 = z4 = z5 = 0.0
    total = 0.0
    for i in range(1, n):
        dt = time[i] - time[i - 1]
        if dt <= 0:
            continue
        v = hr[i]
        if v is None:
            continue
        if v < 40 or v > 220:
            continue
        total += dt
        if v < z2_lo:
            z1 += dt
        elif v < z3_lo:
            z2 += dt
        elif v < z4_lo:
            z3 += dt
        elif v < z5_lo:
            z4 += dt
        else:
            z5 += dt
    if total <= 0:
        return None
    zone_score = (z1 * 1 + z2 * 2 + z3 * 3 + z4 * 4 + z5 * 5) / total
    if zone_score < 1.5:
        zone_label = "Recovery"
    elif zone_score < 2.5:
        zone_label = "Endurance"
    elif zone_score < 3.5:
        zone_label = "Tempo"
    elif zone_score < 4.5:
        zone_label = "Threshold"
    else:
        zone_label = "VO2"
    return {
        "z1_s": z1,
        "z2_s": z2,
        "z3_s": z3,
        "z4_s": z4,
        "z5_s": z5,
        "zone_score": zone_score,
        "zone_label": zone_label,
        "hr_max_used": hr_max,
        "hr_rest_used": hr_rest,
        "zone_method": HR_ZONE_METHOD,
    }


def load_weather(conn: sqlite3.Connection, activity_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT raw_json FROM weather_raw WHERE activity_id=?",
        (activity_id,),
    ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


def upsert_activity_norm(conn: sqlite3.Connection, activity_id: str, values: dict) -> None:
    conn.execute(
        """
        INSERT INTO activities_norm(
          activity_id, avg_hr_norm, flat_pace_sec, flat_pace_weather_sec, cadence_avg,
          stride_len, hr_drift, decoupling, hr_norm_json, pace_smooth_json,
          cadence_smooth_json, hr_smooth_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(activity_id) DO UPDATE SET
          avg_hr_norm=excluded.avg_hr_norm,
          flat_pace_sec=excluded.flat_pace_sec,
          flat_pace_weather_sec=excluded.flat_pace_weather_sec,
          cadence_avg=excluded.cadence_avg,
          stride_len=excluded.stride_len,
          hr_drift=excluded.hr_drift,
          decoupling=excluded.decoupling,
          hr_norm_json=excluded.hr_norm_json,
          pace_smooth_json=excluded.pace_smooth_json,
          cadence_smooth_json=excluded.cadence_smooth_json,
          hr_smooth_json=excluded.hr_smooth_json
        """,
        (
            activity_id,
            values.get("avg_hr_norm"),
            values.get("flat_pace_sec"),
            values.get("flat_pace_weather_sec"),
            values.get("cadence_avg"),
            values.get("stride_len"),
            values.get("hr_drift"),
            values.get("decoupling"),
            values.get("hr_norm_json"),
            values.get("pace_smooth_json"),
            values.get("cadence_smooth_json"),
            values.get("hr_smooth_json"),
        ),
    )


def upsert_activity_calc(conn: sqlite3.Connection, activity_id: str, values: dict) -> None:
    conn.execute(
        """
        INSERT INTO activities_calc(
          activity_id, start_time, activity_type, distance_m, moving_s, avg_speed_mps, avg_hr_raw,
          avg_hr_norm, flat_pace_sec, flat_pace_weather_sec, flat_time, flat_dist, cadence_avg,
          stride_len, hr_drift, decoupling, hr_z1_s, hr_z2_s, hr_z3_s, hr_z4_s, hr_z5_s,
          hr_zone_score, hr_zone_label, hr_max_used, hr_rest_used, hr_zone_method, user_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(activity_id) DO UPDATE SET
          start_time=excluded.start_time,
          activity_type=excluded.activity_type,
          distance_m=excluded.distance_m,
          moving_s=excluded.moving_s,
          avg_speed_mps=excluded.avg_speed_mps,
          avg_hr_raw=excluded.avg_hr_raw,
          avg_hr_norm=excluded.avg_hr_norm,
          flat_pace_sec=excluded.flat_pace_sec,
          flat_pace_weather_sec=excluded.flat_pace_weather_sec,
          flat_time=excluded.flat_time,
          flat_dist=excluded.flat_dist,
          cadence_avg=excluded.cadence_avg,
          stride_len=excluded.stride_len,
          hr_drift=excluded.hr_drift,
          decoupling=excluded.decoupling,
          hr_z1_s=excluded.hr_z1_s,
          hr_z2_s=excluded.hr_z2_s,
          hr_z3_s=excluded.hr_z3_s,
          hr_z4_s=excluded.hr_z4_s,
          hr_z5_s=excluded.hr_z5_s,
          hr_zone_score=excluded.hr_zone_score,
          hr_zone_label=excluded.hr_zone_label,
          hr_max_used=excluded.hr_max_used,
          hr_rest_used=excluded.hr_rest_used,
          hr_zone_method=excluded.hr_zone_method,
          user_id=excluded.user_id
        """,
        (
            activity_id,
            values.get("start_time"),
            values.get("activity_type"),
            values.get("distance_m"),
            values.get("moving_s"),
            values.get("avg_speed_mps"),
            values.get("avg_hr_raw"),
            values.get("avg_hr_norm"),
            values.get("flat_pace_sec"),
            values.get("flat_pace_weather_sec"),
            values.get("flat_time"),
            values.get("flat_dist"),
            values.get("cadence_avg"),
            values.get("stride_len"),
            values.get("hr_drift"),
            values.get("decoupling"),
            values.get("hr_z1_s"),
            values.get("hr_z2_s"),
            values.get("hr_z3_s"),
            values.get("hr_z4_s"),
            values.get("hr_z5_s"),
            values.get("hr_zone_score"),
            values.get("hr_zone_label"),
            values.get("hr_max_used"),
            values.get("hr_rest_used"),
            values.get("hr_zone_method"),
            values.get("user_id"),
        ),
    )


def upsert_activity_core(conn: sqlite3.Connection, values: dict) -> None:
    conn.execute(
        """
        INSERT INTO activities(
          source_id, activity_id, activity_type, start_time, name,
          distance_m, moving_s, elev_gain, user_id
        ) VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(activity_id) DO UPDATE SET
          source_id=excluded.source_id,
          activity_type=excluded.activity_type,
          start_time=excluded.start_time,
          name=excluded.name,
          distance_m=excluded.distance_m,
          moving_s=excluded.moving_s,
          elev_gain=excluded.elev_gain,
          user_id=excluded.user_id
        """,
        (
            values.get("source_id"),
            values.get("activity_id"),
            values.get("activity_type"),
            values.get("start_time"),
            values.get("name"),
            values.get("distance_m"),
            values.get("moving_s"),
            values.get("elev_gain"),
            values.get("user_id"),
        ),
    )


def upsert_activity_run_details(conn: sqlite3.Connection, values: dict) -> None:
    conn.execute(
        """
        INSERT INTO activity_details_run(
          activity_id, avg_hr_raw, avg_hr_norm, flat_pace_sec, flat_pace_weather_sec,
          cadence_avg, stride_len, hr_drift, decoupling,
          hr_z1_s, hr_z2_s, hr_z3_s, hr_z4_s, hr_z5_s,
          hr_zone_score, hr_zone_label, hr_max_used, hr_rest_used, hr_zone_method
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(activity_id) DO UPDATE SET
          avg_hr_raw=excluded.avg_hr_raw,
          avg_hr_norm=excluded.avg_hr_norm,
          flat_pace_sec=excluded.flat_pace_sec,
          flat_pace_weather_sec=excluded.flat_pace_weather_sec,
          cadence_avg=excluded.cadence_avg,
          stride_len=excluded.stride_len,
          hr_drift=excluded.hr_drift,
          decoupling=excluded.decoupling,
          hr_z1_s=excluded.hr_z1_s,
          hr_z2_s=excluded.hr_z2_s,
          hr_z3_s=excluded.hr_z3_s,
          hr_z4_s=excluded.hr_z4_s,
          hr_z5_s=excluded.hr_z5_s,
          hr_zone_score=excluded.hr_zone_score,
          hr_zone_label=excluded.hr_zone_label,
          hr_max_used=excluded.hr_max_used,
          hr_rest_used=excluded.hr_rest_used,
          hr_zone_method=excluded.hr_zone_method
        """,
        (
            values.get("activity_id"),
            values.get("avg_hr_raw"),
            values.get("avg_hr_norm"),
            values.get("flat_pace_sec"),
            values.get("flat_pace_weather_sec"),
            values.get("cadence_avg"),
            values.get("stride_len"),
            values.get("hr_drift"),
            values.get("decoupling"),
            values.get("hr_z1_s"),
            values.get("hr_z2_s"),
            values.get("hr_z3_s"),
            values.get("hr_z4_s"),
            values.get("hr_z5_s"),
            values.get("hr_zone_score"),
            values.get("hr_zone_label"),
            values.get("hr_max_used"),
            values.get("hr_rest_used"),
            values.get("hr_zone_method"),
        ),
    )


def process():
    if not DB_PATH.exists():
        raise SystemExit("DB not initialized. Run scripts/init_db.py")

    started_at = datetime.now(timezone.utc)
    activities_processed = 0
    streams_processed = 0
    weather_processed = 0
    weather_distinct = 0
    run_id = None
    status = "running"
    message = None

    with sqlite3.connect(DB_PATH) as conn:
        configure_sqlite(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
              id INTEGER PRIMARY KEY,
              started_at TEXT NOT NULL,
              finished_at TEXT,
              status TEXT NOT NULL,
              activities_processed INTEGER,
              streams_processed INTEGER,
              weather_processed INTEGER,
              message TEXT
            )
            """
        )
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO pipeline_runs(started_at, status)
            VALUES(?,?)
            """,
            (started_at.isoformat(), status),
        )
        run_id = cur.lastrowid
        conn.commit()

        activities_processed = conn.execute("SELECT COUNT(*) FROM activities_raw").fetchone()[0]
        streams_processed = conn.execute("SELECT COUNT(*) FROM streams_raw").fetchone()[0]
        weather_processed = conn.execute("SELECT COUNT(*) FROM weather_raw").fetchone()[0]
        weather_distinct = conn.execute("SELECT COUNT(DISTINCT activity_id) FROM weather_raw").fetchone()[0]

        rows = conn.execute(
            "SELECT source_id, activity_id, start_time, raw_json, user_id FROM activities_raw"
        ).fetchall()
        runs_for_weekly: List[dict] = []

        try:
            for source_id, activity_id, start_time, raw_json, user_id in rows:
                try:
                    raw = json.loads(raw_json)
                except json.JSONDecodeError:
                    continue

                streams = load_streams(conn, activity_id)
                time_stream = stream_data(streams, "time") or []
                dist_stream = stream_data(streams, "distance") or []
                cadence_stream = stream_data(streams, "cadence")
                hr_stream = stream_data(streams, "heartrate")
                flat = compute_flat_pace(streams)
                avg_hr_norm, hr_norm, _ = normalize_hr(streams)
                hr_drift, decoupling = compute_run_drift(streams, hr_norm)

                weather = load_weather(conn, activity_id)
                flat_weather = adjust_pace_for_weather(
                    flat.flat_pace_sec_per_km if flat else None, weather
                )

                distance_m = raw.get("distance") or 0.0
                moving_s = raw.get("moving_time") or 0.0
                avg_speed_mps = raw.get("average_speed")
                if avg_speed_mps is None and distance_m and moving_s:
                    avg_speed_mps = distance_m / moving_s

                avg_hr_raw = raw.get("average_heartrate")

                pace_smooth = None
                pace_smooth_avg = None
                if time_stream and dist_stream and len(time_stream) == len(dist_stream):
                    pace_smooth, pace_smooth_avg = smooth_pace(time_stream, dist_stream)

                cadence_smooth = None
                cadence_smooth_avg = None
                if cadence_stream:
                    cadence_smooth, cadence_smooth_avg = smooth_cadence(cadence_stream)

                hr_source = hr_norm if hr_norm else (hr_stream or [])
                hr_smooth = None
                hr_smooth_avg = None
                if hr_source:
                    hr_smooth, hr_smooth_avg = smooth_hr(hr_source)
                if hr_smooth_avg is not None:
                    avg_hr_norm = hr_smooth_avg

                zone_data = None
                if time_stream and hr_source:
                    zone_data = compute_hr_zones(time_stream, hr_source, HR_REST, HR_MAX)

                cadence_avg = cadence_smooth_avg or compute_cadence(streams)
                stride_len = (
                    (avg_speed_mps * 60 / cadence_avg)
                    if avg_speed_mps is not None and cadence_avg
                    else None
                )

                hr_norm_json = json.dumps(hr_norm) if hr_norm else None
                pace_smooth_json = json.dumps(pace_smooth) if pace_smooth else None
                cadence_smooth_json = json.dumps(cadence_smooth) if cadence_smooth else None
                hr_smooth_json = json.dumps(hr_smooth) if hr_smooth else None

                upsert_activity_norm(
                    conn,
                    activity_id,
                    {
                        "avg_hr_norm": avg_hr_norm,
                        "flat_pace_sec": flat.flat_pace_sec_per_km if flat else None,
                        "flat_pace_weather_sec": flat_weather,
                        "cadence_avg": cadence_avg,
                        "stride_len": stride_len,
                        "hr_drift": hr_drift,
                        "decoupling": decoupling,
                        "hr_norm_json": hr_norm_json,
                        "pace_smooth_json": pace_smooth_json,
                        "cadence_smooth_json": cadence_smooth_json,
                        "hr_smooth_json": hr_smooth_json,
                    },
                )

                activity_type = normalize_activity_type(str(raw.get("sport_type") or raw.get("type") or ""))
                name = str(raw.get("name") or "").strip()
                elev_gain = raw.get("total_elevation_gain")

                upsert_activity_calc(
                    conn,
                    activity_id,
                    {
                        "start_time": start_time,
                        "activity_type": activity_type,
                        "distance_m": distance_m,
                        "moving_s": moving_s,
                        "avg_speed_mps": avg_speed_mps,
                        "avg_hr_raw": avg_hr_raw,
                        "avg_hr_norm": avg_hr_norm,
                        "flat_pace_sec": flat.flat_pace_sec_per_km if flat else None,
                        "flat_pace_weather_sec": flat_weather,
                        "flat_time": flat.flat_time if flat else None,
                        "flat_dist": flat.dist if flat else None,
                        "cadence_avg": cadence_avg,
                        "stride_len": stride_len,
                        "hr_drift": hr_drift,
                        "decoupling": decoupling,
                        "hr_z1_s": zone_data.get("z1_s") if zone_data else None,
                        "hr_z2_s": zone_data.get("z2_s") if zone_data else None,
                        "hr_z3_s": zone_data.get("z3_s") if zone_data else None,
                        "hr_z4_s": zone_data.get("z4_s") if zone_data else None,
                        "hr_z5_s": zone_data.get("z5_s") if zone_data else None,
                        "hr_zone_score": zone_data.get("zone_score") if zone_data else None,
                        "hr_zone_label": zone_data.get("zone_label") if zone_data else None,
                        "hr_max_used": zone_data.get("hr_max_used") if zone_data else None,
                        "hr_rest_used": zone_data.get("hr_rest_used") if zone_data else None,
                        "hr_zone_method": zone_data.get("zone_method") if zone_data else None,
                        "user_id": user_id,
                    },
                )

                upsert_activity_core(
                    conn,
                    {
                        "source_id": source_id,
                        "activity_id": activity_id,
                        "activity_type": activity_type,
                        "start_time": start_time,
                        "name": name,
                        "distance_m": distance_m,
                        "moving_s": moving_s,
                        "elev_gain": elev_gain,
                        "user_id": user_id,
                    },
                )

                if activity_type.lower() == "run":
                    upsert_activity_run_details(
                        conn,
                        {
                            "activity_id": activity_id,
                            "avg_hr_raw": avg_hr_raw,
                            "avg_hr_norm": avg_hr_norm,
                            "flat_pace_sec": flat.flat_pace_sec_per_km if flat else None,
                            "flat_pace_weather_sec": flat_weather,
                            "cadence_avg": cadence_avg,
                            "stride_len": stride_len,
                            "hr_drift": hr_drift,
                            "decoupling": decoupling,
                            "hr_z1_s": zone_data.get("z1_s") if zone_data else None,
                            "hr_z2_s": zone_data.get("z2_s") if zone_data else None,
                            "hr_z3_s": zone_data.get("z3_s") if zone_data else None,
                            "hr_z4_s": zone_data.get("z4_s") if zone_data else None,
                            "hr_z5_s": zone_data.get("z5_s") if zone_data else None,
                            "hr_zone_score": zone_data.get("zone_score") if zone_data else None,
                            "hr_zone_label": zone_data.get("zone_label") if zone_data else None,
                            "hr_max_used": zone_data.get("hr_max_used") if zone_data else None,
                            "hr_rest_used": zone_data.get("hr_rest_used") if zone_data else None,
                            "hr_zone_method": zone_data.get("zone_method") if zone_data else None,
                        },
                    )
                    runs_for_weekly.append(
                        {
                            "activity_id": activity_id,
                            "start_time": start_time,
                            "distance_m": distance_m,
                            "moving_s": moving_s,
                            "avg_speed_mps": avg_speed_mps,
                            "avg_hr_raw": avg_hr_raw,
                            "avg_hr_norm": avg_hr_norm,
                            "flat_pace_sec": flat.flat_pace_sec_per_km if flat else None,
                            "flat_pace_weather_sec": flat_weather,
                            "cadence_avg": cadence_avg,
                            "stride_len": stride_len,
                            "hr_drift": hr_drift,
                            "decoupling": decoupling,
                            "hr_zone_score": zone_data.get("zone_score") if zone_data else None,
                            "hr_zone_label": zone_data.get("zone_label") if zone_data else None,
                            "flat_time": flat.flat_time if flat else None,
                            "flat_dist": flat.dist if flat else None,
                        }
                    )

            conn.commit()

            status = "ok"
        except Exception as exc:
            status = "error"
            message = str(exc)
            print(f"Pipeline error (run_id={run_id}): {message}")

        finished_at = datetime.now(timezone.utc)
        duration_sec = (finished_at - started_at).total_seconds()
        conn.execute(
            """
            UPDATE pipeline_runs
            SET finished_at=?, status=?, activities_processed=?, streams_processed=?, weather_processed=?, message=?, duration_sec=?
            WHERE id=?
            """,
            (
                finished_at.isoformat(),
                status,
                activities_processed,
                streams_processed,
                weather_distinct,
                message,
                duration_sec,
                run_id,
            ),
        )
        conn.commit()

    LAST_UPDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_UPDATE_PATH.write_text(
        json.dumps({"last_update": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )


def main():
    process()
    print("Processed raw -> normalized -> calculated (views read from DB)")


if __name__ == "__main__":
    main()
