#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

if [[ -z "${APP_IMAGE:-}" ]]; then
  echo "APP_IMAGE is required."
  exit 1
fi

echo "Using image: ${APP_IMAGE}"
docker compose -f "${COMPOSE_FILE}" pull api
docker compose -f "${COMPOSE_FILE}" up -d db
docker compose -f "${COMPOSE_FILE}" run --rm api python -m alembic -c alembic.ini upgrade head
docker compose -f "${COMPOSE_FILE}" up -d api
docker image prune -f >/dev/null 2>&1 || true
echo "Deploy finished successfully."
