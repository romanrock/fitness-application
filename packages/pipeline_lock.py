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
    if (time.time() - mtime) > _lock_ttl():
        return True

    # If the lock holder process is gone, treat as stale even if within TTL.
    try:
        payload = ""
        with open(path, "r", encoding="utf-8") as f:
            payload = f.read()
        pid = None
        for part in payload.split():
            if part.startswith("pid="):
                try:
                    pid = int(part.split("=", 1)[1])
                except ValueError:
                    pid = None
                break
        if pid is None or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return False
        except ProcessLookupError:
            return True
        except PermissionError:
            # PID exists but we can't signal it; assume it's alive.
            return False
        except OSError:
            return False
    except OSError:
        return False


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
