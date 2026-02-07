from fastapi import APIRouter, Response

from packages.metrics import snapshot

router = APIRouter()


@router.get("/metrics")
def metrics():
    counters, durations = snapshot()
    lines = []
    for name, value in sorted(counters.items()):
        lines.append(f"{name} {value}")
    for name, value in sorted(durations.items()):
        lines.append(f"{name}_sum {value}")
    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="text/plain")
