# Phase 3: Detached Analysis, Candidates, and Metrics

Plan: [index.md](index.md)
Tasks: 10-13
Depends on: Phase 2 / Tasks 4-9

## Objective

Project exported representation ledgers and committed speech anchors into
detached analysis: normalized rows, stable `rep-` candidates, forward-only
lineage, three strictly separated layers, researcher-only scope alignment, and
three appended metric families that raise the catalog from 157 to 160.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/evidence_testimony_contract.py` | policy/prefixes 43-70; enums 144-173; token helpers 214-251 | Analysis contract template |
| `src/analysis/evidence_testimony_rows.py` | `harvest_evidence_rows` 397; row types 103-325 | Harvest template |
| `src/analysis/evidence_testimony_objective.py` | `_EVENT_KINDS` 164-181; `_communication_subject` 182; anchor builder 188-261 | Committed event anchor pattern including `Talked`/`Asked`/`Told` |
| `src/analysis/evidence_testimony_detection.py` | `detect_evidence_window_candidates` 147; member/candidate types 55/76 | Detection template |
| `src/analysis/evidence_testimony_identity.py` | `assign_evidence_identities` 120; lineage types 73-92 | Identity/lineage template |
| `src/analysis/evidence_testimony_layers.py` | `project_evidence_layers` 153; `assert_evidence_layer_separation` 199 | Three-layer separation |
| `src/analysis/evidence_testimony_alignment.py` | `classify_evidence_objective_alignment` 182; summary 326 | Researcher-only alignment |
| `src/analysis/evidence_testimony_metrics.py` | three compute functions 115/156/201 | Metric family template |
| `src/analysis/specifications.py` | family ids 232-234; builders 7046-7158; `_BUILDERS` 7369-7371; count 53; validation 7396 | Append-only catalog |
| `src/analysis/metric_service.py` | evidence branch 1706-1784 | Detached emission branch |
| `src/experiments/collectors.py` | evidence wiring 827-845 | Completed-run assembly |
| `src/experiments/evidence_testimony_harvest.py` | `build_completed_run_evidence_harvest` 77 | Harvest bridge |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/delegation_representation_contract.py` | create | Policy, ids, tokens, enums, errors |
| `src/analysis/delegation_representation_rows.py` | create | Harvest rows |
| `src/analysis/delegation_representation_objective.py` | create | Committed speech anchors and windows |
| `src/analysis/delegation_representation_detection.py` | create | Candidate detection |
| `src/analysis/delegation_representation_identity.py` | create | `rep-` identity and lineage |
| `src/analysis/delegation_representation_layers.py` | create | Three layers and guard |
| `src/analysis/delegation_representation_alignment.py` | create | Researcher-only alignment |
| `src/analysis/delegation_representation_metrics.py` | create | Three families |
| `src/analysis/__init__.py` | modify | Public analysis exports |
| `src/analysis/specifications.py` | modify | Family ids/builders/`_BUILDERS`/count 160 |
| `src/analysis/metric_service.py` | modify | `representation_rows` branch |
| `src/experiments/collectors.py` | modify | Collector wiring |
| `src/experiments/delegation_representation_harvest.py` | create | Completed-run harvest |
| `src/analysis/metric_service.py` | modify | `MetricComputationInputs` fields and emission branch |
| `tests/unit/test_delegation_representation_analysis.py` | create | Harvest/detection/identity |
| `tests/unit/test_delegation_representation_layers.py` | create | Layer separation |
| `tests/unit/test_delegation_representation_metrics.py` | create | Family math |
| `tests/unit/test_delegation_representation_metric_service.py` | create | Emission |
| `tests/unit/test_delegation_representation_catalog.py` | create | Catalog pins |
| `tests/unit/test_delegation_representation_catalog_pins.py` | create | Stale-count guard |
| `tests/unit/test_evidence_testimony_catalog.py` | modify | Count 160 and first-157 digest |
| `tests/unit` and `tests/architecture` (44 files) | modify | Sweep 68 metric-count 157 assertions to 160 |
| `docs/analysis-metrics.md`, `docs/architecture.md`, `docs/disputes.md` | modify | Current-pin catalog lines only |

