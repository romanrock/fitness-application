# Production Hardening Plan (Phased)

Parkable plan to take the fitness-platform from local/dev to production readiness, while keeping EC2 (single instance) and local development in sync.

## Status snapshot (2026-02-11)
- Running stack (prod): Docker Compose on a single EC2 instance (API + worker + web + Caddy).
- DB (prod): SQLite on a shared volume (WAL + busy_timeout). Postgres support exists (`FITNESS_DB_URL`), but **not cut over**.
- Ingestion (prod): Strava API delta sync + hourly worker scheduler + manual trigger (`POST /api/sync?force=1`).
- Legacy/local ingest: `strava-local-ingest` is **no longer mounted in prod**; local artifact imports (weather/segments) are optional behind `FITNESS_ENABLE_LOCAL_ARTIFACT_IMPORT=1`.
- Assistant: deterministic insights + optional OpenAI-backed chat (`OPENAI_API_KEY` + `OPENAI_MODEL`), context events stored + memory compaction stub. UI wiring is partial; some reliability/perf work remains.
- Observability: structured logs + `/api/metrics` (Prometheus-style). Sentry support is optional (not configured by default).
- Tests: `python3 scripts/run_tests.py` is green.

## Phase 0 — Baseline safety (complete)
- Env config + venv setup (`scripts/setup_env.py`)
- Run split scripts (`scripts/run_api.py`, `scripts/run_worker.py`, `scripts/run_dev.py`)
- Pipeline health (`GET /api/health`)
- Basic tests + CI artifacts (`scripts/run_tests.py`, `Jenkinsfile`, `scripts/smoke_api.py`)
- Docker artifacts validated (`scripts/verify_docker.sh`, `make docker-build`)

## Phase 1 — Security & identity (complete for single-user)
- JWT expiry enforcement + refresh tokens (rotation + revocation)
- Password policy + login rate limits (per-IP and per-user)
- Password reset: admin/local CLI (`scripts/reset_password.py`) (email reset is a later add-on)
- Secrets management: SSM Parameter Store helper (`scripts/pull_ssm_env.sh`)
  - Assume **no Session Manager**. Use SSH/CloudShell + deploy scripts.

Remaining gaps (acceptable for now):
- No MFA, no email-based reset, no user self-service flows beyond login.
- No audit log / admin UI.

## Phase 2 — Data integrity & DB (in progress)
- Constraints + indexes + basic integrity checks in SQLite migrations.
- Idempotent ingestion (safe replays) + upserts.
- Rollback guide documented (`docs/ROLLBACK.md`).
- Postgres groundwork exists:
  - `FITNESS_DB_URL` support in `packages/db.py`
  - Postgres schema/migrations (`database/schemas/schema_pg.sql`, `database/migrations_pg/`)
  - Local PG helpers (`docker-compose.postgres.yml`, `scripts/pg_local_setup.sh`)

Remaining gaps (production blockers for growth):
- Still running SQLite in prod (multi-container write contention risk). Cutover plan to RDS Postgres is still TBD.

## Phase 3 — Reliability & jobs (complete baseline; iterate)
- Worker retry/backoff + cooldown + stale run cleanup.
- Job visibility endpoints:
  - `GET /api/jobs`, `GET /api/job_runs`, `GET /api/job_dead_letters`
- Per-step ingestion metrics:
  - `pipeline_step_runs_total`, `pipeline_step_failures_total`, `pipeline_step_duration_seconds`
- Locking:
  - Pipeline lock file (`FITNESS_PIPELINE_LOCK_PATH`) to avoid concurrent runs.

Remaining gaps:
- No distributed locking (needed once Postgres/multi-instance exists).
- No queueing system; everything is “in-process jobs”.

## Phase 4 — Observability (complete; Sentry optional)
- Structured logs, request IDs.
- `/api/metrics` endpoint.
- Optional Sentry integration + `scripts/sentry_test.py` (requires a real DSN).

## Phase 5 — API quality (complete baseline; iterate)
- Stable error model.
- Versioned routes (`/api/...` and `/api/v1/...`) for backwards compatibility.
- Contract + e2e + determinism tests:
  - `tests/test_api_contract_http.py`
  - `tests/test_e2e_http.py`
  - `tests/test_e2e_metrics.py`
  - `tests/test_pipeline_deterministic.py`

Remaining gaps:
- `/metrics` and some internal endpoints are unauthenticated (acceptable for private single-user; lock down before “public”).
- FastAPI startup events use deprecated `on_event` (move to lifespan).

## Phase 6 — UI + contracts (in progress)
- Dashboard UI backed by real API data.
- Sync-on-load exists, but needs polish (loading states + consistency + perf).

Remaining gaps:
- Perceived latency: initial dashboard load can be 4–7s (needs caching + lighter payloads + pre-aggregation).

## Phase 6.5 — Assistant groundwork (complete)
- Tables: `context_events`, `objective_profiles`, `insight_sessions`, `assistant_memory`.
- Memory compaction stub: summarize recent sessions and store rolling memory.
- API stubs shipped:
  - `GET /api/insights/daily`
  - `POST /api/insights/context`
  - `POST /api/insights/evaluate`

## Phase 6.6 — Assistant (in progress)
- Deterministic baseline answer exists even without OpenAI.
- OpenAI provider integrated when `OPENAI_API_KEY` is set.

Remaining gaps:
- “On-load” assistant card: should always show a Today recommendation + Trend + predicted 5k/10k without needing chat.
- Better chat UX (streaming, retries, clearer errors, faster first token).
- Context model: convert raw events into “memories” consistently (compaction + retrieval quality).
- Guardrails: cost controls + timeouts + logging around model calls.

## Phase 7 — Deployment & ops (complete docs; Terraform pending)
- Deploy docs + scripts (`docs/DEPLOY.md`, `scripts/deploy.sh`)
- Runbook + alerts checklist (`docs/RUNBOOK.md`, `docs/ALERTS.md`)
- Staging is documented as “minimal”, not automated.

Remaining gaps:
- Terraform/RDS/Network IaC not implemented.

## Repo hygiene / deprecation targets (next)
- Fully deprecate/remove `strava-local-ingest` dependency:
  - Keep `FITNESS_ENABLE_LOCAL_ARTIFACT_IMPORT=1` as a temporary backfill escape hatch.
  - Replace weather/segments imports with native implementations (Strava API + Open-Meteo).
