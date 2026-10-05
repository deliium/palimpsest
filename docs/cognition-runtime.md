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
→ optional offline consolidation when the effective command is Sleep
```

`Wait` does not consolidate. A trusted intervention that replaces `Sleep` skips consolidation; one that forces `Sleep` consolidates. The loop does not add a stage ordinal. Intents commit in `finalize_pending` only after the objective tick succeeds. `DISABLED` adds no consolidation calls and no new boundary records. Logs for this path carry mode, tick, counts, and reason codes only — never propositions, prompts, or trace text.

## Reflection

`ReflectionMode` on `AgentCognitionSpec` defaults to `DISABLED`. It is not a `V2CapabilityFlags` field and not a loop stage. When the mode is `DETERMINISTIC` or `LLM_ASSISTED`, `CognitiveLoop.complete` may call `ReflectionEngine` after the memory update and after any sleep consolidation. The command for this tick is already chosen. A reflection write can change a later command. It does not rewrite events already committed.

| Mode | Schema written | Provider |
| --- | --- | --- |
| `DISABLED` | `runner-config-v4` (no `reflection_mode` key) | never |
| `DETERMINISTIC` | `runner-config-v6` | never |
| `LLM_ASSISTED` | `runner-config-v6` | `reflection.selection.v1` only |

`runner-config-v5` stays consolidation-only and rejects `reflection_mode`. A non-disabled consolidation mode is legal on v5 or v6, so a v6 document may carry both. v6 is emitted only when some agent's reflection mode is not `DISABLED`. Thresholds stay on `ReflectionPolicy` (default interval and minimum gap `8`) and are not runner JSON keys.

A pass runs only after the minimum gap and when at least one enabled trigger is true. Inside the gap, true triggers are recorded as skipped. `DISABLED` does not evaluate triggers.

| Trigger | Fires when |
| --- | --- |
| `elapsed_ticks` | No prior pass and `tick + 1 >= interval`, or `tick - last_reflection_tick >= interval` |
| `significant_occurrences` | This observation's occurrence kinds match the policy allowlist often enough |
| `strong_emotion` | Owner emotional intensity meets the threshold (passthrough is false) |
| `repeated_failure` | Enough subjective `NO_PROGRESS` records, or owner-actor failures on this observation |
| `major_goal_completion` | A completed desire or long-term goal is not yet acknowledged |
| `belief_contradiction` | An owned belief's contradiction mass or count meets the threshold |
| `relationship_change` | A directed profile ordinal is newer than the ordinal already stored |

The first time a relationship pair is seen, finalize stores its ordinal and does not treat that profile as a change. Pattern codes are labels copied from cited subjective evidence. They are not invented predicates.

| Pattern | Writer |
| --- | --- |
| `repeated_action`, `repeated_help` | Belief revision (candidate when the subject and predicate are new) |
| `prediction_error`, `repeated_failure` | Goal intent only; decision-record ids are not memory ids |

Evidence ids must already be in the reflection context. A candidate whose ids are not is dropped. `LLM_ASSISTED` may return only ids from that candidate set. A foreign id, schema failure, or missing provider keeps the deterministic selection and sets `fallback_used`. Fatigue, sleep consolidation, and capability flags are unchanged.

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

## Extended self-model (V2 owned flag)

`V2CapabilityFlags.extended_self_model` (default **off**) owns history-derived, revisable self-beliefs. It does not add a runner JSON key, a persisted `SelfModel` row, or a cognition-trace stage. Default write stays `runner-config-v4`. Runner maps the flag to `CognitionIdentityMode`:

| Flag | Mode | Behavior |
| --- | --- | --- |
| off | `PASSTHROUGH` | V1 `project_self_model`; `SelfModel.identity` stays `None`; no identity influence |
| on | `ENABLED` | `IdentityState` from `identity.<aspect>.<provenance>.<token>` beliefs, including `CANDIDATE` |

Aspects are topics (`ability`, `weakness`, `recurring_behavior`, `inferred_value`, `social_role`, `relationship`, `commitment`, `perceived_status`, `reliability`, `risk_tolerance`, `competence`). They are not person classes. Forbidden tokens (`warrior`, `leader`, `trader`, `good_person`, `evil_person`, `friend`, `enemy`, and the compacted good/evil forms) fail at claim construction. Stored claims are owner-subject `BOOL` `true`. Rate and stability are derived from the revision chain. Identity does not read the decision journal or the reflection cursor, and it does not copy `MemoryRelation` predicates.

The same initial configuration plus different histories yields different self-models. Experiment H (`experiment-h-identity`, `identity-divergence-v1`) pairs `h-disabled` and `h-enabled` on `runner-config-v4` with a shared seed. It is not part of the V1 regression gate. Flags-off command sequence and `exact_trajectory_hash` match identity passthrough.

| Surface | Flag on |
| --- | --- |
| Goals | Keep active goals whose commands match a strong competence view; suspend non-critical medium-term goals that match a strong weakness |
| Planning | One pairwise vote from commitment, inferred value, or risk tolerance. The winning future still compiles to one command. The last feasible future stays. Critical physiological vetoes stay |
| Social reading | Relationship and reliability views scale trust inside 0.85–1.15, then clamp to `[0, 1]` |
| Reflection | When reflection is also enabled, dissonant memory ids are preferred. Identity does not write those beliefs again |
| Dissonance | A conflicting action still proceeds. The next revision adds contradicting evidence instead of replacing the `BOOL` claim |

Dissonance applies on the following tick. Resume stores the last applied tick and operation ids on an in-memory `identity_cursor`. It does not add a subjective table.

**Non-goals:** person classes, a second belief table, LLM-authored identity, and hard bans on conflicting actions.

**Logging:** metadata only. DEBUG events include `self_model_projected` (`identity_mode`, belief and stability-band counts), `identity_appraisal_start`, `identity_appraisal_complete`, `identity_pending`, `identity_dissonance`, `identity_dissonance_deferred`, `identity_goal_bias`, `identity_violation_cost`, `identity_social_scale`, `identity_reflection_cue`, `identity_applied`, `identity_apply_skipped_idempotent`, `identity_cursor_restored`, and `identity_cursor_absent`. Construction logs `identity_mode` and the flag bool. Do not log claim text, predicates, memory bodies, or command arguments.

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

Beliefs and theory-of-mind views are **trace-view projections** (not new `CognitiveLoop` stages). The scientific **emotional state** and **goals** trace views prefer live `EMOTIONAL_STATE` / `GOAL_MANAGEMENT` stage outputs (intensities + driver codes; horizon + status histograms) and fall back to drive/salience or snapshot/motivation only when those stages are absent/PASSTHROUGH-neutral. `advanced_social_inference` (default off) owns a private first-order model. The same flag adds a flat epistemic ledger on that mind: `EpistemicPolicy.max_depth` defaults to 2 and is hard-capped at 3. Rows are not nested child models. Off, the trace stays `unavailable` / `tom_not_implemented` and the ledger is not updated. On, a present `TheoryOfMind` projects a completed summary from hypothesis counts, aspect codes, subject ids, and max confidence. Epistemic rows stay off that summary. The model reads only the owner's observation, the owner's semantic beliefs, retrieved memories, relationship profiles, the cue cursor, and rows already stored on that owner's mind. It does not receive another agent's goals, drives, beliefs, emotion, or mind. Communication planning may judge a selected belief as new, already known, secret, uncertain, or contradictory. Secret is a judgment, not a stored attitude. `theory_of_mind@1` compares future-action snapshots with later occurrences after the run and is not fed back into the loop. Experiment L, Experiment M (`experiment-m-epistemic-asymmetry`), and that metric stay off the V1 regression gate. `multi_hop_testimony_tracking` is still unowned.

### Package split

| Package | Owns |
| --- | --- |
| `agents.cognition.trace` | Pure stage summaries / refs / projector — no `run_id`, no persistence |
| `simulation.cognition_trace` | Run-scoped envelopes, `CognitionTraceRepository` Protocol, Null / in-memory, soft-append after bind |
| `persistence` | Codec bytes only (`SqlAlchemyCognitionTraceRepository`); **must not** import `agents.cognition` |

Configure via top-level frozen `CognitionTraceSpec` on `SimulationRunnerConfig` (`runner-config-v4`). This is **not** a V2 capability flag. When disabled, the runner injects `NullCognitionTraceRepository` (V1 behavioral parity). When enabled, append happens once after successful cognition **bind** (soft-fail: WARN + drop; never alters `ActionSubmission`). Read-only research debugger HTTP lives under `/v1/simulations/{run_id}/debugger/…` (`subjective_debug`); see [Research causal debugger](research-causal-debugger.md).

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

Prospective imagination is default-off (`ProspectiveImaginationMode.DISABLED`) and is not a capability flag. Off keeps the one-step `imagination.v1` path. When a run uses `runner-config-v7`, each agent may roll a subjective chain — possible action, predicted subjective outcome, next action — using beliefs, the read-only causal world model, relationships, goals, the self-model, emotional state, and drives already derived from the current observation. Search stops on five hard budgets: max branches, max depth, max LLM calls, max tokens, and timeout. `CommandPlanner` still compiles exactly one closed command for the current tick. The optional provider may only rank transition ids the deterministic rollout already created.

Counterfactual reasoning is also default-off (`CounterfactualMode.DISABLED`) and is not a capability flag. Off captures no remembered decision and writes no scenario, belief, relationship revision, planning bias, identity request, emotion driver, or audit. When a run uses `runner-config-v8`, an agent may ask what might have followed a different action it already remembers. The alternative is a frozen `CounterfactualScenario` with provenance `IMAGINED_ALTERNATIVE`, predicted from the same subjective transition rules cognition already uses. A scenario is not an `ImaginedFuture`, not a memory trace, not a semantic belief, not an observation, and not a `WorldEvent`. The optional provider may only rank scenario ids the deterministic generator already created.

Communication strategy is default-off (`CommunicationStrategyMode.DISABLED`) and is not a capability flag. Off keeps the honest selector and writes no intent audit. When a run uses `runner-config-v9`, a speaker may choose one render for one claim. The world receives only the command. Omission is `Wait`.

| Mode | Schema written | Effect |
| --- | --- | --- |
| `DISABLED` | `runner-config-v4` (no `communication_strategy_mode` key) | today's command; `intent is None` |
| `DETERMINISTIC` | `runner-config-v9` | one closed strategy for that utterance; audit stays in memory |

`runner-config-v9` also accepts the v8 cognition keys. A non-disabled strategy is also accepted on `runner-config-v10`. Thresholds stay on `CommunicationStrategyPolicy` and are not runner JSON keys. Enabling this mode does not enable theory of mind, emotion, identity, prospective imagination, counterfactual reasoning, or reputation.

Reputation is default-off (`ReputationMode.DISABLED`) and is not a capability flag. Off leaves `snapshot.reputation` unset and adds no command. When a run uses `runner-config-v10`, each owner keeps a private dimensional ledger. A selected `Wait` may become one `Tell` whose text and predicates are dimension names. `Help`, `Attack`, `Give`, and `Move` stay selected. Colloquial readings exist only in `distributed_reputation@1`.

| Mode | Schema written | Effect |
| --- | --- | --- |
| `DISABLED` | `runner-config-v4` (no `reputation_mode` key) | no ledger and no reputation `Tell` |
| `DETERMINISTIC` | `runner-config-v10` | owner-scoped ledger; `Wait` may become one testimony `Tell` |

`runner-config-v11` accepts reputation and the earlier cognition modes. `DETERMINISTIC` reputation is therefore legal on v10 or v11.

Skill learning is default-off (`SkillLearningMode.DISABLED`) and is not a capability flag. Off does not change probabilities, fatigue, help gain, commands, memories, beliefs, or audits. When a run uses `runner-config-v11` or `runner-config-v12`, each enabled owner has a private `CompetenceSelfModel`. Believed level is `support / (support + counter + prior)`, quantized into `[0, 1]`. Skill channels write counter mass `0`. A teaching explain may store a positive counter. Objective growth is visible at the end of tick T. Belief moves on prepare of tick T+1, when that occurrence is on the owner's observation. Same-tick belief is unchanged. After one own successful untargeted search, support is `0.10` and believed level is `quantize(0.10 / 1.10)`. Pairwise selection adds `belief_action_weight * believed_level` as a float difference before the sign check. The maximum term is `0.25`, so a nonzero integer vote still wins. Untargeted search uses believed foraging and targeted search uses believed resource detection. That bias does not change the Bernoulli draw or an efficiency constant.

Teaching is default-off (`TeachingInteractionMode.DISABLED`) and requires skill learning on that same agent. Declarative advice is a separate store from believed competence and from the objective ledger. An explain reaches belief on the next prepare. With trust `1`, prior `1`, and a high band, support becomes `0.08` and believed level is `quantize(0.08 / 1.08)`. An inbound `request_instruction` adds `teaching_response_weight` (`0.25`) to the communicate side's float term. A nonzero integer vote still wins. The answering explain uses the owner's own band.

| Mode | Schema written | Effect |
| --- | --- | --- |
| `DISABLED` | `runner-config-v4` (no `skill_learning_mode` key) | today's formulas and no competence model |
| `DETERMINISTIC` | `runner-config-v11` | objective ledger plus owner-scoped competence beliefs |

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
| `SelfModel` | Deterministic projection of self-relevant semantic beliefs (no predefined traits/roles). `identity` is `None` unless `extended_self_model` is on |
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
| `agents.cognition.reflection` | DEBUG `reflection_triggers`, `reflection_decision_recorded`, `reflection_pending`, `reflection_applied`, `reflection_llm_start`, `reflection_llm_complete`; INFO `reflection_skipped`; ERROR `reflection_cursor_rejected`, `reflection_aborted`, `reflection_llm_rejected` (`foreign_id`, `schema_invalid`, `provider_error`) | mode, tick, trigger codes, counts, `fallback_used`, `reason_code` |
| `simulation.runner` | DEBUG objective goal apply; DEBUG `cognition_config_reflection_mode`; DEBUG `reflection_audit_export` | owner, tick, goal_id, from→to, reason_code; reflection mode, policy version, run id, audit count |

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
| Capability flags | Run-level `V2CapabilityFlags` on `SimulationRunnerConfig` — not stage plugins; default off wires V1 policies; **owned** flags (`advanced_social_inference`, `predictive_world_model`, `extended_self_model`, `short_term_emotional_state`) may enable; `multi_hop_testimony_tracking` still fails closed (`capability_unimplemented`) |
| Cognition execution trace | Top-level `CognitionTraceSpec` (`runner-config-v4`, default off) — not a capability flag; ports only; no HTTP yet |
| Subjective finalization | `AgentRuntime` commits episodic/belief/relationship batches only |
| LLM lifecycle | Remains `api` / `llm.factory` composition — **not** encoded on runner fingerprints |

Off-limits from cognition: `WorldState`, `WorldEvent` stores, analysis reports, experiment collectors/truth specs.

Full seam map: [Architecture — V2 extension seams](architecture.md#v2-extension-seams-scaffolding).

V3 generational cognition must plug in as constructor-injected stage slots / modes — not by renumbering fixed `CognitiveLoop` ordinals. Runtime pins: `prepare_parallel=False` until owned. When `generational_population` is **off**, roster stays bootstrap-fixed and per-tick ordinal = bootstrap registration order. When **on**, mid-run `admit_population_entry` may append registrations; runner rebuilds `RegistrationTranslator` for all live runtimes and constructs a full mid-run `_AgentBundle`; per-tick ordinal = **current registration order** including appends. Objective chronological age / stage on Observation is perception-only — this plan does not auto-form subjective age/maturity/social-role beliefs. See [Architecture — V3 extension seams](architecture.md#v3-extension-seams-scaffolding).

## Cognitive architecture variants

Named architecture ids (`reactive_baseline`, `v1_memory_agent`, `reconstructive_memory_agent`, `imagination_agent`, `reflection_agent`, `theory_of_mind_agent`, `full_v2_agent`) are **composition presets** registered in `agents.cognition.architectures`. They expand into ordinary `AgentCognitionSpec` modes and `V2CapabilityFlags` — they are **not** new capability-flag slots and **not** a runner-config schema bump for `architecture_id`.

### Stage slots

Stable slot → Protocol bindings (composition table, not mid-loop switches):

| Slot | Protocol | Notes |
| --- | --- | --- |
| `perception` | `PerceptionInterpreter` | Existing |
| `retrieval` | `MemoryRetriever` | Declaration key → `MemoryMode`; runner injects `ScopedMemoryRetriever` |
| `reconstruction` | `ReconstructionStage` | Cognition-facing wrapper around `memory.contracts.MemoryReconstructor` (do not shadow that name) |
| `beliefs` | `BeliefRevisionStage` | Memory-update slot (`SubjectiveRevisionHook`), not a new loop ordinal |
| `world_model` | `WorldModelStage` | Wraps `WorldModelPolicy` + mode |
| `reflection` | `ReflectionStage` | Wraps `ReflectionPolicy` / planning |
| `imagination` | `FutureImagination` | Existing |
| `motivation` | `MotivationEvaluator` | Existing |
| `theory_of_mind` | `TheoryOfMindStage` | Wraps `TheoryOfMindPolicy` + mode |
| `planning` | `Planner` (+ intention under planning compose) | Existing |

Missing capability ⇒ bind the slot’s passthrough / empty implementation. Forbidden in `CognitiveLoop`, `AgentRuntime`, or `SimulationRunner` tick paths: `if architecture_id == ...`.

### Expansion path (single authoritative path)

```text
ArchitectureDefinition
  → validate_architecture_compatibility(definition, ArchitectureModeSnapshot)
  → experiments.architectures.expand_architecture → SimulationRunnerConfig
  → SimulationRunner._cognition_config_for + _memory_retriever_for
  → build_cognitive_loop(CognitionLoopConfig)