## Task 10: Harvest representation rows and objective speech anchors

### Intent

Analysis must consume only exported, metadata-safe rows and committed events. It
must never import cognition, an event store, or a live ledger.

### Implementation Steps

1. Create `src/analysis/delegation_representation_contract.py` with
   `REPRESENTATION_ANALYSIS_POLICY_VERSION = "delegation-representation-analysis.v1"`,
   analytical prefixes (`rep-`, `rep-edge-`), `RepresentationAnalysisError`, and
   safe-token helpers:
   `representation_owner_token(owner_id)`,
   `representation_principal_token(kind, ref)`,
   `derive_representation_candidate_id(...)`, `representation_edge_id(...)`.
2. Create `src/analysis/delegation_representation_rows.py` with frozen rows:
   `RepresentationMandateRow`, `RepresentationPositionRow`,
   `RepresentationRevocationRow`, `RepresentationConflictRow`,
   `RepresentationHarvestRows`, and `harvest_representation_rows(ledgers, ...)`.
3. Each row carries an `owner_token` (hashed), a `principal_token` (hashed agent
   id, or the `orgc-`/region id unchanged), scope kind/subject token, duration,
   status, recognition basis, tick span, and counts. Rows carry no actor ids,
   free text, commands, or world events.
4. Create `src/analysis/delegation_representation_objective.py` with
   `RepresentationObjectiveAnchorKind` = `COMMUNICATION`, `TRANSFER`,
   `HARM`, `COMMITMENT_DECLARED`; reuse the duck-typed extraction pattern from
   `evidence_testimony_objective.py:164-261` (`details.kind` names `Talked`,
   `Asked`, `Told`, `Given`, `Taken`, `Attacked`, `CommitmentDeclared`).
5. Extract the verified `speaker_id` for communication anchors and keep the
   `communication_id` as the subject token; map entity ids through
   `entity_to_agent`.
6. Implement `build_representation_windows(anchors, *, max_windows=1024)` that
   buckets anchors into deterministic tick windows with explicit `partial`
   coverage for empty windows.
7. Create `src/experiments/delegation_representation_harvest.py` with
   `build_completed_run_representation_harvest(runner_result, ...) ->
   RepresentationHarvest` that reads `representation_ledgers` and committed
   events and never mutates the result.

### Required Interfaces and Contracts

```python
def harvest_representation_rows(
    ledgers: Iterable[object],
    *,
    entity_to_agent: Mapping[str, str],
) -> RepresentationHarvestRows: ...

def representation_objective_anchor_rows_from_events(
    events: Iterable[object],
    entity_to_agent: Mapping[str, str],
) -> tuple[RepresentationObjectiveAnchorRow, ...]: ...
```

- Inputs are duck-typed and validated for the expected attributes; a missing or
  malformed ledger raises `RepresentationAnalysisError("representation_harvest_invalid")`.
- No import of `agents`, `world`, `simulation`, `persistence`, or `api` from
  these modules.

### Error Handling and Logging

- `_LOG.debug("representation_harvest ledgers=%d mandates=%d anchors=%d", ...)`.
- WARN `representation_harvest_skipped` with a count when a ledger lacks the
  expected shape; never log ids.
- Never log principal refs, scope subjects, or event bodies.

### Tests

- `tests/unit/test_delegation_representation_analysis.py`: harvest counts and
  token determinism; principal token hashing; event kind mapping; window
  bucketing and partial coverage; invalid input raises the safe code.

### Acceptance Criteria

