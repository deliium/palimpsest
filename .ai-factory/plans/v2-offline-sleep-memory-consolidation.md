# Implementation Plan: Offline Memory Consolidation During Sleep

Branch: main
Created: 2026-09-25
Improved: 2026-09-25 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M5.5 — Offline Memory Consolidation During Sleep"
Rationale: Registered after implementation (2026-09-25). Opt-in `ConsolidationMode` only; M6 remains open for remaining `V2CapabilityFlags`.

## Compatibility contract

This plan adds opt-in offline consolidation that runs in agent cognition when the effective command is `Sleep`. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only authority for the physical `Sleep` effect (`Slept`, fatigue recovery). Cognition still sees one immutable `Observation` and never `WorldState`, `WorldEvent` stores, or another agent's memory.
2. Capability flags unchanged. Do not add or own a `V2CapabilityFlags` field. `short_term_emotional_state` stays the only owned flag. Reserved flags still fail closed with `capability_unimplemented`. Consolidation is `ConsolidationMode` on `AgentCognitionSpec`, default `DISABLED`.
3. V1 regression gate stays green under flags-off, tracing-off, and default `ConsolidationMode.DISABLED`. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment F is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bumps use accepted-set + exact key-set discipline. The default write stays `runner-config-v4` with the current cognition key set and no `consolidation_mode` key. `runner-config-v5` is emitted only when some agent’s mode is not `DISABLED`, and its cognition objects require `consolidation_mode`. v1–v4 restore to `DISABLED` and reject that key. A non-disabled mode on a v4 config fails closed.
5. No scripted emergence, no friend/enemy/leader labels, and no free-form sleep narration as authority.
6. No LLM → world shortcuts. LLM output may only select among deterministic candidate IDs. It never becomes an `AgentCommand` and never mutates world state.
7. Experiments stay reproducible. Experiment F arms share seed, world, and stochastic identity. LLM tests use a deterministic fake provider.
8. Optional cognition tracing stays outside the objective fold. This plan does not add a `CognitiveLoop` ordinal and does not bump the cognition-trace schema or Alembic. Tracing on versus off must not change `exact_trajectory_hash` when consolidation is disabled.

## Goal

When an agent sleeps, optional cognitive maintenance may reorganize information the agent already holds:

- episodic consolidation
- strengthening and weakening memory traces
- semantic belief formation from repeated patterns
- merging repeated patterns
- forgetting low-relevance details
- relationship reflection
- goal maintenance
- self-model updates via owner-referential beliefs

Sleep does not reveal objective truth. A false memory stays false unless the agent already holds later subjective evidence that the existing belief policy would accept. Consolidation never reads the world, analysis reports, or other agents' stores to correct a trace.

Experiments configure three closed treatments:

| Treatment | `ConsolidationMode` | Behavior |
| --- | --- | --- |
| Disabled (default) | `DISABLED` | Physical sleep only. Subjective path matches today. |
| Deterministic | `DETERMINISTIC` | Pure policy over owner-scoped traces, beliefs, relationships, and goals. |
| LLM-assisted | `LLM_ASSISTED` | Same candidate set; provider may only select candidate IDs. Invalid or missing provider falls back to the deterministic selection. |

Physical sleep stays in `WorldEngine` (`Sleep` / `_SleepOp` / `_mutate_sleep` / `Slept`). Cognitive consolidation belongs to agent cognition and `AgentRuntime` finalize.

## Design Decisions (locked by `/aif-improve`)

