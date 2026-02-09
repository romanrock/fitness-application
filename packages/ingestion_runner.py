from pathlib import Path
import os
import subprocess
import sys
import time

from packages.config import RUN_STRAVA_SYNC, STRAVA_LOCAL_PATH, STRAVA_API_ENABLED
from packages.metrics import inc, observe
from packages.pipeline_lock import pipeline_lock


def _run_step(step: str, cmd: list[str], cwd: str | None = None) -> bool:
    start = time.perf_counter()
    res = subprocess.run(cmd, cwd=cwd)
    duration = time.perf_counter() - start
    inc(f"pipeline_step_runs_total{{step=\"{step}\"}}")
    observe(f"pipeline_step_duration_seconds{{step=\"{step}\"}}", duration)
    if res.returncode != 0:
        inc(f"pipeline_step_failures_total{{step=\"{step}\"}}")
        return False
    return True


def run_ingestion_pipeline() -> bool:
    root = Path(__file__).resolve().parents[1]
    py = os.getenv("FITNESS_PYTHON")
    if not py:
        venv_py = root / ".venv" / "bin" / "python"
        py = str(venv_py) if venv_py.exists() else sys.executable
    with pipeline_lock() as acquired:
        if not acquired:
            print("Pipeline lock active; skipping ingestion run.")
            return False
        ok = _run_step("migrate", [py, str(root / "scripts" / "migrate_db.py")])
        if STRAVA_API_ENABLED:
            ok = _run_step("strava_api", [py, str(root / "services" / "ingestion" / "strava_api_import.py")]) and ok
        elif RUN_STRAVA_SYNC and (STRAVA_LOCAL_PATH / "run_all.js").exists():
            ok = _run_step(
                "strava_local",
                ["node", str(STRAVA_LOCAL_PATH / "run_all.js")],
                cwd=str(STRAVA_LOCAL_PATH),
            ) and ok
        ok = _run_step("strava_import", [py, str(root / "services" / "ingestion" / "strava_import.py")]) and ok
        ok = _run_step("weather_import", [py, str(root / "services" / "ingestion" / "weather_import.py")]) and ok
        ok = _run_step("segments_import", [py, str(root / "services" / "ingestion" / "segments_import.py")]) and ok
        ok = _run_step("pipeline", [py, str(root / "services" / "processing" / "pipeline.py")]) and ok
    return ok
