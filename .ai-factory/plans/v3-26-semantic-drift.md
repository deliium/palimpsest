# Implementation Plan: V3-26 Semantic Drift

Branch: main (current branch; `git.create_branches: false`)
Created: 2026-10-18
Mode: full (ultra depth requested)

## Settings

- Testing: yes
- Logging: verbose
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Artifact naming: every plan artifact produced for this feature begins `v3-`; canonical file is `.ai-factory/plans/v3-26-semantic-drift.md`.
- Implementation scope: longitudinal, owner-scoped tracking of what a term or composition has meant over time. A bounded sense history records promotions, referent changes, merged associations, and usage contexts. Detached analysis computes semantic stability, drift, and divergence across time, candidate communities, and generations. **No forced meaning change, no shared dictionary, no world authority for meaning, no new command, no new event, no new runner-config schema, no new capability flag, no new replay/codec pair.**

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"
Rationale: Extends the owned cultural/historical substrate so private vocabulary and composition drift can be measured longitudinally across populations and generations without turning meaning into objective world state.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] full mode confirmed; git.create_branches=false; resolved plan file: .ai-factory/plans/v3-26-semantic-drift.md (format=slug)
INFO [aif-plan] plan_default_milestone=auto surfaces M6 first; explicit V3 scope uses M7, following v3-22/v3-23/v3-24/v3-25 precedent; this plan does not close M6
INFO [aif-plan] ultra request treated as full-mode depth; this skill has no separate ultra mode
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] baseline selectors to recheck before implementation: 43 commands, 73 observer semantic types, 106 metric families, runner-config-v46, replay-v22/codec v20, Alembic 0017, latest Experiment BB

## Goal

Give researchers a longitudinal account of what a term or composition meant to an owner, how that meaning changed, and whether meanings diverged across groups and generations. The engine must not steer evolution: it only records sense states that already occur through ordinary observation, communication, memory, and meaning-shift policy. Three layers stay separate:

- **Objective referent:** opaque entity or occurrence identity observed by the owner.
- **Subjective sense:** the owner's current referent hypothesis, confidence, and associated concept digests.
- **Analytical distribution:** detached, digest-only summaries of stability, drift, and divergence. They never re-enter cognition and never assert that one meaning is correct.

A term may legitimately keep its meaning for the whole run, shift once, or differ between populations. All three outcomes are valid. The plan fails if it forces convergence or treats divergence as a defect.

## Current Implementation Evidence

- **Naming already models sense change.** `src/agents/cognition/semantic_naming.py` owns `TerminologyLedger`, `LabelBinding`, `NamingCandidate`, `NamingEvidenceItem`, `sense_revision`, `meaning_shift_streak`, `last_tick`, and the locked `semantic-naming.v1` policy. `_meaning_shift` increments `sense_revision` but keeps only the current candidate set and the revision count, so the history of prior senses is lost.
- **Symbolic composition already models sense change.** `src/agents/cognition/symbolic_language.py` owns `SymbolicComposition`, `SymbolicReferentHypothesis`, `SymbolicEvidenceItem`, `sense_revision`, `meaning_shift_streak`, and the locked `symbolic-language.v1` policy. `_meaning_shift` likewise increments a revision counter without retaining prior referent states.
- **Current analysis is snapshot-based.** `src/analysis/semantic_naming_metrics.py` computes `emergent_semantic_naming@1` from one caller-supplied binding snapshot. Its `meaning_shift_rate`, `label_turnover_rate`, and `extinction_rate` describe the final snapshot only. `src/analysis/symbolic_language_metrics.py` owns three snapshot families and does not expose a per-tick sense timeline.
- **Detached rows already carry group context.** `src/experiments/composition.py` harvests naming borrowing rows, symbolic composition rows, candidate-community membership, and generation-index maps. `src/analysis/metric_service.py` already assembles symbolic and contact families behind a fail-safe wrapper.
- **Generation context is only partially exported.** `collectors.py` probes `generation_index_by_owner` / `generation_index_by_agent` and `initial_lifecycle_records` from the arm/result, but `SimulationRunnerResult` does not declare or populate a lifecycle field even though `engine.lifecycle_records` is authoritative. Population lifecycle and blank-slate bootstrap are owned by v3-02/v3-03 and already available to an experiment.
- **Runtime carrying exists but export is incomplete.** `AgentRuntimeCheckpoint` carries `semantic_naming` and `symbolic_language`, and `SimulationRunnerResult` is the experiment-facing result. The result does not explicitly declare `terminology_ledgers` / `symbolic_ledgers`; collectors probe for them dynamically. This plan makes the export explicit so drift analysis is not silently absent.
- **Baseline:** 43 command variants, 73 observer semantic types, 106 metric families, `runner-config-v46`, replay-v22/codec v20, Alembic `0017`, latest Experiment BB. Recheck all selectors before implementation if other feature work lands first.

