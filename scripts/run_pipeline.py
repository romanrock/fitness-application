import subprocess
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from packages.config import DB_PATH, API_PORT, WEB_PORT, REFRESH_SECONDS, RUN_MODE
from packages.pipeline_lock import pipeline_lock


def run(cmd, cwd=None):
    subprocess.run(cmd, check=True, cwd=cwd or str(ROOT))


def venv_python():
    venv = ROOT / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin") / ("python.exe" if sys.platform.startswith("win") else "python")
    return venv if venv.exists() else None


def ensure_venv():
    if venv_python():
        return
    print("Creating .venv and installing dependencies...")
    subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
    py = venv_python()
    if not py:
        raise SystemExit("Virtualenv creation failed.")
    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(py), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)


def uvicorn_available(py):
    try:
        subprocess.run([str(py), "-c", "import uvicorn"], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def start_api(py):
    if not uvicorn_available(py):
        print("Uvicorn not installed. Run: python3 scripts/setup_env.py")
        return None
    reload_flag = ["--reload"] if RUN_MODE != "prod" else []
    return subprocess.Popen(
        [str(py), "-m", "uvicorn", "apps.api.main:app", *reload_flag, "--host", "0.0.0.0", "--port", str(API_PORT)],
        cwd=str(ROOT),
    )


def start_web():
    if RUN_MODE == "prod":
        return None
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(WEB_PORT)],
        cwd=str(ROOT / "apps" / "web"),
    )

def run_pipeline():
    py = venv_python() or sys.executable
    with pipeline_lock() as acquired:
        if not acquired:
            print("Pipeline lock active; skipping ingestion run.")
            return
        if not DB_PATH.exists():
            run([str(py), str(ROOT / "scripts" / "init_db.py")])
        run([str(py), str(ROOT / "scripts" / "migrate_db.py")])
        run([str(py), str(ROOT / "services" / "ingestion" / "strava_import.py")])
        run([str(py), str(ROOT / "services" / "ingestion" / "weather_import.py")])
        run([str(py), str(ROOT / "services" / "ingestion" / "segments_import.py")])
        run([str(py), str(ROOT / "services" / "processing" / "pipeline.py")])
        print("Pipeline complete")


def schedule_pipeline(stop_event: threading.Event, interval_seconds: int = 3600):
    while not stop_event.is_set():
        try:
            run_pipeline()
        except subprocess.CalledProcessError as exc:
            print(f"Pipeline failed: {exc}")
        # Sleep in short intervals so Ctrl+C exits quickly.
        for _ in range(interval_seconds):
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
                run_pipeline()
            except subprocess.CalledProcessError as exc:
                print(f"Pipeline failed: {exc}")


def main():
    ensure_venv()
    stop_event = threading.Event()
    scheduler = threading.Thread(
        target=schedule_pipeline,
        args=(stop_event, REFRESH_SECONDS),
        daemon=True,
    )
    scheduler.start()
    trigger = threading.Thread(target=manual_trigger, args=(stop_event,), daemon=True)
    trigger.start()

    py = venv_python() or sys.executable
    print("Note: scripts/run_pipeline.py is a legacy all-in-one runner.")
    print("Preferred: scripts/run_api.py + scripts/run_worker.py (or scripts/run_dev.py for dev).")

    api = start_api(py)
    web = start_web()
    if api:
        print(f"API running at http://127.0.0.1:{API_PORT}")
    if web:
        print(f"Web app running at http://127.0.0.1:{WEB_PORT}")
    else:
        print("Web app not started (RUN_MODE=prod).")
    print("Pipeline runs every hour.")
    print("Type 'r' + Enter to run on demand.")
    print("Press Ctrl+C to stop.")
    try:
        if api:
            api.wait()
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        if api:
            api.terminate()
        if web:
            web.terminate()


if __name__ == "__main__":
    main()
