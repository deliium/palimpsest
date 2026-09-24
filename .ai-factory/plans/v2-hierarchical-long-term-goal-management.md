# Implementation Plan: V2 Hierarchical Long-Term Goal Management

Branch: main
Created: 2026-09-23
Improved: 2026-09-23 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "none"
Rationale: Skipped — ROADMAP.md has no incomplete milestone (`WARN [aif-plan] no incomplete roadmap milestone; skipping linkage`).

## Compatibility contract

This plan upgrades **production cognition goal handling** (always-on when `CognitionGoalManagementMode.ENABLED`). It is **not** a `V2CapabilityFlags` feature and **not** gated by `CognitionTraceSpec`.

1. V1 invariants intact (WorldEngine authority, Observation trust, subjective ≠ objective fold, no CoT/payload logging).
2. Do **not** enable reserved cognitive flags; do not overload tracing spec for goal management.
3. V1 regression gate must stay green after updating expectations where applying goal status to live `Agent.goals` changes commands for goal-bearing agents (trajectory hash may change vs pre-fix stale-ACTIVE behavior — document and refresh goldens/assertions in Task 16).
4. Goal codecs use accepted-set + exact key-set discipline (`GOAL_MODEL_VERSION` 2→3; legacy v2 decode with documented defaults).
5. No scripted emergence / no LLM→world shortcuts; decomposition uses a closed template registry only.
6. Experiments remain reproducible under deterministic fakes; catalog A–E stay flags-off and tracing-off by default.
7. Analysis `goal_completion` continues to consume **objective** transition receipts only; subjective `FAILED` / `SUSPENDED` do not invent objective completions.
8. No new Alembic migration unless indexed SQL columns are proven necessary for inspection — opaque `goal-revision-v*` envelopes remain sufficient (same bar as cognition-trace `0013`).

## Goal

Replace the flat V1 `Goal` list (active / completed / abandoned + outcome/progress) with an owner-scoped hierarchical **Goal Management** system that maintains desires, long-/medium-term goals, subgoals, and current intentions across completed / failed / abandoned / suspended states; supports competition, reinforcement, postpone/resume, decomposition, revision, and impossibility after subjective world changes; integrates into `CognitiveLoop` and planning while preserving multi-criteria, non-scalar intention selection; and proves short-term vs long-term conflict with scenario tests.

## Design Decisions (locked by `/aif-improve`)

- **Extend, do not flatten.** Keep structured `GoalOutcome` / `GoalProgress` and owner-scoped immutability. Bump `GOAL_MODEL_VERSION` to **3** with an explicit decode path for v2 payloads. Do not introduce a permanent total reward or collapse drives + goals into one utility scalar. Forbid any new permanent reward / total-utility field on `DecisionMetadata` or selection artifacts.
- **Hierarchy is first-class.** Closed `GoalHorizon`: `DESIRE`, `LONG_TERM`, `MEDIUM_TERM`, `SUBGOAL`, `CURRENT_INTENTION`. Parent links use **`parent_goal_id` only** (no parallel `PARENT_OF` relation kind). Ordered `dependency_ids` plus relation kinds `DEPENDS_ON` | `COMPETES_WITH` | `REINFORCES` express compete/reinforce/depends. Current-intention nodes are hierarchical foci, **not** deliberation’s `SelectedIntention` / tick command.
- **Expanded lifecycle.** `GoalStatus`: `ACTIVE`, `COMPLETED`, `FAILED`, `ABANDONED`, `SUSPENDED`. Suspend = postpone with resume; abandon = terminal drop; fail = success conditions become subjectively impossible or failure conditions fire.
- **Live agent mutation is mandatory.** Today objective `GoalTransitionReceipt`s are recorded but **`Agent.goals` stay ACTIVE**, so cognition never sees completions. This plan **must** apply objective receipts and GoalManager intents to live `Agent.goals` before the next snapshot (ordered, owner-checked). Receipt-only bookkeeping is insufficient.
- **Scientific revisions must be published.** Ports (`GoalRevisionRecord`, `encode_goal_transition_receipt`, `append_goal_revision`) already exist but the runner does not publish them. Wire publish for objective + subjective transitions. Prefer extending `goal-revision-v1` document fields via a version bump (`goal-revision-v2`) only if hierarchical reason codes / horizon must appear in the opaque envelope; otherwise keep v1 receipt shape and store full post-transition `Goal` via agent checkpoint codecs.
- **Subjective vs objective reason codes.** Extend `GoalTransitionReasonCode` (or add a parallel subjective reason enum on intents) for `FAILED`, `SUSPENDED`, `RESUMED`, `DECOMPOSED`, `REVISED`. Precedence: objective COMPLETED for observable outcome kinds wins over concurrent subjective FAILED on the same goal/tick.
- **`GoalManager` as a CognitiveLoop stage.** `ComponentKind.GOAL_MANAGEMENT` between `SELF_STATE` and `FUTURES`. Protocol + policy `goals.v1` in `agents/cognition/goal_manager.py`. Output `GoalBoard` (frozen). Config: `CognitionGoalManagementMode` (`ENABLED` | `PASSTHROUGH`) on `CognitionLoopConfig`, wired in `build_cognitive_loop` (mirror `imagination_mode`).
- **Closed decomposition templates.** Production policy uses a closed template registry (template code → required parent outcome kinds / child outcome skeletons). Reference/scenario tests may seed the winter→food-reserve hierarchy via that registry — **no** free-text LLM decomposition and **no** hard-coded winter action scripts inside the policy.
- **Cognition-local goal IDs.** Decomposition must not import `simulation.derive_goal_id`. Use a cognition-local stable id helper (memory-style `owner/tick/parent/template` keys truncated to stable-id limits).
- **Selection stays multi-criteria.** Competition/reinforcement uses pairwise / veto / dominance over separate vectors — same philosophy as `MultiCriteriaIntentionSelector`. Never reduce “survive winter vs eat now” to one reward number.
- **Subjective-only inputs.** Situation, physiology projection, owner goals, drives, `SelfModel`, relationships, semantic beliefs, reconstructed memory structure only. Never `WorldState`, event stores, analysis metrics, or ground truth.
- **Trace projection prefers GoalBoard.** Scientific GOALS trace view prefers `GOAL_MANAGEMENT` / `GoalBoard` (horizon + status histograms, foci refs); fall back to snapshot/motivation only if the stage is absent. Tracing remains optional and outside the objective fold.
- **Runtime commit timing.** Snapshot for invocation N is fixed; applied goal mutations appear on N+1. Checkpoints encode hierarchical goals via goal v3 codecs.

