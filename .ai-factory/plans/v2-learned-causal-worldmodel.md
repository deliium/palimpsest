# Implementation Plan: Agent-Owned Learned Causal WorldModel

Branch: main
Created: 2026-09-26
Improved: 2026-09-26 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan owns the still-unimplemented `predictive_world_model` flag and leaves `advanced_social_inference` and `multi_hop_testimony_tracking` unowned.

## Compatibility contract

This plan adds an owner-scoped causal world model that agents update from their own subjective episodes. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. The model reads the owner's `Observation`, reconstructed memories already retrieved for that owner, and optional emotional intensity already appraised for this tick. It never receives `WorldState`, `PhysicalRules`, `WorldEvent`, an event repository, replay, analysis truth, or another agent's store.
2. Own exactly one reserved flag. Add `predictive_world_model` to `_V2_OWNED_CAPABILITY_FLAGS`. Default remains off. Off is a passthrough: no hypotheses, no checkpoint field value, no command bias, no audit. `advanced_social_inference` and `multi_hop_testimony_tracking` stay unimplemented and still fail closed with `capability_unimplemented`.
3. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment I is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. No runner schema bump. `predictive_world_model` is already a key on `runner-config-v3` through `v6`. Do not add policy knobs to runner JSON. Do not add `runner-config-v7`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Thresholds live on `WorldModelPolicy`.
5. No scripted emergence. Example sentences in this plan are meanings of structured atoms. "Alice" is a counterpart id copied from a visible body or from the occurrence's other entity. "Forest" is `Observation.self_body.location_id`. There is no `ItemKind.TOOL` and no new harvest bonus in physical rules. Friend, enemy, leader, and culture labels stay forbidden.
6. No LLM → world shortcuts. The provider may only choose hypothesis ids from a deterministic candidate set through `StructuredOutput`. It never emits a probability, a new condition atom, an `AgentCommand`, or a world mutation.
7. Experiments stay reproducible. Experiment I arms share seed, scenario, and stochastic identity. LLM tests use `FakeLLMProvider`. Analysis comparison runs after the run and is not fed back into cognition.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `CognitiveLoop` ordinal and do not bump the cognition-trace schema or Alembic. Tracing on versus off must not change `exact_trajectory_hash` when the flag is off.

## Goal

Give each agent a private causal world model, used only when `V2CapabilityFlags.predictive_world_model` is enabled. The agent gradually forms hypotheses such as the ones below. Slots are copied from subjective records the agent already holds. They are not stored prose and not read from `PhysicalRules`.

| Meaning | Conditions copied from subjective records | Predicted outcome |
| --- | --- | --- |
| "Forest at night is dangerous." | `LOCATION` = `Observation.self_body.location_id`, `DAY_PHASE=night` | `DANGER` |
| "Asking Alice for food is likely to get help." | `COUNTERPART` from the ask's other entity, `ACTION=ask`, `CONCEPT` only when that ask has exactly one concept token | `HELP` |
| "Rain makes resource search harder." | `WEATHER=rain`, `ACTION=search` | `SEARCH_FAILURE` |
| "Holding this item improves harvesting." | `HELD_ITEM_KIND` when exactly one item is `HELD_BY_SELF`, `ACTION=search` | `SEARCH_SUCCESS` |

There is no harvest command. Search is the extraction action (`simulation.engine._resolve_search_effect`). A held item does not change objective search probability today (`search_base_probability + search_visibility_weight * visibility` in `WorldEngine`). A "tool helps" hypothesis is allowed to form anyway and to be false.

The model may be incomplete, incorrect, overgeneralized, and biased toward salient episodes. Confidence is a subjective support ratio. It is not an estimate of the engine's Bernoulli probability, and that probability is never passed into `agents.cognition`.

Each hypothesis stores:

- conditions
- predicted outcome
- confidence
- evidence
- counter-evidence
- provenance
- update history

Learning integrates with observations, reconstructed memories, reflection, imagination, and planning. Routine updates are arithmetic. An optional structured LLM call may only re-rank hypotheses the arithmetic step already created.

