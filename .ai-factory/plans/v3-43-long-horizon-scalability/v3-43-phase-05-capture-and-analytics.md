# Phase 5: Append-only evidence spooling and exact incremental analytics

Plan: [index.md](index.md)
Tasks: 13–15
Depends on: Tasks 3, 5–8, 10; Tasks 11–12 are independent physical-reader work

## Objective

Move optional retained capture out of growing in-process dictionaries, remove repeated whole-run loads, and introduce exact incremental calculators only where their equivalence can be demonstrated. Raw provenance remains available; derived views never feed cognition.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/experiments/cultural_evidence.py` | `CulturalEvidenceRecorder` 181–313 | Frames accumulate, duplicate detection scans all frames, `result()` materializes all frames. |
| `src/experiments/civilization_capture.py` | `CivilizationEvidenceRecorder` 77–239 | Event batches and boundaries remain in dictionaries; monotonicity repeatedly scans max keys. |
| `src/research_runner/civilization_composition.py` | final publication 79+ | Publication currently composes retained history after execution. |
| `src/experiments/civilization_publication.py` | `CivilizationCapturedHistory` 55–109; `compose_civilization_boundary` 112–135 | Tuple conversion and repeated full-prefix selection prevent a spool iterator alone from bounding publication memory. |
| `src/experiments/cultural_evidence.py`, `src/experiments/cultural_evidence_serialization.py`, `src/experiments/matrix_runner.py` | arm-field builder 140; strict evidence encoder 365; artifact writer 291+ | Current production paths normalize/materialize complete captures and accept only the concrete normalized input type. |
| `src/analysis/generational_cohort.py` | `compute_generational_cohort_comparison` | Exact population-derived metric is a bounded first incremental target. |
| `src/analysis/cultural_trait_dynamics.py` | `compute_cultural_trait_dynamics`, coverage/population helpers | Preserve fixed denominators, coverage, baseline and exact numerical ordering. |
| `src/analysis/cultural_evolution_metrics.py` | `_MEASUREMENT_REGISTRY` | Six families have different estimands; one aggregate cannot replace them. |
| `src/persistence/analysis_sqlalchemy.py` | `load` 94; `_load_events` 379 | Complete objective plus subjective run load. |
| `src/research_runner/generational_composition.py` | `PostgresCommunitySampleProvider` 144–209 | Regional input and identities each independently reload history. |
| `src/experiments/generational_execution.py` | final cultural evidence/metrics 279–302 | Avoid moving the peak from ticks into final result construction. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/persistence.py` | modify | Neutral append/read byte-spool protocol and pinned analysis-page DTOs. |
| `src/persistence/evidence_spool_filesystem.py` | create | Bounded append-only segment spool with boundary index and atomic seal. |
| `src/experiments/cultural_evidence.py`, `src/experiments/civilization_capture.py` | modify | In-memory/spooled recorder strategies and O(1) duplicate/last-boundary checks. |
| `src/experiments/cultural_metric_artifacts.py`, `src/experiments/civilization_publication.py` | modify | Streaming iteration/publication; preserve exact existing logical output. |
| `src/experiments/cultural_evidence_serialization.py`, `src/experiments/matrix_runner.py`, `src/experiments/coordinator.py` | modify | Explicit source-backed evidence dispatch and streamed canonical writes at real arm/artifact consumers. |
| `src/analysis/cultural_evolution_evidence.py`, `src/analysis/civilization_overlays.py` | modify | Separate source iteration and bounded working input from legacy full-input wrappers; preserve exact evidence and output contracts. |
| `src/research_runner/civilization_composition.py`, `src/research_runner/composition.py` | modify | Explicit opt-in spool composition, no import from simulation to adapters. |
| `src/analysis/incremental_generational.py`, `src/analysis/incremental_cultural_traits.py` | create | Exact incremental states/calculators. |
| `src/experiments/generational_execution.py` | modify | Select incremental/batch paths explicitly and preserve family availability. |
| `src/persistence/analysis_sqlalchemy.py`, `src/research_runner/generational_composition.py` | modify | Manifest-pinned page/window loads and one evidence session per sampled boundary. |
| `tests/unit/test_evidence_spool.py`, `tests/unit/test_incremental_v3_metrics.py`, `tests/unit/test_generational_sample_loading.py` | create | Equivalence, bounded loading and exact failure semantics. |

## Task 13: Spool optional capture through append-only neutral ports

### Implementation Steps

