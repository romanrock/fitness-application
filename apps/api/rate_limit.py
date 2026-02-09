import time
from typing import Dict, List


_attempts: Dict[str, List[float]] = {}


def check_rate_limit(key: str, limit: int, window_sec: int) -> bool:
    now = time.time()
    window_start = now - window_sec
    times = _attempts.get(key, [])
    times = [t for t in times if t >= window_start]
    if len(times) >= limit:
        _attempts[key] = times
        return False
    times.append(now)
    _attempts[key] = times
    return True


def clear_rate_limit(key: str) -> None:
    _attempts.pop(key, None)
