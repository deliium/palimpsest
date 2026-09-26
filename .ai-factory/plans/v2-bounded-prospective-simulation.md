# Implementation Plan: Bounded Multi-Step Prospective Imagination

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

This plan extends `ImaginationEngine` from one-step futures into a bounded subjective rollout. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. The rollout reads the owner's observation, situation, self-model, retrieved memory, goal board, emotional evaluation, drives already derived from that observation, relationships, beliefs, and an optional `CausalWorldModel`. It never receives `WorldState`, `PhysicalRules`, `WorldEvent`, an event repository, replay, analysis truth, or another agent's store.
2. No new capability flag. `ProspectiveImaginationMode` defaults to `DISABLED`. Off is the current `imagination.v1` path: same seeds, same one-step futures, `horizon_ticks=1`, no tree, no LLM call, no audit. `advanced_social_inference` and `multi_hop_testimony_tracking` stay unimplemented and still fail closed with `capability_unimplemented`. `predictive_world_model`, `extended_self_model`, and `short_term_emotional_state` stay owned and are not required for the shallow path.
3. V1 regression gate stays green under flags-off, tracing-off, and prospective-disabled. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment J is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only when the mode is on. Default write stays `runner-config-v4`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. `runner-config-v5` stays consolidation-only. `runner-config-v6` stays the reflection schema when prospective mode is `DISABLED`. Non-disabled prospective mode requires `runner-config-v7`, and v7 requires that mode on at least one agent. v7 is also a legal schema for consolidation and for reflection: accept it wherever v6 is accepted for reflection and wherever v5 or v6 is accepted for consolidation. The v7 cognition key set is the v6 key set plus `prospective_mode`. Horizon, branching factor, and budgets are not runner JSON keys. They live on `ProspectivePolicy`. Accepted v1–v6 documents omit `prospective_mode` and restore `DISABLED`.
5. No scripted emergence. Friend, enemy, leader, and culture labels stay forbidden. The experiment does not add a milestone script or a new physical rule.
6. No LLM → world shortcuts. The provider may only rank transition ids that the deterministic rollout already created, through `StructuredOutput`. It never emits a probability, a new situation atom, an `AgentCommand`, or a world mutation.
7. Experiments stay reproducible. Experiment J's two catalog arms share seed, scenario, and stochastic identity. The false-belief case is a unit test with an injected model, not a catalog checkpoint. LLM tests use `FakeLLMProvider`. Analysis comparison runs after the run and is not fed back into cognition.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `CognitiveLoop` ordinal and do not bump the cognition-trace schema or Alembic. Tracing on versus off must not change `exact_trajectory_hash` when prospective mode is disabled.

## Goal

Keep today's one-step imagination, and add an opt-in subjective rollout:

```text
current subjective situation
  -> possible action
  -> predicted subjective outcome
  -> next possible action
  -> predicted outcome
  -> ...
```

Each step may use beliefs, the subjective causal world model, relationships, goals, the self-model, emotional state, and drives. No step queries an objective future. Search stops on a configurable horizon and branching factor, and on hard budgets: max branches, max depth, max LLM calls, max tokens, and timeout. Low-value branches may be dropped approximately. Every kept transition stores its own confidence and uncertainty. Motivation and `CommandPlanner` still compile exactly one closed `AgentCommand` for the current tick.

Deeper search must be able to improve a place-then-search goal, and the same depth must be able to carry a false danger hypothesis forward so the agent abandons that goal. The hypothesis is not corrected during imagination.

## Design Decisions (locked)

