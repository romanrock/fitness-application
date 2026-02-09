#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "[verify] Docker is not installed. Install Docker Desktop or Colima and re-run."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "[verify] docker compose not available. Install docker compose or docker-compose."
  exit 1
fi

echo "[verify] docker version"
docker version >/dev/null

echo "[verify] compose config"
"${COMPOSE[@]}" config >/dev/null

echo "[verify] compose build"
"${COMPOSE[@]}" build

echo "[verify] ok"
