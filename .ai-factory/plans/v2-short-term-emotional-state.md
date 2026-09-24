# Implementation Plan: V2 Short-Term Emotional State

Branch: main
Created: 2026-09-24
Improved: 2026-09-24 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M5.3 — Short-Term Emotional State"
Rationale: Linked after `/aif-roadmap` registered V2 M5.x delivered milestones (2026-09-24).

## Compatibility contract

This plan owns a new default-off `V2CapabilityFlags.short_term_emotional_state` and introduces a real `AgentEmotionalState` CognitiveLoop stage. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact (WorldEngine authority, Observation trust, subjective ≠ objective fold, no CoT/payload logging, no LLM→world shortcuts).
2. Capability flags opt-in — `short_term_emotional_state` defaults **off** (exact V1-equivalent wiring). Other reserved flags remain unimplemented and fail closed. Enabling the owned flag must **not** raise `capability_unimplemented`.
3. V1 regression gate stays green under flags-off **and** tracing-off. Flag-on arms are separate tests; they must not alter flags-off `exact_trajectory_hash`.
4. Schema bumps use accepted-set + exact key-set discipline (runner capability-flag JSON; agent/checkpoint codecs for durable emotional carry).
5. No scripted emergence / no friend-enemy labels / no free-form emotional narration from LLMs.
6. No LLM → world shortcuts; emotion never mutates `WorldState` or appears in objective events.
7. Experiments remain reproducible under deterministic fakes; catalog A–E stay flags-off by default.
8. Optional cognition tracing stays outside the objective fold; emotional-stage traces are structured intensities/reason codes only.

## Goal

Add a transient, owner-scoped **`AgentEmotionalState`** that is separate from objective world state and from V1 per-trace `emotional_salience`. V1 salience remains a memory property; V2 short-term emotion is a numeric vector over a small closed configurable catalog that decays/regulates over ticks and deterministically updates from observations, remembered events, threats, goal progress/failure, social interactions, relationships, and physical condition. When the capability flag is on, emotion may bias situation-focus weights, memory retrieval weighting, reconstruction, subjective risk estimation, communication, intention selection, and social behavior — without free-form affect narrative.

## Design Decisions (locked by `/aif-improve`)

- **Own a capability flag.** Add `short_term_emotional_state: bool = False` to `V2CapabilityFlags`. Replace the runner’s “any flag → fail closed” gate with an **owned-flag allowlist** so only unimplemented flags raise `capability_unimplemented`. This plan owns `short_term_emotional_state` only.
- **Closed emotion catalog (configurable, not free-form).** Default kinds: `fear`, `anger`, `sadness`, `relief`, `attachment`, `anxiety`, `confidence`. Catalog membership, per-kind decay, gain ceilings, and regulation floors/ceilings live in a frozen `EmotionRegulationPolicy` (versioned). Callers may disable kinds by policy config; they may **not** invent string labels at runtime or via LLM.
- **Numeric / deterministic transitions only.** Intensities are finite unit-interval floats quantized via `memory.models.quantize_score` / `SCORE_QUANTUM` (or a cognition-local twin with identical quantum). Updates are closed driver → delta maps with stable reason codes. No prose affect fields on stage artifacts.
- **Separate from V1 memory salience.** `MemoryTrace.emotional_salience` stays as-is. Live state may *read* salience as a driver and may *bias* retrieval/reconstruction weights; it must not overwrite authoritative objective history or silently rewrite salience as truth.
- **Separate from drives and goals.** Drives remain independent need vectors; goals remain hierarchical intentions. Emotion is a third subjective channel that can modulate appraisals without collapsing into a permanent total utility / reward scalar.
- **`EmotionKind.FEAR` ≠ `RelationshipDimension.FEAR`.** Relationship fear is an asymmetric directed assessment dimension; emotion fear is transient owner affect. Drivers may *read* relationship fear as input; never conflate the two types or enums.
- **Pipeline position.** Insert `ComponentKind.EMOTIONAL_STATE` after `GOAL_MANAGEMENT` and before `FUTURES`. **Prior-tick** state (from snapshot) biases `MEMORY_RETRIEVAL` and situation-focus weighting in the same invocation; the **updated** state biases same-tick futures→planning and is committed for the next tick.
- **Same-tick goal drivers use `GoalBoard`.** Live `Agent.goals` update on N+1. The emotional engine must drive from this-tick `GoalBoard` statuses / `GoalTransitionIntent`s (plus situation, memory, physiology, relationships, inbox) — never from post-commit agent goals, `WorldState`, event stores, or analysis metrics.
- **Mode mirror.** Add `CognitionEmotionalStateMode` (`ENABLED` | `PASSTHROUGH`) on `CognitionLoopConfig`. Runner maps `capability_flags.short_term_emotional_state=False` → PASSTHROUGH; `True` → ENABLED. Unit tests may inject ENABLED without the runner.
- **Carry lives on `AgentRuntime`, not `Agent`.** Store prior/post state in `AgentRuntime` (owner-checked). Thread through `build_perspective(..., emotional_state=...)` → `Perspective` → `SubjectiveSnapshot.emotional_state`. After successful cognition finalize, commit post-stage state onto the runtime so invocation N+1 sees it. Do **not** add emotion to the `agents.models.Agent` identity model.
- **Durable resume via agent/checkpoint codecs.** Prefer encoding emotional state beside agent checkpoint payloads (accepted-set + legacy missing→empty). Do **not** force a `subjective_serialization` bump unless that envelope already owns an equivalent field. No Alembic migration in this plan.
- **“Attention” = situation-focus / claim reweighting + retrieval bias.** There is no separate attention subsystem. Flag-on influence means closed situation claim/focus weights plus memory retrieval/reconstruction bias. A full attention module is out of scope.
- **Trace projection prefers live stage.** Scientific `EMOTIONAL_STATE` prefers the new stage intensities + reason codes; fall back to drive/salience projection only when the stage is absent/PASSTHROUGH-neutral.
- **Influence surfaces (flag-on only).** Deterministic bias hooks — never LLM narration:
  - Situation-focus / claim reweighting (not a separate attention engine)
  - Memory retrieval score bias (prior state)
  - Reconstruction salience / ranking bias
  - Subjective risk likelihood/severity scaling in imagination
  - Motivation / multi-criteria intention votes
  - Social-message / communication policy preferences
