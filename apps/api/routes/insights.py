import json
import logging
import os
import re
import uuid
import time
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from urllib import request, error

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
logger = logging.getLogger("fitness.api")

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


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _trend_label(value: float | None, better_lower: bool, threshold: float = 0.5) -> str:
    if value is None:
        return "unknown"
    if abs(value) < threshold:
        return "flat"
    improving = value < 0 if better_lower else value > 0
    return "improving" if improving else "declining"


def _extract_response_text(payload: Dict[str, object]) -> str | None:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    output = payload.get("output")
    if isinstance(output, list):
        chunks: List[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            for part in item.get("content", []) or []:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "output_text" and part.get("text"):
                    chunks.append(str(part["text"]))
        text = "".join(chunks).strip()
        return text or None
    return None


def _coerce_list(value: object, limit: int = 3) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _coerce_time_seconds(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.replace(".", "", 1).isdigit():
        try:
            return float(raw)
        except ValueError:
            return None
    parts = raw.split(":")
    if len(parts) in (2, 3):
        try:
            parts = [float(p) for p in parts]
        except ValueError:
            return None
        if len(parts) == 2:
            minutes, seconds = parts
            return minutes * 60 + seconds
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    return None


def _format_turns(turns: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    for turn in turns:
        question = turn.get("question")
        answer = turn.get("answer")
        if question:
            lines.append(f"User: {question}")
        if answer:
            lines.append(f"Assistant: {answer}")
    return "\n".join(lines).strip()


def _load_memory(conn, user_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT summary_json, last_session_id
        FROM assistant_memory
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    if not row:
        return None, 0
    summary_json = row[0] or "{}"
    last_session_id = row[1] or 0
    try:
        summary = json.loads(summary_json)
    except json.JSONDecodeError:
        summary = {"summary": summary_json}
    return summary, last_session_id


def _save_memory(conn, user_id: int, summary: Dict[str, object], last_session_id: int):
    cur = conn.cursor()
    cur.execute("SELECT id FROM assistant_memory WHERE user_id = ? LIMIT 1", (user_id,))
    row = cur.fetchone()
    payload = json.dumps(summary)
    if row:
        cur.execute(
            """
            UPDATE assistant_memory
            SET summary_json = ?, updated_at = CURRENT_TIMESTAMP, last_session_id = ?
            WHERE user_id = ?
            """,
            (payload, last_session_id, user_id),
        )
    else:
        cur.execute(
            """
            INSERT INTO assistant_memory(user_id, summary_json, last_session_id)
            VALUES(?, ?, ?)
            """,
            (user_id, payload, last_session_id),
        )


def _call_openai_memory_summary(existing_summary: str | None, turns_text: str):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None, None, "missing_api_key"
    model = os.getenv("OPENAI_MODEL", "gpt-5.2-2025-12-11")
    system_text = (
        "You are summarizing a long-term memory for a running coach. "
        "Return JSON with keys: summary (string), goals (array), preferences (array), "
        "injuries (array), notes (array). Keep it concise."
    )
    user_text = "Existing summary:\n"
    user_text += (existing_summary or "None") + "\n\n"
    user_text += "New turns:\n" + turns_text
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "text": {"format": {"type": "json_object"}},
    }
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except error.HTTPError as exc:
        return None, model, f"http_error:{exc.code}"
    except error.URLError:
        return None, model, "network_error"
    except json.JSONDecodeError:
        return None, model, "bad_json"

    text = _extract_response_text(payload)
    if not text:
        return None, model, "empty_response"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None, model, "invalid_json"
    if not isinstance(parsed, dict):
        return None, model, "invalid_payload"
    return parsed, model, None


def _maybe_compact_memory(conn, user_id: int):
    try:
        summary, last_id = _load_memory(conn, user_id)
    except Exception:
        return
    last_id = last_id or 0
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, prompt_json, response_json
        FROM insight_sessions
        WHERE user_id = ? AND id > ?
        ORDER BY id ASC
        """,
        (user_id, last_id),
    )
    rows = cur.fetchall()
    if len(rows) < 6:
        return
    turns: List[Dict[str, str]] = []
    for row in rows[-12:]:
        prompt_json = row[1] or "{}"
        response_json = row[2] or "{}"
        try:
            prompt = json.loads(prompt_json)
        except json.JSONDecodeError:
            prompt = {}
        try:
            response = json.loads(response_json)
        except json.JSONDecodeError:
            response = {}
        question = prompt.get("question")
        answer = response.get("answer")
        if question or answer:
            turns.append({"question": str(question or ""), "answer": str(answer or "")})
    turns_text = _format_turns(turns)
    existing_summary = None
    if isinstance(summary, dict):
        existing_summary = summary.get("summary")
    summary_payload, model, err = _call_openai_memory_summary(existing_summary, turns_text)
    if summary_payload:
        summary_payload["model"] = model
        summary_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_memory(conn, user_id, summary_payload, rows[-1][0])
    elif err and err != "missing_api_key":
        logger.warning("assistant_memory compact_error=%s model=%s", err, model)


def _parse_range_days(question: str, context: Dict[str, object] | None) -> int | None:
    if context:
        for key, mult in (
            ("range_days", 1),
            ("range_weeks", 7),
            ("range_months", 30),
            ("range_years", 365),
        ):
            raw = context.get(key)
            if isinstance(raw, (int, float)) and raw > 0:
                return int(raw * mult)
    q = question.lower()
    patterns = [
        (r"(?:last|past|previous|over the last)\s+(\d+)\s*days?", 1),
        (r"(?:last|past|previous|over the last)\s+(\d+)\s*weeks?", 7),
        (r"(?:last|past|previous|over the last)\s+(\d+)\s*months?", 30),
        (r"(?:last|past|previous|over the last)\s+(\d+)\s*years?", 365),
        (r"(?:last|past|previous|over the last)\s+year\b", 365),
        (r"(?:last|past|previous|over the last)\s+month\b", 30),
        (r"(?:last|past|previous|over the last)\s+week\b", 7),
    ]
    for pattern, mult in patterns:
        match = re.search(pattern, q)
        if not match:
            continue
        if match.lastindex:
            return int(match.group(1)) * mult
        return mult
    return None


def _summarize_window(conn, user_id: int, start_dt: datetime, end_dt: datetime):
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*), SUM(c.distance_m), SUM(c.moving_s), AVG(c.avg_hr_norm), AVG(c.avg_hr_raw)
        FROM activities a
        JOIN activities_calc c ON c.activity_id = a.activity_id
        WHERE a.user_id = ?
          AND lower(a.activity_type) = 'run'
          AND a.start_time >= ?
          AND a.start_time <= ?
        """,
        (user_id, start_iso, end_iso),
    )
    row = cur.fetchone() or [0, 0, 0, None, None]
    run_count = row[0] or 0
    distance_m = row[1] or 0
    moving_s = row[2] or 0
    avg_hr = row[3] or row[4]
    avg_pace_sec = None
    if distance_m and moving_s:
        avg_pace_sec = moving_s / (distance_m / 1000.0)

    cur.execute(
        """
        SELECT MIN(time_s)
        FROM segments_best
        WHERE distance_m = 5000 AND date >= ? AND date <= ?
        """,
        (start_iso, end_iso),
    )
    best_5k = (cur.fetchone() or [None])[0]
    cur.execute(
        """
        SELECT MIN(time_s)
        FROM segments_best
        WHERE distance_m = 10000 AND date >= ? AND date <= ?
        """,
        (start_iso, end_iso),
    )
    best_10k = (cur.fetchone() or [None])[0]

    cur.execute(
        """
        SELECT COUNT(DISTINCT strftime('%Y-%W', start_time))
        FROM activities
        WHERE user_id = ?
          AND lower(activity_type) = 'run'
          AND start_time >= ?
          AND start_time <= ?
        """,
        (user_id, start_iso, end_iso),
    )
    weeks_with_runs = (cur.fetchone() or [0])[0] or 0

    cur.execute(
        """
        SELECT start_time
        FROM activities
        WHERE user_id = ?
          AND lower(activity_type) = 'run'
          AND start_time >= ?
          AND start_time <= ?
        ORDER BY start_time
        """,
        (user_id, start_iso, end_iso),
    )
    times = [_parse_dt(r[0]) for r in cur.fetchall()]
    times = [t for t in times if t is not None]
    longest_gap_days = None
    if len(times) >= 2:
        gaps = []
        for prev, cur_time in zip(times, times[1:]):
            gap = (cur_time - prev).days
            gaps.append(gap)
        longest_gap_days = max(gaps) if gaps else None

    cur.execute(
        """
        SELECT week, avg_pace_sec
        FROM metrics_weekly
        WHERE user_id = ?
          AND week >= ?
        ORDER BY week
        """,
        (user_id, week_key(start_dt)),
    )
    weekly_pace_series = [r[1] for r in cur.fetchall() if r[1] is not None]
    pace_trend = linear_slope(weekly_pace_series) if weekly_pace_series else None

    cur.execute(
        """
        SELECT strftime('%Y', a.start_time) as yr, SUM(c.distance_m)
        FROM activities a
        JOIN activities_calc c ON c.activity_id = a.activity_id
        WHERE a.user_id = ?
          AND lower(a.activity_type) = 'run'
          AND a.start_time >= ?
          AND a.start_time <= ?
        GROUP BY yr
        ORDER BY yr
        """,
        (user_id, start_iso, end_iso),
    )
    yearly = {r[0]: (r[1] or 0) / 1000.0 for r in cur.fetchall() if r[0]}

    return {
        "start": start_iso,
        "end": end_iso,
        "runs": run_count,
        "distance_km": round(distance_m / 1000.0, 1) if distance_m else 0.0,
        "moving_hours": round(moving_s / 3600.0, 2) if moving_s else 0.0,
        "avg_pace_sec": round(avg_pace_sec, 2) if avg_pace_sec else None,
        "avg_hr": round(avg_hr, 1) if avg_hr else None,
        "best_5k_time_s": best_5k,
        "best_10k_time_s": best_10k,
        "weeks_with_runs": weeks_with_runs,
        "longest_gap_days": longest_gap_days,
        "pace_trend": pace_trend,
        "yearly_distance_km": yearly,
    }


def _call_openai_insights(
    question: str,
    context: Dict[str, object],
    metrics: Dict[str, object],
    history_text: str | None,
    memory_summary: str | None,
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None, None, "missing_api_key"
    model = os.getenv("OPENAI_MODEL", "gpt-5.2-2025-12-11")
    system_text = (
        "You are a running coach for a single athlete. "
        "Respond in JSON with keys: answer (string), today_recommendation (string), "
        "trend_insight (string), predicted_5k_time_s (number or null), "
        "predicted_10k_time_s (number or null), recommendations (array), follow_ups (array). "
        "Be concise, avoid medical claims, and ask follow-ups if context is missing. "
        "Return valid JSON only."
    )
    user_text = f"Question: {question}\n"
    user_text += f"Context: {json.dumps(context, ensure_ascii=False)}\n"
    user_text += f"Metrics: {json.dumps(metrics, ensure_ascii=False)}\n"
    if memory_summary:
        user_text += f"Memory summary: {memory_summary}\n"
    if history_text:
        user_text += f"Recent conversation:\n{history_text}\n"
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "text": {"format": {"type": "json_object"}},
    }
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except error.HTTPError as exc:
        return None, model, f"http_error:{exc.code}"
    except error.URLError:
        return None, model, "network_error"
    except json.JSONDecodeError:
        return None, model, "bad_json"

    text = _extract_response_text(payload)
    if not text:
        return None, model, "empty_response"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None, model, "invalid_json"
    if not isinstance(parsed, dict):
        return None, model, "invalid_payload"
    return parsed, model, None


@router.post("/insights/evaluate", response_model=InsightsEvaluateResponse)
def insights_evaluate(payload: InsightsEvaluateRequest, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    session_id = payload.session_id or str(uuid.uuid4())
    recommendations: List[str] = []
    follow_ups: List[str] = []
    dist_7d_km = None
    dist_28d_km = None
    pace_trend = None
    hr_trend = None
    last_run_at = None
    has_hr = False
    history_text = None
    memory_summary = None

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT week, distance_m, avg_pace_sec, avg_hr_norm, monotony, strain
            FROM metrics_weekly
            WHERE user_id = ?
            ORDER BY week DESC
            LIMIT 12
            """,
            (user["id"],),
        )
        rows = cur.fetchall()
        if rows:
            dist_7d_km = (rows[0][1] or 0) / 1000.0
            dist_28d_km = sum((r[1] or 0) for r in rows[:4]) / 1000.0
            pace_series = [r[2] for r in reversed(rows) if r[2] is not None]
            hr_series = [r[3] for r in reversed(rows) if r[3] is not None]
            has_hr = bool(hr_series)
            pace_trend = linear_slope(pace_series)
            hr_trend = linear_slope(hr_series)

        cur.execute(
            """
            SELECT MAX(start_time)
            FROM activities
            WHERE user_id = ? AND lower(activity_type) = 'run'
            """,
            (user["id"],),
        )
        row = cur.fetchone()
        last_run_at = _parse_dt(row[0] if row else None)

        cur.execute(
            """
            SELECT COUNT(*)
            FROM context_events
            WHERE user_id = ?
              AND occurred_at >= ?
            """,
            (user["id"], (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()),
        )
        recent_context = (cur.fetchone() or [0])[0]

        try:
            memory_payload, _ = _load_memory(conn, user["id"])
            if isinstance(memory_payload, dict):
                memory_summary = memory_payload.get("summary")
        except Exception:
            memory_summary = None

        try:
            cur.execute(
                """
                SELECT prompt_json, response_json
                FROM insight_sessions
                WHERE user_id = ? AND session_id = ?
                ORDER BY id DESC
                LIMIT 6
                """,
                (user["id"], session_id),
            )
            rows = list(reversed(cur.fetchall()))
            turns: List[Dict[str, str]] = []
            for prompt_json, response_json in rows:
                try:
                    prompt = json.loads(prompt_json or "{}")
                except json.JSONDecodeError:
                    prompt = {}
                try:
                    response = json.loads(response_json or "{}")
                except json.JSONDecodeError:
                    response = {}
                question = prompt.get("question")
                answer = response.get("answer")
                if question or answer:
                    turns.append({"question": str(question or ""), "answer": str(answer or "")})
            history_text = _format_turns(turns) if turns else None
        except Exception:
            history_text = None

        requested_days = _parse_range_days(payload.question, payload.context)
        window_summaries: Dict[str, object] = {}
        now_dt = datetime.now(timezone.utc)
        windows = [
            ("3m", 90),
            ("6m", 180),
            ("12m", 365),
            ("3y", 365 * 3),
        ]
        for label, days in windows:
            start_dt = now_dt - timedelta(days=days)
            window_summaries[label] = _summarize_window(conn, user["id"], start_dt, now_dt)
        if requested_days:
            start_dt = now_dt - timedelta(days=requested_days)
            window_summaries["requested"] = _summarize_window(
                conn, user["id"], start_dt, now_dt
            )

    metrics_payload = {
        "dist_7d_km": dist_7d_km,
        "dist_28d_km": dist_28d_km,
        "pace_trend": pace_trend,
        "hr_trend": hr_trend,
        "has_hr": has_hr,
        "last_run_at": last_run_at.isoformat() if last_run_at else None,
        "window_summaries": window_summaries,
    }
    provider = "deterministic"
    model = None
    llm_error = None
    today_recommendation = None
    trend_insight = None
    predicted_5k_time_s = None
    predicted_10k_time_s = None

    if dist_28d_km is None or dist_28d_km == 0:
        recommendations.append("Start with an easy 20–30 min run or walk today.")
        recommendations.append("Aim for 2–3 short sessions this week to rebuild consistency.")
    else:
        if dist_7d_km == 0:
            recommendations.append("You haven't run this week — do an easy 20–40 min run today.")
        trend = _trend_label(pace_trend, better_lower=True, threshold=0.5)
        if trend == "improving":
            recommendations.append("Keep one quality session and one long easy run this week.")
        elif trend == "declining":
            recommendations.append("Prioritize recovery: keep runs easy and add one rest day.")
        else:
            recommendations.append("Maintain volume with mostly easy runs and one moderate session.")

    if not has_hr:
        follow_ups.append("Do you have HR data available? It improves trend accuracy.")
    if last_run_at is None or (datetime.now(timezone.utc) - last_run_at).days >= 14:
        follow_ups.append("When did you last train and how do you feel today?")
    if recent_context == 0:
        follow_ups.append("How was your sleep and soreness today?")

    trend_pace = _trend_label(pace_trend, better_lower=True, threshold=0.5)
    trend_hr = _trend_label(hr_trend, better_lower=True, threshold=0.3)
    pace_clause = f"Pace is {trend_pace}"
    if pace_trend is not None:
        pace_clause += f" ({pace_trend:+.2f} sec/km/wk)"
    hr_clause = f"HR is {trend_hr}"
    if hr_trend is not None:
        hr_clause += f" ({hr_trend:+.2f} bpm/wk)"
    volume_clause = "Last 7d volume: n/a"
    if dist_7d_km is not None:
        volume_clause = f"Last 7d volume: {dist_7d_km:.1f} km"
    if dist_28d_km is not None:
        volume_clause += f", 28d: {dist_28d_km:.1f} km"
    answer = f"Trend summary: {pace_clause}, {hr_clause}. {volume_clause}. This is general guidance; listen to your body."
    trend_insight = f"{pace_clause}. {hr_clause}."
    if recommendations:
        today_recommendation = recommendations[0]
    summary_source = (
        window_summaries.get("requested")
        or window_summaries.get("12m")
        or window_summaries.get("3y")
        or {}
    )
    if isinstance(summary_source, dict):
        predicted_5k_time_s = summary_source.get("best_5k_time_s")
        predicted_10k_time_s = summary_source.get("best_10k_time_s")

    llm_payload, model, llm_error = _call_openai_insights(
        payload.question,
        payload.context or {},
        metrics_payload,
        history_text,
        memory_summary,
    )
    if llm_payload:
        provider = "openai"
        answer = str(llm_payload.get("answer") or answer).strip() or answer
        today_recommendation = (
            str(llm_payload.get("today_recommendation") or today_recommendation).strip()
            if (llm_payload.get("today_recommendation") or today_recommendation)
            else today_recommendation
        )
        trend_insight = (
            str(llm_payload.get("trend_insight") or trend_insight).strip()
            if (llm_payload.get("trend_insight") or trend_insight)
            else trend_insight
        )
        predicted_5k_time_s = _coerce_time_seconds(
            llm_payload.get("predicted_5k_time_s")
            or llm_payload.get("predicted_5k")
            or predicted_5k_time_s
        )
        predicted_10k_time_s = _coerce_time_seconds(
            llm_payload.get("predicted_10k_time_s")
            or llm_payload.get("predicted_10k")
            or predicted_10k_time_s
        )
        recommendations = _coerce_list(llm_payload.get("recommendations"), limit=3) or recommendations
        follow_ups = _coerce_list(llm_payload.get("follow_ups"), limit=3) or follow_ups
    elif llm_error and llm_error != "missing_api_key":
        logger.warning("insights_evaluate llm_error=%s model=%s", llm_error, model)

    logger.info("insights_evaluate provider=%s model=%s", provider, model or "deterministic")

    response_payload = {
        "status": "ok",
        "answer": answer,
        "today_recommendation": today_recommendation,
        "trend_insight": trend_insight,
        "predicted_5k_time_s": predicted_5k_time_s,
        "predicted_10k_time_s": predicted_10k_time_s,
        "recommendations": recommendations,
        "follow_ups": follow_ups,
        "session_id": session_id,
    }
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO insight_sessions(user_id, session_date, session_id, prompt_json, response_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                time.strftime("%Y-%m-%d"),
                session_id,
                json.dumps(
                    {
                        "session_id": session_id,
                        "question": payload.question,
                        "context": payload.context or {},
                        "metrics": metrics_payload,
                    }
                ),
                json.dumps(
                    {
                        "provider": provider,
                        "model": model,
                        "answer": answer,
                        "today_recommendation": today_recommendation,
                        "trend_insight": trend_insight,
                        "predicted_5k_time_s": predicted_5k_time_s,
                        "predicted_10k_time_s": predicted_10k_time_s,
                        "recommendations": recommendations,
                        "follow_ups": follow_ups,
                    }
                ),
            ),
        )
        _maybe_compact_memory(conn, user["id"])
        conn.commit()

    return response_payload


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
