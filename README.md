# Palimpsest

Reproducible, discrete, text-based multi-agent AI society experiments.

This repository is a **Python 3.12+ modular monolith**. It establishes package boundaries, V1 typed domain contracts, an authoritative deterministic `WorldEngine` tick loop with V1 physical simulation rules, an explicit cognitive loop and per-agent runtime, schema-versioned event persistence and replay, configuration, an HTTP liveness API, observability, and containers. LLM invocation stays outside the engine behind a provider-neutral structured boundary. Agent recall is reconstructive and subjective; optional reconsolidation is append-only and never mutates objective history.

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
./run.sh
```

Then open `http://127.0.0.1:8080/` (`PALIMPSEST_API_PUBLISH_PORT` when set). That start pulls the published image and does not install Godot, open the editor, install export templates, export, or copy web files. `docker compose up -d` on `compose.yaml` is the same path.

```bash
# Host API with Compose Postgres only (reload)
./scripts/api.sh

# Unit and architecture tests (no Docker, no PostgreSQL, no Godot)
uv run --frozen --python 3.12.14 pytest
```

`GET /health` returns exactly `{"status":"ok"}`.

| Script | Purpose |
| --- | --- |
| `./run.sh` | Pull the published image and start the stack |
| `./run-dev.sh` | Contributor build, including the web export |
| `./scripts/up.sh` | Same pull path as `./run.sh` |
| `./scripts/api.sh` | Host Uvicorn + Compose `db`, migrate, `--reload` |
| `./scripts/migrate.sh` | `alembic upgrade head` against configured DSN |
| `./scripts/down.sh` | `docker compose down` (add `--volumes` to drop data) |

Development credentials in `compose.yaml` are **not production**. `docker compose config` expands values and is **not secret-safe**.

## Documentation

| Page | Contents |
| --- | --- |
| [Architecture](docs/architecture.md) | Bounded packages, `WorldEngine` lifecycle, perception boundary, eleven invariants, V2 seams + downstream plan contract |
| [Simulation runner](docs/simulation-runner.md) | Config-driven `SimulationRunner`, `runner-config-v3` flags, fingerprint vs trajectory identity |
| [Experiments](docs/experiments.md) | Trusted A–E catalog, `v1_regression_profile`, false-story boundary, coordinator, persistence (`0010`) |
| [Analysis metrics](docs/analysis-metrics.md) | V1 metric catalog, populations/denominators, numerical policy, known-answer fixtures |
| [Research API](docs/research-api.md) | FastAPI control/inspection/debug, WebSocket cursors/backpressure, capability credentials |
| [Read-only observer](docs/observer.md) | Observer protocol, frames, and the read-only HTTP and WebSocket routes |
| [Godot observer](docs/godot-observer.md) | Prebuilt Web client served by the API, version strip, `?run_id=` |
| [Cognition and agent runtime](docs/cognition-runtime.md) | `CognitiveLoop`, drives/goals, subjective imagination/motivation/intention, `AgentRuntime`, metadata-only logs |
| [Memory reconstruction](docs/memory-reconstruction.md) | Subjective recall, reconsolidation, lineage, drift analysis, Alembic `0006`/`0007`/`0008`, safe logging |
| [Social communication](docs/social-communication.md) | Talk/Ask/Tell delivery vs testimony, owner-scoped traces, trust-weighted beliefs, transmission analysis |
| [LLM providers](docs/llm-providers.md) | Structured `LLMProvider`, modes, retries, prompts, local OpenAI-compatible config, fakes |
| [Physical simulation](docs/physical-simulation.md) | Topology, capacities, actions, physiology, death, schema-v4, tests |
| [Configuration](docs/configuration.md) | `PALIMPSEST_` settings (including `PALIMPSEST_LLM_*`), logging, redaction, seeds, identifiers, clocks |
| [Development](docs/development.md) | Tests, migrations (head `0012`), local and Docker workflows, exact commands |
| [Persistence](docs/persistence.md) | Event store, Alembic through `0012`, subjective + scientific evidence, run control, stream outbox, replay |

## Invariants (summary)

1. World state is authoritative.
2. Agents receive immutable, agent-specific observations, never `WorldState`.
3. Objective world state and subjective agent state remain separate.
4. Every agent action is a closed typed command resolved by `WorldEngine` through private world rules.
5. LLM output is untrusted and cannot mutate world state directly (structurally validated `LLMResult` still requires explicit cognition translation).
6. Objective `WorldEvent` values are immutable closed occurrence facts.
7. Agent memories and beliefs are mutable and may be incorrect.
8. Memory is agent- and run-scoped and is never shared automatically.
9. Information crosses agent boundaries only through perception and explicit communication.
10. Randomness is injected and derived from an explicit simulation seed.
11. Cognition is a strategy protocol that returns `AgentCommand` over the same world contracts.

See [docs/architecture.md](docs/architecture.md) and [docs/physical-simulation.md](docs/physical-simulation.md) for the engine lifecycle and physical rules.

## License

CC0-1.0
