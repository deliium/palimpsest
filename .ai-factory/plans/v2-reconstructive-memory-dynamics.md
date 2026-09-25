# Implementation Plan: V2 Reconstructive Memory Dynamics

Branch: main
Created: 2026-09-24
Improved: 2026-09-24 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M5.4 — Reconstructive Memory Dynamics"
Rationale: Registered after implementation (2026-09-25). Opt-in `MemoryMode.RECONSTRUCTIVE_V2` only; M6 remains open for remaining `V2CapabilityFlags`.

## Compatibility contract

This plan extends owner-scoped reconstructive memory with an opt-in **V2 dynamics profile** behind `MemoryMode.RECONSTRUCTIVE_V2`. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact (WorldEngine authority, Observation trust, subjective ≠ objective fold, no CoT/payload logging, no LLM→world shortcuts).
2. Capability flags unchanged — this plan does **not** add or own a `V2CapabilityFlags` entry. Existing owned flag `short_term_emotional_state` and unimplemented reserved flags behave exactly as today. Memory treatment remains `MemoryMode` on `AgentCognitionSpec` / runner agent specs.
3. V1 regression gate stays green under flags-off **and** tracing-off **and** default `MemoryMode.RECONSTRUCTIVE` (V1 basic). The gate must **not** require a healthy V2 arm: pin reference + V1 reconstructive only (see Task 8). V2 arms are separate catalog/tests; they must not alter V1-arm `exact_trajectory_hash`.
4. Schema bumps use accepted-set + exact key-set discipline (`MemoryMode` / `CognitionMemoryMode` enum value addition; runner agent-spec JSON accepts the new mode string; legacy documents without V2 mode remain valid).
5. No scripted emergence / no friend-enemy labels / no free-form memory narration from LLMs as authority.
6. No LLM → world shortcuts; reconstruction remains non-authoritative; memory never mutates `WorldState` or appears in objective events as truth.
7. Experiments remain reproducible under deterministic fakes; catalog A–E default arms stay reference + V1 reconstructive for regression; V2 is an explicit additional Experiment A catalog arm.
8. Optional cognition tracing stays outside the objective fold; any memory-dynamics audit/trace fields are structured IDs, counts, and reason codes only — never narratives or concept text.

## Goal

Extend V1 episodic memory into a more realistic **reconstructive** system without simply deleting old rows by age. Under `MemoryMode.RECONSTRUCTIVE_V2`, recall becomes cue-dependent, competitive, decay- and salience-sensitive, and subject to interference, confidence degradation, source confusion, repeated-retrieval effects, and semanticization of repeated experiences — while **complete provenance** remains on stored traces and **memory errors stay auditable** by experiment/analysis infrastructure and **invisible as objective truth** to the agent.

Experiments must be able to compare three closed policies:

| Policy | `MemoryMode` | Behavior |
| --- | --- | --- |
| Perfect / reference | `REFERENCE` | Existing exact/reference retrieval (`ReferenceMemoryRetriever`) |
| Basic V1 reconstructive | `RECONSTRUCTIVE` | Frozen current merge-recall + optional reconsolidation (bit-identical) |
| Advanced V2 | `RECONSTRUCTIVE_V2` | Dynamics engine below (opt-in only; never default) |

Provide metrics hooks for recall accuracy, source confusion, memory survival, interference, and confidence calibration.

## Design Decisions (locked by `/aif-improve`)