- **Mode, not a flag.** Add lockstep enums `ProspectiveImaginationMode` in `src/simulation/runner_models.py` and `CognitionProspectiveMode` in `src/agents/cognition/configuration.py`: `DISABLED`, `DETERMINISTIC`, `LLM_ASSISTED`. Default is `DISABLED`. This is not a `V2CapabilityFlags` slot. `CognitionImaginationMode` stays `DISABLED` / `ENABLED` and Experiment B is unchanged.
- **Policy owns the knobs.** `ProspectivePolicy` version `prospective-v1`. Fields: `horizon` (default 3), `branching_factor` (default 3), `max_branches` (default 16), `max_depth` (default 3), `max_llm_calls` (default 1), `max_tokens` (default 256), `timeout_seconds` (default 0.05), `allow_provider` (default false), and an optional injected clock. Effective depth is `min(horizon, max_depth)`. Construction fails closed when `horizon` exceeds `max_depth` (`horizon_exceeds_max_depth`), when any cap is not a positive int except `max_llm_calls` and `max_tokens` which may be zero, or when `timeout_seconds` is not finite and `>= 0`. `DISABLED` does not consult the policy. `None` policy means the V1 path.
- **Not runner JSON.** `_cognition_config_for` builds `default_prospective_policy(allow_provider=False)` for `DETERMINISTIC` and `allow_provider=True` only for `LLM_ASSISTED`. Tests may pass another policy on `CognitionLoopConfig`. Do not add `runner-config` keys for horizon or budgets.
- **Not a loop stage.** Do not add a `ComponentKind` or an ordinal. `CognitiveLoop.prepare` still calls `imagine` at `FUTURES`. Pass the policy as a keyword-only optional argument. `DISABLED` / `None` leaves the current function body as the only path.
- **Subjective situation only.** A rollout node copies slots the agent already holds. It does not project the next world tick.
  - **Beliefs.** `_collect_evidence` runs once at the root. Child nodes reuse that evidence. Predicted outcomes do not create or revise `SemanticBelief` records.
  - **Causal world model.** Read-only `match_hypothesis`. A `MOVE` node copies the visible exit `destination_id` into the predicted `LOCATION` atom, the same atom `contemplated_situation_atoms` already builds. Day phase and weather stay the root observation values. Do not call `update_world_model`. A `None` model leaves matches empty. Never read `search_base_probability`, `PhysicalRules`, or `WorldState`.
  - **Relationships.** Reuse the owned profiles in `_direction_social_effects`. Do not emit relationship revisions.
  - **Goals.** `_direction_goal_effects` is not edited. Prospective nodes, including the root, apply one chain rule: an active `GATHER_INFORMATION` goal scores `SEARCH` (`+0.4`, confidence `0.7`) only when that node's predicted location already equals an active `REACH_PLACE.place_id` on the same board. Until then that information goal scores `0`. `REACH_PLACE` still scores `MOVE` toward that `place_id` at `+0.3` while the predicted location is not yet there.
  - **Affordances.** Every node calls `_affordances` on the root observation. The only carried situation slot is predicted location. It starts at `Observation.self_body.location_id` and becomes the chosen visible exit id after `MOVE`. Do not build a new `Observation`.
  - **Self-model.** Read-only. Copy it onto the root evidence path. Do not call identity update and do not add a new identity penalty table.
  - **Emotional state.** Call existing `scale_subjective_risks` at each node with the same `EmotionalStateEvaluation`, before the value formula. The locked fixture passes no evaluation, so the risk products below stay unchanged. Do not add an emotion transition table and do not write emotional state.
  - **Drives.** `_build_future` still supplies drive effects from the root observation. Do not read `AgentBody`. Drive deltas are not part of path value.
