# Cognition and agent runtime

[← Previous Page](architecture.md) · [Back to README](../README.md) · [Next Page →](memory-reconstruction.md)

V1 adds an explicit async cognitive pipeline and a per-agent runtime on top of observation, command, `WorldEngine`, and provider-neutral LLM boundaries. World mutation remains exclusively in `WorldEngine`. Production deliberation is **deterministic and subjective**: identical observations can yield different commands when beliefs, reconstructed memories, goals, relationships, or drive profiles differ. Beliefs and memories may be wrong; neither estimate is treated as objectively correct.

## Pipeline

```text
Observation
→ perception interpretation
→ memory retrieval
→ situation model
→ beliefs/self state
→ goal management (GoalManager / GoalBoard)
→ emotional state (EmotionalStateEngine / PASSTHROUGH)
→ possible futures (ImaginationEngine)
→ motivation evaluation (MotivationAppraisal)
→ intention selection (MultiCriteriaIntentionSelector)
→ planning (CommandPlanner)
→ one structured AgentCommand
```

Each stage is a narrow async protocol under `agents.cognition`. Components are constructor-injected into `CognitiveLoop` with plain Python control flow (no LangGraph/LangChain/DAG engine). Every completed stage appends a versioned `ComponentBoundaryRecord` (typed I/O artifacts, confidence, status, decision metadata). Records are scientific receipts — not chain-of-thought, prompts, or raw provider responses.

`final_confidence` on a successful result is the **planner-supplied** confidence only. It is not an aggregate statistical estimate.

## Short-term emotional state (V2 owned flag)

`V2CapabilityFlags.short_term_emotional_state` (default **off**) owns a transient, owner-scoped `AgentEmotionalState` vector over a closed catalog (`fear`, `anger`, `sadness`, `relief`, `attachment`, `anxiety`, `confidence`). Runner maps the flag to `CognitionEmotionalStateMode`:

| Flag | Mode | Behavior |
| --- | --- | --- |
| off | `PASSTHROUGH` | Re-emit prior/empty state; no retrieval/focus/risk/intention/social bias |
| on | `ENABLED` | `emotion.v1` numeric drivers + deterministic bias hooks |

**V1 `MemoryTrace.emotional_salience`** remains a per-trace memory property. Live short-term emotion may *read* salience and *bias* retrieval/reconstruction ranking; it must not rewrite stored traces or fold into `WorldState` / objective events.

**Pipeline timing:** prior-tick state (from `AgentRuntime` → perspective → `SubjectiveSnapshot`) biases memory retrieval and situation-focus claim order in the same invocation. The updated stage output biases same-tick futures → planning and is committed onto the runtime for N+1. Carry lives on `AgentRuntime`, not on `agents.models.Agent`.

**Attention:** there is no separate attention subsystem. Flag-on “attention” means closed situation-focus / claim reweighting plus retrieval bias only.

**Enums:** `EmotionKind.FEAR` (transient owner affect) is distinct from `RelationshipDimension.FEAR` (asymmetric directed assessment). Drivers may read relationship fear as input; the types must never be conflated.

**Logging allowlist:** policy version, owner/tick, kind counts, intensity bands, driver/reason codes, bias_applied — never free-form affect narrative, observation payloads, or memory text.

**Non-goals:** free-form emotional prose, personality traits, writing emotion into objective world state, collapsing emotion+drives+goals into one reward scalar, enabling other reserved V2 flags.

## Optional cognition execution trace

In-memory `ComponentBoundaryRecord` receipts are not durable. An optional, default-off **cognition execution trace** projects those receipts (plus snapshot context) into a stable scientific stage sequence for debugger / experiment consumers — without influencing `WorldEngine`, admission, or objective replay.

### Trace-view stage sequence

```text
Observation
→ retrieved memories
→ reconstructed memories
→ situation model
→ beliefs
→ emotional state (structured projection; no free-form affect narrative)
→ goals
→ imagined futures
→ theory-of-mind models when available (else explicit unavailable)
→ selected intention
→ planned action
```