- **Policy surface = extend `MemoryMode`, not a capability flag.** Mutually exclusive experiment treatments already live on `MemoryMode` (Experiment A). Adding `RECONSTRUCTIVE_V2` keeps comparison first-class. Default remains `RECONSTRUCTIVE`. Update **`MemoryMode` and `CognitionMemoryMode` in lockstep** (`runner` converts via `CognitionMemoryMode(spec.memory_mode.value)`). Keep `MEMORY_POLICY_VERSION = "memory-policy-v1"` stable — it is the cognition wire version, **not** the V1/V2 dynamics selector.
- **V2 selection carrier on the recall request.** Orchestrator cannot see runner `MemoryMode`. Inject optional `dynamics_policy: MemoryDynamicsPolicy | None` on `MemoryRecallRequest` (None → V1/REFERENCE path; non-None → V2 dynamics). Runner/`ScopedMemoryRetriever` supplies `memory-dynamics-v1` defaults only when mode is `RECONSTRUCTIVE_V2`. No separate `dynamics_policy_id` on agent specs.
- **Freeze V1 path.** When `dynamics_policy is None` and mode is `RECONSTRUCTIVE`, retrieve → evidence → `DeterministicMemoryReconstructor` → optional reconsolidation remains bit-identical (same score quantum, tie-breaks, merge rules).
- **No age-based hard deletes.** Soft-forget via existing `MemoryRetentionPolicy` / `forget` remains. V2 may collapse retrieval strength and reconstructability; source rows stay for audit until explicit soft-forget. Content immutable; only access metadata + append-only lineage/audit may change.
- **Agent vs experiment split (hard gate).** Agent-facing `ReconstructedMemory` may be wrong. True provenance + competitor sets live on traces + **`RecallAuditRecord` on `MemoryRecallResult.audits` only**. Never put audits on `RetrievedMemoryContext`, `ReconstructionRecord` content, or agent perspective. Do **not** invent a `ReconstructionRecord` metadata bag — codecs are closed (`memory/codec.py`).
- **Audit export is mandatory (no Alembic by default).** Current `PersistedReconstructionRow` / composition cannot reconstruct competitor sets or distortion codes. Collect audits in-run (scientific/arm evidence), map through `experiments.composition` into analysis sources, and feed `MetricComputationInputs.memory_dynamics_report`. Durable Alembic audit tables remain a **fallback only** if in-run export proves insufficient — not a required task.
- **Semanticization pending surface (new).** Recall has no belief channel today (beliefs only via `MemoryUpdateIntent.REVISE_SEMANTIC_BELIEF`). Add ownership-checked pending semanticization / belief-revision intent on `RetrievedMemoryContext` → `CognitiveLoopResult` → `AgentRuntime`, parallel to `pending_reconsolidation`. Reuse `SemanticBeliefService` / `belief_formation`; no second belief store.
- **Emotion × V2 ordering (locked).** Dynamics + audit run inside `MemoryService.recall` **first**. Existing `apply_retrieval_emotion_bias` / `apply_reconstruction_emotion_bias` may re-rank **agent-visible** hits/reconstructions afterward when `short_term_emotional_state` is on. Audit `selected_ids` reflect **pre-emotion** competition. Flags-off / PASSTHROUGH leave bias off; this plan does not require the emotion flag.
- **Deterministic V2 engine in `memory/dynamics.py`.** No wall clock, no global RNG, no Python `hash()`, quantized via `quantize_score` / `SCORE_QUANTUM`. Prefer pure functions of cue + trace IDs + tick for confusion/competition so unit tests need no RNG stream. LLM reconstructor path unchanged.
- **Retrieval strength.** Prefer ephemeral/computed strength + access-receipt updates. No immutable-content rewrite. Prefer existing fields before adding selective-mutable columns.
- **Reconsolidation.** Append-only derived traces + reconstruction records; parents never deactivated as a reconsolidation side effect. Audits stay off the reconstruction content hash.
- **SQL path.** Prefer V2 branching inside shared `MemoryRecallOrchestrator` via request `dynamics_policy`. Do not require SQL factory reconstructor injection unless durable audit persistence is later chosen.
- **Experiment A + regression isolation.** Catalog `experiment_a_memory` gains `a-reconstructive-v2`. V1 regression gate must pin **only** `a-reference` + `a-reconstructive` (helper or explicit filter) so a broken V2 path cannot fail V1 hashes.
- **Metrics family.** `MetricFamilyId.MEMORY_DYNAMICS` / `memory_dynamics@1` with values: `recall_accuracy`, `source_confusion`, `memory_survival`, `interference`, `confidence_calibration`. Bump `METRIC_FAMILY_COUNT` 15→16, `_BUILDERS`, docs/tests that say “fifteen”, optional `memory_dynamics_report` on `MetricComputationInputs` (mirror `memory_drift_report`). Collector wiring depends on audit export.
- **Fail closed.** Unknown modes, invalid dynamics knobs, ownership mismatches, non-finite scores abort with stable reason codes.
- **Logging.** Metadata only: mode, policy version, selected/competitor counts, distortion codes, strength deltas, metric assembly. Never narratives, concepts, embeddings, prompts, or fingerprints as payload surrogates.

