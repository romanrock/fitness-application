# Fitness Platform Setup

## Docs
- `docs/PROD_PLAN.md`

## 1) Run the full dev app (single command)
```bash
python3 scripts/run_dev.py
```

This starts the worker (pipeline scheduler), API, and the React UI (Vite) together.
Set `RUN_MODE=prod` to disable dev conveniences later (no reload, no Vite/web server).
If `RUN_STRAVA_SYNC=1`, it will also run the Strava sync before importing data.
If this is your first run, create a user first:
```bash
python3 scripts/create_user.py yourname yourpassword --assign-existing
```
To reset a password locally (single-user admin flow):
```bash
python3 scripts/reset_password.py yourname
```
Password policy defaults: min 10 chars and at least 2 character classes (lower/upper/digit/symbol).

## 2) Run the pipeline only
```bash
python3 scripts/run_pipeline.py
```

This will initialize the DB if missing, apply migrations, import raw data, process metrics,
then start the API and web app. Migrations are required to create SQL views.
It also re-runs the pipeline every hour. Type `r` + Enter to run on demand.
If the virtualenv is missing, it will be created automatically.

## 2b) Run API + worker separately (recommended)
```bash
python3 scripts/run_api.py
python3 scripts/run_worker.py
```

Use this split in production-style setups. The API serves requests while the worker
handles ingestion + processing on a schedule.

## Notes
- `metrics_weekly` is a SQL view created by migrations.
- `setup_env.py` remains optional for manual/CI setup.
- A basic CI pipeline is defined in `Jenkinsfile`.
- `/api/health` now includes the last pipeline run status.
- Pipeline runs record duration and errors in `pipeline_runs`.
- Auth: JWT is enabled; in dev you can set `FITNESS_AUTH_DISABLED=1` to bypass.
- Repo hygiene: keep `.env`, `data/*.db*`, `exports/`, `.venv/`, and `.pytest_cache/` out of git.

Note: API runs on `http://127.0.0.1:8000`, web runs on `http://127.0.0.1:8788`.

## 2) Run steps manually (optional)
```bash
python3 scripts/init_db.py
python3 scripts/migrate_db.py
python3 services/ingestion/strava_import.py
python3 services/ingestion/weather_import.py
python3 services/processing/pipeline.py
```

## 3) Run the React UI (Vite) manually
```bash
cd apps/web
npm install
npm run dev
```

## Tests
```bash
python3 scripts/run_tests.py
```
Smoke test (starts API and calls `/api/health`):
```bash
python3 scripts/smoke_api.py
```
Note: This requires the environment to allow binding to localhost ports.

## 5) Run API (FastAPI)
```bash
uvicorn apps.api.main:app --reload
```

## 6) Open Web App
Serve `apps/web` from any static server (or add a simple Python server later).

## Docker (prod-style)
```bash
docker compose up --build
```
Note: Docker setup is pending on machines without Docker installed. Revisit once Docker Desktop (or Colima) is available locally.

## Docker build validation (Phase 0)
```bash
make docker-build
```
This validates the docker compose config and builds images without starting containers.

## Postgres (optional)
Quick local setup:
```bash
./scripts/pg_local_setup.sh
```
Or set `FITNESS_DB_URL` manually (e.g. `postgresql://user:pass@localhost:5432/fitness`) and run:
```bash
python3 scripts/migrate_db.py
```

## Production deployment (single instance)
1) Set environment (recommended via a local `.env` file, not committed):
```
RUN_MODE=prod
FITNESS_AUTH_DISABLED=0
FITNESS_JWT_SECRET=change-me
FITNESS_JWT_EXP_MINUTES=60
FITNESS_DB_PATH=/app/data/fitness.db
STRAVA_LOCAL_PATH=/app/strava-local-ingest
RUN_STRAVA_SYNC=1
FITNESS_CORS_ORIGINS=https://your-domain.example
FITNESS_REFRESH_ENABLED=0
FITNESS_REFRESH_TTL_DAYS=14
DOMAIN=your-domain.example
FITNESS_SENTRY_DSN=
FITNESS_SENTRY_TRACES_SAMPLE_RATE=0.0
FITNESS_SENTRY_PROFILES_SAMPLE_RATE=0.0
FITNESS_ENV=prod
FITNESS_RELEASE=
```

2) Start services:
```bash
docker compose up -d --build
```

3) Create user:
```bash
python3 scripts/create_user.py yourname yourpassword --assign-existing
```

Optional: verify Sentry is wired (requires `FITNESS_SENTRY_DSN`):
```bash
python3 scripts/sentry_test.py
```

## Backups (SQLite)
Use the helper script (inside the container or on the host with the DB volume mounted):
```bash
FITNESS_BACKUP_S3_BUCKET=your-bucket \
FITNESS_BACKUP_S3_PREFIX=fitness-platform \
./scripts/backup_db.sh
```

Restore:
```bash
gunzip /app/data/backups/fitness-<timestamp>.db.gz
mv /app/data/backups/fitness-<timestamp>.db /app/data/fitness.db
```

Verify latest backup:
```bash
./scripts/backup_verify.sh
```