## Compatibility and Authority Contract

1. `WorldEngine` remains the sole objective mutation authority. This plan adds **no** world behavior: no new command, no new event, no new perception field, no new RNG stream, no new identifier namespace, no Alembic migration.
2. The closed `AgentCommand` count stays **43**. The observer semantic-type count stays **73**. Replay stays `EVENT_SCHEMA_REPLAY_V22`, persistence codec stays `v20`, and `communication.v1` is unchanged. No runner-config schema is added; `runner-config-v46` remains the highest schema.
3. No new capability flag. Semantic-drift history is an additive part of the existing per-agent naming and symbolic modes, which default `DISABLED`. Mode policy versions remain `semantic-naming.v1` and `symbolic-language.v1` because locked behavior constants do not change.
4. History is **owner-scoped** and bounded. A label binding and a symbolic composition each retain at most 16 sense records. Records are appended only when the existing policy promotes or shifts a sense, or when an exact merge copies associations. The plan never injects a meaning.
5. The engine never reads drift metrics. Analysis outputs are detached and read-only; no agent receives referent distributions, group membership, generation summaries, or divergence scores.
6. Objective referents and owner hypotheses stay separate. An analysis row may contain the owner's referent kind and opaque referent digest; it must not claim the referent is objectively correct or that two owners share a belief.
7. Analysis is metadata-only. No raw label token, composition part text, message body, prompt, or narration enters a metric document or log. Cross-owner comparison uses surface digests; owner-scoped ids are never treated as shared identity.
8. Disabled modes remain byte-identical: no sense records, no new result fields beyond empty tuples, no observation changes, no RNG consumption, no trajectory changes.
9. Different populations and generations may diverge. Contact may change meanings only through existing delivered communication; no convergence, assimilation, or "correct meaning" success condition exists.
10. `multi_hop_testimony_tracking` remains fail-closed. This plan does not add multi-hop evidence propagation.
11. Observer frames and the Godot protocol do not change. Any researcher presentation remains optional and must read a read-only checkpoint/result, never objective events.

## Design Decisions

### Bounded sense history in the subjective ledger

- Add `NamingSenseTrigger` (`promoted`, `shifted`, `merged`) and `NamingSenseRecord` to `semantic_naming.py`:
  - `ordinal`, `tick`, `trigger`, `referent_kind`, `referent_id`, `associated_ids`, `confidence`.
  - `associated_ids` is the ordered tuple of other candidate entity ids visible to the owner at that moment; it is owner-local, not a truth claim.
- Add `LabelBinding.sense_history: tuple[NamingSenseRecord, ...] = ()` and carry it through `_BindingDraft`, `_drafts_from`, and `_freeze`.
- Append a `promoted` record in `_promote` when a binding becomes `ACTIVE`.
- Append a `shifted` record in `_meaning_shift` on the tick when `sense_revision` increments, capturing the new top candidate and confidence.
- Append a `merged` record to the surviving binding in `_merge` when a weaker binding's candidates are absorbed.
- Validate ordinal monotonicity, non-decreasing tick order, closed triggers, quantized confidence, unique associated ids, and the 16-record cap. Reject foreign owners and embedded ledgers exactly as today.
- Add `SymbolicSenseTrigger` (`promoted`, `shifted`) and `SymbolicSenseRecord` with `ordinal`, `tick`, `trigger`, `referent_kind`, `confidence`, and `associated_ids`. Here `associated_ids` contains the constituent labels' current top candidate ids when available, so a composition's associated concepts are observable without copying another owner's ledger.
- Add `SymbolicComposition.sense_history` and append on symbolic promotion and symbolic meaning shift. No new trigger is invented for ordinary use; usage remains in the existing evidence rows and `usage_count`.

### Usage contexts

