#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${FITNESS_BACKUP_DIR:-/app/data/backups}"
TARGET="${1:-}"

if [ -z "$TARGET" ]; then
  TARGET=$(ls -t "$BACKUP_DIR"/fitness-*.db.gz 2>/dev/null | head -n 1 || true)
fi

if [ -z "$TARGET" ] || [ ! -f "$TARGET" ]; then
  echo "Backup file not found." >&2
  exit 1
fi

TMP_DB=$(mktemp /tmp/fitness_backup_XXXXXX.db)
trap 'rm -f "$TMP_DB"' EXIT

gunzip -c "$TARGET" > "$TMP_DB"

python3 - <<PY
import sqlite3
conn = sqlite3.connect("$TMP_DB")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activities'")
if not cur.fetchone():
    raise SystemExit("Missing activities table")
cur.execute("SELECT COUNT(*) FROM activities")
count = cur.fetchone()[0]
print(f"Backup OK. activities count={count}")
PY
