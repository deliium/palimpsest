# Phase 3: Detached Analysis, Disagreement, and Metrics

Plan: [index.md](index.md)
Tasks: 9-12
Depends on: Phase 2 / Task 7

## Objective

Harvest owner agency ledgers into detached rows, summarize proposals, positions,
amendments, decisions, and implementation per analytical candidate, project the
three layers without leakage, and append two metric families (146 → 148). The
analysis never creates, splits, merges, dissolves, or re-identifies a candidate.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/organization_operations.py` | Row classes 126-410; `OrganizationOperationHarvestRows` 413-453; `_ledger_rows` 472-811; `harvest_organization_operation_rows` 814-858; `summarize_organization_operations`; `_CandidateAccumulator` 897-923 | Exact detached-row and summary pattern |
| `src/analysis/organization_metrics.py` | `_operation_availability` 122-137; `_operation_document` 140-173; operation compute functions | Metric availability/document pattern |
| `src/analysis/organization_layers.py` | `OrganizationObjectiveRow` 38-72; `OrganizationSubjectiveRow` 75-96; `OrganizationLayerView` 98-104; `project_organization_layers` 107-263; leakage check 266-303 | Three-layer projection and hard leakage failure |
| `src/analysis/organization_lineage.py` | `_content` 100-133; `derive_organization_lineage` 148-272; `OrganizationAnalysis` | Determinism digest and analysis container |
| `src/analysis/specifications.py` | `MetricFamilyId` 218-223; operation spec builders 6407-6537; `_BUILDERS` tail 6681-6686; `METRIC_FAMILY_COUNT` 53 | Append-only catalog pattern |
| `src/analysis/organization_detection.py` | `OrganizationCandidate` 61-94; `member_ids`, `owner_ids`, `anchor_signature` | Candidate matching inputs; never mutate |
| `src/analysis/organization_identity.py` | `assign_organization_identities`; continuation rules | Must stay unchanged |
| `src/analysis/organization_lineage.py` | `derive_organization_lineage`, `validate_organization_lineage` | Must stay unchanged |
| `tests/unit/test_organization_operations_analysis.py` | Row/summary tests | Test pattern to mirror |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/organization_agency.py` | create | Rows, harvest, candidate summary, deterministic matching |
| `src/analysis/organization_layers.py` | modify | Agency counts on objective/subjective rows, `agency` on the view, leak prefixes |
| `src/analysis/organization_lineage.py` | modify | `OrganizationAnalysis.agency_summary`, include it in `_content` |
| `src/analysis/organization_metrics.py` | modify | Two compute functions and availability/document helpers |
| `src/analysis/specifications.py` | modify | Two `MetricFamilyId` entries, two `_spec_*` builders, `_BUILDERS` append, `METRIC_FAMILY_COUNT=148` |
| `src/analysis/__init__.py` | modify | Export agency rows/summary/compute functions |
| `src/analysis/metric_service.py` | modify | Add `organization_agency_rows` to `MetricComputationInputs` (311); summarize and pass the agency summary through the organization metric block (1430-1474) |
| `src/experiments/collectors.py` | modify | Read `arm.runner_result.organization_agency_ledgers`, harvest agency rows, and add `organization_agency_rows` to the metric inputs (789-802 pattern) |
| `src/experiments/organization_harvest.py` | modify | Read `organization_agency_ledgers` from the runner result and pass them to analysis |
| `src/experiments/organization_publication.py` | modify | Accept the agency summary as an input in phase 5; phase 3 only wires the harvest |

## Task 9: Harvest owner agency ledgers into detached rows

### Intent

Convert exported owner ledgers into normalized, immutable research rows without
importing cognition, world authority, persistence, API, or observer packages.

### Implementation Steps

