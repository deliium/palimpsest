# Architecture

[Back to README](../README.md) · [Next Page →](cognition-runtime.md)

Palimpsest is a modular monolith under `src/`. Cross-module imports must target a package `__init__.py` facade or names listed in `__all__`. Private modules (leading `_`) are not cross-boundary APIs.

## Bounded packages

| Package | Responsibility | May import |
| --- | --- | --- |
| `world` | Opaque IDs, typed observations, closed commands, immutable events. Private `World` / `WorldState` / operations / rules / physical / transitions | *(none)* |
| `agents` | Agent identity, hierarchical goals (`GOAL_MODEL_VERSION` 3), and subjective `Agent` contracts | `world` (agent-facing only) |
| `agents.cognition` | Async `CognitiveLoop`, stage protocols (incl. `GoalManager` / `GoalBoard`), reconstructive memory stage, `LLMMemoryReconstructor`, production subjective goal/imagination/motivation/deliberation policies; sync `CognitionStrategy` retained | `world`, `agents`, `memory`, `social`, `llm` |
| `memory` | Owner-scoped episodic `MemoryTrace`, semantic beliefs/revisions, `MemoryService`, reconstructive recall, scoring/decay | `world`, `agents` (opaque `EventId` only — never `WorldEvent`) |
| `social` | Opaque communication envelopes and directed relationship profiles (trust/fear/affection/debt/respect/resentment/familiarity/dependency) | `world`, `agents` |
| `llm` | Provider-neutral structured `LLMProvider` / `LLMResult` | *(none)* |
| `simulation` | `WorldEngine`, `AgentRuntime`, `SimulationRunner`, bootstrap, lifecycle, seed/clock/RNG/IDs, codecs, `SubjectiveStateService`, persistence ports, durable tick service, replay | `world`, `agents`, `agents.cognition`, `memory`, `social`, `llm` |
| `observer` | Read-only presentation contracts, layout catalogs, semantic event adaptation, and objective frames. No tick authority | `world`, `simulation` public facts (not `simulation.engine`) |
| `experiments` | Trusted A–E catalog, coordinator, collectors, analysis-only truth specs | `simulation`, `analysis`, `agents`, `world` |
| `persistence` | SQLAlchemy adapters for simulation repositories, owner-scoped memory, subjective models, and experiment records | `simulation`, `infrastructure`, `memory`, `social`, `experiments` (ports only) |
| `api` | HTTP composition root | `simulation`, `infrastructure`, `persistence`, `observer` |
| `analysis` | Read-only events/exports + experiment memory-drift joins | `world`, `simulation`, `memory` (read-only contracts) |
| `infrastructure` | Settings, logging, PostgreSQL adapters | *(none of the domain packages)* |

Private world authority (`world/_state.py`, `world/_transitions.py`, `world/_operations.py`, `world/_rules.py`, `world/_physical.py`, `world/_perception.py`, `world/_replay.py`) may be imported only by `simulation.engine`, `simulation.bootstrap`, and other private `world._*` modules. They are not re-exported from `world`.

`memory` and `social` are independent (no cross-imports). Base `agents` must not import `agents.cognition`. `llm` imports no domain module. `simulation` must not import `api`, `analysis`, `experiments`, `infrastructure`, or `persistence`. Domain packages do not import `infrastructure` or `experiments`. `persistence` may import public `memory` and `social` facades and `experiments.persistence` ports for durable adapters (intentional). `analysis` may import `memory` read-only contracts for drift and social-transmission analysis. Subjective beliefs, self-model projections, and relationship profiles never become `WorldEvent` variants or enter `AUTHORITATIVE_TABLES`. See [Persistence](persistence.md), [Simulation runner](simulation-runner.md), [Experiments](experiments.md), [Analysis metrics](analysis-metrics.md), [Research API](research-api.md), [Read-only observer](observer.md), [Memory reconstruction](memory-reconstruction.md), and [Social communication](social-communication.md).

Import-linter (`pyproject.toml`) and `tests/architecture/boundary_checker.py` enforce the allowlist, private-world authority, public facades, framework leakage, provider SDKs, and prohibited `random` / wall-clock / UUID defaults in domain code.

## Public facades

Import packages, not private modules:

- `world`: IDs, values, objective models, closed commands, `Observation`, causes/effects, `ActionProposal`, `ActionRequest` (non-authoritative), `WorldEvent`, `detached_mapping`
- `agents`: `AgentId`, `Agent`, `Goal` (horizons/statuses/relations), `IdentityTranslator`
- `agents.cognition`: `CognitiveLoop`, stage protocols/defaults, `GoalManager` / `GoalBoard` / `CognitionGoalManagementMode`, production `HierarchicalGoalManager` / `ImaginationEngine` / `MotivationAppraisal` / `MultiCriteriaIntentionSelector` / `CommandPlanner`, `CognitionStrategy`, `Perspective`, `SelfModel`, `SubjectiveSnapshot`, `LLMMemoryReconstructor`
- `memory`: `MemoryTrace`, `MemoryService`, semantic belief contracts, recall/reconstruction, scoring/decay policies, legacy `Belief`, owner-bound stores, `OwnershipError`
- `social`: `CommunicationEnvelope`, directed relationship profiles/revisions, legacy `Relationship`, `EnvelopeSender`
- `llm`: `LLMProvider`, `LLMRequest`, `LLMResult`, `StructuredOutput`, prompts (incl. `reconstructive_memory/v1`), factory
- `simulation`: `WorldEngine`, `AgentRuntime`, `WorldBootstrap`, lifecycle types, `build_perspective`, `SubjectiveStateService`, persistence DTOs/ports, `PersistentSimulationService`, `ReplayService`, codecs (incl. subjective-v1), deterministic IDs/RNG/clock, export ports
- `persistence`: repository factories, `create_memory_service`, and `create_subjective_state_service` (always require owner scope)
- `analysis`: `EventSource`, `ExportSource`, `MemoryDriftAnalysisService`, drift/chain DTOs, `MetricFamilyId` / `metric_specification` catalog
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
- New physical runs emit schema-v5 replay events (structured communication + occurrence context). Schemas v2–v4 remain readable; schema-1 export remains an audit artifact where applicable. Version taxonomy: `simulation.compatibility` / [Persistence](persistence.md).

## Perception boundary

Objective `WorldState` stays private. Agent-facing cognition sees only immutable, agent-specific `Observation` values produced by private `world._perception.PerceptionService` and routed by the engine.

| Concern | Contract |
| --- | --- |
| Input | Tick-start snapshot + committed events from tick `N−1` (never the still-open tick) |
| Output | Exactly one detached `Observation` per registered observer; repeated `observe()` in one open tick is equal |
| Routing | `WorldEngine.observation_for(AgentId)` or `ObservationBatch.for_observer`; cognition uses `build_perspective` |
| Forbidden to cognition | `WorldState`, `World`, engine snapshots, private projectors, raw `WorldEvent`, another agent's observation, all-agent batches |

### Domain-contract evolution (Observation / commands / communications)

Later V2 feature plans may evolve agent-facing contracts only under this accepted-set discipline (this scaffolding plan adds **no** new fields, commands, or communication variants):

1. **Observation and related codecs** — new write versions only when the wire shape changes; legacy decode remains in an `ACCEPTED_*` set. Cognition inputs must not silently widen to authority types (`WorldState`, private `world._*`, `WorldEvent` stores).
2. **Closed `AgentCommand` set** — remains closed at fifteen variants unless a versioned bump lands together with admission rules, world-operation evaluation, event details, and replay codecs in the same change.
3. **Communications** — stay event-only (`Talk`/`Ask`/`Tell` → `Talked`/`Asked`/`Told`). Delivery proves delivery, not truth; declared lineage on `StructuredUtterance` is distrustable testimony. Content never becomes world-owned fact.
4. **Hard gate for any domain bump** — live and restored engines at the same tick must emit equal observations (including canonical serialization). Required regression: `tests/unit/test_checkpoint_restoration.py::test_live_and_restored_observations_match_with_prior_events` (and siblings). Do not ship a domain wire change that breaks live/restored parity.

See also `simulation.compatibility` (version taxonomy) and [.ai-factory/ARCHITECTURE.md](../.ai-factory/ARCHITECTURE.md).

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
9. **Information crosses agents only via perception, explicit communication, or physical external artifacts.** Perception and Talk/Ask/Tell delivery events never copy sender memory, beliefs, reconstructions, or relationship state. Portable items transferred by Take/Drop/Give (and observed via perception) are the only physical channel for shared external state. Social envelopes cannot carry memory traces or `Agent` values; silent cross-agent memory/belief copy is forbidden.
10. **Randomness is injected from an explicit seed.** `SimulationRunConfig.seed` is required; only `simulation.randomness` may use `random.Random` instances. Seeds are never logged.
11. **Cognition is a strategy protocol.** `CognitionStrategy.propose(perspective)` returns `AgentCommand` and has no LLM, repository, `WorldState`, or mutation capability in its signature.

## Determinism and trust stages

- Stream seeds and IDs use SHA-256 over canonical length-prefixed bytes. Derivation-v2 includes the physical-rules fingerprint so equal seeds with different rules do not alias. Legacy derivation-v1 remains for old records.
- Operational HTTP request IDs and log timestamps are infrastructure metadata. They cannot populate simulation IDs, event order, domain times, or RNG seeds (`reject_operational_identifier`).
- Trust pipeline: `AgentCommand` → engine-owned admission → private pending prepare (actions + autonomous) → single finalizer → atomic `WorldEngine` commit.
- Exact external LLM replay requires **recorded responses or deterministic stubs**. Local seed derivation is not enough (`LLM_REPLAY_REQUIREMENT`).

## Deferred scope

