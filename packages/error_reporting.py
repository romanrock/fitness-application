import logging
import os

try:  # Optional dependency
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
except ImportError:  # pragma: no cover - optional
    sentry_sdk = None
    FastApiIntegration = None
    LoggingIntegration = None
    StarletteIntegration = None


def _float_env(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def init_error_reporting(service_name: str, enable_fastapi: bool = False) -> bool:
    dsn = os.getenv("FITNESS_SENTRY_DSN")
    if not dsn or sentry_sdk is None:
        return False

    integrations = []
    if LoggingIntegration is not None:
        integrations.append(LoggingIntegration(level=logging.INFO, event_level=logging.ERROR))
    if enable_fastapi and FastApiIntegration is not None and StarletteIntegration is not None:
        integrations.extend([FastApiIntegration(), StarletteIntegration()])

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("FITNESS_ENV", os.getenv("RUN_MODE", "prod")),
        release=os.getenv("FITNESS_RELEASE"),
        traces_sample_rate=_float_env("FITNESS_SENTRY_TRACES_SAMPLE_RATE", 0.0),
        profiles_sample_rate=_float_env("FITNESS_SENTRY_PROFILES_SAMPLE_RATE", 0.0),
        integrations=integrations,
        send_default_pii=False,
    )
    sentry_sdk.set_tag("service", service_name)
    return True
