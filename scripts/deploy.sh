#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "[deploy] Pulling latest code..."
git fetch --all --prune
git checkout main
git pull origin main

echo "[deploy] Building and starting containers..."
if command -v docker-compose >/dev/null 2>&1; then
  docker-compose up -d --build
else
  docker compose up -d --build
fi

echo "[deploy] Done."