1. Create `src/analysis/organization_agency.py` with row classes:
   - `OrganizationAgencyOwnerRow`: `owner_id`, `concept_count`, `proposal_count`,
     `position_count`, `amendment_count`, `decision_count`,
     `implementation_count`, `notices`, `policy_version`.
   - `OrganizationProposalRow`: `organization_id`, `proposal_id`,
     `proposal_ref`, `topic`, `domain`, `effect`, `implementation_mode`,
     `target_kind`, `target_ref`, `procedure_ref`, `revision`, `status`,
     `opened_tick`, `deadline_tick`, `support_count`, `oppose_count`,
     `abstain_count`, `contest_count`, `resolved`.
   - `OrganizationPositionRow`: `organization_id`, `proposal_id`, `revision`,
     `actor_id`, `stance`, `authority_basis`, `disputed`, `tick`.
   - `OrganizationAmendmentRow`: `organization_id`, `proposal_id`,
     `amendment_id`, `from_revision`, `to_revision`, `domain`, `effect`,
     `target_kind`, `target_ref`, `procedure_ref`, `amended_tick`, `resolved`.
   - `OrganizationCollectiveDecisionRow`: `organization_id`, `decision_id`,
     `proposal_id`, `revision`, `procedure_ref`, `recognition`,
     `authority_basis`, `support_count`, `oppose_count`, `abstain_count`,
     `contest_count`, `implementation_mode`, `effect`, `target_kind`,
     `target_ref`, `decided_tick`, `window_end_tick`, `implementation_status`,
     `provenance_code`, `resolved`.
   - `OrganizationImplementationRow`: `organization_id`, `implementation_id`,
     `decision_id`, `actor_id`, `status`, `effect`, `observed_tick`,
     `provenance_code`, `resolved`.
   - `OrganizationAgencyHarvestRows`: `owner`, `proposals`, `positions`,
     `amendments`, `decisions`, `implementations`, `concept_ticks`.
   - `OrganizationCandidateAgency` and `OrganizationAgencySummary` (Task 10).
2. Implement `_ledger_rows(ledger)` defensively with `getattr` and tuple
   normalization, mirroring `_ledger_rows` in `organization_operations.py`.
   Reject a foreign owner, a duplicate concept id, a malformed span, or a
   non-sequence family.
3. Implement `harvest_organization_agency_rows(ledgers)` and
   `harvest_organization_agency_snapshot(runner_result)`:
   - `None` → empty tuple.
   - Already-harvested rows are idempotent and sorted by owner.
   - Duplicate owners fail closed with `organization_agency_row_invalid`.
   - Read `runner_result.organization_agency_ledgers` defensively.
4. Add deterministic sorting per family:
   proposals `(organization_id, opened_tick, proposal_id)`;
   positions `(organization_id, proposal_id, revision, actor_id, tick)`;
   amendments `(organization_id, proposal_id, to_revision)`;
   decisions `(organization_id, decided_tick, decision_id)`;
   implementations `(organization_id, decision_id, actor_id, observed_tick)`.
5. Add `organization_agency_concept_counts(rows)` and
   `organization_agency_decision_ticks(rows)` helpers for the layer projection.
6. In `src/experiments/organization_harvest.py`, extend
   `OrganizationHarvest` with `agency_rows` and read
   `organization_agency_ledgers` in `build_completed_run_organization_harvest`.
   Do not import `agents.cognition`.
7. In `src/analysis/metric_service.py`, add
   `organization_agency_rows: Sequence[object] | None = None` to
   `MetricComputationInputs` beside `organization_operation_rows` at 311-312.
   In the organization block at 1430-1474:
   - import `harvest_organization_agency_rows` and
     `summarize_organization_agency`;
   - harvest `inputs.organization_agency_rows`;
   - pass `agency_rows`/`agency_summary` to
     `project_organization_layers` and `derive_organization_lineage`.
8. In `src/experiments/collectors.py`, after the existing operation-ledger block
   at 789-802, read `arm.runner_result.organization_agency_ledgers`, harvest
   agency rows, and `replace(inputs, organization_agency_rows=...)`. Do not
   import cognition; use the analysis harvester only.

### Required Interfaces and Contracts

- Rows are detached, frozen dataclasses; they never import cognition.
- Owner-local ids (`orgp-`, `orgpm-`, `orgcd-`, `orgci-`, `orgcev-`) may appear
  in subjective rows; objective rows and analytical candidate summaries must not
  contain them.
- A missing field becomes `None`/`()`; a wrong type fails closed.
- `ImplementationRow.actor_id` is an agent id in detached analysis; publication
  converts it to a 16-hex `actor_ref` and never publishes the raw id.
- No row carries an utterance body, prompt, label, or `WorldEvent`.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "analysis is read-only" and "No analysis type is
  imported by simulation/persistence".
- V4-04 harvest pattern (cited above).
- Original Request: track implementation/compliance/refusal/sabotage.

### Error Handling and Logging

- Invalid rows raise `OrganizationAnalysisError("organization_agency_row_invalid")`.
- Log INFO `organization_agency_harvest owners=%s concepts=%s proposals=%s decisions=%s implementations=%s`
  (counts only).
- WARN if a ledger notice indicates truncation; never log owner sets or actor
  sets.

