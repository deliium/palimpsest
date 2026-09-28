#!/usr/bin/env bash
# Start the published stack. Does not build an image or install an editor.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

IMAGE="${PALIMPSEST_API_IMAGE:-ghcr.io/deliium/palimpsest:0.1.0}"
PORT="${PALIMPSEST_API_PUBLISH_PORT:-8080}"
URL="http://127.0.0.1:${PORT}/"
OPEN=0

log_info() {
  printf 'INFO %s\n' "$*"
}

fail() {
  printf 'ERROR startup_failed reason_code=%s\n' "$1" >&2
  exit 1
}

redact() {
  sed -E \
    -e 's#(://[^[:space:]/:]+:)[^@[:space:]]+@#\1***@#g' \
    -e 's#([Pp]assword|[Tt]oken|[Ss]ecret|[Aa]pi[_-]?[Kk]ey)[=:][^[:space:]]+#\1=***#g'
}

for arg in "$@"; do
  case "$arg" in
    --open) OPEN=1 ;;
    --build)
      printf 'The published start does not build. Use ./run-dev.sh\n' >&2
      fail "build_refused"
      ;;
    *)
      printf 'Unknown argument: %s\n' "$arg" >&2
      fail "unknown_argument"
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  fail "docker_missing"
fi
if ! docker info >/dev/null 2>&1; then
  fail "daemon_down"
fi
log_info "startup_docker_ok"
log_info "startup_pull_started image=${IMAGE}"

if ! docker compose -f compose.yaml pull; then
  printf 'The release image is unavailable. Contributors can start with ./run-dev.sh\n' >&2
  fail "pull_failed"
fi

if ! docker compose -f compose.yaml up -d --wait --wait-timeout 180; then
  docker compose -f compose.yaml ps --all 2>/dev/null | redact >&2 || true
  docker compose -f compose.yaml logs --no-color --tail 80 api 2>/dev/null | redact >&2 || true
  fail "health_timeout"
fi

printf 'Observer: %s\n' "$URL"
log_info "startup_ready url=${URL}"

if [[ "$OPEN" -eq 1 ]]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL"
  elif command -v open >/dev/null 2>&1; then
    open "$URL"
  else
    printf 'note: no browser launcher found; open %s\n' "$URL"
  fi
fi
