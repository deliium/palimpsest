# Architecture

[Back to README](../README.md) · [Next Page →](configuration.md)

Palimpsest is a modular monolith under `src/`. Cross-module imports must target a package `__init__.py` facade or names listed in `__all__`. Private modules (leading `_`) are not cross-boundary APIs.

## Bounded packages

| Package | Responsibility | May import |
| --- | --- | --- |
| `world` | Opaque IDs, typed observations, closed commands, immutable events. Private `World` / `WorldState` / operations / rules / transitions | *(none)* |
| `agents` | Agent identity, goals, and subjective `Agent` contracts | `world` (agent-facing only) |
| `agents.cognition` | Strategy protocol; returns non-authoritative `AgentCommand` | `world`, `agents`, `memory`, `social`, `llm` |
| `memory` | Owner-bound `MemoryTrace` / `Belief` stores | `world`, `agents` |
| `social` | Opaque communication envelopes and relationships | `world`, `agents` |
| `llm` | Provider-neutral untrusted responses | *(none)* |
| `simulation` | `WorldEngine`, bootstrap, lifecycle, seed/clock/RNG/IDs, schema-1 codec, export ports | `world`, `agents`, `agents.cognition`, `memory`, `social`, `llm` |
| `api` | HTTP composition root | `simulation`, `infrastructure` |
| `analysis` | Read-only event/export sources | `world`, `simulation` |
| `infrastructure` | Settings, logging, PostgreSQL adapters | *(none of the domain packages)* |

Private world authority (`world/_state.py`, `world/_transitions.py`, `world/_operations.py`, `world/_rules.py`, `world/_perception.py`) may be imported only by `simulation.engine`, `simulation.bootstrap`, and other private `world._*` modules. They are not re-exported from `world`.

`memory` and `social` are independent. Base `agents` must not import `agents.cognition`. `llm` imports no domain module. `simulation` must not import `api` or `analysis`. Domain packages do not import `infrastructure`.

Import-linter (`pyproject.toml`) and `tests/architecture/boundary_checker.py` enforce the allowlist, private-world authority, public facades, framework leakage, provider SDKs, and prohibited `random` / wall-clock / UUID defaults in domain code.

## Public facades

Import packages, not private modules:

- `world`: IDs, values, objective models, closed commands, `Observation`, `ActionProposal`, `ActionRequest` (non-authoritative), `WorldEvent`, `detached_mapping`
- `agents`: `AgentId`, `Agent`, `Goal`, `IdentityTranslator`
- `agents.cognition`: `CognitionStrategy` (`propose` → `AgentCommand`), `Perspective`
- `memory`: `MemoryTrace`, `Belief`, owner-bound stores, `OwnershipError`
- `social`: `CommunicationEnvelope`, `Relationship`, `EnvelopeSender`
- `llm`: `LLMClient`, `LLMResponse`
- `simulation`: `WorldEngine`, `WorldBootstrap`, lifecycle types (`TickToken`, `ActionSubmission`, `TickResult`, …), `SimulationRunConfig`, schema-1 `encode_domain` / `decode_domain`, deterministic IDs/RNG/clock, export ports
- `analysis`: `EventSource`, `ExportSource`
- `api`: `create_app`
- `infrastructure`: `load_settings`, `configure_logging`, `create_database_resources`

## WorldEngine lifecycle

`simulation.WorldEngine` is the sole public authority that advances objective world state:

```text
observe() → ObservationBatch + TickToken
→ ordered ActionSubmission(token, AgentId, AgentCommand)
→ resolve_tick(...) → TickResult + commit
→ tick N+1
```

- Tick and world revision are independent; revision advances only when a semantic mutation commits.
- Ordered input position is resolution priority. Conflicts arise only when an initially valid action is invalidated by an earlier effect.
- At most one action per registered agent per tick; omitted agents produce nothing.
- `Take` / `Drop` / `Give` mutate; `Search` / `Talk` / `Ask` / `Tell` / `Wait` are event-only; `Move` / `Eat` / `Drink` / `Sleep` / `Help` / `Attack` / `Flee` are deferred-policy.
- Schema-1 export remains an objective-event audit artifact (`SimulationExport`). Bootstrap, tokens, submissions, and resolutions are not wire types.

## Eleven invariants

These are encoded as types and import rules, and enforced by `WorldEngine` for objective evolution.

1. **World state is authoritative.** Mutations commit only through `WorldEngine`; private world modules prepare candidates and never commit independently.
2. **Agents receive immutable observations, never `WorldState`.** `WorldState` is absent from public `world` exports.
3. **Objective and subjective state stay separate.** `Agent` / goals / memories / beliefs are not world aggregates.
4. **Actions are structured and typed.** Fifteen closed `AgentCommand` variants; cognition returns commands; the engine admits and resolves them.
5. **LLM output is untrusted.** `LLMResponse` cannot mutate world state.
6. **`WorldEvent` is immutable.** Closed occurrence details; no open payloads. Rejected/conflicted/deferred/duplicate outcomes emit no world events.
7. **Memories and beliefs may be wrong.** They are mutable owner-bound aggregates (`MemoryTrace` / `Belief`).
8. **Memory is agent-scoped.** Stores reject cross-owner writes; nothing shares memory automatically.
9. **Information crosses agents only via perception and explicit communication.** Envelopes cannot carry memory traces or `Agent` values.
10. **Randomness is injected from an explicit seed.** `SimulationRunConfig.seed` is required; only `simulation.randomness` may use `random.Random` instances.
11. **Cognition is a strategy protocol.** `CognitionStrategy.propose(perspective)` returns `AgentCommand` and has no LLM, repository, `WorldState`, or mutation capability in its signature.

## Determinism and trust stages

- Stream seeds and IDs use SHA-256 over canonical length-prefixed bytes (`DERIVATION_VERSION = "v1"`), never Python `hash()`.
- Operational HTTP request IDs and log timestamps are infrastructure metadata. They cannot populate simulation IDs, event order, domain times, or RNG seeds (`reject_operational_identifier`).
- Trust pipeline: `AgentCommand` → engine-owned admission → private batch preparation → atomic `WorldEngine` commit. Cognition and LLM stay outside the engine.
- Wire codec: `simulation.encode_domain` / `decode_domain` use schema version `1` for an explicit immutable allowlist (not `ActionRequest`, lifecycle types, bootstrap, or authority types).
- Exact external LLM replay requires **recorded responses or deterministic stubs**. Local seed derivation is not enough (`LLM_REPLAY_REQUIREMENT`).

## Deferred scope

No agent cognition loop inside the engine, topology/nutrition/combat/healing policy beyond deferred outcomes, weather progression, metabolism, prompts, memory retrieval algorithms, analysis metrics, production LLM providers, or application tables beyond the pgvector extension bootstrap. No Kafka, Kubernetes, Celery, or extra vector databases.

Production PostgreSQL privilege design for `CREATE EXTENSION` is deferred; development credentials may create `vector`.

## See also

- [Configuration](configuration.md)
- [Development](development.md)
