# Phase 3: Detached Analysis, Competing Systems, and Metrics

Plan: [index.md](index.md)
Tasks: 9-12
Depends on: Phase 2 / Task 8

## Objective

Harvest exported formal-rule ledgers into detached rows, build bounded evidence
windows, detect overlapping rule-system candidates without combining competing
systems, mint stable analytical identities, project three separated layers, and
append exactly three metric families (148 → 151) through real completed-run
assembly.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/organizations.py` | owner/concept rows 107-346; harvest 660-685 | Detached row shape and harvest entrypoint. |
| `src/analysis/organization_evidence.py` | window evidence 69; build windows 151 | Tick-window evidence pattern. |
| `src/analysis/organization_detection.py` | candidate 61; union-find 117; detection 378 | Overlap-legal candidate detection (never a partition). |
| `src/analysis/organization_identity.py` | identity assignment 97-126 | Stable creation-evidence ids and transitions. |
| `src/analysis/organization_lineage.py` | edge 48; analysis 74; derive 167; validate 295 | Forward-only lineage contract. |
| `src/analysis/organization_layers.py` | objective 40; subjective 83; view 117; projection 126; separation 326 | Three-layer separation and leakage guard. |
| `src/analysis/organization_metrics.py` | metric functions 370-599 | Availability/coverage document pattern. |
| `src/analysis/organization_agency.py` | rows 95-255; summary 621-736 | Summary/candidate map pattern. |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53; family enum 218-225; builder tail 6812-6819 | Catalog append point; first 148 must not move. |
| `src/analysis/metric_service.py` | inputs 311-313; organization block 1431-1558 | Assembly and fingerprint pattern. |
| `src/experiments/collectors.py` | organization carry 779-817 | Completed-run collector wiring. |
| `src/experiments/organization_harvest.py` | harvest 59-138 | Runner-result harvest bridge. |
| `tests/unit/test_organization_agency_metrics.py` | append/first-146 pins 100-114 | Pin style for the new append. |
| `tests/unit/test_organization_operations_regression.py` | 148 tail pin 52-62 | Must become 151 with the new tail. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/formal_rule_contract.py` | create | Analysis policy, ids, statuses, coverage, errors. |
| `src/analysis/formal_rules.py` | create | Detached rows and harvest. |
| `src/analysis/formal_rule_evidence.py` | create | Bounded windows and objective anchors. |
| `src/analysis/formal_rule_detection.py` | create | Overlap-legal candidate detection. |
| `src/analysis/formal_rule_identity.py` | create | Stable `frule-` identity and transitions. |
| `src/analysis/formal_rule_lineage.py` | create | Forward-only lineage and analysis digest. |
| `src/analysis/formal_rule_layers.py` | create | Three-layer projection and leakage guard. |
| `src/analysis/formal_rule_metrics.py` | create | Three metric documents. |
| `src/analysis/specifications.py` | modify | Append three families; count 148 → 151. |
| `src/analysis/metric_service.py` | modify | Input slot, assembly block, fingerprints. |
| `src/experiments/collectors.py` | modify | Carry `formal_rule_ledgers` into inputs. |
| `tests/unit/test_formal_rule_analysis.py` | create | Rows, windows, detection, identity, lineage. |
| `tests/unit/test_formal_rule_layers.py` | create | Three layers and leakage. |
| `tests/unit/test_formal_rule_metrics.py` | create | Metric documents and exact value keys. |
| `tests/unit/test_formal_rule_catalog.py` | create | 151 count and unchanged first 148. |
| `tests/unit/test_formal_rule_metric_service.py` | create | Completed-run assembly emits all three. |

## Task 9: Harvest owner formal-rule ledgers into detached rows and windows

### Intent

Normalize exported ledgers into a read-only row bundle that the rest of analysis
can consume without importing cognition types or live services.

### Implementation Steps

