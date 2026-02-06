# Production Hardening Plan (Phased)

This is a parkable, staged plan to take the fitness-platform from local/dev to production readiness.

## Phase 0 — Baseline safety
- Env config + venv setup
- Run split (API/worker/dev)
- Pipeline health + duration
- Basic tests + Jenkins steps
- Docker artifacts (not validated)

## Phase 1 — Security & identity
- JWT hardening: expiry enforcement, refresh tokens, rotation, revocation
- Password policy, lockout, rate limiting
- Secrets via vault/SSM (no `.env` in prod)

## Phase 2 — Data integrity & DB
- Schema constraints, foreign keys, unique indexes
- Idempotent ingestion (safe replays)
- Migration rollback plan
- Move off SQLite for prod (Postgres)

## Phase 3 — Reliability & jobs
- Worker supervision + retry/backoff + circuit breakers
- Job scheduling with visibility + dead-letter handling
- Metrics on ingestion/processing latency and failure rate

## Phase 4 — Observability
- Structured logs, correlation IDs
- Metrics (Prometheus/OpenTelemetry)
- Error reporting (Sentry or similar)

## Phase 5 — API quality
- Versioned API contracts
- OpenAPI tests + integration tests
- Consistent error model
- API contract tests for activity/summary/series endpoints (protect UI)
- Deterministic pipeline tests with seeded streams (pace smoothing, zones)
- Missing-stream warnings surfaced in API responses/logs

## Phase 6 — UI + contracts
- Remove mock data
- API contract tests (frontend → backend)
- Performance budgets + caching

## Phase 7 — Deployment & ops
- CI/CD pipeline (GitHub Actions + AWS OIDC)
- Staging environment
- Infra as code (Terraform)
- Runbooks + alerts

### AWS Free Tier deployment (target)
- EC2 t3.micro running Docker Compose (API + worker + web + caddy)
- RDS Postgres (free tier) for primary DB
- GitHub Actions deploys via AWS OIDC + SSM run-command