## Non-Goals

- Adding a `V2CapabilityFlags` entry for reconstructive memory
- LLM-backed reconstructive distortion or new prompt package versions
- Hard-deleting traces solely because of age
- Feeding audit truth, metrics, or analysis reports into live cognition / memory formation
- Collapsing memory dynamics into a single reward scalar
- Free-form confabulation without bounded structured fragments
- Changing WorldEngine admission, Observation trust, or authoritative event immutability
- Owning other reserved V2 capability flags
- HTTP/debug UI for memory audits
- Replacing Experiment A’s V1 arms or changing flags-off regression baselines
- Mandatory Alembic audit migration (fallback only)
- Combined V2+emotion integration tests beyond the locked ordering contract (separate plan may own combo arms)

## Mechanism map (V2 only)

| Mechanism | Behavior | Primary leverage |
| --- | --- | --- |
| Temporal decay | Effective confidence / salience / retrieval strength decline with logical age; no row delete | `scoring.logical_age_ticks`, `retention_strength`, dynamics wrappers |
| Retrieval-strength changes | Strength updates from access receipts and competition outcomes | `access_count`, `last_access_tick`, score breakdown |
| Cue-dependent recall | Cue overlap dominates selection; different cues → different winners/blends | `MemoryQueryContext` + competition |
| Interference | Similar traces suppress each other in the ranked window | `memory/dynamics.py` similarity |
| Competition among traces | Winner-take-most or policy-weighted blend into reconstruction | dynamics + V2 reconstructor |
| Emotional salience | High salience resists decay; biases fragment survival | `MemoryTrace.emotional_salience` |
| Confidence degradation | Reconstruction confidence ≤ / &lt; source aggregate under age, mix, competition | `ReconstructedMemory.confidence` |
| Source confusion | Agent-visible attribution may misattribute; stored provenance exact | `RecallAuditRecord` |
| Repeated retrieval | Retrieved strengthened; competitors weakened | access receipts + strength |
| Semanticization | Repeated similar episodes → pending belief gist intent; episodic discriminability ↓ | pending surface + `belief_formation` |

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(memory): add V2 dynamics contracts, request carrier, and pure engine`
- **Commit 2** (after tasks 4–7): `feat(memory): wire RECONSTRUCTIVE_V2 recall, semanticization pending, emotion ordering`
- **Commit 3** (after tasks 8–10): `feat(experiments): Experiment A V2 arm, audit export, and regression isolation`
- **Commit 4** (after tasks 11–13): `feat(analysis): memory_dynamics metrics, fixtures, and docs`

## Tasks

### Phase 1: Contracts and Dynamics Engine

- [x] Task 1: Extend closed `MemoryMode` / `CognitionMemoryMode` with `RECONSTRUCTIVE_V2` and freeze defaults.
  - Deliverable: Add `RECONSTRUCTIVE_V2 = "reconstructive_v2"` to **both** `simulation.runner_models.MemoryMode` and `agents.cognition.configuration.CognitionMemoryMode` in lockstep. Default remains `RECONSTRUCTIVE`. Keep `MEMORY_POLICY_VERSION` unchanged. Update runner agent-spec encode/decode (enum member is enough — no separate accepted-string frozenset). Update exhaustive construction site `_memory_retriever_for` to accept the new mode only once Task 7 wires it; until then, constructing V2 may fail closed with `INVALID_CONFIG`/`memory_mode` **or** Task 1+7 land in the same commit (prefer Commit 2 for full wire; Task 1 lands enums + serialization + tests that unknown strings still fail closed). Refresh tests that assert a two-mode set (`test_experiment_definitions` will move in Task 8).
  - Expected behavior: Documents round-trip `reconstructive_v2`; defaults still encode `reconstructive`; `CognitionMemoryMode(spec.memory_mode.value)` succeeds for all three values.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, unit tests for models/serialization/configuration.
  - Logging requirements: DEBUG construction may log `memory_mode` string only. ERROR on unsupported mode with stable stage code. Never log memory payloads.
  - Dependencies: None.

- [x] Task 2: Add `MemoryDynamicsPolicy`, `RecallAuditRecord`, and request/result carriers.
  - Deliverable: Frozen `MemoryDynamicsPolicy` (version `memory-dynamics-v1`) with quantized knobs for decay, interference, competition blend, salience resistance, confidence floor, source-confusion mass, testing-effect gain/loss, semanticization thresholds. Closed `MemoryDistortionCode`. Frozen `RecallAuditRecord` (reconstruction_id, owner_id, tick, true `source_memory_ids`, competitor_ids, selected_ids, distortion codes, confidence_before/after, strength delta summaries — IDs/counts only). Add optional `dynamics_policy: MemoryDynamicsPolicy | None = None` on `MemoryRecallRequest`. Add optional `audits: tuple[RecallAuditRecord, ...] = ()` on `MemoryRecallResult` only. **Do not** add metadata to `ReconstructionRecord` or change reconstruction content codecs. Preserve complete `MemoryProvenance` on traces; never rewrite parent provenance to match confused attribution.
  - Expected behavior: Invalid knobs fail closed; V1/REFERENCE leave `dynamics_policy=None` and empty audits; V2 recall with a reconstruction always emits ≥1 audit.
  - Files: `src/memory/models.py`, `src/memory/__init__.py`, `tests/unit/test_memory_dynamics_models.py`.
  - Logging requirements: Models log-free. Safe `repr` with IDs/counts/codes only.
  - Dependencies: None (can parallel Task 1).

- [x] Task 3: Implement pure `memory/dynamics.py` with isolated unit tests.
  - Deliverable: Pure functions implementing: (1) temporal decay of effective confidence/salience/strength; (2) retrieval-strength from age × access × salience; (3) interference from concept/entity/relation overlap; (4) cue-dependent competition → selected + competitors; (5) salience-biased fragment survival; (6) confidence degradation; (7) deterministic source-confusion for **agent-visible** attribution only; (8) testing-effect strength deltas; (9) semanticization trigger (similarity + repeat → bool + gist concept set). Compose into V2 reconstruct helper → `ReconstructedMemory` + `RecallAuditRecord` (+ inputs for reconsolidation / belief intents). Quantize all floats. Unit tests per mechanism + combined interference.
  - Expected behavior: Identical inputs → identical outputs; cue flips winners; similar episodes interfere; salience slows decay; confusion audit ≠ agent attribution; no deletes.
  - Files: `src/memory/dynamics.py`, `src/memory/__init__.py`, `tests/unit/test_memory_dynamics.py`.
  - Logging requirements: Pure module log-free (orchestration logs in Task 4).
  - Dependencies: Task 2.

### Phase 2: Orchestration, Pending Surfaces, Emotion Contract

- [x] Task 4: Wire V2 path in shared recall orchestrator / `MemoryService`; freeze V1; lock Emotion×V2 ordering.
  - Deliverable: When `request.dynamics_policy is not None`, run retrieve → dynamics competition → V2 reconstruct → attach `audits` on `MemoryRecallResult` → optional reconsolidation intent. When `dynamics_policy is None`, existing deterministic reconstructor only (golden/parity vs current fixtures). Branch inside shared `MemoryRecallOrchestrator` so in-memory and SQL recall share behavior; do **not** require SQL reconstructor factory injection. Cognition adapter (`agents.cognition.memory`) continues to map only agent-safe fields into `RetrievedMemoryContext` (strip `audits` / evidence). **Ordering contract:** service recall (dynamics+audit) completes before any `apply_*_emotion_bias` re-ranking; document that audit `selected_ids` are pre-emotion; flags-off bias remains off. `apply` still commits access receipts + reconsolidation atomically.
  - Expected behavior: V1 fixture recalls unchanged; V2 emits audits; agents never see audit objects; emotion bias cannot rewrite stored audits.
  - Files: `src/memory/reconstruction.py`, `src/memory/service.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/emotion_bias.py` (docs/order assertions only if needed), `tests/unit/test_memory_reconstruction.py`, `tests/unit/test_memory_v2_orchestration.py`, `tests/unit/test_emotional_memory_bias.py` (ordering assertion when both enabled).
  - Logging requirements: DEBUG `memory_recall_v2_start/complete` with policy version, source_count, selected_count, competitor_count, distortion_code_counts, pending_reconsolidation bool, emotion_bias_applied bool (from adapter). WARN on truncation. ERROR on ownership/contract failure. Never log narratives/concepts.
  - Dependencies: Tasks 1–3.

- [x] Task 5: Add pending semanticization / belief-revision surface through loop → runtime.
  - Deliverable: Extend `RetrievedMemoryContext` with optional pending semanticization intent (ownership-checked `BeliefRevisionRequest` or thin wrapper). Thread via `CognitiveLoopResult` (parallel to `pending_reconsolidation`). `AgentRuntime` applies it with existing belief-revision apply path after successful cognition finalize. V2 dynamics trigger only (Task 3 predicate); V1 leaves None. Fail closed on owner mismatch. No second belief store — reuse `SemanticBeliefService` / `belief_formation`.
  - Expected behavior: Repeated similar V2 recalls can enqueue one belief revision; REFERENCE/V1 never do; failed cognition leaves beliefs unchanged.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/loop.py`, `src/simulation/agent_runtime.py`, unit tests for pending apply + ownership.
  - Logging requirements: DEBUG semanticization_pending bool, belief_id present bool, owner/tick — never proposition text.
  - Dependencies: Tasks 2–4.

