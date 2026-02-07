import threading
from collections import defaultdict


_lock = threading.Lock()
_counters = defaultdict(int)
_durations = defaultdict(float)


def inc(name: str, value: int = 1) -> None:
    with _lock:
        _counters[name] += value


def observe(name: str, value: float) -> None:
    with _lock:
        _durations[name] += value


def snapshot() -> tuple[dict, dict]:
    with _lock:
        return dict(_counters), dict(_durations)