- Usage context is reconstructed from existing `NamingEvidenceItem` and `SymbolicEvidenceItem` rows: tick, channel, actor/speaker id, and lineage reference. No new observation payload is added.
- The latest sense record at or before an evidence tick supplies the referent digest for that usage. If no prior sense exists, the usage row reports `referent_digest=None` rather than inventing a meaning.
- Channel counts are descriptive: `observed`, `communicated`, `remembered`, `self_use`. They are never treated as causal proof of why a meaning changed.

### Detached row contracts

Create `src/analysis/semantic_drift_metrics.py` with frozen rows and validation:

- `SemanticSenseRow(owner_id, term_digest, term_source, referent_kind, referent_digest, associated_digests, tick, sense_revision, trigger)`
- `SemanticUsageRow(owner_id, term_digest, term_source, tick, channel, actor_digest, referent_digest)`
- `SemanticAnalysisInputs(senses, usages, communities, generation_index_by_owner, expected_owner_count)`

`term_source` is closed: `label` or `composition`. `term_digest` is a stable surface digest:

- label: SHA-256 of `label|<token>` truncated to 16 hex chars;
- composition: SHA-256 of `composition|<kind>|<part_digest_a>|<part_digest_b>` truncated to 16 hex chars.

The digest makes the same surface form comparable across owners while the underlying `composition_id` and `binding_id` stay owner-scoped. Communities and generations are resolved at analysis time from detached rows/maps, never stored in the ledger.

### Metric families

- **`semantic_stability@1`** — per-term retention and sense persistence:
  - term count, terms with at least two sense observations, stable-referent count/rate, stable-association count/rate, retention across consecutive sense records per term, mean sense revision, cross-generation stability for terms observed in two or more generations, coverage.
  - Terms with fewer than two sense records contribute to `term_count` but not to stability-rate denominators.
  - Availability `absent` when no term has two observations.
- **`semantic_drift@1`** — recorded change and usage context:
  - transition count, referent-switch count, association-change count, drift rate over transitions, mean Jaccard distance between consecutive association sets, mean ticks between changes, revision count, multi-referent term count, usage-context count, channel counts, coverage.
  - Drift is a description of recorded transitions, never a target. A run with zero transitions reports zero drift and full stability.
- **`semantic_divergence@1`** — distributions across groups and generations:
  - group count, generation count, between-group divergence, within-group divergence, between-generation divergence, within-generation divergence, cross-generation continuity, pairwise divergence, coverage.
  - Use the existing `analysis.numerical.jensen_shannon_divergence` over referent-digest distributions for each shared term. Senses with no referent digest are excluded from the distribution and reported as coverage gaps. Report `absent` when neither communities nor generations are available. Missing membership is a coverage gap, never an inferred zero.
- Register `MetricFamilyId.SEMANTIC_STABILITY`, `SEMANTIC_DRIFT`, `SEMANTIC_DIVERGENCE`; `METRIC_FAMILY_COUNT` moves 106 → 109.

### Experiment BC (off the V1 regression gate)

- New `src/experiments/semantic_drift_scenario.py`, experiment id `semantic_drift@1`, catalog builder `experiment_bc_semantic_drift`.
- Arms:
  - `bc-off`: naming and symbolic modes disabled; no sense history and all three families absent.
  - `bc-stable`: one population with naming + symbolic deterministic; history must be internally consistent and may show zero drift.
  - `bc-isolated`: two region-separated populations with naming + symbolic and no contact; group divergence is reported when candidate communities exist, and no cross-group meaning transmission is asserted without delivered communication.
  - `bc-contact`: two region-separated populations with owned contact/trade/teaching channels; cross-group borrowing may appear only through delivered communication.
  - `bc-generation`: generational population with `generational_population=True`, a bounded lifespan, explicit blank-slate bootstrap, and naming + symbolic deterministic; reports generation coverage when more than one generation is observed.
  - `bc-unsupported` non-run fixture: symbolic mode without naming rejects with the existing stable code.
- The arbiter asserts only structural facts: history ordinals/ticks are monotonic, every shift increments `sense_revision`, isolated populations do not share meanings without a delivery channel, generations start blank-slate, and metrics do not force convergence. It never asserts that drift, stability, or divergence "should" occur.

### Analysis assembly

