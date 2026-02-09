# Alerts Checklist

Minimal alerting targets for single‑instance EC2.

## Availability
- API health endpoint failing (`/api/health`)
- HTTPS endpoint unreachable (Caddy down)

## Data pipeline
- `job_runs` has a run stuck in `running` > 30 min
- `job_dead_letters` non‑empty
- `pipeline_step_failures_total` increases rapidly

## Performance
- `/api/insights` > 3s p95 (user‑perceived slowness)
- `/api/activities` > 1s p95

## Storage
- EC2 disk usage > 80%
- SQLite DB size growth spikes

## Security
- Repeated auth failures (`http_401` spikes)
*** End Patch} }],
