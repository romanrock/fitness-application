from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..schemas import ActivitySegmentsResponse, SegmentsBestResponse
from ..utils import db_exists, get_db


router = APIRouter()


def _stream_series(raw_json: str | None):
    if not raw_json:
        return None
    try:
        import json

        parsed = json.loads(raw_json)
    except Exception:
        return None
    data = parsed.get("data")
    if not isinstance(data, list):
        return None
    return data


def _best_segment_time(time_s: list[float], dist_m: list[float], target_m: float) -> float | None:
    # Sliding window on monotonic distance stream: O(n).
    if not time_s or not dist_m:
        return None
    if len(time_s) != len(dist_m):
        return None
    n = len(time_s)
    j = 0
    best = None
    for i in range(n):
        if j < i:
            j = i
        start_d = dist_m[i]
        while j < n and (dist_m[j] - start_d) < target_m:
            j += 1
        if j >= n:
            break
        dt = time_s[j] - time_s[i]
        if dt <= 0:
            continue
        if best is None or dt < best:
            best = dt
    return best


@router.get("/segments_best", response_model=SegmentsBestResponse)
def segments_best(user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT distance_m, time_s, activity_id, date, scope
            FROM segments_best
            WHERE scope IN ('best_all', 'best_12w')
            ORDER BY scope, distance_m
            """
        )
        data = {"best_all": {}, "best_12w": {}}
        for dist, time_s, activity_id, date, scope in cur.fetchall():
            bucket = data.get(scope)
            if bucket is None:
                continue
            bucket[int(dist)] = {
                "time_s": time_s,
                "activity_id": activity_id,
                "date": date,
            }
        return data


@router.get("/activity/{activity_id}/segments", response_model=ActivitySegmentsResponse)
def activity_segments(activity_id: str, user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT distance_m, time_s
            FROM segments_best
            WHERE scope = 'activity' AND activity_id = ?
            ORDER BY distance_m
            """,
            (activity_id,),
        )
        segments = {int(dist): time_s for dist, time_s in cur.fetchall()}
        if segments:
            return {"segments": segments}

        # Fallback: compute basic rolling bests from streams (API-only mode).
        cur.execute(
            """
            SELECT stream_type, raw_json
            FROM streams_raw
            WHERE user_id = ? AND activity_id = ? AND stream_type IN ('time', 'distance')
            """,
            (user["id"], activity_id),
        )
        raw = {row[0]: row[1] for row in cur.fetchall()}
        time_series = _stream_series(raw.get("time"))
        dist_series = _stream_series(raw.get("distance"))
        if not time_series or not dist_series:
            return {"segments": {}}
        try:
            time_series = [float(x) for x in time_series]
            dist_series = [float(x) for x in dist_series]
        except Exception:
            return {"segments": {}}
        out = {}
        for target in (1000, 3000, 5000, 10000):
            best = _best_segment_time(time_series, dist_series, float(target))
            if best is not None:
                out[target] = best
        return {"segments": out}