No Anthropic-native adapters, pathfinding beyond one adjacent edge, crafting, diseases, revival, or multi-tick sleeping state. Psychological **fear of death** is implemented as subjective opportunity foreclosure inside cognition (see [Cognition and agent runtime](cognition-runtime.md)); it does not alter physical death rules. Reconstructive recall and append-only reconsolidation are **implemented** (see [Memory reconstruction](memory-reconstruction.md)); LLM-backed reconstruction remains optional and provider lifecycle is not wired into the API/`compose` composition root yet. No Kafka, Kubernetes, Celery, or extra vector databases.

Production PostgreSQL privilege design for `CREATE EXTENSION` is deferred; development credentials may create `vector`.

## V2 extension seams (scaffolding)

Later V2 feature plans plug into these seams only. They must not re-open WorldEngine authority, Observation trust, or replay identity.

| Seam | Where | Notes |
| --- | --- | --- |
| CognitiveLoop stage protocols | `agents.cognition` constructor injection | Plain Python; no LangGraph/discovery plugins |
| `AgentCognitionSpec` modes | `MemoryMode` / `ImaginationMode` (+ mortality on run config) | Closed enums; new modes need versioned bumps |
| Run-level `V2CapabilityFlags` | `SimulationRunnerConfig` / `runner-config-v3+` | Default off = V1-equivalent; flags-on fail closed until owned |
| Cognition execution trace | `CognitionTraceSpec` / `runner-config-v4` + Alembic `0013` | Default off; not a capability flag; non-authoritative; ports only (no HTTP yet) |
| `AgentRuntime` subjective finalization | `simulation.agent_runtime` | Episodic + beliefs + relationships; never objective fold |
| PerceptionService | private `world._perception` | Observe-only; never forms memory/belief |
| Communication eligibility | private world policy + `world.communications` | Event-only delivery; testimony distrust |
| Experiment catalog arms | `experiments.catalog` A–E on the V1 gate; F–H off that gate | Flags ride in runner JSON; stay on `experiment-definition-v1` |
| Analysis evidence stages | `analysis` only | Never feed reports into live cognition |
| LLM lifecycle composition | `api` + `llm.factory` | **Not** a runner flag; still deferred until a cognition consumer owns it |

**Off-limits:** WorldEngine admission, event immutability / `AUTHORITATIVE_TABLES`, Observation → authority type widening, silent cross-agent memory copy, scripted “emergence” roles.

See `simulation.compatibility`, [Simulation runner](simulation-runner.md), and [.ai-factory/ARCHITECTURE.md](../.ai-factory/ARCHITECTURE.md).

### Downstream V2 plan contract

Every later V2 feature plan must satisfy this checklist before merge:

1. **V1 invariants intact** — WorldEngine authority, Observation trust, append-only history, subjective ≠ objective fold, LLM non-authority, no silent cross-agent copy, reproducible seeds/stubs where claimed.
2. **Capability flags opt-in** — reserved `V2CapabilityFlags` stay default-off; enabling a flag without an owning plan fails closed (`capability_unimplemented`); owned flags (`predictive_world_model`, `extended_self_model`, `short_term_emotional_state`) may enable without that error; no silent behavior when off.
3. **V1 regression gate green** — `tests/unit/test_v1_regression_gate.py` (catalog A–E + short reference) and replay/API compat suites remain passing under flags-off **and** tracing-off (`v1_regression_profile` rejects enabled tracing).
4. **Schema bumps use accepted-set + exact key-set discipline** — never drop accepted V1 versions in the same change that adds a write version; runner JSON uses versioned `_require_keys` (no silent extra fields on an existing schema id).
5. **No scripted emergence** — no hard-coded friend/enemy/leader/culture roles or milestone scripts that fake social outcomes beyond existing trusted override patterns.
6. **No LLM → world shortcuts** — validated LLM shape still requires cognition translation + normal admission; never direct `WorldState` mutation.
7. **Experiments stay reproducible** — `experiment-definition-v1`; flags ride in runner JSON; paired arms keep shared seed/scenario/stochastic identity; prefer deterministic fakes or recorded LLM paths. Experiment H (`extended_self_model`), Experiment I (`predictive_world_model`, metric `causal_world_model@1`), Experiment J (`prospective_imagination@1`), and Experiment K (`counterfactual_reasoning@1`) stay off the V1 regression gate.
8. **Optional tracing stays outside the objective fold** — cognition-trace tables are non-authoritative and must not enter `EvidenceManifest` / objective high-water; tracing on vs off must not change `exact_trajectory_hash`.

Register roadmap milestones via `/aif-roadmap` (e.g. M5 for this scaffolding) — not from individual feature plans inventing milestone IDs ad hoc.

## See also

- [Cognition and agent runtime](cognition-runtime.md)
- [Memory reconstruction](memory-reconstruction.md)
- [Social communication](social-communication.md)
- [LLM providers](llm-providers.md)
- [Physical simulation](physical-simulation.md)
- [Configuration](configuration.md)
- [Development](development.md)
- [Persistence](persistence.md)
