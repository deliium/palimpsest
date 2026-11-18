# Phase 3: Detached predictive evidence and versioned publication

Plan: [index.md](index.md)
Tasks: 9–12
Depends on: Tasks 1–8

## Objective

Publish what models predicted before outcomes, their observed performance and
coverage, without deriving forecasts retrospectively from current hypotheses.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
| --- | --- | --- |
| `src/analysis/scientific_hypotheses_contract.py` | forbidden keys | Existing hypothesis rows explicitly exclude accuracy/calibration/score; use a sibling contract. |
| `src/analysis/replication_contract.py` | `ReplicationAnalysis`, policy bounds | Bounded detached rows, notices and window conventions. |
| `src/experiments/replication_completed_run.py` | `replication_facts`, `build_completed_run_replication_analysis` | Trusted owner-state-to-detached-facts bridge. |
| `src/experiments/scientific_hypotheses_completed_run.py` | prediction export from current hypothesis | Do not copy retrospective current-prediction attribution. |
| `src/analysis/specifications.py` | catalog assembly, existing 256 families | Append-only family registration. |
| `src/analysis/metric_service.py` | optional scientific analysis inputs | Do not emit predictive families when analysis input is absent. |
| `src/simulation/replication_models.py`, `replication_codec.py`, `replication_ports.py`, `replication_paging.py` | sibling snapshot/read/publication patterns | Canonical snapshots and independent inner ports. |

## Files to Change

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/analysis/scientific_models_contract.py`, `scientific_models_rows.py` | create | Closed detached sources, row kinds, errors, limits. |
| `src/analysis/scientific_models_analysis.py`, `scientific_models_metrics.py` | create | Windowed evidence checks and descriptive metrics. |
| `src/experiments/scientific_models_completed_run.py` | create | Trusted normalized/tokenized facts from completed results. |
| `src/analysis/specifications.py`, `src/analysis/metric_service.py` | modify | Six additive families and optional input. |
| `src/experiments/collectors.py` | modify | Completed-run input injection. |
| `src/simulation/scientific_models_models.py`, `scientific_models_codec.py` | create | Bounded sibling snapshot and canonical digest. |
| `src/simulation/scientific_models_ports.py`, `scientific_models_paging.py` | create | Separate read/publish ports and pure selection. |
| `src/experiments/scientific_models_publication.py` | create | Opt-in post-completion composition/publication. |
| Relevant package `__init__.py` files | modify | Explicit facades following existing science exports. |
| `tests/unit/test_scientific_models_completed_run.py`, `test_scientific_models_analysis.py`, `test_scientific_models_layers.py` | create | Source timing, separation and absence semantics. |
| `tests/unit/test_scientific_models_catalog.py`, `test_scientific_models_snapshot.py`, `test_scientific_models_publication.py` | create | Catalog, canonical bytes and publication isolation. |

## Task 9: Normalize frozen owner forecasts into detached source facts

### Implementation Steps

1. Define detached `ModelHypothesisFact`, `PredictiveModelFact`,
   `PriorPredictionFact`, `ObservedModelOutcomeFact`, `PredictiveRevisionFact`
   and `PredictiveCoverageFact`. Inputs are frozen tuples, never cognition
   ledgers or runtime objects. Predictive probabilities and losses are explicitly
   allowed only in this new contract; retain legacy hypothesis forbidden keys.
2. `scientific_model_facts(result, ...)` reads only
   `SimulationRunnerResult.scientific_model_ledgers` after completion; Task 8
   populates that validated tuple through the runner export. No live runner or
   runtime checkpoint access is required. Export
   immutable issuance payloads; never reconstruct them from the current model,
   hypothesis, source revision history, or objective event stream.
3. Use run-scoped domain-separated tokens for owner, hypothesis, model, revision,
   target, context, case and receipt IDs. Map all references through one identity
   map. Do not export raw owner/entity IDs, resource names, prose, claims,
   conditions or state digests as payload surrogates.
4. Preserve target kinds, alphabets, categorical prediction/outcome, probability
   milli vectors, confidence, explicit unit category, horizon, issuance/finalized
   tick, physical sample/event tick, receipt tick and source-evidence channel.
   Resource raw quantities stay private; publish direction class and unit token.
   Retain source lineage by tokens, not copied subjective payloads.
5. Mark source missing/partial/truncated separately from a known-empty ledger.
   Duplicate identical facts are a no-op; conflicting bytes for one identity are
   an integrity failure. Detached source facts do not assert target truth.
   A real empty exported owner ledger means known-empty; an expected owner
   missing from the tuple means partial/unavailable. Science off means absent
   analysis, not a synthesized empty science input.

### Interfaces, Errors and Logging

Add `build_completed_run_scientific_models_analysis(...)` with the existing
completed-run builder's neutral input/output pattern. Analysis never imports
cognition or experiments; experiments owns translation. Missing exports produce
coverage, while malformed timing/reference closure fails safely. Log counts only.

### Tests

Use a real completed `SimulationRunnerResult` and frozen issued case; revise its
source hypothesis later and prove the exported old prediction is unchanged.
Assert no raw owner/operand/condition content, no private world imports, no
forecast inferred from an objective event, and explicit partial export status.
Discard the live runner before building facts. Exercise
`assemble_arm_metric_bundle`/`collect_catalog_metrics` with the real builder.

### Acceptance Criteria and Verification

Every detached prediction is traceable to a frozen owner record rather than
retrospective reconstruction.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_completed_run.py tests/unit/test_scientific_models_layers.py -q`

