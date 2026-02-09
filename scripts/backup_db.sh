#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${FITNESS_DB_PATH:-/app/data/fitness.db}"
DB_URL="${FITNESS_DB_URL:-}"
BACKUP_DIR="${FITNESS_BACKUP_DIR:-/app/data/backups}"
S3_BUCKET="${FITNESS_BACKUP_S3_BUCKET:-}"
S3_PREFIX="${FITNESS_BACKUP_S3_PREFIX:-fitness-platform}"

if [[ -n "$DB_URL" ]]; then
  echo "Postgres detected (FITNESS_DB_URL set). Use pg_dump for backups." >&2
  exit 1
fi

if [ ! -f "$DB_PATH" ]; then
  echo "DB not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TS="$(date -u +"%Y%m%dT%H%M%SZ")"
BACKUP_PATH="$BACKUP_DIR/fitness-${TS}.db"

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB_PATH" ".backup '$BACKUP_PATH'"
else
  python3 - <<PY
import sqlite3
db_path = "${DB_PATH}"
backup_path = "${BACKUP_PATH}"
with sqlite3.connect(db_path) as conn:
    with sqlite3.connect(backup_path) as dest:
        conn.backup(dest)
PY
fi

gzip -f "$BACKUP_PATH"
GZ_PATH="$BACKUP_PATH.gz"

echo "Backup created: $GZ_PATH"

if [ -n "$S3_BUCKET" ]; then
  if command -v aws >/dev/null 2>&1; then
    aws s3 cp "$GZ_PATH" "s3://$S3_BUCKET/$S3_PREFIX/"
    echo "Uploaded to s3://$S3_BUCKET/$S3_PREFIX/"
  else
    echo "AWS CLI not found; cannot upload backup. Install awscli or unset FITNESS_BACKUP_S3_BUCKET." >&2
    exit 2
  fi
else
  echo "FITNESS_BACKUP_S3_BUCKET not set; skipping upload."
fi