- [x] Task 6: Runner presets for three profiles; inject `dynamics_policy` only for V2.
  - Deliverable: `_memory_retriever_for`: `REFERENCE` → `ReferenceMemoryRetriever`; `RECONSTRUCTIVE` → V1 `ScopedMemoryRetriever` (no dynamics policy); `RECONSTRUCTIVE_V2` → scoped retriever that sets `MemoryRecallRequest.dynamics_policy` to `memory-dynamics-v1` defaults. Soft-forget remains the only deactivation path — V2 must not hard-delete/purge by age. Keep `emotion_bias` construction orthogonal. Construction diagnostics include `memory_mode` + dynamics_policy_version when V2.
  - Expected behavior: Three modes construct; invalid mode fails closed; V1 requests have `dynamics_policy is None`.
  - Files: `src/simulation/runner.py`, `src/agents/cognition/defaults.py` / presets as needed, construction tests.
  - Logging requirements: DEBUG log memory_mode + dynamics_policy_version (or `none`) at bundle construction.
  - Dependencies: Tasks 1, 4.

### Phase 3: Experiments and Audit Export

- [x] Task 7: Extend Experiment A with `a-reconstructive-v2` and isolate V1 regression arms.
  - Deliverable: Add catalog arm `a-reconstructive-v2` / `memory_reconstructive_v2` with `MemoryMode.RECONSTRUCTIVE_V2` to `experiment_a_memory` (three arms sharing seed/world/stochastic identity). Introduce an explicit V1-arm helper or gate filter (e.g. `experiment_a_memory_v1_arms` or condition-id allowlist `a-reference` + `a-reconstructive`) used by `test_v1_regression_gate.py` so the gate **does not** execute the V2 arm. Update `test_experiment_definitions.py` for the three-mode set on the full definition; regression tests assert only two arms run.
  - Expected behavior: Full Experiment A has three arms; V1 regression trajectories unchanged and independent of V2 health.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py` if exporting helper, `tests/unit/test_experiment_definitions.py`, `tests/unit/test_v1_regression_gate.py`, related flag-default tests that enumerate A arms.
  - Logging requirements: Experiment construction logs condition ids/counts only.
  - Dependencies: Task 6.

- [x] Task 8: Wire analysis-only audit export into experiment composition and collectors.
  - Deliverable: Define a neutral in-run audit evidence DTO (IDs/codes/counts only) collected during V2 recalls (runner/scientific sink or arm artifact — **not** agent-visible). Map via `experiments.composition` into analysis sources. Extend Experiment A collectors to populate `MetricComputationInputs.memory_dynamics_report` when audits exist. Do **not** require Alembic; do **not** extend `PersistedReconstructionRow` unless export without durability proves impossible (escalate then — out of default scope).
  - Expected behavior: V2 arm runs produce exportable audits; REFERENCE/V1 produce none; agents still cannot read audits.
  - Files: `src/experiments/persistence.py` (ports only if needed), `src/experiments/composition.py`, `src/experiments/collectors.py`, `src/analysis/sources.py` as needed, collector unit tests.
  - Logging requirements: DEBUG audit_export_count, condition_id — never narratives.
  - Dependencies: Tasks 2, 4, 7.

### Phase 4: Metrics, Fixtures, Docs

- [x] Task 9: Add `memory_dynamics@1` metric family with five hooks and collector input.
  - Deliverable: Add `MetricFamilyId.MEMORY_DYNAMICS`; bump `METRIC_FAMILY_COUNT` 15→16; update `_BUILDERS`, `validate_metric_catalog`, and any “fifteen families” docs/tests. Implement `src/analysis/memory_dynamics_metrics.py` with document values `recall_accuracy`, `source_confusion`, `memory_survival`, `interference`, `confidence_calibration` (canonical quantized floats + defined empty behavior). Add optional `memory_dynamics_report` on `MetricComputationInputs`; assemble when present (mirror drift). Architecture isolation: metrics never flow into cognition.
  - Expected behavior: Known-answer fixtures stable; missing report → empty/ABSENT per spec; V1-only runs assemble without failure.
  - Files: `src/analysis/specifications.py`, `src/analysis/memory_dynamics_metrics.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `tests/unit/test_metric_specifications.py`, `tests/unit/metric_fixtures.py`, assembly tests, isolation tests if needed.
  - Logging requirements: DEBUG family id + value keys present; never fact text.
  - Dependencies: Tasks 2, 8.