- **Fail closed.** Unknown emotion kinds, non-finite intensities, ownership mismatches, and unowned capability flags abort with stable reason codes.
- **Runner JSON exact key-set.** Extending `V2CapabilityFlags` requires updating `_CAPABILITY_FLAG_KEYS` / encode-decode in `runner_serialization.py`, golden runner configs, and replacing any hardcoded `flag_count=4` with `len(_V2_CAPABILITY_FLAG_NAMES)`.

## Non-Goals

- Free-form emotional prose, CoT affect, or LLM-authored emotion labels as authoritative state
- Personality archetypes, mood disorders, or permanent trait systems
- A dedicated attention / perceptual-filter subsystem beyond situation-focus and retrieval bias
- Writing emotion into `WorldState`, objective events, or `EvidenceManifest`
- Collapsing emotion + drives + goals into one reward/utility scalar
- Enabling other reserved V2 capability flags
- HTTP/debug UI for emotional state
- New Alembic tables for emotion (unless a later inspection plan proves need)
- Changing WorldEngine admission or Observation trust boundaries
- Placing emotional state on `agents.models.Agent` as a permanent identity field

## Commit Plan
- **Commit 1** (after tasks 1–4): `feat(cognition): add AgentEmotionalState contracts, stage, and capability flag`
- **Commit 2** (after tasks 5–9): `feat(cognition): implement emotional transitions, runtime carry, and influence hooks`
- **Commit 3** (after tasks 10–11): `feat(simulation): checkpoint emotional state and update cognition traces`
- **Commit 4** (after tasks 12–15): `test(cognition): emotional divergence, flag gating, regression, and docs`

## Tasks

### Phase 1: Contracts and Capability Ownership

