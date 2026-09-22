# Palimpsest

## Overview

Palimpsest is a Python 3.12+ modular monolith for reproducible, discrete, text-based multi-agent AI society experiments. The current V1 surface establishes package boundaries, typed domain contracts, an authoritative deterministic `WorldEngine` tick loop with agent-specific perception, an explicit async `CognitiveLoop` and per-agent `AgentRuntime`, owner-scoped episodic `MemoryService` with reconstructive recall and append-only reconsolidation (in-memory and PostgreSQL/pgvector), deterministic subjective imagination/motivation/intention policies (independent drives, structured goals, opportunity-based fear of death, multi-criteria selection → one closed `AgentCommand`), schema-versioned event persistence and replay, experiment-only memory-drift analysis, configuration, an HTTP liveness API, observability, and containers. A provider-neutral async LLM boundary returns only strict structured output plus normalized metadata; LLM provider lifecycle composition in the API remains deferred.

## Core Features

- Bounded packages for world authority, agents, cognition strategies/`CognitiveLoop`, memory (including reconstructive recall and semantic beliefs), social envelopes and directed relationship profiles, LLM trust boundaries, simulation/`WorldEngine`/`AgentRuntime`/`SimulationRunner`/`SubjectiveStateService`, trusted `experiments` catalog (A–E), persistence adapters, analysis ports (events + drift), API, and infrastructure
- Typed immutable agent-facing `Observation` contracts, private world authority (`World` / `WorldState` / rules / perception / operations), and versioned event/export codecs (replay-v4 occurrence context)
- Deterministic `PerceptionService` projecting one observation per agent from tick-start state plus prior committed events; cognition routed via `AgentRuntime` / `build_perspective`
- Explicit async cognitive pipeline with replaceable stage protocols, scientific boundary records, reconstructive memory stage, emergent `SelfModel`, production subjective imagination/motivation/deliberation policies, deterministic fakes, and fail-closed runtime lifecycle
- Eleven independent drives, structured goal outcomes/progress, opportunity-based mortality appraisal (no permanent reward / no death_penalty), and multi-criteria intention selection compiling one non-authoritative `AgentCommand`
- Subjective reconstructive recall (`MemoryRecallRequest` → `ReconstructedMemory`) with deterministic and optional LLM-backed policies; non-destructive reconsolidation and lineage outside authoritative replay
- Semantic beliefs with append-only revisions/evidence, asymmetric relationship dimensions (no friend/enemy/leader labels), and atomic owner-scoped subjective commits
- Async `LLMProvider` with immutable `LLMRequest`/`LLMResult`, strict `StructuredOutput`, versioned prompt resources (including `reconstructive_memory/v1`), and a configurable OpenAI-compatible HTTP adapter (no vendor SDKs)
- Deterministic seed-derived RNG streams (including explicit stochastic/comparison identity), logical clock, namespaced IDs, and live/restored observation parity
- Configuration-driven `SimulationRunner` with staged prepare/bind/finalize cognition and versioned experiment result documents
- `PALIMPSEST_` settings (including disabled-by-default `PALIMPSEST_LLM_*`), structured logging (no observation/communication/memory/belief/relationship/LLM payloads), async SQLAlchemy lifecycle, Alembic + pgvector bootstrap (migration head `0010`)
- FastAPI `/health` liveness and Docker Compose development stack (API does not yet own LLM provider lifecycle)

## Tech Stack

- **Programming language:** Python >=3.12 (reference pin 3.12.14)
- **Package manager / build:** uv + Hatchling (`src` layout, committed `uv.lock`)
- **Framework:** FastAPI + Uvicorn
- **Validation:** Pydantic v2 + pydantic-settings (LLM structured-output contracts only; domain packages stay Pydantic-free)
- **Database:** PostgreSQL 17 with pgvector
- **ORM / migrations:** SQLAlchemy 2 async + Alembic + asyncpg
- **Logging:** structlog (infrastructure); stdlib logging inside `llm` (metadata-only)
- **HTTP client:** httpx (runtime; OpenAI-compatible LLM transport and tests)
- **Scientific computing (analysis metrics):** NumPy >=2, pandas >=2, SciPy >=1.11, NetworkX >=3 (canonical quantized metric output; not unconstrained BLAS/platform bit identity)
- **Testing:** pytest, pytest-asyncio, Hypothesis, import-linter, Ruff, mypy

## Architecture Notes

Modular monolith with explicit bounded packages under `src/`. Domain modules do not import infrastructure; the API composition root wires adapters. `simulation.WorldEngine` is the sole public mutation authority; private world modules prepare candidates and project observations only. Cognition never receives `WorldState` or another agent's observation. Agents, memory, cognition, and reconstruction APIs may carry opaque `EventId` correlation only — never `WorldEvent` or event stores. Structured `Talk`/`Ask`/`Tell` proves delivery only; declared lineage is testimony; each receiver forms a fresh communicated `MemoryTrace`. Read-only `analysis` may join objective events with subjective reconstruction and social-transmission evidence after the fact. The `llm` package is import-closed against world/simulation/API/infrastructure, forbids vendor SDKs, and never converts results into commands—future cognition must translate validated decision schemas into fresh `AgentCommand` values and use normal admission. Cross-module imports use package facades / `__all__`. Import-linter and AST boundary checks enforce dependency rules.

## Architecture

Detailed architecture guidelines live in `.ai-factory/ARCHITECTURE.md`.

**Pattern:** Structured Modules (Technical Layer / Bounded Packages)

## Non-Functional Requirements

- **Logging:** Configurable via `PALIMPSEST_LOG_LEVEL`; structured, secret-safe, UTC operational timestamps; LLM and memory/reconstruction logs stay metadata-only
- **Error handling:** Fail closed on invalid settings and ambiguous migration targets; LLM errors expose only safe codes/status/attempts
- **Security:** Credentials are `SecretStr`; DSNs/prompts/bodies are never logged; non-root container user
- **Reproducibility:** Explicit simulation seeds; no global RNG or wall-clock domain defaults; LLM retries use injected sleep/monotonic clocks; exact external LLM reconstructive recall needs recorded outputs or stubs
- **Testing:** Unit/architecture by default; integration and Compose are opt-in markers; LLM tests are network-free with deterministic fakes
