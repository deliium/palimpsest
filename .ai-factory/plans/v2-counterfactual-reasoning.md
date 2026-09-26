# Implementation Plan: Counterfactual Reasoning

Branch: main
Created: 2026-09-26
Improved: 2026-09-26 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds a default-off cognition mode and does not claim `advanced_social_inference`, `multi_hop_testimony_tracking`, or any new capability flag.

## Compatibility contract

This plan adds owner-scoped counterfactuals generated from the agent's subjective model. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. A counterfactual reads the owner's observation, remembered decisions captured from that owner's own effective command and ACTOR occurrences, retrieved memory, beliefs, relationships, goal board, self-model, emotional evaluation, and an optional read-only `CausalWorldModel`. It never receives `WorldState`, `PhysicalRules`, `WorldEvent`, an event repository, replay, analysis truth, or another agent's store. It does not rewind objective history and does not query what would have happened in a past tick.
2. No new capability flag. `CounterfactualMode` defaults to `DISABLED`. Off means no remembered-decision capture, no scenarios, no belief or relationship revision, no planning bonus, no identity request, no emotion driver, and no audit. `advanced_social_inference` and `multi_hop_testimony_tracking` stay unimplemented and still fail closed with `capability_unimplemented`. Owned flags stay owned and are not required for the default path.
3. V1 regression gate stays green under flags-off, tracing-off, and counterfactual-disabled. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment K is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only when the mode is on. Default write stays `runner-config-v4`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. `runner-config-v5` stays consolidation-only. `runner-config-v6` stays the reflection schema when counterfactual mode is `DISABLED`. `runner-config-v7` stays the prospective schema when counterfactual mode is `DISABLED`. Non-disabled counterfactual mode requires `runner-config-v8`, and v8 requires that mode on at least one agent. v8 is also a legal schema for consolidation, reflection, and prospective imagination: accept it wherever v7 is accepted for those modes. The v8 cognition key set is the v7 key set plus `counterfactual_mode`. Horizon and budgets are not runner JSON keys. Accepted v1–v7 documents omit `counterfactual_mode` and restore `DISABLED`.
5. No scripted emergence. Friend, enemy, leader, and culture labels stay forbidden. The experiment does not add a milestone script or a new physical rule. Do not add `EmotionKind.REGRET`. The closed `emotion.v1` catalog stays unchanged.
6. No LLM → world shortcuts. The provider may only rank scenario ids that the deterministic generator already created, through `StructuredOutput`. It never emits a probability, a new outcome atom, an `AgentCommand`, or a world mutation.
7. Experiments stay reproducible. Experiment K's two catalog arms share seed, scenario, and stochastic identity. Distinction proofs are unit tests. LLM tests use `FakeLLMProvider`. Analysis comparison runs after the run and is not fed back into cognition.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `CognitiveLoop` ordinal and do not bump the cognition-trace schema or Alembic. Tracing on versus off must not change `exact_trajectory_hash` when counterfactual mode is disabled.

## Goal

Agents sometimes ask, from records they already hold:

- What might have happened if I had not helped Bob?
- What if I had searched another location?
- What if I had trusted Alice?

Each consideration is a frozen `CounterfactualScenario` with a referenced remembered decision, one alternative action, a predicted alternative outcome, confidence, relevant goals, emotional impact, and provenance `IMAGINED_ALTERNATIVE`. The predicted outcome comes from the subjective transition rules cognition already uses. It is not a lookup in simulation history.

A kept scenario may affect beliefs, the next intention comparison, the self-model when `extended_self_model` is enabled, a relationship expectation, and a regret-like affect. None of those writes is an objective `WorldEvent`. The scenario is not a memory trace, not a semantic belief, not an `ImaginedFuture`, and not an observation.

## Design Decisions (locked)