- Rows are deterministic and metadata-only.
- No live cognition or event store is imported.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_analysis.py -q`
- Expected: pass.

## Task 11: Detect candidates and derive forward-only lineage

### Intent

Researchers need stable representation candidates that can overlap, fragment,
and dissolve without inventing an objective representative registry.

### Implementation Steps

1. Create `src/analysis/delegation_representation_detection.py` with
   `RepresentationMemberItem`, `RepresentationCandidate`,
   `detect_representation_window_candidates(windows)`.
2. Group mandates by
   `(principal_kind, principal_token, scope_kind, scope_subject_token)`.
   Candidates may overlap across principals and scopes; membership is never a
   partition.
3. Derive candidate status:
   `recognized` when any member is recognized and no member is contested;
   `contested` when recognized and contested coexist; `fragmented` when members
   split across two or more representatives with no majority; `claimed` when only
   claims exist; `dissolved` when every member is revoked/expired/superseded with
   no continuation.
4. Create `src/analysis/delegation_representation_identity.py` with
   `assign_representation_identities(windows, detections)`, minting `rep-` ids
   from creation evidence `(principal_kind, principal_token, scope_kind,
   scope_subject, first_tick, first_owner_token)`.
5. Implement forward-only lineage in
   `src/analysis/delegation_representation_lineage.py` with closed kinds
   `continued`, `transformed`, `split`, `merge`, `dissolved`, `emerged`; an
   identity is inherited on continuation and newly minted on split/merge.
6. Emit `rep-edge-` ids for edges from sorted endpoints, kind, and tick.
7. Never read a live ledger, never change a candidate by merging evidence from a
   different principal, and never create a dispute, organization, office, or
   mediation candidate.

### Required Interfaces and Contracts

- Candidate ids are stable for the same creation evidence and change on
  split/merge only by minting a new id.
- Lineage is forward-only: no retroactive rewrite of a prior window.
- `RepresentationCandidateStatus` = `claimed`, `recognized`, `contested`,
  `fragmented`, `dissolved`, `unknown`.

### Error Handling and Logging

- `representation_candidate_ambiguous` WARN when one window yields two
  candidates for the same key; keep both and mark fragmented.
- DEBUG counts only; no candidate ids, principals, or representatives.

### Tests

- `tests/unit/test_delegation_representation_analysis.py`: stable id across
  windows; split/merge minting; continuation inheritance; fragmented status;
  dissolved after revocations; no overlap conflict.

### Acceptance Criteria

- Identity is creation-evidence based and forward-only.
- Overlap and fragmentation are legal and visible.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_analysis.py -q`
- Expected: pass.

## Task 12: Project layers and researcher-only scope alignment

### Intent

Objective counts, owner beliefs, and analytical candidates must never mix, and
objective scope alignment must remain a researcher-only classification that never
reaches cognition.

### Implementation Steps

1. Create `src/analysis/delegation_representation_layers.py` with
   `RepresentationObjectiveRow`, `RepresentationSubjectiveRow`,
   `RepresentationAnalyticalRow`, `RepresentationLayerView`, and
   `project_representation_layers(harvest, candidates, lineage)`.
2. Objective rows carry aggregate counts by anchor kind and tick window only.
   Subjective rows carry owner tokens and per-status counts. Analytical rows
   carry `rep-` ids, status, scope kinds, and lineage kinds.
3. Implement `assert_representation_layer_separation(view)` rejecting: an
   objective row with an owner token or candidate id; a subjective row with a
   candidate id or lineage edge; an analytical row with an actor id or scope
   subject text.
4. Create `src/analysis/delegation_representation_alignment.py` with
   `classify_representation_scope_alignment(mandate, anchors)`:
   - `not_applicable` when the principal is unresolved, scope is
     `transact`/`decide`/`coordinate_project`/`unknown`, or no window exists.
   - `consistent` when the representative has at least one communication anchor
     inside `[start_tick, end_tick)` (or `[start_tick, revocation_tick)`) for a
     `speak_for`/`negotiate`/`carry_message` scope.
   - `inconsistent` when the representative has communication anchors only
     outside the mandate window.
   - `unresolved` when no communication anchor by the representative exists.