- **Transition record.** Frozen `ImaginedTransition`: id, parent id, depth, direction, target id, confidence, `SubjectiveUncertainty`, quantized value, prune reason or none. Id is sha256 of owner, parent id, depth, direction, and target. No RNG, wall clock, or Python `hash()`.
- **Confidence and uncertainty per step.** Quantize with `_EFFECT_QUANTUM = 1e-6` from `src/agents/cognition/models.py`. Let one-step confidence be the value `_build_future` already computes. `confidence' = quantize(parent_confidence * one_step_confidence)` with root parent confidence `1`. Epistemic uses only this formula: `quantize(min(1, parent_epistemic + 0.15))`, plus `0.25` when no hypothesis matches that node. Do not also add the epistemic value from `_direction_risks`. Aleatory: `quantize(min(1, max(parent_aleatory, one_step_aleatory)))`. Band: `HIGH` if epistemic `>= 0.66`, else `MEDIUM` if epistemic `>= 0.33`, else `LOW`. Both components stay in `[0, 1]`.
- **Value and approximate prune.** `SubjectiveRisk` has `severity`, `likelihood`, and `confidence`. `step_value = quantize(sum(progress_delta) - sum(severity * likelihood * confidence))`. Path value is the sum of step values. With belief danger and safety at `0` and no emotional evaluation, the root `MOVE` risk product is `0.024` (`UNKNOWN` `0.2 * 0.3 * 0.4`) and the root `SEARCH` risk product is `0.041` (`UNKNOWN` `0.25 * 0.35 * 0.4` plus `RESOURCE_LOSS` `0.1 * 0.15 * 0.4`). `WAIT` scores `0`. At each node, generate the root affordance seeds, score them, and keep the top `branching_factor`. Dropped siblings get prune reason `LOW_VALUE`. Tie-break by `ActionDirection` declaration order, then target id, then seed id. This is a discard, not an exhaustive backup of the dropped branch.
- **Hard budgets.** Stop expanding when expanded nodes would exceed `max_branches` (`BUDGET_BRANCHES`), depth would exceed effective depth (`BUDGET_DEPTH`), the next LLM call would exceed `max_llm_calls` (`BUDGET_LLM`) or `max_tokens` (`BUDGET_TOKENS`), or the injected clock has advanced by at least `timeout_seconds` (`BUDGET_TIMEOUT`). A partial tree is still valid. Cognition never calls `time.time` or `time.monotonic`. The loop config may inject a monotonic callable; unit tests inject a scripted clock. A missing clock disables the timeout check so results stay deterministic.
- **Collapse to one current action.** The winning path is highest path value, then higher path confidence, then shorter depth, then smaller future id. `DETERMINISTIC` and `LLM_ASSISTED` imagine returns exactly one `ImaginedFuture`: that path's first step. Copy the path's positive goal effects onto it, including a later `GATHER_INFORMATION` effect of `+0.4` at confidence `0.7`. Set `horizon_ticks` to the path depth, confidence to the path confidence, and uncertainty to the terminal transition's uncertainty. `MultiCriteriaIntentionSelector` must not see the losing siblings. `CommandPlanner.plan` stays the only compiler and still returns exactly one closed command (`Wait` on fallback). If every branch is pruned, emit the existing single wait future. With the information goal as the board focus, one visible exit `D`, no water, no food, no fatigue, one search affordance, and no emotional evaluation: V1 (`None` policy) keeps `Search`; depth at least 2 with no danger hypothesis keeps `Move` toward `D` at path value `0.3 - 0.024 + 0.4 - 0.041`; the same depth with `LOCATION=D` `DANGER` at confidence `0.8` makes the move-then-search path negative after `_raise_physical_harm(0.8)` and the winner is `Wait`.
- **LLM grounding.** `allow_provider=True` may call `LLMProvider.generate` once through schema `prospective.selection.v1` and prompt package `src/llm/prompts/prospective/v1/`, and only after deterministic scores exist. The call lives in `src/agents/cognition/prospective_selection.py`, which imports the `llm` facade. `prospective.py` does not import `llm`. Register that facade edge in `pyproject.toml` `ignore_imports` beside `agents.cognition.world_model_selection`. Payload fields are transition ids, depth, direction codes, and confidence bands. The schema returns a subset of those ids. Unknown ids, a probability field, a missing provider, transport error, or schema failure keep the deterministic ranking and set `fallback_used`. The call counts against `max_llm_calls` and adds `max_output_tokens` against `max_tokens`. `allow_provider=False` never calls the provider.
- **Audits.** `ProspectiveAudit` is in-run and analysis-only. Fields: owner, tick, mode, depth reached, expanded count, pruned count, llm call count, token count, timeout hit, `fallback_used`, first-step direction code, confidence band, uncertainty band. No observation text, prompts, or hypothesis payloads. Append it on `AgentRuntime` and export it the same way as `export_world_model_audits`, onto `SimulationRunnerResult.prospective_audits` (in-memory, default empty, not written by runner-result serialization). `DISABLED` leaves the tuple empty.
- **Objective comparison.** `analysis/prospective_imagination_metrics.py` implements `prospective_imagination@1`. It reads audit fields and committed events after the run. It may report whether the first committed command kind matches the audit direction, and an empirical harm count at a place id copied from events. It reads those fields without importing the rollout. The rollout must not import `analysis`.

## Non-Goals

