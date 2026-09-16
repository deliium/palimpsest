# Palimpsest

## Overview

Palimpsest is a Python 3.12+ modular monolith for reproducible, discrete, text-based multi-agent AI society experiments. The current V1 surface establishes package boundaries, typed domain contracts, an authoritative deterministic `WorldEngine` tick loop, schema-v1 event export, configuration, persistence bootstrap, an HTTP liveness API, observability, and containers. Agent cognition and LLM invocation remain outside the engine.

## Core Features

- Bounded packages for world authority, agents, cognition strategies, memory, social envelopes, LLM trust boundaries, simulation/`WorldEngine`, persistence adapters, analysis ports, API, and infrastructure
- Typed immutable agent-facing contracts, private world authority (`World` / `WorldState` / rules / operations), and schema-v1 event/export codec
- Deterministic seed-derived RNG streams, logical clock, namespaced IDs, and replay-stable tick resolution
- `PALIMPSEST_` settings, structured logging, async SQLAlchemy lifecycle, Alembic + pgvector bootstrap
- FastAPI `/health` liveness and Docker Compose development stack

## Tech Stack

- **Programming language:** Python >=3.12 (reference pin 3.12.14)
- **Package manager / build:** uv + Hatchling (`src` layout, committed `uv.lock`)
- **Framework:** FastAPI + Uvicorn
- **Validation:** Pydantic v2 + pydantic-settings
- **Database:** PostgreSQL 17 with pgvector
- **ORM / migrations:** SQLAlchemy 2 async + Alembic + asyncpg
- **Logging:** structlog
- **Testing:** pytest, pytest-asyncio, Hypothesis, httpx, import-linter, Ruff, mypy

## Architecture Notes

Modular monolith with explicit bounded packages under `src/`. Domain modules do not import infrastructure; the API composition root wires adapters. `simulation.WorldEngine` is the sole public mutation authority; private world modules prepare candidates only. Cross-module imports use package facades / `__all__`. Import-linter and AST boundary checks enforce dependency rules.

## Non-Functional Requirements

- **Logging:** Configurable via `PALIMPSEST_LOG_LEVEL`; structured, secret-safe, UTC operational timestamps
- **Error handling:** Fail closed on invalid settings and ambiguous migration targets
- **Security:** Credentials are `SecretStr`; DSNs/prompts/bodies are never logged; non-root container user
- **Reproducibility:** Explicit simulation seeds; no global RNG or wall-clock domain defaults
- **Testing:** Unit/architecture by default; integration and Compose are opt-in markers
