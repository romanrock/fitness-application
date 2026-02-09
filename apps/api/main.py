from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import threading
import time
import uuid
import logging

from packages.config import (
    CORS_ORIGINS,
    REFRESH_SECONDS,
    RUN_MODE,
)
from packages.ingestion_runner import run_ingestion_pipeline
from packages.logging_utils import setup_logging
from packages.request_context import request_id_var
from packages.metrics import inc, observe
from .routes import activities as activities_routes
from .routes import auth as auth_routes
from .routes import health as health_routes
from .routes import insights as insights_routes
from .routes import jobs as jobs_routes
from .routes import metrics as metrics_routes
from .routes import segments as segments_routes
from .routes import sync as sync_routes


setup_logging()
logger = logging.getLogger("fitness.api")

app = FastAPI(title="Fitness Platform API")


def format_error(code: str, message: str, request_id: str | None = None, details: dict | None = None):
    payload = {"error": {"code": code, "message": message, "request_id": request_id}}
    if details:
        payload["error"]["details"] = details
    return payload


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


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("request_error %s %s %.1fms", request.method, request.url.path, duration_ms)
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        status_code = getattr(response, "status_code", "ERR")
        inc("http_requests_total")
        inc(f"http_requests_total{{path=\"{request.url.path}\",status=\"{status_code}\"}}")
        observe("http_request_duration_seconds", duration_ms / 1000.0)
        observe(f"http_request_duration_seconds{{path=\"{request.url.path}\"}}", duration_ms / 1000.0)
        logger.info("%s %s -> %s %.1fms", request.method, request.url.path, status_code, duration_ms)
        request_id_var.reset(token)
        if response is not None:
            response.headers["x-request-id"] = request_id

# Consistent error model
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = request_id_var.get() or "-"
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    code = f"http_{exc.status_code}"
    details = exc.detail if isinstance(exc.detail, dict) else None
    return JSONResponse(status_code=exc.status_code, content=format_error(code, message, req_id, details))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = request_id_var.get() or "-"
    logger.exception("unhandled_exception %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content=format_error("internal_error", "Internal server error", req_id))

# Public routes (unprefixed) + /api + /api/v1
app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(activities_routes.router_public)
app.include_router(metrics_routes.router)
app.include_router(jobs_routes.router)

app.include_router(health_routes.router, prefix="/api")
app.include_router(auth_routes.router, prefix="/api")
app.include_router(activities_routes.router_public, prefix="/api")
app.include_router(activities_routes.router_api, prefix="/api")
app.include_router(insights_routes.router, prefix="/api")
app.include_router(segments_routes.router, prefix="/api")
app.include_router(sync_routes.router, prefix="/api")
app.include_router(metrics_routes.router, prefix="/api")
app.include_router(jobs_routes.router, prefix="/api")

app.include_router(health_routes.router, prefix="/api/v1")
app.include_router(auth_routes.router, prefix="/api/v1")
app.include_router(activities_routes.router_public, prefix="/api/v1")
app.include_router(activities_routes.router_api, prefix="/api/v1")
app.include_router(insights_routes.router, prefix="/api/v1")
app.include_router(segments_routes.router, prefix="/api/v1")
app.include_router(sync_routes.router, prefix="/api/v1")
app.include_router(metrics_routes.router, prefix="/api/v1")
app.include_router(jobs_routes.router, prefix="/api/v1")