```

`compose_loop_config_from_snapshot` stays consistent with `_cognition_config_for` flag→mode mapping. Retrieval/reconstruction keys are declaration tokens only; they do not construct `MemoryService`-bound retrievers inside cognition factories.

## Cognitive budgets (per-tick)

`CognitiveBudgetMode` / `CognitionBudgetMode` defaults to `DISABLED`. This is **not** a `V2CapabilityFlags` slot. When `DISABLED`, stage-local caps (`ProspectivePolicy`, memory `limit`, ToM store size, reflection intervals) behave as today with no cross-stage ledger.

When `ENFORCED`, `CognitiveLoop.prepare` constructs one `TickBudgetLedger` from `CognitiveBudgetPolicy` (`cognitive-budget-v1`) and degrades gracefully on exhaustion (refuse further LLM calls, truncate recall, stop expanding imagination / ToM targets, skip reflection) while still emitting exactly one closed `AgentCommand`. Cognition never calls `time.time` / `time.monotonic`; timeout uses an injected monotonic `clock` only (missing/non-callable disables the check).

Charge dimensions: LLM calls, tokens, imagination branches (prospective nodes beyond root + kept counterfactuals), planning depth (prospective/counterfactual only — not epistemic nesting), recalled memories, ToM targets, reflection cadence floor, timeout. Reason codes stay on `BudgetExhaustedReason` (distinct from `ProspectivePruneReason`).

`runner-config-v22` is emitted only when some agent's mode is `ENFORCED` (nine flat cognition keys: mode + eight numeric limits). Narratives-only configs stay on v21. Presets `low_cost_budget_limits()` / `high_cost_budget_limits()` live in cognition. In-run `CognitiveBudgetAudit` exports on `SimulationRunnerResult.cognitive_budget_audits` (not runner-result JSON). Tracing may project a final `BUDGET_SUMMARY` stage (`cognition-trace-stage-summary-v1` unchanged). Experiment AD and analysis `cognitive_budget@1` stay off the V1 regression gate.

### Preset → schema table

| architecture_id | memory | imagination | reflection | prospective | mortality | owned flags | schema |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `reactive_baseline` | reference | disabled | disabled | disabled | disabled | all off | v4 |
| `v1_memory_agent` | reconstructive | enabled | disabled | disabled | enabled | all off | v4 |
| `reconstructive_memory_agent` | reconstructive_v2 | enabled | disabled | disabled | enabled | all off | v4 |
| `imagination_agent` | reconstructive | enabled | disabled | deterministic | enabled | all off | v7 |
| `reflection_agent` | reconstructive | enabled | deterministic | disabled | enabled | all off | v6 |
| `theory_of_mind_agent` | reconstructive | enabled | disabled | disabled | enabled | `advanced_social_inference` | v4 |
| `full_v2_agent` | reconstructive_v2 | enabled | deterministic | disabled | enabled | all four owned | v6 |

`full_v2_agent` is cognitive-core only: social ledger modes stay `DISABLED`; prospective stays `DISABLED` so schema can be v6. `multi_hop_testimony_tracking` must not be required or enabled via any architecture (`architecture_unimplemented_flag` / `capability_unimplemented`).

### Digest and experiments

`architecture_definition_digest(definition)` is diagnostics-only (logs / `label_code` prefix). It must not become a runner JSON field. Experiment AC (`experiment-ac-cognitive-architectures`, conditions `ac-<architecture_id>`) shares world scenario, seed matrix, and stochastic identity across arms; it stays **off** the V1 regression gate. Experiment AD (`experiment-ad-cognitive-budgets`, conditions `ad-low-cost` / `ad-high-cost`) expands `full_v2_agent`, then overrides `prospective_mode=DETERMINISTIC`, `cognitive_budget_mode=ENFORCED`, nested limits from the locked presets, and `schema_version=runner-config-v22`; arms differ only by limits and stay **off** the V1 gate.

Validation reason codes: `architecture_missing_flag`, `architecture_forbidden_flag`, `architecture_mode_mismatch`, `architecture_slot_unbound`, `architecture_unknown_impl`, `architecture_unimplemented_flag`, `architecture_unknown`, `capability_unimplemented`.

## Deferred

- Production LLM-backed cognition stages (beyond optional reconstructive recall)
- Concurrent agent execution
- General M4 analysis metrics over cognition receipts
- LLM provider lifecycle composition in API / `compose.yaml` (factory ports exist; deferred until a cognition consumer owns it)
- Multi-hop testimony tracking (unowned capability flag)

## See Also

- [Architecture](architecture.md)
- [Memory reconstruction](memory-reconstruction.md)
- [Physical simulation](physical-simulation.md)
- [LLM providers](llm-providers.md)
- [Development](development.md)