### Tests

Create `tests/unit/test_organization_agency_harvest.py`:
- Harvest one valid ledger into the expected rows and counts.
- Empty/None → empty tuple.
- Already-harvested input is idempotent.
- Duplicate owner fails closed.
- Foreign concept owner fails closed.
- A malformed span or non-sequence family fails closed.
- Sorting is canonical.
- No `agents.cognition` import in the analysis module (AST check).
- `build_completed_run_organization_harvest` reads `organization_agency_ledgers`.
- `experiments.collectors` puts harvested agency rows into
  `MetricComputationInputs.organization_agency_rows` for a completed arm.
- `analysis.metric_service.assemble_metric_documents` consumes the agency rows
  without an import cycle or a cognition import.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_harvest.py tests/unit/test_organization_harvest_completed_run.py tests/unit/test_experiment_collectors.py tests/unit/test_metric_service.py -q`

### Acceptance Criteria

- Harvest is defensive, deterministic, and read-only.
- The analysis package gains no cognition dependency.
- Missing evidence stays absent, never zero-filled.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_harvest.py -q`
- Expected: all tests pass.

## Task 10: Summarize collective agency and implementation per candidate

### Intent

Join normalized agency rows to existing analytical candidates and produce
per-candidate counts for process, disagreement, recognition, and implementation.
The summary never mints or changes an `org-` identity.

### Implementation Steps

1. Add `OrganizationCandidateAgency` with:
   `organization_id`, `proposal_count`, `amendment_count`, `support_count`,
   `oppose_count`, `abstain_count`, `recognized_decision_count`,
   `contested_decision_count`, `unrecognized_decision_count`,
   `expired_proposal_count`, `implemented_decision_count`,
   `partial_decision_count`, `unimplemented_decision_count`,
   `obstructed_decision_count`, `unknown_decision_count`, `compliance_count`,
   `refusal_count`, `sabotage_count`, `contrary_count`, `orphaned_count`,
   `coverage_ratio`.
2. Add `OrganizationAgencySummary` with `candidates`,
   `candidate_count`, `candidates_with_agency`, `proposal_count`,
   `amendment_count`, `support_count`, `oppose_count`, `abstain_count`,
   `decision_count`, `implementation_count`, `orphaned_count`,
   `history_truncated`, `coverage_ratio`,
   `coverage: OrganizationCoverage | None`, `provenance_code`.
3. Implement `summarize_organization_agency(rows, candidates, *,
   member_rows: Sequence[OrganizationHarvestRows] = ())`:
   - Build a member set per owner/concept from the existing harvest rows? Agency
     rows do not carry members. Accept the existing `OrganizationHarvestRows`
     as an optional second input, or accept a mapping of concept → member ids
     from `harvest_organization_rows`. Use the existing
     `OrganizationHarvestRows` member rows; do not re-read cognition.
   - Match a concept to a candidate when member Jaccard >= 0.5 or the candidate's
     `procedure_anchor_ids` intersect the concept's procedure refs; tie-break by
     candidate key. This mirrors V4-04 `_matched_groups`.
   - A concept with no match contributes to `orphaned_count`, never to a new
     candidate.
   - Count positions by stance on the latest proposal revision only; superseded
     revisions remain in rows but do not inflate current support/opposition/
     abstention counts. Count decisions by recognition and implementation
     status, implementations by status.
   - Candidate `coverage_ratio = decisions with at least one implementation
     record / decision_count` when `decision_count > 0`, else `None`.
   - Summary `coverage_ratio = candidates_with_agency / candidate_count` when
     `candidate_count > 0`, else `None`.
   - `history_truncated` is true when any owner row has an
     `agency_truncated`/`implementation_truncated` notice or an agency family
     cap was hit.
   - `provenance_code` is `ok` when complete, `collective_agency_truncated`
     when any cap/truncation applies, `orphaned_concept` when concepts have no
     candidate, and `unknown_evidence` when a decision has unknown
     implementation. These are closed tokens; never free text.
4. Ensure the summary is deterministic: candidates sorted by
   `organization_id`; counts are integers; ratios are quantized with
   `quantize_float`.
5. Do not import `organization_detection` mutation functions, identity, or
   lineage; only read `OrganizationCandidate` values.

### Required Interfaces and Contracts

- The summary joins existing candidates; it never creates, splits, merges,
  dissolves, or re-identifies one.
- A candidate with zero agency rows is counted in the denominator but not in
  `candidates_with_agency`.