Experiments and unit tests compare subjective confidence with objective empirical frequencies after the fact. Tests show a false causal belief forming from a salient coincidence and remaining above the action threshold after mild counter-evidence.

## Design Decisions (locked)

- **Separate store.** Hypotheses are not `SemanticBelief` records and are not identity aspects. `memory.beliefs` stays subject-predicate claims. A `CausalHypothesis` is a conditional. Do not project hypotheses into belief revisions.
- **Flag, not a new mode enum on the runner.** `CognitionWorldModelMode` is `PASSTHROUGH` or `ENABLED`, derived in `simulation.runner._cognition_config_for` the same way as `extended_self_model`. `PASSTHROUGH` when the flag is off. `ENABLED` when it is on. `WorldModelPolicy.allow_provider` defaults to false even when the flag is on. Tests may pass a policy with `allow_provider=True` on `CognitionLoopConfig`. That boolean is not a runner JSON key.
- **Not a loop stage.** Do not add a `ComponentKind` or an ordinal in `_STAGE_ORDER`. From `CognitiveLoop.prepare`, after emotional appraisal and before `FUTURES`, call `update_world_model` only when mode is `ENABLED`. Pass the resulting `CausalWorldModel` into `imagine`, `evaluate`, `select`, and `plan`. When mode is `PASSTHROUGH`, those arguments stay `None` and the existing functions keep today's behavior. `DISABLED`/passthrough adds no boundary record.
- **Commit on successful finalize.** `prepare` computes the next model and uses it for this tick's command. `AgentRuntime.finalize_pending` stores it only after a successful `resolve_tick`, same durability rule as emotional state. Abort discards the tentative model so a retry recomputes it from the same observation. Flag off leaves the runtime field `None`.
- **Checkpoint.** Add optional `causal_world_model` on the in-memory `AgentRuntimeCheckpoint`, default `None`. Thread it through `export_runtime_checkpoint` and `restore_runtime_checkpoint`. Do not bump a checkpoint schema and do not add an Alembic revision. The checkpoint is not a versioned JSON document. Flag off leaves the field `None`.
- **Episode atoms.** One outcome episode carries one value per slot. Do not take the cartesian product of visible bodies, held items, and concepts. Build episodes only from this tick's owner-visible `Observation` and from `RetrievedMemoryContext` reconstructions whose provenance id is not already on this observation. Memory contributes missing episodes. It does not double-count the same provenance.
  - `LOCATION`: `Observation.self_body.location_id` when `self_body` is present. `Observation.locations` is not the observer's place.
  - `DAY_PHASE`: `Observation.day_phase` when present.
  - `WEATHER`: `Observation.weather_condition` when present.
  - `COUNTERPART`: the single `other_entity_id` on the outcome occurrence when that outcome is social (`HELP`, or harm aimed at the observer). Omit the slot when the occurrence has no other entity or when several counterparts would apply.
  - `HELD_ITEM_KIND`: `ObservedItem.kind` for placement `HELD_BY_SELF` only when exactly one such item is visible. Omit the slot when zero or several items are held.
  - `ACTION`: occurrence `kind` when the actor is the observer (`search`, `ask`, `move`, and the other command kind strings already on the occurrence). Do not import `world.events`.
  - `CONCEPT`: the single concept token already on the ask `ObservedCommunication` that belongs to this episode, or on a reconstructed memory, and only when that source has exactly one concept. Never parse utterance `text`. Omit the slot when the count is not one.
  - Absent and ambiguous slots are omitted. A hypothesis never contains a slot the agent did not perceive. An empty atom set is rejected. Read health as `ObservedSelf.health.value`. Do not import `world.models`.
