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
| `experiments` | Trusted A–E catalog, coordinator, collectors, analysis-only truth specs, `experiment-matrix-v1` expansion/batch (no HTTP) | `simulation`, `analysis`, `agents`, `world` |
| `research_runner` | Thin CLI composition for matrix batches (`palimpsest-matrix`); no HTTP server | `experiments`, `simulation`, `persistence`, `infrastructure`, `analysis` (never `api`) |
| `persistence` | SQLAlchemy adapters for simulation repositories, owner-scoped memory, subjective models, and experiment records | `simulation`, `infrastructure`, `memory`, `social`, `experiments` (ports only) |
| `api` | HTTP composition root | `simulation`, `infrastructure`, `persistence`, `observer` |
| `analysis` | Read-only events/exports + experiment memory-drift joins | `world`, `simulation`, `memory` (read-only contracts) |
| `infrastructure` | Settings, logging, PostgreSQL adapters | *(none of the domain packages)* |

Private world authority (`world/_state.py`, `world/_transitions.py`, `world/_operations.py`, `world/_rules.py`, `world/_physical.py`, `world/_perception.py`, `world/_replay.py`) may be imported only by `simulation.engine`, `simulation.bootstrap`, and other private `world._*` modules. They are not re-exported from `world`.

`memory` and `social` are independent (no cross-imports). Base `agents` must not import `agents.cognition`. `llm` imports no domain module. `simulation` must not import `api`, `analysis`, `experiments`, `infrastructure`, or `persistence`. Domain packages do not import `infrastructure` or `experiments`. `experiments` must not import `api`, `infrastructure`, or `persistence`. `research_runner` must not import `api` (matrix CLI is process-local). `persistence` may import public `memory` and `social` facades and `experiments.persistence` ports for durable adapters (intentional). `analysis` may import `memory` read-only contracts for drift and social-transmission analysis. Subjective beliefs, self-model projections, and relationship profiles never become `WorldEvent` variants or enter `AUTHORITATIVE_TABLES`. See [Persistence](persistence.md), [Simulation runner](simulation-runner.md), [Experiments](experiments.md), [Analysis metrics](analysis-metrics.md), [Research API](research-api.md), [Read-only observer](observer.md), [Memory reconstruction](memory-reconstruction.md), and [Social communication](social-communication.md).

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
- All twenty-four commands have explicit applied / rejected / conflicted behavior (no deferred physical policy). Details: [Physical simulation](physical-simulation.md).
- New physical runs emit schema-v5 replay events (structured communication + occurrence context). Schemas v2–v4 remain readable; schema-1 export remains an audit artifact where applicable. Replay-v6 is an accepted schema written only by a run whose production catalog is non-empty. Replay-v7 is accepted and is written only by a run whose environmental dynamics spec is set. Replay-v8 is accepted and is written only when artifacts are active at run start (codec `v5`). The default write remains replay-v5. Version taxonomy: `simulation.compatibility` / [Persistence](persistence.md).

## Perception boundary

Objective `WorldState` stays private. Agent-facing cognition sees only immutable, agent-specific `Observation` values produced by private `world._perception.PerceptionService` and routed by the engine.

| Concern | Contract |
| --- | --- |
| Input | Tick-start snapshot + committed events from tick `N−1` (never the still-open tick) |
| Output | Exactly one detached `Observation` per registered observer; repeated `observe()` in one open tick is equal |
| Routing | `WorldEngine.observation_for(AgentId)` or `ObservationBatch.for_observer`; cognition uses `build_perspective` |
| Forbidden to cognition | `WorldState`, `World`, engine snapshots, private projectors, raw `WorldEvent`, another agent's observation, all-agent batches |

### Domain-contract evolution (Observation / commands / communications)

Later V2/V3 feature plans may evolve agent-facing contracts only under this accepted-set discipline (V3 scaffolding alone adds **no** kinship/settlement/institution wire; owned `generational_population` co-lands versioned seams below):

