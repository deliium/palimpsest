# Architecture

[Back to README](../README.md) · [Next Page →](llm-providers.md)

Palimpsest is a modular monolith under `src/`. Cross-module imports must target a package `__init__.py` facade or names listed in `__all__`. Private modules (leading `_`) are not cross-boundary APIs.

## Bounded packages

| Package | Responsibility | May import |
| --- | --- | --- |
| `world` | Opaque IDs, typed observations, closed commands, immutable events. Private `World` / `WorldState` / operations / rules / physical / transitions | *(none)* |
| `agents` | Agent identity, goals, and subjective `Agent` contracts | `world` (agent-facing only) |
| `agents.cognition` | Strategy protocol; returns non-authoritative `AgentCommand` | `world`, `agents`, `memory`, `social`, `llm` |
| `memory` | Owner-bound `MemoryTrace` / `Belief` stores | `world`, `agents` |
| `social` | Opaque communication envelopes and relationships | `world`, `agents` |
| `llm` | Provider-neutral structured `LLMProvider` / `LLMResult` | *(none)* |
| `simulation` | `WorldEngine`, bootstrap, lifecycle, seed/clock/RNG/IDs, codecs, persistence ports, durable tick service, replay | `world`, `agents`, `agents.cognition`, `memory`, `social`, `llm` |
| `persistence` | SQLAlchemy adapters for simulation repository ports | `simulation`, `infrastructure` |
| `api` | HTTP composition root | `simulation`, `infrastructure`, `persistence` |
| `analysis` | Read-only event/export sources | `world`, `simulation` |
| `infrastructure` | Settings, logging, PostgreSQL adapters | *(none of the domain packages)* |

Private world authority (`world/_state.py`, `world/_transitions.py`, `world/_operations.py`, `world/_rules.py`, `world/_physical.py`, `world/_perception.py`, `world/_replay.py`) may be imported only by `simulation.engine`, `simulation.bootstrap`, and other private `world._*` modules. They are not re-exported from `world`.

`memory` and `social` are independent. Base `agents` must not import `agents.cognition`. `llm` imports no domain module. `simulation` must not import `api`, `analysis`, `infrastructure`, or `persistence`. Domain packages do not import `infrastructure`. See [Persistence](persistence.md) for the durable event store and replay contract.

Import-linter (`pyproject.toml`) and `tests/architecture/boundary_checker.py` enforce the allowlist, private-world authority, public facades, framework leakage, provider SDKs, and prohibited `random` / wall-clock / UUID defaults in domain code.

## Public facades

Import packages, not private modules:

- `world`: IDs, values, objective models, closed commands, `Observation`, causes/effects, `ActionProposal`, `ActionRequest` (non-authoritative), `WorldEvent`, `detached_mapping`
- `agents`: `AgentId`, `Agent`, `Goal`, `IdentityTranslator`
- `agents.cognition`: `CognitionStrategy` (`propose` → `AgentCommand`), `Perspective`
- `memory`: `MemoryTrace`, `Belief`, owner-bound stores, `OwnershipError`
- `social`: `CommunicationEnvelope`, `Relationship`, `EnvelopeSender`
- `llm`: `LLMProvider`, `LLMRequest`, `LLMResult`, `StructuredOutput`, prompts, factory
- `simulation`: `WorldEngine`, `WorldBootstrap`, lifecycle types, `build_perspective`, persistence DTOs/ports, `PersistentSimulationService`, `ReplayService`, codecs, deterministic IDs/RNG/clock, export ports
- `persistence`: repository factories (`create_run_repository`, …)
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
8. **Memory is agent-scoped.** Stores reject cross-owner writes; nothing shares memory automatically.
9. **Information crosses agents only via perception and explicit communication.** Envelopes cannot carry memory traces or `Agent` values.
10. **Randomness is injected from an explicit seed.** `SimulationRunConfig.seed` is required; only `simulation.randomness` may use `random.Random` instances. Seeds are never logged.
11. **Cognition is a strategy protocol.** `CognitionStrategy.propose(perspective)` returns `AgentCommand` and has no LLM, repository, `WorldState`, or mutation capability in its signature.

## Determinism and trust stages

- Stream seeds and IDs use SHA-256 over canonical length-prefixed bytes. Derivation-v2 includes the physical-rules fingerprint so equal seeds with different rules do not alias. Legacy derivation-v1 remains for old records.
- Operational HTTP request IDs and log timestamps are infrastructure metadata. They cannot populate simulation IDs, event order, domain times, or RNG seeds (`reject_operational_identifier`).
- Trust pipeline: `AgentCommand` → engine-owned admission → private pending prepare (actions + autonomous) → single finalizer → atomic `WorldEngine` commit.
- Exact external LLM replay requires **recorded responses or deterministic stubs**. Local seed derivation is not enough (`LLM_REPLAY_REQUIREMENT`).

## Deferred scope

No agent cognition loop inside the engine, fear-of-death psychology, memory retrieval algorithms, analysis metrics, Anthropic-native adapters, pathfinding beyond one adjacent edge, crafting, diseases, revival, or multi-tick sleeping state. Provider lifecycle is not wired into the API/`compose` composition root yet. No Kafka, Kubernetes, Celery, or extra vector databases.

Production PostgreSQL privilege design for `CREATE EXTENSION` is deferred; development credentials may create `vector`.

## See also

- [LLM providers](llm-providers.md)
- [Physical simulation](physical-simulation.md)
- [Configuration](configuration.md)
- [Development](development.md)
- [Persistence](persistence.md)
