# Runbook (EC2 + Docker Compose)

This runbook covers day‑to‑day ops for the single‑instance EC2 deployment.

## Quick health check
```
cd /home/ec2-user/fitness-platform
docker-compose ps
curl -s https://roman-fitness.duckdns.org/api/health
curl -s https://roman-fitness.duckdns.org/api/jobs -H "Authorization: Bearer $TOKEN"
```

## Deploy (manual)
```
cd /home/ec2-user/fitness-platform
git pull --rebase origin main
docker-compose up -d --build
```

## Restart a single service
```
docker-compose up -d --build api
docker-compose up -d --build worker
docker-compose up -d --build web
docker-compose up -d --build caddy
```

## Logs
```
docker logs --tail 200 fitness-platform-api-1
docker logs --tail 200 fitness-platform-worker-1
docker logs --tail 200 fitness-platform-caddy-1
```

## Pipeline / jobs visibility
```
curl -s https://roman-fitness.duckdns.org/api/job_runs -H "Authorization: Bearer $TOKEN"
curl -s https://roman-fitness.duckdns.org/api/job_dead_letters -H "Authorization: Bearer $TOKEN"
curl -s https://roman-fitness.duckdns.org/api/metrics | grep pipeline_step
```

## Backfill Strava streams (segments/PBs)
```
docker-compose exec -T api python services/ingestion/strava_streams_backfill.py --limit 200 --sleep 0.5
```

## Backfill weather (Open-Meteo)
```
docker-compose exec -T api python services/ingestion/weather_api_import.py --limit 200 --sleep 0.2
```

## Verify segments exist for a run
```
ACT_ID=1234567890
docker-compose exec -T api python scripts/diagnose_activity.py "$ACT_ID"
curl -s "https://roman-fitness.duckdns.org/api/activity/${ACT_ID}/segments" -H "Authorization: Bearer $TOKEN"
```

## Clear stale pipeline lock (last resort)
```
rm -f /home/ec2-user/fitness-platform/data/fitness_pipeline.lock
```

## Clear stale job runs (optional)
```
python3 - <<'PY'
import sqlite3
from datetime import datetime, timedelta, timezone
db="/home/ec2-user/fitness-platform/data/fitness.db"
cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
now = datetime.now(timezone.utc).isoformat()
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute(
    "UPDATE job_runs SET status='error', error='stale_run', finished_at=? "
    "WHERE status='running' AND started_at < ?",
    (now, cutoff),
)
conn.commit()
print("cleared stale:", cur.rowcount)
PY
```

## DB backup (SQLite)
```
./scripts/backup_db.sh
```

## Rollback
See `docs/ROLLBACK.md`.

## DNS / HTTPS
```
curl -I https://roman-fitness.duckdns.org
```

If cert issuance fails, confirm:
- Security group allows inbound 80/443
- `DOMAIN` in `.env` matches hostname
*** End Patch"} }']]],