1. Create `src/analysis/formal_rule_contract.py`:
   - `FORMAL_RULE_ANALYSIS_POLICY_VERSION = "formal-rule-analysis.v1"`
   - `FORMAL_RULE_IDENTITY_POLICY_VERSION = "formal-rule-identity.v1"`
   - `FORMAL_RULE_CANDIDATE_ID_PREFIX = "frule-"`
   - `FORMAL_RULE_EDGE_ID_PREFIX = "frule-edge-"`
   - `FORMAL_RULE_ID_HEX_LEN = 16`
   - `FORMAL_RULE_MAX_HARVEST_RULES = 4096`
   - `FormalRuleCoverage(observed, expected, partial)` with an explicit
     `coverage_fraction` property returning `None` when `expected == 0`; analysis,
     layers, snapshot, and API all use this one type/shape.
   - `FormalRuleCandidateStatus`: `recognized`, `partial`, `contested`,
     `fragmented`, `temporary`, `dissolved`
   - `FormalRuleLayer`: `objective`, `subjective`, `analytical`
   - `FormalRuleLineageKind`: `continued`, `transformed`, `split`, `merge`,
     `dissolved`, `emerged`
   - `FormalRuleAnalysisError` with safe codes.
   - `derive_formal_rule_id(creation_digest) -> frule-<16hex>`;
     `formal_rule_edge_id(source, target, kind, tick) -> frule-edge-<16hex>`
     using a canonical SHA-256 over the four fields and a
     `formal-rule-edge` domain separator; `require_formal_rule_candidate_id`;
     `require_formal_rule_edge_id`.
   - `FormalRuleCoverage` is never duplicated as a tuple or dict in Tasks 10-11;
     snapshot models accept the same observed/expected/partial values.
2. Create `src/analysis/formal_rules.py` with frozen rows:
   - `FormalRuleOwnerRow(owner_id)`
   - `FormalRuleSystemRow(owner_id, system_id, scope_kind, scope_digest,
     authority_kind, rule_ids, status, competing_system_ids, first_tick,
     last_tick)`
   - `FormalRuleRow(owner_id, rule_id, system_id, stage, constraint_kind,
     action_token, scope_kind, scope_digest, authority_kind, recognition,
     status, strength, version_count, written_status, sanction_kinds,
     exception_count)`
   - `FormalRuleVersionRow(owner_id, rule_id, version_id, version_number, stage,
     constraint_kind, scope_kind, scope_digest, action_token, authority_kind,
     recognition, written_status, tick, revision_kind)`
   - `FormalRulePositionRow(owner_id, rule_id, position_id, actor_id, stance,
     provenance, tick)`
   - `FormalRuleResponseRow(owner_id, rule_id, response_id, actor_id, kind,
     provenance, tick)`
   - `FormalRuleEvidenceRow(owner_id, rule_id, evidence_id, channel, provenance,
     tick, artifact_present, repository_present)`
   - `FormalRuleHarvestRows(owners, systems, rules, versions, positions,
     responses, evidence, window_ticks)`
3. Implement `harvest_formal_rule_rows(ledgers, *, window_ticks)`. Accept a
   sequence of exported ledgers, validate owner uniqueness and ordering, and
   emit sorted rows. Reject non-ledger objects with
   `formal_rule_harvest_invalid`.
4. Create `src/analysis/formal_rule_evidence.py`:
   - `FormalRuleObjectiveAnchorRow(tick, observed_artifact_count,
     observed_repository_count, observed_occurrence_count,
     known_person_ids, scope_anchor_ids)`
   - `FormalRuleWindowEvidence(start_tick, end_tick, owner_rows, objective_rows,
     rule_ids, system_ids, lane_presence)`
   - `build_formal_rule_windows(rows, *, window_ticks)` groups by complete
     windows, never fabricates a missing tick, and marks coverage `partial` when
     any tick is missing.
5. No cognition, simulation runtime, API, persistence, or experiment import.
   Analysis imports only public contracts and its own modules.
6. Do not read a world event store, a `WorldState`, or a command. Objective
   anchor rows are supplied by the caller from detached evidence.

### Required Interfaces and Contracts

```python
def harvest_formal_rule_rows(
    ledgers: Sequence[object],
    *,
    window_ticks: int,
) -> FormalRuleHarvestRows: ...

def build_formal_rule_windows(
    rows: FormalRuleHarvestRows,
    *,
    window_ticks: int,
) -> tuple[FormalRuleWindowEvidence, ...]: ...

def formal_rule_edge_id(source: str, target: str, kind: str, tick: int) -> str: ...
```

- Rows are frozen, sorted, and duplicate-free.
- `frule-` ids are minted only in Task 10, never in rows.
- A harvest never mutates an owner ledger.
- Missing owner ledgers are absent, not synthesized.

### Requirement Evidence

- `analysis/organizations.py` 107-346, 660-685.
- `analysis/organization_evidence.py` 69, 151.
- `.ai-factory/ARCHITECTURE.md` "analysis is read-only" and dependency table.

