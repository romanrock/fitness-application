import sqlite3

from fastapi import APIRouter, Depends

from packages.config import DB_PATH
from ..deps import get_current_user
from ..schemas import ActivitySegmentsResponse, SegmentsBestResponse
from ..utils import db_exists


router = APIRouter()


@router.get("/segments_best", response_model=SegmentsBestResponse)
def segments_best(user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with sqlite3.connect(DB_PATH) as conn:
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
    with sqlite3.connect(DB_PATH) as conn:
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
        return {"segments": segments}