- `recognition=contested` counts as a decision, not as unrecognized.
- `implemented`/`partial`/`unimplemented`/`obstructed`/`unknown` are mutually
  exclusive decision-level statuses.
- `refusal_count`/`sabotage_count`/`contrary_count` are actor-level counts;
  `obstructed_decision_count` is decision-level and may overlap them.
- No composite "collective agency score" exists.

### Requirement Evidence

- Original Request: supporters, opponents, abstention, recognized outcomes,
  compliance, refusal, sabotage, implementation failure.
- `.ai-factory/ARCHITECTURE.md` Key Principle 1 and V4-03 analysis identity
  contract.
- V4-04 `summarize_organization_operations` and `_matched_groups`.

### Error Handling and Logging

- A malformed summary input raises `organization_agency_summary_invalid`.
- Log INFO `organization_agency_summary candidates=%s with_agency=%s decisions=%s unimplemented=%s`
  (counts only).
- No actor ids, proposal refs, or labels in logs.

### Tests

Create `tests/unit/test_organization_agency_analysis.py`:
- A concept matching a candidate by members contributes to that candidate.
- A concept with no member overlap is orphaned, not a new candidate.
- Recognition counts: recognized, contested, unrecognized, expired.
- Implementation counts: implemented, partial, unimplemented, obstructed,
  unknown.
- Actor-level refusal/sabotage/contrary counts.
- Coverage ratio and `None` when no candidates.
- Deterministic output for shuffled rows.
- Candidate count and identities are unchanged before/after summarization.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_analysis.py tests/unit/test_organization_detection.py tests/unit/test_organization_analysis_identity.py -q`

### Acceptance Criteria

- The summary is a detached join, not an identity source.
- All statuses and counts are explicit and non-overlapping where required.
- No candidate is created, changed, or dissolved.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_analysis.py -q`
- Expected: all tests pass.

## Task 11: Project collective agency into the three layers without leakage

### Intent

Add agency counts to the objective and subjective layers and the summary to the
analytical layer, with hard failure on any cross-layer identity leak.

### Implementation Steps

1. In `src/analysis/organization_layers.py`:
   - Add `collective_decision_count`, `collective_implementation_count`, and
     `collective_unimplemented_count` to `OrganizationObjectiveRow` (counts only).
   - Add `proposal_count`, `decision_count`, `implementation_count`, and
     `unimplemented_count` to `OrganizationSubjectiveRow`.
   - Add `agency: OrganizationAgencySummary | None = None` to
     `OrganizationLayerView`.
2. Extend `project_organization_layers` with optional
   `agency_rows` and `agency_summary` parameters; keep existing callers
   compatible by defaulting to `None`.
   - Objective counts are derived from decision/implementation ticks and the
     window span; never from owner ids.
   - Subjective counts are per owner/concept.
   - Analytical `agency` is the summary; do not add per-owner data.
3. Extend `assert_organization_layer_separation`:
   - Objective rows must not contain any string starting with `orgc-`, `orgp-`,
     `orgpm-`, `orgcd-`, `orgci-`, `orgcev-`, `org-`, `orgcpd-`, `orgcpi-`.
   - Subjective rows must use `orgc-` for `organization_id`; they may contain
     owner-local agency ids in other fields, but no `org-`/`orgcpd-`/`orgcpi-`.
   - Analytical candidates and the agency summary must not use `orgc-` or any
     owner-local agency prefix as candidate keys or organization ids.
   - A summary candidate id must start `org-`.
4. In `src/analysis/organization_lineage.py`:
   - Add `agency_summary: OrganizationAgencySummary | None = None` to
     `OrganizationAnalysis`; validate that a non-`None` value is the exact type.
   - Add it to `_content` so `determinism_digest` includes it.
   - Pass it through `derive_organization_lineage(..., agency_summary=...)`.
5. Update `src/analysis/__init__.py` exports.

### Required Interfaces and Contracts

- Objective layer: counts only, no ids.
- Subjective layer: owner-local `orgc-`/agency ids, never analytical `org-`.
- Analytical layer: `org-` candidates and the agency summary, never owner-local
  ids.
