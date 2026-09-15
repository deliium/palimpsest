# Architecture

[Back to README](../README.md) · [Next Page →](configuration.md)

Palimpsest is a modular monolith under `src/`. Cross-module imports must target a package `__init__.py` facade or names listed in `__all__`. Private modules (leading `_`) are not cross-boundary APIs.

## Bounded packages

| Package | Responsibility | May import |
| --- | --- | --- |
| `world` | Opaque IDs, typed observations, closed commands, immutable events. Private `World` / `WorldState` / operations / transitions | *(none)* |
| `agents` | Agent identity, goals, and subjective `Agent` contracts | `world` (agent-facing only) |
| `agents.cognition` | Strategy protocol; returns non-authoritative `AgentCommand` | `world`, `agents`, `memory`, `social`, `llm` |
| `memory` | Owner-bound `MemoryTrace` / `Belief` stores | `world`, `agents` |
| `social` | Opaque communication envelopes and relationships | `world`, `agents` |
| `llm` | Provider-neutral untrusted responses | *(none)* |
| `simulation` | Run config, clock, RNG, IDs, admission, versioned codec, export ports | `world`, `agents`, `agents.cognition`, `memory`, `social`, `llm` |
| `api` | HTTP composition root | `simulation`, `infrastructure` |
| `analysis` | Read-only event/export sources | `world`, `simulation` |
| `infrastructure` | Settings, logging, PostgreSQL adapters | *(none of the domain packages)* |

`world/_state.py`, `world/_transitions.py`, and `world/_operations.py` are authority-facing. Only `simulation` (and those private modules) may import them. They are not re-exported from `world`.

`memory` and `social` are independent. Base `agents` must not import `agents.cognition`. `llm` imports no domain module. `simulation` must not import `api` or `analysis`. Domain packages do not import `infrastructure`. FastAPI stays in `api`; SQLAlchemy/Alembic/asyncpg stay in `infrastructure` (the API may use infrastructure adapters transitively).

Import-linter (`pyproject.toml`) and `tests/architecture/boundary_checker.py` enforce the allowlist, private-world authority, public facades, framework leakage, provider SDKs, and prohibited `random` / wall-clock / UUID defaults in domain code.

## Public facades

Import packages, not private modules:

- `world`: IDs, values, objective models, closed commands, `Observation`, `ActionProposal`, `ActionRequest`, `WorldEvent`, `TransitionOutcome`, `accept_action_request`, `detached_mapping`
- `agents`: `AgentId`, `Agent`, `Goal`, `IdentityTranslator`
- `agents.cognition`: `CognitionStrategy` (`propose` → `AgentCommand`), `Perspective`
- `memory`: `MemoryTrace`, `Belief`, owner-bound stores, `OwnershipError`
- `social`: `CommunicationEnvelope`, `Relationship`, `EnvelopeSender`
- `llm`: `LLMClient`, `LLMResponse`
- `simulation`: `SimulationRunConfig`, `admit_agent_command`, `encode_domain` / `decode_domain`, deterministic IDs/RNG/clock, export ports
- `analysis`: `EventSource`, `ExportSource`
- `api`: `create_app`
- `infrastructure`: `load_settings`, `configure_logging`, `create_database_resources`

## Eleven invariants

These are encoded as types and import rules. Behavioral simulation enforcement (tick loop, perception, policy) is **deferred**.

1. **World state is authoritative.** Mutations go through private world transitions, not agent or LLM types.
2. **Agents receive immutable observations, never `WorldState`.** `WorldState` is absent from public `world` exports.
3. **Objective and subjective state stay separate.** `Agent` / goals / memories / beliefs are not world aggregates.
4. **Actions are structured and typed.** Fifteen closed `AgentCommand` variants; cognition returns commands; simulation admits `ActionRequest`; only private validation promotes to authority.
5. **LLM output is untrusted.** `LLMResponse` cannot be passed to the world gateway.
6. **`WorldEvent` is immutable.** Closed occurrence details; no open payloads.
7. **Memories and beliefs may be wrong.** They are mutable owner-bound aggregates (`MemoryTrace` / `Belief`).
8. **Memory is agent-scoped.** Stores reject cross-owner writes; nothing shares memory automatically.
9. **Information crosses agents only via perception and explicit communication.** Envelopes cannot carry memory traces or `Agent` values.
10. **Randomness is injected from an explicit seed.** `SimulationRunConfig.seed` is required; only `simulation.randomness` may use `random.Random` instances.
11. **Cognition is a strategy protocol.** `CognitionStrategy.propose(perspective)` returns `AgentCommand` and has no LLM, repository, `WorldState`, or mutation capability in its signature.

## Determinism and trust stages

- Stream seeds and IDs use SHA-256 over canonical length-prefixed bytes (`DERIVATION_VERSION = "v1"`), never Python `hash()`.
- Operational HTTP request IDs and log timestamps are infrastructure metadata. They cannot populate simulation IDs, event order, domain times, or RNG seeds (`reject_operational_identifier`).
- Trust pipeline: `AgentCommand` → simulation `admit_agent_command` → non-authoritative `ActionRequest` → private `World.apply_admitted_request` validation → `TransitionResult` events. Reachability, ownership effects, combat, and scheduling remain deferred.
- Wire codec: `simulation.encode_domain` / `decode_domain` use schema version `1` for an explicit immutable allowlist (not `ActionRequest` or authority types).
- Exact external LLM replay requires **recorded responses or deterministic stubs**. Local seed derivation is not enough (`LLM_REPLAY_REQUIREMENT`).

## Deferred scope

No tick loop, scheduler, action-resolution policy (pathfinding, visibility, inventory capacity, combat math, social permission), weather progression, metabolism, prompts, memory retrieval algorithms, analysis metrics, production LLM providers, or application tables beyond the pgvector extension bootstrap. Structural contracts validate types/graph shape only. No Kafka, Kubernetes, Celery, or extra vector databases.

Production PostgreSQL privilege design for `CREATE EXTENSION` is deferred; development credentials may create `vector`.

## See also

- [Configuration](configuration.md)
- [Development](development.md)