- [x] Task 1: Define closed emotion catalog and `AgentEmotionalState` model.
  - Deliverable: Add frozen types under `agents.cognition` (prefer `models.py` or new `emotion.py` re-exported from the facade): closed `EmotionKind` (`FEAR` | `ANGER` | `SADNESS` | `RELIEF` | `ATTACHMENT` | `ANXIETY` | `CONFIDENCE`), `EmotionIntensity` / ordered intensity map, owner-scoped `AgentEmotionalState` (owner, tick, intensities, last_update_tick, regulation metadata refs), and versioned `EmotionRegulationPolicy` (per-kind decay rates, gain caps, floors/ceilings, enabled kind set). Quantize intensities with `memory.models.quantize_score` / `SCORE_QUANTUM` (or an identical cognition-local quantum). Validate ownership, exact kind set when enabled, finite unit intervals. Safe `repr` (owner/tick/kind counts/bands only — never narrative).
  - Expected behavior: Default catalog matches the seven kinds; disabled kinds omit from active vector; identical inputs construct identical states.
  - Files: `src/agents/cognition/models.py` and/or `src/agents/cognition/emotion.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_emotional_state_models.py`.
  - Logging requirements: Models stay log-free. Validation errors expose stable field reason codes only; tests prove intensities appear only as quantized numbers in allowed debug helpers, never as prose.
  - Dependencies: None.

- [x] Task 2: Define stage artifacts, driver reason codes, and EmotionalState protocol.
  - Deliverable: Add frozen stage output (`EmotionalStateEvaluation` wrapping post-update `AgentEmotionalState`, ordered driver reason codes, decision metadata). Add closed `EmotionDriverCode` for observation / memory-salience / threat / goal-progress / goal-failure / social-interaction / relationship / physical-condition / decay / regulation. Add `ComponentKind.EMOTIONAL_STATE`. Extend `_STAGE_OUTPUT_TYPES`, proposal/boundary validation, and `EmotionalStateAppraiser` protocol in `contracts.py`. Add `CognitionEmotionalStateMode` (`ENABLED` | `PASSTHROUGH`) on `CognitionLoopConfig` and wire selection in `build_cognitive_loop`.
  - Expected behavior: Stage ordinals remain a closed ordered pipeline; PASSTHROUGH re-emits prior/zero state without driver deltas; ownership/type checks fail closed.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_cognition_models.py`, `tests/unit/test_cognition_configuration.py`.
  - Logging requirements: Pure models log-free; config DEBUG may log mode value only.
  - Dependencies: Task 1.

- [x] Task 3: Own `V2CapabilityFlags.short_term_emotional_state`, allowlist, and runner JSON key-set.
  - Deliverable: Add `short_term_emotional_state: bool = False` to `V2CapabilityFlags` and `_V2_CAPABILITY_FLAG_NAMES`. Introduce an explicit owned-flag frozenset (initially `{short_term_emotional_state}`). Change `SimulationRunner` construction so only **non-owned** enabled flags raise `CAPABILITY_UNIMPLEMENTED`. Update `capability_flags_digest`, diagnostics, and **`runner_serialization.py`** `_CAPABILITY_FLAG_KEYS` / `_encode_capability_flags` / `_decode_capability_flags` for the fifth exact key. Replace hardcoded `flag_count=4` in runner construction logs with `len(_V2_CAPABILITY_FLAG_NAMES)`. Refresh golden runner configs and unit assertions that enumerate the four legacy keys (`tests/unit/test_runner_serialization.py`, `tests/unit/test_v2_golden_runner_configs.py`, `tests/unit/test_v2_flag_defaults.py`, construction tests).
  - Expected behavior: All-false flags construct and round-trip; owned flag alone constructs; any other enabled flag still fails closed; digests remain deterministic; schemav3/v4 documents include the new key.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner.py`, `src/simulation/runner_serialization.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_v2_flag_defaults.py`, `tests/unit/test_v2_golden_runner_configs.py`.
  - Logging requirements: DEBUG construction logs enabled owned vs unimplemented flag names (counts/names only). ERROR on unimplemented flags with `capability_unimplemented`. Never log emotion intensities here.
  - Dependencies: None (can parallel Task 1–2).

- [x] Task 4: Map runner flag → cognition emotional mode and document V1 parity.
  - Deliverable: Extend `_cognition_config_for` (and agent-bundle wiring) so `capability_flags.short_term_emotional_state` False→`PASSTHROUGH`, True→`ENABLED` on `CognitionLoopConfig`. Ensure catalog A–E / `v1_regression_profile` remain flags-off. Add a focused assertion that flags-off trajectories match pre-change V1 behavior for a short reference seed.
  - Expected behavior: Flag-off: no command divergence from emotion bias. Flag-on: emotional policy is injected.
  - Files: `src/simulation/runner.py`, `tests/unit/test_v1_regression_gate.py`, runner cognition wiring tests.
  - Logging requirements: DEBUG log emotional_state_mode + flag bool at agent bundle construction (metadata only).
  - Dependencies: Tasks 2, 3.