1. Add a byte-oriented `EvidenceSpool` protocol to experiment persistence ports: append canonical record with lane/boundary/identity, lookup identity, iterate pinned ordered records, seal and read status. Payload DTO encoding/validation stays in experiments/simulation owners; persistence stores verified bytes and metadata, never imports analysis.
   Add experiment-owned `CulturalCaptureSource` and `CivilizationHistorySource` read interfaces over it. Expose pinned run/world/source identity, coverage/status, ordered boundary iteration, exact `read_boundary(tick)`, event-batch range iteration and identity lookup; do not expose `tuple(all_frames)` as the scalable interface. Adapters validate typed records incrementally with the same scope/order/conflict rules as legacy DTO constructors.
2. Implement filesystem segments and indexed boundary/identity pages with configured row/byte ceilings and a bounded decoded-page cache. Each append is atomic; identical duplicates are idempotent, conflicting duplicates fail. Maintain last committed boundary and counts incrementally, not `max(dictionary)` or full scans. Cold records are not deleted when cache entries are evicted.
3. Preserve existing default in-memory recorders. Add explicit composition-only spool injection for V3 benchmark/research CLI runs, not runner JSON fields or capability flags. The existing capture sink still receives only finalized owner-safe projections/metadata receipts. Failed optional capture continues to latch failure without altering scientific ticks.
4. Expose ordered iterator/read-at-boundary interfaces so publication/analytics need not call legacy materializing `result()`, `event_batches` or `boundaries`. Keep those legacy accessors semantically intact for explicit small callers, and label full materialization in scale diagnostics.
5. Add `compose_civilization_boundary_from_source(source, tick)` and select it explicitly in `finalize_civilization_capture`; keep `CivilizationCapturedHistory` and its existing composer as legacy reference wrappers, not a constructor around a spool iterator. Obtain the exact current boundary and stream required preceding boundary/event ranges through the owning calculators in bounded blocks. Refactor only those calculator inputs that would force full-prefix tuples. Preserve original complete input coverage, stable sort/output and markers; no endpoint-only substitution. Full-prefix rescans may remain CPU/I/O-expensive and must be measured separately from peak memory. Introduce `build_cultural_arm_fields_from_source` with a tagged source-backed evidence value in the existing object-valued arm field; update coordinator, generational execution and matrix artifact writing to dispatch that type explicitly instead of calling the old concrete-input encoder.
6. Normalize source-backed cultural evidence through repeatable ordered passes with disk-backed qualified donor/evidence-pointer lookup when historical joins require it. Stream canonical existing evidence JSON sections in the same sorted key/row order, computing digests over exactly the emitted bytes. Keep the legacy `CulturalEvolutionInputs` constructor/encoder unchanged for materialized callers and prove byte-for-byte streamed parity within existing artifact limits. Do not silently relax evidence byte/depth limits: oversize required output fails completion with its explicit size reason and narrows the envelope. Reuse byte-identical frozen dead-owner projections/content-addressed records without altering logical frame identity, ordering or coverage/gaps.
7. Separate source-backed storage/publication from exact batch-metric execution. The four cultural families not incrementally implemented in Task 14 may still require materialized normalized input under an explicit memory budget; identify that stage and its peak rather than relabeling it bounded. Preserve all required legacy metric outputs when the budget permits, and fail the required analysis/artifact stage honestly when it does not. No scalable completion claim may omit a required family, quietly alter coverage, or hide a whole-input constructor inside a source adapter.
8. Keep existing logical capture quotas unchanged. Account all logical rows even if physical deduplication saves bytes; record physical versus logical byte counts separately. Running to 100k with a default 10k-frame quota must be reported as truncated capture unless a separately measured explicit budget is provided.

### Required Interfaces and Contracts

Spooling bounds hot capture/publication buffers, not total historical disk, logical output or every exact batch-metric stage. Introduce frozen experiment-owned `SourceBackedCulturalEvidence` carrying a pinned `CulturalCaptureSource`, selected window, source revision, capture status and canonical evidence digest; it is an internal composition type, not a runner/result/API wire field. The matrix artifact writer explicitly selects its streamed writer while retaining the old concrete-input encoder for `CulturalEvolutionInputs`. Disabled capture performs no spool I/O. An interrupted optional spool is not a complete publication. Never backfill missing capture from a sealed scientific archive or synthesize uncaptured subjective evidence. Task 13 depends on Tasks 5 and 10, not on the lineage/civilization physical layout changes in Tasks 11–12.

### Requirement Evidence

User: records, culture provenance, traces and bounded hot loading without deletion. `docs/cultural-evolution-metrics.md`: disabled/missing/partial/truncated distinctions and deceased provenance sources. Existing recorder failure contracts above.

### Error Handling and Logging