- **Mode, not a flag.** Add lockstep enums `CounterfactualMode` in `src/simulation/runner_models.py` and `CognitionCounterfactualMode` in `src/agents/cognition/configuration.py`: `DISABLED`, `DETERMINISTIC`, `LLM_ASSISTED`. Default is `DISABLED`. This is not a `V2CapabilityFlags` slot.
- **Not a loop stage.** Do not add a `ComponentKind` or an ordinal. `CognitiveLoop.prepare` calls `consider_counterfactuals` after goal management and before emotional appraisal. The policy and `remembered_decisions` are keyword-only arguments, each defaulting so existing callers stay valid (`None` policy, empty decisions). `AgentRuntime` passes the store. `DISABLED` or a missing policy does not call it. Scenarios are not appended to `PossibleFutures`. They stay on a side channel, `last_counterfactual_scenarios()`, the same way `ImaginationEngine.last_prospective_audit()` avoids a proposal-schema bump.
- **Policy owns the knobs.** `CounterfactualPolicy` version `counterfactual-v1`. Fields: `max_decisions` (default 4), `min_confidence` (default 0.5), `direction_bonus` (default 0.2), `max_llm_calls` (default 1), `max_tokens` (default 256), `allow_provider` (default false). Construction fails closed when caps are not positive ints except `max_llm_calls` and `max_tokens` which may be zero, or when `min_confidence` or `direction_bonus` is outside `[0, 1]`, with stable reason codes. `_cognition_config_for` builds `default_counterfactual_policy(allow_provider=False)` for `DETERMINISTIC` and `allow_provider=True` only for `LLM_ASSISTED`. Tests may pass another policy on `CognitionLoopConfig`. Do not put these knobs in runner JSON.
- **Remembered decision, not a world event.** When the mode is not `DISABLED`, successful `finalize_pending` appends one `RememberedDecision` after `_apply_pending_side_effects` has committed this tick's traces. `command_kind` is `command.kind` (`"help"`, `"search"`, `"wait"`), not `type(command).__name__`. Outcome uses `classify_subjective_outcome` on owner ACTOR occurrences, with `place_changed=False` the same way reflection calls it. That function returns `PERCEIVED_CHANGE` or `NO_PROGRESS`. `place_id` comes from `Observation.self_body.location_id`. Counterpart: for `"help"`, `Help.target_id`; for `"wait"`, the other agent's id on a `talked`, `asked`, or `told` occurrence in that same observation. `memory_id` is the `DIRECT_OBSERVATION` trace written in this finalize whose concept equals `command.kind`, or absent when no such trace was written. Do not read `WorldEvent`. Do not append the reflection decision journal, and do not require `ReflectionMode`. `DISABLED` leaves the store `None`. Keep at most `max_decisions` most recent records. Round-trip the tuple on the in-process `AgentRuntimeCheckpoint` as an optional field defaulting to `None`. Do not add an Alembic revision and do not write the store into runner-result JSON.
- **One alternative, not a rollout.** `alternative_for` reads the stored decision, not the next tick's communication window:
  - `"help"` → `ActionDirection.WAIT`. The stored counterpart stays the referenced person. This is the "not helped Bob" case.
  - `"search"` → `ActionDirection.MOVE` toward the first current `observation.exits` entry, sorted by `destination_id`, whose destination differs from the remembered `place_id`. No such exit yields no scenario (`no_alternative`).
  - `"wait"` with a stored communication counterpart → `ActionDirection.COMMUNICATE` toward that agent. This is the "trusted Alice" case. Do not require the utterance to still be on the current observation.
  - Any other kind yields no scenario (`no_alternative`).
