import json
import time
import statistics
from typing import Dict

from fastapi import APIRouter, Depends

from ..cache import get_or_set
from ..deps import get_current_user
from ..schemas import (
    InsightsContextRequest,
    InsightsContextResponse,
    InsightsDailyResponse,
    InsightsEvaluateRequest,
    InsightsEvaluateResponse,
    InsightsResponse,
    InsightsSeriesResponse,
)
from ..utils import compute_vdot, db_exists, get_db, get_last_update, linear_slope, week_key


router = APIRouter()

CACHE_TTL_SECONDS = 45


@router.get("/insights", response_model=InsightsResponse)
def insights(user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}

    last_update = get_last_update()
    cache_key = f"insights:{user['id']}"

    def compute():
        now = time.time()
        one_year_ago = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 365 * 24 * 3600))
        days_28_ago = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 28 * 24 * 3600))
        days_7_ago = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 7 * 24 * 3600))
        with get_db() as conn:
            cur = conn.cursor()

            # PBs from segments (if available).
            cur.execute(
                """
                SELECT distance_m, time_s, activity_id, date
                FROM segments_best
                WHERE scope = 'best_all' AND distance_m IN (5000, 10000)
                """
            )
            pb_all: Dict[int, Dict[str, object]] = {}
            for dist, time_s, activity_id, date in cur.fetchall():
                pb_all[int(dist)] = {
                    "time_s": time_s,
                    "activity_id": activity_id,
                    "date": date,
                }

            cur.execute(
                """
                SELECT a.activity_id, a.start_time, c.distance_m, c.moving_s
                FROM activities a
                JOIN activities_calc c ON c.activity_id = a.activity_id
                WHERE lower(a.activity_type) = 'run'
                  AND a.user_id = ?
                  AND a.start_time >= ?
                  AND c.distance_m IS NOT NULL
                  AND c.moving_s IS NOT NULL
                  AND c.moving_s > 0
                """,
                (user["id"], one_year_ago),
            )
            best_vdot = None
            best_source = None
            for activity_id, start_time, distance_m, moving_s in cur.fetchall():
                if distance_m is None or moving_s is None:
                    continue
                if distance_m < 5000:
                    continue
                vdot = compute_vdot(distance_m, moving_s)
                if vdot is None:
                    continue
                if best_vdot is None or vdot > best_vdot:
                    best_vdot = vdot
                    best_source = {
                        "activity_id": activity_id,
                        "start_time": start_time,
                        "distance_m": distance_m,
                        "moving_s": moving_s,
                    }

            # Best 5K/10K in last 12 months (full activity bests).
            best_12m: Dict[int, Dict[str, object]] = {}
            cur.execute(
                """
                SELECT a.activity_id, a.start_time, c.distance_m, c.moving_s
                FROM activities a
                JOIN activities_calc c ON c.activity_id = a.activity_id
                WHERE lower(a.activity_type) = 'run'
                  AND a.user_id = ?
                  AND a.start_time >= ?
                  AND c.distance_m >= 5000
                  AND c.moving_s > 0
                """,
                (user["id"], one_year_ago),
            )
            for activity_id, start_time, distance_m, moving_s in cur.fetchall():
                dist = float(distance_m)
                pace = moving_s / (dist / 1000)
                if dist >= 5000:
                    prev = best_12m.get(5000)
                    if not prev or pace < prev["pace"]:  # type: ignore[index]
                        best_12m[5000] = {
                            "time_s": moving_s,
                            "activity_id": activity_id,
                            "date": start_time,
                            "pace": pace,
                        }
                if dist >= 10000:
                    prev = best_12m.get(10000)
                    if not prev or pace < prev["pace"]:  # type: ignore[index]
                        best_12m[10000] = {
                            "time_s": moving_s,
                            "activity_id": activity_id,
                            "date": start_time,
                            "pace": pace,
                        }

            # Estimated bests from segment PBs (Riegel).
            cur.execute(
                """
                SELECT distance_m, time_s
                FROM segments_best
                WHERE scope IN ('best_12w', 'best_all')
                  AND distance_m IN (3000, 5000, 10000)
                ORDER BY CASE scope WHEN 'best_12w' THEN 0 ELSE 1 END
                """
            )
            segment_best: Dict[int, float] = {}
            for dist, time_s in cur.fetchall():
                if dist not in segment_best:
                    segment_best[int(dist)] = time_s

            def riegel(t1, d1, d2, exp=1.06):
                return t1 * ((d2 / d1) ** exp)

            est_5k = None
            est_10k = None
            if 3000 in segment_best:
                est_5k = riegel(segment_best[3000], 3000, 5000)
                est_10k = riegel(segment_best[3000], 3000, 10000)
            elif 5000 in segment_best:
                est_10k = riegel(segment_best[5000], 5000, 10000)
            elif 10000 in segment_best:
                est_5k = riegel(segment_best[10000], 10000, 5000)

            cur.execute(
                """
                SELECT week, avg_pace_sec, avg_hr_norm, eff_index
                FROM metrics_weekly
                WHERE user_id = ?
                ORDER BY week DESC
                LIMIT 12
                """,
                (user["id"],),
            )
            rows = cur.fetchall()
            rows = list(reversed(rows))
            pace_series = [r[1] for r in rows if r[1] is not None]
            hr_series = [r[2] for r in rows if r[2] is not None]
            eff_series = [r[3] for r in rows if r[3] is not None]

            pace_trend = linear_slope(pace_series)
            hr_trend = linear_slope(hr_series)
            eff_trend = linear_slope(eff_series)

            cur.execute(
                """
                SELECT monotony, strain, week
                FROM metrics_weekly
                WHERE user_id = ?
                ORDER BY week DESC
                LIMIT 1
                """,
                (user["id"],),
            )
            row = cur.fetchone()
            monotony = row[0] if row else None
            strain = row[1] if row else None

            # Weekly fatigue load: moving time (s) * avg HR (bpm).
            cur.execute(
                """
                SELECT week, moving_s, avg_hr_norm
                FROM metrics_weekly
                WHERE user_id = ?
                ORDER BY week DESC
                LIMIT 6
                """,
                (user["id"],),
            )
            fatigue_rows = cur.fetchall()
            weekly_fatigue = []
            for week, moving_s, avg_hr_norm in fatigue_rows:
                if moving_s is None or avg_hr_norm is None:
                    continue
                weekly_fatigue.append(
                    {"week": week, "load": float(moving_s) * float(avg_hr_norm)}
                )
            weekly_fatigue_sorted = list(reversed(weekly_fatigue))
            last_week_load = weekly_fatigue_sorted[-1]["load"] if weekly_fatigue_sorted else None
            last_4 = weekly_fatigue_sorted[-4:] if len(weekly_fatigue_sorted) >= 1 else []
            fatigue_4w_avg = (
                sum(w["load"] for w in last_4) / len(last_4) if last_4 else None
            )

            # Recovery index (28d): median efficiency vs max efficiency.
            cur.execute(
                """
                SELECT c.distance_m, c.moving_s, COALESCE(c.avg_hr_norm, c.avg_hr_raw)
                FROM activities_calc c
                JOIN activities a ON a.activity_id = c.activity_id
                WHERE a.user_id = ?
                  AND lower(a.activity_type) = 'run'
                  AND a.start_time >= ?
                  AND c.distance_m IS NOT NULL
                  AND c.moving_s IS NOT NULL
                  AND c.moving_s > 0
                  AND COALESCE(c.avg_hr_norm, c.avg_hr_raw) IS NOT NULL
                """,
                (user["id"], days_28_ago),
            )
            efficiencies = []
            for distance_m, moving_s, avg_hr in cur.fetchall():
                if not distance_m or not moving_s or not avg_hr:
                    continue
                pace_sec = moving_s / (distance_m / 1000)
                if pace_sec <= 0:
                    continue
                # Speed per bpm proxy.
                eff = (1000 / pace_sec) / avg_hr
                if eff > 0:
                    efficiencies.append(eff)
            recovery_index = None
            if efficiencies:
                eff_med = statistics.median(efficiencies)
                eff_max = max(efficiencies)
                if eff_max > 0:
                    recovery_index = 100 * (eff_med / eff_max)

            # Pace/HR efficiency trend (12w) using weekly data.
            cur.execute(
                """
                SELECT avg_pace_sec, avg_hr_norm
                FROM metrics_weekly
                WHERE user_id = ?
                ORDER BY week DESC
                LIMIT 12
                """,
                (user["id"],),
            )
            eff_weekly = []
            for avg_pace_sec, avg_hr_norm in cur.fetchall():
                if avg_pace_sec and avg_hr_norm:
                    eff = (1000 / avg_pace_sec) / avg_hr_norm
                    eff_weekly.append(eff)
            eff_weekly = list(reversed(eff_weekly))
            efficiency_trend = linear_slope(eff_weekly)

            cur.execute(
                """
                SELECT AVG(decoupling), AVG(hr_drift)
                FROM activities_calc
                WHERE activity_type = 'run'
                  AND activity_id IN (
                    SELECT activity_id
                    FROM activities
                    WHERE user_id = ?
                      AND lower(activity_type) = 'run'
                      AND start_time >= ?
                  )
                """,
                (user["id"], days_28_ago),
            )
            decoupling_avg, hr_drift_avg = cur.fetchone() or (None, None)

            cur.execute(
                """
                SELECT COALESCE(SUM(distance_m), 0)
                FROM activities
                WHERE user_id = ?
                  AND lower(activity_type) = 'run'
                  AND start_time >= ?
                """,
                (user["id"], days_7_ago),
            )
            dist_7d = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT COALESCE(SUM(distance_m), 0)
                FROM activities
                WHERE user_id = ?
                  AND lower(activity_type) = 'run'
                  AND start_time >= ?
                """,
                (user["id"], days_28_ago),
            )
            dist_28d = cur.fetchone()[0] or 0

        return {
            "vdot_best": best_vdot,
            "vdot_source": best_source,
            "pb_all": pb_all,
            "pb_12m": best_12m,
            "est_5k_s": est_5k,
            "est_10k_s": est_10k,
            "pace_trend_sec_per_week": pace_trend,
            "hr_trend_bpm_per_week": hr_trend,
            "eff_trend_per_week": eff_trend,
            "monotony": monotony,
            "strain": strain,
            "decoupling_28d": decoupling_avg,
            "hr_drift_28d": hr_drift_avg,
            "weekly_fatigue": weekly_fatigue_sorted,
            "fatigue_last_week": last_week_load,
            "fatigue_4w_avg": fatigue_4w_avg,
            "recovery_index_28d": recovery_index,
            "efficiency_trend_12w": efficiency_trend,
            "dist_7d_km": dist_7d / 1000 if dist_7d else 0,
            "dist_28d_km": dist_28d / 1000 if dist_28d else 0,
        }

    return get_or_set(cache_key, CACHE_TTL_SECONDS, last_update, compute)


@router.get("/insights/daily", response_model=InsightsDailyResponse)
def insights_daily(user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    return {"date": time.strftime("%Y-%m-%d"), "summary": None}


@router.post("/insights/context", response_model=InsightsContextResponse)
def insights_context(payload: InsightsContextRequest, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    occurred_at = payload.occurred_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO context_events(user_id, occurred_at, event_type, payload_json, source)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                occurred_at,
                payload.event_type,
                json.dumps(payload.payload),
                payload.source,
            ),
        )
        conn.commit()
    return {"status": "stored", "stored_at": occurred_at}


@router.post("/insights/evaluate", response_model=InsightsEvaluateResponse)
def insights_evaluate(payload: InsightsEvaluateRequest, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    _ = user  # placeholder for future personalization
    return {"status": "pending", "answer": None}


@router.get("/insights/series", response_model=InsightsSeriesResponse)
def insights_series(metric: str = "pace_trend", weeks: int = 52, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    weeks = max(4, min(104, weeks))
    now = time.time()
    start_cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - weeks * 7 * 24 * 3600))
    series = []
    series_meta = None
    with get_db() as conn:
        cur = conn.cursor()

        if metric in {
            "pace_trend",
            "hr_trend",
            "eff_trend",
            "monotony",
            "strain",
            "volume",
            "fatigue_load",
            "eff_trend_phr",
            "recovery_index",
        }:
            cur.execute(
                """
                SELECT week, distance_m, moving_s, avg_pace_sec, avg_hr_norm, eff_index, monotony, strain
                FROM metrics_weekly
                WHERE user_id = ?
                ORDER BY week DESC
                LIMIT ?
                """,
                (user["id"], weeks),
            )
            rows = list(reversed(cur.fetchall()))
            eff_values = []
            for week, distance_m, moving_s, avg_pace_sec, avg_hr_norm, eff_index, monotony, strain in rows:
                value = None
                if metric == "pace_trend":
                    value = avg_pace_sec
                elif metric == "hr_trend":
                    value = avg_hr_norm
                elif metric == "eff_trend":
                    value = eff_index
                elif metric == "monotony":
                    value = monotony
                elif metric == "strain":
                    value = strain
                elif metric == "volume":
                    value = (distance_m / 1000) if distance_m is not None else None
                elif metric == "fatigue_load":
                    value = (moving_s * avg_hr_norm) if (moving_s and avg_hr_norm) else None
                elif metric == "eff_trend_phr":
                    if avg_pace_sec and avg_hr_norm:
                        value = (1000 / avg_pace_sec) / avg_hr_norm
                if value is not None:
                    eff_values.append(value)
                series.append({"week": week, "value": value})

            if metric == "recovery_index":
                valid = [v for v in eff_values if v]
                if valid:
                    best = max(valid)
                    series = [
                        {"week": row["week"], "value": (row["value"] / best) * 100 if row["value"] else None}
                        for row in series
                    ]

        elif metric in {"vdot", "decoupling"}:
            cur.execute(
                """
                SELECT a.start_time, c.distance_m, c.moving_s, c.decoupling
                FROM activities a
                JOIN activities_calc c ON c.activity_id = a.activity_id
                WHERE a.user_id = ?
                  AND lower(a.activity_type) = 'run'
                  AND a.start_time >= ?
                """,
                (user["id"], start_cutoff),
            )
            buckets: Dict[str, list] = {}
            for start_time, distance_m, moving_s, decoupling in cur.fetchall():
                week = week_key(start_time or "")
                if metric == "decoupling":
                    if decoupling is None:
                        continue
                    buckets.setdefault(week, []).append(decoupling)
                else:
                    if distance_m is None or moving_s is None or distance_m < 5000:
                        continue
                    vdot = compute_vdot(distance_m, moving_s)
                    if vdot is None:
                        continue
                    buckets.setdefault(week, []).append(vdot)
            for week in sorted(buckets.keys()):
                if metric == "decoupling":
                    vals = buckets[week]
                    value = sum(vals) / len(vals) if vals else None
                else:
                    value = max(buckets[week]) if buckets[week] else None
                series.append({"week": week, "value": value})

        if metric == "decoupling":
            cur.execute(
                "SELECT COUNT(*) FROM streams_raw WHERE user_id=? AND stream_type='heartrate'",
                (user["id"],),
            )
            hr_count = cur.fetchone()[0] or 0
            if hr_count == 0:
                series_meta = {"reason": "missing_hr_streams"}

        if series_meta is None:
            has_values = any(point.get("value") is not None for point in series)
            if not series or not has_values:
                series_meta = {"reason": "no_data"}

    return {"metric": metric, "series": series, "series_meta": series_meta}