## Non-Goals

- Global scalar reward / utility maximizer over all motivations
- LLM-authored free-text goal narratives as authoritative structure
- WorldEngine changes, new `AgentCommand` kinds, or objective “true” goal completion beyond existing observable outcome kinds
- Friend/enemy/role labels or personality archetypes
- Feeding analysis metrics back into live GoalManager
- New Alembic tables/columns for goals (unless a later inspection plan proves indexed SQL necessary)
- HTTP / research-API expansion for hierarchical goal boards
- V2 capability-flag gating or `CognitionTraceSpec` coupling

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(agents): extend hierarchical goal model and codecs`
- **Commit 2** (after tasks 4–7): `feat(cognition): add GoalManager stage, config mode, and loop/planning wiring`
- **Commit 3** (after tasks 8–10): `feat(simulation): apply goal mutations, publish revisions, and update traces`
- **Commit 4** (after tasks 11–16): `test(cognition): hierarchy dynamics, conflict scenarios, regression, and docs`

## Tasks

### Phase 1: Hierarchical Goal Contracts

- [x] Task 1: Extend goal domain model for hierarchy, provenance, and lifecycle.
  - Deliverable: In `src/agents/models.py`, add closed `GoalHorizon` (`DESIRE` | `LONG_TERM` | `MEDIUM_TERM` | `SUBGOAL` | `CURRENT_INTENTION`), expand `GoalStatus` with `FAILED` and `SUSPENDED`, add `GoalOriginKind` / provenance refs, `GoalRelationKind` limited to `DEPENDS_ON` | `COMPETES_WITH` | `REINFORCES` (parentage is **only** `parent_goal_id`), and structured success/failure condition types (closed kinds aligned with or wrapping `GoalOutcome`). Extend frozen `Goal` with: `horizon`, `confidence`, provenance, `created_tick`, optional `deadline_tick`, `parent_goal_id`, ordered `dependency_ids`, ordered relation edges, drive links, opaque self-model/belief refs, success/failure conditions — keep `outcome` / `progress` / `priority` / `description` / owner scope. Bump `GOAL_MODEL_VERSION` to 3. Validate uniqueness, owner consistency, no cycles via `parent_goal_id` + `dependency_ids` (fail closed), finite unit intervals, non-negative ticks. Preserve safe `repr` (IDs/status/horizon only).
  - Expected behavior: Winter hierarchy expressible as linked immutable goals; suspended/failed distinct from abandoned/completed; defaults keep flat-active constructors usable in existing tests.
  - Files: `src/agents/models.py`, `src/agents/__init__.py`, `tests/unit/test_v1_agent_models.py` (extend or add focused goal-model tests).
  - Logging requirements: Domain models stay log-free. Validation errors expose stable field reason codes only; tests prove descriptions/targets/conditions never appear in `repr` or error strings.
  - Dependencies: None.

- [x] Task 2: Version codecs and checkpoint/evidence payloads for goal v3.
  - Deliverable: Update `src/simulation/serialization.py` goal encode/decode for exact key-set `GOAL_MODEL_VERSION=3`; intentionally decode v2→v3 with documented defaults (horizon default, confidence from progress, empty relations, `created_tick=0`, no deadline, no parent). Ensure agent/checkpoint/runner initial_goals round-trip hierarchical fields. Fail closed on unknown versions or missing required keys. Keep analysis `GoalTransitionRow` on objective receipts; do not force subjective FAILED/SUSPENDED into objective completion metrics.
  - Expected behavior: Live/restored agent and checkpoint parity; legacy v2 fixtures upgrade deterministically.
  - Files: `src/simulation/serialization.py`, `src/simulation/runner_serialization.py` (if initial_goals path needs it), `tests/unit/test_v1_domain_serialization.py`, `tests/unit/test_runner_serialization.py`.
  - Logging requirements: DEBUG encode/decode version + goal_count only. WARN/ERROR: schema reason codes, run/owner IDs — never descriptions/targets/conditions.
  - Dependencies: Task 1.

- [x] Task 3: Define GoalBoard artifacts, GoalManager protocol, stage kind, and config mode.
  - Deliverable: Add frozen `GoalBoard` / `GoalTransitionIntent` (and related) in `src/agents/cognition/models.py`; add `ComponentKind.GOAL_MANAGEMENT`; include `GoalBoard` in `_STAGE_OUTPUT_TYPES` and `CognitiveLoopProposal` / boundary validation; add `GoalManager` protocol in `contracts.py`; add `CognitionGoalManagementMode` (`ENABLED` | `PASSTHROUGH`) on `CognitionLoopConfig` and wire selection in `build_cognitive_loop`; export from cognition facade.
  - Expected behavior: Stage ordinals remain a closed ordered pipeline; ownership/type checks fail closed; PASSTHROUGH available for tests that need flat V1-like boards.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_cognition_models.py`, `tests/unit/test_cognition_configuration.py`, `tests/typecheck/cognitive_loop.py` (if present).
  - Logging requirements: Pure models log-free; contract tests assert metadata-only `repr` for board/intents.
  - Dependencies: Task 1.

