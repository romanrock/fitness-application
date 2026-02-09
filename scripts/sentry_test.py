import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.error_reporting import init_error_reporting

try:
    import sentry_sdk
except ImportError:  # pragma: no cover - optional dependency
    sentry_sdk = None


def main() -> int:
    if sentry_sdk is None:
        print("sentry_sdk is not installed.")
        return 1
    if not init_error_reporting("sentry_test"):
        print("FITNESS_SENTRY_DSN is not set.")
        return 1
    sentry_sdk.capture_message("fitness-platform test event", level="info")
    sentry_sdk.flush(timeout=5)
    print("sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