Beliefs and ToM-unavailable placeholders are **trace-view projections** (not new `CognitiveLoop` stages). The scientific **emotional state** and **goals** trace views prefer live `EMOTIONAL_STATE` / `GOAL_MANAGEMENT` stage outputs (intensities + driver codes; horizon + status histograms) and fall back to drive/salience or snapshot/motivation only when those stages are absent/PASSTHROUGH-neutral. ToM records `unavailable` / `tom_not_implemented` until a later plan owns `advanced_social_inference`.

### Package split

| Package | Owns |
| --- | --- |
| `agents.cognition.trace` | Pure stage summaries / refs / projector — no `run_id`, no persistence |
| `simulation.cognition_trace` | Run-scoped envelopes, `CognitionTraceRepository` Protocol, Null / in-memory, soft-append after bind |
| `persistence` | Codec bytes only (`SqlAlchemyCognitionTraceRepository`); **must not** import `agents.cognition` |

Configure via top-level frozen `CognitionTraceSpec` on `SimulationRunnerConfig` (`runner-config-v4`). This is **not** a V2 capability flag. When disabled, the runner injects `NullCognitionTraceRepository` (V1 behavioral parity). When enabled, append happens once after successful cognition **bind** (soft-fail: WARN + drop; never alters `ActionSubmission`). HTTP / debugger UI routes are deferred — repository ports are the consumer API.

### Logging allowlist (trace)

| Logger | Safe extras |
| --- | --- |
| `agents.cognition.trace` | stage kinds, counts, ordinals, reason codes, invocation/agent/tick ids |
| `simulation.cognition_trace` | run/agent/tick/invocation ids, hash prefixes, stage_count, sample/truncate reason codes |
| `persistence.cognition_trace` | append/commit/identical-retry/divergent-conflict metadata (same pattern as scientific evidence) |

Never log observation/memory/belief text, prompts, CoT, raw provider bodies, credentials, or endpoints.

## Production V1 deliberation policy

`default_cognitive_loop()` wires versioned production policies for imagination, motivation, intention, and planning. Perception/situation/self-state defaults remain literal stand-ins; empty memory retrieval is replaced when a `MemoryService` / `ScopedMemoryRetriever` is injected. Constructor injection still accepts mocks and legacy placeholders for tests.

| Policy | Module / class | Version constant |
| --- | --- | --- |
| Goal management | `HierarchicalGoalManager` (or `PassthroughGoalManager`) | `goals.v1` (`GOAL_POLICY_VERSION`) |
| Imagination | `ImaginationEngine` | `imagination.v1` (`IMAGINATION_POLICY_VERSION`) |
| Motivation / fear of death | `MotivationAppraisal` | `motivation.v1` (`MOTIVATION_POLICY_VERSION`) |
| Intention selection | `MultiCriteriaIntentionSelector` | `deliberation.v1` (`DELIBERATION_POLICY_VERSION`) |
| Command planning | `CommandPlanner` | `planner.v1` (`PLANNER_POLICY_VERSION`) |

`CognitionGoalManagementMode` on `CognitionLoopConfig` selects `ENABLED` (hierarchical `goals.v1`) or `PASSTHROUGH` (re-emit snapshot goals without decompose/compete). Production defaults to **ENABLED**. This is always-on cognition policy — **not** a `V2CapabilityFlags` feature and **not** gated by `CognitionTraceSpec`.

### Drives

Eleven independent drives remain simultaneously inspectable: hunger, thirst, safety, fatigue, belonging, curiosity, status, autonomy, competence, predictability, novelty. Each has a stable disposition/baseline and a contextual activation. Activations are not personality classes or a global reward. Conflicting pressures (for example urgent thirst vs. safety) stay visible as separate vectors.

### Goals and GoalBoard

`Goal` (`GOAL_MODEL_VERSION` 3) is owner-scoped and hierarchical:

- **Horizons** (closed): `DESIRE`, `LONG_TERM`, `MEDIUM_TERM`, `SUBGOAL`, `CURRENT_INTENTION`
- **Statuses**: `ACTIVE`, `COMPLETED`, `FAILED`, `ABANDONED`, `SUSPENDED`
- **Parentage**: `parent_goal_id` only (no parallel parent relation kind)
- **Relations**: ordered `DEPENDS_ON` | `COMPETES_WITH` | `REINFORCES`
- Structured `GoalOutcome` / `GoalProgress`, confidence, provenance, drive links, success/failure conditions