- **Outcomes.** Closed `CausalOutcome` codes derived from owner-visible facts. `public_facts` exposes `kind`, `actor_id`, and `target_id` only, so item kind is never read from a `give` occurrence.
  - `DANGER`: an owner-targeted harm occurrence (`attack` with the observer as the other party, or `flee` with `success is False`), or `ObservedSelf.health.value` strictly below the last health float on the model cursor. The first tick has no prior health, so it skips the health-delta check. The cursor stores that float from `ObservedSelf` only. It does not read `AgentBody`.
  - `HELP`: an occurrence of `help` or `give` where the observer is the recipient. Food stays on the ask only when `CONCEPT` is copied from exactly one existing concept token.
  - `SEARCH_SUCCESS` / `SEARCH_FAILURE`: observer-actor occurrence `kind=search` with `success is True` / `False`.
  - Absence of harm does not create a hypothesis. When the tick's ambient atoms (`LOCATION`, `DAY_PHASE`, `WEATHER`) cover every atom of an existing `DANGER` hypothesis and no harm occurred, add counter weight `1` to that hypothesis. A matched `ask` with no `HELP` for that counterpart on the next model update adds counter weight `1` to the matching `HELP` hypothesis and does not create a new outcome. Opposite search outcomes add counter-mass to the other search hypothesis when one already exists. A tick with no search does not counter a search hypothesis. Both search hypotheses may remain.
- **Confidence.** Policy version `world-model-v1`. Let `prior = 1`. Matching support adds salience weight. Counter-evidence adds weight `1` (mild), never the harm salience. `confidence = support / (support + counter + prior)`, quantized with the cognition effect quantum `_EFFECT_QUANTUM = 1e-6` from `src/agents/cognition/models.py` into `[0, 1]`. Do not introduce a coarser quantum.
  - Base weight `1`.
  - Harm outcomes use weight `4` (`salience_harm`).
  - One salient harm episode yields `4 / 5 = 0.8`.
  - Two later mild counters yield `4 / 7`, which stays above default `action_threshold` `0.55`. Three mild counters fall to `0.5`, below the threshold. This is the persistence fixture.
  - Emotional intensity at or above the policy emotion threshold multiplies support weight by `2` only when an `AgentEmotionalState` is already present. Missing or passthrough emotion does not enable `short_term_emotional_state` and does not multiply.
