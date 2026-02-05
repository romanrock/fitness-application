import os
import datetime
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.config import API_PORT, REFRESH_SECONDS, WEB_PORT, RUN_MODE


LOG_PATH = ROOT / "data" / "dev.log"


def log(message):
    timestamp = datetime.datetime.now(datetime.UTC).isoformat()
    line = f"[{timestamp}] {message}"
    print(line)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text((LOG_PATH.read_text() if LOG_PATH.exists() else "") + line + "\n", encoding="utf-8")


def run(cmd, cwd=None):
    log(f"RUN: {' '.join(str(c) for c in cmd)} (cwd={cwd or str(ROOT)})")
    res = subprocess.run(cmd, cwd=cwd or str(ROOT), capture_output=True, text=True)
    if res.stdout:
        log(f"STDOUT: {res.stdout.strip()}")
    if res.stderr:
        log(f"STDERR: {res.stderr.strip()}")
    if res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=res.stderr)


def run_with_retry(cmd, cwd=None, retries=2, delay=3):
    for attempt in range(retries + 1):
        try:
            run(cmd, cwd=cwd)
            return
        except subprocess.CalledProcessError as exc:
            if attempt >= retries:
                raise
            log(f"Retrying after error: {exc}")
            time.sleep(delay)


def venv_python():
    venv = ROOT / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin") / (
        "python.exe" if sys.platform.startswith("win") else "python"
    )
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
    env = os.environ.copy()
    if RUN_MODE != "prod":
        env["FITNESS_AUTH_DISABLED"] = "1"
        env["FITNESS_RUN_INGEST_ON_START"] = "1"
        env["FITNESS_PIPELINE_INTERVAL"] = str(REFRESH_SECONDS)
    return subprocess.Popen(
        [str(py), "-m", "uvicorn", "apps.api.main:app", *reload_flag, "--host", "0.0.0.0", "--port", str(API_PORT)],
        cwd=str(ROOT),
        env=env,
    )


def start_vite():
    if RUN_MODE == "prod":
        return None
    web_dir = ROOT / "apps" / "web"
    if not (web_dir / "node_modules").exists():
        subprocess.run(["npm", "install"], check=True, cwd=str(web_dir))
    return subprocess.Popen([
        "npm",
        "run",
        "dev",
        "--",
        "--port",
        str(WEB_PORT)
    ], cwd=str(web_dir))


def start_worker():
    if RUN_MODE == "prod":
        return None
    py = venv_python() or sys.executable
    return subprocess.Popen([str(py), str(ROOT / "scripts" / "run_worker.py")], cwd=str(ROOT))


def main():
    ensure_venv()
    py = venv_python() or sys.executable
    if RUN_MODE != "prod":
        os.environ["FITNESS_AUTH_DISABLED"] = "1"
        os.environ["FITNESS_RUN_INGEST_ON_START"] = "0"
        os.environ["FITNESS_PIPELINE_INTERVAL"] = str(REFRESH_SECONDS)

    api = start_api(py)
    vite = start_vite()
    worker = start_worker()

    if api:
        print(f"API running at http://127.0.0.1:{API_PORT}")
    if vite:
        print(f"Web app (Vite) running at http://127.0.0.1:{WEB_PORT}")
    else:
        print("Web app not started (RUN_MODE=prod).")
    if worker:
        print("Worker running (pipeline scheduler).")
    print(f"Mode: {RUN_MODE}. Pipeline runs every hour. Type Ctrl+C to stop.")

    try:
        if api:
            api.wait()
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if api:
            api.terminate()
        if vite:
            vite.terminate()
        if worker:
            worker.terminate()


if __name__ == "__main__":
    main()