`GoalManager` (`ComponentKind.GOAL_MANAGEMENT`) emits a frozen `GoalBoard`: ordered goals, ordered `CURRENT_INTENTION` foci, transition intents, and decision metadata. Only **ACTIVE** board goals enter forward imagination/motivation/planning; suspended/failed/abandoned are excluded except as mortality outstanding-value inputs. Decomposition uses a **closed template registry** only (no free-text LLM structure). Cognition-local goal IDs are minted without importing `simulation`.

**Current-intention foci ≠ `SelectedIntention`.** Foci are hierarchical planning foci on the board; tick command selection remains multi-criteria deliberation over imagined futures. Competition/reinforcement uses pairwise / veto / dominance over separate vectors — **never** a permanent total-reward or utility scalar on `DecisionMetadata`.

Subjective impossibility (matching failure conditions against semantic beliefs) marks goals `FAILED` without deleting long-term parents; parent confidence/progress is dampened. ACTIVE/SUSPENDED children of `FAILED` / `ABANDONED` parents are cascade-`ABANDONED`, and goals past `deadline_tick` are abandoned as a terminal drop (distinct from suspend/resume). Critical physiological need can suspend competing medium-term work and resume it when the need drops.

### Live agent mutation and scientific revisions

Objective `GoalTransitionReceipt`s and subjective `GoalTransitionIntent`s are applied to live `Agent.goals` (ordered, owner-checked) so invocation **N+1** snapshots see updated statuses. Objective `COMPLETED` for observable outcome kinds wins over concurrent subjective `FAILED` on the same goal/tick. Scientific goal-revision evidence is published for both objective and subjective transitions; analysis `goal_completion` continues to consume **objective** receipts only.

### Imagination inputs and candidates

`ImaginationEngine` builds a bounded ordered set of `ImaginedFuture` candidates from:

- observation-derived situation and exact self physiology
- active goals and drive profile
- `SelfModel`, directed relationships
- semantic beliefs and structured reconstructed memories

It must **never** receive `WorldState`, `ObservationBatch`, objective event repositories, replay state, hidden physical rules, or actual world probabilities. Belief confidence, remembered experience, future confidence, and subjective outcome probability remain distinct values. Ranked source hits alone are not remembered outcomes.

Each candidate states a feasible direction/target, horizon, expected need/goal changes, typed risks, social effects, confidence, uncertainty, mortality appraisal components, and subjective provenance IDs.

### Motivation and fear of death

`MotivationAppraisal` activates drives from perceived need pressures, appraises active-goal progress and social/self-model fit per future, and computes typed subjective risks. **Fear of death** is opportunity foreclosure (`MortalityOpportunityForeclosure`): subjective mortality estimate combined with outstanding goal value, attachment/dependency effects, safety activation, autonomy loss, and reduction of future option space. There is **no** hard-coded `death_penalty` and **no** permanent total reward scalar.

Terminal truth remains authoritative: `AgentRuntime` still stops cognition after an observed dead self. Anticipatory mortality appraisal cannot declare an agent dead or alter physical rules.

### Intention selection and command translation

Selection is multi-criteria and deterministic:

1. reject infeasible candidates
2. apply contextual safety / critical-need vetoes
3. remove Pareto-dominated options
4. pairwise compare over activated drives, active goals, social/self-model, risk, and uncertainty
5. apply documented stable tie-breaks

The selected future/intention is non-authoritative. `CommandPlanner` compiles one fresh exact member of the closed `AgentCommand` union from the chosen direction and typed target, supported by current observed affordances; otherwise it emits `Wait`. `ActionPlan.command` is the only value passed toward `ActionSubmission`; `WorldEngine` retains all legality and mutation authority. `ImaginedFuture` is never an agent command.

## Contracts