- **Overgeneralization.** When an episode with two or more atoms adds support `w` to the full conjunction, each parent formed by deleting exactly one atom receives `generalize_rate * w` (`0.5`) for the same outcome. Do not recurse to grandparents in that episode. Parents can match more situations than the evidence covered and can cross `action_threshold` on their own.
- **Salience bias in prediction.** A hypothesis matches a contemplated situation when every one of its atoms is present. Among matches for an outcome, choose the highest confidence. Tie-break by more atoms, then hypothesis id. A very confident broad parent can beat a weakly supported specific child. This is intentional bias, not model averaging toward the truth.
- **Incompleteness.** Cap stored hypotheses at `max_hypotheses` (64). When full, drop the lowest confidence, then the oldest last-update tick, then the greater id. Cap evidence ids and update-history entries (`max_history` 32) by dropping the oldest.
- **Provenance and history.** Evidence and counter-evidence are bounded opaque id strings copied from observation provenance or `MemoryId` values already in the retrieval context. `CausalUpdateRecord` stores tick, hypothesis id, support delta, counter delta, and a closed reason (`SUPPORT`, `COUNTER`, `GENERALIZE`). No episode payload.
- **Imagination.** Match a future against the current `self_body.location_id`, the observation's phase and weather, `ImaginedFuture.direction`, and `ImaginedFuture.target_entity_id`. When a model is passed, matching `DANGER` raises `SubjectiveRiskKind.PHYSICAL_HARM` on `MOVE` toward that location and on `SEARCH` while the observer is already there. Matching `HELP` raises support for `ActionDirection.COMMUNICATE` toward that counterpart. Matching `SEARCH_FAILURE` lowers the `SEARCH` drive effect. Matching `SEARCH_SUCCESS` raises it. Magnitudes are the quantized hypothesis confidence. Existing `_DANGER_PREDICATES` behavior stays. A `None` model leaves `ImaginationEngine.imagine` unchanged.
- **Planning.** `MultiCriteriaIntentionSelector` applies the same matches as a bias after feasibility, only when a model is passed and a hypothesis confidence is at least `action_threshold`. Above-threshold `DANGER` down-ranks `MOVE` whose `target_entity_id` is the hypothesis location and `SEARCH` while `self_body.location_id` is already that location. Above-threshold `HELP` prefers `ActionDirection.COMMUNICATE` toward that counterpart. `_compile_command` keeps using `DeterministicSocialMessagePolicy`, which is what emits `Ask`. Do not add an `Ask` direction and do not construct `Ask` in the selector. Above-threshold `SEARCH_FAILURE` down-ranks `SEARCH`. Above-threshold `SEARCH_SUCCESS` prefers `SEARCH` when the matched hypothesis includes `HELD_ITEM_KIND`. Bias is quantized with `_EFFECT_QUANTUM` and does not override a critical veto. It must not run when the model argument is `None`.
- **Reflection.** Do not let reflection write hypotheses. Decision-record `prediction_error` grouping stays as it is. When reflection runs and the model is enabled, add a sibling goal candidate whose evidence ids are hypothesis ids whose latest update reason is `COUNTER`. Those ids are not `MemoryId`s, are not mixed into `SubjectiveDecisionRecord` evidence, and must not become `BeliefRevisionRequest`. Skip that sibling when reflection already emitted a `prediction_error` goal for the same pattern in this pass. If reflection is `DISABLED`, do not emit the sibling.
- **LLM grounding.** `allow_provider=True` calls `LLMProvider.generate` only through schema `world_model.selection.v1` and prompt package `llm/prompts/world_model/v1/`. The payload is hypothesis ids, outcome codes, atom counts, and quantized confidence bands already computed. The schema returns a subset of those ids. It has no probability field and no atom field. Unknown ids, missing provider, transport error, or schema failure keep the deterministic ranking and set `fallback_used`. `allow_provider=False` never calls the provider.
- **Audits.** `WorldModelAudit` is in-run and analysis-only. Fields: owner, tick, mode, hypothesis count, update count, max confidence, `fallback_used`, and a bounded `snapshots` tuple. Each snapshot is hypothesis id, canonical atom tokens, outcome, and quantized confidence. It does not include evidence ids or episode payloads. Attach it on `SimulationRunnerResult` the same way as `reflection_audits` (in-memory field, default empty, not written by runner-result serialization). Do not put audits on observations, prompts, or `runner-result-v2`.
- **Objective comparison.** `analysis/causal_world_model_metrics.py` implements `causal_world_model@1`. It reads those audit snapshots and committed events through the existing analysis event source. Match `LOCATION` with `WorldEvent.occurrence.origin_location_id`, the same join `analysis/objective_metrics.py` already uses. Derive day phase inside analysis from the run's physical rules. When an atom such as `WEATHER` is not on the committed event, set `empirical_status=unmatched` and do not guess a rate. Store `predicted_confidence`, `empirical_rate` when matched, and absolute error on the metric record. This module is the only place allowed to see both numbers. It must not import `update_world_model`, and the updater must not import `analysis`.
- **Fail closed.** Unknown outcome or slot strings, owner mismatches, non-finite weights, empty atom sets, and foreign memory ids abort with stable reason codes. A bad episode is dropped, not repaired from the world.

## Non-Goals

