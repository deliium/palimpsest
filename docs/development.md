# Development

[← Previous Page](configuration.md) · [Back to README](../README.md) · [Next → Persistence](persistence.md)

## Locked environment

```bash
uv sync --frozen --python 3.12.14
```

Do not omit `--frozen` in development or containers. The reference interpreter is **3.12.14**.

## WorldEngine

`simulation.WorldEngine` is the sole public mutation authority. Construct it from `SimulationRunConfig` (required seed) and immutable `WorldBootstrap`, then:

1. `observe()` → `ObservationBatch` with an engine-issued `TickToken` (projections from tick-start state + prior committed window)
2. Route one observation per agent via `observation_for(AgentId)` / `AgentRuntime` (or `build_perspective` + `CognitiveLoop`)
3. Submit an ordered sequence of `ActionSubmission(token, AgentId, AgentCommand)`
4. `resolve_tick(...)` → `TickResult` and atomic commit to tick N+1

`AgentRuntime` owns per-agent start/active/terminal lifecycle, cognition invocation, memory-update hooks, and submission construction from the engine token. See [Cognition and agent runtime](cognition-runtime.md).

Equivalent bootstrap + seed + ordered submissions must produce identical ticks, revisions, resolutions, objective events, observations, and replay fingerprints. Physical rules and autonomous physiology participate in every committed tick. Perception never invents facts or forms memories. See [Architecture](architecture.md) and [Physical simulation](physical-simulation.md).

## Tests

Default pytest excludes live infrastructure:

```bash
uv run --frozen --python 3.12.14 pytest
# equivalent addopts: -m "not integration and not compose"
```

| Command | What it covers |
| --- | --- |
| `uv run --frozen --python 3.12.14 pytest` | Unit + architecture (no Docker, no PostgreSQL) |
| `uv run --frozen --python 3.12.14 pytest tests/unit/physical -q` | Physical conservation, physiology, scale, seed proofs |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_openai_compatible*.py tests/unit/test_llm_*.py tests/unit/test_fake_llm_provider.py -q` | Provider codec/transport, prompts, factory, fake |
| `uv run --frozen --python 3.12.14 pytest tests/architecture/test_llm_provider_isolation.py -q` | LLM import/signature/logging isolation |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_world_perception*.py tests/unit/test_perception_event_isolation.py -q` | Visibility, noninterference, event audience, routing isolation |
| `uv run --frozen --python 3.12.14 pytest tests/unit/test_cognition_*.py tests/unit/test_agent_runtime.py tests/unit/test_imagination_engine.py tests/unit/test_motivation_appraisal.py tests/unit/test_fear_of_death.py tests/unit/test_intention_selection.py tests/unit/test_action_planner.py tests/unit/test_subjective_risk_*.py tests/unit/test_v1_*memory*.py tests/unit/test_memory_reconstruction*.py tests/unit/test_memory_llm_reconstruction.py tests/unit/test_memory_drift_analysis.py tests/unit/test_reconstruction_analysis_service.py tests/unit/test_semantic_belief_*.py tests/unit/test_subjective_*.py tests/unit/test_self_model_development.py tests/architecture/test_cognitive_loop_isolation.py tests/architecture/test_memory_isolation.py tests/architecture/test_social_isolation.py tests/architecture/test_analysis_isolation.py -q` | Cognition + subjective deliberation + beliefs/relationships + reconstructive memory + drift analysis isolation |
| `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_agent_runtime_world_engine.py -q` | In-memory AgentRuntime ↔ WorldEngine (no Postgres) |
| `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_episodic_memory_pgvector.py tests/integration/test_memory_concurrency.py tests/integration/test_migrations.py tests/integration/test_subjective_state_persistence.py -q` | Opt-in Postgres episodic + subjective agent models + migration head `0008` |
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

Revision `0001` enables `pgvector`. Revision `0002` creates the append-only simulation event store. Revisions `0003`/`0004` add physical state and occurrence context. Revision `0005` adds owner-scoped episodic memory tables. Revision `0006` adds reconstruction/derivation provenance (append-only reconstruction tables; selective content immutability on traces). Revision `0007` adds semantic beliefs and directed relationship profiles (append-only revisions; outside `AUTHORITATIVE_TABLES`). Revision `0008` adds social transmission provenance columns on memory traces and belief evidence. Current head is **`0008`**. Downgrade of `0001` is a documented no-op for the extension. Never use `metadata.create_all()`.

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
- [Cognition and agent runtime](cognition-runtime.md)
- [Memory reconstruction](memory-reconstruction.md)
- [LLM providers](llm-providers.md)
- [Configuration](configuration.md)
- [Persistence](persistence.md)