1. **Observation and related codecs** — new write versions only when the wire shape changes; legacy decode remains in an `ACCEPTED_*` set. Cognition inputs must not silently widen to authority types (`WorldState`, private `world._*`, `WorldEvent` stores). Channel-off Observation stays unchanged; channel-on may add closed optional `lifecycle` fields only.
2. **Closed `AgentCommand` set** — remains closed at twenty-six variants, including harvest, craft, build, repair, store, the four artifact commands (`Inscribe` / `Amend` / `Erase` / `TransferArtifact`), and dependency-care `Feed` / `Transport` (legal only when `dependency_care.care_action_policy` allows). A later bump still lands together with admission rules, world-operation evaluation, event details, and replay codecs in the same change. The production catalog is not an observation field and is not a cognition input to the engine.
3. **Communications** — stay event-only (`Talk`/`Ask`/`Tell` → `Talked`/`Asked`/`Told`). Delivery proves delivery, not truth; declared lineage on `StructuredUtterance` is distrustable testimony. Content never becomes world-owned fact.
4. **Roster / birth / kinship-visible / dependency-need facts** — mid-run roster and birth-class occurrences for `generational_population` co-landed in v3-02 (`admit_population_entry`, replay-v9 / codec v6, Observation `lifecycle`). v3-03 extends the same owned flag with blank-slate `NewAgentInitialization` (runner-config-v25, sibling `AgentInitializationRecorded` / replay-v10 / codec v7) — no cultural/map/language injection at birth; origin refs are experimental labels only. v3-04 deepens the same flag with developmental stage effects / gradual aging / lifespan distributions on `runner-config-v26` (Observation `lifecycle` object stays closed; assigned lifespan is checkpoint/record-only). v3-05 owns `kinship_inheritance` for **objective genealogy only** on `runner-config-v27|v28` (parent→child edges, derived sibling/ancestor/descendant queries, default `perception_mode=none`; optional closed `kinship_visible` when `self_incident_public`). Relatedness never implies trust/affection/loyalty/obligation/inheritance/group identity. v3-06 deepens owned `generational_population` with exact `dependency_care` on `runner-config-v28` (self-satisfy denials, unmet-need progression, `Feed`/`Transport`, optional `ObservedDependencyNeeds` when `perception_mode=self_and_colocated`; never parent→caregiver hardwiring). Do **not** silently widen `Observation` outside closed additive objects.
5. **Hard gate for any domain bump** — live and restored engines at the same tick must emit equal observations (including canonical serialization). Required regression: `tests/unit/test_checkpoint_restoration.py::test_live_and_restored_observations_match_with_prior_events` (and siblings). Do not ship a domain wire change that breaks live/restored parity.

See also `simulation.compatibility` (version taxonomy) and [.ai-factory/ARCHITECTURE.md](../.ai-factory/ARCHITECTURE.md).

### Field access matrix

| Access | Examples |
| --- | --- |
| Always self-known | Self physiology/inventory, hour, day phase, visibility, local weather condition, current location id/name, adjacent exits |
| Visibility-gated (≥ 0.5) | Local ground items, resources (quantity only), structures at the location, ground artifacts at the location, coarse nearby bodies, public occurrence facts for local bystanders. Artifacts held by self are always visible; foreign held artifacts are omitted. |
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
4. **Actions are structured and typed.** Twenty-four closed `AgentCommand` variants; cognition returns commands; the engine admits and resolves them.
5. **LLM output is untrusted.** Structurally validated `LLMResult` / `StructuredOutput` cannot mutate world state or become commands without an explicit cognition translation step.
6. **`WorldEvent` is immutable.** Closed occurrence details; no open payloads. Rejected/conflicted/duplicate outcomes emit no world events.
7. **Memories and beliefs may be wrong.** They are mutable owner-bound aggregates (`MemoryTrace` / `Belief`).
8. **Memory is agent- and run-scoped.** Normal `MemoryService` instances bind one `MemoryScope(run_id, owner_id)`. Stores reject cross-owner writes; retrieval/recall never joins objective events. Remembered episodes are reconstructed (`ReconstructedMemory`), not raw traces.
9. **Information crosses agents only via perception, explicit communication, or physical external artifacts.** Perception and Talk/Ask/Tell delivery events never copy sender memory, beliefs, reconstructions, or relationship state. Shared physical state may move as portable items (Take/Drop/Give) or as WorldEngine-owned information artifacts (Inscribe/Amend/Erase/TransferArtifact); both are observed via perception, and artifact meaning is never auto-downloaded into memory. Social envelopes cannot carry memory traces or `Agent` values; silent cross-agent memory/belief copy is forbidden.
10. **Randomness is injected from an explicit seed.** `SimulationRunConfig.seed` is required; only `simulation.randomness` may use `random.Random` instances. Seeds are never logged.
11. **Cognition is a strategy protocol.** `CognitionStrategy.propose(perspective)` returns `AgentCommand` and has no LLM, repository, `WorldState`, or mutation capability in its signature.

## Determinism and trust stages

- Stream seeds and IDs use SHA-256 over canonical length-prefixed bytes. Derivation-v2 includes the physical-rules fingerprint so equal seeds with different rules do not alias. Legacy derivation-v1 remains for old records.
- Operational HTTP request IDs and log timestamps are infrastructure metadata. They cannot populate simulation IDs, event order, domain times, or RNG seeds (`reject_operational_identifier`).
- Trust pipeline: `AgentCommand` → engine-owned admission → private pending prepare (actions + autonomous) → single finalizer → atomic `WorldEngine` commit.
- Exact external LLM replay requires **recorded responses or deterministic stubs**. Local seed derivation is not enough (`LLM_REPLAY_REQUIREMENT`). Satisfied by `deterministic_fake` or a `replay` store of validated exchanges (`llm.recording`); see [LLM providers](llm-providers.md).

## Deferred scope