- Owning `advanced_social_inference` or `multi_hop_testimony_tracking`
- Exposing `search_base_probability`, `search_visibility_weight`, `weather_visibility`, weather transition probabilities, `attack_hit_probability`, or `flee_success_probability` to cognition
- Adding `ItemKind.TOOL`, a harvest command, or any change to `PhysicalRules` or `WorldEngine` search resolution
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, or adding an Alembic revision
- Writing causal hypotheses into `SemanticBelief` or enabling `extended_self_model`
- Letting LLM output become a stored confidence or a command
- Feeding empirical rates or analysis metrics back into live planning
- Putting Experiment I on the V1 regression gate
- Bumping `runner-config` or putting `WorldModelPolicy` knobs in runner JSON

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition): add subjective causal hypothesis updates`
- **Commit 2** (after tasks 4–6): `feat(cognition): let causal beliefs bias imagination and planning`
- **Commit 3** (after tasks 7–10): `test(experiments): compare subjective causal predictions with empirical outcomes`

## Tasks

### Phase 1: Contracts, Flag Ownership, and Deterministic Updates

- [x] Task 1: Add causal hypothesis contracts and `WorldModelPolicy`.
  - Deliverable: frozen types in `src/agents/cognition/world_model.py`, exported from `src/agents/cognition/__init__.py`.
  - Types: `CausalSlot` (`LOCATION`, `DAY_PHASE`, `WEATHER`, `COUNTERPART`, `HELD_ITEM_KIND`, `ACTION`, `CONCEPT`), `CausalAtom` (slot plus bounded copied value), `CausalOutcome` (`DANGER`, `HELP`, `SEARCH_SUCCESS`, `SEARCH_FAILURE`), `CausalUpdateReason` (`SUPPORT`, `COUNTER`, `GENERALIZE`), `CausalUpdateRecord`, `CausalHypothesis` (atoms, outcome, support, counter, confidence, evidence ids, counter-evidence ids, provenance source kind, update history), `CausalWorldModel` (owner id, hypotheses, last observed health, last tick), `WorldModelPolicy` (`world-model-v1`, prior `1`, salience harm `4`, emotion multiplier `2`, generalize rate `0.5`, action threshold `0.55`, caps above, `allow_provider=False`), `CognitionWorldModelMode` (`PASSTHROUGH`, `ENABLED`) next to the other cognition modes in `src/agents/cognition/configuration.py`.
  - Hypothesis id is sha256 of owner, canonical atom key, and outcome, following `belief_formation` id stability. No RNG, wall clock, or Python `hash()`.
  - Quantize confidence with `_EFFECT_QUANTUM = 1e-6` from `src/agents/cognition/models.py`. The persistence fixture is `4/5 = 0.8` after one harm episode and `4/7` after two mild counters, still above `0.55`.
  - Constructors reject empty atoms, duplicate slots, non-finite masses, owner mismatch, and unknown enums with stable reason codes.
  - Logging: logger `agents.cognition.world_model`. DEBUG on construction with owner id, policy version, and hypothesis count. ERROR with field name and reason code on validation failure. No atom values, evidence payloads, or health numbers at INFO.
  - Files: `src/agents/cognition/world_model.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_causal_world_model.py`.

- [x] Task 2: Own `predictive_world_model` and wire passthrough versus enabled.
  - Deliverable: the flag may be enabled without `capability_unimplemented`. Off stays V1-equivalent.
  - Add the name to `_V2_OWNED_CAPABILITY_FLAGS` in `src/simulation/runner_models.py`. Update the dataclass docstring and the owned-flag note in `src/simulation/compatibility.py` so `predictive_world_model` is listed beside `extended_self_model` and `short_term_emotional_state`. In `simulation.runner._cognition_config_for`, set `CognitionWorldModelMode.ENABLED` only when the flag is true, and build `default_world_model_policy(allow_provider=False)`.
  - Update `tests/unit/test_runner_models.py` so an enabled `predictive_world_model` is owned and `unimplemented_enabled_names()` is empty for that flag. Keep `advanced_social_inference` and `multi_hop_testimony_tracking` unimplemented. Update `tests/unit/test_simulation_runner_construction.py` so enabling this flag alone constructs, and enabling an unowned flag still fails closed.
  - Logging: existing runner DEBUG line `cognition_config_world_model_mode flag=%s mode=%s policy_version=%s` beside the identity and emotion mode logs. Logger `simulation.runner`. Do not log policy weights.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_simulation_runner_construction.py`.