| Type | Role |
| --- | --- |
| `CognitiveLoopInput` | One `Observation` + owning `AgentId` + immutable `InternalAgentState` + frozen `SubjectiveSnapshot` |
| `SubjectiveSnapshot` | Owner-scoped goals, drives, semantic beliefs, directed relationships, owner-safe social identity |
| Stage artifacts | Frozen perception/memory/situation/`SelfModel`/`GoalBoard`/`PossibleFutures`/`MotivationEvaluation`/`SelectedIntention`/`ActionPlan` |
| `SelfModel` | Deterministic projection of self-relevant semantic beliefs (no predefined traits/roles) |
| `CognitiveLoopResult` | Exact closed `AgentCommand` + ordered boundary records + subjective update intents |
| `MemoryUpdateIntent` | Post-cognition intents (`WRITE_MEMORY` / `WRITE_BELIEF` / `REVISE_BELIEF` / `REVISE_RELATIONSHIP`); stores are not mutated inside the loop |

Every cognition invocation sees one frozen owner snapshot. Proposed belief and relationship revisions become visible only on the next invocation after an atomic commit. The synchronous `CognitionStrategy.propose(Perspective)` contract remains for existing callers.

## Memory stage and fakes

`agents.cognition.memory.ScopedMemoryRetriever` builds current context/beliefs, calls bound `MemoryService.recall()`, and maps results into `RetrievedMemoryContext`: **`reconstructions` are the remembered episodes**; ranked hits and pending access receipts are scientific metadata only. Optional `ReconsolidationIntent` stays pending until `AgentRuntime` applies it with access receipts via `MemoryService.apply()` after the whole loop succeeds. Inject `LLMMemoryReconstructor` only when provider-backed reconstruction is desired; the default path is deterministic and provider-free.

Details: [Memory reconstruction](memory-reconstruction.md).

`tests/fakes/cognition.py` and `tests/fakes/memory.py` provide scriptable fakes (including `FakeEmbedder` / `FakeLogicalTickSource`) with metadata-only call records. Legacy placeholder stages (`PlaceholderFutureImagination`, `StableMotivationEvaluator`, `StableIntentionSelector`, `WaitFallbackPlanner`) remain for mock injection.

## AgentRuntime

`simulation.AgentRuntime` is the trusted composition boundary:

1. `start()` → `ACTIVE`
2. `process_observation(observation, token=TickToken)` builds a perspective with a frozen subjective snapshot (ownership check), runs cognition, then commits episodic writes/accesses/reconstructions plus belief and relationship revisions through one owner-scoped `SubjectiveStateService` batch
3. Dead self in the observation → `TERMINAL` (no cognition, no submission)
4. Cognition failure → no submission and no subjective mutation (including no reconsolidation)
5. Subjective updates describe the committed observation and internal decision process — not uncommitted action outcomes

`SubjectiveStateService` prevalidates intents, applies copy-then-swap (in-memory) or one PostgreSQL transaction (durable), and rolls back every subjective change on any adapter failure. Retries with the same operation ID are idempotent. Cognition never sees `TickToken`, `WorldState`, or private world modules. Only simulation constructs submissions; engine admission still derives actor/request/world/revision authority.

## Logging (metadata only)

| Logger | Levels | Allowed fields |
| --- | --- | --- |
| `agents.cognition.loop` | DEBUG stage start/complete; ERROR failure codes | invocation/agent ids, component/version, ordinal, status, confidence band, command type, counts |
| `agents.cognition.goal_manager` | DEBUG `goal_manager_start` / `goal_manager_complete`; WARN truncation/cycle; ERROR ownership | policy version, owner/tick, mode, goal/status/horizon counts, transition counts by reason, foci_count, template_code counts |
| `agents.cognition.imagination` | DEBUG start/result; WARN truncation; ERROR ownership | owner/tick, policy version, evidence counts, candidate count, direction codes, fallback |
| `agents.cognition.motivation` | DEBUG appraisal complete | policy version, owner/tick, active-drive/goal counts, appraised-future count, risk-kind counts, uncertainty band |
| `agents.cognition.deliberation` | DEBUG filter/selection/planner | policy version, candidate counts per filter, direction code, tie-break code, command type, `goal_focus_support` |
| `agents.cognition.memory` | DEBUG `memory_recall_mapped`; ERROR ownership codes | owner/tick, policy versions, source/reconstruction/pending counts, provider/fallback flags |
| `agents.cognition.reconstruction` | DEBUG/INFO/WARN LLM reconstruct path | reconstruction/request IDs, tick, prompt/policy versions, counts, fallback flags |
| `simulation.agent_runtime` | DEBUG lifecycle/cognition/apply/goal-commit; INFO start/terminal/`runtime_reconsolidation_committed`; WARN/ERROR codes | run/agent/tick/invocation/status/counts; goal apply: owner, tick, goal_id, from→to, reason_code |
| `simulation.runner` | DEBUG objective goal apply | owner, tick, goal_id, from→to, reason_code |

