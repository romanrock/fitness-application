import logging
import os

from .request_context import job_run_id_var, request_id_var


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        record.job_run_id = job_run_id_var.get() or "-"
        return True


class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get() or "-"
        if not hasattr(record, "job_run_id"):
            record.job_run_id = job_run_id_var.get() or "-"
        return super().format(record)


def setup_logging() -> None:
    level = os.getenv("FITNESS_LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # Ensure every LogRecord has request_id so formatters never fail.
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get() or "-"
        if not hasattr(record, "job_run_id"):
            record.job_run_id = job_run_id_var.get() or "-"
        return record

    logging.setLogRecordFactory(record_factory)

    log_format = (
        "%(asctime)s %(levelname)s %(name)s "
        "request_id=%(request_id)s job_run_id=%(job_run_id)s %(message)s"
    )
    logging.basicConfig(level=level, format=log_format)

    root = logging.getLogger()
    root.addFilter(ContextFilter())

    formatter = SafeFormatter(log_format)
    # Add filter + formatter to all handlers to keep request_id in sync.
    for handler in root.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(ContextFilter())
