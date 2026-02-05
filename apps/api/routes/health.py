import sqlite3

from fastapi import APIRouter

from packages.config import DB_PATH
from ..schemas import HealthResponse
from ..utils import db_exists, get_last_update


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    last_update = get_last_update()
    pipeline = None
    if db_exists():
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT id, started_at, finished_at, status, activities_processed, streams_processed,
                           weather_processed, message, duration_sec
                    FROM pipeline_runs
                    ORDER BY id DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
                if row:
                    pipeline = {
                        "id": row[0],
                        "started_at": row[1],
                        "finished_at": row[2],
                        "status": row[3],
                        "activities_processed": row[4],
                        "streams_processed": row[5],
                        "weather_processed": row[6],
                        "message": row[7],
                        "duration_sec": row[8],
                    }
            except sqlite3.OperationalError:
                pipeline = None
    return {"status": "ok", "last_update": last_update, "pipeline": pipeline}
