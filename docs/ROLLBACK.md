# DB Rollback Guide (SQLite)

Use this when a migration or pipeline step goes wrong.

## Before migrations
1. Stop the API/worker (or run in maintenance mode).
2. Create a backup:
   - `bash scripts/backup_db.sh`

This writes a timestamped copy under `data/backups/`.

## Rollback steps
1. Stop the API/worker.
2. Restore the latest backup:
   - `cp data/backups/fitness.db.<timestamp> data/fitness.db`
3. Restart services.

## Verify integrity
Run:
```
python3 scripts/db_integrity_check.py
```

If you need to re‑apply migrations after rollback, run:
```
python3 scripts/migrate_db.py
```