## Task 10: Add bounded analysis and six append-only metric families

### Implementation Steps

1. `harvest_scientific_models_analysis` verifies reference closure, temporal
   inequalities, probability sums, comparable case pairing and deduplication.
   Keep owner-prediction/outcome rows distinct from derived analytical
   calibration/comparison rows. No new objective truth alignment is inferred.
2. Use 32-tick windows assigned by issuance tick, maximum 512 windows, maximum
   8192 rows per section, minimum three observed paired cases. Window scores use
   only resolved prior cases, even if outcomes arrive in a later window.
   Pending observations at the extraction boundary stay right-censored.
   Window identity is absolute `issued_tick // 32`. Keep the latest 512
   available issuance windows: the bound limits their count, not the maximum
   absolute index. Row identity includes window, row kind and qualified
   case/model/source identity.
3. Recompute Phase 1 arithmetic independently from normalized facts inside
   analysis; do not import cognition scoring helpers. Cross-package dependency
   rules outweigh avoiding a few lines of duplicated arithmetic. Golden vectors
   must prove owner and detached calculations agree.
4. Append exactly these six `@1` families at positions `[256:262]`:
   `scientific_model_structure`, `scientific_model_predictions`,
   `scientific_model_observed_outcomes`, `scientific_model_calibration`,
   `scientific_model_revisions`, `scientific_model_comparison`.
   Existing first 256 IDs/order/versions/value keys remain identical.
5. Lock scalar metric keys respectively:
   - structure: `model_count`, `hypothesis_count`, `target_kind_count`;
   - predictions: `prediction_count`, `case_count`, `pending_case_count`;
   - outcomes: `observed_case_count`, `unavailable_case_count`,
     `not_attempted_case_count`, `not_comparable_case_count`, `evicted_case_count`;
   - calibration: `scored_prediction_count`, `calibration_group_count`,
     `insufficient_group_count`;
   - revisions: `revision_count`, `source_revision_count`,
     `parameter_revision_count`;
   - comparison: `comparison_count`, `paired_case_count`,
     `lower_loss_a_count`, `lower_loss_b_count`, `tie_count`,
     `insufficient_comparison_count`.
   These are counts across groups, not pooled cross-target performance. Detailed
   per-group Brier/calibration and differences live in typed snapshot rows.
6. Add optional `scientific_models_analysis` input in metric service/collector
   following replication. No input means no six-family emission; channel-off
   results and existing metrics remain unchanged.
   Collector consumes `arm.runner_result.scientific_model_ledgers`, constructs
   one normalized `ScientificModelsAnalysis`, then passes it to metric service
   without re-harvesting. Do not gate this owner-only evidence on availability
   of global committed-event capture; retained forecasts remain analyzable.
   Missing/partial owner exports produce explicit coverage.

### Errors, Logging and Tests

Reject impossible precommit/outcome ordering and mismatched frozen identities.
Report `retention_cap`, `partial_owner_export`, `outcome_missing`,
`condition_unknown`, `not_comparable` and `unavailable_no_observable` notices.
No composite scientific score, owner ranking, causality or consensus output.

Test exact old catalog prefix, six new keysets, absent versus empty analysis,
future and delayed observations, partial windows and agreement with arithmetic
golden vectors. Assert hypothesis forbidden-key tests stay unchanged.

### Acceptance Criteria and Verification

