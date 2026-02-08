# Deployment Notes (EC2)

## Environment and DNS
- HTTPS requires a hostname (not a raw IP).
- DuckDNS setup used: `roman-fitness.duckdns.org`.
- Update DuckDNS with the public IP:
  - `curl "https://www.duckdns.org/update?domains=roman-fitness&token=TOKEN&ip=$(curl -s https://checkip.amazonaws.com)"`
- Ensure `/home/ec2-user/fitness-platform/.env` contains:
  - `DOMAIN=roman-fitness.duckdns.org`
  - `STRAVA_API_ENABLED=1` (when switching to API-based sync)
  - `RUN_STRAVA_SYNC=0` (disable local ingest)

## Security group
Allow inbound:
- TCP 80 from 0.0.0.0/0
- TCP 443 from 0.0.0.0/0

## Caddy
- Caddyfile expects `DOMAIN` from `.env`:
  - `{$DOMAIN} { ... }`
- Restart:
  - `docker-compose up -d caddy`
- Verify:
  - `curl -I https://roman-fitness.duckdns.org`

## Docker compose on EC2
- Pull latest changes from git:
  - `git pull --rebase origin main`
- Recreate services:
  - `docker-compose up -d --build caddy worker`
  - `docker-compose up -d --build api` (after `.env` updates or sync logic changes)
 - Pipeline lock is shared across containers via:
   - `FITNESS_PIPELINE_LOCK_PATH=/app/data/fitness_pipeline.lock`

## Worker health
- Worker uses `RUN_STRAVA_SYNC` and `PYTHONPATH` to avoid missing local ingest artifacts.
- Defaults:
  - `RUN_STRAVA_SYNC=0` (set in docker-compose)
  - `PYTHONPATH=/app`
- Healthcheck uses:
  - `PYTHONPATH=/app python scripts/worker_healthcheck.py`

## Strava API sync
- Set these in `.env` before enabling API sync:
  - `STRAVA_CLIENT_ID`
  - `STRAVA_CLIENT_SECRET`
  - `STRAVA_REFRESH_TOKEN`
  - `STRAVA_ACCESS_TOKEN` (optional; refresh token will update this)
  - `STRAVA_EXPIRES_AT` (optional)

## Notes
- Keep secrets in `.env` on EC2; do not commit to git.
- Code/config changes should be committed and pulled on EC2.