- **Trigger.** Run consolidation only when `CognitiveLoop.complete` receives an effective command whose type is `world.actions.Sleep`, the agent is not terminal, and `CognitionConsolidationMode` on `CognitionLoopConfig` is not `DISABLED`. The loop must not import `simulation`. `Wait` does not consolidate. `IntentionCode.REST` consolidates only because it already compiles to `Sleep()`. Trusted intervention that replaces `Sleep` skips consolidation. Intervention that forces `Sleep` consolidates.
- **Timing.** Build consolidation intents during `complete`, after the memory-update stage, from `proposal.loop_input.snapshot` plus this invocation’s not-yet-stored `WRITE_MEMORY` intents. Do not call `MemoryService` from the pure policy or from the loop. Persist them only inside the existing `finalize_pending` path after `resolve_tick` succeeds. A failed or skipped objective tick leaves subjective stores unchanged.
- **No new loop stage.** Do not insert an ordinal into `_STAGE_ORDER`. Disabled mode must not add boundary records, trace envelopes, or objective events. Physical fatigue recovery remains unconditional for an admitted `Sleep` and does not depend on consolidation mode.
- **Layered inputs.** `memory/consolidation.py` sees only this owner’s `MemoryTrace` values and belief-formation candidates. `agents.cognition` builds the orchestration context from `SubjectiveSnapshot` (memories, semantic beliefs, relationships, goals) and the prepare-stage `SelfModel`. `memory` does not import `social` or `agents.cognition`. The context must not accept `WorldState`, `WorldEvent`, event repositories, analysis DTOs, `RecallAuditRecord`, or another owner’s IDs.
- **Outputs reuse current writers.** Strengthening appends `MemoryAccessReceipt` values with deterministic `operation_id` `offline-consolidation:{tick}:{memory_id}` (existing idempotency; no new reason field and no migration). Weakening withholds that receipt. Whole-trace forgetting stamps `forgotten_at_tick` only on selected IDs, in memory and with an ID-filtered SQL update. Do not call `MemoryService.forget` / `MemoryForgetRequest` (that path sweeps the whole store under `MemoryRetentionPolicy`). Merging uses append-only derived traces (`plan_reconsolidation` or the same lineage rules): parents stay active, generation stays dense, and derived fragments are copied only from cited sources. Beliefs and relationships reuse `BeliefRevisionRequest` and `RelationshipRevisionRequest`. Goals reuse `GoalTransitionIntent` and the existing `GoalTransitionIntentReason` set. No second belief, relationship, or goal store.
- **Detail forgetting.** `ConceptMention` has no salience. A derived gist keeps concepts, entities, and relations that occur in more than one cited source and drops fragments that occur in only one. Parents keep their stored content until a selected soft-forget.
- **Operation order.** Score → form belief candidates from repeated patterns → merge eligible clusters → strengthen selected survivors → soft-forget selected low-retention IDs → relationship revisions and goal intents only for traces this same pass merged or selected to forget. Deadline and parent-status maintenance stay on the existing goal stage. Do not form beliefs from material that this pass has already forgotten. An empty episodic selection yields zero relationship and goal counts.
- **Self-model.** Do not persist `SelfModel` and do not enable `extended_self_model`. Owner-referential belief revisions are the update. The next `SELF_STATE` projection reflects them.
- **Orthogonal to `MemoryMode`.** Consolidation reads stored traces on the snapshot. It does not require `RECONSTRUCTIVE_V2`, does not retune `memory/dynamics.py`, and does not read recall audits. `MEMORY_POLICY_VERSION` and `COGNITION_POLICY_VERSION` stay unchanged.
- **LLM grounding.** Deterministic policy always materializes a closed candidate set first (`offline-consolidation-v1`). `LLM_ASSISTED` sends only IDs, counts, and closed reason codes in a versioned prompt package `llm/prompts/offline_consolidation/v1/`. Structured output `offline_consolidation.selection.v1` has ID lists and no prose claim field. Any ID outside the candidate set, any new entity, or any schema failure discards the provider selection and applies the deterministic selection. The policy field `allow_provider` stays false except when the runner builds the `LLM_ASSISTED` policy. Belief text the agent later stores still comes from existing `belief_formation` gists of cited traces, never from model prose.
- **Schema.** Add `ConsolidationMode` on `AgentCognitionSpec` and lockstep `CognitionConsolidationMode` on `CognitionLoopConfig`. Keep `RUNNER_SCHEMA_VERSION` as `runner-config-v4`. Add `runner-config-v5` to the accepted set and emit it only when some agent is not `DISABLED`. Keep result schema `runner-result-v2`.
- **Audits.** `OfflineConsolidationAudit` (owner, tick, mode, counts, memory/belief/relationship/goal IDs, reason codes) is in-run and analysis-only. Attach the tuple on `SimulationRunnerResult` the same way as `memory_dynamics_audits`. Do not place audits on `RetrievedMemoryContext`, observations, prompts, or the result JSON document. No Alembic journal.
- **Experiment F.** `experiment_f_sleep_consolidation` with two arms, `f-disabled` (`DISABLED`, schema v4) and `f-deterministic` (`DETERMINISTIC`, schema v5), otherwise identical. Initial fatigue is high enough that both arms select `Sleep` on the same tick before subjective divergence can change the command. `LLM_ASSISTED` is covered by a runner/cognition test with a fake provider, not by a networked catalog arm.
- **Fail closed.** Unknown mode strings, owner mismatches, non-finite policy knobs, and candidate-set violations abort with stable reason codes. Disabled mode performs no consolidation calls.

