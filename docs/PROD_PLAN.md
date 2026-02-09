# Production Hardening Plan (Phased)

This is a parkable, staged plan to take the fitness-platform from local/dev to production readiness.

## Phase 0 — Baseline safety (complete)
- Env config + venv setup (`scripts/setup_env.py`, `.venv` bootstrap in `scripts/run_dev.py`)
- Run split (API/worker/dev) (`scripts/run_api.py`, `scripts/run_worker.py`, `scripts/run_dev.py`)
- Pipeline health + duration (`/api/health` exposes latest `pipeline_runs`)
- Basic tests + Jenkins steps (`scripts/run_tests.py`, `Jenkinsfile`, `scripts/smoke_api.py`)
- Docker artifacts validated (`scripts/verify_docker.sh`, `make docker-build`)

## Phase 1 — Security & identity (complete)
- JWT hardening: expiry enforcement, refresh token rotation + revocation
- Password policy + lockout/rate limiting (configurable limits)
- Password reset flow (admin/local CLI; email-based later)
- Secrets via vault/SSM Parameter Store (no `.env` in prod)
  - Assume **no Session Manager**. Use SSH + CI deploy to inject env from Parameter Store.
  - Added: `scripts/pull_ssm_env.sh` to materialize env from SSM.
  - Added: `scripts/reset_password.py` for single-user admin reset.

## Phase 2 — Data integrity & DB (complete)
- Schema constraints, foreign keys, unique indexes
- Idempotent ingestion (safe replays)
- Migration rollback plan
- Move off SQLite for prod (Postgres)
  - Phase 2 work started: weather_raw de-dupe + unique index, raw/normalized lookup indexes
  - Added DB integrity check script + foreign key enforcement on connections
  - Rollback guide documented in docs/ROLLBACK.md
  - Raw/stream ingestion now upserts to stay idempotent on replays
  - Idempotent ingestion audit complete (Strava API/local ingest, weather, segments, pipeline)
  - Postgres transition plan drafted: docs/POSTGRES_PLAN.md
  - Postgres implementation started: DB_URL support + Postgres schema/migrations added
  - Local Postgres test setup added: docker-compose.postgres.yml + scripts/pg_local_setup.sh

## Phase 3 — Reliability & jobs (in progress)
- Worker supervision + retry/backoff + circuit breakers
- Job scheduling with visibility + dead-letter handling
- Metrics on ingestion/processing latency and failure rate
- Strava delta sync (prod)
  - Replace local `run_all.js` with Strava API polling
  - Store cursor (`last_activity_at` / `last_activity_id`) in DB
  - Fetch deltas only on schedule + on app open
  - Add webhooks for near‑real‑time updates (Strava event subscription)
    - Verify signature + store events
    - Trigger ingestion on event
    - Fallback to low‑frequency poll (safety net)
  - Note: `run_all.js` remains **local‑only** for backfills; prod uses API polling/webhooks
  - Added job visibility endpoints: `GET /api/jobs`, `GET /api/job_runs`
  - Added stale run cleanup + jittered backoff in worker
  - Added per-step ingestion metrics (duration + failures) for worker + API sync
  - Added dead-letter visibility endpoint: `GET /api/job_dead_letters`

## Phase 4 — Observability (complete; Sentry optional)
- Structured logs, correlation IDs
- Metrics (Prometheus/OpenTelemetry)
- Error reporting (Sentry or similar)
  - Added request‑ID + structured request logging
  - Added lightweight `/metrics` endpoint (Prometheus‑style, self‑host friendly)
  - Added optional Sentry integration (API + worker via env)
  - Added `scripts/sentry_test.py` to validate event delivery

## Phase 5 — API quality
- Versioned API contracts
- OpenAPI tests + integration tests
- Consistent error model
- API contract tests for activity/summary/series endpoints (protect UI)
- Deterministic pipeline tests with seeded streams (pace smoothing, zones)
- Missing-stream warnings surfaced in API responses/logs
- Performance optimization plan (insights latency)
  - Measure: add query timing + slow query logging
  - Data shaping: avoid large JSON in list views, paginate aggressively
  - Indexes: verify indexes on time/user/activity type for insights
  - Cache: cache insights payloads with short TTL + invalidate on pipeline run
  - Pre-aggregation: materialize 7d/28d/12w metrics to avoid heavy recompute

## Phase 6 — UI + contracts (complete)
- Remove mock data
- API contract tests (frontend → backend)
- Performance budgets + caching

## Phase 6.5 — AI assistant groundwork (feature‑flagged, no LLM yet; in progress)
- DB tables: `context_events`, `objective_profiles`, `insight_sessions`
- Compaction stub: store raw events + rolling summaries
- API contracts (schemas only):
  - `GET /insights/daily`
  - `POST /insights/context`
  - `POST /insights/evaluate`
- No UI wiring or LLM calls yet

## Phase 6.6 — AI assistant (post‑hardening)
- Deterministic default recommendations
- Context drawer UI + feedback inputs
- LLM personalization with guardrails

## Phase 7 — Deployment & ops (complete; Terraform pending)
- CI/CD pipeline (GitHub Actions + AWS OIDC)
- Staging environment
- Infra as code (Terraform)
- Runbooks + alerts
  - Added SSH deploy workflow + `scripts/deploy.sh`
  - Added runbook (`docs/RUNBOOK.md`) and alerts checklist (`docs/ALERTS.md`)

## Phase 7.1 — Repo hygiene / cleanup (prep for prod)
- `.gitignore` hardening: remove/ignore `data/*.db`, WAL/SHM, `exports/`, `.DS_Store`, `__pycache__`, `.pytest_cache`, `.venv/`
- Remove unused/local‑only artifacts from repo
- Verify Docker image size + prune dev‑only deps

### AWS Free Tier deployment (target)
- EC2 t3.micro running Docker Compose (API + worker + web + caddy)
- RDS Postgres (free tier) for primary DB
- GitHub Actions deploys via AWS OIDC + **SSH** (no Session Manager)