### Error Handling and Logging

- Invalid ledger/owner/order: `formal_rule_harvest_invalid`.
- Window overflow: trim complete windows and mark `partial` coverage.
- INFO: `formal_rule_harvest owners=%s rules=%s windows=%s` (counts only).
- WARN on partial coverage with counts.
- Never log owner ids, rule ids, scope digests, action tokens, or positions.

### Tests

`tests/unit/test_formal_rule_analysis.py`:

- `test_harvest_is_sorted_unique_and_owner_scoped`
- `test_harvest_rejects_non_ledgers_and_duplicate_owners`
- `test_windows_do_not_fabricate_missing_ticks`
- `test_partial_coverage_is_explicit`
- `test_analysis_imports_no_cognition_runtime_or_persistence`

Run: `uv run pytest tests/unit/test_formal_rule_analysis.py -q`.

### Acceptance Criteria

- A complete ledger set produces deterministic rows and windows.
- Missing evidence is visible as partial coverage, never invented.
- No `frule-` identity is minted yet.

### Verification

- `uv run pytest tests/unit/test_formal_rule_analysis.py -q`
- `uv run lint-imports`

## Task 10: Detect and summarize formal-rule systems without minting owner identity

### Intent

Create detached `frule-` candidates that may overlap and compete, assign stable
identities across windows, and summarize development/authority/response counts
per candidate. This layer must not create an objective rule or alter an
organization candidate.

### Implementation Steps

1. `src/analysis/formal_rule_detection.py`:
   - `FormalRuleMemberClaim` and `FormalRuleCandidate` records with
     `candidate_key`, scope/action/constraint/authority anchors, owner ids,
     tick span, status, and coverage.
   - `detect_formal_rule_candidates(rows, windows)` uses connected components
     over shared scope digest + action token + authority family. Two rules with
     the same scope/action but different constraints stay **separate**
     candidates that share an overlap anchor; they are never unioned.
   - Candidate keys are `cand-<16hex>` internal keys; `frule-` is assigned by
     identity.
2. `src/analysis/formal_rule_identity.py`:
   - `FormalRuleRecord`, `FormalRuleTransition`, `FormalRuleWindowSnapshot`,
     `FormalRuleIdentityAssignment`.
   - `assign_formal_rule_identities(windows)` walks windows in tick order and
     assigns `frule-` ids from creation evidence: sorted owner ids + scope digest
     + action token + constraint + first tick.
   - Continuation threshold Jaccard `0.5`; transformation `0.75`; split
     containment `0.4`; merge absorption `0.5`. Preserve the prior id on
     continuation; mint a new id on split/merge/emergence.
   - Competing candidates retain distinct ids even when their anchor sets
     overlap.
3. `src/analysis/formal_rule_lineage.py`:
   - `FormalRuleLineageEdge(edge_id, source_candidate_id, target_candidate_id,
     kind, tick, jaccard, containment)`.
   - `FormalRuleAnalysis(windows, records, edges, coverage, summaries,
     determinism_digest)`.
   - `derive_formal_rule_lineage(...)` and `validate_formal_rule_lineage(...)`.
   - Only forward edges in tick order; no cycles; endpoints exist; no lineage
     edge may point at an organization `org-` or macro-society `msoc-` id.
4. Add summary structs:
   - `FormalRuleCandidateDevelopment(candidate_id, stage_counts,
     documented_count, recognized_enforcement_count, written_count,
     mean_version_count, coverage)`
   - `FormalRuleCandidateAuthority(candidate_id, system_count, proponent_count,
     recognized_authority_count, authority_histogram, competing_count,
     contested_count, coverage)`
   - `FormalRuleCandidateResponse(candidate_id, follow_count, violate_count,
     challenge_count, reinterpret_count, ignore_count, sanction_histogram,
     exception_count, coverage)`
   - `FormalRuleSummary(candidates, development, authority, response,
     coverage: FormalRuleCoverage, determinism_digest)`
5. `summarize_formal_rules(rows, analysis)` produces the summary without
   filtering or re-identifying candidates.
6. Add `formal_rule_analysis_digest` over sorted semantic content; no dict
   insertion order, no wall clock.

### Required Interfaces and Contracts

