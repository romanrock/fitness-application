from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in some environments
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]

if load_dotenv:
    load_dotenv(ROOT / ".env")

DB_URL = os.getenv("FITNESS_DB_URL")
DB_PATH = Path(os.getenv("FITNESS_DB_PATH", ROOT / "data" / "fitness.db"))
LAST_UPDATE_PATH = Path(os.getenv("FITNESS_LAST_UPDATE_PATH", ROOT / "data" / "last_update.json"))
API_HOST = os.getenv("FITNESS_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("FITNESS_API_PORT", "8000"))
WEB_PORT = int(os.getenv("FITNESS_WEB_PORT", "8788"))
REFRESH_SECONDS = int(os.getenv("FITNESS_REFRESH_SECONDS", "3600"))
SYNC_ON_OPEN_SECONDS = int(os.getenv("FITNESS_SYNC_ON_OPEN_SECONDS", "900"))
RUN_MODE = os.getenv("RUN_MODE", "dev").lower()
STRAVA_LOCAL_PATH = Path(os.getenv("STRAVA_LOCAL_PATH", ROOT.parent / "strava-local-ingest"))
RUN_STRAVA_SYNC = os.getenv("RUN_STRAVA_SYNC", "1") == "1"
STRAVA_API_ENABLED = os.getenv("STRAVA_API_ENABLED", "0") == "1"
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
STRAVA_ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")
STRAVA_EXPIRES_AT = os.getenv("STRAVA_EXPIRES_AT")
JWT_SECRET = os.getenv("FITNESS_JWT_SECRET", "dev-secret")
JWT_ALG = os.getenv("FITNESS_JWT_ALG", "HS256")
JWT_EXP_MINUTES = int(os.getenv("FITNESS_JWT_EXP_MINUTES", "60"))
AUTH_DISABLED = os.getenv("FITNESS_AUTH_DISABLED", "1" if RUN_MODE == "dev" else "0") == "1"
AUTH_LOGIN_IP_LIMIT = int(os.getenv("FITNESS_AUTH_LOGIN_IP_LIMIT", "20"))
AUTH_LOGIN_USER_LIMIT = int(os.getenv("FITNESS_AUTH_LOGIN_USER_LIMIT", "5"))
AUTH_LOGIN_WINDOW_SEC = int(os.getenv("FITNESS_AUTH_LOGIN_WINDOW_SEC", "900"))
PW_MIN_LEN = int(os.getenv("FITNESS_PW_MIN_LEN", "10"))
PW_REQUIRE_CLASSES = int(os.getenv("FITNESS_PW_REQUIRE_CLASSES", "2"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FITNESS_CORS_ORIGINS",
        "http://127.0.0.1:8788,http://localhost:8788",
    ).split(",")
    if origin.strip()
]
REFRESH_ENABLED = os.getenv("FITNESS_REFRESH_ENABLED", "0") == "1"
REFRESH_TTL_DAYS = int(os.getenv("FITNESS_REFRESH_TTL_DAYS", "14"))

# HR zones configuration (HRR / Karvonen)
HR_REST = float(os.getenv("FITNESS_HR_REST", "48"))
HR_MAX = float(os.getenv("FITNESS_HR_MAX", "185"))
HR_ZONE_METHOD = os.getenv("FITNESS_HR_ZONE_METHOD", "hrr")

# Worker reliability settings
PIPELINE_MAX_RETRIES = int(os.getenv("FITNESS_PIPELINE_MAX_RETRIES", "2"))
PIPELINE_BACKOFF_BASE_SEC = float(os.getenv("FITNESS_PIPELINE_BACKOFF_BASE_SEC", "5"))
PIPELINE_BACKOFF_MAX_SEC = float(os.getenv("FITNESS_PIPELINE_BACKOFF_MAX_SEC", "120"))
PIPELINE_FAIL_THRESHOLD = int(os.getenv("FITNESS_PIPELINE_FAIL_THRESHOLD", "3"))
PIPELINE_COOLDOWN_SEC = int(os.getenv("FITNESS_PIPELINE_COOLDOWN_SEC", "900"))
