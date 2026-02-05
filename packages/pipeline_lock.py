import os
import time
from contextlib import contextmanager
from typing import Iterator


DEFAULT_LOCK_PATH = "/tmp/fitness_pipeline.lock"
DEFAULT_RETRIES = 5
DEFAULT_DELAY_SEC = 2
DEFAULT_TTL_SEC = 60 * 30


def _lock_path() -> str:
    return os.getenv("FITNESS_PIPELINE_LOCK_PATH", DEFAULT_LOCK_PATH)


def _lock_ttl() -> int:
    try:
        return int(os.getenv("FITNESS_PIPELINE_LOCK_TTL_SECONDS", str(DEFAULT_TTL_SEC)))
    except ValueError:
        return DEFAULT_TTL_SEC


def _is_stale(path: str) -> bool:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return False
    return (time.time() - mtime) > _lock_ttl()


def _acquire(path: str) -> bool:
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        payload = f"pid={os.getpid()} time={time.time()}\n"
        os.write(fd, payload.encode("utf-8"))
    finally:
        os.close(fd)
    return True


def _release(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


@contextmanager
def pipeline_lock() -> Iterator[bool]:
    path = _lock_path()
    retries = DEFAULT_RETRIES
    delay = DEFAULT_DELAY_SEC
    try:
        retries = int(os.getenv("FITNESS_PIPELINE_LOCK_RETRIES", str(DEFAULT_RETRIES)))
    except ValueError:
        pass
    try:
        delay = float(os.getenv("FITNESS_PIPELINE_LOCK_RETRY_SEC", str(DEFAULT_DELAY_SEC)))
    except ValueError:
        pass

    acquired = False
    for attempt in range(retries + 1):
        if _acquire(path):
            acquired = True
            break
        if _is_stale(path):
            _release(path)
            if _acquire(path):
                acquired = True
                break
        if attempt < retries:
            time.sleep(delay)

    try:
        yield acquired
    finally:
        if acquired:
            _release(path)