### Phase 2: GoalManager Policy and Loop Integration

- [x] Task 4: Implement cognition-local stable goal-id helper.
  - Deliverable: Add a deterministic goal-id factory under `agents.cognition` (e.g. in `goal_manager.py` or a small helper module) that builds `GoalId` from owner/tick/parent/template/ordinal keys without importing `simulation`. Match stable-id length/charset rules. Unit-test collision resistance for distinct keys and determinism for identical keys.
  - Expected behavior: Decomposition can mint child IDs inside cognition; import-linter stays clean.
  - Files: `src/agents/cognition/goal_manager.py` (or helper), `tests/unit/test_goal_manager.py`.
  - Logging requirements: No payload logs; tests may DEBUG id-prefix only if needed.
  - Dependencies: Task 1.

- [x] Task 5: Implement deterministic `GoalManager` policy (`goals.v1`) with closed decomposition templates.
  - Deliverable: New `src/agents/cognition/goal_manager.py` implementing hierarchical maintenance: progress/status updates; compete vs reinforce via multi-criteria rules; postpone→`SUSPENDED`, abandon, resume, mark `FAILED` on subjective impossibility; select ordered `CURRENT_INTENTION` foci; decompose only via a **closed template registry** (template codes → child outcome skeletons / horizons). Emit `GoalBoard` + transition intents. `GOAL_POLICY_VERSION = "goals.v1"`. Provide PASSTHROUGH manager that re-emits snapshot goals without decompose/compete mutations (still validates ownership).
  - Expected behavior: Same observation + different goals/beliefs → different boards; short-term focus can win a tick without deleting long-term parents; impossible goals → FAILED with stable reason codes; no scalar utility; no winter hard-script in production policy.
  - Files: `src/agents/cognition/goal_manager.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_goal_manager.py`.
  - Logging requirements: DEBUG `goal_manager_start` / `goal_manager_complete` with policy version, owner/tick, counts by status/horizon, transition_count by reason, foci_count, template_code counts. WARN truncation/cycle rejection; ERROR ownership/contract failure. Never log descriptions, outcomes, conditions, belief claims.
  - Dependencies: Tasks 1, 3, 4.

