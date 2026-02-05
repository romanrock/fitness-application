import subprocess
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.config import DB_PATH, REFRESH_SECONDS, RUN_STRAVA_SYNC, STRAVA_LOCAL_PATH
from packages.pipeline_lock import pipeline_lock


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
        if not DB_PATH.exists():
            run_with_retry([str(py), str(ROOT / "scripts" / "init_db.py")])
        if RUN_STRAVA_SYNC:
            run_with_retry(["node", str(STRAVA_LOCAL_PATH / "run_all.js")], cwd=str(STRAVA_LOCAL_PATH))
        run_with_retry([str(py), str(ROOT / "scripts" / "migrate_db.py")])
        run_with_retry([str(py), str(ROOT / "services" / "ingestion" / "strava_import.py")])
        run_with_retry([str(py), str(ROOT / "services" / "ingestion" / "weather_import.py")])
        run_with_retry([str(py), str(ROOT / "services" / "ingestion" / "segments_import.py")])
        run_with_retry([str(py), str(ROOT / "services" / "processing" / "pipeline.py")])
        print("Pipeline complete")


def schedule_pipeline(stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            run_pipeline_once()
        except subprocess.CalledProcessError as exc:
            print(f"Pipeline failed: {exc}")
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
            try:
                run_pipeline_once()
            except subprocess.CalledProcessError as exc:
                print(f"Pipeline failed: {exc}")


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