## Non-Goals

- Owning or adding a `V2CapabilityFlags` entry for sleep or consolidation
- Multi-tick sleeping, shelter-gated sleep, or changing `_mutate_sleep` fatigue rules
- Hard-deleting memory rows
- Correcting memories against world state, analysis truth, or other agents
- A persisted self-model table or personality traits
- A new `CognitiveLoop` stage, cognition-trace schema bump, or Alembic revision
- Wiring LLM provider lifecycle into the API or `compose.yaml`
- Putting Experiment F on the V1 regression gate
- Feeding consolidation audits back into live planning

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(memory): add offline consolidation contracts and deterministic episodic policy`
- **Commit 2** (after tasks 4–6): `feat(cognition): consolidate owner memory when sleep is the effective command`
- **Commit 3** (after tasks 7–9): `feat(experiments): compare agents with and without sleep consolidation`

## Tasks

### Phase 1: Contracts, Schema, and Deterministic Policy

- [x] Task 1: Add closed consolidation modes, episodic policy types, and audits.
  - Deliverable: Add `ConsolidationMode` (`DISABLED`, `DETERMINISTIC`, `LLM_ASSISTED`) in `src/simulation/runner_models.py` and lockstep `CognitionConsolidationMode` in `src/agents/cognition/configuration.py`. Add frozen `OfflineConsolidationPolicy` version `offline-consolidation-v1` with quantized knobs for cluster similarity, strengthen retention floor, and soft-forget threshold. `allow_provider` defaults false. Add episodic-only `OfflineConsolidationCandidateSet`, `OfflineConsolidationSelection`, and `OfflineConsolidationAudit` (IDs, counts, closed reason codes only) in `memory`. Do not put `GoalBoard`, `SelfModel`, or relationship profiles in `memory`. Trace construction rejects a foreign owner. Invalid knobs fail closed. Default mode is `DISABLED`.
  - Expected behavior: Disabled is the default. Audits and selections are safe to `repr` without propositions, narratives, or relationship assessments. Import-linter still forbids `memory` → `social` and `memory` → `agents.cognition`.
  - Files: `src/simulation/runner_models.py`, `src/agents/cognition/configuration.py`, `src/memory/models.py`, `src/memory/__init__.py`, `tests/unit/test_offline_consolidation_models.py`.
  - Logging requirements: Model modules stay log-free. DEBUG construction in later wiring may log mode and policy version only. ERROR on invalid mode uses a stable reason code. Never log trace text, beliefs, prompts, or payloads. Levels follow `PALIMPSEST_LOG_LEVEL`.
  - Dependencies: None.

- [x] Task 2: Accept `runner-config-v5` only when consolidation is enabled.
  - Deliverable: Add `RUNNER_SCHEMA_VERSION_V5 = "runner-config-v5"` to `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. Leave `RUNNER_SCHEMA_VERSION` as `runner-config-v4`. Version-branch `_encode_cognition` / `_decode_cognition`: v1–v4 omit `consolidation_mode`, restore `DISABLED`, and reject the key if present; v5 requires it. A config whose schema is v4 and whose any agent mode is not `DISABLED` fails closed (`consolidation_mode_requires_v5`). Update `simulation.compatibility` so the default write stays v4, v5 is accepted, and the fixture note says A–E fingerprints stay on v4. Add the field to `AgentCognitionSpec` and `CognitionLoopConfig` with fail-closed type checks. `_cognition_config_for` copies the spec mode into `CognitionConsolidationMode`. Export new public names through existing facades and `__all__`.
  - Expected behavior: Golden v1–v4 configs still decode and their `runner_config_fingerprint` / `cognition_fingerprint` stay unchanged when mode is `DISABLED`. `tests/unit/test_v1_regression_gate.py` still sees `RUNNER_SCHEMA_VERSION_V4`. A v5 document round-trips `consolidation_mode`. Unknown strings fail closed. `COGNITION_POLICY_VERSION` remains `cognition-policy-v1`. Flags and trace behavior stay unchanged.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/agents/cognition/configuration.py`, facade `__init__.py` files as needed, `tests/unit` runner serialization and compatibility tests. Do not retarget the V4 pins in `test_v1_regression_gate.py`, `test_runner_serialization.py`, or `test_runner_models.py`.
  - Logging requirements: DEBUG `runner_config_decoded` may include schema version and consolidation mode string. ERROR `invalid_enum` / `invalid_fields` with path and reason code. Never log scenario payloads or DSN material.
  - Dependencies: Task 1.

- [x] Task 3: Implement the deterministic episodic and belief policy.
  - Deliverable: Add pure `src/memory/consolidation.py`. Given this owner’s traces and policy, emit a candidate set and the deterministic selection: clusters of similar traces, belief candidates produced only through existing `belief_formation` extractors over those traces, merge groups, strengthen IDs, and soft-forget IDs. The derived gist keeps concepts, entities, and relations that occur in more than one cited source. Merge lineage follows dense generation and does not deactivate parents. Quantize floats with the existing score quantum. No RNG, wall clock, or Python `hash()`. Do not import `social`, `agents.cognition`, or `simulation`. Do not call `MemoryService.forget`. A false communicated trace is not rewritten toward any fact absent from the owner’s traces.
  - Expected behavior: Identical inputs yield identical selections. Repeated similar episodes propose a merge whose gist omits a concept that appears on only one source, plus a belief candidate. A low-retention trace is selected for soft-forget. An isolated false memory is not replaced with a different claim. `DISABLED` is not handled here; callers skip the module.
  - Files: `src/memory/consolidation.py`, `src/memory/__init__.py`, `tests/unit/test_offline_consolidation_policy.py`.
  - Logging requirements: Pure module stays log-free. Tests may assert later orchestration metadata, not payload logs.
  - Dependencies: Task 1.

### Phase 2: Cognition, Sleep Trigger, and LLM Selection

- [x] Task 4: Orchestrate relationship reflection, goal maintenance, and self-model belief selection.
  - Deliverable: Add `src/agents/cognition/consolidation.py`. Build the cognition context from `SubjectiveSnapshot` plus the prepare-stage `SelfModel`. Call the Task 3 policy on snapshot memories combined with this invocation’s `WRITE_MEMORY` traces. After that episodic selection, emit `RelationshipRevisionRequest` values and `GoalTransitionIntent` values only for traces this pass merged or selected to forget, using the existing `GoalTransitionIntentReason` set. Do not re-emit deadline or parent-status transitions already owned by `HierarchicalGoalManager`. Self-model update means keeping belief candidates whose claims already reference the owner under the current `SelfModelProjectionPolicy`; do not write a self-model record. An empty episodic selection produces an audit with zero relationship and goal counts.
  - Expected behavior: Reflection cannot create the reverse relationship edge. Goal intents do not mark objective success. A sleep pass with no merge and no forget does not revise relationships or goals. Self-model projection on the next cycle changes only when owner-referential beliefs changed. Empty stores yield an empty selection and an audit with zero counts.
  - Files: `src/agents/cognition/consolidation.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_offline_consolidation_orchestration.py`.
  - Logging requirements: DEBUG `offline_consolidation_candidates` with owner id, tick, mode, and counts (traces, merges, forgets, beliefs, relationships, goals). WARN on truncated candidate windows with the cap and omitted count. ERROR on owner mismatch with reason code `owner_mismatch`. Never log propositions, goal text, or dimension assessments.
  - Dependencies: Task 3.

- [x] Task 5: Run consolidation only for an effective `Sleep` and commit it in finalize.
  - Deliverable: In `CognitiveLoop.complete`, after the memory-update stage, call the orchestrator only when the effective command type is `Sleep`, the agent is not terminal, and `CognitionConsolidationMode` is `DETERMINISTIC` or `LLM_ASSISTED`. Do not import `simulation` from the loop. Pass snapshot memories plus this invocation’s `WRITE_MEMORY` intents. Thread results on the existing pending subjective batch: `MemoryAccessReceipt` values (`operation_id` `offline-consolidation:{tick}:{memory_id}`), derived traces, selected-ID soft-forgets, belief revisions, relationship revisions, and goal intents. `AgentRuntime.finalize_pending` applies them through current `SubjectiveStateService` / memory / goal paths after successful `resolve_tick`. Add an ID-filtered soft-forget on `MemoryService` and the SQL adapter that stamps `forgotten_at_tick` for those IDs only. Do not call `MemoryForgetRequest`. Attach `offline_consolidation_audits` on the in-memory `SimulationRunnerResult` the same way as `memory_dynamics_audits`, without a `runner-result` schema bump. Do not modify `world/_rules.py`, admission, or `_mutate_sleep`. `DISABLED` adds no consolidation calls and no new boundary records.
  - Expected behavior: Disabled sleep still emits `Slept` and the usual fatigue delta, with unchanged subjective stores aside from ordinary observation encoding, and catalog configs stay `runner-config-v4`. Deterministic sleep strengthens, merges, or soft-forgets only the selected IDs, then the next tick can recall the derived gist. A repeated finalize with the same access `operation_id` does not increment `access_count` again. If resolve fails, pending consolidation is dropped. `Wait` never consolidates.
  - Files: `src/agents/cognition/loop.py`, `src/simulation/agent_runtime.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/memory/service.py`, `src/memory/contracts.py`, `src/persistence/memory_sqlalchemy.py`, `tests/unit/test_sleep_consolidation_runtime.py`.
  - Logging requirements: INFO `offline_consolidation_skipped` with reason `disabled`, `not_sleep`, or `terminal` (ids and tick only). DEBUG `offline_consolidation_pending` and `offline_consolidation_applied` with counts and mode. ERROR `offline_consolidation_aborted` with reason code when apply fails; do not attach trace bodies. World sleep resolution logs stay unchanged.
  - Dependencies: Tasks 2 and 4.

- [x] Task 6: Add LLM-assisted selection over the deterministic candidate set.
  - Deliverable: Add prompt package `src/llm/prompts/offline_consolidation/v1/` (`manifest.json`, `system.txt`, `user.txt`) and schema `offline_consolidation.selection.v1` containing only candidate-ID lists. `LLMOfflineConsolidationSelector` in `src/agents/cognition/consolidation.py` calls `LLMProvider.generate` only when mode is `LLM_ASSISTED`. The runner sets `allow_provider=True` only for that mode; `DISABLED` and `DETERMINISTIC` keep it false and never call the provider. Validate that every returned ID is in the candidate set. On missing provider, disallow, transport error, schema failure, or foreign ID, apply the deterministic selection and record `fallback_used`. Inject the provider the same way as `LLMMemoryReconstructor`; do not compose providers in API lifespan.
  - Expected behavior: A fake provider that returns a legal subset changes which candidates apply and still cannot introduce a new memory id or a prose claim. A fake provider that returns an unknown id falls back with no extra writes. `LLM_ASSISTED` without a bound provider falls back and still sleeps.
  - Files: `src/llm/prompts/offline_consolidation/v1/*`, `src/agents/cognition/consolidation.py`, `src/simulation/runner.py`, `tests/unit/test_offline_consolidation_llm.py`, `tests/fakes/` as needed.
  - Logging requirements: Use stdlib logging on `agents.cognition.consolidation`. DEBUG `offline_consolidation_llm_start` / `_complete` with prompt version, schema version, candidate counts, selected counts, `used_provider`, `fallback_used`. ERROR `offline_consolidation_llm_rejected` with reason code `foreign_id`, `schema_invalid`, or `provider_error`. Never log prompts, completions, or candidate narratives. Match the `llm` metadata allowlist. Tests that assert these records filter `caplog` to `agents.cognition.consolidation`.
  - Dependencies: Tasks 4 and 5.

### Phase 3: Experiment, Metrics, and Docs

- [x] Task 7: Add Experiment F comparing consolidation off and on.
  - Deliverable: Add `experiment_f_sleep_consolidation` in `src/experiments/catalog.py` with arms `f-disabled` (`ConsolidationMode.DISABLED`, `runner-config-v4`) and `f-deterministic` (`DETERMINISTIC`, `runner-config-v5`). Arms share seed, scenario, and stochastic identity via the existing catalog builders. Extend `_with_agent_modes` (or the local equivalent) to override consolidation mode without changing memory, imagination, drives, or capability flags. Set initial fatigue so both arms' effective command is `Sleep` on the same early tick. Export the builder from `src/experiments/__init__.py`. Do not add the experiment to the V1 regression catalog tuple in `tests/unit/test_v1_regression_gate.py`.
  - Expected behavior: Both arms sleep on that tick and record the same fatigue effect. The disabled arm stays schema v4 with no consolidation audit. The deterministic arm is schema v5 and, after finalize, its audit counts differ (at least one of merge, belief revision, strengthen, or soft-forget under the fixture). Later ticks may diverge. Re-running either arm is deterministic.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_experiment_definitions.py`, `tests/unit/test_sleep_consolidation_experiment.py`.
  - Logging requirements: Experiment construction DEBUG logs experiment id, condition ids, and consolidation mode strings only.
  - Dependencies: Task 5.

- [x] Task 8: Export in-run consolidation audits and add metric family `offline_consolidation@1`.
  - Deliverable: Harvest `SimulationRunnerResult.offline_consolidation_audits` (Task 5) the same way collectors read `memory_dynamics_audits`. Map the tuple through `experiments.composition` into a neutral report on `MetricComputationInputs`. Do not add the audits to the `runner-result-v2` JSON document. Add `MetricFamilyId` for offline consolidation, bump `METRIC_FAMILY_COUNT` from 16 to 17, and update `_BUILDERS` plus catalog validation tests. Implement `src/analysis/offline_consolidation_metrics.py` with quantized values `consolidation_invocations`, `traces_strengthened`, `traces_soft_forgotten`, `patterns_merged`, `belief_revisions`, `relationship_revisions`, and `goal_transitions`. Empty or disabled input follows the catalog's existing absent/empty convention. Metrics stay in `analysis` and are not imported by cognition or memory formation.
  - Expected behavior: The disabled arm contributes zeros or an absent report per spec. The deterministic arm reports counts that match its audits. V1 catalog assembly still succeeds when the report is missing.
  - Files: `src/analysis/specifications.py`, `src/analysis/offline_consolidation_metrics.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `src/experiments/composition.py`, `src/experiments/collectors.py`, `tests/unit/test_metric_specifications.py`, metric fixture tests.
  - Logging requirements: DEBUG `offline_consolidation_metrics_assembled` with family id and which value keys are present. Never log belief text or memory content.
  - Dependencies: Tasks 5 and 7.

- [x] Task 9: Prove consolidation cannot import objective truth, and document the behavior.
  - Deliverable: Add a fixture where the owner holds a false communicated trace and the world state disagrees. After deterministic sleep, stored provenance and the false content remain, and no new fragment appears that existed only in world state. Add an assertion that `WorldEngine.resolve_tick` on `Sleep` does not call memory or cognition consolidation (import/architecture boundary or a seam spy — prefer the existing import-linter / architecture tests if a rule already separates `world` from `memory`). Update `docs/memory-reconstruction.md`, `docs/cognition-runtime.md`, `docs/experiments.md`, `docs/analysis-metrics.md`, and a short note in `docs/physical-simulation.md` that fatigue recovery is independent of consolidation mode. This task is the documentation checkpoint for Docs: yes; keep the docs aligned with shipped behavior and route wording through `/aif-docs` during implementation.
  - Expected behavior: The false-memory fixture fails if consolidation reads world truth. Docs describe the mode table, the sleep trigger, LLM candidate restriction, and Experiment F. `test_v1_regression_gate.py` passes without Experiment F.
  - Files: `tests/unit/test_offline_consolidation_no_truth.py`, architecture test module if a boundary assertion is added, `docs/memory-reconstruction.md`, `docs/cognition-runtime.md`, `docs/experiments.md`, `docs/analysis-metrics.md`, `docs/physical-simulation.md`.
  - Logging requirements: Tests may assert metadata fields (`mode`, `fallback_used`, counts). They must not require payload logging. Docs describe the metadata-only allowlist for the new event names.
  - Dependencies: Tasks 5–8.

## Verification checklist

- [x] Default `ConsolidationMode.DISABLED`; default write stays `runner-config-v4`; A–E trajectory hashes and v4 fingerprints stay unchanged
- [x] `runner-config-v5` is accepted only when some agent is not `DISABLED`, and that document requires `consolidation_mode`
- [x] `V2CapabilityFlags`, cognition-trace schema, and `runner-result-v2` are unchanged; no new Alembic revision
- [x] Consolidation runs only for effective `Sleep` and commits only after a successful tick
- [x] `WorldEngine` still owns fatigue recovery and does not call memory
- [x] Deterministic passes use only owner-scoped subjective inputs and do not correct false memories from world state
- [x] `LLM_ASSISTED` selects only candidate IDs and falls back when validation fails
- [x] Experiment F compares `f-disabled` and `f-deterministic` under a shared seed and a shared sleep tick
- [x] `offline_consolidation@1` assembles from audits; missing reports do not break V1 metric assembly
- [x] Logs for the new path are metadata-only
