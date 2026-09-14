#!/usr/bin/env bash
# Stop the Compose stack. Pass --volumes to remove the Postgres volume.
set -euo pipefail

# shellcheck source=scripts/_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

require_cmd docker

exec docker compose down "$@"