**Never log:** observations, memories, belief claims/values, goal descriptions/targets, self-model propositions, relationship dimension values, reconstructions/narratives, candidate effect/risk vectors, mortality components, communications, cognitive artifact bodies, prompts, provider outputs, action/command text arguments, seeds, or credentials. Logs may include run/owner/invocation IDs, ticks, policy versions, counts, statuses, direction/command **type** codes, and stable reason codes only.

Safe example:

```text
runtime_cognition_complete agent_id=agent-1 tick=3 invocation_id=agent-1-t3-i0 boundary_count=9 memory_update_count=0 command_type=Drink
```

Control verbosity with `PALIMPSEST_LOG_LEVEL`.

## Tests

```bash
# Core loop + defaults
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_cognition_models.py \
  tests/unit/test_cognitive_loop.py \
  tests/unit/test_cognition_defaults.py \
  tests/unit/test_agent_runtime.py \
  tests/architecture/test_cognitive_loop_isolation.py -q

# Subjective deliberation policies
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_imagination_engine.py \
  tests/unit/test_motivation_appraisal.py \
  tests/unit/test_fear_of_death.py \
  tests/unit/test_intention_selection.py \
  tests/unit/test_action_planner.py \
  tests/unit/test_subjective_risk_decisions.py \
  tests/unit/test_subjective_risk_property.py -q

# In-memory runtime admission (override default deselection of integration marker)
uv run --frozen --python 3.12.14 pytest \
  -m 'unit or integration' \
  tests/integration/test_agent_runtime_world_engine.py \
  tests/integration/test_subjective_risk_runtime_scenarios.py -q
```

Integration coverage is in-memory (no PostgreSQL/Docker/network/LLM). Divergence tests hold the objective observation constant and vary only subjective evidence.

## V2 extension seams (cognition / runtime)

| Seam | Contract |
| --- | --- |
| Stage protocols | Constructor-injected into `CognitiveLoop`; replace one stage at a time |
| Modes | `AgentCognitionSpec.memory_mode` / `imagination_mode`; run-level mortality |
| Capability flags | Run-level `V2CapabilityFlags` on `SimulationRunnerConfig` — not stage plugins; default off wires V1 policies; **owned** flags (currently `short_term_emotional_state`) may enable; other flags still fail closed (`capability_unimplemented`) |
| Cognition execution trace | Top-level `CognitionTraceSpec` (`runner-config-v4`, default off) — not a capability flag; ports only; no HTTP yet |
| Subjective finalization | `AgentRuntime` commits episodic/belief/relationship batches only |
| LLM lifecycle | Remains `api` / `llm.factory` composition — **not** encoded on runner fingerprints |

Off-limits from cognition: `WorldState`, `WorldEvent` stores, analysis reports, experiment collectors/truth specs.

Full seam map: [Architecture — V2 extension seams](architecture.md#v2-extension-seams-scaffolding).

## Deferred

- Production LLM-backed cognition stages (beyond optional reconstructive recall)
- Concurrent agent execution
- General M4 analysis metrics over cognition receipts
- LLM provider lifecycle composition in API / `compose.yaml` (factory ports exist; deferred until a cognition consumer owns it)
- HTTP / debugger UI over cognition-trace repository ports
- Theory-of-mind cognition (trace records `unavailable` until owned)

## See Also

- [Architecture](architecture.md)
- [Memory reconstruction](memory-reconstruction.md)
- [Physical simulation](physical-simulation.md)
- [LLM providers](llm-providers.md)
- [Development](development.md)
