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
  world/            # agent-facing contracts + private _state/_transitions
  agents/           # identity and subjective state
  agents/cognition/ # CognitionStrategy leaf layer
  memory/           # owner-bound memories/beliefs
  social/           # communication envelopes
  llm/              # provider-neutral untrusted responses
  simulation/       # seed, clock, RNG, IDs, export ports
  analysis/         # read-only event/export protocols
  api/              # FastAPI composition root
  infrastructure/   # settings, logging, database adapters
alembic/            # migrations (pgvector bootstrap)
tests/
  unit/ architecture/ integration/ compose/ typecheck/
```

## Dependency Rules

- ✅ `world` imports no other bounded module
- ✅ Base `agents` may import agent-facing `world` only; never `agents.cognition`
- ✅ `memory` / `social` may import `world` + `agents`; remain independent of each other
- ✅ `llm` imports no domain module
- ✅ `agents.cognition` may import public contracts from agents/world/memory/social/llm
- ✅ `simulation` may import domain public contracts; must not import `api` or `analysis`
- ✅ `api` may import `simulation` and `infrastructure`
- ✅ `analysis` is read-only over immutable events / export contracts
- ✅ `infrastructure` imports no domain policy
- ❌ Domain packages must not import `infrastructure`, FastAPI, or ORM stacks
- ❌ Non-simulation packages must not import `world._state` / `world._transitions`
- ❌ Cross-module imports of private modules or transitive re-exports

## Layer/Module Communication

- Composition root (`api`) loads settings, configures logging, and owns database lifespan
- Future simulation orchestrator consumes public contracts; world mutations stay behind private transitions
- LLM responses stop at cognition; only typed `ActionRequest` may enter the world gateway
- Analysis consumes immutable exports/events, never live mutable repositories

## Key Principles

1. World state is authoritative; agents receive immutable observations only
2. Objective and subjective state remain separate; memory is owner-scoped
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
from world import ActionRequest, Observation, accept_action_request
from simulation import SimulationRunConfig, create_named_stream
```

### Forbidden authority import outside simulation

```python
# Not allowed from agents/memory/api/analysis/llm:
from world._state import WorldState
```

## Anti-Patterns

- Passing `LLMResponse` or `ActionProposal` into the world gateway
- Sharing mutable memory payloads across agents
- Reading `PALIMPSEST_` secrets or opening DB connections at import time
- Using Docker/PostgreSQL inside default unit tests

## See Also

- `docs/architecture.md` — contributor-facing matrix and invariants
- `.ai-factory/plans/feature-v1-project-foundation.md` — foundation plan
