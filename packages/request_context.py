from contextvars import ContextVar
from contextlib import contextmanager


request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
job_run_id_var: ContextVar[str | None] = ContextVar("job_run_id", default=None)


@contextmanager
def job_run_context(run_id: int | str | None):
    token = job_run_id_var.set(str(run_id) if run_id is not None else None)
    try:
        yield
    finally:
        job_run_id_var.reset(token)
