# Thread Handoff Summary

## Current focus (tests failing)
- Failing tests: `tests/test_e2e_metrics.py`
  - `test_activity_summary_has_pace_and_notes`
  - `test_insights_recovery_index_fallback`
  - `test_decoupling_series_meta_when_hr_missing`
  - `test_weekly_and_volume_series_present`
- Last error signature (pytest):
  - Returns `{"db": "missing"}` for:
    - `activities.activity_summary(...)`
    - `insights.insights(...)`
    - `insights.insights_series(...)`
    - `activities.weekly(...)`
  - Assertions fail because values are `None`.
- Hypothesis: helpers are reading real DB path instead of temp DB from tests.
- Next files to inspect for DB path mismatch:
  - `packages/config.py` (DB_PATH / FITNESS_DB_PATH)
  - `apps/api/deps.py` (get_db / db connection creation)
  - `apps/api/utils.py` (db helpers)
  - Possibly `apps/api/routes/activities.py`, `apps/api/routes/insights.py`

## Last explicit step completed
- Step 1: opened/reviewed `tests/test_e2e_metrics.py`; no changes made, no validation yet.
- Step 2 pending: inspect DB path usage and wiring.

---

## Production plan (docs/PROD_PLAN.md)
- Phase 0 — Baseline safety (env/venv, run split, pipeline health, basic tests, docker artifacts)
- Phase 1 — Security & identity (JWT hardening, secrets mgmt)
- Phase 2 — Data integrity & DB (constraints, idempotent ingest, rollback, Postgres)
- Phase 3 — Reliability & jobs (supervision, retries, scheduler + metrics)
- Phase 4 — Observability (structured logs, metrics, error reporting)
- Phase 5 — API quality (versioning, OpenAPI tests)
- Phase 6 — UI + contracts (remove mocks, contract tests, perf budgets)
- Phase 7 — Deployment & ops (CI/CD, staging, Terraform, runbooks)

---

## LLM assistant feature (to include in plan)
- Requirements:
  - Answer: “What should I do today? How am I trending?”
  - App should ask follow-up questions when context missing.
  - Store context indefinitely but compact/aggregate over time.
  - Personal app: store whatever needed; privacy not a constraint.
  - “Deepest understanding over time” is priority.
- Minimal groundwork for scheduling/DB phase: add tables + API contract stubs (no LLM yet).