- A leak raises `organization_layer_leak` before any metric is computed.
- `OrganizationAnalysis.determinism_digest` changes when the agency summary
  changes; existing V4-03/V4-04 content remains included.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` Key Principle 1.
- V4-03 `organization_layers.py` 226-303.
- V4-04 layer-leak test pattern.

### Error Handling and Logging

- Leak detection fails closed with `organization_layer_leak`; log ERROR with the
  layer name and field name only (no value).
- INFO `organization_agency_layers objective=%s subjective=%s candidates=%s`
  (counts only).

### Tests

Extend `tests/unit/test_organization_layers.py` and create
`tests/unit/test_organization_agency_analysis.py` cases:
- Objective rows contain no owner/analytical prefixes.
- Subjective rows use `orgc-`; agency ids are allowed only there.
- Analytical summary uses `org-`.
- Injecting an `orgc-`/`orgp-` string into an objective row raises
  `organization_layer_leak`.
- Injecting an `org-` id into a subjective row raises
  `organization_layer_leak`.
- `determinism_digest` changes when the agency summary changes and is stable for
  reordered rows.
- V4-03/V4-04 layer outputs remain unchanged when the agency summary is `None`.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_layers.py tests/unit/test_organization_agency_analysis.py tests/unit/test_organization_determinism.py -q`

### Acceptance Criteria

- Three layers remain strictly separated.
- Existing V4-03/V4-04 layer and digest behavior is unchanged when agency is
  absent.