- **Sometimes.** Generate a scenario only when `outcome_code` is `NO_PROGRESS`. `PERCEIVED_CHANGE` skips with `not_salient`. A non-salient decision is not deleted. `UNKNOWN` stays in the value table for a record constructed with that code. `classify_subjective_outcome` does not return it: owner `success=True` is `PERCEIVED_CHANGE`, and `success=False` or no owner success is `NO_PROGRESS`.
- **Predicted outcome from the subjective model.** `remembered_value` is `-0.2` for `NO_PROGRESS`, `0` for `UNKNOWN`, and `+0.2` for `PERCEIVED_CHANGE`. Alternative value is `0` for `WAIT`, `0.3` for `MOVE` when an eligible exit exists, and `0.25` for `COMMUNICATE`. Confidence is `0.75` for help→wait, `0.6` for search→move, and `quantize(min(1, 0.5 + 0.5 * max(trust, 0)))` for wait→communicate, where `trust` is the owner's current directed `trust` toward that agent, or `0` when no profile exists. Quantize with the existing effect quantum `1e-6`. Difference above `0.05` is `CounterfactualAffectCode.REGRET`. Difference below `-0.05` is `RELIEF`. Otherwise `NEUTRAL`. Magnitude is `quantize(min(1, abs(alternative_value - remembered_value)))`. Relevant goals are the decision's `goal_ids`. `PredictedAlternativeOutcome` stores the alternative direction, alternative value, and magnitude. No free-text narrative.
- **Provenance.** `CounterfactualProvenanceKind` has one member, `IMAGINED_ALTERNATIVE`. The constructor requires that member. `ObservationSourceKind`, `MemorySourceKind`, or any other enum raises `TypeError` (`invalid_provenance`). Objective inputs are rejected by the same `_reject_objective` pattern as `src/agents/cognition/prospective.py`: module prefix `world.events`, `world.models`, or `world._`, plus split type names so the source file does not contain the contiguous strings `WorldEvent`, `WorldState`, or `PhysicalRules`. The raised message is `not a subjective input`. Scenario id is sha256 of owner, decision id, alternative direction, and target id. No RNG, wall clock, or Python `hash()`.
- **Beliefs.** When confidence is at least `min_confidence`, affect is not `NEUTRAL`, and `memory_id` is present, emit one `BeliefRevisionRequest`. Subject is `ClaimSubjectKind.CONCEPT` whose concept is the decision id. Predicate is exactly `counterfactual_alternative`. Value is `BeliefValueKind.TEXT` holding the alternative direction code. Evidence cites that existing memory id. Do not create a trace of the alternative. Missing `memory_id` skips the revision with `no_memory_evidence`. `extract_evidence_candidates` and `form_from_traces` must not emit this predicate. The belief is not an observed occurrence.
- **Future planning.** `_pairwise_compare` returns integer votes. Do not add `direction_bonus` to that integer. Pass a keyword-only bias map into `IntentionSelector.select` (default `None`), following `world_bias`. The highest-confidence non-neutral scenario marks futures whose direction equals its alternative with bias `direction_bonus` (`0.2`); other futures stay `0`. One `counterfactual_vote` is cast when one side's bias is greater, the same comparison `model_vote` already uses. Losing scenarios do not become futures. `CommandPlanner.plan` still returns exactly one closed command. `DISABLED` passes no bias and keeps today's winner.
- **Self-model.** Only when `CognitionIdentityMode.ENABLED` and affect is `REGRET` and `memory_id` is present, emit one self-belief `identity.weakness.own_choice.counterfactual_regret` with bool `true`, citing that memory id. The token is not in `_FORBIDDEN_IDENTITY_TOKENS`. Passthrough identity emits nothing. This is not a second belief store and not a person class.
- **Relationship expectations.** Emit one `RelationshipRevisionRequest` only for help→wait and wait→communicate, when confidence meets the floor, affect is not `NEUTRAL`, and `memory_id` is present. Resolve the stored counterpart with the entity-to-agent resolver the memory update hook already uses. Skip with `unresolved_counterpart` unless it resolves to an `AgentId` other than the owner. `RelationshipInteractionSignal.strength` stays in `[0, 1]` and equals confidence. Sign comes from the effect map, not from a negative strength. `"wait"` → communicate uses `RelationshipSignalKind.COUNTERFACTUAL_TRUST_UP` mapped to `(TRUST, 0.1)`. `"help"` → wait uses `RelationshipSignalKind.COUNTERFACTUAL_TRUST_DOWN` mapped to `(TRUST, -0.1)`. The resulting trust delta is `quantize(±0.1 * confidence)`. Search→move does not revise a relationship. Do not emit `HELP_GIVEN`, `COMMUNICATION`, or any other existing signal from a scenario. Evidence `memory_ref` is the remembered episode.
- **Regret-like affect.** The affect lives on the scenario and on a runtime-carried `CounterfactualState` (latest code and magnitude). It is not an `EmotionKind`. `EmotionalStateAppraiser.appraise` gains a keyword-only `counterfactual_scenarios` argument defaulting to empty. `PassthroughEmotionalStateAppraiser` ignores it. When `short_term_emotional_state` is enabled, driver `EmotionDriverCode.COUNTERFACTUAL` adds `quantize(0.25 * magnitude)` to `SADNESS` for `REGRET` or to `RELIEF` for `RELIEF`. Passthrough emotion leaves `AgentEmotionalState` unchanged. Do not add a catalog member.
- **LLM grounding.** `allow_provider=True` may call `LLMProvider.generate` once through schema `counterfactual.selection.v1` and prompt package `src/llm/prompts/counterfactual/v1/`, and only after deterministic scenarios exist. The call lives in `src/agents/cognition/counterfactual_selection.py`, which imports the `llm` facade. `counterfactual.py` does not import `llm`. Register that facade edge in `pyproject.toml` `ignore_imports` beside `agents.cognition.prospective_selection`. Payload fields are scenario ids, direction codes, and confidence bands. The schema returns a subset of those ids. Unknown ids, a probability field, a missing provider, transport error, or schema failure keep the deterministic set and set `fallback_used`. `allow_provider=False` never calls the provider.
- **Audits.** `CounterfactualAudit` is in-run and analysis-only. Fields: owner, tick, mode, scenario count, skipped count, regret count, relief count, neutral count, llm call count, `fallback_used`, highest direction code, confidence band, provenance code. No observation text, prompts, counterpart names, or outcome narratives. Append it on `AgentRuntime` and export it the same way as `export_prospective_audits`, onto `SimulationRunnerResult.counterfactual_audits` (in-memory, default empty, not written by runner-result serialization). `DISABLED` leaves the tuple empty.
- **Objective comparison.** `analysis/counterfactual_metrics.py` implements `counterfactual_reasoning@1`. It reads audit fields and committed event ids after the run. It reports the audit scenario count and that no scenario id equals a `WorldEvent` id. It does not import the generator. The generator must not import `analysis`.

