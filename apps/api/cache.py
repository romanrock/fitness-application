import time
from typing import Any, Callable, Dict, Optional, Tuple


_cache: Dict[str, Tuple[float, Any, Optional[str]]] = {}


def get_or_set(key: str, ttl_seconds: int, last_update: Optional[str], compute: Callable[[], Any]) -> Any:
    now = time.time()
    entry = _cache.get(key)
    if entry:
        expires_at, value, cached_last_update = entry
        if expires_at > now and cached_last_update == last_update:
            return value
    value = compute()
    _cache[key] = (now + ttl_seconds, value, last_update)
    return value


def clear() -> None:
    _cache.clear()