- [x] Task 10: Deterministic interference and source-confusion fixtures.
  - Deliverable: Fixtures with two+ similar experiences (overlapping concepts/entities, distinct provenance); different cues select/combine different traces; repeated recall changes relative strength/survival; agent-visible attribution can disagree with audit true sources; confidence calibration moves under degradation. Assert V1 (`dynamics_policy=None`) on the same store does not apply interference blend/confusion. Prefer `InMemoryMemoryService` + fixed ticks/IDs.
  - Expected behavior: Deterministic across runs; expected winner IDs / distortion codes asserted in tests only.
  - Files: `tests/unit/test_memory_dynamics_fixtures.py`, optional analysis known-answer using the same fixture.
  - Logging requirements: Tests may assert metadata log fields; never require payload logging.
  - Dependencies: Tasks 3–4, Task 9 for metric assertions.

- [x] Task 11: Documentation and V1 regression gate green.
  - Deliverable: Update `docs/memory-reconstruction.md` (V2 dynamics, request `dynamics_policy`, agent vs `MemoryRecallResult.audits`, Emotion×V2 ordering, no age-delete, mode table), `docs/experiments.md` (Experiment A third arm + regression arm isolation), `docs/analysis-metrics.md` (`memory_dynamics@1`, sixteen families). Confirm `test_v1_regression_gate.py` passes under flags-off, tracing-off, V1 arms only.
  - Expected behavior: Docs match shipped behavior; regression gate green; V2 described as opt-in mode.
  - Files: `docs/memory-reconstruction.md`, `docs/experiments.md`, `docs/analysis-metrics.md`, regression tests.
  - Logging requirements: N/A for docs; regression tests metadata-only.
  - Dependencies: Tasks 6–10.

