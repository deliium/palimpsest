#!/usr/bin/env bash
# Contributor path: build the local image, including the web export, then start.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  printf 'ERROR startup_failed reason_code=%s\n' "docker_missing" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  printf 'ERROR startup_failed reason_code=%s\n' "daemon_down" >&2
  exit 1
fi
printf 'INFO startup_docker_ok\n'

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  PALIMPSEST_REVISION="$(git rev-parse HEAD)"
else
  PALIMPSEST_REVISION="unknown"
fi
export PALIMPSEST_REVISION

exec docker compose -f compose.yaml -f compose.dev.yaml up -d --build --wait --wait-timeout 180