## Non-Goals

- Owning `advanced_social_inference` or `multi_hop_testimony_tracking`
- Rewinding `WorldEngine`, replaying past ticks, or reading `PhysicalRules` to score an alternative
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, or adding an Alembic revision
- Adding `EmotionKind.REGRET` or a free-form affect label
- Storing a counterfactual as a `MemoryTrace`, an `ImaginedFuture`, an observation occurrence, or a `WorldEvent`
- Writing `HELP_GIVEN` or `COMMUNICATION` relationship signals for an alternative that did not happen
- Putting Experiment K on the V1 regression gate
- Feeding the analysis metric back into live planning

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition): add counterfactual scenario contracts`
- **Commit 2** (after tasks 4–6): `feat(cognition): apply subjective counterfactual conclusions`
- **Commit 3** (after tasks 7–9): `test(cognition): keep counterfactuals distinct from world events`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end.

## Tasks

### Phase 1: Contracts, Schema, and Remembered Decisions

- [x] Task 1: Add counterfactual contracts and provenance checks.
  - Deliverable: frozen types in `src/agents/cognition/counterfactual.py`, exported from `src/agents/cognition/__init__.py`.
  - Types: `CognitionCounterfactualMode` in `src/agents/cognition/configuration.py`; `CounterfactualProvenanceKind` (`IMAGINED_ALTERNATIVE` only); `CounterfactualAffectCode` (`REGRET`, `RELIEF`, `NEUTRAL`); `CounterfactualAffect`; `RememberedDecision`; `PredictedAlternativeOutcome`; `CounterfactualScenario` (decision ref, alternative direction, optional target id, predicted outcome, confidence, goal ids, emotional impact, provenance); `CounterfactualPolicy` (`counterfactual-v1`, defaults above); `CounterfactualState`. Constructors reject a foreign provenance enum, confidence or magnitude outside `[0, 1]`, and duplicate scenario ids with stable reason codes. Objective inputs use the `_reject_objective` pattern from Design Decisions and raise `TypeError` with message `not a subjective input`. The module must not import `world.events`, `world._*`, `simulation`, `analysis`, `llm`, or `llm.models`, and its source must not contain the contiguous strings `WorldEvent`, `WorldState`, or `PhysicalRules`.
  - Logging: logger `agents.cognition.counterfactual`. DEBUG on construction with owner id, policy version, `max_decisions`, and `min_confidence`. ERROR with field name and reason code on validation failure. No counterpart ids, goal text, or outcome prose at INFO.
  - Files: `src/agents/cognition/counterfactual.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_counterfactual_reasoning.py`.

- [x] Task 2: Wire the mode through runner config without new policy keys.
  - Deliverable: `CounterfactualMode` on `AgentCognitionSpec`, default `DISABLED`. Non-disabled mode requires `runner-config-v8`, and v8 requires that mode on at least one agent. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Widen consolidation, reflection, and prospective acceptance so v8 is legal wherever v7 is legal for those modes. Prospective non-disabled mode accepts v7 or v8 and still rejects v1–v6. v7 still requires prospective and still rejects a `counterfactual_mode` key. The v8 cognition key set in `src/simulation/runner_serialization.py` is the v7 key set plus `counterfactual_mode`. `_encode_cognition` writes that key only for v8. v1–v7 omit it and restore `DISABLED`.
  - Update `src/simulation/compatibility.py` so the runner-config entry accepts v8 and describes that trigger. Add `RUNNER_SCHEMA_VERSION_V8` to `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. In `simulation.runner._cognition_config_for`, map the enum and build `default_counterfactual_policy` only when the mode is not `DISABLED`. Store it on `CognitionLoopConfig`.
  - Update runner model and construction tests so an unowned capability flag still fails closed, a counterfactual-enabled config on v4 or v7 fails with `counterfactual_mode_requires_v8`, the same config on v8 constructs, and v8 plus non-disabled prospective and reflection constructs. v7 with prospective and counterfactual mode `DISABLED` still constructs.
  - Logging: DEBUG `cognition_config_counterfactual_mode mode=%s policy_version=%s` beside the existing mode logs. Logger `simulation.runner`. Do not log policy weights. ERROR on schema rejection with `reason_code=counterfactual_mode_requires_v8` or `v8_requires_counterfactual`.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_simulation_runner_construction.py`.

- [x] Task 3: Capture remembered decisions from the subjective observation.
  - Deliverable: after a successful finalize, and only when counterfactual mode is not `DISABLED`, append one `RememberedDecision` after `_apply_pending_side_effects`. `command_kind` is `command.kind`. For `"help"`, store `Help.target_id`. For `"wait"`, store the other agent's id from a `talked`, `asked`, or `told` occurrence on that same observation. Use `classify_subjective_outcome` with `place_changed=False`. Set `memory_id` from the `DIRECT_OBSERVATION` trace committed in this finalize whose concept equals `command.kind`. Do not import `world.events`. Do not write the reflection journal. Cap the store at `max_decisions`. `DISABLED` leaves it `None` and does not call the helper. Export and restore the tuple on `AgentRuntimeCheckpoint` with default `None`.
  - Logging: DEBUG line exactly `remembered_decision_appended owner_id=%s tick=%s command_kind=%s outcome_code=%s decision_count=%s`. The unit test asserts those five tokens on logger `simulation.agent_runtime`. No occurrence facts and no entity ids at INFO. WARNING `remembered_decision_skipped` with `reason_code=disabled` when the mode is off and a capture helper is invoked.
  - Depends on tasks 1 and 2.
  - Files: `src/agents/cognition/counterfactual.py`, `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `tests/unit/test_counterfactual_reasoning.py`.