```python
def detect_formal_rule_candidates(rows, windows) -> tuple[FormalRuleCandidate, ...]: ...
def assign_formal_rule_identities(windows) -> FormalRuleIdentityAssignment: ...
def derive_formal_rule_lineage(rows, windows) -> FormalRuleAnalysis: ...
def summarize_formal_rules(rows, analysis) -> FormalRuleSummary: ...
```

- Competing systems may share anchors and still be separate candidates.
- A candidate id never changes across continuation.
- No organization/macro-society candidate is created, split, merged, dissolved,
  or re-identified.
- A missing window yields `partial` coverage, not a false continuation.

### Requirement Evidence

- Original Request "Allow competing rule systems".
- `organization_detection.py` 378-484; `organization_identity.py` 126-300;
  `organization_lineage.py` 146-269.
- `organization_layers.py` 226-303.

### Error Handling and Logging

- Unknown endpoint/duplicate id/cycle: `formal_rule_lineage_invalid`.
- Bad candidate key: `formal_rule_candidate_invalid`.
- INFO: `formal_rule_analysis candidates=%s edges=%s` (counts only).
- WARN on partial coverage or truncated lineage.
- Never log candidate anchors, owner sets, scope digests, or rule ids.

### Tests

`tests/unit/test_formal_rule_analysis.py` (continue):

- `test_opposite_constraints_remain_separate_candidates`
- `test_competing_candidates_may_share_anchors`
- `test_identity_is_stable_on_continuation`
- `test_split_and_merge_mint_forward_only_ids`
- `test_lineage_is_acyclic_and_forward_only`
- `test_formal_rule_lineage_never_references_organization_candidates`
- `test_summary_is_deterministic_under_row_permutation`

Run: `uv run pytest tests/unit/test_formal_rule_analysis.py -q`.

### Acceptance Criteria

- Two competing systems are two candidates, not one merged candidate.
- Identity is deterministic across repeated runs and row orderings.
- No objective rule or organization identity is created.

### Verification

- `uv run pytest tests/unit/test_formal_rule_analysis.py -q`
- `uv run mypy src/analysis`

## Task 11: Project formal rules into the three layers without leakage

### Intent

Keep objective counts, owner claims, and analytical summaries in separate types
so later metrics and publications cannot collapse them into one truth model.

### Implementation Steps

1. Create `src/analysis/formal_rule_layers.py`:
   - `FormalRuleObjectiveRow(tick, observed_artifact_count,
     observed_repository_count, observed_occurrence_count)`.
   - `FormalRuleSubjectiveRow(owner_id, system_ids, rule_ids, stage_counts,
     status_counts, response_counts)`.
   - `FormalRuleAnalyticalRow(candidate_id, status, scope_kind, action_token,
     constraint_kinds, stage, rule_count, version_count,
     competing_candidate_ids)`.
   - `FormalRuleLayerView(objective, subjective, analytical, summary,
     coverage: FormalRuleCoverage)`.
2. `project_formal_rule_layers(rows, analysis, summary)` builds the view.
3. `assert_formal_rule_layer_separation(view)` rejects:
   - owner ids in objective/analytical rows;
   - `frs-`/`frl-`/`frv-`/`fre-`/`frp-`/`frr-`/`frx-` ids in objective rows;
   - `frule-` ids in subjective rows;
   - counts in subjective/analytical rows that are raw event payloads;
   - any `org-`, `msoc-`, or world entity id used as a formal-rule candidate id.
4. Add `formal_rule_layer_digest` for deterministic equality.
5. Do not import cognition, simulation runtime, experiments, persistence, API, or
   observer.

### Required Interfaces and Contracts

