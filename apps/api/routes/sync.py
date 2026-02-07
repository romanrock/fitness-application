import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from packages.config import SYNC_ON_OPEN_SECONDS
from packages.ingestion_runner import run_ingestion_pipeline
from ..deps import get_current_user
from ..utils import get_last_update


router = APIRouter()


def _parse_last_update(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


@router.post("/sync")
def sync_on_open(force: bool = False, user=Depends(get_current_user)):
    last_update = get_last_update()
    last_dt = _parse_last_update(last_update)
    now = datetime.now(timezone.utc)

    if not force and last_dt:
        elapsed = (now - last_dt).total_seconds()
        if elapsed < SYNC_ON_OPEN_SECONDS:
            return {
                "status": "skipped",
                "reason": "fresh",
                "last_update": last_update,
                "min_interval_sec": SYNC_ON_OPEN_SECONDS,
            }

    thread = threading.Thread(target=run_ingestion_pipeline, daemon=True)
    thread.start()
    return {
        "status": "started",
        "last_update": last_update,
        "min_interval_sec": SYNC_ON_OPEN_SECONDS,
    }