### Phase 2: Transition Policy and Loop Integration

- [x] Task 5: Implement deterministic `EmotionalStateEngine` (`emotion.v1`).
  - Deliverable: New `src/agents/cognition/emotion.py` (or policy module) implementing: (1) per-kind decay/regulation toward baseline using `EmotionRegulationPolicy` and tick delta; (2) closed driver deltas from interpreted perception, retrieved memory salience, situation threat claims, **this-tick `GoalBoard` statuses / transition intents** (not live `Agent.goals`), inbox/social envelopes, relationship dimensions (including reading `RelationshipDimension.FEAR` as input only), and observation physiology/terminal cues; (3) clamp/quantize; (4) emit `EmotionalStateEvaluation` + stable reason codes. Provide PASSTHROUGH appraiser that returns prior/zero state with `passthrough` reason. Version constant `EMOTION_POLICY_VERSION = "emotion.v1"`.
  - Expected behavior: Identical subjective inputs → identical outputs; high threat raises fear/anxiety; goal-failure intents raise sadness/anger (policy weights); relief on threat removal / goal-progress intents; attachment from positive social/relationship evidence; confidence from competence/progress cues — all numeric, no narrative.
  - Files: `src/agents/cognition/emotion.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_emotional_state_engine.py`.
  - Logging requirements: DEBUG `emotional_state_start` / `emotional_state_complete` with policy version, owner/tick, active_kind_count, max_intensity_band, driver_code_counts, decay_applied. WARN on truncation/disabled-kind rejection; ERROR on ownership/contract failure. Never log free-text affect, observation payloads, or memory content.
  - Dependencies: Tasks 1, 2.

