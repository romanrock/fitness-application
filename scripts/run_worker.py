import subprocess
from pathlib import Path
import sys
import random
import threading
import time
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages import db
from packages.config import (
    REFRESH_SECONDS,
    RUN_STRAVA_SYNC,
    STRAVA_API_ENABLED,
    STRAVA_LOCAL_PATH,
    PIPELINE_MAX_RETRIES,
    PIPELINE_BACKOFF_BASE_SEC,
    PIPELINE_BACKOFF_MAX_SEC,
    PIPELINE_FAIL_THRESHOLD,
    PIPELINE_COOLDOWN_SEC,
)
from packages.pipeline_lock import pipeline_lock
from packages.job_state import (
    load_job_state,
    mark_stale_runs,
    update_job_state,
    start_job_run,
    finish_job_run,
    record_dead_letter,
)


def run(cmd, cwd=None):
    subprocess.run(cmd, check=True, cwd=cwd or str(ROOT))


def run_with_retry(cmd, cwd=None, retries=2, delay=3):
    for attempt in range(retries + 1):
        try:
            run(cmd, cwd=cwd)
            return
        except subprocess.CalledProcessError as exc:
            if attempt >= retries:
                raise
            print(f"Retrying after error: {exc}")
            time.sleep(delay)


def venv_python():
    venv = ROOT / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin") / (
        "python.exe" if sys.platform.startswith("win") else "python"
    )
    return venv if venv.exists() else None


def run_pipeline_once():
    py = venv_python() or sys.executable
    with pipeline_lock() as acquired:
        if not acquired:
            print("Pipeline lock active; skipping ingestion run.")
            return
        if not db.db_exists():
            run_with_retry([str(py), str(ROOT / "scripts" / "init_db.py")])
        run_with_retry([str(py), str(ROOT / "scripts" / "migrate_db.py")])
        if STRAVA_API_ENABLED:
            run_with_retry([str(py), str(ROOT / "services" / "ingestion" / "strava_api_import.py")])
        elif RUN_STRAVA_SYNC and (STRAVA_LOCAL_PATH / "run_all.js").exists():
            run_with_retry(["node", str(STRAVA_LOCAL_PATH / "run_all.js")], cwd=str(STRAVA_LOCAL_PATH))
        elif RUN_STRAVA_SYNC:
            print(f"STRAVA_LOCAL_PATH missing run_all.js: {STRAVA_LOCAL_PATH}")
        run_with_retry([str(py), str(ROOT / "services" / "ingestion" / "strava_import.py")])
        run_with_retry([str(py), str(ROOT / "services" / "ingestion" / "weather_import.py")])
        run_with_retry([str(py), str(ROOT / "services" / "ingestion" / "segments_import.py")])
        run_with_retry([str(py), str(ROOT / "services" / "processing" / "pipeline.py")])
        print("Pipeline complete")


def _backoff_seconds(attempt: int) -> float:
    base = PIPELINE_BACKOFF_BASE_SEC * (2 ** max(attempt - 1, 0))
    jitter = random.uniform(0.8, 1.2)
    return min(base * jitter, PIPELINE_BACKOFF_MAX_SEC)


def _run_with_retries() -> tuple[bool, str | None, int]:
    attempts = 0
    last_error = None
    for attempt in range(1, PIPELINE_MAX_RETRIES + 2):
        attempts = attempt
        try:
            run_pipeline_once()
            return True, None, attempts
        except subprocess.CalledProcessError as exc:
            last_error = str(exc)
            if attempt <= PIPELINE_MAX_RETRIES:
                delay = _backoff_seconds(attempt)
                print(f"Pipeline attempt {attempt} failed; retrying in {delay:.1f}s")
                time.sleep(delay)
    return False, last_error, attempts


