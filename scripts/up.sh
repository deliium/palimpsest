#!/usr/bin/env bash
# Start the published stack. This is the same pull path as ./run.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for arg in "$@"; do
  if [[ "$arg" == "--build" ]]; then
    printf 'The published start does not build. Use ./run-dev.sh\n' >&2
    printf 'ERROR startup_failed reason_code=%s\n' "build_refused" >&2
    exit 1
  fi
done

exec "$ROOT/run.sh" "$@"