- `MetricComputationInputs` gains `semantic_drift_analysis: SemanticAnalysisInputs | None = None`.
- `collectors.py` harvests naming and symbolic ledgers from `arm` or `arm.runner_result` **outside** the regional/events branch, derives `generation_index_by_owner` from the exported lifecycle records when the arm map is absent, reuses candidate-community rows when present, and attaches the analysis input whenever at least one ledger exists. `events` is optional; composed-message usage rows simply do not contribute when unavailable.
- `metric_service.py` computes the three families inside the existing `_safe` wrapper. Flags-off runs emit `absent` availability or omit the families according to the current catalog convention without errors.

### Presentation and documentation

- No observer endpoint or Godot protocol change is required. Optional researcher UI work is out of scope unless implementation discovers an existing panel that already reads generic metric documents.
- Documentation: `docs/social-communication.md` (sense history and no-forced-drift rule), `docs/architecture.md` (schema/boundary/counts), `docs/configuration.md` (modes unchanged, history caps not configurable), `docs/persistence.md` and `docs/simulation-runner.md` (ledger export, unchanged replay/codec), `docs/analysis-metrics.md` (three families, 106 → 109), `docs/experiments.md` (Experiment BC and arms), `docs/development.md` (verification block), and `README.md` index if needed.

## Commit Plan

Commit messages are suggestions for implementation; this planning command creates no commits.

- **Commit 1** (tasks 1–4): `feat(v3): record bounded sense history and export runner evidence`
- **Commit 2** (tasks 5–9): `feat(v3): add detached semantic stability, drift, and divergence metrics`
- **Commit 3** (task 10): `feat(v3): add Experiment BC semantic drift`
- **Commit 4** (tasks 11–12): `docs(v3): document semantic drift tracking and metrics`
- **Commit 5** (task 13): `test(v3): reconcile semantic drift gates and metric counts`

## Tasks

### Phase 1 — Subjective sense history and export

- [x] **Task 1: Add bounded naming sense history.**
  - Files: `src/agents/cognition/semantic_naming.py`, `src/agents/cognition/__init__.py`; create `tests/unit/test_semantic_sense_history.py`; update `tests/unit/test_semantic_naming.py`, `tests/unit/test_semantic_naming_runtime.py`.
  - Deliver `NamingSenseTrigger`, `NamingSenseRecord`, `_MAX_SENSE_HISTORY = 16`, `LabelBinding.sense_history`, `_BindingDraft.sense_history`, and append logic in `_promote`, `_meaning_shift`, and `_merge`. Carry history through `_drafts_from` and `_freeze`.
  - Enforce ordinal monotonicity, non-decreasing ticks, closed triggers, quantized confidence, unique associated ids, cap, and owner consistency. Keep `sense_revision` as the authoritative count; a `shifted` record is appended only when that count increments.
  - Acceptance: promotion creates one `promoted` record; a known-answer meaning shift creates exactly one `shifted` record with the new top candidate; merge records association absorption; no record is created on ordinary evidence or decay; disabled mode yields no ledger and no history.
  - Logging: DEBUG at append with owner id, trigger, tick, and record count only; INFO once per updated ledger with status counts. Never log label tokens, candidate entity ids, or associated content.
  - Dependencies: none.

- [x] **Task 2: Add bounded symbolic sense history.**
  - Files: `src/agents/cognition/symbolic_language.py`, `src/agents/cognition/__init__.py`; create `tests/unit/test_symbolic_sense_history.py`; update `tests/unit/test_symbolic_language_learning.py`, `tests/unit/test_symbolic_language_runtime.py`.
  - Deliver `SymbolicSenseTrigger`, `SymbolicSenseRecord`, `SymbolicComposition.sense_history`, `_CompositionDraft.sense_history`, and append logic in `_promote` and `_meaning_shift`.
  - Thread the owner `bindings` map (or the owner `TerminologyLedger`) into `_promote`, `_meaning_shift`, and `_freeze`; these functions do not currently receive terminology. Resolve `associated_ids` from the current top candidates for the composition parts when available; otherwise leave the tuple empty. Never copy another owner's hypothesis or confidence.
  - Acceptance: symbolic promotion and shift are recorded with monotonic ordinals; repeated shifts cap at 16 without exceptions; a composition with missing constituent senses still records its referent kind with an empty association tuple; no behavior or ordering changes when history is empty.
  - Logging: DEBUG at append with owner id, trigger, tick, and record count only; INFO once per updated ledger with composition/status counts. Never log parts, tokens, or entity ids.
  - Dependencies: none.