Disk/permission/quota/conflict failures latch explicit capture status; already committed evidence stays readable. Fail a capture-required benchmark/artifact completion on incomplete required evidence while preserving successful scientific execution status. INFO seal/count/byte summaries; bounded DEBUG append timings; no record text/private labels or payload hashes in logs.

### Tests

Memory versus spool exact frames, status, canonical file bytes/digests and metrics; duplicate/conflict; failure mid-append/seal; disk/quota exhaustion; capture-off noninterference; resume from supported finalized prefix without fake backfill; dead-owner projection reuse; bounded retained decoded objects over many frames; publication finalization barrier. Exercise actual runner→recorder→generational/coordinator arm→matrix writer and CLI civilization finalizer paths. Use a test source that raises on all-history tuple construction and counts decoded live records; publication must still succeed with reference-equivalent output. Separately test full-batch metric stage budget failure and required-family completeness, including artifact size failure. Extend existing cultural/civilization capture tests.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_evidence_spool.py tests/unit/test_cultural_evidence_capture.py tests/unit/test_civilization_capture.py --cov=experiments --cov=persistence --cov=simulation --cov=analysis --cov-report=term` passes. Source-backed final publication RSS is measured and does not secretly rematerialize the complete spool. Any explicit global batch-analysis materialization is measured as a distinct budgeted stage and included in end-to-end envelope qualification.

## Task 14: Add exact incremental population and trait-dynamics calculations

### Implementation Steps

1. Introduce pure, detached reducers for `generational_cohort_comparison@1` and `cultural_trait_dynamics@1` only. Inputs are validated finalized progress rows and ordered normalized cultural inventory boundaries; outputs remain the existing metric documents/measurements. No new metric family or algorithm identifier is justified unless semantics change, which is out of scope.
2. For generational comparison, consume exact progress/cohort counter deltas in boundary order and retain original scalar numerators/denominators and coverage. For traits, use a sealed-window two-pass reducer, not irreversible online final rows. First pass builds the exact per-dimension union of traits across all selected boundaries, fixed baseline trait set, sparse per-boundary carrier counts/coverage and qualified evidence-pointer index in the source-backed scratch store. Retain prior complete-boundary presence, continuous-persistence and extinction state. Second pass iterates every selected boundary against the complete sorted trait union, emitting the batch algorithm's zero-frequency rows even before a trait first appeared. Compute diversity with the same canonical counts/numerical helpers; emit missing/disabled/partial rows with unchanged availability and evidence IDs.
   Canonical final output is externally merge-sorted by the existing `_sort_key`: measurement ID, dimension, trait ID or empty string, baseline tick, end tick. Preserve duplicate/tie ordering from the reference emitter. A future trait changes earlier frequency-row membership, so checkpoints may cache sparse reducer inputs but cannot mark earlier final documents immutable before the selected source/window is sealed. Reuse no prior final rows when union, baseline/window or source identity changes.
3. Apply only accepted complete intervals; preserve channel-disabled, population-empty, missing/partial coverage, censorship and gap semantics exactly. A boundary replay is idempotent only with identical identity/content; out-of-order/conflicting boundaries are errors, not silently skipped samples.
4. Add a disposable derived `v3-analytical-view-v1` checkpoint keyed by run/config/manifest, input boundary high-water, selected window/baseline, source-prefix and sealed-source identity, metric/algorithm/library identity, pass/stage and coverage. It is a rebuildable sidecar with atomic publication. Resume sparse first-pass state only when exact prefix anchors match; resume final-row generation only for the identical sealed trait union/window/source. Otherwise recompute from retained evidence. Never treat it as scientific source history or feed it into stop/cognitive policy.
5. Route all other metric families to the existing exact batch calculators. Record which families are incremental versus full-scan/graph-bound in the measured envelope. In particular, do not approximate transmission attribution, fixed-pair population structure, narrative survival, technology lineage or institution lineage with these two reducers.
6. Provide exact ordered output iteration for large per-boundary metric products. Reducer memory grows with distinct required trait/baseline/output identity state; publish this cost rather than promising universal O(1) memory.

### Required Interfaces and Contracts

The first incremental surface is intentionally narrow and exact. Trait-dynamics finalization is offline/two-pass because the existing batch contract is future-dependent; its full boundary×trait-union output can still be large and must count against output budgets. Canonical metric documents must match batch outputs on supported inputs, including row membership/order, provenance, evidence IDs, availability and quantization—not only final numeric values. Seed-block intervals/paired contrasts keep their existing statistical rules and receive unchanged complete cell outputs.

### Requirement Evidence

User: incremental metrics/materialized analytical views while preserving history. Existing metric family contracts are authoritative for estimands and denominators; roadmap counts are not algorithm specifications.

### Error Handling and Logging

Reject wrong input manifest/algorithm and nonadvancing/conflicting boundaries with safe codes. Derived-view corruption triggers verified rebuild from retained evidence, never fabricated zeros. DEBUG processed-boundary/count/timing summaries; no cultural trait labels or narrative bodies.

### Tests

Hypothesis batch-versus-incremental equality across births/deaths, empty/disabled/gapped coverage, trait disappearance/reappearance, competing labels and baseline death; interrupted/replayed derived checkpoint in both passes; changed manifest/library/window identity; stable quantization; no event/hash effects. Include a trait first appearing only at the final boundary and assert all earlier zero-frequency rows/evidence pointers exactly match the batch oracle; adding a later trait invalidates prior final rows while preserving eligible first-pass prefix state. Verify external-sort row ordering, budgeted output overflow and nonincremental families' unchanged exact paths.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_incremental_v3_metrics.py --cov=analysis --cov=experiments --cov-report=term` passes. Benchmark repeated analysis over retained completed cells and report accumulator/derived-view footprint and exact output digest parity.

