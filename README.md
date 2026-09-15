# Palimpsest

Reproducible, discrete, text-based multi-agent AI society experiments.

This repository is a **Python 3.12+ modular monolith**. It establishes package boundaries, V1 typed domain contracts, an authoritative deterministic `WorldEngine` tick loop (observe → ordered submissions → resolve), schema-v1 event export, configuration, persistence, an HTTP liveness API, observability, and containers. Agent cognition and LLM invocation stay outside the engine.

## Requirements

- Python **3.12.14** (reference pin in `.python-version`; `requires-python = ">=3.12"`)
- [uv](https://docs.astral.sh/uv/) with a committed `uv.lock`
- Optional: PostgreSQL 17 with pgvector for integration tests
- Optional: Docker Compose v2 for the development stack

## Install

```bash
uv sync --frozen --python 3.12.14
```

Locked installs do not re-resolve dependencies. Copy `.env.example` to `.env` only when you need local overrides.

## Quick start

```bash
# Full stack (Postgres + migrations + API) via Docker Compose
./scripts/up.sh

# Or: API on the host with Compose Postgres only (reload)
./scripts/api.sh

# Unit and architecture tests (no Docker, no PostgreSQL)
uv run --frozen --python 3.12.14 pytest

# API liveness
curl -s http://127.0.0.1:8080/health
# {"status":"ok"}
```

| Script | Purpose |
| --- | --- |
| `./scripts/up.sh` | `docker compose up --build` (full stack) |
| `./scripts/api.sh` | Host Uvicorn + Compose `db`, migrate, `--reload` |
| `./scripts/migrate.sh` | `alembic upgrade head` against configured DSN |
| `./scripts/down.sh` | `docker compose down` (add `--volumes` to drop data) |

Development credentials in `compose.yaml` are **not production**. `docker compose config` expands values and is **not secret-safe**.

## Documentation

| Page | Contents |
| --- | --- |
| [Architecture](docs/architecture.md) | Bounded packages, `WorldEngine` lifecycle, public facades, eleven invariants, deferred scope |
| [Configuration](docs/configuration.md) | `PALIMPSEST_` settings, logging, redaction, seeds, identifiers, clocks |
| [Development](docs/development.md) | Tests, migrations, local and Docker workflows, exact commands |

## Invariants (summary)

1. World state is authoritative.
2. Agents receive immutable observations, never `WorldState`.
3. Objective world state and subjective agent state remain separate.
4. Every agent action is a closed typed command resolved by `WorldEngine` through private world rules.
5. LLM output is untrusted and cannot mutate world state directly.
6. Objective `WorldEvent` values are immutable closed occurrence facts.
7. Agent memories and beliefs are mutable and may be incorrect.
8. Memory is agent-scoped and is never shared automatically.
9. Information crosses agent boundaries only through perception and explicit communication.
10. Randomness is injected and derived from an explicit simulation seed.
11. Cognition is a strategy protocol that returns `AgentCommand` over the same world contracts.

See [docs/architecture.md](docs/architecture.md) for the engine lifecycle, enforcement, and what remains deferred.

## License

CC0-1.0
