#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[pg] starting local postgres..."
if command -v docker-compose >/dev/null 2>&1; then
  docker-compose -f docker-compose.postgres.yml up -d
else
  docker compose -f docker-compose.postgres.yml up -d
fi

echo "[pg] waiting for postgres..."
for i in {1..20}; do
  if (command -v docker-compose >/dev/null 2>&1 && docker-compose -f docker-compose.postgres.yml exec -T postgres pg_isready -U fitness -d fitness >/dev/null 2>&1) || \
     (docker compose -f docker-compose.postgres.yml exec -T postgres pg_isready -U fitness -d fitness >/dev/null 2>&1); then
    echo "[pg] ready"
    break
  fi
  sleep 1
done

export FITNESS_DB_URL="${FITNESS_DB_URL:-postgresql://fitness:fitness@127.0.0.1:5432/fitness}"
echo "[pg] using FITNESS_DB_URL=$FITNESS_DB_URL"
echo "[pg] running migrations..."
PYTHONPATH="$ROOT_DIR" python3 scripts/migrate_db.py
echo "[pg] done"
