# Fitness Platform (Python + SQLite + Web)

This is the next‑gen, structured version of the local Strava tooling.

## Goals
- Multi‑source ingestion (Strava, weather, Garmin, golf)
- Normalization + analytics pipeline
- SQLite for local dev (upgradeable to Postgres)
- Small web app (PWA‑ready) + API

## Data Layers
- Raw: `activities_raw`, `streams_raw`, `weather_raw`
- Normalized/Processed: `activities_norm` (HR normalization + cleaned metrics)
- Calculated: `activities_calc` (derived metrics ready for analysis)
- View: `metrics_weekly` (SQL view for weekly rollups)

Migrations are required after init to create views and new tables.

## Structure
- `apps/api` — FastAPI backend
- `apps/web` — React + Vite web app (PWA-ready)
- `services/` — auth, ingestion, processing, presentation
- `packages/` — shared logic + connectors
- `database/` — schemas + migrations
- `infra/terraform` — AWS infra (later)

## Next step
Production hardening + more data sources (see `docs/PROD_PLAN.md`).

## Quick start
```bash
python3 scripts/run_dev.py
```

## Documentation
- `docs/SETUP.md`
- `docs/PROD_PLAN.md`

## CI readiness
- `Jenkinsfile` included
- `Dockerfile` + `docker-compose.yml` provided

## React UI
```bash
cd apps/web
npm install
npm run dev
```

Then open:
- API: http://127.0.0.1:8000
- Web: http://127.0.0.1:8788

While it runs:
- Pipeline refreshes hourly
- Type `r` + Enter to refresh on demand

## Config
Set environment variables in `.env` (see `.env.example`). In `RUN_MODE=prod`, dev servers and reload are disabled.
Create a user before ingestion:
```bash
python3 scripts/create_user.py yourname yourpassword --assign-existing
```

## Runtime split (recommended for prod-like use)
```bash
python3 scripts/run_api.py
python3 scripts/run_worker.py
```

Run the API and worker separately to avoid pipeline work impacting API availability.

## Health & status
- `/api/health` includes last pipeline run status and counts.
- Pipeline runs include duration and last error message.

## Auth
- Login: `POST /api/auth/login` with `{"username":"...","password":"..."}`.
- Use `Authorization: Bearer <token>` for API calls.
- For local dev, set `FITNESS_AUTH_DISABLED=1` to bypass.

## Docker (prod-style)
```bash
docker compose up --build
```

Services:
- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:8788` (proxies `/api` to API)