5. Add `summarize_representation(...)` producing counts and
   `RepresentationAnalysisSummary` with explicit denominators and coverage.
6. Implement `representation_analysis_digest(...)` over the canonical summary.

### Required Interfaces and Contracts

- `RepresentationLayer` = `objective`, `subjective`, `analytical`.
- Alignment statuses are exactly `consistent`, `unresolved`, `inconsistent`,
  `not_applicable`; `not_applicable` never counts as `consistent`.
- The alignment takes no world state, event store, cognition input, prompt, or
  stop selector.

### Error Handling and Logging

- `representation_layer_leakage` raises `RepresentationAnalysisError` (hard
  failure, no graceful fallback).
- WARN `representation_alignment_partial` with counts when windows are missing.
- Never log representative ids or principal tokens in alignment logs.

### Tests

- `tests/unit/test_delegation_representation_layers.py`: separation guard rejects
  each leak class; valid view projects; alignment matrix for the four statuses;
  `not_applicable` exclusion from the consistent count.

### Acceptance Criteria

- A leak is a hard failure.
- Alignment is researcher-only and deterministic.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_layers.py -q`
- Expected: pass.

## Task 13: Add three metric families and raise the catalog to 160

### Intent

The families must be emitted by real completed-run assembly, not only synthetic
fixtures, the first 157 families must remain byte-identical, and every
hard-coded catalog pin in tests and current-pin docs must move with the count.

### Implementation Steps

1. In `src/analysis/specifications.py`, add family ids
   `REPRESENTATION_MANDATE_STRUCTURE`,
   `REPRESENTATION_RECOGNITION_SUPPORT`,
   `REPRESENTATION_SCOPE_ALIGNMENT` with values
   `representation_mandate_structure@1`,
   `representation_recognition_support@1`,
   `representation_scope_alignment@1`.
2. Add `_spec_representation_mandate_structure`,
   `_spec_representation_recognition_support`, and
   `_spec_representation_scope_alignment` following the evidence builders at
   7046-7158: stable id, version `1`, deterministic value keys, no free text.
3. Append the three builders to `_BUILDERS` immediately after the evidence
   builders (7369-7371) and set `METRIC_FAMILY_COUNT = 160` at line 53.
4. Create `src/analysis/delegation_representation_metrics.py` with:
   - `compute_representation_mandate_structure`: counts by principal kind, scope
     kind, duration kind, provenance, and status; total mandates; coverage.
   - `compute_representation_recognition_support`: support/opposition root
     counts, recognized/contested/rejected counts, denominator = mandates with
     at least one position or principal act, explicit partial coverage.
   - `compute_representation_scope_alignment`: the four alignment counts and the
     applicable denominator; `not_applicable` reported separately.
5. Add `representation_rows` and `representation_objective_rows` to
   `MetricComputationInputs` in `src/analysis/metric_service.py` (class at line
   218, default `None`), and include them in the
   `dataclasses.replace(...)` call sites used by the collector.
6. In `src/analysis/metric_service.py`, add the evidence-style guarded branch:
   `if inputs.representation_rows is not None:` with lazy imports, window
   building, candidate/lineage/layer projection, and three `_safe(...)` calls.
7. In `src/experiments/collectors.py`, read
   `arm.runner_result.representation_ledgers`, build `entity_to_agent`, and
   `replace(inputs, representation_rows=..., representation_objective_rows=...)`;
   then `assemble_metric_documents(inputs)` as at 865.
8. Export the new analysis modules from `src/analysis/__init__.py`.
9. Update `tests/unit/test_evidence_testimony_catalog.py` in the same task:
   raise the expected count to 160, keep the existing first-154 digest pin, and
   add a first-157 digest pin computed from the catalog **before** appending the
   three builders (capture it from the pre-edit working tree, not from the new
   list). Add a full-160 digest pin for future stability.
10. Sweep every hard-coded catalog-count assertion. The pre-change tree has 68
    metric-count assertions across 44 files:
    `grep -rl --include='*.py' -E "METRIC_FAMILY_COUNT\s*==\s*157|==\s*157"
    tests/unit tests/architecture`. Replace `157` with `160` only where the
    assertion describes the current catalog count (`METRIC_FAMILY_COUNT`,
    `len(all_metric_specifications())`, `len(validate_metric_catalog())`,
    `len({spec.family_id ...})`, `len(specs)`). Preserve
    `specs[:154] == 154` and the first-154 digest pin.
11. Update current-pin documentation lines required by the existing docs tests:
    `docs/analysis-metrics.md:41` (closed cardinality),
    `docs/architecture.md:565`, `596`, `634`, and `docs/disputes.md:225`.
    Preserve historical revision statements: `docs/evidence-testimony.md:143`
    ("154 to 157"), the V4-07/V4-08 historical counts in
    `docs/architecture.md`, and the unrelated `8,157` in
    `docs/long-horizon-scalability.md`. `tests/unit/test_organization_docs.py`
    asserts the current `METRIC_FAMILY_COUNT` string appears in
    `docs/architecture.md`, so this step is required before the docs suites can
    pass.
12. Add `tests/unit/test_delegation_representation_catalog_pins.py` with a
    stale-pin guard: assert `METRIC_FAMILY_COUNT == 160`; scan
    `tests/unit`/`tests/architecture` `.py` files for the metric-count patterns
    above followed by `157` and assert no match.
13. Run the full `tests/unit tests/architecture` suite and fix any missed pin in
    this task; do not defer a stale-pin failure to Task 20.

### Required Interfaces and Contracts

- Family ids, order, version, and value keys are append-only.
- A run without representation ledgers emits no representation documents (no
  fabricated zeros).
- A run with representation ledgers emits all three documents with `PRESENT`
  status, including explicit `partial` coverage when windows are missing.

### Error Handling and Logging

- Metric computation errors are isolated by the existing `_safe` wrapper and
  reported as family-level `ERROR`; one family failing must not drop the others.
- `INFO representation_metrics families=3` once per assembly.
- WARN `representation_metrics_partial` with counts only.

### Tests

- `tests/unit/test_delegation_representation_metrics.py`: each family math,
  denominators, coverage, zero-mandate run, and `not_applicable` handling.
- `tests/unit/test_delegation_representation_metric_service.py`: flags-off emits
  nothing; flags-on emits three documents; completed-run collector wiring.
- `tests/unit/test_delegation_representation_catalog.py`: count is 160; ids and
  order; the three new families are last; first-157 digest is unchanged from the
  pre-append baseline.
- `tests/unit/test_delegation_representation_catalog_pins.py`: no metric-count
  assertion still compares against 157; docs current-pin lines carry 160.

### Acceptance Criteria

- Catalog is exactly 160 with the three new families appended.
- Real completed-run assembly emits all three.
- First 157 families keep id, order, version, and value keys.
- No test file or current-pin doc line still asserts 157.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_metrics.py tests/unit/test_delegation_representation_metric_service.py tests/unit/test_delegation_representation_catalog.py tests/unit/test_delegation_representation_catalog_pins.py tests/unit/test_evidence_testimony_catalog.py -q`
- `uv run pytest tests/unit tests/architecture -q`
- Expected: pass; the second command catches every swept pin.

## Phase Risks and Mitigations

- Risk: catalog reordering silently changes legacy metric digests.
  Mitigation: append-only builders and a first-157 digest assertion.
- Risk: analysis reads a live ledger and leaks owner state.
  Mitigation: harvest accepts exported ledgers only; import-linter blocks
  `analysis -> agents`.
- Risk: alignment is treated as truth.
  Mitigation: the four-status classification is excluded from every cognition
  input, and Task 20 asserts no cognition module imports analysis.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
