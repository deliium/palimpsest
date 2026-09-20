# Architecture: Structured Modules (Bounded Packages)

## Overview

Palimpsest uses a modular-monolith layout of bounded packages under `src/`. Each package owns a clear responsibility and public facade. This matches the foundation's need for enforceable trust boundaries (world authority vs agent-facing contracts, untrusted LLM output, deterministic simulation primitives) without introducing microservices.

## Decision Rationale

- **Project type:** Research / simulation foundation (contracts-first)
- **Tech stack:** Python, FastAPI, SQLAlchemy async, PostgreSQL/pgvector
- **Key factor:** Hard dependency and trust-stage boundaries must be machine-checkable before simulation behavior exists

## Folder Structure

```text
src/
  world/            # agent-facing Observation DTOs + private _state/_perception/_rules/_replay
  agents/           # identity, Agent, goals
  agents/cognition/ # CognitionStrategy leaf layer (Perspective → AgentCommand)
  memory/           # owner-bound MemoryTrace/Belief
  social/           # communication envelopes + Relationship
  llm/              # provider-neutral untrusted responses
  simulation/       # WorldEngine, bootstrap, lifecycle, build_perspective, codecs, replay
  persistence/      # SQLAlchemy adapters for simulation repository ports (no domain imports)
  analysis/         # read-only event/export protocols
  api/              # FastAPI composition root
  infrastructure/   # settings, logging, database adapters
alembic/            # migrations (pgvector + event store + occurrence context)
tests/
  unit/ architecture/ integration/ compose/ typecheck/
```

## Dependency Rules

- ✅ `world` imports no other bounded module
- ✅ Base `agents` may import agent-facing `world` only; never `agents.cognition`
- ✅ `memory` / `social` may import `world` + `agents`; remain independent of each other
- ✅ `llm` imports no domain module
- ✅ `agents.cognition` may import public contracts from agents/world/memory/social/llm
- ✅ `simulation` may import domain public contracts; must not import `api`, `analysis`, `infrastructure`, or `persistence`
- ✅ `persistence` may import public `simulation` contracts and `infrastructure` only
- ✅ `api` may import `simulation`, `infrastructure`, and `persistence`
- ✅ `persistence` may import only public `simulation` contracts and generic `infrastructure`
- ✅ `api` may import `simulation`, `infrastructure`, and `persistence`
- ✅ `analysis` is read-only over immutable events / export contracts
- ✅ `infrastructure` imports no domain policy
- ❌ Domain packages must not import `infrastructure`, FastAPI, or ORM stacks
- ❌ Non-simulation packages must not import private `world._*` authority modules
- ❌ Only `simulation.engine` / `simulation.bootstrap` and private `world._*` may import world authority internals
- ❌ Only `infrastructure` and `persistence` may import SQLAlchemy/Alembic/asyncpg
- ❌ Cross-module imports of private modules or transitive re-exports

## Layer/Module Communication

- Composition root (`api`) loads settings, configures logging, and owns database lifespan
- `WorldEngine` owns observation tokens, ordered admission, private batch preparation, and atomic commit
- Private `PerceptionService` projects one agent-specific `Observation` from tick-start state + prior committed events; cognition receives it only via `observation_for` / `build_perspective`
- LLM responses stop at cognition; only typed commands enter the engine as submissions
- Analysis consumes immutable exports/events, never live mutable repositories

## Key Principles

1. World state is authoritative; agents receive immutable, agent-specific observations only
2. Objective and subjective state remain separate; perception does not form memories or beliefs
3. Randomness and IDs derive from an explicit seed (no Python `hash()`, no global RNG)
4. Operational metadata (HTTP request IDs, log timestamps) never become domain IDs or seeds
5. Enforce boundaries with import-linter + AST checks, not convention alone

## Code Organization Note

- **New Features:** Follow the bounded-package rules and facades in this document and `docs/architecture.md`
- **Existing Code:** Documented structure matches the implemented foundation
- **Interoperability:** Wire infrastructure only at the API/composition boundary

## Code Examples

### Public facade import

```python
from simulation import (
    ActionSubmission,
    SimulationRunConfig,
    WorldBootstrap,
    WorldEngine,
)
from world import Observation, Wait
from simulation import build_perspective
```

### Forbidden authority import outside simulation

```python
# Not allowed from agents/memory/api/analysis/llm:
from world._state import WorldState  # private authority
from world._perception import PerceptionService  # private projector
```

## Anti-Patterns

- Passing `LLMResponse` into `WorldEngine` or treating `ActionRequest` as authoritative
- Handing an all-agent `ObservationBatch` or another agent's observation to cognition
- Sharing mutable memory payloads across agents
- Reading `PALIMPSEST_` secrets or opening DB connections at import time
- Using Docker/PostgreSQL inside default unit tests

## See Also

- `docs/architecture.md` — contributor-facing matrix, WorldEngine lifecycle, perception boundary, and invariants
- `.ai-factory/plans/perception-observation-system.md` — perception plan