- [x] **Task 3: Export naming and symbolic ledgers from the runner result.**
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner.py`, `src/simulation/agent_runtime.py`; create `tests/unit/test_runner_ledger_export.py`; update `tests/unit/test_symbolic_language_checkpoint.py`, `tests/unit/test_semantic_naming_runtime.py`.
  - Declare `terminology_ledgers: tuple[object, ...] = ()` and `symbolic_ledgers: tuple[object, ...] = ()` on `SimulationRunnerResult`; validate them as ordered immutable tuples without importing cognition into the result model at module import time.
  - Add runner exports that read each runtime checkpoint (`semantic_naming`, `symbolic_language`) and populate the result in `run()`. Skip `None` ledgers. Preserve owner order and do not mutate ledgers.
  - Acceptance: enabled runs expose one ledger per owner in deterministic order; disabled runs expose empty tuples; a re-export is idempotent; the result document, event journal, replay, and codec are unchanged; blank-slate bootstrap still contains no naming/symbolic fields.
  - Logging: INFO once at result finalization with ledger counts; DEBUG with per-owner mode and history counts only. Never log tokens, candidates, or composition parts.
  - Dependencies: 1, 2.

- [x] **Task 4: Export lifecycle records and derive a generation map.**
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner.py`, `src/experiments/collectors.py`; create `tests/unit/test_runner_lifecycle_export.py`; update `tests/unit/test_runner_ledger_export.py`.
  - Declare `initial_lifecycle_records: tuple[object, ...] = ()` on `SimulationRunnerResult` and validate it as an ordered immutable tuple. Populate it in `run()` from `self._engine.lifecycle_records`; do not import world lifecycle types into the result model at module import time.
  - Derive `generation_index_by_owner` from those records in `collectors.py` when the arm does not already expose a map. Match the field name already probed by `collectors.py:149`.
  - Acceptance: enabled generational runs expose one record per entry in deterministic order; disabled runs expose an empty tuple; restored runs preserve records; the result document, event journal, replay, and codec are unchanged; the existing historical-memory generation join and the new semantic-divergence generation axis receive a real map.
  - Logging: INFO once at result finalization with lifecycle-record count; DEBUG with generation count and owner coverage only. Never log lifecycle stage content or owner payloads.
  - Dependencies: 3.

### Phase 2 — Detached analysis

- [x] **Task 5: Define detached semantic-drift rows and harvest them.**
  - Files: create `src/analysis/semantic_drift_metrics.py` (row DTOs and digest helpers first); update `src/experiments/composition.py`, `src/experiments/collectors.py`, `src/analysis/__init__.py`; create `tests/unit/test_semantic_drift_rows.py`.
  - Deliver `SemanticSenseRow`, `SemanticUsageRow`, `SemanticAnalysisInputs`, `semantic_term_digest`, `semantic_sense_rows_from_ledgers`, `semantic_usage_rows_from_ledgers`, and `semantic_analysis_inputs_from_harvest`.
  - Harvest naming sense records and symbolic sense records into the same row shape with closed `term_source`. Join evidence rows to the latest sense at or before the evidence tick. Resolve communities and generation maps only through existing detached rows/maps.
  - Move the naming/symbolic ledger harvest out of the `if regional_input is not None and events is not None` block in `collectors.py`; attach `semantic_drift_analysis` whenever at least one ledger exists, with `events` optional. Reuse the generation map from Task 4 when the arm map is absent.
  - Acceptance: rows round-trip; missing ledgers yield empty inputs rather than fabricated zeros; raw tokens never appear in rows; the same surface form has the same digest across owners; owner-scoped ids remain owner-scoped; no analysis module imports ledger types; `bb-single` retains its symbolic families and now emits semantic-drift families without communities.
  - Logging: DEBUG with row counts, coverage bands, and source counts; INFO once per harvest. Never log owner-specific content.
  - Dependencies: 3, 4.

