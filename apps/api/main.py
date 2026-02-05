from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import subprocess
import threading
from pathlib import Path
import time

from packages.config import (
    CORS_ORIGINS,
    REFRESH_SECONDS,
    RUN_MODE,
    RUN_STRAVA_SYNC,
    STRAVA_LOCAL_PATH,
)
from packages.pipeline_lock import pipeline_lock
from .routes import activities as activities_routes
from .routes import auth as auth_routes
from .routes import health as health_routes
from .routes import insights as insights_routes
from .routes import segments as segments_routes


app = FastAPI(title="Fitness Platform API")


def run_ingestion_pipeline():
    root = Path(__file__).resolve().parents[2]
    py = os.getenv("FITNESS_PYTHON", str(root / ".venv" / "bin" / "python"))
    with pipeline_lock() as acquired:
        if not acquired:
            print("Pipeline lock active; skipping ingestion run.")
            return
        if RUN_STRAVA_SYNC and (STRAVA_LOCAL_PATH / "run_all.js").exists():
            subprocess.run(["node", str(STRAVA_LOCAL_PATH / "run_all.js")], cwd=str(STRAVA_LOCAL_PATH))
        subprocess.run([py, str(root / "scripts" / "migrate_db.py")])
        subprocess.run([py, str(root / "services" / "ingestion" / "strava_import.py")])
        subprocess.run([py, str(root / "services" / "ingestion" / "weather_import.py")])
        subprocess.run([py, str(root / "services" / "ingestion" / "segments_import.py")])
        subprocess.run([py, str(root / "services" / "processing" / "pipeline.py")])


def pipeline_loop(interval_sec: int):
    while True:
        run_ingestion_pipeline()
        time.sleep(interval_sec)


@app.on_event("startup")
def trigger_ingestion_on_start():
    if RUN_MODE == "prod":
        return
    if os.getenv("FITNESS_RUN_INGEST_ON_START", "0") != "1":
        return
    interval = int(os.getenv("FITNESS_PIPELINE_INTERVAL", str(REFRESH_SECONDS)))
    thread = threading.Thread(target=pipeline_loop, args=(interval,), daemon=True)
    thread.start()


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes (unprefixed) + /api + /api/v1
app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(activities_routes.router_public)

app.include_router(health_routes.router, prefix="/api")
app.include_router(auth_routes.router, prefix="/api")
app.include_router(activities_routes.router_public, prefix="/api")
app.include_router(activities_routes.router_api, prefix="/api")
app.include_router(insights_routes.router, prefix="/api")
app.include_router(segments_routes.router, prefix="/api")

app.include_router(health_routes.router, prefix="/api/v1")
app.include_router(auth_routes.router, prefix="/api/v1")
app.include_router(activities_routes.router_public, prefix="/api/v1")
app.include_router(activities_routes.router_api, prefix="/api/v1")
app.include_router(insights_routes.router, prefix="/api/v1")
app.include_router(segments_routes.router, prefix="/api/v1")