def _should_skip_for_cooldown() -> bool:
    if not db.db_exists():
        return False
    with db.connect() as conn:
        db.configure_connection(conn)
        state = load_job_state(conn, "pipeline")
        if state.cooldown_until:
            try:
                until = datetime.fromisoformat(state.cooldown_until)
            except ValueError:
                return False
            if datetime.now(timezone.utc) < until:
                remaining = (until - datetime.now(timezone.utc)).total_seconds()
                print(f"Pipeline cooldown active; skipping for {remaining:.0f}s.")
                return True
    return False


def _record_job_state(success: bool, error: str | None, attempts: int, started_at: datetime, finished_at: datetime) -> None:
    if not db.db_exists():
        return
    with db.connect() as conn:
        db.configure_connection(conn)
        state = load_job_state(conn, "pipeline")
        consecutive_failures = state.consecutive_failures
        cooldown_until = state.cooldown_until
        status = "ok" if success else "error"
        if success:
            consecutive_failures = 0
            cooldown_until = None
        else:
            consecutive_failures += 1
            if consecutive_failures >= PIPELINE_FAIL_THRESHOLD:
                cooldown_until = (datetime.now(timezone.utc) + timedelta(seconds=PIPELINE_COOLDOWN_SEC)).isoformat()
                record_dead_letter(conn, "pipeline", error, attempts, status)
        update_job_state(
            conn,
            "pipeline",
            consecutive_failures,
            cooldown_until,
            started_at.isoformat(),
            finished_at.isoformat(),
            status,
            error,
        )


def schedule_pipeline(stop_event: threading.Event):
    while not stop_event.is_set():
        if _should_skip_for_cooldown():
            time.sleep(5)
            continue
        started_at = datetime.now(timezone.utc)
        run_id = None
        if db.db_exists():
            with db.connect() as conn:
                db.configure_connection(conn)
                mark_stale_runs(conn, "pipeline", REFRESH_SECONDS * 2)
                run_id = start_job_run(conn, "pipeline")
        try:
            success, error, attempts = _run_with_retries()
        except subprocess.CalledProcessError as exc:
            success, error, attempts = False, str(exc), PIPELINE_MAX_RETRIES + 1
        finished_at = datetime.now(timezone.utc)
        if run_id and db.db_exists():
            with db.connect() as conn:
                db.configure_connection(conn)
                finish_job_run(
                    conn,
                    run_id,
                    "ok" if success else "error",
                    attempts,
                    error,
                    (finished_at - started_at).total_seconds(),
                )
        _record_job_state(success, error, attempts, started_at, finished_at)
        for _ in range(REFRESH_SECONDS):
            if stop_event.is_set():
                return
            time.sleep(1)


def manual_trigger(stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            cmd = input().strip().lower()
        except EOFError:
            return
        if cmd in ("r", "run"):
            if _should_skip_for_cooldown():
                continue
            started_at = datetime.now(timezone.utc)
            run_id = None
            if db.db_exists():
                with db.connect() as conn:
                    db.configure_connection(conn)
                    run_id = start_job_run(conn, "pipeline")
            try:
                success, error, attempts = _run_with_retries()
            except subprocess.CalledProcessError as exc:
                success, error, attempts = False, str(exc), PIPELINE_MAX_RETRIES + 1
            finished_at = datetime.now(timezone.utc)
            if run_id and db.db_exists():
                with db.connect() as conn:
                    db.configure_connection(conn)
                    finish_job_run(
                        conn,
                        run_id,
                        "ok" if success else "error",
                        attempts,
                        error,
                        (finished_at - started_at).total_seconds(),
                    )
            _record_job_state(success, error, attempts, started_at, finished_at)


def main():
    stop_event = threading.Event()
    scheduler = threading.Thread(
        target=schedule_pipeline,
        args=(stop_event,),
        daemon=True,
    )
    scheduler.start()
    trigger = threading.Thread(target=manual_trigger, args=(stop_event,), daemon=True)
    trigger.start()

    print("Worker running. Pipeline runs every hour.")
    print("Type 'r' + Enter to run on demand.")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()


if __name__ == "__main__":
    main()
