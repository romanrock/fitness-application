from fastapi import APIRouter, Depends, Query

from ..deps import get_current_user
from ..schemas import JobDeadLettersResponse, JobRunsResponse, JobsResponse
from ..utils import db_exists, dict_rows, get_db


router = APIRouter()


@router.get("/jobs", response_model=JobsResponse)
def jobs(user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT job_name, consecutive_failures, cooldown_until,
                       last_started_at, last_finished_at, last_status,
                       last_error, updated_at
                FROM job_state
                ORDER BY job_name
                """
            )
            return {"jobs": list(dict_rows(cur))}
        except Exception:
            return {"jobs": []}


@router.get("/job_runs", response_model=JobRunsResponse)
def job_runs(limit: int = Query(50, ge=1, le=500), user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, job_name, started_at, finished_at, status,
                       attempts, error, duration_sec
                FROM job_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return {"runs": list(dict_rows(cur))}
        except Exception:
            return {"runs": []}


@router.get("/job_dead_letters", response_model=JobDeadLettersResponse)
def job_dead_letters(limit: int = Query(50, ge=1, le=500), user=Depends(get_current_user)):
    if not db_exists():
        return {"db": "missing"}
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, job_name, failed_at, error, attempts, last_status
                FROM job_dead_letters
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return {"dead_letters": list(dict_rows(cur))}
        except Exception:
            return {"dead_letters": []}
