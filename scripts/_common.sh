# Shared helpers for local run scripts. Source only; do not execute.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_VERSION="$(tr -d '[:space:]' <"$ROOT/.python-version")"
UV_RUN=(uv run --frozen --python "$PYTHON_VERSION")

DEFAULT_DATABASE_URL='postgresql+asyncpg://palimpsest:palimpsest@127.0.0.1:5432/palimpsest'

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "error: required command not found: $name" >&2
    exit 1
  fi
}

ensure_env_file() {
  if [[ ! -f "$ROOT/.env" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    echo "created .env from .env.example"
  fi
  if ! grep -Eq '^[[:space:]]*PALIMPSEST_DATABASE_URL=' "$ROOT/.env"; then
    printf '\nPALIMPSEST_DATABASE_URL=%s\n' "$DEFAULT_DATABASE_URL" >>"$ROOT/.env"
    echo "enabled PALIMPSEST_DATABASE_URL in .env (development default)"
  fi
}

load_database_url() {
  if [[ -n "${PALIMPSEST_DATABASE_URL:-}" ]]; then
    return 0
  fi
  if [[ -f "$ROOT/.env" ]]; then
    # shellcheck disable=SC1091
    set -a
    # shellcheck disable=SC1090
    source "$ROOT/.env"
    set +a
  fi
  if [[ -z "${PALIMPSEST_DATABASE_URL:-}" ]]; then
    export PALIMPSEST_DATABASE_URL="$DEFAULT_DATABASE_URL"
  fi
}

wait_for_db() {
  local attempts=30
  local i
  for ((i = 1; i <= attempts; i++)); do
    if docker compose exec -T db pg_isready -U palimpsest -d palimpsest >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "error: database did not become ready in time" >&2
  exit 1
}
