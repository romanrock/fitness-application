import json
import logging
import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query, HTTPException

from ..cache import get_or_set
from ..deps import get_current_user
from ..schemas import (
    ActivityDetailResponse,
    ActivityRouteResponse,
    ActivitySeriesResponse,
    ActivityTotalsResponse,
    ActivitiesResponse,
    LapsResponse,
    StatsResponse,
    StreamsResponse,
    SummaryResponse,
    WeeklyResponse,
)
from ..utils import build_date_filter, db_exists, decode_polyline, dict_rows, get_last_update, get_db


router_public = APIRouter()
router_api = APIRouter()

logger = logging.getLogger("fitness.api")

CACHE_TTL_SECONDS = 45
MAX_ACTIVITIES_LIMIT = 200


@router_public.get("/stats", response_model=StatsResponse)
def stats(user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM activities_raw WHERE user_id=?", (user["id"],))
        activities = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM streams_raw WHERE user_id=?", (user["id"],))
        streams = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM weather_raw WHERE user_id=?", (user["id"],))
        weather = cur.fetchone()[0]
        return {"activities_raw": activities, "streams_raw": streams, "weather_raw": weather}


@router_public.get("/weekly", response_model=WeeklyResponse)
def weekly(limit: int = 52, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}

    last_update = get_last_update()
    cache_key = f"weekly:{user['id']}:{limit}"

    def compute():
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                  week, runs, distance_m, moving_s, avg_pace_sec, flat_pace_sec,
                  flat_pace_weather_sec, avg_hr_norm, cadence_avg, stride_len,
                  eff_index, roll_pace_sec, roll_hr, roll_dist, monotony, strain
                FROM metrics_weekly
                WHERE user_id = ?
                ORDER BY week DESC
                LIMIT ?
                """,
                (user["id"], limit),
            )
            return {"weekly": list(dict_rows(cur))}

    return get_or_set(cache_key, CACHE_TTL_SECONDS, last_update, compute)


@router_public.get("/activities", response_model=ActivitiesResponse)
def activities(
    activity_type: str = Query("run", alias="type"),
    limit: int = 100,
    offset: int = 0,
    start: str | None = None,
    end: str | None = None,
    user=Depends(get_current_user),
):
    if not db_exists():
        return {"db": "missing"}
    limit = max(1, min(MAX_ACTIVITIES_LIMIT, limit))
    with get_db() as conn:
        cur = conn.cursor()
        date_clause, date_params = build_date_filter(start, end)
        cur.execute(
            f"""
            SELECT
              a.activity_id,
              a.start_time,
              a.activity_type,
              a.name,
              a.distance_m,
              a.moving_s,
              a.elev_gain,
              d.avg_hr_norm,
              d.flat_pace_sec,
              d.flat_pace_weather_sec,
              d.cadence_avg,
              d.stride_len,
              d.hr_drift,
              d.decoupling,
              d.hr_zone_score,
              d.hr_zone_label
            FROM activities a
            LEFT JOIN activity_details_run d ON d.activity_id = a.activity_id
            WHERE lower(a.activity_type) = lower(?)
              AND a.user_id = ?
              {date_clause}
            ORDER BY a.start_time DESC
            LIMIT ? OFFSET ?
            """,
            (activity_type, user["id"], *date_params, limit, offset),
        )
        return {"activities": list(dict_rows(cur))}


@router_api.get("/activity_totals", response_model=ActivityTotalsResponse)
def activity_totals(start: str | None = None, end: str | None = None, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    last_update = get_last_update()
    cache_key = f"totals:{user['id']}:{start}:{end}"

    def compute():
        with get_db() as conn:
            cur = conn.cursor()
            date_clause, date_params = build_date_filter(start, end)
            cur.execute(
                f"""
                SELECT lower(a.activity_type) AS activity_type,
                       COUNT(*) AS count,
                       COALESCE(SUM(a.distance_m), 0) AS distance_m
                FROM activities a
                WHERE a.user_id = ?
                  {date_clause}
                GROUP BY lower(a.activity_type)
                """,
                (user["id"], *date_params),
            )
            return {"totals": list(dict_rows(cur))}

    return get_or_set(cache_key, CACHE_TTL_SECONDS, last_update, compute)


@router_public.get("/activity/{activity_id}", response_model=ActivityDetailResponse)
def activity_detail(activity_id: str, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              a.activity_id,
              a.start_time,
              a.activity_type,
              a.name,
              a.distance_m,
              a.moving_s,
              a.elev_gain,
              d.avg_hr_raw,
              d.avg_hr_norm,
              d.flat_pace_sec,
              d.flat_pace_weather_sec,
              d.cadence_avg,
              d.stride_len,
              d.hr_drift,
              d.decoupling,
              n.hr_norm_json
            FROM activities a
            LEFT JOIN activity_details_run d ON d.activity_id = a.activity_id
            LEFT JOIN activities_norm n ON n.activity_id = a.activity_id
            WHERE a.activity_id = ?
              AND a.user_id = ?
            """,
            (activity_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not_found")
        cols = [c[0] for c in cur.description]
        data = {cols[i]: row[i] for i in range(len(cols))}
        # Add weather context when available.
        weather = conn.execute(
            "SELECT raw_json FROM weather_raw WHERE activity_id=? AND user_id=?",
            (activity_id, user["id"]),
        ).fetchone()
        if weather and weather[0]:
            try:
                data["weather"] = json.loads(weather[0])
            except json.JSONDecodeError:
                data["weather"] = None
        else:
            data["weather"] = None
        return data


@router_public.get("/activity/{activity_id}/streams", response_model=StreamsResponse)
def activity_streams(activity_id: str, types: str = "time,distance,heartrate,cadence,altitude", downsample: int = 1, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    want = {t.strip() for t in types.split(",") if t.strip()}
    if not want:
        return {"streams": {}}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT stream_type, raw_json FROM streams_raw WHERE activity_id=? AND user_id=?",
            (activity_id, user["id"]),
        )
        out: Dict[str, Any] = {}
        for stream_type, raw_json in cur.fetchall():
            if stream_type not in want:
                continue
            try:
                payload = json.loads(raw_json)
                data = payload.get("data")
                if downsample > 1 and isinstance(data, list):
                    payload["data"] = data[::downsample]
                out[stream_type] = payload
            except json.JSONDecodeError:
                out[stream_type] = None
        return {"streams": out}


@router_public.get("/activity/{activity_id}/laps", response_model=LapsResponse)
def activity_laps(activity_id: str, lap_m: int = 1000, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT raw_json FROM streams_raw WHERE activity_id=? AND stream_type='distance' AND user_id=?",
            (activity_id, user["id"]),
        )
        dist_row = cur.fetchone()
        cur.execute(
            "SELECT raw_json FROM streams_raw WHERE activity_id=? AND stream_type='time' AND user_id=?",
            (activity_id, user["id"]),
        )
        time_row = cur.fetchone()
        cur.execute(
            "SELECT raw_json FROM streams_raw WHERE activity_id=? AND stream_type='altitude' AND user_id=?",
            (activity_id, user["id"]),
        )
        alt_row = cur.fetchone()
        if not dist_row or not time_row:
            return {"laps": []}
        try:
            dist = json.loads(dist_row[0]).get("data", [])
            time_stream = json.loads(time_row[0]).get("data", [])
            alt = json.loads(alt_row[0]).get("data", []) if alt_row and alt_row[0] else []
        except json.JSONDecodeError:
            return {"laps": []}
        if not dist or not time_stream or len(dist) != len(time_stream):
            return {"laps": []}

        def flat_pace_segment(start_idx: int, end_idx: int):
            total_dist = 0.0
            flat_time = 0.0
            has_alt = alt and len(alt) == len(dist)
            for j in range(start_idx + 1, end_idx + 1):
                dt = time_stream[j] - time_stream[j - 1]
                dd = dist[j] - dist[j - 1]
                if dt <= 0 or dd <= 0:
                    continue
                grade = 0.0
                if has_alt:
                    da = alt[j] - alt[j - 1]
                    grade = da / dd
                    if grade > 0.1:
                        grade = 0.1
                    if grade < -0.1:
                        grade = -0.1
                cost = 1 + 0.045 * grade + 0.35 * grade * grade
                pace_sec_per_m = dt / dd
                flat_sec_per_m = pace_sec_per_m * cost
                flat_time += flat_sec_per_m * dd
                total_dist += dd
            if total_dist <= 0:
                return None
            return (flat_time / total_dist) * 1000

        laps: List[Dict[str, Any]] = []
        next_mark = lap_m
        lap_start_idx = 0
        for i in range(1, len(dist)):
            if dist[i] >= next_mark:
                lap_time = time_stream[i] - time_stream[lap_start_idx]
                lap_dist = dist[i] - dist[lap_start_idx]
                pace_sec = (lap_time / (lap_dist / 1000)) if lap_dist > 0 else None
                elev_change = None
                if alt and len(alt) == len(dist):
                    elev_change = alt[i] - alt[lap_start_idx]
                flat_pace_sec = flat_pace_segment(lap_start_idx, i)
                laps.append(
                    {
                        "lap": len(laps) + 1,
                        "time": lap_time,
                        "distance_m": lap_dist,
                        "pace_sec": pace_sec,
                        "elev_change_m": elev_change,
                        "flat_pace_sec": flat_pace_sec,
                    }
                )
                lap_start_idx = i
                next_mark += lap_m

        # Final partial lap if remaining distance > 100m
        if dist[-1] - dist[lap_start_idx] > 100:
            lap_time = time_stream[-1] - time_stream[lap_start_idx]
            lap_dist = dist[-1] - dist[lap_start_idx]
            pace_sec = (lap_time / (lap_dist / 1000)) if lap_dist > 0 else None
            elev_change = None
            if alt and len(alt) == len(dist):
                elev_change = alt[-1] - alt[lap_start_idx]
            flat_pace_sec = flat_pace_segment(lap_start_idx, len(dist) - 1)
            laps.append(
                {
                    "lap": len(laps) + 1,
                    "time": lap_time,
                    "distance_m": lap_dist,
                    "pace_sec": pace_sec,
                    "elev_change_m": elev_change,
                    "flat_pace_sec": flat_pace_sec,
                }
            )
        return {"laps": laps}


@router_public.get("/activity/{activity_id}/summary", response_model=SummaryResponse)
def activity_summary(activity_id: str, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT stream_type FROM streams_raw WHERE activity_id=? AND user_id=?",
            (activity_id, user["id"]),
        )
        stream_types = {row[0] for row in cur.fetchall()}
        stream_status = {
            "has_time": "time" in stream_types,
            "has_distance": "distance" in stream_types,
            "has_hr": "heartrate" in stream_types,
            "has_altitude": "altitude" in stream_types,
            "has_cadence": "cadence" in stream_types,
        }
        summary_notes: List[str] = []
        if not (stream_status["has_time"] and stream_status["has_distance"]):
            summary_notes.append("missing_streams")
            logger.warning(
                "missing_streams activity_id=%s user_id=%s", activity_id, user["id"]
            )
        if not stream_status["has_hr"]:
            summary_notes.append("missing_hr_streams")
            logger.warning(
                "missing_hr_streams activity_id=%s user_id=%s", activity_id, user["id"]
            )
        cur.execute(
            """
            SELECT r.raw_json, c.distance_m, c.moving_s, a.elev_gain,
                   d.avg_hr_norm, d.avg_hr_raw, d.flat_pace_sec, d.cadence_avg, d.stride_len,
                   d.hr_z1_s, d.hr_z2_s, d.hr_z3_s, d.hr_z4_s, d.hr_z5_s,
                   d.hr_zone_score, d.hr_zone_label, d.hr_max_used, d.hr_rest_used, d.hr_zone_method,
                   n.pace_smooth_json
            FROM activities a
            LEFT JOIN activities_raw r ON r.activity_id = a.activity_id AND r.user_id = a.user_id
            LEFT JOIN activities_calc c ON c.activity_id = a.activity_id
            LEFT JOIN activity_details_run d ON d.activity_id = a.activity_id
            LEFT JOIN activities_norm n ON n.activity_id = a.activity_id
            WHERE a.activity_id = ?
              AND a.user_id = ?
            """,
            (activity_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not_found")
        raw = {}
        if row[0]:
            try:
                raw = json.loads(row[0])
            except json.JSONDecodeError:
                raw = {}

        distance_m = row[1]
        moving_s = row[2]
        elev_gain = row[3]
        avg_hr_norm = row[4]
        avg_hr_raw = row[5]
        flat_pace_sec = row[6]
        cadence_avg = row[7]
        stride_len = row[8]
        hr_z1_s = row[9]
        hr_z2_s = row[10]
        hr_z3_s = row[11]
        hr_z4_s = row[12]
        hr_z5_s = row[13]
        hr_zone_score = row[14]
        hr_zone_label = row[15]
        hr_max_used = row[16]
        hr_rest_used = row[17]
        hr_zone_method = row[18]
        pace_smooth_json = row[19]
        calories = raw.get("calories")
        if calories is None:
            kj = raw.get("kilojoules")
            if kj is not None:
                calories = round(kj * 0.239006)
        if calories is None and distance_m:
            try:
                weight_kg = float(os.getenv("FITNESS_WEIGHT_KG", "75"))
            except ValueError:
                weight_kg = 75.0
            calories = round((distance_m / 1000) * weight_kg)
        max_hr = raw.get("max_heartrate")

        avg_pace_sec = (moving_s / (distance_m / 1000)) if moving_s and distance_m else None
        best_pace_sec = None
        if pace_smooth_json:
            try:
                pace_series = [p for p in json.loads(pace_smooth_json) if p]
                pace_series = [p for p in pace_series if 150 <= p <= 900]
                if pace_series:
                    best_pace_sec = min(pace_series)
            except json.JSONDecodeError:
                best_pace_sec = None

        hr_zones = None
        if hr_max_used and hr_rest_used and moving_s:
            hrr = hr_max_used - hr_rest_used
            if hrr > 0:
                z1_lo = hr_rest_used + 0.50 * hrr
                z2_lo = hr_rest_used + 0.60 * hrr
                z3_lo = hr_rest_used + 0.70 * hrr
                z4_lo = hr_rest_used + 0.80 * hrr
                z5_lo = hr_rest_used + 0.90 * hrr
                total = moving_s or 0

                def pct(v):
                    return (v / total) * 100 if total else None

                hr_zones = [
                    {"zone": 1, "low": z1_lo, "high": z2_lo, "seconds": hr_z1_s, "pct": pct(hr_z1_s or 0)},
                    {"zone": 2, "low": z2_lo, "high": z3_lo, "seconds": hr_z2_s, "pct": pct(hr_z2_s or 0)},
                    {"zone": 3, "low": z3_lo, "high": z4_lo, "seconds": hr_z3_s, "pct": pct(hr_z3_s or 0)},
                    {"zone": 4, "low": z4_lo, "high": z5_lo, "seconds": hr_z4_s, "pct": pct(hr_z4_s or 0)},
                    {"zone": 5, "low": z5_lo, "high": hr_max_used, "seconds": hr_z5_s, "pct": pct(hr_z5_s or 0)},
                ]

        return {
            "distance_m": distance_m,
            "moving_s": moving_s,
            "elev_gain": elev_gain,
            "avg_pace_sec": avg_pace_sec,
            "best_pace_sec": best_pace_sec or flat_pace_sec,
            "avg_hr_norm": avg_hr_norm,
            "avg_hr_raw": avg_hr_raw,
            "max_hr": max_hr,
            "calories": calories,
            "cadence_avg": cadence_avg,
            "stride_len": stride_len,
            "flat_pace_sec": flat_pace_sec,
            "hr_zones": hr_zones,
            "hr_zone_score": hr_zone_score,
            "hr_zone_label": hr_zone_label,
            "hr_max_used": hr_max_used,
            "hr_rest_used": hr_rest_used,
            "hr_zone_method": hr_zone_method,
            "stream_status": stream_status,
            "summary_notes": summary_notes,
        }


@router_public.get("/activity/{activity_id}/series", response_model=ActivitySeriesResponse)
def activity_series(activity_id: str, downsample: int = 5, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT raw_json FROM streams_raw WHERE activity_id=? AND stream_type='time' AND user_id=?",
            (activity_id, user["id"]),
        )
        time_row = cur.fetchone()
        cur.execute(
            "SELECT raw_json FROM streams_raw WHERE activity_id=? AND stream_type='distance' AND user_id=?",
            (activity_id, user["id"]),
        )
        dist_row = cur.fetchone()
        cur.execute(
            "SELECT raw_json FROM streams_raw WHERE activity_id=? AND stream_type='heartrate' AND user_id=?",
            (activity_id, user["id"]),
        )
        hr_row = cur.fetchone()
        cur.execute(
            "SELECT hr_norm_json FROM activities_norm WHERE activity_id=?",
            (activity_id,),
        )
        hr_norm_row = cur.fetchone()
        cur.execute(
            "SELECT pace_smooth_json, cadence_smooth_json, hr_smooth_json FROM activities_norm WHERE activity_id=?",
            (activity_id,),
        )
        smooth_row = cur.fetchone()
        cur.execute(
            "SELECT raw_json FROM streams_raw WHERE activity_id=? AND stream_type='cadence' AND user_id=?",
            (activity_id, user["id"]),
        )
        cad_row = cur.fetchone()
        cur.execute(
            "SELECT raw_json FROM streams_raw WHERE activity_id=? AND stream_type='altitude' AND user_id=?",
            (activity_id, user["id"]),
        )
        alt_row = cur.fetchone()
        if not time_row or not dist_row:
            logger.warning(
                "missing_streams_series activity_id=%s user_id=%s has_time=%s has_distance=%s",
                activity_id,
                user["id"],
                bool(time_row),
                bool(dist_row),
            )
            return {"series": {}}

        def load_data(row):
            try:
                return json.loads(row[0]).get("data", [])
            except json.JSONDecodeError:
                return []

        time_stream = load_data(time_row)
        dist = load_data(dist_row)
        hr = load_data(hr_row) if hr_row else []
        hr_norm = []
        if hr_norm_row and hr_norm_row[0]:
            try:
                hr_norm = json.loads(hr_norm_row[0])
            except json.JSONDecodeError:
                hr_norm = []
        pace_smooth = cadence_smooth = hr_smooth = []
        if smooth_row:
            try:
                pace_smooth = json.loads(smooth_row[0]) if smooth_row[0] else []
            except json.JSONDecodeError:
                pace_smooth = []
            try:
                cadence_smooth = json.loads(smooth_row[1]) if smooth_row[1] else []
            except json.JSONDecodeError:
                cadence_smooth = []
            try:
                hr_smooth = json.loads(smooth_row[2]) if smooth_row[2] else []
            except json.JSONDecodeError:
                hr_smooth = []
        # If smoothed arrays are present but contain only nulls, treat as missing
        if pace_smooth and not any(v is not None for v in pace_smooth):
            pace_smooth = []
        if cadence_smooth and not any(v is not None for v in cadence_smooth):
            cadence_smooth = []
        if hr_smooth and not any(v is not None for v in hr_smooth):
            hr_smooth = []
        cad = load_data(cad_row) if cad_row else []
        alt = load_data(alt_row) if alt_row else []

        if not time_stream or not dist or len(time_stream) != len(dist):
            return {"series": {}}

        out_time = time_stream[::downsample]
        out_dist = dist[::downsample]
        out = {
            "time": out_time,
            "pace": (pace_smooth[::downsample] if pace_smooth else []),
            "hr": (hr_smooth if hr_smooth else (hr_norm if hr_norm else hr))[::downsample] if (hr_smooth or hr_norm or hr) else [],
            "cadence": (cadence_smooth if cadence_smooth else cad)[::downsample] if (cadence_smooth or cad) else [],
            "elevation": alt[::downsample] if alt else [],
        }

        def forward_fill(values):
            last = None
            filled = []
            for v in values:
                if v is None:
                    filled.append(last)
                else:
                    last = v
                    filled.append(v)
            return filled

        if not out["pace"] or not any(v is not None for v in out["pace"]):
            for i in range(1, len(time_stream), downsample):
                dt = time_stream[i] - time_stream[i - 1]
                dd = dist[i] - dist[i - 1]
                pace = (dt / (dd / 1000)) if dd > 0 else None
                out["pace"].append(pace)

        out["pace"] = forward_fill(out["pace"])
        out["hr"] = forward_fill(out["hr"])
        out["cadence"] = forward_fill(out["cadence"])

        def rolling_distance_avg(distances, values, window_m=200):
            if not distances or not values:
                return values
            out_vals = []
            start_idx = 0
            for i, d in enumerate(distances):
                while start_idx < i and distances[start_idx] < d - window_m:
                    start_idx += 1
                window = [v for v in values[start_idx:i + 1] if v is not None]
                out_vals.append(sum(window) / len(window) if window else values[i])
            return out_vals

        out["pace"] = rolling_distance_avg(out_dist, out["pace"], window_m=200)

        return {"series": out}


@router_public.get("/activity/{activity_id}/route", response_model=ActivityRouteResponse)
def activity_route(activity_id: str, downsample: int = 5, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT raw_json FROM streams_raw WHERE activity_id=? AND stream_type='latlng' AND user_id=?",
            (activity_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                "SELECT raw_json FROM activities_raw WHERE activity_id=? AND user_id=?",
                (activity_id, user["id"]),
            )
            activity_row = cur.fetchone()
            if not activity_row:
                return {"route": []}
            try:
                activity = json.loads(activity_row[0])
                summary_polyline = (activity.get("map") or {}).get("summary_polyline")
                if summary_polyline:
                    coords = decode_polyline(summary_polyline)
                    return {"route": coords[::downsample]}
            except json.JSONDecodeError:
                pass
            return {"route": []}
        try:
            payload = json.loads(row[0])
            latlng = payload.get("data") or []
            return {"route": latlng[::downsample]}
        except json.JSONDecodeError:
            return {"route": []}
