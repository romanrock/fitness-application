from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from packages import db

@dataclass
class JobState:
    job_name: str
    consecutive_failures: int
    cooldown_until: Optional[str]
    last_started_at: Optional[str]
    last_finished_at: Optional[str]
    last_status: Optional[str]
    last_error: Optional[str]
    updated_at: str


def ensure_job_tables(conn) -> None:
    if db.is_postgres():
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_runs (
          id INTEGER PRIMARY KEY,
          job_name TEXT NOT NULL,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          status TEXT NOT NULL,
          attempts INTEGER,
          error TEXT,
          duration_sec REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_state (
          job_name TEXT PRIMARY KEY,
          consecutive_failures INTEGER NOT NULL DEFAULT 0,
          cooldown_until TEXT,
          last_started_at TEXT,
          last_finished_at TEXT,
          last_status TEXT,
          last_error TEXT,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_dead_letters (
          id INTEGER PRIMARY KEY,
          job_name TEXT NOT NULL,
          failed_at TEXT NOT NULL,
          error TEXT,
          attempts INTEGER,
          last_status TEXT
        )
        """
    )
    conn.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_iso(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def load_job_state(conn, job_name: str) -> JobState:
    ensure_job_tables(conn)
    row = conn.execute(
        """
        SELECT job_name, consecutive_failures, cooldown_until,
               last_started_at, last_finished_at, last_status, last_error, updated_at
        FROM job_state
        WHERE job_name=?
        """,
        (job_name,),
    ).fetchone()
    if row:
        return JobState(
            row[0],
            row[1],
            _to_iso(row[2]),
            _to_iso(row[3]),
            _to_iso(row[4]),
            row[5],
            row[6],
            _to_iso(row[7]) or _now_iso(),
        )
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO job_state(
            job_name, consecutive_failures, cooldown_until,
            last_started_at, last_finished_at, last_status, last_error, updated_at
        )
        VALUES(?, 0, NULL, NULL, NULL, NULL, NULL, ?)
        """,
        (job_name, now),
    )
    conn.commit()
    return JobState(job_name, 0, None, None, None, None, None, now)


def update_job_state(
    conn,
    job_name: str,
    consecutive_failures: int,
    cooldown_until: Optional[str],
    last_started_at: Optional[str],
    last_finished_at: Optional[str],
    last_status: Optional[str],
    last_error: Optional[str],
) -> None:
    ensure_job_tables(conn)
    conn.execute(
        """
        UPDATE job_state
        SET consecutive_failures=?,
            cooldown_until=?,
            last_started_at=?,
            last_finished_at=?,
            last_status=?,
            last_error=?,
            updated_at=?
        WHERE job_name=?
        """,
        (
            consecutive_failures,
            cooldown_until,
            last_started_at,
            last_finished_at,
            last_status,
            last_error,
            _now_iso(),
            job_name,
        ),
    )
    conn.commit()


def start_job_run(conn, job_name: str) -> int:
    ensure_job_tables(conn)
    cur = conn.cursor()
    if db.is_postgres():
        cur.execute(
            """
            INSERT INTO job_runs(job_name, started_at, status)
            VALUES(?, ?, ?)
            RETURNING id
            """,
            (job_name, _now_iso(), "running"),
        )
        run_id = cur.fetchone()[0]
        conn.commit()
        return run_id
    cur.execute(
        """
        INSERT INTO job_runs(job_name, started_at, status)
        VALUES(?, ?, ?)
        """,
        (job_name, _now_iso(), "running"),
    )
    conn.commit()
    return cur.lastrowid


def finish_job_run(
    conn,
    run_id: int,
    status: str,
    attempts: int,
    error: Optional[str],
    duration_sec: float,
) -> None:
    ensure_job_tables(conn)
    conn.execute(
        """
        UPDATE job_runs
        SET finished_at=?,
            status=?,
            attempts=?,
            error=?,
            duration_sec=?
        WHERE id=?
        """,
        (_now_iso(), status, attempts, error, duration_sec, run_id),
    )
    conn.commit()


def record_dead_letter(
    conn,
    job_name: str,
    error: Optional[str],
    attempts: int,
    last_status: str,
) -> None:
    ensure_job_tables(conn)
    conn.execute(
        """
        INSERT INTO job_dead_letters(job_name, failed_at, error, attempts, last_status)
        VALUES(?, ?, ?, ?, ?)
        """,
        (job_name, _now_iso(), error, attempts, last_status),
    )
    conn.commit()