- Owning `advanced_social_inference` or `multi_hop_testimony_tracking`
- Changing V1 `_direction_goal_effects`, Experiment B, or the one-step path when the policy is `None` or `DISABLED`
- Querying `WorldEngine`, `PhysicalRules`, or objective outcome rates from cognition
- Emitting more than one `AgentCommand` for the tick
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, or adding an Alembic revision
- Writing beliefs, hypotheses, relationships, emotion, or the self-model from imagined transitions
- Putting `ProspectivePolicy` knobs in runner JSON
- Putting Experiment J on the V1 regression gate
- Feeding the analysis metric back into live planning

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition): add bounded subjective prospective rollout`
- **Commit 2** (after tasks 4–6): `feat(cognition): collapse prospective search to one current command`
- **Commit 3** (after tasks 7–9): `test(experiments): show deeper plans help and amplify false beliefs`

## Tasks

### Phase 1: Contracts, Schema, and Deterministic Rollout

- [x] Task 1: Add prospective contracts and budget checks.
  - Deliverable: frozen types in `src/agents/cognition/prospective.py`, exported from `src/agents/cognition/__init__.py`.
  - Types: `CognitionProspectiveMode` (`DISABLED`, `DETERMINISTIC`, `LLM_ASSISTED`) in `src/agents/cognition/configuration.py`; `ProspectivePruneReason` (`LOW_VALUE`, `BUDGET_BRANCHES`, `BUDGET_DEPTH`, `BUDGET_LLM`, `BUDGET_TOKENS`, `BUDGET_TIMEOUT`); `ProspectivePolicy` (`prospective-v1`, defaults above, optional clock); `ImaginedTransition`; `ProspectiveRollout` (owner id, root situation atom count, transitions, budgets exhausted). Constructors reject `horizon > max_depth`, non-finite timeout, duplicate transition ids, and confidence or uncertainty outside `[0, 1]` with stable reason codes.
  - Logging: logger `agents.cognition.prospective`. DEBUG on construction with owner id, policy version, horizon, branching factor, and the five budget caps. ERROR with field name and reason code on validation failure. No atom values or goal text at INFO.
  - Files: `src/agents/cognition/prospective.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_prospective_imagination.py`.

- [x] Task 2: Wire the mode through runner config without new policy keys.
  - Deliverable: `ProspectiveImaginationMode` on `AgentCognitionSpec`, default `DISABLED`. Non-disabled mode requires `runner-config-v7`, and v7 requires that mode on at least one agent. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. v7 is accepted wherever v6 is accepted for reflection and wherever v5 or v6 is accepted for consolidation, so an agent that both reflects and plans prospectively validates. The v7 cognition key set in `src/simulation/runner_serialization.py` is the v6 key set plus `prospective_mode`. `_encode_cognition` writes that key only for v7. v1–v6 omit it and restore `DISABLED`. Horizon and budgets are absent from every key set.
  - Update `src/simulation/compatibility.py` so the runner-config entry accepts v7 and describes that trigger. Add `RUNNER_SCHEMA_VERSION_V7` to `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. In `simulation.runner._cognition_config_for`, map the enum and build `default_prospective_policy` only when the mode is not `DISABLED`. Store it on `CognitionLoopConfig` beside `world_model_policy`.
  - Update runner model and construction tests so an unowned capability flag still fails closed, a prospective-enabled config on v4 fails with `prospective_mode_requires_v7`, the same config on v7 constructs, and v7 plus a non-disabled `reflection_mode` constructs. v6 with reflection and prospective mode `DISABLED` still constructs.
  - Logging: DEBUG `cognition_config_prospective_mode mode=%s policy_version=%s` beside the existing mode logs. Logger `simulation.runner`. Do not log policy weights. ERROR on schema rejection with `reason_code=prospective_mode_requires_v7` or `v7_requires_prospective`.
  - Depends on task 1.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_simulation_runner_construction.py`.

- [x] Task 3: Implement the deterministic subjective rollout.
  - Deliverable: `rollout_prospective(...)` in `src/agents/cognition/prospective.py`. Given the same inputs `imagine` already has, plus a `ProspectivePolicy`, it expands action, predicted subjective outcome, next action, and so on, up to the effective depth and branching factor, then stops on the hard budgets.
  - Use `_affordances`, `_build_future`, `_collect_evidence`, `scale_subjective_risks`, and `match_hypothesis` as specified in Design Decisions. Call `_affordances` on the root observation at every node. Carry only predicted location. Apply the chain rule inside this function, including the root: `GATHER_INFORMATION` is `0` until predicted location equals `REACH_PLACE.place_id`, then `SEARCH` scores `+0.4`. `step_value` subtracts `severity * likelihood * confidence`. Prospective epistemic uses the locked formula and does not add `_direction_risks` epistemic. Passing `WorldState` or `PhysicalRules` raises `TypeError`. The module must not import `llm`, `world.models`, `world.events`, `simulation`, `analysis`, or `world._*`.
  - A scripted clock that jumps past `timeout_seconds` stops with `BUDGET_TIMEOUT` and returns the partial rollout. `max_branches=1` expands only the root. Effective depth `1` stores only first-step transitions. On the locked fixture with no danger hypothesis and depth at least 2, the winning path value is `0.3 - 0.024 + 0.4 - 0.041` and the first step is `MOVE` toward `D`.
  - Logging: DEBUG per kept transition with owner id, tick, transition id, depth, direction code, confidence band, uncertainty band, and prune reason when present. INFO once per rollout with expanded count, pruned count, and depth reached. WARNING on budget stop with reason code and no payload. ERROR on owner mismatch.
  - Depends on task 1.
  - Files: `src/agents/cognition/prospective.py`, `src/agents/cognition/imagination.py` only for shared private helpers that must stay behavior-compatible, `tests/unit/test_prospective_imagination.py`.

### Phase 2: One Current Command, Optional Ranking, and Audit

- [x] Task 4: Collapse the rollout to one future and one current command.
  - Deliverable: `ImaginationEngine.imagine` accepts keyword-only `prospective_policy: ProspectivePolicy | None = None`. `None` or `DISABLED` returns today's futures for a fixed fixture, including `horizon_ticks=1`. `DETERMINISTIC` returns exactly one `ImaginedFuture`: the winning first step from task 3. Copy that path's positive goal effects onto it, including a later `GATHER_INFORMATION` effect of `+0.4` at confidence `0.7`. Losing siblings are not returned, so `MultiCriteriaIntentionSelector` cannot pick them. The existing emotion scale and world-model bias still run on that single future.
  - `CognitiveLoop` reads the policy from `CognitionLoopConfig` the same way it reads `world_model_policy`. Thread the optional argument through `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/loop.py`, and `tests/fakes/cognition.py`. Do not add a stage ordinal. `CommandPlanner.plan` is unchanged and still returns one `ActionPlan.command` whose type is in the current closed allowlist.
  - Fixture: one visible exit `D`, no water, no food, no fatigue, one search affordance, no emotional evaluation, `REACH_PLACE` for `D`, and the focus set to the `GATHER_INFORMATION` goal. V1 keeps `Search` through `_prefer_goal_focus_support`. Depth at least 2 returns `Move` toward `D`.
  - Logging: DEBUG `prospective_collapse` with owner id, tick, winning direction, horizon, and confidence band. DEBUG `prospective_skipped` with `status=skipped` when the policy is absent. Logger `agents.cognition.imagination`. No observation bodies.
  - Depends on tasks 2 and 3.
  - Files: `src/agents/cognition/imagination.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, `tests/fakes/cognition.py`, `tests/unit/test_prospective_imagination.py`, `tests/unit/test_imagination_engine.py`.