- [x] Task 3: Implement the deterministic episode updater.
  - Deliverable: `update_world_model(model, episodes, policy) -> CausalWorldModel` plus `episodes_from_observation` and `episodes_from_reconstructions`.
  - Apply the confidence, salience, overgeneralization, counter-mass, and cap rules in Design Decisions. Recompute confidence from masses with `_EFFECT_QUANTUM`. Preserve update history order.
  - Bind one episode per outcome, one value per slot, using `self_body.location_id`. Omit `HELD_ITEM_KIND` unless exactly one item is held. Omit `CONCEPT` unless the source has exactly one concept token. `HELP` is `help` or `give` to the observer. Do not read an item kind from `public_facts`.
  - On a tick with no harm, add counter weight `1` to each existing `DANGER` hypothesis covered by the ambient atoms. Do not create a hypothesis for the absence. Opposite search outcomes counter each other. A tick with no search does not counter search hypotheses. Skip health-delta `DANGER` when the cursor has no prior health.
  - `episodes_from_observation` accepts `Observation`, owner id, and the previous model cursor. Its parameter type is `Observation`. Passing `WorldState` or `PhysicalRules` raises `TypeError`. It must not import `world.models`, `world.events`, `simulation`, or `analysis`. It may import `world.observations` and `world.values`.
  - Reconstructed episodes are produced by a function that accepts the retrieval context types cognition already has, and it skips provenance ids already used by observation episodes. The same one-value-per-slot rules apply.
  - Logging: DEBUG per applied update with owner id, tick, hypothesis id, outcome code, reason code, atom count, and quantized confidence. INFO once per call with episode count, created count, updated count, dropped count. WARNING when an episode is dropped, with reason code and no payload. ERROR on owner mismatch.
  - Depends on task 1.
  - Files: `src/agents/cognition/world_model.py`, `tests/unit/test_causal_world_model.py`.

### Phase 2: Runtime, Imagination, Planning, Memory, and Reflection

