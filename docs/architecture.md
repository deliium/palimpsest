# Architecture

[Back to README](../README.md) · [Next Page →](cognition-runtime.md)

Palimpsest is a modular monolith under `src/`. Cross-module imports must target a package `__init__.py` facade or names listed in `__all__`. Private modules (leading `_`) are not cross-boundary APIs.

## Bounded packages

| Package | Responsibility | May import |
| --- | --- | --- |
| `world` | Opaque IDs, typed observations, closed commands, immutable events. Private `World` / `WorldState` / operations / rules / physical / transitions | *(none)* |
| `agents` | Agent identity, goals, and subjective `Agent` contracts | `world` (agent-facing only) |
| `agents.cognition` | Async `CognitiveLoop`, stage protocols, reconstructive memory stage, `LLMMemoryReconstructor`; sync `CognitionStrategy` retained | `world`, `agents`, `memory`, `social`, `llm` |
| `memory` | Owner-scoped episodic `MemoryTrace`, semantic beliefs/revisions, `MemoryService`, reconstructive recall, scoring/decay | `world`, `agents` (opaque `EventId` only — never `WorldEvent`) |
| `social` | Opaque communication envelopes and directed relationship profiles (trust/fear/affection/debt/respect/resentment/familiarity/dependency) | `world`, `agents` |
| `llm` | Provider-neutral structured `LLMProvider` / `LLMResult` | *(none)* |
| `simulation` | `WorldEngine`, `AgentRuntime`, bootstrap, lifecycle, seed/clock/RNG/IDs, codecs, `SubjectiveStateService`, persistence ports, durable tick service, replay | `world`, `agents`, `agents.cognition`, `memory`, `social`, `llm` |
| `persistence` | SQLAlchemy adapters for simulation repositories, owner-scoped memory, and subjective agent models | `simulation`, `infrastructure`, `memory`, `social` |
| `api` | HTTP composition root | `simulation`, `infrastructure`, `persistence` |
| `analysis` | Read-only events/exports + experiment memory-drift joins | `world`, `simulation`, `memory` (read-only contracts) |
| `infrastructure` | Settings, logging, PostgreSQL adapters | *(none of the domain packages)* |

Private world authority (`world/_state.py`, `world/_transitions.py`, `world/_operations.py`, `world/_rules.py`, `world/_physical.py`, `world/_perception.py`, `world/_replay.py`) may be imported only by `simulation.engine`, `simulation.bootstrap`, and other private `world._*` modules. They are not re-exported from `world`.

`memory` and `social` are independent (no cross-imports). Base `agents` must not import `agents.cognition`. `llm` imports no domain module. `simulation` must not import `api`, `analysis`, `infrastructure`, or `persistence`. Domain packages do not import `infrastructure`. `persistence` may import public `memory` and `social` facades for durable subjective adapters (intentional). `analysis` may import `memory` read-only contracts for drift analysis. Subjective beliefs, self-model projections, and relationship profiles never become `WorldEvent` variants or enter `AUTHORITATIVE_TABLES`. See [Persistence](persistence.md) and [Memory reconstruction](memory-reconstruction.md).

Import-linter (`pyproject.toml`) and `tests/architecture/boundary_checker.py` enforce the allowlist, private-world authority, public facades, framework leakage, provider SDKs, and prohibited `random` / wall-clock / UUID defaults in domain code.

## Public facades

Import packages, not private modules:

- `world`: IDs, values, objective models, closed commands, `Observation`, causes/effects, `ActionProposal`, `ActionRequest` (non-authoritative), `WorldEvent`, `detached_mapping`
- `agents`: `AgentId`, `Agent`, `Goal`, `IdentityTranslator`
- `agents.cognition`: `CognitiveLoop`, stage protocols/defaults, `CognitionStrategy`, `Perspective`, `SelfModel`, `SubjectiveSnapshot`, `LLMMemoryReconstructor`
- `memory`: `MemoryTrace`, `MemoryService`, semantic belief contracts, recall/reconstruction, scoring/decay policies, legacy `Belief`, owner-bound stores, `OwnershipError`
- `social`: `CommunicationEnvelope`, directed relationship profiles/revisions, legacy `Relationship`, `EnvelopeSender`
- `llm`: `LLMProvider`, `LLMRequest`, `LLMResult`, `StructuredOutput`, prompts (incl. `reconstructive_memory/v1`), factory
- `simulation`: `WorldEngine`, `AgentRuntime`, `WorldBootstrap`, lifecycle types, `build_perspective`, `SubjectiveStateService`, persistence DTOs/ports, `PersistentSimulationService`, `ReplayService`, codecs (incl. subjective-v1), deterministic IDs/RNG/clock, export ports
- `persistence`: repository factories, `create_memory_service`, and `create_subjective_state_service` (always require owner scope)
- `analysis`: `EventSource`, `ExportSource`, `MemoryDriftAnalysisService`, drift/chain DTOs
- `api`: `create_app`
- `infrastructure`: `load_settings`, `configure_logging`, `create_database_resources`

**Forbidden in agents / memory / cognition / reconstruction APIs:** `WorldEvent` values, event repositories, replay services, snapshots, or private world state. Opaque `EventId` correlation on provenance is allowed. Only `analysis` may join objective events with subjective reconstruction evidence after the fact.

## WorldEngine lifecycle

`simulation.WorldEngine` is the sole public authority that advances objective world state:

```text
observe() → ObservationBatch + TickToken
→ ordered ActionSubmission(token, AgentId, AgentCommand)
→ resolve_tick(...) → TickResult + commit
→ tick N+1
```

- Tick and world revision are independent; revision advances at most once per mutating tick.
- Actions resolve in input order against an evolving state; autonomous effects follow (weather → regen → metabolism/exposure/death).
- Ordered input position is resolution priority. Conflicts arise only when an initially valid action is invalidated by an earlier effect.
- At most one action per registered agent per tick; omitted agents produce nothing; empty submissions still run autonomous physiology.
- All fifteen commands have explicit applied / rejected / conflicted behavior (no deferred physical policy). Details: [Physical simulation](physical-simulation.md).
- New physical runs emit schema-v4 replay events (effect-complete + causes + occurrence context). Schema-v3 remains readable; schema-1 export remains an audit artifact where applicable.

## Perception boundary

Objective `WorldState` stays private. Agent-facing cognition sees only immutable, agent-specific `Observation` values produced by private `world._perception.PerceptionService` and routed by the engine.

| Concern | Contract |
| --- | --- |
| Input | Tick-start snapshot + committed events from tick `N−1` (never the still-open tick) |
| Output | Exactly one detached `Observation` per registered observer; repeated `observe()` in one open tick is equal |
| Routing | `WorldEngine.observation_for(AgentId)` or `ObservationBatch.for_observer`; cognition uses `build_perspective` |
| Forbidden to cognition | `WorldState`, `World`, engine snapshots, private projectors, raw `WorldEvent`, another agent's observation, all-agent batches |

### Field access matrix

| Access | Examples |
| --- | --- |
| Always self-known | Self physiology/inventory, hour, day phase, visibility, local weather condition, current location id/name, adjacent exits |
| Visibility-gated (≥ 0.5) | Local ground items, resources (quantity only), coarse nearby bodies, public occurrence facts for local bystanders |
| Participant-only | Extra occurrence fields for actors/targets (still redacted; no cause IDs or replay payloads) |
| Recipient-only | Communication text to sender + intended recipient |
| Omitted | Location capacities/shelter, resource max/regen, other-agent inventory/exact needs, remote weather/topology, request/system cause IDs |

Other bodies expose coarse health bands only. Perception never invents facts, never treats uttered text as objective truth, and never creates `MemoryTrace` or `Belief` values. Social `inbox` remains a separate out-of-band channel; observed communications live on `Observation.communications` with narrow provenance (source kind + tick/event correlation).

### Event audience and timing