- [x] Task 6: Insert emotional stage into `CognitiveLoop` with constructor injection and proposal wiring.
  - Deliverable: Update `_STAGE_ORDER` and `CognitiveLoop.prepare` to run emotional appraisal after `GOAL_MANAGEMENT` and before `FUTURES`. Inject `EmotionalStateAppraiser` on the loop (mirror `GoalManager`). Extend `CognitiveLoopProposal` with the evaluation field; include it in boundary validation. Pass prior state from `SubjectiveSnapshot.emotional_state` into the stage; pass updated evaluation into downstream stage calls. Shift ordinals; update architecture isolation / loop / typecheck tests.
  - Expected behavior: Stage boundary records include `EMOTIONAL_STATE`; PASSTHROUGH keeps downstream unbiased; ENABLED feeds updated state forward.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/models.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/configuration.py`, `tests/unit/test_cognitive_loop.py`, `tests/architecture/test_cognitive_loop_isolation.py`, `tests/typecheck/cognitive_loop.py` (if present).
  - Logging requirements: Loop DEBUG includes new stage kind/ordinal/status; metadata only.
  - Dependencies: Task 5.

### Phase 3: Runtime Carry and Influence Hooks

- [x] Task 7: Carry emotional state on `AgentRuntime` through perspective → snapshot (N→N+1).
  - Deliverable: Add owner-scoped `_emotional_state` on `AgentRuntime` (default empty/None). Extend `Perspective` and `build_perspective(..., emotional_state=...)` in `agents/cognition/contracts.py` + `simulation/perception.py` to thread into `SubjectiveSnapshot.emotional_state`. After successful cognition finalize/bind, commit post-stage `AgentEmotionalState` onto the runtime (ownership-checked) so the next snapshot includes it. Snapshot for invocation N stays fixed; mutations appear on N+1. Do not mutate `Agent` domain identity.
  - Expected behavior: Fear induced on tick t is visible as prior state on tick t+1 retrieval bias; objective world unchanged; flags-off / PASSTHROUGH leave empty/neutral carry.
  - Files: `src/agents/cognition/contracts.py`, `src/agents/cognition/models.py`, `src/simulation/perception.py`, `src/simulation/agent_runtime.py`, related unit tests (`tests/unit/test_agent_runtime.py`, perspective tests).
  - Logging requirements: DEBUG commit emotional_state_present, kind_count, tick — never intensities as INFO payloads; DEBUG may include quantized max intensity only.
  - Dependencies: Tasks 2, 6.

- [x] Task 8: Wire prior-state bias into memory retrieval / reconstruction and situation-focus weights.
  - Deliverable: When prior `AgentEmotionalState` is non-neutral and mode ENABLED, apply deterministic retrieval score bias (congruent salience / threat-tagged traces under fear/anxiety; attachment-congruent social traces under attachment) without changing `MemoryTrace` storage. Extend reconstruction ranking/salience blend similarly. Apply closed situation-focus / claim reweighting from prior emotion (this is the plan’s “attention” surface — not a new attention engine). Keep V1 scoring path bit-identical when prior state is absent/zero or mode PASSTHROUGH. Prefer cognition-side bias wrappers over mutating `memory.scoring` globals; if scoring policy gains optional emotion weights, version the policy id and keep defaults emotion-neutral.
  - Expected behavior: Same store + same query + different prior emotion → different ranked hits / focus weights when ENABLED; identical when PASSTHROUGH/off.
  - Files: `src/agents/cognition/memory.py`, `src/agents/cognition/reconstruction.py`, situation modeler/defaults as needed, optionally `src/memory/scoring.py`, `tests/unit/test_emotional_memory_bias.py`.
  - Logging requirements: DEBUG bias_applied bool, policy version, hit_count delta, focus_code_counts — never trace text/embeddings.
  - Dependencies: Tasks 1, 7.

- [x] Task 9: Wire updated-state bias into risk, intention, and social/communication behavior.
  - Deliverable: Extend protocol signatures for `FutureImagination`, `MotivationEvaluator`, `IntentionSelector`, `Planner`, and `SocialMessagePolicy` to accept optional `EmotionalStateEvaluation` (default None). When ENABLED, scale subjective risk likelihood/severity (e.g. emotion fear/anxiety ↑ physical-harm weight; confidence ↓ foreclosure weight within clamps). Add multi-criteria intention votes / veto nudges without a total-reward field. Bias `DeterministicSocialMessagePolicy` toward attachment/anger/anxiety-consistent talk/ask/tell preferences via closed codes only. PASSTHROUGH and None leave existing V1 math unchanged. Keep `EmotionKind.FEAR` distinct from `RelationshipDimension.FEAR` in code and tests.
  - Expected behavior: Identical observation + goals + drives + memories, differing only in emotional state → different selected intention/command and/or communication choice under ENABLED.
  - Files: `src/agents/cognition/contracts.py`, `src/agents/cognition/imagination.py`, `src/agents/cognition/motivation.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/defaults.py` (planner), `src/agents/cognition/communication.py`, `src/agents/cognition/loop.py`, `tests/unit/test_emotional_influence_hooks.py`.
  - Logging requirements: DEBUG reason codes like `emotion_risk_scale`, `emotion_intention_vote`, `emotion_social_bias` with kind bands only — never utterance text.
  - Dependencies: Tasks 2, 5, 6.

- [x] Task 10: Version agent/checkpoint codecs for emotional state (accepted-set discipline).
  - Deliverable: Encode/decode `AgentRuntime` emotional carry via agent/checkpoint serialization paths (exact key-set write version; intentional legacy decode defaults: missing emotion → empty state). Fail closed on unknown versions. Do **not** bump `subjective_serialization` unless that envelope already owns the field. Do not add Alembic tables. Flags-off runs omit or empty-encode harmlessly.
  - Expected behavior: Live/restored parity for emotional vector when durable resume is used; in-memory multi-tick works without durable path.
  - Files: `src/simulation/serialization.py` (and/or agent checkpoint helpers used by persistence), `tests/unit/test_v1_domain_serialization.py` / checkpoint restore tests as applicable.
  - Logging requirements: DEBUG encode/decode version + kind_count only.
  - Dependencies: Task 7.

- [x] Task 11: Update cognition-trace emotional projection to prefer live stage.
  - Deliverable: When `ComponentKind.EMOTIONAL_STATE` completed with intensities, project kind refs, intensity bands, driver reason codes, and counts into `CognitionTraceStageKind.EMOTIONAL_STATE`. Map the component in `_COMPONENT_TO_TRACE` as appropriate without breaking the fixed scientific sequence. Fall back to existing drive/salience projection only when stage missing/PASSTHROUGH-neutral. Keep tracing non-authoritative and outside the objective fold.
  - Expected behavior: Flag-on + tracing-on shows structured emotion summary; tracing on/off does not change `exact_trajectory_hash`.
  - Files: `src/agents/cognition/trace.py`, `tests/unit/test_cognition_trace_projection.py` (or existing trace tests).
  - Logging requirements: Existing trace allowlist only (kinds, bands, counts, reason codes).
  - Dependencies: Tasks 6, 7.

### Phase 4: Controlled Tests and Docs

- [x] Task 12: Unit tests for decay/regulation and driver transitions.
  - Deliverable: Table-driven tests beyond Task 5 smoke coverage: per-kind decay over N ticks toward baseline; clamp at ceilings; disabled kinds ignored; each driver code (including GoalBoard failure/progress intents) produces expected directional deltas; determinism; ownership fail-closed; no prose fields on artifacts; relationship-fear driver does not type-confuse with `EmotionKind.FEAR`.
  - Expected behavior: Stable quantized outputs; reason-code sets match drivers applied.
  - Files: `tests/unit/test_emotional_state_engine.py`, `tests/unit/test_emotional_state_models.py`.
  - Logging requirements: Capture logs and assert allowlisted keys only.
  - Dependencies: Task 5.

- [x] Task 13: Controlled divergence tests — identical objective situation, different prior emotion.
  - Deliverable: Construct two cognition invocations with **byte-identical** `Observation` (and same goals/drives/memory store contents) but different seeded prior `AgentEmotionalState` under ENABLED (seed via runtime/perspective). Assert divergent retrieval ranking and/or selected `AgentCommand` / communication choice. Add a third PASSTHROUGH/flag-off control where both priors collapse to identical commands. Prefer pure unit tests with fakes (no Docker).
  - Expected behavior: Proves emotion is causal for behavior independently of objective world state.
  - Files: `tests/unit/test_emotional_state_behavior_divergence.py`.
  - Logging requirements: Assert DEBUG includes emotion bias reason codes when ENABLED; absent when PASSTHROUGH.
  - Dependencies: Tasks 7, 8, 9.

- [x] Task 14: Capability gating and V1 regression proofs.
  - Deliverable: Tests that (a) enabling unowned flags still fails closed; (b) enabling only `short_term_emotional_state` constructs and changes behavior vs flag-off for a minimal threat scenario; (c) runner JSON round-trips the fifth capability key; (d) `tests/unit/test_v1_regression_gate.py` remains green flags-off/tracing-off; (e) import-linter / architecture isolation still pass. Inverse of goal-management’s “not a capability flag” test: assert emotional state **is** gated by the owned flag.
  - Expected behavior: Flag-off bit-identical to V1 reference for regression profile; flag-on is opt-in only.
  - Files: `tests/unit/test_runner_models.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_v1_regression_gate.py`, architecture tests as needed.
  - Logging requirements: Assert construction ERROR reason_code for unimplemented flags.
  - Dependencies: Tasks 3, 4, 9, 13.

- [x] Task 15: Documentation checkpoint (`/aif-docs`).
  - Deliverable: Update `docs/cognition-runtime.md` pipeline diagram and policy table for emotional stage + flag mapping; clarify V1 salience vs V2 short-term state; document situation-focus (not a separate attention engine); note `EmotionKind` vs `RelationshipDimension.FEAR`; logging allowlist and non-goals. Cross-link Downstream V2 contract / owned capability flag. Keep README lean.
  - Expected behavior: Contributors can enable the flag and understand decay/drivers/influence surfaces without reading the plan.
  - Files: `docs/cognition-runtime.md`, optionally `docs/architecture.md` (V2 extension seams / owned flags), `docs/memory-reconstruction.md` (salience vs live emotion note).
  - Logging requirements: N/A (docs).
  - Dependencies: Tasks 6–11.

## Implementation Notes

- Prefer extending GoalManager-style patterns (`Cognition*Mode`, stage protocol, versioned policy, PASSTHROUGH, constructor injection) over inventing a plugin system.
- Keep emotion out of `world` and `analysis` live paths; analysis may later read durable checkpoint exports if codecs exist — out of scope unless needed for tests.
- Quantize all intensity math with `quantize_score` / `SCORE_QUANTUM` for cross-platform determinism.
- Do not feed analysis metrics or ground-truth event stores into the emotional engine.
- Deferred (out of scope here): a dedicated attention / perceptual-filter subsystem beyond situation-focus claim weights and retrieval bias.