- [x] Task 5: Add optional structured LLM ranking inside the budgets.
  - Deliverable: when `allow_provider` is true and both LLM budgets remain, the provider returns a subset of transition ids and collapse prefers those ids among the deterministic survivors. The single collapsed future still follows that ranking. Failures set `fallback_used` and keep deterministic order. Default policy never calls the provider. `max_llm_calls=0` or a token budget that cannot fit `max_output_tokens` skips the call with `BUDGET_LLM` or `BUDGET_TOKENS`.
  - Put the call in `src/agents/cognition/prospective_selection.py`, which imports the `llm` facade. `prospective.py` does not import `llm`. Register `agents.cognition.prospective_selection -> llm` in `pyproject.toml` `ignore_imports` beside `agents.cognition.world_model_selection`. Add schema `prospective.selection.v1` at `src/llm/prompts/prospective/v1/`, matching `src/llm/prompts/world_model/v1/`. Reject responses that contain a probability, a new atom, a command, or an unknown id.
  - Logging: DEBUG `prospective_llm_selection` with owner id, tick, candidate count, selected count, token count, `fallback_used`. WARNING on fallback with reason code (`missing_provider`, `schema_rejected`, `foreign_id`, `transport`, `budget_llm`, `budget_tokens`). Do not log prompts or raw provider bodies. Logger `agents.cognition.prospective_selection`. LLM metadata stays on the existing `llm` logger.
  - Depends on tasks 3 and 4.
  - Files: `src/agents/cognition/prospective_selection.py`, `src/llm/prompts/prospective/v1/`, `pyproject.toml`, `tests/unit/test_prospective_imagination.py`.

