# Development

[← Previous Page](configuration.md) · [Back to README](../README.md)

## Locked environment

```bash
uv sync --frozen --python 3.12.14
```

Do not omit `--frozen` in development or containers. The reference interpreter is **3.12.14**.

## WorldEngine

`simulation.WorldEngine` is the sole public mutation authority. Construct it from `SimulationRunConfig` (required seed) and immutable `WorldBootstrap`, then:

1. `observe()` → `ObservationBatch` with an engine-issued `TickToken`
2. Submit an ordered sequence of `ActionSubmission(token, AgentId, AgentCommand)`
3. `resolve_tick(...)` → `TickResult` and atomic commit to tick N+1

Equivalent bootstrap + seed + ordered submissions must produce identical ticks, revisions, resolutions, objective events, and schema-1 export bytes. Lifecycle types and bootstrap are not schema-1 wire values. See [Architecture](architecture.md).

## Tests

Default pytest excludes live infrastructure:

```bash
uv run --frozen --python 3.12.14 pytest
# equivalent addopts: -m "not integration and not compose"
```

| Command | What it covers |
| --- | --- |
| `uv run --frozen --python 3.12.14 pytest` | Unit + architecture (no Docker, no PostgreSQL) |
| `uv run --frozen --python 3.12.14 pytest -m integration` | Disposable Postgres via `PALIMPSEST_TEST_DATABASE_URL` |
| `uv run --frozen --python 3.12.14 pytest -m compose` | Compose file checks and optional stack smoke |
| `uv run --frozen --python 3.12.14 ruff check src tests` | Lint |
| `uv run --frozen --python 3.12.14 mypy src tests` | Strict typing |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_packaging.py` | Wheel install / package discovery |

Integration tests **fail** in CI if `PALIMPSEST_TEST_DATABASE_URL` is missing; locally they **skip** with a warning. The URL must name a disposable `palimpsest_test` database. Unsafe names (`postgres`, `template0`, `template1`) are rejected before migration. `CREATE EXTENSION vector` requires privilege; limitation skips locally with WARNING.

Compose tests never run in the default suite. The smoke test uses a unique Compose project name and `PALIMPSEST_API_PUBLISH_PORT`, captures **redacted** logs on failure, and always `down --volumes --remove-orphans` for that project only.

Set `PALIMPSEST_TEST_DEBUG=1` for concise test-harness DEBUG on stderr.

## Migrations

Alembic does **not** store a database URL in `alembic.ini`. `alembic/env.py` loads validated settings (`PALIMPSEST_DATABASE_URL`, or the test URL for integration).

```bash
./scripts/migrate.sh
# or:
export PALIMPSEST_DATABASE_URL='postgresql+asyncpg://palimpsest:palimpsest@127.0.0.1:5432/palimpsest'
uv run --frozen --python 3.12.14 alembic upgrade head
```

Revision `0001` runs `CREATE EXTENSION IF NOT EXISTS vector` and creates no application tables. Downgrade is a documented no-op. Never use `metadata.create_all()`.

## Local run scripts

Convenience wrappers live under `scripts/` (repo root as cwd):

| Script | Equivalent |
| --- | --- |
| `./scripts/up.sh` | `docker compose up --build` |
| `./scripts/down.sh` | `docker compose down` |
| `./scripts/api.sh` | Compose `db` → `alembic upgrade head` → host Uvicorn `--reload` |
| `./scripts/migrate.sh` | `uv run --frozen --python 3.12.14 alembic upgrade head` |

`api.sh` and `migrate.sh` create `.env` from `.env.example` when missing and ensure a development `PALIMPSEST_DATABASE_URL` is set. They still honor an already-exported URL or an existing `.env`.

## Local API

Runtime requires `PALIMPSEST_DATABASE_URL`. Preferred:

```bash
./scripts/api.sh
```

Factory entrypoint without the wrapper:

```bash
uv run --frozen --python 3.12.14 uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8080
```

`GET /health` returns exactly `{"status":"ok"}` without querying PostgreSQL. Unsupported methods return 405. `X-Request-ID` is accepted when safe, otherwise generated.

## Docker Compose

```bash
./scripts/up.sh
# or: docker compose up --build
```

Order: database health → one-shot `alembic upgrade head` → API. The API image runs Uvicorn as uid **1001** on port 8080. Healthcheck uses Python `urllib`, not `curl`.

Images are digest-pinned (Python 3.12.14 slim, pgvector PostgreSQL 17). Install uses `uv sync --frozen --no-dev --no-editable`. Compose builds use `network: host` so `uv` can resolve PyPI when the Docker bridge DNS is unavailable. Manual image builds on the same hosts may need `docker build --network=host`.

Development passwords in `compose.yaml` are **non-production**. Expanded `docker compose config` output is **not secret-safe**. Production extension-privilege design is deferred.

```bash
docker compose config --quiet
uv run --frozen --python 3.12.14 pytest -m compose
./scripts/down.sh
```

## See also

- [Architecture](architecture.md)
- [Configuration](configuration.md)
