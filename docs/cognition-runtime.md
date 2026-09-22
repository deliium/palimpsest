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
→ possible futures (ImaginationEngine)
→ motivation evaluation (MotivationAppraisal)
→ intention selection (MultiCriteriaIntentionSelector)
→ planning (CommandPlanner)
→ one structured AgentCommand
```

Each stage is a narrow async protocol under `agents.cognition`. Components are constructor-injected into `CognitiveLoop` with plain Python control flow (no LangGraph/LangChain/DAG engine). Every completed stage appends a versioned `ComponentBoundaryRecord` (typed I/O artifacts, confidence, status, decision metadata). Records are scientific receipts — not chain-of-thought, prompts, or raw provider responses.

`final_confidence` on a successful result is the **planner-supplied** confidence only. It is not an aggregate statistical estimate.

## Production V1 deliberation policy

`default_cognitive_loop()` wires versioned production policies for imagination, motivation, intention, and planning. Perception/situation/self-state defaults remain literal stand-ins; empty memory retrieval is replaced when a `MemoryService` / `ScopedMemoryRetriever` is injected. Constructor injection still accepts mocks and legacy placeholders for tests.

| Policy | Module / class | Version constant |
| --- | --- | --- |
| Imagination | `ImaginationEngine` | `imagination.v1` (`IMAGINATION_POLICY_VERSION`) |
| Motivation / fear of death | `MotivationAppraisal` | `motivation.v1` (`MOTIVATION_POLICY_VERSION`) |
| Intention selection | `MultiCriteriaIntentionSelector` | `deliberation.v1` (`DELIBERATION_POLICY_VERSION`) |
| Command planning | `CommandPlanner` | `planner.v1` (`PLANNER_POLICY_VERSION`) |

### Drives

Eleven independent drives remain simultaneously inspectable: hunger, thirst, safety, fatigue, belonging, curiosity, status, autonomy, competence, predictability, novelty. Each has a stable disposition/baseline and a contextual activation. Activations are not personality classes or a global reward. Conflicting pressures (for example urgent thirst vs. safety) stay visible as separate vectors.

### Goals

`Goal` carries owner scope, priority, human-readable description, closed structured `GoalOutcome`, and `GoalProgress` lifecycle metadata. Only **active** goals enter deliberation. Goal effects on candidates stay separate from drive effects.

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
| Stage artifacts | Frozen perception/memory/situation/`SelfModel`/`PossibleFutures`/`MotivationEvaluation`/`SelectedIntention`/`ActionPlan` |
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
| `agents.cognition.imagination` | DEBUG start/result; WARN truncation; ERROR ownership | owner/tick, policy version, evidence counts, candidate count, direction codes, fallback |
| `agents.cognition.motivation` | DEBUG appraisal complete | policy version, owner/tick, active-drive/goal counts, appraised-future count, risk-kind counts, uncertainty band |
| `agents.cognition.deliberation` | DEBUG filter/selection/planner | policy version, candidate counts per filter, direction code, tie-break code, command type |
| `agents.cognition.memory` | DEBUG `memory_recall_mapped`; ERROR ownership codes | owner/tick, policy versions, source/reconstruction/pending counts, provider/fallback flags |
| `agents.cognition.reconstruction` | DEBUG/INFO/WARN LLM reconstruct path | reconstruction/request IDs, tick, prompt/policy versions, counts, fallback flags |
| `simulation.agent_runtime` | DEBUG lifecycle/cognition/apply; INFO start/terminal/`runtime_reconsolidation_committed`; WARN/ERROR codes | run/agent/tick/invocation/status/counts |

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
| Capability flags | Run-level `V2CapabilityFlags` on `SimulationRunnerConfig` — not stage plugins; default off wires V1 policies; any flag on fails closed until a later plan owns it |
| Subjective finalization | `AgentRuntime` commits episodic/belief/relationship batches only |
| LLM lifecycle | Remains `api` / `llm.factory` composition — **not** encoded on runner fingerprints |

Off-limits from cognition: `WorldState`, `WorldEvent` stores, analysis reports, experiment collectors/truth specs.

Full seam map: [Architecture — V2 extension seams](architecture.md#v2-extension-seams-scaffolding).

## Deferred

- Production LLM-backed cognition stages (beyond optional reconstructive recall)
- Durable cognition-artifact persistence
- Concurrent agent execution
- General M4 analysis metrics over cognition receipts
- LLM provider lifecycle composition in API / `compose.yaml` (factory ports exist; deferred until a cognition consumer owns it)

## See Also

- [Architecture](architecture.md)
- [Memory reconstruction](memory-reconstruction.md)
- [Physical simulation](physical-simulation.md)
- [LLM providers](llm-providers.md)
- [Development](development.md)