- [x] Task 4: Apply the update inside `prepare` and carry the model on the runtime.
  - Deliverable: enabled agents learn from the current observation before they imagine, and successful finalize persists the new model. Flag off does not change commands, boundary records, or checkpoints.
  - Add optional `causal_world_model` defaulting to `None` on `SubjectiveSnapshot`, `Perspective`, `CognitiveLoopProposal`, and `CognitiveLoopResult`. In `CognitiveLoop.prepare`, after emotional appraisal and before `FUTURES`, when mode is `ENABLED`, build episodes, update from the model on the loop input snapshot, and store the result on the proposal. Pass it as a keyword-only optional argument into imagine, motivation, intention, and planning. `PASSTHROUGH` skips the call and leaves the argument `None`.
  - Thread that optional argument through `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, and `tests/fakes/cognition.py` so existing stubs keep working. Run `uv run ruff check` on every file that gained the parameter.
  - `AgentRuntime` holds the model, copies it onto the subjective snapshot it already builds for emotion, exports and restores it, and commits it only after successful resolve. Abort leaves the prior model in place. The checkpoint field lives on the in-memory `AgentRuntimeCheckpoint` and defaults to `None`.
  - Logging: DEBUG `world_model_prepare` with owner id, tick, mode, hypothesis count. DEBUG `world_model_committed` / `world_model_commit_skipped` with owner id, tick, and `world_model_present`. No hypotheses at INFO. Logger `agents.cognition.loop` for the prepare hook and `simulation.agent_runtime` for commit, matching emotion.
  - Depends on tasks 2 and 3.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `src/simulation/subjective_state.py`, `tests/fakes/cognition.py`, `tests/unit/test_causal_world_model_runtime.py`.

- [x] Task 5: Bias imagination and intention selection with matched hypotheses.
  - Deliverable: a passed model at or above `action_threshold` changes subjective risk and direction preference. A `None` model preserves current scores and the selected command for the same fixture.
  - Extend `ImaginationEngine.imagine` and `MultiCriteriaIntentionSelector.select` with an optional model argument defaulting to `None`. Match using the current `self_body.location_id`, phase, weather, `ImaginedFuture.direction`, and `target_entity_id`. Apply the danger, help, search-failure, and search-success rules from Design Decisions using only hypothesis confidence. `HELP` biases `ActionDirection.COMMUNICATE`. `_compile_command` still calls `DeterministicSocialMessagePolicy` to emit `Ask`. Do not read visibility, weather factors, or search probabilities. Keep `_DANGER_PREDICATES` behavior.
  - The selector bias runs after feasibility and does not override a critical veto. Quantize with `_EFFECT_QUANTUM`.
  - Logging: DEBUG `world_model_imagination_bias` and `world_model_deliberation_bias` with owner id, tick, matched hypothesis id, outcome code, quantized confidence, and direction. DEBUG when the model is `None` with `status=skipped`. No observation bodies. Loggers `agents.cognition.imagination` and `agents.cognition.deliberation`.
  - Depends on task 4.
  - Files: `src/agents/cognition/imagination.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/motivation.py` only if drive effects must carry the search bias, `src/agents/cognition/loop.py`, `tests/unit/test_causal_world_model_runtime.py`.

- [ ] Task 6: Use reconstructed memories as extra episodes and let reflection cite counters.
  - Deliverable: a memory whose provenance is not already on the observation can create or support a hypothesis. Reflection's `prediction_error` goal intent may cite hypothesis ids that just received `COUNTER`. Reflection does not write the world model and does not emit belief revisions for those ids.
  - Call the reconstruction episode helper from the prepare update in task 4. In `src/agents/cognition/reflection.py`, add a sibling of `_goal_pattern_candidates` for hypothesis ids whose latest reason is `COUNTER`. Leave the `SubjectiveDecisionRecord` grouping unchanged. Drop the sibling when reflection mode is disabled, and skip it when this pass already emitted a decision-record `prediction_error` goal. Hypothesis ids must not enter `BeliefRevisionRequest`.
  - Logging: DEBUG `world_model_memory_episodes` with owner id, tick, memory episode count, skipped duplicate count. DEBUG `world_model_reflection_prediction_error` with owner id, tick, cited hypothesis count. No memory text. Logger `agents.cognition.world_model` and `agents.cognition.reflection`.
  - Depends on tasks 3 and 4.
  - Files: `src/agents/cognition/world_model.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/reflection.py`, `tests/unit/test_causal_world_model.py`, `tests/unit/test_causal_world_model_runtime.py`.

### Phase 3: Optional LLM Ranking, Experiment, Proofs, and Docs

- [ ] Task 7: Add optional structured LLM selection over existing hypotheses.
  - Deliverable: when `allow_provider` is true, the provider returns a subset of hypothesis ids and planning prefers those that also pass the deterministic match. Failures fall back to confidence order and set `fallback_used`. Default policy never calls the provider.
  - Add schema `world_model.selection.v1` under the existing LLM prompt/schema layout used by `llm/prompts/reflection/v1/`. Payload fields are ids, outcome codes, atom counts, and confidence bands. Reject responses that contain a probability, a new atom, or an unknown id.
  - Attach `WorldModelAudit` on `SimulationRunnerResult` for enabled agents only, following `reflection_audits` in `src/simulation/runner.py`. Include the bounded snapshot tuple (hypothesis id, canonical atom tokens, outcome, quantized confidence) and keep the field out of runner-result serialization.
  - Logging: DEBUG `world_model_llm_selection` with owner id, tick, candidate count, selected count, `fallback_used`. WARNING on fallback with reason code (`missing_provider`, `schema_rejected`, `foreign_id`, `transport`). Do not log prompts or raw provider bodies. Logger `agents.cognition.world_model`. LLM metadata stays on the existing `llm` logger.
  - Depends on tasks 4 and 5.
  - Files: `src/agents/cognition/world_model.py`, `llm/prompts/world_model/v1/`, `src/simulation/runner.py`, `tests/unit/test_causal_world_model.py`.

- [ ] Task 8: Add Experiment I and the post-hoc comparison metric.
  - Deliverable: two arms share seed, scenario, and stochastic identity. `i-disabled` leaves the flag off. `i-enabled` sets `predictive_world_model=True` and stays on `runner-config-v4`. The disabled arm's objective hash matches the same base config. The enabled arm may diverge after a hypothesis crosses threshold. The experiment is registered beside Experiment H in `src/experiments/catalog.py` and is not added to `tests/unit/test_v1_regression_gate.py`.
  - `causal_world_model@1` in `src/analysis/causal_world_model_metrics.py` joins audit snapshots to committed events and writes predicted confidence, empirical rate, absolute error, and match status. Match `LOCATION` through `WorldEvent.occurrence.origin_location_id`. Derive day phase in analysis from the run's physical rules. If an atom such as `WEATHER` is absent from the event, set `empirical_status=unmatched` and leave the rate empty. Register the spec the same way as `identity_dynamics@1` / `reflection@1` (`src/analysis/specifications.py`, `src/analysis/__init__.py`). Do not import `update_world_model`. The metric result is not an input to `CognitiveLoop`.
  - Logging: DEBUG `experiment_i_built` with experiment id and condition ids, logger `experiments.catalog`. DEBUG `causal_world_model_metric` with hypothesis count, matched count, unmatched count, logger `analysis.causal_world_model_metrics`. Do not log per-hypothesis empirical rates at INFO.
  - Depends on tasks 2 and 7.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/analysis/causal_world_model_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_causal_world_model_experiment.py`.