- [x] Task 6: Attach the in-memory prospective audit.
  - Deliverable: `ProspectiveAudit` built from the rollout for enabled agents only. Append it on `AgentRuntime` and export it through `export_prospective_audits`, following `export_world_model_audits`. Store the tuple on `SimulationRunnerResult.prospective_audits`. Omit it from runner-result serialization. `DISABLED` leaves the tuple empty.
  - Fields match Design Decisions. Confidence and uncertainty are bands, not raw observation payloads.
  - Logging: DEBUG `prospective_audit` with owner id, tick, expanded count, pruned count, and whether timeout hit. Logger `simulation.agent_runtime` on append and `simulation.runner` on export. No paths at INFO.
  - Depends on tasks 2 and 4.
  - Files: `src/agents/cognition/prospective.py`, `src/simulation/agent_runtime.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `tests/unit/test_prospective_imagination.py`.

### Phase 3: Experiment, Proofs, and Docs

- [x] Task 7: Add Experiment J for deeper planning, and prove a false belief changes the rollout winner.
  - Deliverable: two catalog arms share seed, scenario, and stochastic identity. `j-shallow` leaves prospective mode `DISABLED` and stays on `runner-config-v4`. `j-deep` sets `DETERMINISTIC` and uses `runner-config-v7` with default policy horizon 3. Register Experiment J beside Experiment I in `src/experiments/catalog.py`. Do not add it to `tests/unit/test_v1_regression_gate.py`. Catalog definitions stay on `SimulationRunnerConfig`; they do not restore a `CausalWorldModel`.
  - Required catalog outcomes on the task 4 fixture: `j-shallow` first command kind is search and `j-deep` first command kind is move toward `D`.
  - False-belief proof, in `tests/unit/test_prospective_imagination.py`: inject `LOCATION=D` `DANGER` at confidence `0.8` (support `4`, counter `0`, prior `1`). The observer's current location is not `D`. Depth at least 2 makes the move-then-search path negative after `_raise_physical_harm(0.8)`, and the collapsed command is `Wait`. After `imagine`, the stored hypothesis confidence is still `0.8`.
  - `prospective_imagination@1` reads audit fields and committed events without importing the rollout. Feed it the false-belief audit and events with no harm at `D`; absolute error against audit confidence is large. The metric return value is not an argument to `CognitiveLoop`. Register the spec the same way as `causal_world_model@1`.
  - Logging: DEBUG `experiment_j_built` with experiment id and condition ids, logger `experiments.catalog`. DEBUG `prospective_imagination_metric` with arm id, matched count, and unmatched count, logger `analysis.prospective_imagination_metrics`. Do not log per-step values at INFO.
  - Depends on tasks 2, 4, and 6.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/analysis/prospective_imagination_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_prospective_imagination.py`, `tests/unit/test_prospective_imagination_experiment.py`.

- [x] Task 8: Prove budgets, uncertainty, one command, and the objective-future boundary.
  - Deliverable: tests that fail if search exceeds a budget, if a transition drops uncertainty, if two commands are returned, or if cognition can see engine probabilities.
  - Required cases in `tests/unit/test_prospective_imagination.py`:
    - `None` policy: future ids, directions, and `horizon_ticks` match the current engine fixture.
    - Each transition in a depth-3 rollout has epistemic, aleatory, band, and confidence inside `[0, 1]`, and a depth-2 epistemic is strictly above its parent when no hypothesis matches.
    - `max_branches`, `max_depth`, `max_llm_calls`, `max_tokens`, and a scripted timeout each stop with the matching reason code and still yield one `AgentCommand`.
    - `src/agents/cognition/prospective.py` source does not contain `search_base_probability`, `PhysicalRules`, `WorldState`, or `time.monotonic`. Constructing a rollout with a `PhysicalRules` instance raises `TypeError`.
    - `CommandPlanner` returns the single collapsed winner from task 4. Output count is 1, and its command type is in the existing allowlist.
    - `src/agents/cognition/prospective.py` does not import `llm`. The provider import is only in `src/agents/cognition/prospective_selection.py`.
  - Logging assertions: DEBUG records contain direction and reason codes and do not contain `search_base_probability` or prompt text.
  - Depends on tasks 3, 4, 5, and 7. The single command asserted here is the collapsed winner from task 4.
  - Files: `tests/unit/test_prospective_imagination.py`, `tests/unit/test_prospective_imagination_experiment.py`.

- [x] Task 9: Document the mode, budgets, and Experiment J boundary.
  - Deliverable: mandatory docs checkpoint through `/aif-docs`. Update `docs/cognition-runtime.md` with prospective mode default-off, the subjective chain, the five budgets, and the single-command rule. Update the Downstream V2 checklist sentence in `docs/architecture.md` so Experiment J (`prospective_imagination@1`) stays off the V1 regression gate beside Experiment I. Do not document a world-engine rollout.
  - Logging: none in docs. Implementation logs stay metadata-only as specified above.
  - Depends on tasks 4 and 7.
  - Files: `docs/cognition-runtime.md`, `docs/architecture.md`.