- [x] **Task 6: Implement `semantic_stability@1`.**
  - Files: `src/analysis/semantic_drift_metrics.py`, `src/analysis/specifications.py`; create `tests/unit/test_semantic_stability_metrics.py`.
  - Compute term count, terms with at least two sense records, stable-referent and stable-association counts/rates, retention across consecutive sense records per term, mean sense revision, cross-generation stability, and coverage. Use the first and last sense per term for stability; use generation maps for the cross-generation measure.
  - Terms with fewer than two sense records contribute to `term_count` but not to stability-rate denominators.
  - Acceptance: zero-transition histories report full stability where defined; a referent switch lowers referent stability without changing association stability when associations are unchanged; missing generation data leaves the generation measure absent, not zero; identical inputs produce identical documents.
  - Logging: INFO at assembly with family id and availability; DEBUG with aggregate counts only.
  - Dependencies: 5.

- [x] **Task 7: Implement `semantic_drift@1`.**
  - Files: `src/analysis/semantic_drift_metrics.py`, `src/analysis/specifications.py`; create `tests/unit/test_semantic_drift_metrics.py`.
  - Compute transition count, referent-switch count/rate, association-change count, mean Jaccard distance between consecutive association sets, mean ticks between changes, revision count, multi-referent term count, usage-context count, and channel counts.
  - Acceptance: a `shifted` trigger increments transition and referent-switch counts; association-only changes increment association-change without a referent switch; usage rows do not double-count transitions; zero transitions produce zero counts and no fabricated rate; empty input yields `absent`.
  - Logging: INFO at assembly with availability; DEBUG with aggregate counts only.
  - Dependencies: 5.

- [x] **Task 8: Implement `semantic_divergence@1`.**
  - Files: `src/analysis/semantic_drift_metrics.py`, `src/analysis/specifications.py`; create `tests/unit/test_semantic_divergence_metrics.py`.
  - Build per-term referent-digest distributions per community and generation. Reuse `analysis.numerical.jensen_shannon_divergence` for pairwise values. Report between/within group and generation means, cross-generation continuity, pairwise divergence, and coverage.
  - Exclude senses with `referent_digest is None` from every JS distribution and report them as coverage gaps.
  - Acceptance: two groups with disjoint referents show maximum divergence; one group yields no pairwise value; absent communities and generations yield `absent`, not zero; unknown referents do not create a shared "unknown" bucket; a term absent from one generation is excluded from continuity, not counted as change; identical rows produce identical documents.
  - Logging: INFO at assembly with family id, group/generation counts, and availability; DEBUG with aggregate pair/coverage counts only.
  - Dependencies: 5.

