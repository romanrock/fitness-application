from pathlib import Path
import os
import subprocess

from packages.config import RUN_STRAVA_SYNC, STRAVA_LOCAL_PATH, STRAVA_API_ENABLED
from packages.pipeline_lock import pipeline_lock


def run_ingestion_pipeline() -> bool:
    root = Path(__file__).resolve().parents[1]
    py = os.getenv("FITNESS_PYTHON", str(root / ".venv" / "bin" / "python"))
    with pipeline_lock() as acquired:
        if not acquired:
            print("Pipeline lock active; skipping ingestion run.")
            return False
        if STRAVA_API_ENABLED:
            subprocess.run([py, str(root / "services" / "ingestion" / "strava_api_import.py")])
        elif RUN_STRAVA_SYNC and (STRAVA_LOCAL_PATH / "run_all.js").exists():
            subprocess.run(["node", str(STRAVA_LOCAL_PATH / "run_all.js")], cwd=str(STRAVA_LOCAL_PATH))
        subprocess.run([py, str(root / "scripts" / "migrate_db.py")])
        subprocess.run([py, str(root / "services" / "ingestion" / "strava_import.py")])
        subprocess.run([py, str(root / "services" / "ingestion" / "weather_import.py")])
        subprocess.run([py, str(root / "services" / "ingestion" / "segments_import.py")])
        subprocess.run([py, str(root / "services" / "processing" / "pipeline.py")])
    return True