No Anthropic-native adapters, pathfinding beyond one adjacent edge, crafting, diseases, revival, or multi-tick sleeping state. Psychological **fear of death** is implemented as subjective opportunity foreclosure inside cognition (see [Cognition and agent runtime](cognition-runtime.md)); it does not alter physical death rules. Reconstructive recall and append-only reconsolidation are **implemented** (see [Memory reconstruction](memory-reconstruction.md)); LLM-backed reconstruction remains optional and provider lifecycle is not wired into the API/`compose` composition root yet. No Kafka, Kubernetes, Celery, or extra vector databases.

Production PostgreSQL privilege design for `CREATE EXTENSION` is deferred; development credentials may create `vector`.

## V3 scaffolding invariant inventory

V3 compatibility scaffolding reuses the existing architecture gates under `tests/architecture/` (world authority, cognitive-loop / LLM / social / experiment / analysis / Godot / observer isolation, cognitive-architecture boundaries, import-linter) plus `tests/unit/test_v2_scientific_invariants.py`. Gap pins for fixed bootstrap roster (no mid-run register/unbind API today), `prepare_parallel=False`, Godot/presentation non-authority, and forbid scripted `civilization_emerged` / `institution_formed` / `kinship_must_form` mandate helpers live in `tests/architecture/test_v3_scaffolding_invariants.py`. Analysis and experiment packages must still never feed live cognition.

Version taxonomy: `simulation.compatibility` pins Alembic head `0017`, default runner write `runner-config-v4`, planned accepted `runner-config-v23` (v22 ∪ `v3_capability_flags`), observer `observer-protocol-v1` / `observer-layout-v1`, Research UI `/research/`, and event write replay-v5. See [Persistence](persistence.md).

## V2 extension seams (scaffolding)

Later V2 feature plans plug into these seams only. They must not re-open WorldEngine authority, Observation trust, or replay identity.

| Seam | Where | Notes |
| --- | --- | --- |
| CognitiveLoop stage protocols | `agents.cognition` constructor injection | Plain Python; no LangGraph/discovery plugins |
| `AgentCognitionSpec` modes | `MemoryMode` / `ImaginationMode` (+ mortality on run config) | Closed enums; new modes need versioned bumps |
| Run-level `V2CapabilityFlags` | `SimulationRunnerConfig` / `runner-config-v3+` | Default off = V1-equivalent; flags-on fail closed until owned |
| Cognition execution trace | `CognitionTraceSpec` / `runner-config-v4` + Alembic `0013` | Default off; not a capability flag; non-authoritative; HTTP debugger under `subjective_debug` (observational GET-only; see [Research causal debugger](research-causal-debugger.md)) |
| `AgentRuntime` subjective finalization | `simulation.agent_runtime` | Episodic + beliefs + relationships; never objective fold |
| PerceptionService | private `world._perception` | Observe-only; never forms memory/belief |
| Communication eligibility | private world policy + `world.communications` | Event-only delivery; testimony distrust |
| Experiment catalog arms | `experiments.catalog` A–E on the V1 gate; F–Z off that gate | Flags ride in runner JSON; stay on `experiment-definition-v1` |
| Analysis evidence stages | `analysis` only | Never feed reports into live cognition |
| LLM lifecycle composition | `api` + `llm.factory` | **Not** a runner flag; still deferred until a cognition consumer owns it |

**Off-limits:** WorldEngine admission, event immutability / `AUTHORITATIVE_TABLES`, Observation → authority type widening, silent cross-agent memory copy, scripted “emergence” roles.

See `simulation.compatibility`, [Simulation runner](simulation-runner.md), and [.ai-factory/ARCHITECTURE.md](../.ai-factory/ARCHITECTURE.md).

### Downstream V2 plan contract

Every later V2 feature plan must satisfy this checklist before merge:

1. **V1 invariants intact** — WorldEngine authority, Observation trust, append-only history, subjective ≠ objective fold, LLM non-authority, no silent cross-agent copy, reproducible seeds/stubs where claimed.
2. **Capability flags opt-in** — reserved `V2CapabilityFlags` stay default-off; enabling a flag without an owning plan fails closed (`capability_unimplemented`); owned flags (`advanced_social_inference`, `predictive_world_model`, `extended_self_model`, `short_term_emotional_state`) may enable without that error; no silent behavior when off. `multi_hop_testimony_tracking` is still unowned. Named cognitive architecture variants (`agents.cognition.architectures` / Experiment AC) are composition presets over existing modes and owned flags — not new flag slots and not a runner schema key for `architecture_id` (see [Cognition and agent runtime](cognition-runtime.md#cognitive-architecture-variants)).
3. **V1 regression gate green** — `tests/unit/test_v1_regression_gate.py` (catalog A–E + short reference) and replay/API compat suites remain passing under flags-off **and** tracing-off (`v1_regression_profile` rejects enabled tracing).
4. **Schema bumps use accepted-set + exact key-set discipline** — never drop accepted V1 versions in the same change that adds a write version; runner JSON uses versioned `_require_keys` (no silent extra fields on an existing schema id).
5. **No scripted emergence** — no hard-coded friend/enemy/leader/culture roles or milestone scripts that fake social outcomes beyond existing trusted override patterns.
6. **No LLM → world shortcuts** — validated LLM shape still requires cognition translation + normal admission; never direct `WorldState` mutation.
7. **Experiments stay reproducible** — `experiment-definition-v1`; flags ride in runner JSON; paired arms keep shared seed/scenario/stochastic identity; prefer deterministic fakes or recorded LLM paths. Experiment H (`extended_self_model`), Experiment I (`predictive_world_model`, metric `causal_world_model@1`), Experiment J (`prospective_imagination@1`), Experiment K (`counterfactual_reasoning@1`), Experiment L (`advanced_social_inference`, metric `theory_of_mind@1`), Experiment M (`advanced_social_inference`, epistemic ledger), Experiments N, O, and P (`communication_strategy@1`), and Experiment AC (`experiment-ac-cognitive-architectures`, shared-seed architecture matrix) stay off the V1 regression gate. `theory_of_mind@1` and `communication_strategy@1` are analysis-only and are not inputs to cognition. `communication_strategy@1` assigns `memory_error` only when `cited_event_id` names a committed occurrence whose public tokens do not cover the source tokens. `v1_regression_profile` is unchanged: it checks capability flags and tracing, and catalog A–E stay on `runner-config-v4` with communication strategy and reputation `DISABLED`. `runner-config-v9` carries every `runner-config-v8` cognition key plus `communication_strategy_mode` and is emitted only when that mode is `DETERMINISTIC` and every reputation mode is `DISABLED`. A non-disabled strategy is accepted on v9 or v10. `runner-config-v10` carries every v9 cognition key plus `reputation_mode` and is emitted only when some agent's `ReputationMode` is `DETERMINISTIC`. No capability flag was added for either mode. Experiment Q and `distributed_reputation@1` stay off the V1 regression gate. The metric averages private ledgers inside a caller-supplied neighborhood and is not an input to cognition. `advanced_social_inference` still owns a private first-order mind and, on the same flag, a flat epistemic ledger (`max_depth` default 2, hard cap 3). Communication judgments are new, already known, secret, uncertain, or contradictory. Secret is not a stored attitude. One agent does not receive another agent's private goals, drives, beliefs, or mind model. `multi_hop_testimony_tracking` remains unowned. `SkillLearningMode` defaults to `DISABLED`. `runner-config-v11` is emitted only when that mode is `DETERMINISTIC`. No capability flag was added for skill learning. Experiment R and `skill_learning@1` stay off the V1 regression gate. `TeachingInteractionMode` defaults to `DISABLED`. `runner-config-v12` is emitted only when that mode is `DETERMINISTIC`. No capability flag was added for teaching. Experiments S and T and `cultural_transmission@1` stay off the V1 regression gate. Environmental dynamics are not a capability flag. `runner-config-v14` is emitted only when an `EnvironmentalDynamicsSpec` is set. Replay-v7 is accepted while the default event write stays replay-v5. Experiment U (`experiment-u-seasonal-scarcity`) and `environmental_dynamics@1` stay off the V1 regression gate. The metric counts season changes and depletions from the objective log and is not an input to cognition. `TerritorialClaimMode` defaults to `DISABLED`. `runner-config-v15` is emitted only when some agent's mode is `DETERMINISTIC`. No capability flag was added. Experiment V (`experiment-v-territorial-claims`) shares seed, topology, bodies, and stochastic identity; the scarce and abundant arms differ in the food resource. Experiment V and `spatial_control@1` stay off the V1 regression gate. The metric is analysis-only and is not an input to cognition. The claim policy is `territorial-claims.v1`. `GroupFormationMode` defaults to `DISABLED`. `runner-config-v16` is emitted only when some agent's `GroupFormationMode` is `DETERMINISTIC`. Experiment W and `emergent_group_formation@1` stay off the V1 regression gate and out of cognition. The policy is `group-formation.v1`. `SocialNormMode` defaults to `DISABLED`. `runner-config-v17` is emitted only when some agent's mode is `DETERMINISTIC`. Experiment X and `emergent_social_norms@1` stay off the V1 regression gate and out of cognition. The policy is `social-norms.v1`. `SocialConventionMode` defaults to `DISABLED`. `runner-config-v18` is emitted only when some agent's mode is `DETERMINISTIC`. Experiment Y and `persistent_social_conventions@1` stay off the V1 regression gate and out of cognition. The policy is `social-conventions.v1`. `ArtifactInterpretationMode` defaults to `DISABLED`. `runner-config-v19` is emitted only when some agent's mode is `DETERMINISTIC`. Replay-v8 and persistence codec `v5` are accepted and written only when artifacts are active at run start; the default event write stays replay-v5 and the default codec stays `v2`. Experiment Z (`experiment-z-external-artifacts`) and `external_artifact_memory@1` stay off the V1 regression gate and out of cognition. No capability flag was added. `SemanticNamingMode` defaults to `DISABLED`. `runner-config-v20` is emitted only when some agent's mode is `DETERMINISTIC`. Experiment AA (`experiment-aa-emergent-naming`) and `emergent_semantic_naming@1` stay off the V1 regression gate and out of cognition. The policy is `semantic-naming.v1`. `CulturalNarrativeMode` defaults to `DISABLED`. `runner-config-v21` is emitted only when some agent's mode is `DETERMINISTIC`. Experiment AB (`experiment-ab-cultural-narratives`) and `cultural_narrative_lineage@1` stay off the V1 regression gate and out of cognition. The policy is `cultural-narratives.v1`. `CognitiveBudgetMode` defaults to `DISABLED` (not a capability flag). `runner-config-v22` is emitted only when some agent's mode is `ENFORCED` and widens prior mode allowlists through v22 (including `cultural_narrative_mode` on `{v21,v22}`). Experiment AD (`experiment-ad-cognitive-budgets`) and `cognitive_budget@1` stay off the V1 regression gate and out of cognition. The policy is `cognitive-budget-v1`. `observer-protocol-v1` is unchanged. Research simulation branching (Alembic `0015`, `/v1/.../branches`) creates a new child `run_id` from a parent fork tick + one closed `ResearchIntervention`; it must not reuse agent `CounterfactualScenario` / prospective types, must not rewrite parent history, and must not add a capability flag.
8. **Optional tracing stays outside the objective fold** — cognition-trace tables are non-authoritative and must not enter `EvidenceManifest` / objective high-water; tracing on vs off must not change `exact_trajectory_hash`. Forking does not clone cognition-trace rows.
9. **Observed metrics stay separate from agent-visible state** — `MetricDocument`s, phenomenon indicator panels (`phenomenon-indicators-v1`), matrix metric sidecars (`cells/<cell_id>.metrics.json`), and `matrix-metric-summary-v1` are analysis-only. They must not appear on `Observation` / `Perspective`, belief or relationship ledgers, or cognition stages, and they stay off the V1 regression gate. Panels report multi-indicator `support_band` codes only — never boolean `culture_emerged` / `norm_emerged` / `society_formed` labels.

Register roadmap milestones via `/aif-roadmap` (e.g. M5 for this scaffolding) — not from individual feature plans inventing milestone IDs ad hoc.

## V3 extension seams (scaffolding)

Later V3 generational plans plug into these seams only. They must not re-open WorldEngine authority, Observation trust, Godot write authority, or scripted emergence.

| Seam | Where today | Pin / reserved against |
| --- | --- | --- |
| Dynamic roster / birth registration | Bootstrap `AgentRegistration` + `WorldEngine.admit_population_entry` (channel-gated) + runner translator rebuild / mid-run `_AgentBundle` via `NewAgentInitialization` blank-slate bind | **Owned by v3-02/v3-03/v3-04** when `generational_population` is on (`runner-config-v24` lifecycle; `v25` + explicit `new_agent_initialization`; `v26` developmental children); flag-off keeps fixed bootstrap roster. Deny-list mutators stay forbidden. Bootstrap agents seed lifecycle records without Created/Entered/Initialized events |
| New-agent blank-slate bootstrap | `NewAgentInitializationSpec`, species-defaults registry (`species_default_v1`), subjective-copy deny-list, seeded `StreamScope(namespace="new_agent_init")`, spawn-location precedence, sibling `AgentInitializationRecorded` | **Owned by v3-03** on the same flag; modes may enable learning capacity, ledger **content** starts empty; no `agents[0]` subjective clone |
| Lifetimes / developmental stages | `AgentLifecycleRecord` (+ `assigned_lifespan_ticks`), chronological age = `tick − entry_tick`, `LifecycleStageChanged`, ephemeral stage capability effects, `DeathCause.LIFESPAN` via existing `Died` | **Owned by v3-02/v3-04** on `generational_population`; v3-04 adds `runner-config-v26` developmental children (`stage_capability_effects`, `gradual_aging`, `lifespan_distribution`). Effects are WorldEngine-only (ephemeral capacity / fatigue / learning / denied `AgentCommand.kind`); ELDER ≠ leader; objective age ≠ SelfModel. Dual-key checkpoint decode for assigned lifespan (no replay-v11). Experiment AG off the V1 gate |
| Kinship / inheritance | `world.kinship` graph on engine snapshot (`kinship_edges` / codec v8), `KinshipEdgeRecorded` (replay-v11), inspection/analysis DTOs, Experiment AH | **Owned by v3-05** for objective genealogy when `kinship_inheritance` is on (`runner-config-v27` + exact `kinship`; also accepted on `v28`). Cultural inheritance / knowledge handoff deferred under the same flag. Edges survive death; never auto-write social relationship dimensions or SelfModel |
| Dependency / caregiving | `world.dependency_care` + `DependencyCareSpec` on `runner-config-v28` (no new V3 flag), self-satisfy denials, unmet-need progression, `Feed`/`Transport`, optional caregiving cognition bias, inspection/metrics, Experiment AI | **Deepens owned `generational_population`** (v3-06). Requires lifecycle on + exact `dependency_care`. Never hard-codes parent→caregiver; neglect/shared/non-kin care are legal. Care bias reads `dependency_care.caregiving_cognition_mode` only (not an `AgentCognitionSpec` enum). Write-pair `(EVENT_SCHEMA_REPLAY_V12, codec v9)` when channel active |
| Developmental learning / socialization | `DevelopmentalLearningSpec` on `runner-config-v29` (no new V3 flag), `species_default_developmental_v1` (modes-on / content-empty), owner-scoped `DevelopmentalKnowledgeLedger` + acquisition provenance, rate/budget compose, metadata audits, analysis metrics, Experiment AJ | **Deepens owned `generational_population`** (v3-07). Requires lifecycle on + exact `developmental_learning` (absent object = off; present+`disabled` rejected). Never society-wide injection or peer ledger clone; kinship cultural handoff stays deferred. No new event-schema write-pair / Alembic `0018`. Mode lives under the channel object only (not `AgentCognitionSpec`) |
| Intergenerational mentorship | `MentorshipSpec` on `runner-config-v30` (no new V3 flag), owner-scoped mentorship bonds + taught-content lineage, composes V2 `TeachingInteractionMode`, fidelity/mutation metrics, Experiment AK | **Deepens owned `generational_population`** (v3-08). Requires lifecycle on + exact `mentorship` (absent object = off; present+`disabled` rejected). Never copies internal state; kinship cultural handoff stays deferred (owned by v3-09 cultural channel). No new event-schema write-pair / Alembic `0018`. Mode lives under the channel object only (not `AgentCognitionSpec`) |
| Multi-settlement / migration | Location graph + Move + capacities | Topology bootstrap-fixed (`multi_polity_migration`) |
| Institutional / economy | Structures, production, group/norm/convention ledgers | Beliefs ≠ world authority; no scripted institution outcomes (`institutional_economy`) |
| Cultural-historical memory / language | `CulturalFeatureProvenanceSpec` on `runner-config-v31|…|v35`, dual subjective (`agents.cognition.cultural_features`) / analytical (`analysis` only) representation, Experiment AL; analysis-only Assmann layers via `HistoricalMemoryLayersSpec` on **`runner-config-v32`** (optional on v33–v35), Experiment AM; durable records via `DurableRecordsSpec` on **`runner-config-v33|v34|v35`**, Experiment AN; knowledge repositories via `KnowledgeRepositoriesSpec` on **`runner-config-v34|v35`**, Experiment AO; knowledge genealogy via `KnowledgeGenealogySpec` on **`runner-config-v35`**, Experiment AP; bounded experimentation via `BoundedExperimentationSpec` on **`runner-config-v36`**, Experiment AQ; technique lifecycle via `TechniqueLifecycleSpec` on **`runner-config-v37`**, Experiment AR | **Owns `cultural_historical_memory`** (v3-09; deepened by v3-10/v3-11/v3-12/v3-13). Flag + exact `cultural_feature_provenance` on `{v31..v35}`; cultural-only legal (lifecycle optional). v3-10 adds sibling `historical_memory_layers` on **v32** (optional on v33–v35). v3-11 adds sibling `durable_records` on **`{v33,v34,v35}`** (no new V3 flag): physical genres/lineage/imperfect copy/damage/tombstone with write-pair `(EVENT_SCHEMA_REPLAY_V13, codec v10)`; marks ≠ truth. v3-12 adds sibling `knowledge_repositories` on **`{v34,v35}`** (requires durable + provenance; no new V3 flag): WorldEngine-owned containers, membership, access, maintenance/decay, imperfect index, retrieval with write-pair `(EVENT_SCHEMA_REPLAY_V14, codec v11)`; no LibraryInstitution; cultural archive/library labels stay subjective. v3-13 adds sibling `knowledge_genealogy` on **v35** (requires provenance; no new V3 flag; **no write-pair bump**): owner-scoped practical-knowledge ledger + multi-parent DAG; triple representation (objective capability ≠ subjective knowledge ≠ research lineage); cross-owner edges via analysis join only; no `GlobalTechniqueRegistry` / society encyclopedia. Kinship cultural inheritance handoff deferred. Alembic head stays `0017`. Mode under channel objects only (not `AgentCognitionSpec`). v3-14 adds sibling `bounded_experimentation` on **v36** (provenance required; no new flag). `WorldEngine` alone reads the law catalog and writes `experiment_resolved`. Closed `AgentCommand` count is **35**. SEMANTIC types are **54** (`EXPERIMENT_RESOLVED`). Protocol stays `observer-protocol-v1`. Write-pair `(EVENT_SCHEMA_REPLAY_V15, codec v12)` only while the channel is active. An LLM may draft a closed hypothesis and cannot name physics. v3-15 adds analysis-only `technique_lifecycle` on **runner-config-v37** (requires provenance and knowledge genealogy; no new flag; no write-pair bump). States are research labels, not a technology tree. |
| Long-horizon experiments | Matrix runner, branching, scale infra | Experiment/matrix extension only |
| Run-level `V3CapabilityFlags` | `SimulationRunnerConfig` / `runner-config-v23`+; `generational_population` requires `runner-config-v24|…|v35`; `kinship_inheritance` requires `runner-config-v27|…|v35`; `cultural_historical_memory` requires `{v31..v35}` | Default-off = V2-equivalent wiring; **owned** `generational_population`, `kinship_inheritance`, and `cultural_historical_memory` may enable; other V3 flags still fail closed at `from_config`. Explicit `new_agent_initialization` requires ≥`v25`; non-default developmental children require `v26`; `dependency_care` requires `v28`+ + lifecycle flag; `developmental_learning` requires `v29+` + lifecycle flag; `mentorship` requires `v30+` + lifecycle flag; `cultural_feature_provenance` requires `{v31..v35}` + cultural flag; `historical_memory_layers` requires `{v32..v35}` + cultural flag + provenance; `durable_records` requires `{v33..v35}` + cultural flag + provenance; `knowledge_repositories` requires `{v34,v35}` + cultural flag + provenance + durable; `knowledge_genealogy` requires `v35` + cultural flag + provenance; `bounded_experimentation` requires `v36` + cultural flag + provenance |
| LLM lifecycle composition | `api` + `llm.factory` | **Not** a runner flag; still deferred |

**Runtime pins:** `prepare_parallel=False` until an owned plan changes it. When `generational_population` is on, per-tick ordinal = **current registration order** (including mid-run admits); flag-off ordinal stays bootstrap-fixed. New generational cognition plugs in as constructor-injected stage slots/modes — not by renumbering fixed `CognitiveLoop` ordinals. No scripted civilization/institution/kinship helpers. No biological sex/reproduction mechanics; demographic policies are seed-derived experiment config only. Stage ids remain opaque configurable strings (AG example: `dependent`/`learning`/`independent`/`elder`); denied kinds are concrete `AgentCommand.kind` tokens only. Godot stays read-only with **no** elder-authority presentation chrome.

**Write-pair priority** (extends `checkpoint_schema_for_production`): knowledge-repositories channel on → `(EVENT_SCHEMA_REPLAY_V14, "v11")`; else durable-records channel on → `(EVENT_SCHEMA_REPLAY_V13, "v10")`; else dependency-care channel on → `(EVENT_SCHEMA_REPLAY_V12, "v9")`; else kinship channel on → `(EVENT_SCHEMA_REPLAY_V11, "v8")`; else new-agent provenance active → `(EVENT_SCHEMA_REPLAY_V10, "v7")`; else lifecycle channel on → `(EVENT_SCHEMA_REPLAY_V9, "v6")`; else artifacts → `(v8, "v5")`; else dynamics → `(v7, "v4")`; else production → `(v6, "v3")`; else → `(replay-v5, "v2")`. Knowledge genealogy (v35) does **not** change write-pair selection (subjective + analysis harvest only). Bounded experimentation selects `(EVENT_SCHEMA_REPLAY_V15, "v12")` only when the channel is active at run start; channel-off keeps the prior priority. Possession succession selects `(EVENT_SCHEMA_REPLAY_V16, "v13")` only when `possession_succession` is active; that pair outranks experimentation. Channel off does not select v16. Assigned lifespan restores via dual-key lifecycle-record decode on codec v6|v7|v8|v9|v10|v11 (synthesize `lifespan_ticks` when absent).

**Off-limits:** WorldEngine admission bypass, event immutability / `AUTHORITATIVE_TABLES`, Observation → authority type widening, Godot write authority, scripted emergence booleans, full Research UI / Godot family-tree / nursery chrome (inspection/analysis scaffolding only), Alembic `0018` by default.

### Downstream V3 plan contract

Every later V3 feature plan must satisfy this checklist before merge:

1. **V1/V2 invariants intact** — WorldEngine authority, Observation trust, append-only history, subjective ≠ objective fold, LLM non-authority, no silent cross-agent copy, reproducible seeds/stubs where claimed, Godot read-only / non-semantic coordinates.
2. **V3 flags opt-in** — reserved `V3CapabilityFlags` stay default-off; enabling an **unowned** flag fails closed at `SimulationRunner.from_config` (`capability_unimplemented`); no silent behavior when off. Owned flags: `generational_population` (v3-02–v3-04/v3-06/v3-07/v3-08) requires `runner-config-v24|…|v35` + exact `population_lifecycle` (v3-06 adds sibling `dependency_care` on **v28+**; v3-07 adds sibling `developmental_learning` on **v29+**; v3-08 adds sibling `mentorship` on **v30+**, no new flag); `kinship_inheritance` (v3-05) requires `runner-config-v27|…|v35` + exact `kinship` (kinship-only forbids lifecycle/init/dependency_care/developmental_learning/mentorship — **not** cultural); `cultural_historical_memory` (v3-09; deepened by v3-10/v3-11/v3-12/v3-13/v3-14) requires `{v31..v36}` + exact `cultural_feature_provenance` (cultural-only forbids lifecycle siblings; dual subjective/analytical representation; no global Culture); v3-10 adds sibling `historical_memory_layers` on **v32** (optional on v33–v35; analysis-only Assmann layers — never agent knowledge); v3-11 adds sibling `durable_records` on **`{v33..v35}`** (no new V3 flag; physical marks/lineage/imperfect copy — marks ≠ truth); v3-12 adds sibling `knowledge_repositories` on **`{v34,v35}`** (requires durable + provenance; no LibraryInstitution; cultural archive/library labels subjective only); v3-13 adds sibling `knowledge_genealogy` on **v35** (requires provenance; no new V3 flag; no write-pair; triple representation; cross-owner DAG edges analysis-only; no `GlobalTechniqueRegistry`). v3-14 adds sibling `bounded_experimentation` on **v36** (requires provenance; no new flag; write-pair `(EVENT_SCHEMA_REPLAY_V15, codec v12)` only when the channel is active; LLM drafts cannot name physics; success is not knowledge until an explicit learn, teach, or record step). v3-15 adds analysis-only `technique_lifecycle` on **runner-config-v37** (requires provenance and knowledge genealogy; no new V3 flag; no write-pair bump). v3-16 adds optional `possession_succession` on **runner-config-v38** only (`custody_mechanism=corpse`; no new V3 flag; no inheritance law). Command count is 36 (`AssertPossessionClaim`). Observer semantic count is 57 (`CORPSE_CUSTODY_OPENED`, `AGENT_TOOK_FROM_CORPSE`, `POSSESSION_CLAIM_ASSERTED`). Protocol id stays `observer-protocol-v1`. Alembic head stays `0017`. Explicit `new_agent_initialization` requires ≥`v25`; developmental stage extensions require `v26`. Wire for other flags remains sibling root `v3_capability_flags` on `runner-config-v23`+; default write stays `runner-config-v4` when all V3 flags are off.
3. **V1 + V2 regression green** — `tests/unit/test_v1_regression_gate.py` and `tests/unit/test_v2_scientific_invariants.py` remain passing under V3 flags off; use `v3_scaffolding_profile` / `v2_regression_profile`. Lifecycle-on arms use Experiment AE (v24), AF (v25 blank-slate), AG (v26 developmental stages); kinship-on uses Experiment AH (v27); dependency-care uses Experiment AI (v28); developmental learning uses Experiment AJ (v29); mentorship uses Experiment AK (v30); cultural transmission uses Experiment AL (v31); historical memory layers uses Experiment AM (v32); durable records uses Experiment AN (v33); knowledge repositories uses Experiment AO (v34); knowledge genealogy uses Experiment AP (v35); bounded experimentation uses Experiment AQ (v36); technique lifecycle uses Experiment AR (v37); possession succession uses Experiment AS (v38); stay **off** the V1 gate.
4. **Schema bumps use accepted-set + exact key-set discipline** — never drop accepted V1/V2 versions in the same change that adds a write version; runner JSON uses versioned `_require_keys` (no silent extra fields on an existing schema id). Mode allowlists that top out at v34 include v35.
5. **No scripted emergence** — no `civilization_emerged` / `institution_formed` / `kinship_must_form` / `culture_emerged` / `parents_always_care` / `neglect_forbidden` mandates.
6. **No LLM → world shortcuts** — validated LLM shape still requires cognition translation + normal admission.
7. **Experiments stay reproducible** — `experiment-definition-v1`; flags ride in runner JSON; prefer deterministic fakes or recorded LLM paths.
8. **Optional tracing/analysis stay outside the objective fold** — not in `EvidenceManifest` / objective high-water; no V3 fields on `GET /version`.
9. **Alembic** — head stays `0017` unless a later plan proves indexed SQL columns are necessary; V3 flags remain runner JSON only.

Register roadmap milestones via `/aif-roadmap` (e.g. **M7 — V3 Generational Architecture Scaffolding**) — not from individual feature plans inventing milestone IDs ad hoc. Keep later plan filenames / bundle stems prefixed with `v3-`.

## See also

- [Cognition and agent runtime](cognition-runtime.md)
- [Memory reconstruction](memory-reconstruction.md)
- [Social communication](social-communication.md)
- [LLM providers](llm-providers.md)
- [Physical simulation](physical-simulation.md)
- [Configuration](configuration.md)
- [Development](development.md)
- [Persistence](persistence.md)