<!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: Subjective Alternatives and Their Effects

- [x] Task 4: Generate scenarios from the subjective model.
  - Deliverable: `consider_counterfactuals(...)` in `src/agents/cognition/counterfactual.py`. For each salient remembered decision, apply `alternative_for` and the locked value, confidence, and affect formulas. `CognitiveLoop.prepare` takes keyword-only `remembered_decisions` defaulting to `()` and the policy from `CognitionLoopConfig`. `AgentRuntime` passes its store. Scenarios are exposed through `last_counterfactual_scenarios()` and are not a new proposal field. Thread the call through `src/agents/cognition/loop.py`, `contracts.py`, `defaults.py`, and `tests/fakes/cognition.py` before emotional appraisal without a new ordinal. Empty decisions or `DISABLED` return no scenarios and do not change futures. Objective inputs raise `TypeError` via `_reject_objective`. `"search"` chooses the first current `observation.exits` destination, sorted by `destination_id`, that differs from the remembered `place_id`. `"wait"` uses the counterpart stored at capture.
  - Required fixtures in `tests/unit/test_counterfactual_reasoning.py`:
    - Help Bob with the owner help occurrence `success=False`, so the outcome is `NO_PROGRESS`: alternative `WAIT`, affect `REGRET`, magnitude `0.2`, confidence `0.75`, provenance `IMAGINED_ALTERNATIVE`. `success=True` logs `not_salient` and produces no scenario.
    - Search at place A, owner search occurrence `success=False`, and a current exit to B: alternative `MOVE` toward B, affect `REGRET`, magnitude `0.5`, confidence `0.6`.
    - Wait while that same observation contained a message from Alice, trust `0.8`: outcome `NO_PROGRESS`, alternative `COMMUNICATE` toward the stored counterpart, confidence `0.9`, affect `REGRET`, magnitude `0.45`. The next observation does not need to repeat the utterance.
    - `PERCEIVED_CHANGE` produces no scenario and logs `not_salient`.
  - Logging: DEBUG per kept scenario with owner id, tick, scenario id, direction code, confidence band, affect code, and provenance code. The unit test asserts those tokens on `agents.cognition.counterfactual`. INFO once per call with kept count and skipped count. WARNING on skip with reason code `not_salient`, `no_alternative`, or `no_remembered_decision`. ERROR on owner mismatch. No names or prompts.
  - Depends on tasks 1, 2, and 3.
  - Files: `src/agents/cognition/counterfactual.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, `tests/fakes/cognition.py`, `tests/unit/test_counterfactual_reasoning.py`.

- [x] Task 5: Let conclusions affect beliefs, planning, self-model, relationships, and regret-like affect.
  - Deliverable: on finalize, apply the locked belief revision, identity revision, and relationship expectation only when their gates pass. `IntentionSelector.select` takes a keyword-only bias map defaulting to `None`. `_pairwise_compare` adds one `counterfactual_vote` when one future's bias `0.2` is greater than the other's, matching `model_vote`. `CommandPlanner` still receives one future. Add `EmotionDriverCode.COUNTERFACTUAL` and keyword-only `counterfactual_scenarios` on `EmotionalStateAppraiser.appraise`. `PassthroughEmotionalStateAppraiser` ignores that argument. The sadness or relief delta runs only when emotional state mode is `ENABLED`. Add one `COUNTERFACTUAL` row to the driver table in `tests/unit/test_emotional_state_engine.py`. Passthrough emotion and passthrough identity stay byte-identical to today. Do not add `EmotionKind.REGRET`. Scenarios are not inserted into `PossibleFutures`. A belief formed this way uses predicate `counterfactual_alternative` and cites the real memory id. Relationship revisions use only `COUNTERFACTUAL_TRUST_UP` or `COUNTERFACTUAL_TRUST_DOWN`, with strength equal to confidence and the counterpart resolved to another `AgentId`. An unresolved counterpart logs `unresolved_counterpart` and writes no signal.
  - Tests: with equal futures, the alternative direction wins by that one vote and the command count is 1; without scenarios the previous tie-break remains. A help→wait regret with a memory id writes that belief predicate and does not add a second trace whose concept is `wait`. Identity passthrough writes no self-belief; identity enabled writes `identity.weakness.own_choice.counterfactual_regret`. The relationship profile gains no `HELP_GIVEN` signal. Help→wait regret writes `COUNTERFACTUAL_TRUST_DOWN` and trust changes by `quantize(-0.1 * confidence)`. Emotion enabled increases `SADNESS` by `0.05` for magnitude `0.2`. Emotion passthrough leaves intensities unchanged.
  - Logging: DEBUG line exactly `counterfactual_effect owner_id=%s tick=%s effect_code=%s reason_code=%s` with effect code `belief`, `plan`, `identity`, `relationship`, or `affect`. The unit test asserts those tokens. Logger `agents.cognition.counterfactual` for belief, plan, and affect; `agents.cognition.identity` for the self-belief; `simulation.agent_runtime` for the relationship revision enqueue. No claim text.
  - Depends on tasks 2 and 4.
  - Files: `src/agents/cognition/counterfactual.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/emotion.py`, `src/agents/cognition/identity.py`, `src/agents/cognition/models.py`, `src/social/relationships.py`, `src/simulation/agent_runtime.py`, `tests/unit/test_counterfactual_reasoning.py`, `tests/unit/test_emotional_state_engine.py`, `tests/fakes/cognition.py`.

- [x] Task 6: Add optional structured ranking and the in-memory audit.
  - Deliverable: when `allow_provider` is true and both LLM budgets remain, the provider returns a subset of scenario ids and later effects use that subset. Failures set `fallback_used` and keep the deterministic set. Default policy never calls the provider. `CounterfactualAudit` is exported through `export_counterfactual_audits` onto `SimulationRunnerResult.counterfactual_audits` and omitted from runner-result serialization. `DISABLED` leaves the tuple empty.
  - Put the call in `src/agents/cognition/counterfactual_selection.py`. That module imports the `llm` facade and must not import `llm.models`. `counterfactual.py` does not contain `import llm`. Register `agents.cognition.counterfactual_selection -> llm` in `pyproject.toml` `ignore_imports`. Add schema `counterfactual.selection.v1` matching `src/llm/prompts/prospective/v1/`. Reject a probability, a new outcome, a command, or an unknown id.
  - Logging: DEBUG line exactly `counterfactual_llm_selection owner_id=%s tick=%s candidate_count=%s selected_count=%s token_count=%s fallback_used=%s`. The unit test asserts those six tokens on logger `agents.cognition.counterfactual_selection`, and asserts `import llm` is absent from `src/agents/cognition/counterfactual.py`. WARNING `counterfactual_llm_fallback reason_code=...` for `missing_provider`, `schema_rejected`, `foreign_id`, `transport`, `budget_llm`, or `budget_tokens`. DEBUG `counterfactual_audit` with owner id, tick, scenario count, regret count, and `fallback_used`. Do not log prompts or provider bodies. Loggers `simulation.agent_runtime` and `simulation.runner` cover append and export.
  - Depends on tasks 4 and 5.
  - Files: `src/agents/cognition/counterfactual_selection.py`, `src/llm/prompts/counterfactual/v1/`, `pyproject.toml`, `src/simulation/agent_runtime.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `tests/unit/test_counterfactual_reasoning.py`.