## Out of scope (explicit)

- LLM reconstructive distortion / new `reconstructive_memory/v2` prompts
- New capability flag ownership
- Hard purge by age
- Attention subsystem beyond existing emotion/situation-focus hooks
- Changing authoritative replay schemas
- Mandatory Alembic audit tables (fallback only if Task 8 blocked)
- Full V2+emotion combo experiment arms (ordering contract only)

## Verification checklist

- [x] `MemoryMode` and `CognitionMemoryMode` each have three values; default `RECONSTRUCTIVE`
- [x] `MEMORY_POLICY_VERSION` unchanged; V2 selected via `MemoryRecallRequest.dynamics_policy`
- [x] V1 reconstructive recalls bit-identical on frozen fixtures
- [x] V2 produces `MemoryRecallResult.audits`; agents cannot read audits
- [x] Semanticization pending applies via runtime parallel to reconsolidation
- [x] Emotion bias runs after dynamics; audit reflects pre-emotion selection
- [x] No age-based hard deletes in V2 path
- [x] Experiment A includes `a-reconstructive-v2`; V1 regression pins two arms only
- [x] Audit export feeds `memory_dynamics_report`
- [x] `memory_dynamics@1` exposes five named hooks; catalog size 16
- [x] Interference fixtures deterministic
- [x] V1 regression gate green (flags-off, tracing-off)
- [x] Logs metadata-only
