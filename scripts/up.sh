#!/usr/bin/env bash
# Start the full local stack (PostgreSQL, migrations, API) via Docker Compose.
set -euo pipefail

# shellcheck source=scripts/_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

require_cmd docker

echo "starting palimpsest (docker compose)…"
exec docker compose up --build "$@"