Catalog is 262 families; detailed calibration and comparison remain target- and
cohort-qualified, never aggregated as one civilization-science score.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_analysis.py tests/unit/test_scientific_models_catalog.py tests/unit/test_metric_specifications.py -q`

## Task 11: Define canonical predictive snapshots and read/publication ports

### Implementation Steps

1. Introduce `ScientificModelsSnapshot` with schema
   `scientific-models-snapshot-v1`, locked policy, run/publication identity,
   finalized-through boundary, source coverage, notices, and seven sections:
   `models`, `predictions`, `outcomes`, `calibration`, `revisions`,
   `comparisons`, `coverage`. Include hypothesis lineage in model rows.
2. Distinguish row classes and evidence-layer tags:
   `owner_prediction`, `owner_observation`, `owner_revision`,
   `analytical_calibration`, `analytical_comparison`, `coverage`.
   No row labels an observation as objective truth.
3. Canonical encoder sorts bounded rows by stable ID, preserves categorical order,
   rejects unknown keys/enums and inconsistent counts/foreign references, and
   uses canonical JSON hashing. Maximum snapshot size is 8 MiB; per-section row
   cap is 8192. Byte overflow fails publication, not scientific execution.
4. Add `ScientificModelsReader`, `ScientificModelsPublisher`, publication options
   and receipt types modeled on replication ports. Keep read and publication
   capabilities separate.
5. Add `page_scientific_models_rows` with page size 1–500, snapshot-pinned stable
   ordering, section plus optional `model_token`, `target_kind`, `status`,
   `issued_from_tick`, `issued_through_tick` filters. Validate range ordering;
   filters never turn missing coverage into an empty-known cohort.
6. Cap reference-closed case bundles before analytics, not independent row
   slices. Select cases in descending `(issued_tick, case_token)` order within
   retained windows. Admission reserves both predictions, optional outcome/
   binding evidence and required model/source revisions; shared rows count once.
   Model rows use `(model_token, revision_token)` identity and embed a token-only
   source-hypothesis revision summary, requiring no new public section.
7. If a bundle exceeds any section's 8192-row cap, omit the entire case with
   surfaced cap counts; never retain one candidate or an orphan outcome.
   Fill remaining capacity with unreferenced current model/revision rows in
   stable ID order. Opaque old evidence/parent references may be unavailable;
   all retained case→model/source-revision references must resolve.
8. Calculate calibration/comparison from exactly the selected paired cohort.
   If derived rows exceed caps, omit whole groups with coverage, not a subset
   of bins with a complete-looking aggregate. Canonically sort after selection.
   If the reference-closed result still exceeds 8 MiB, refuse publication
   with a quota receipt, never byte-trim rows. Propagate nested cap notices/
   omission counts into analysis and snapshot summary coverage.

### Errors, Logging and Tests

Use closed safe `ScientificModelsError` codes. Do not import analysis,
infrastructure or concrete persistence into simulation contracts. No payload logs.
Test canonical twins, field tampering, cross-run refs, maximum size/caps, all
sections, pagination stability and immutable old snapshots.
Test one member of a pair reaching a cap, shared/pinned revision closure, retired
models referenced by old cases, multiple absolute windows and post-cap score
denominators recomputed independently.

### Acceptance Criteria and Verification

A snapshot contains enough frozen forecast/outcome evidence to reproduce each
published comparison, with explicit coverage limits and no raw owner identity.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_snapshot.py -q`

## Task 12: Compose and publish only after scientific completion

### Implementation Steps

1. Add `compose_scientific_models_snapshot`, `build_scientific_models_harvest_result`
   and `publish_scientific_models_snapshot` in the experiment publication module,
   following `replication_publication.py`.
2. Compose normalized facts → detached analysis → validated inner snapshot →
   supplied publisher. Producer construction is trusted composition; API never
   imports this bridge, runs analysis or builds missing artifacts.
3. Publication is programmatically opt-in. No runner field, command, cognition
   feedback, automatic filesystem capture or matrix/CLI scope expansion is
   added. A completed scientific run can legitimately have no published model
   snapshot; lack of publication does not imply no models.
4. Record scientific completion independently from publication readiness.
   Publication quota/corruption/failure leaves scientific history and completed
   result untouched. Only valid immutable snapshots may become visible.
5. Define `ScientificModelsHarvestResult` with status
   `published|disabled|missing|quota_exceeded|corrupt`, `publication_id`,
   `stored`, `byte_size`, safe `reason`, and independent `scientific_status`.
   `snapshot=None` returns `missing`; a valid snapshot with `publisher=None`
   returns `disabled`; refused quotas return `quota_exceeded`; malformed store
   bytes/errors return `corrupt`; success returns `published`. Wrong non-null
   snapshot types fail validation before publication. No result reruns science.

### Errors, Logging and Tests

Propagate safe publication error codes and counts, never payload-bearing
exceptions. Test success, idempotence, known-empty science, missing export,
unfinished run rejection, quota failure and publisher exception isolation.
Test optional snapshot/publisher independently and every exact receipt status
with unchanged scientific status.

### Acceptance Criteria and Verification

Publication adds no live authority and cannot rerun or repair scientific history.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_publication.py -q`

## Phase Risks and Mitigations

- Existing exports can use current predictions: V4-30 reads only issued records.
- Calibration requires new allowed fields: add a sibling contract, never weaken
  old hypothesis restrictions.
- Cross-domain pooling would imply a science score: detailed performance is
  grouped; catalog families contain counts only.

## Phase Completion Checklist

- Frozen evidence, independent arithmetic, canonical snapshot and opt-in producer
  all have focused tests.
- All first 256 metric definitions remain byte-/value-equivalent.
- Progress updates belong only in `index.md`.
