# Palimpsest

## Overview

Palimpsest is a Python 3.12+ modular monolith for reproducible, discrete, text-based multi-agent AI society experiments. The current foundation establishes package boundaries, typed domain contracts, configuration, persistence bootstrap, an HTTP liveness API, observability, and containers without implementing a simulation loop or domain simulation behavior.

## Core Features

- Bounded packages for world authority, agents, cognition strategies, memory, social envelopes, LLM trust boundaries, simulation primitives, analysis ports, API, and infrastructure
- Typed immutable agent-facing contracts and private world authority surfaces
- Deterministic seed-derived RNG streams, logical clock, and namespaced IDs
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

Modular monolith with explicit bounded packages under `src/`. Domain modules do not import infrastructure; the API composition root wires adapters. World authority (`WorldState` / transitions) is private to simulation. Cross-module imports use package facades / `__all__`. Import-linter and AST boundary checks enforce dependency rules.

## Non-Functional Requirements

- **Logging:** Configurable via `PALIMPSEST_LOG_LEVEL`; structured, secret-safe, UTC operational timestamps
- **Error handling:** Fail closed on invalid settings and ambiguous migration targets
- **Security:** Credentials are `SecretStr`; DSNs/prompts/bodies are never logged; non-root container user
- **Reproducibility:** Explicit simulation seeds; no global RNG or wall-clock domain defaults
- **Testing:** Unit/architecture by default; integration and Compose are opt-in markers