<!-- Commit checkpoint: tasks 4-6 -->

### Phase 3: Distinction Proofs, Experiment, and Docs

- [x] Task 7: Add Experiment K and the analysis-only metric.
  - Deliverable: two catalog arms share seed, scenario, and stochastic identity. `k-off` leaves counterfactual mode `DISABLED` and stays on `runner-config-v4`. `k-on` sets `DETERMINISTIC` and uses `runner-config-v8`. Register Experiment K beside Experiment J in `src/experiments/catalog.py`. Do not add it to `tests/unit/test_v1_regression_gate.py`.
  - Required catalog outcome: `k-off` produces an empty audit tuple; `k-on` produces at least one audit whose provenance code is `IMAGINED_ALTERNATIVE` after a salient remembered decision. The metric return value is not an argument to `CognitiveLoop`.
  - `counterfactual_reasoning@1` reads audits and committed event ids without importing the generator. It reports scenario count and a zero overlap with event ids. Register the spec the same way as `prospective_imagination@1`. Bump `METRIC_FAMILY_COUNT` from 21 to 22.
  - Logging: DEBUG `experiment_k_built` with experiment id and condition ids, logger `experiments.catalog`. DEBUG `counterfactual_metric` with arm id, scenario count, and event overlap count, logger `analysis.counterfactual_metrics`. Do not log scenario payloads at INFO.
  - Depends on tasks 2 and 6.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/analysis/counterfactual_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_counterfactual_reasoning.py`, `tests/unit/test_counterfactual_experiment.py`.

- [x] Task 8: Prove the five-way distinction and the objective-history boundary.
  - Deliverable: `tests/unit/test_counterfactual_distinction.py` builds one of each and shows they stay distinct:
    - memory: a `MemoryTrace` with `MemorySourceKind.DIRECT_OBSERVATION`
    - belief: a `SemanticBelief` whose predicate is not `counterfactual_alternative`, plus the counterfactual belief from task 5
    - future imagination: an `ImaginedFuture` from `ImaginationEngine` with the policy unset
    - counterfactual scenario: provenance `IMAGINED_ALTERNATIVE`
    - objective observation: an `Observation` occurrence, and a `WorldEvent` that the scenario is not an instance of
  - Required assertions:
    - The scenario's type is none of `MemoryTrace`, `SemanticBelief`, `ImaginedFuture`, `Observation`, or `WorldEvent`.
    - `PossibleFutures` from a disabled-policy `imagine` call does not contain the scenario id.
    - Recall over the source trace does not return the scenario id.
    - `MemorySourceKind` has no imagined member, and the scenario is not stored by `build_direct_observation_memory_trace`.
    - The counterfactual belief's predicate is `counterfactual_alternative` and its evidence memory id is the real episode. The trace concept remains the occurrence kind (`help`), not the alternative direction.
    - No committed event id equals a scenario id. `src/agents/cognition/counterfactual.py` source does not contain `WorldEvent`, `WorldState`, `PhysicalRules`, `search_base_probability`, or `time.monotonic`.
    - Constructing a scenario with a `WorldEvent` or a non-counterfactual provenance raises `TypeError`.
    - `EmotionKind` does not contain `REGRET`.
    - DEBUG records contain direction, affect, and provenance codes and do not contain prompt text.
  - Logging assertions use the logger names from tasks 1 and 4. No new production logger in the test module.
  - Depends on tasks 4, 5, and 7.
  - Files: `tests/unit/test_counterfactual_distinction.py`, `tests/architecture/test_cognitive_loop_isolation.py`.

- [x] Task 9: Document the mode, the five-way distinction, and Experiment K.
  - Deliverable: mandatory docs checkpoint through `/aif-docs`. Update `docs/cognition-runtime.md` with counterfactual mode default-off, the subjective alternative, the provenance constant, and the rule that scenarios are not futures, memories, or events. Update the Downstream V2 checklist sentence in `docs/architecture.md` so Experiment K (`counterfactual_reasoning@1`) stays off the V1 regression gate beside Experiment J. Extend `docs/experiments.md` so the catalog runs through K, and state that J and K stay off `tests/unit/test_v1_regression_gate.py`. Add a `counterfactual_reasoning@1` paragraph to `docs/analysis-metrics.md`: the family is present only when the audit exists, and assembly logs no scenario payload. Note that `runner-config-v8` is the counterfactual schema and that v8 may also carry consolidation, reflection, and prospective mode. Do not document an objective rewind.
  - Logging: none in docs. Implementation logs stay metadata-only as specified above.
  - Depends on tasks 4 and 7.
  - Files: `docs/cognition-runtime.md`, `docs/architecture.md`, `docs/experiments.md`, `docs/analysis-metrics.md`.
<!-- Commit checkpoint: tasks 7-9 -->
