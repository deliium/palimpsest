#!/usr/bin/env bash
# Apply Alembic migrations using validated settings (PALIMPSEST_DATABASE_URL / .env).
set -euo pipefail

# shellcheck source=scripts/_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

require_cmd uv

ensure_env_file
load_database_url

exec "${UV_RUN[@]}" alembic upgrade head "$@"