- [x] Task 6: Insert GoalManager into `CognitiveLoop` and feed imagination/motivation/deliberation/planning.
  - Deliverable: Update `CognitiveLoop.prepare` order: perception → memory → situation → self_state → **goal_management** → futures → motivation → intention → planning. Pass `GoalBoard` into imagination/motivation/deliberation so eligible statuses/horizons enter candidate effects; suspended/failed/abandoned excluded from forward planning except mortality outstanding-value inputs. Align `CommandPlanner` / intention selection so futures advancing current-intention foci and ready dependencies are preferred, while critical need vetoes still preempt. Shift ordinals; update architecture isolation tests. Preserve one closed `AgentCommand` per tick and Wait fallback.
  - Expected behavior: Post-management hierarchy drives effects; thirst-critical veto can override long-horizon focus; no permanent reward field on decision metadata.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/imagination.py`, `src/agents/cognition/motivation.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/contracts.py`, `tests/unit/test_cognitive_loop.py`, `tests/architecture/test_cognitive_loop_isolation.py`, `tests/unit/test_imagination_engine.py`, `tests/unit/test_motivation_appraisal.py`, `tests/unit/test_intention_selection.py`, `tests/unit/test_action_planner.py`.
  - Logging requirements: Loop DEBUG includes new stage kind/ordinal/status; selection reason codes may include `goal_focus_support` / `critical_need_veto`; metadata only.
  - Dependencies: Task 5.

- [x] Task 7: Unit tests for hierarchy dynamics (compete, reinforce, suspend, resume, fail, decompose).
  - Deliverable: Table-driven tests for parent/child integrity; short- vs long-term foci divergence; reinforcement of parent progress; postpone/resume; abandon; FAILED after subjective impossibility; decompose via template registry with stable cognition-local IDs; determinism; cycle fail-closed; assert no total-reward field used in selection metadata.
  - Expected behavior: Stable reason codes; identical inputs → identical boards.
  - Files: `tests/unit/test_goal_manager.py`, optionally `tests/unit/test_goal_hierarchy_models.py`.
  - Logging requirements: Capture logs and assert allowlisted keys only.
  - Dependencies: Tasks 5–6.

### Phase 3: Runtime Mutation, Evidence, Trace

- [x] Task 8: Apply objective goal receipts to live `Agent.goals`.
  - Deliverable: After each `_evaluate_goals_at_boundary` (mid-run and run-end), apply emitted `GoalTransitionReceipt`s to the owning runtime’s `Agent.goals` (replace immutable goal entries with updated status). Keep receipt skip-set (`completed_ids`) consistent with live status. Owner-check and deterministic ordering. Ensure next `build_perspective` / snapshot sees updated statuses.
  - Expected behavior: A REACH_PLACE completion removes that goal from ACTIVE deliberation on subsequent ticks; death/run-end abandonments update live agents, not only result receipts.
  - Files: `src/simulation/runner.py`, `src/simulation/agent_runtime.py` (helper to replace goals), `tests/unit/test_agent_runtime.py`, runner/goal evaluation tests.
  - Logging requirements: DEBUG apply: owner, tick, goal_id, from→to, reason_code only.
  - Dependencies: Task 2.

- [x] Task 9: Commit GoalBoard intents, extend reason codes, and publish scientific goal revisions.
  - Deliverable: After successful cognition finalize, apply `GoalTransitionIntent`s to `Agent.goals` (ordered, owner-checked) with precedence rules vs same-tick objective COMPLETED. Extend `GoalTransitionReasonCode` and/or intent reason enum for subjective FAILED/SUSPENDED/RESUMED/DECOMPOSED/REVISED. Publish revisions through existing scientific-evidence ports (`encode_goal_transition_receipt` / `GoalRevisionRecord` / `append_goal_revision` or finalized-boundary batch) for both objective receipts and subjective commits. Update checkpoint restore. Optionally seed a minimal hierarchy on one reference-scenario agent via closed templates.
  - Expected behavior: Invocation N+1 sees updated hierarchy; revisions are ordered and reproducible; analysis still keys off objective receipts for `goal_completion`.
  - Files: `src/simulation/agent_runtime.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/simulation/evidence.py`, scientific evidence wiring as needed, `src/experiments/reference_scenario.py` (minimal seed), unit tests.
  - Logging requirements: INFO/DEBUG goal commit: owner, tick, transition_count, status from→to, reason codes, goal_ids; revision append mirrors existing `goal_revision_*` metadata-only logs.
  - Dependencies: Tasks 2, 5, 6, 8.

- [x] Task 10: Update cognition-trace goal projection for GoalBoard / hierarchy.
  - Deliverable: Extend `agents/cognition/trace.py` so GOALS scientific stage prefers `ComponentKind.GOAL_MANAGEMENT` / `GoalBoard` (horizon + status histograms, foci refs, goal_count). Map `GOAL_MANAGEMENT` in component→trace helpers as appropriate without breaking the fixed scientific sequence. Fall back to snapshot/motivation/self-state only if board absent. Keep ToM unavailable behavior unchanged. Flags-off V1 gate unaffected.
  - Expected behavior: Tracing-on runs show hierarchical counts from the new stage; no description leakage.
  - Files: `src/agents/cognition/trace.py`, `tests/unit/test_cognition_trace_projection.py`.
  - Logging requirements: Metadata-only; tests assert no description leakage.
  - Dependencies: Tasks 3, 5, 6.

### Phase 4: Scenarios, Regression, Docs

- [x] Task 11: Scenario tests — conflicting short-term vs long-term goals.
  - Deliverable: Deterministic scenario (unit preferred) with long-term survive-winter / food-reserve hierarchy **and** acute hunger/thirst. Assert: (1) long-term goals remain ACTIVE (not abandoned) while short-term survival command wins a high-need tick; (2) when acute need drops and reserve subgoal is focal, behavior shifts toward search/secure/cooperate affordances; (3) believed-impossible resource → subgoal FAILED/SUSPENDED, parent confidence/progress updates, path no longer selected; (4) no permanent scalar reward field participates in selection.
  - Expected behavior: Tests fail if long-term goals are deleted whenever short-term needs win a tick, or if a total-utility score is introduced.
  - Files: `tests/unit/test_goal_conflict_scenarios.py` (new); reuse cognition fakes.
  - Logging requirements: Harness logs tick, owner, command type, active_foci_count, status histograms only.
  - Dependencies: Tasks 6, 8, 9, 7.

- [x] Task 12: Architecture / isolation gates.
  - Deliverable: import-linter + cognitive-loop isolation hold (`GoalManager` in cognition; base `agents` has no cognition import; no `simulation` import from goal-id helper). Exhaustive `ComponentKind` / ordinal switches updated. Forbidden: feeding analysis into GoalManager; WorldEngine trust bypass.
  - Expected behavior: `tests/architecture/` green.
  - Files: architecture tests, import-linter config only if required.
  - Logging requirements: N/A beyond existing patterns.
  - Dependencies: Tasks 4, 6, 9, 10.

- [x] Task 13: V1 regression expectations after live goal-status application.
  - Deliverable: Lock always-on hierarchical policy (not a capability flag / not tracing). Update `tests/unit/test_v1_regression_gate.py` and any golden trajectory / goal-bearing assertions so gates stay green after Agent.goals actually reflect COMPLETED/ABANDONED. Document that `exact_trajectory_hash` may differ from the pre-fix “stale ACTIVE goals” behavior for agents with observable goal outcomes — refresh expectations rather than preserving the bug. Catalog A–E remain flags-off and tracing-off.
  - Expected behavior: V1 regression gate green; no new flag required to “turn on” GoalManager in production config.
  - Files: `tests/unit/test_v1_regression_gate.py`, related golden/fixtures as needed, brief note in docs task.
  - Logging requirements: Assert metadata-only extras where logs are checked.
  - Dependencies: Tasks 8, 9, 11, 12.

- [x] Task 14: Documentation checkpoint (`/aif-docs`).
  - Deliverable: Update `docs/cognition-runtime.md` for horizons, statuses, GoalBoard stage placement, config mode, multi-criteria competition, subjective impossibility, live agent mutation + scientific revision publish, current-intention ≠ SelectedIntention, anti-scalar rule, logging allowlist. Touch `docs/architecture.md` facade/seam if needed. Optionally one DESCRIPTION bullet. Explicit non-goals: no utility maximizer; no Alembic/HTTP in this plan.
  - Expected behavior: Docs match shipped policy versions and allowlists.
  - Files: `docs/cognition-runtime.md`, optionally `docs/architecture.md`, `.ai-factory/DESCRIPTION.md`.
  - Logging requirements: Document allowlisted fields for `goal_manager_*` and goal-apply logs.
  - Dependencies: Tasks 6, 9, 10, 11, 13.

## Out of scope (surfaced by `/aif-improve`, not in this plan)

- Alembic / new indexed goal SQL columns — defer until inspection needs prove necessity; opaque envelopes suffice now.
- HTTP / debugger UI / research-API routes for hierarchical goal boards — ports + checkpoints only.