- [x] **Task 9: Register the three families and wire metric assembly.**
  - Files: `src/analysis/specifications.py` (`METRIC_FAMILY_COUNT` 106 → 109), `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `src/analysis/serialization.py`; update `tests/unit/test_metric_specifications.py`, `tests/unit/test_metric_service.py`, and every unit test that pins `METRIC_FAMILY_COUNT == 106`.
  - Add `SEMANTIC_STABILITY`, `SEMANTIC_DRIFT`, `SEMANTIC_DIVERGENCE` specs with evidence inputs, denominators, zero-holding policy, and value keys. Add the assembly branch behind `_safe`.
  - Acceptance: catalog validation passes at 109; all three specs are discoverable by family id; flags-off runs remain green and omit or mark families absent; metric documents expose only digests/bands/counts; no unsupported family is accepted by serialization.
  - Logging: INFO at assembly with each family id and availability; WARN on absent/degraded inputs with safe codes.
  - Dependencies: 6, 7, 8.

### Phase 3 — Experiment

- [x] **Task 10: Add Experiment BC and dispatch.**
  - Files: create `src/experiments/semantic_drift_scenario.py`; update `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/coordinator.py`, `src/experiments/matrix_runner.py`; create `tests/unit/test_experiment_bc.py`.
  - Implement `semantic_drift@1` with `bc-off`, `bc-stable`, `bc-isolated`, `bc-contact`, `bc-generation`, and the `bc-unsupported` config fixture. Reuse `_scenario`/`_regions` from the multiple-societies scenario and existing naming/symbolic modes. The generation arm uses `runner-config-v46` plus `generational_population=True`, a bounded `example_population_lifecycle_spec`, and `default_new_agent_initialization_spec`.
  - Add `generation_index_by_owner` to `ExperimentArmResult` and populate it in the coordinator from `runner_result.initial_lifecycle_records` (or the derived map); do not rely on a dynamically attached attribute that no code sets. Use a horizon/lifespan combination such as `max_ticks=24`, `lifespan_ticks=12`, and `max_population=6` so more than one generation is possible, but do not make the arbiter require one.
  - Arbiter: off arm has no sense history; enabled arms have monotonic history; isolated arms assert group divergence availability only when communities exist and no cross-group meaning without delivered communication; contact arms assert borrowing only through delivered communication; generation arms assert blank-slate bootstrap and generation coverage when more than one generation appears; unsupported config fails closed.
  - Acceptance: all arms run under the same seed/scenario identity where applicable; deterministic results across runs; catalog/count assertions updated; no arm claims forced drift, convergence, or semantic correctness.
  - Logging: INFO at scenario build/arbitration with arm id and aggregate counts; DEBUG with safe structural details only. Never log tokens or message bodies.
  - Dependencies: 3, 4, 9.

### Phase 4 — Documentation

- [x] **Task 11: Update core contracts and runtime documentation.**
  - Files: `docs/social-communication.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/persistence.md`, `docs/simulation-runner.md`.
  - Document sense-history records and caps, the no-forced-drift rule, owner-scoped referents, unchanged modes and policy versions, explicit ledger and lifecycle-record export, generation-map derivation, unchanged `runner-config-v46` / replay-v22 / codec v20 / Alembic `0017`, and the 43/73/109 counts. State that meaning is not objective world state.
  - Acceptance: docs match code selectors; no stale claim of a schema bump; all internal links resolve; no convergence or correctness claim.
  - Logging: not applicable to docs; examples must be metadata-only.
  - Dependencies: 9, 10.

- [x] **Task 12: Update metrics, experiment, and development documentation.**
  - Files: `docs/analysis-metrics.md`, `docs/experiments.md`, `docs/development.md`, `README.md` (index if needed).
  - Add the three families and formulas, Experiment BC arms, verification block, and the 106 → 109 family count. Explain that stability, drift, and divergence are descriptive and that no evolution is forced.
  - Acceptance: links/anchors resolve; docs identify exact verification commands; README index remains complete.
  - Logging: not applicable to docs.
  - Dependencies: 9, 10.

### Phase 5 — Verification

- [x] **Task 13: Reconcile architecture, compatibility, and full verification gates.**
  - Files: tests and any narrowly required wiring discovered by verification; do not weaken gates. Update `tests/architecture/` isolation/import tests and all count pins.
  - Verify: focused semantic-drift tests; `uv run --frozen --python 3.12.14 pytest`; Ruff; mypy; import-linter; architecture suite; the required six-file V1/V2 compatibility gate; the V3 flags-off scientific-invariant gate; and the new BC focused suite. Confirm Alembic head stays `0017`, replay/codec pair stays `v22`/`v20`, command count stays 43, observer semantic count stays 73, and metric family count is 109.
  - Acceptance: no new gate exclusions or suppressed errors; disabled runs remain byte-identical; sense history is capped and monotonic; ledger and lifecycle export are deterministic; Experiment BC and all three metric families are registered and tested.
  - Logging: record verification outcomes and any safe failure codes in the plan log; never paste tokens, message bodies, prompts, or content.
  - Dependencies: 1–12.

## Verification Notes

- Focused suites to add or run during implementation:
  - `tests/unit/test_semantic_sense_history.py`
  - `tests/unit/test_symbolic_sense_history.py`
  - `tests/unit/test_runner_ledger_export.py`
  - `tests/unit/test_runner_lifecycle_export.py`
  - `tests/unit/test_semantic_drift_rows.py`
  - `tests/unit/test_semantic_stability_metrics.py`
  - `tests/unit/test_semantic_drift_metrics.py`
  - `tests/unit/test_semantic_divergence_metrics.py`
  - `tests/unit/test_experiment_bc.py`
- Required repository gates: default pytest, Ruff, mypy, import-linter, architecture isolation, V1/V2 compatibility, and V3 flags-off invariants. No Godot suite is required because no observer semantic type, router entry, or protocol shape changes.
- Manual reviewer checks: confirm history is append-only and bounded; confirm a shift record exists only when `sense_revision` increments; confirm no raw token or entity id reaches a metric document or log; confirm groups/generations are resolved only from detached membership; confirm isolated populations do not acquire meanings without a delivered channel; confirm disabled arms are byte-identical.