- `FormalRuleObjectiveRow` contains counts only, never ids or claims.
- `FormalRuleSubjectiveRow` contains owner-local ids and status/count summaries.
- `FormalRuleAnalyticalRow` contains `frule-` candidates and no owner ids.
- Leakage raises `FormalRuleAnalysisError("formal_rule_layer_leakage")`.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` Key Principle 1.
- `organization_layers.py` 40-326.

### Error Handling and Logging

- Leakage: `formal_rule_layer_leakage` with the field name only.
- INFO: `formal_rule_layers objective=%s subjective=%s analytical=%s`.
- Never log the leaked value.

### Tests

`tests/unit/test_formal_rule_layers.py`:

- `test_objective_layer_has_counts_only`
- `test_subjective_layer_contains_owner_local_ids`
- `test_analytical_layer_contains_only_frule_ids`
- `test_leakage_is_a_hard_failure`
- `test_layer_digest_is_order_independent`

Run: `uv run pytest tests/unit/test_formal_rule_layers.py -q`.

### Acceptance Criteria

- The three layers are distinct runtime types.
- Any cross-layer id or payload fails closed.
- The projection is deterministic.

### Verification

- `uv run pytest tests/unit/test_formal_rule_layers.py -q`
- `uv run lint-imports`

## Task 12: Add three metric families and raise the catalog to 151

### Intent

Publish the requested dimensions as detached metric documents and wire them into
real completed-run assembly, not only direct test calls.

### Implementation Steps

1. In `src/analysis/specifications.py`:
   - set `METRIC_FAMILY_COUNT = 151`;
   - append `MetricFamilyId.FORMAL_RULE_DEVELOPMENT`,
     `FORMAL_RULE_AUTHORITY`, `FORMAL_RULE_RESPONSE` after
     `ORGANIZATION_COLLECTIVE_IMPLEMENTATION` (the enum currently ends at 225);
   - add three `MetricSpecification` builders and append them to `_BUILDERS`
     after the organization builders at 6812-6819. Do not reorder existing
     builders.
2. Exact family contracts:

| Family | Algorithm / schema | Value keys |
|--------|--------------------|------------|
| `formal_rule_development@1` | `formal-rule-development.v1` / `formal-rule-development-v1` | `candidate_count`, `active_count`, `documented_count`, `recognized_enforcement_count`, `stage_histogram`, `constraint_histogram`, `written_representation_count`, `mean_version_count`, `coverage` |
| `formal_rule_authority@1` | `formal-rule-authority.v1` / `formal-rule-authority-v1` | `system_count`, `proponent_count`, `recognized_authority_count`, `authority_histogram`, `competing_system_count`, `contested_system_count`, `coverage` |
| `formal_rule_response@1` | `formal-rule-response.v1` / `formal-rule-response-v1` | `follow_count`, `violate_count`, `challenge_count`, `reinterpret_count`, `ignore_count`, `response_histogram`, `expected_sanction_histogram`, `exception_count`, `coverage` |

   Value keys must be unique, non-empty, sorted where the existing catalog
   convention requires it, and quantized through the existing metric helpers.
3. Create `src/analysis/formal_rule_metrics.py` with:
   - `compute_formal_rule_development_metric(summary, layers)`
   - `compute_formal_rule_authority_metric(summary, layers)`
   - `compute_formal_rule_response_metric(summary, layers)`
   Each returns the existing metric-document shape with availability `absent`,
   `partial`, or `present`, and a coverage value.
4. `src/analysis/metric_service.py`:
   - add `formal_rule_rows: Sequence[object] | None = None` to
     `MetricComputationInputs` after `organization_agency_rows`;
   - after the organization block (1431-1558), run harvest → windows → detect →
     identity → lineage → layers → summary → three metric appends;
   - add fingerprints and canonical encoding for all three;
   - do not alter organization metric computation or ordering.
5. `src/experiments/collectors.py`: in `assemble_arm_metric_bundle`, carry
   `runner_result.formal_rule_ledgers` through
   `harvest_formal_rule_rows` and `replace(inputs, formal_rule_rows=...)`
   before `assemble_metric_documents`.
6. Update every hard-coded `148` metric-catalog assertion to `151`. Use
   `grep -rn "148" tests/unit tests/architecture` and change only catalog count
   assertions, not unrelated numeric literals. At minimum:
   - `tests/unit/test_metric_specifications.py` 42-55
   - `tests/unit/test_organization_catalog.py` 25-29
   - `tests/unit/test_organization_operations_regression.py` 52-62
   - `tests/unit/test_organization_agency_metrics.py` 100-114
   - `tests/unit/test_organization_operations_catalog.py`
   - `tests/unit/test_macro_society_catalog.py`
   - `tests/unit/test_cultural_evolution_metric_service.py` 81-82
   - `tests/unit/test_technique_lifecycle_metrics.py` 35
   - `tests/unit/test_historical_memory_metrics.py` 68
   - `tests/unit/test_institutional_memory_metrics.py` 189
   - `tests/unit/test_knowledge_genealogy_metrics.py` 48
   - `tests/unit/test_dependency_care_metrics.py` 30
   - `tests/unit/test_developmental_learning_metrics.py` 33
   - `tests/unit/test_regional_demographics.py` 622-623
   - `tests/unit/test_public_good_metrics.py` 28
   - `tests/unit/test_structured_commitments_metrics.py` 50
   - `tests/unit/test_subjective_value_metrics.py` 30
   - `tests/unit/test_translation_rows.py` 136
   - `tests/unit/test_mentorship_metrics.py` and the remaining files reported by
     the grep.
7. Update the last-family-order pins so the tail is exactly
   `formal_rule_development`, `formal_rule_authority`, `formal_rule_response`.
8. Add `tests/unit/test_formal_rule_catalog.py`:
   - `test_catalog_validates_at_151`
   - `test_first_148_families_are_unchanged`
   - `test_three_formal_rule_families_are_last`
   - `test_each_family_has_exact_value_keys`
   - `test_version_identifiers_are_id_at_1`
9. Add `tests/unit/test_formal_rule_metrics.py`:
   - `test_absent_when_no_rows`
   - `test_partial_coverage_is_explicit`
   - `test_development_histograms_and_counts`
   - `test_authority_competing_and_contested_counts`
   - `test_response_counts_and_sanctions`
   - `test_documents_are_deterministic_under_permutation`
10. Add `tests/unit/test_formal_rule_metric_service.py`:
    - `test_completed_run_inputs_emit_all_three_documents`
    - `test_collector_carries_formal_rule_ledgers`
    - `test_metric_service_rejects_catalog_drift`
11. Do not add analysis types to simulation or persistence.

### Required Interfaces and Contracts

- Catalog count is exactly 151; the first 148 family ids, order, versions, and
  value keys are byte-identical.
- New documents use existing schema/version/fingerprint enveloping.
- Availability is `absent` when no formal-rule rows exist, `partial` when
  coverage is incomplete, and `present` when all required lanes are covered.
- A metric never mints a candidate or changes identity.
- A metric never reads live cognition or world authority.

### Requirement Evidence

- `specifications.py` 52-53, 218-225, 6671-6825.
- `metric_service.py` 217-331, 401-431, 1431-1558.
- `collectors.py` 105-817.
- `organization_metrics.py` 370-599.
- `.ai-factory/ARCHITECTURE.md` "analysis is read-only" and metric append rules.

### Error Handling and Logging

- Unknown catalog family: existing `metric_specification` failure path.
- Missing rows: availability `absent`, no exception.
- Partial coverage: `partial`, WARN with counts.
- Truncation: `formal_rule_truncated` notice propagated into coverage.
- INFO: `formal_rule_metrics documents=3`.
- Never log row contents, owner ids, rule ids, scope digests, or action tokens.

### Tests

- `uv run pytest tests/unit/test_formal_rule_catalog.py tests/unit/test_formal_rule_metrics.py tests/unit/test_formal_rule_metric_service.py -q`
- `uv run pytest tests/unit/test_metric_specifications.py tests/unit/test_organization_catalog.py tests/unit/test_organization_agency_metrics.py -q`
- Expected: 151 families; the first 148 unchanged; all three documents emitted
  by completed-run assembly.

### Acceptance Criteria

- The catalog is exactly 151 and validates.
- The first 148 entries are unchanged in id, order, version, and value keys.
- Completed-run assembly emits the three new documents.
- No analysis type leaks into simulation or persistence.

### Verification

- `uv run pytest tests/unit/test_formal_rule_catalog.py tests/unit/test_formal_rule_metrics.py tests/unit/test_formal_rule_metric_service.py -q`
- `uv run python -c "from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications as a; assert METRIC_FAMILY_COUNT == 151 == len(a())"`
- `uv run lint-imports`

## Phase Risks and Mitigations

- Risk: competing systems are merged by union-find.
  Mitigation: union only on shared scope/action/authority family with the same
  constraint; opposite constraints share an anchor but never a component.
- Risk: metric assembly only works in direct unit calls.
  Mitigation: Task 12 wires `MetricComputationInputs.formal_rule_rows` and
  `experiments.collectors`, and tests completed-run assembly.
- Risk: the 148 → 151 update misses a hard-coded test.
  Mitigation: run the grep from step 6 and the full `tests/unit` lane in Task 21.
- Risk: analysis creates organization identity.
  Mitigation: lineage validation rejects `org-`/`msoc-` endpoints, and Task 11
  leakage checks reject cross-type ids.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
- First 148 metric families unchanged; three new families appended.
- No analysis import enters simulation or persistence.