Committed events carry versioned occurrence context (origin, destination, affected entity, private recipient) so audience decisions do not guess from `target_id` or post-tick state. Actors and targets may receive participant details; visible local bystanders get public action facts; remote or low-visibility observers get nothing. Rejected, duplicate, and conflicted outcomes emit no world events and therefore no observed occurrences.

### Logging

Projection code is log-free. Engine orchestration may log DEBUG counts, tick/revision, visibility bands, and stable reason codes. Never log observation payloads, communication text, memories, private state, hidden identities, seeds, or credentials. Verbosity follows `PALIMPSEST_LOG_LEVEL`.

## Eleven invariants

These are encoded as types and import rules, and enforced by `WorldEngine` for objective evolution.

1. **World state is authoritative.** Mutations commit only through `WorldEngine`; private world modules prepare candidates and never commit independently.
2. **Agents receive immutable observations, never `WorldState`.** `WorldState` is absent from public `world` exports. Each agent receives only its own observation via trusted routing.
3. **Objective and subjective state stay separate.** `Agent` / goals / memories / beliefs are not world aggregates.
4. **Actions are structured and typed.** Fifteen closed `AgentCommand` variants; cognition returns commands; the engine admits and resolves them.
5. **LLM output is untrusted.** Structurally validated `LLMResult` / `StructuredOutput` cannot mutate world state or become commands without an explicit cognition translation step.
6. **`WorldEvent` is immutable.** Closed occurrence details; no open payloads. Rejected/conflicted/duplicate outcomes emit no world events.
7. **Memories and beliefs may be wrong.** They are mutable owner-bound aggregates (`MemoryTrace` / `Belief`).
8. **Memory is agent- and run-scoped.** Normal `MemoryService` instances bind one `MemoryScope(run_id, owner_id)`. Stores reject cross-owner writes; retrieval/recall never joins objective events. Remembered episodes are reconstructed (`ReconstructedMemory`), not raw traces.
9. **Information crosses agents only via perception and explicit communication.** Envelopes cannot carry memory traces or `Agent` values.
10. **Randomness is injected from an explicit seed.** `SimulationRunConfig.seed` is required; only `simulation.randomness` may use `random.Random` instances. Seeds are never logged.
11. **Cognition is a strategy protocol.** `CognitionStrategy.propose(perspective)` returns `AgentCommand` and has no LLM, repository, `WorldState`, or mutation capability in its signature.

## Determinism and trust stages

- Stream seeds and IDs use SHA-256 over canonical length-prefixed bytes. Derivation-v2 includes the physical-rules fingerprint so equal seeds with different rules do not alias. Legacy derivation-v1 remains for old records.
- Operational HTTP request IDs and log timestamps are infrastructure metadata. They cannot populate simulation IDs, event order, domain times, or RNG seeds (`reject_operational_identifier`).
- Trust pipeline: `AgentCommand` → engine-owned admission → private pending prepare (actions + autonomous) → single finalizer → atomic `WorldEngine` commit.
- Exact external LLM replay requires **recorded responses or deterministic stubs**. Local seed derivation is not enough (`LLM_REPLAY_REQUIREMENT`).

## Deferred scope

No fear-of-death psychology, analysis metrics over cognition receipts, Anthropic-native adapters, pathfinding beyond one adjacent edge, crafting, diseases, revival, or multi-tick sleeping state. Reconstructive recall and append-only reconsolidation are **implemented** (see [Memory reconstruction](memory-reconstruction.md)); LLM-backed reconstruction remains optional and provider lifecycle is not wired into the API/`compose` composition root yet. No Kafka, Kubernetes, Celery, or extra vector databases.

Production PostgreSQL privilege design for `CREATE EXTENSION` is deferred; development credentials may create `vector`.

## See also

- [Cognition and agent runtime](cognition-runtime.md)
- [Memory reconstruction](memory-reconstruction.md)
- [LLM providers](llm-providers.md)
- [Physical simulation](physical-simulation.md)
- [Configuration](configuration.md)
- [Development](development.md)
- [Persistence](persistence.md)
