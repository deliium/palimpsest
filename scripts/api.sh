#!/usr/bin/env bash
# Run the API on the host against Compose Postgres (db only).
# Starts the database if needed, applies migrations, then Uvicorn with reload.
set -euo pipefail

# shellcheck source=scripts/_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

require_cmd docker
require_cmd uv

ensure_env_file
load_database_url

echo "ensuring dependencies…"
uv sync --frozen --python "$PYTHON_VERSION"

echo "starting Postgres (compose service: db)…"
docker compose up -d db
wait_for_db

echo "applying migrations…"
"${UV_RUN[@]}" alembic upgrade head

host="${PALIMPSEST_API_HOST:-127.0.0.1}"
port="${PALIMPSEST_API_PORT:-8080}"

echo "API listening on http://${host}:${port}  (GET /health)"
exec "${UV_RUN[@]}" uvicorn api.app:create_app \
  --factory \
  --host "$host" \
  --port "$port" \
  --reload
