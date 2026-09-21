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
  agents/cognition/ # CognitiveLoop + stage protocols/defaults; CognitionStrategy retained
  memory/           # owner-scoped episodic MemoryTrace/Belief + MemoryService
  social/           # communication envelopes + Relationship
  llm/              # provider-neutral StructuredOutput / LLMResult (no vendor SDKs)
  llm/prompts/      # immutable versioned prompt package resources
  llm/providers/    # OpenAI-compatible HTTP adapter + pure codec
  simulation/       # WorldEngine, AgentRuntime, bootstrap, lifecycle, codecs, replay
  persistence/      # SQLAlchemy adapters for simulation ports + MemoryService
  analysis/         # read-only event/export protocols
  api/              # FastAPI composition root (no LLM provider wiring yet)
  infrastructure/   # settings (incl. PALIMPSEST_LLM_*), logging, database adapters
alembic/            # migrations (pgvector + event store + occurrence + episodic memory)
tests/
  unit/ architecture/ integration/ compose/ typecheck/ fakes/
```

## Dependency Rules

- ✅ `world` imports no other bounded module
- ✅ Base `agents` may import agent-facing `world` only; never `agents.cognition`
- ✅ `memory` / `social` may import `world` + `agents`; remain independent of each other
- ✅ `llm` imports no domain, simulation, API, persistence, or infrastructure module
- ✅ `llm` uses stdlib `logging` only (metadata allowlist; no `exc_info` / structlog / payload fields)
- ✅ `agents.cognition` may import public contracts from agents/world/memory/social/llm
- ✅ `simulation` may import domain public contracts; must not import `api`, `analysis`, `infrastructure`, or `persistence`
- ✅ `persistence` may import public `simulation` contracts, public `memory` contracts, and `infrastructure`
- ✅ `api` may import `simulation`, `infrastructure`, and `persistence`
- ✅ `analysis` is read-only over immutable events / export contracts
- ✅ `infrastructure` imports no domain policy
- ❌ Domain packages must not import `infrastructure`, FastAPI, or ORM stacks
- ❌ Non-simulation packages must not import private `world._*` authority modules
- ❌ Only `simulation.engine` / `simulation.bootstrap` and private `world._*` may import world authority internals
- ❌ Only `infrastructure` and `persistence` may import SQLAlchemy/Alembic/asyncpg
- ❌ Vendor LLM SDKs (`openai`, `anthropic`, …) are forbidden everywhere in `src/`
- ❌ Cross-module imports of private modules or transitive re-exports

## Layer/Module Communication

- Composition root (`api`) loads settings, configures logging, and owns database lifespan
- LLM settings exist under `PALIMPSEST_LLM_*`; factory construction stays standalone in `llm.factory` until a cognition consumer owns lifecycle composition (API/`compose.yaml` unchanged)
- `WorldEngine` owns observation tokens, ordered admission, private batch preparation, and atomic commit
- `AgentRuntime` owns per-agent cognition invocation, deferred memory apply, and `ActionSubmission` construction from an engine-issued token; cognition never sees `TickToken` or `WorldState`
- Owner-scoped episodic memory uses structured `MemoryTrace` values; durable adapter is `persistence.create_memory_service(scope=..., ...)`; mutable subjective tables are outside append-only authoritative history
- Private `PerceptionService` projects one agent-specific `Observation` from tick-start state + prior committed events; cognition receives it only via `observation_for` / `AgentRuntime` / `build_perspective`
- Async `LLMProvider.generate(LLMRequest[T]) -> LLMResult[T]` returns only strict `StructuredOutput` plus normalized metadata; raw provider text/mappings never leave the adapter
- Structurally valid LLM output remains non-authoritative. Cognition must translate an exact decision schema into a fresh `AgentCommand`, then use normal `ActionSubmission` / admission / world-operation gates
- Analysis consumes immutable exports/events, never live mutable repositories

## Key Principles

1. World state is authoritative; agents receive immutable, agent-specific observations only
2. Objective and subjective state remain separate; perception does not form memories or beliefs
3. Randomness and IDs derive from an explicit seed (no Python `hash()`, no global RNG)
4. Operational metadata (HTTP request IDs, log timestamps) never become domain IDs or seeds
5. Enforce boundaries with import-linter + AST checks, not convention alone
6. LLM validation proves shape only—never truth, policy, actor identity, or world authority

## Code Organization Note

- **New Features:** Follow the bounded-package rules and facades in this document and `docs/architecture.md`
- **Existing Code:** Documented structure matches the implemented foundation
- **Interoperability:** Wire infrastructure only at the API/composition boundary; do not allocate LLM providers in API lifespan until cognition consumes them

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
from llm import LLMProvider, LLMRequest, LLMResult, StructuredOutput
```

### Forbidden authority import outside simulation

```python
# Not allowed from agents/memory/api/analysis/llm:
from world._state import WorldState  # private authority
from world._perception import PerceptionService  # private projector
```

### Forbidden LLM trust bypass

```python
# Not allowed — no direct conversion; cognition translation is a separate stage:
require_agent_command(llm_result)           # TypeError
require_action_submission(structured_output)  # TypeError
llm_result.to_agent_command()               # does not exist
```

## Anti-Patterns

- Passing `LLMResult` / `StructuredOutput` / model dumps into `WorldEngine`, `ActionSubmission`, admission, or world operations
- Treating `ActionRequest` as authoritative without private world validation
- Handing an all-agent `ObservationBatch` or another agent's observation to cognition
- Sharing mutable memory payloads across agents
- Reading `PALIMPSEST_` secrets or opening DB connections at import time
- Importing vendor LLM SDKs or logging prompt/output/schema/endpoint content from `llm`
- Using Docker/PostgreSQL inside default unit tests

## See Also

- `docs/architecture.md` — contributor-facing matrix, WorldEngine lifecycle, perception boundary, and invariants
- `.ai-factory/plans/v1-agent-runtime-cognitive-loop.md` — cognitive loop and AgentRuntime plan
- `.ai-factory/plans/llm-provider-abstraction.md` — provider-neutral LLM boundary plan
- `.ai-factory/plans/perception-observation-system.md` — perception plan