## Task 15: Page batch evidence and reuse pinned historical samples

### Implementation Steps

1. Add neutral manifest-pinned objective/event and subjective-evidence page APIs to experiment persistence ports. Implement keysets and verified high-water bounds in `SqlAlchemyAnalysisEvidenceLoader`; keep the existing full `load()` entrypoint for explicit legacy callers. No arbitrary ten-million-row limit substitutes for completion.
2. Change `PostgresCommunitySampleProvider.sample()` to open one pinned boundary evidence session shared by regional input and identity projection. Build immutable admission identity indexes once from exact ordered admission events; extend them only through the next verified high-water. Regional windows read only required exact intervals plus defined carry state, not the entire journal twice.
3. Use request/boundary-local caching keyed by run/owner/manifest/boundary/algorithm identity with explicit item/byte caps. Do not share mutable analysis snapshots across concurrent cells or credentials. Eviction only removes recomputable derived data.
4. Feed page iterators into detached experiment composition, then analysis reducers. For algorithms requiring a global graph or full sort, use explicit offline batch execution and bounded disk spill/sorted runs with stable qualified keys; do not silently change the estimator or imply all 136 families are streamable. The initial implementation only external-sorts generic neutral rows for the two new reducers; other global algorithms stay on documented legacy paths.
5. Reuse existing trace soft caps and paged exports. Add full read-only trace export iteration to the cold-copy workflow using existing trace codecs; do not delete previously recorded invocations or make trace omission invisible. Trace caps remain opt-in, default off and outside scientific history.

### Required Interfaces and Contracts

Persistence never imports analysis; simulation never imports either adapter/analysis. All samples are pinned to the finalized boundary, not a later live head. Long-dead admission identities remain indexed and historically queryable. Full materializing legacy modes remain available but are excluded from bounded-loading claims.

### Requirement Evidence

User: batch analytics, historical queries and cognition traces. Source: duplicate `_snapshot()` loads and current full-run loader. Architecture: neutral DTO→experiment bridge→detached analysis.

### Error Handling and Logging

Boundary/hash mismatch, missing required evidence or stale derived index fails closed. Optional trace cap reports its existing reason/status. DEBUG loader-call/row/byte counts and cache status; no payload-bearing SQL/errors.

### Tests

`test_generational_sample_loading.py`: one loader session per sample; fixed-window row count independent of unrelated later events; restored old boundary; stable identity after death; concurrent append pinned out; cross-run/owner isolation; repeated cursor/gap rejection; exact old/new sample equality. Verify trace export completeness/cap status and append-only deletion rejection.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_generational_sample_loading.py tests/unit/test_incremental_v3_metrics.py --cov=research_runner --cov=experiments --cov=persistence --cov=analysis --cov-report=term` passes. Guarded durable scale queries demonstrate reduced rows/loader calls and unchanged sampled output.

## Phase Risks and Mitigations

- Spooling can shift peak allocation to finalization: test streaming publication explicitly and record that peak.
- Global exact analytics can remain expensive: scope incremental claims to the two verified families and publish offline-family costs/limits.
- Quotas can stop future capture: historical data stays, but the envelope must report coverage end and cannot call truncated evidence complete.

## Phase Completion Checklist

- Tasks 13–15 pass exact-output and noninterference tests.
- No raw history or required provenance is replaced by derived state.
- Update progress only in `index.md`.