- [ ] Task 9: Prove false beliefs can form and persist, and prove objective probabilities stay hidden.
  - Deliverable: tests that fail if a salient false hypothesis is erased by mild counter-evidence, if overgeneral parents do not form, if missing weather invents a weather atom, or if cognition can see engine probabilities.
  - Required cases in `tests/unit/test_causal_world_model.py` and `tests/unit/test_causal_world_model_runtime.py`:
    - One harm episode at `self_body.location_id` during `NIGHT` yields confidence `0.8` for `LOCATION+DAY_PHASE → DANGER`. Two later night episodes with no harm leave confidence at `4/7`, which is above `0.55` under `_EFFECT_QUANTUM`. The hypothesis is still the one planning would match. Three mild counters fall below the threshold.
    - The one-atom parent `LOCATION → DANGER` exists after that episode and can match a daytime situation.
    - An observation with `weather_condition is None` produces no `WEATHER` atom.
    - A single search failure while `RAIN` and exactly one held `ItemKind.MATERIAL` produce `SEARCH_FAILURE` for that conjunction and a one-atom parent such as `HELD_ITEM_KIND → SEARCH_FAILURE` from `generalize_rate`. Assert the subjective confidence. In the analysis test, feed events whose empirical search success rate is high and assert the metric error is large while the hypothesis confidence is unchanged. The updater's return value must not include the empirical rate. A weather atom with no weather fact on the event is `unmatched`.
    - A help episode for a counterpart plus `ask` plus an existing concept token `food` yields `HELP` above threshold. A later unmatched ask is mild counter-evidence and does not clear the hypothesis in one step.
    - Flag off: the runtime model stays `None`, and the command sequence of a fixed fixture matches the passthrough loop.
    - `src/agents/cognition/world_model.py` source does not contain `search_base_probability`, `PhysicalRules`, or `WorldState`. Constructing episodes from a `PhysicalRules` instance raises `TypeError`.
  - Logging assertions: DEBUG records for the salient update contain outcome and reason codes and do not contain `search_base_probability`.
  - Depends on tasks 3, 5, and 8.
  - Files: `tests/unit/test_causal_world_model.py`, `tests/unit/test_causal_world_model_runtime.py`, `tests/unit/test_causal_world_model_experiment.py`, `tests/unit/test_v1_regression_gate.py` (assert Experiment I is absent only if the gate enumerates experiment ids).

- [ ] Task 10: Document the owned flag and the subjective/objective split.
  - Deliverable: readers can see that `predictive_world_model` is owned and default off, that agents do not receive engine probabilities, and that `causal_world_model@1` is analysis-only. Route the edits through `/aif-docs`.
  - Update the owned-flag lists and downstream checklist examples in `docs/architecture.md`, the capability table in `docs/cognition-runtime.md`, and the fail-closed paragraph in `docs/simulation-runner.md`. State Experiment I and `causal_world_model@1` stay off the V1 regression gate.
  - Logging: none in docs. Implementation touchpoints already log mode, update counts, fallback, and metric match counts as specified above.
  - Depends on tasks 2 and 8.
  - Files: `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/simulation-runner.md`.
