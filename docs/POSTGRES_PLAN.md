# Postgres Transition Plan

Goal: move production from SQLite to Postgres while keeping local dev simple.
Non‑goal: rewrite the app around a full ORM; keep SQL + migrations working.

## Phase 2A — Prepare code for dual DB
- Add `FITNESS_DB_URL` support (e.g. `postgresql://user:pass@host:5432/fitness`).
- Keep `FITNESS_DB_PATH` for SQLite; prefer DB_URL when set.
- Centralize DB connection in one module (single entrypoint).
- Ensure `PRAGMA foreign_keys` is only applied for SQLite.

## Phase 2B — Make migrations Postgres‑safe
- Audit current SQL migrations for SQLite‑only syntax.
- Create Postgres‑safe variants if needed (e.g. `database/migrations_pg/`).
- Keep `schema_migrations` table consistent across both backends.
- Add a quick migration test against Postgres (local docker).

## Phase 2C — Data migration path
- Add export script for SQLite → CSV (one file per table).
- Add import script for Postgres using `COPY` (or `psql \\copy`).
- Preserve `user_id`, `source_id`, and timestamps.
- Validate row counts + spot check a few activities.

## Phase 2D — Cutover + rollback
- Cutover plan: stop app → export → import → run migrations → start app.
- Rollback plan: keep last SQLite backup; revert `FITNESS_DB_URL` to `FITNESS_DB_PATH`.
- Verify `/api/health` and a few API endpoints after cutover.

## Proposed local docker (for testing)
- Add `docker-compose.postgres.yml` later with a `postgres` service.
- Wire `FITNESS_DB_URL` via `.env` when testing.

## Acceptance criteria
- Migrations run cleanly on Postgres.
- API + worker operate on Postgres with no code changes outside DB adapter.
- Data parity: activities + streams + weather counts match after migration.