- Agency counts are visible without leaking owner identity.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_layers.py tests/unit/test_organization_agency_analysis.py -q`
- Expected: all tests pass.

## Task 12: Add two metric families and raise the catalog to 148

### Intent

Append `organization_collective_agency@1` and
`organization_collective_implementation@1` to the metric catalog, raising the
count from 146 to 148 without changing the first 146 families.

### Implementation Steps

1. In `src/analysis/specifications.py`:
   - Append to `MetricFamilyId`:
     `ORGANIZATION_COLLECTIVE_AGENCY = "organization_collective_agency"` and
     `ORGANIZATION_COLLECTIVE_IMPLEMENTATION = "organization_collective_implementation"`.
   - Set `METRIC_FAMILY_COUNT = 148`.
2. Add `_spec_organization_collective_agency()`:
   - `evidence_inputs`: objective event state, agent-visible projection, belief
     revision/testimony.
   - `population="final_window_candidate_collective_agency_process"`.
   - `denominator="candidate_count"`, `denominator_kind=ACTIVE_EDGES`.
   - `cohort_window="final observation window in one analytical run"`.
   - `deceased_policy="dissolved concepts retain their last recorded agency process"`.
   - `zero_holding_policy="no agency rows -> availability=absent; never zero-filled"`.
   - `opportunity_vs_occurrence="proposals and positions are owner beliefs, not opportunities, quorums, or permissions"`.
   - `censoring_policy="unrecognized and expired proposals stay explicit; never inferred as support"`.
   - `value_keys`: `as_of_tick`, `proposal_count`, `amendment_count`,
     `support_count`, `oppose_count`, `abstain_count`,
     `recognized_decision_count`, `contested_decision_count`,
     `unrecognized_decision_count`, `expired_proposal_count`,
     `procedure_linked_count`, `decision_coverage_ratio`.
   - `decision_coverage_ratio = candidates with at least one decision /
     candidate_count`; `None` when there are no candidates.
3. Add `_spec_organization_collective_implementation()`:
   - `population="final_window_candidate_collective_implementation"`.
   - `denominator="decision_count"`, `denominator_kind=EVALUABLE_CLAIMS`.
   - `deceased_policy="dissolved concepts retain recorded implementation outcomes"`.
   - `zero_holding_policy="no decisions -> availability=absent; never zero-filled"`.
   - `opportunity_vs_occurrence="implementation is observed agent action or explicit testimony; never organization execution"`.
   - `censoring_policy="unobserved actors stay unknown; silence is never refusal or sabotage"`.
   - `value_keys`: `as_of_tick`, `decision_count`,
     `implemented_decision_count`, `partial_decision_count`,
     `unimplemented_decision_count`, `obstructed_decision_count`,
     `unknown_decision_count`, `compliance_count`, `refusal_count`,
     `sabotage_count`, `contrary_count`, `implementation_coverage_ratio`,
     `censored_actor_count`.
   - `implementation_coverage_ratio = decisions with at least one
     implementation record / decision_count`; `None` when there are no
     decisions.
4. Append both builders to `_BUILDERS` after the V4-04 operation builders.
5. In `src/analysis/organization_metrics.py`:
   - Add `_agency_summary` and `_agency_availability` helpers.
   - `_agency_availability` returns `ABSENT` when the summary is `None`, or when
     there are no candidates, or when the family's required rows are empty
     (agency family: no proposals and no decisions; implementation family: no
     decisions). It returns `PARTIAL` when `history_truncated`,
     `orphaned_count > 0`, coverage < 1.0, or any decision is `unknown`;
     otherwise `PRESENT`.
   - Add `compute_organization_collective_agency_metric` and
     `compute_organization_collective_implementation_metric` using
     `_document` semantics and quantized floating values.
   - `compliance_count` is the number of `implemented` implementations;
     `refusal_count`/`sabotage_count`/`contrary_count` are actor-level counts.
   - `censored_actor_count` is the number of `unknown` implementations.
6. Export both compute functions from `src/analysis/__init__.py`, and update the
   `organization_metrics.py` module docstring from "Four detached metric
   families" to the actual count.
7. In `src/analysis/metric_service.py`, register both families in the existing
   organization metric block at 1430-1474 with the `_safe(...)` pattern:
   - import both compute functions;
   - call `compute_organization_collective_agency_metric` and
     `compute_organization_collective_implementation_metric` with the
     `organization_analysis`;
   - pass `agency_summary` into `project_organization_layers` and
     `derive_organization_lineage` so the metric documents and the analysis
     digest agree.
8. Update every exact `146` metric-family assertion in the test suite to `148`,
   including `tests/architecture/test_v3_baseline_inventory.py`,
   `tests/architecture/test_path_dependence_boundaries.py`, and family-specific
   tests that pin the current catalog count. Do not rewrite assertions about
   historical counts or older plans.
9. Do not change any earlier family's id, order, version, value keys, or
   formulas.

### Required Interfaces and Contracts

- Catalog count is exactly 148; the last two families are the new ones.
- Family ids render with the existing `@1` algorithm version convention.
- Values are scalar or quantized; no composite score.
- Availability is `ABSENT`/`PARTIAL`/`PRESENT` with explicit denominators.
- The first 146 families are byte-identical in id, order, version, and value
  keys.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Metric families" pin and append-only catalog
  discipline.
- V4-04 `_spec_organization_operations`/`_spec_organization_operation_authority`
  pattern.
- Original Request: recognized outcomes, compliance, refusal, sabotage,
  implementation failure.

### Error Handling and Logging

- A malformed summary raises `organization_agency_metric_invalid`.
- Log INFO `organization_agency_metrics families=2 catalog=148` once.
- WARN if availability is partial with a safe reason code; never log actor sets.

### Tests

Create `tests/unit/test_organization_agency_metrics.py` and
`tests/unit/test_organization_agency_catalog.py`:
- Catalog count is 148; ids unique; last two are the new families.
- The first 146 family ids/order/version/value keys equal a frozen snapshot.
- Both documents have the expected value keys, availability, population,
  denominator, and provenance source kind.
- Absent summary → `ABSENT` with empty values.
- Partial coverage/truncation → `PARTIAL`.
- Recognized/contested/unrecognized/expired counts.
- Implemented/partial/unimplemented/obstructed/unknown counts; compliance,
  refusal, sabotage, contrary, censored actor counts.
- No composite score key.
- Existing V4-04 operation metrics are unchanged.
- `analysis.metric_service.assemble_metric_documents` emits both new documents
  for an arm whose `MetricComputationInputs.organization_agency_rows` are set,
  and omits them (ABSENT) when the rows are empty.
- `tests/unit/test_metric_service.py` and `tests/unit/test_experiment_collectors.py`
  cover the assembly path, not just the compute functions.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_metrics.py tests/unit/test_organization_agency_catalog.py tests/unit/test_organization_operations_metrics.py tests/unit/test_organization_operations_catalog.py tests/unit/test_metric_service.py tests/unit/test_experiment_collectors.py -q`

### Acceptance Criteria

- The catalog is exactly 148 with two appended families.
- All earlier families are unchanged.
- Both families are analysis-only and never feed cognition.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_metrics.py tests/unit/test_organization_agency_catalog.py -q`
- Expected: all tests pass.

## Phase Risks and Mitigations

- Risk: the summary accidentally mints a new `org-` identity.
  Mitigation: the summary accepts existing candidates only; identity functions
  are not imported; a test asserts candidate identities are unchanged.
- Risk: owner ids leak into the objective layer through a new count field.
  Mitigation: the leak check covers every new prefix and a negative test injects
  each one.
- Risk: metric count changes break unrelated pin tests.
  Mitigation: Task 12 updates every 146 assertion to 148 in one pass and Task 21
  runs the full suite.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
