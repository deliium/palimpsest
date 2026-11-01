# Phase 3: Detached Analysis, Disagreement, and Metrics

Plan: [index.md](index.md)
Tasks: 9-12
Depends on: Phase 2 / Tasks 3-8

## Objective

Turn exported owner operation ledgers into detached analysis rows, per-candidate
operation summaries, three-layer projections with hard leakage checks, and two
new metric families. Operations must not create, split, merge, or dissolve
candidates; they describe what owners believe an already-detected structure
controls or does, under which authority, and with which disputes.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/organizations.py` | owner row 79-103; concept rows 105-316; `harvest_organization_rows` 633-656; `harvest_organization_snapshot` 658-666 | The operation harvest follows the same defensive row pattern and rejects duplicate owners. |
| `src/analysis/organization_contract.py` | policy 47-55; `OrganizationCandidateStatus` 72-118; `derive_organization_id` 175-201 | Detached vocabulary and identity remain unchanged. |
| `src/analysis/organization_detection.py` | `OrganizationCandidate` 60-95; `detect_organization_candidates` 378-484 | `owner_ids`, member ids, and anchor signatures are the join keys for operation summaries. |
| `src/analysis/organization_identity.py` | `OrganizationIdentityAssignment` 97-109; `assign_organization_identities` 126-300 | Final-window candidate ids are the analytical keys; operations never mint ids. |
| `src/analysis/organization_layers.py` | `OrganizationObjectiveRow` 33-66; `OrganizationSubjectiveRow` 68-84; `OrganizationLayerView` 85-91; projection 93-224; separation 226-248 | Add operation counts and a summary without moving ids across layers. |
| `src/analysis/organization_lineage.py` | `OrganizationAnalysis` 71-85; `derive_organization_lineage` 146-269; `build_organization_analysis` 314-329 | Add an optional operation summary to the analysis object; lineage rules are untouched. |
| `src/analysis/organization_metrics.py` | `_availability` 52-69; `_document` 71-105; four compute functions 123-305 | The two new families follow the same `MetricDocument` and availability rules. |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53; family ids 218-221; specs 6204-6397; builders 6546-6549; validation 6574 | Raise 144 → 146 by appending two families only. |
| `src/analysis/metric_service.py` | `AnalysisInputs.organization_rows` 311; organization block 1429-1489 | Add `organization_operation_rows` and two `_safe` calls. |
| `src/experiments/collectors.py` | organization harvest 779-789 | Pass the operation ledger rows into metric inputs. |
| `src/experiments/organization_harvest.py` | `OrganizationHarvest` 46-66; builder 68-117 | Add operation rows and the summary to the completed-run harvest. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/organization_operations.py` | create | Detached operation row types, harvest, per-candidate summary, disagreement/provenance classification. |
| `src/analysis/organizations.py` | modify | Re-export or compose operation rows without changing concept rows. |
| `src/analysis/organization_layers.py` | modify | Operation counts in objective/subjective rows and summary in the layer view. |
| `src/analysis/organization_lineage.py` | modify | Optional `operation_summary` on `OrganizationAnalysis`. |
| `src/analysis/organization_metrics.py` | modify | Two compute functions. |
| `src/analysis/specifications.py` | modify | Two family ids/specs/builders; count 146. |
| `src/analysis/metric_service.py` | modify | New input field and two registered metric calls. |
| `src/analysis/__init__.py` | modify | Re-export operation rows/summary/functions. |
| `src/experiments/organization_harvest.py` | modify | Read `organization_operation_ledgers`; build operation rows/summary. |
| `src/experiments/collectors.py` | modify | Pass operation rows to analysis inputs. |
| `tests/unit/test_organization_operations_harvest.py` | create | Row harvest, provenance, empty/missing attributes. |
| `tests/unit/test_organization_operations_analysis.py` | create | Summaries, disagreement, layers, leakage. |
| `tests/unit/test_organization_operations_metrics.py` | create | Two families and availability. |
| `tests/unit/test_organization_operations_catalog.py` | create | 146 catalog registration and append-only order. |

## Task 9: Harvest owner operation ledgers into detached rows

### Intent

Create the only analysis-facing representation of operation beliefs. It must be
defensive (duck-typed attributes), ordered, duplicate-owner-free, and independent
of `agents.cognition`.

### Implementation Steps

1. Create `src/analysis/organization_operations.py` with a module docstring stating
   it is read-only, detached, and never imports `agents.cognition`, world state,
   persistence, API, or infrastructure.
2. Define `OrganizationOperationOwnerRow`:
   - `owner_id`, `concept_count`, `notices`, `policy_version`, and record-family
     counts.
3. Define detached row types mirroring the beliefs, all with `organization_id`
   (`orgc-`):
   - `OrganizationControlRow`: domain, anchor_kind, anchor_id, stance,
     authority_basis, legitimacy_doctrine, decision_ref, role_ref, first_tick,
     last_tick, owner_support_count, contest_count.
   - `OrganizationAdmissionRow`: member_id, stance, authority_basis, role_ref,
     decision_ref, temporal_scope, expires_tick, span, support, contest.
   - `OrganizationDepartureRow`: member_id, stance, authority_basis, decision_ref,
     span, support, contest.
   - `OrganizationAssignmentRow`: office_id, occupant_id, stance, authority_basis,
     decision_ref, span, support, contest.
   - `OrganizationProcedureActionRow`: procedure_ref, command_kind, actor_id,
     outcome, authority_basis, decision_ref, span, support, contest.
   - `OrganizationCommitmentOperationRow`: commitment_id, role, counterpart_id,
     stance, authority_basis, decision_ref, due_tick, span, support, contest.
   - `OrganizationDecisionRow`: decision_id, domain, act, actor_id, target_id,
     anchor_kind, anchor_id, authority_basis, stance, support_count, oppose_count,
     provenance_code, tick.
   - `OrganizationActionRow`: action_id, decision_id, domain, act, actor_id,
     command_kind, anchor_kind, anchor_id, outcome, provenance_code, tick.
4. Add `OrganizationOperationHarvestRows` containing the owner row and every row
   tuple, with `has_operations` and `has_contest` properties.
5. Implement `harvest_organization_operation_rows(ledgers)`:
   - reject duplicate owners;
   - sort owners by id and every tuple deterministically;
   - read documented attributes with `getattr` and skip malformed optional values
     rather than raising on a missing attribute;
   - preserve `orgc-`, `orgd-`, and `orga-` ids in detached rows (analysis may use
     them) but never expose owner ids beyond `owner_id`.
6. Add `harvest_organization_operation_snapshot(runner_result)` reading
   `runner_result.organization_operation_ledgers`.
7. Update `src/experiments/organization_harvest.py`:
   - read `organization_operation_ledgers`;
   - add `operation_rows: tuple[OrganizationOperationHarvestRows, ...] = ()`;
   - call the harvest after the concept rows;
   - keep the empty-run path with empty operation rows.
8. Update `src/analysis/__init__.py` exports.

### Required Interfaces and Contracts

- The harvest never imports `agents.cognition`; it reads duck-typed attributes.
- Duplicate owners, unsorted input, or a foreign owner row fail closed.
- Missing optional attributes produce `None`/empty tuples, never invented zeros
  for unresolved evidence.
- Decision/action ids remain owner-local analysis data and are never published by
  the snapshot layer.
- The function is deterministic: same ledgers → same row order and content.

### Requirement Evidence

- V4-03 `harvest_organization_rows` 633-656 precedent.
- `.ai-factory/ARCHITECTURE.md` "analysis" dependency rule: read-only domain
  contracts, no live cognition.
- Original Request: provenance must be recorded; the harvest preserves decision
  and action ids for analysis.

### Error Handling and Logging

- `OrganizationAnalysisError("organization_operation_row_invalid")` for duplicate
  owners or malformed rows.
- INFO once per harvest:
  `organization_operation_harvest owners=%s concepts=%s decisions=%s actions=%s`.
  No anchors, labels, or ids in logs.

### Tests

- `tests/unit/test_organization_operations_harvest.py`:
  - harvests every record family in deterministic order;
  - duplicate owners fail;
  - missing `organization_operation_ledgers` yields an empty harvest;
  - a ledger with a missing optional attribute is tolerated;
  - the module imports no `agents`, `experiments`, `api`, `persistence`,
    `infrastructure`, or `observer` package.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_harvest.py -q`

### Acceptance Criteria

- All operation record families are harvested.
- The harvest is detached, ordered, and duplicate-free.
- No live cognition or world authority is imported.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_harvest.py -q`
- Expected: pass.

## Task 10: Summarize operations and disagreement per candidate

### Intent

Attach owner-local operation evidence to the analytical candidate it supports
without inventing a new identity or changing detection. The summary is the single
source for snapshot and metric operation counts.

### Implementation Steps

1. Define `OrganizationCandidateOperations`:
   - `organization_id` (`org-` analytical id);
   - `control_counts: tuple[tuple[str, int], ...]` by domain;
   - `admission_count`, `departure_count`, `assignment_count`,
     `procedure_action_count`, `commitment_count`, `decision_count`,
     `action_count`;
   - `contested_domains: tuple[str, ...]` sorted;
   - `authority_counts: tuple[tuple[str, int], ...]`;
   - `provenance_counts: tuple[tuple[str, int], ...]`;
   - `orphaned_count`;
   - `mean_owner_support: float` (quantized to 6 decimals);
   - `coverage_ratio: float | None`.
2. Define `OrganizationOperationSummary` with `candidates`, total counts,
   `orphaned_count`, `history_truncated`, and `coverage`.
3. Implement `summarize_organization_operations(rows, assignment)`:
   - use the final identity window only, matching V4-03's formation population;
     operation concepts whose `last_tick` is before the final window are outside
     the summary population and are not counted as orphaned;
   - for each `(owner_id, organization_id)` operation concept active in the final
     window, find candidate rows in that window whose `owner_ids` contains the
     owner; score by member intersection + anchor-signature intersection; choose
     the highest score with a deterministic tie-break on `candidate_key`;
   - aggregate operation counts into the chosen candidate;
   - count final-window operation concepts that fail to match any candidate as
     `orphaned_count`;
   - a contested record is any `stance == "disputed"` or `contest_count > 0`;
     map it to the record's domain; `contested_domains` is sorted unique;
   - `coverage_ratio` = candidates with any operation / candidates in the window;
   - empty rows → `None`.
4. Add `operation_summary: OrganizationOperationSummary | None = None` to
   `OrganizationAnalysis` and pass it through `derive_organization_lineage` /
   `build_organization_analysis`.
5. Ensure operations never alter candidate status, member ids, anchors, identity
   records, or lineage edges.
6. Log INFO once: `organization_operation_summary candidates=%s contested=%s
   orphaned=%s`.

### Required Interfaces and Contracts

- The summary is keyed by `org-`; owner-local `orgc-` ids never appear in it.
- A candidate may have zero operations; that is valid and not `ABSENT` by itself.
- `contested_domains` uses exactly the eight domain tokens; disagreement is not
  collapsed into a single boolean.
- `mean_owner_support` is a mean of owner-local counts, not a population statistic
  or consensus measure.
- No capacity, prevalence, probability, or prediction field exists.

### Requirement Evidence

- Original Request: "Allow organizations to operate even when members disagree
  about membership, authority, resource legitimacy, procedures."
- V4-03 `OrganizationAnalysis` three-layer contract.
- `src/analysis/organization_layers.py` 226-248 leakage rules.

### Error Handling and Logging

- A missing assignment or empty rows returns `None`/empty summary, never a
  fabricated zero-coverage candidate.
- Ambiguous matches use a deterministic candidate-key tie-break; they are never
  randomly assigned.
- Logs contain counts only; no ids, labels, or anchor values.

### Tests

- `tests/unit/test_organization_operations_analysis.py`:
  - a single operation concept maps to exactly one final-window candidate;
  - two owners with overlapping concepts map deterministically;
  - ambiguous equal-overlap cases use `candidate_key`;
  - contested control/assignment/procedure records produce the right
    `contested_domains`;
  - unmatched operations increment `orphaned_count`;
  - empty rows return `None`;
  - operations do not change candidate status/members/anchors/lineage.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_analysis.py -q`

### Acceptance Criteria

- Per-candidate operation counts, authority, provenance, and disagreement exist.
- Summary keys are analytical `org-` ids only.
- Detection, identity, and lineage are unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_analysis.py -q`
- Expected: pass.

## Task 11: Project operations into the three layers without leakage

### Intent

Keep the V4-03 authority separation enforceable: objective counts carry no
organization ids, subjective rows carry `orgc-`, and analytical operations carry
`org-`. Operations must never leak owner-local decisions into objective rows.

### Implementation Steps

1. Extend `OrganizationObjectiveRow` with `operation_action_count: int = 0`. The
   value is the number of observed action rows overlapping the window; it carries
   no ids and no per-owner detail.
2. Extend `OrganizationSubjectiveRow` with `operation_count: int = 0` and
   `contested_operation_count: int = 0`, computed from the owner's operation rows
   for that `orgc-` concept.
3. Extend `OrganizationLayerView` with
   `operations: OrganizationOperationSummary | None = None`.
4. Change `project_organization_layers(detection, owner_rows, operation_summary=None)`
   to attach the summary and compute the new counts. Keep the existing
   `detection` union type.
5. Extend `assert_organization_layer_separation`:
   - objective rows still must not contain `orgc-` or `org-` in any string field;
   - subjective rows must use `orgc-`;
   - analytical candidate ids must be `org-`;
   - operation summary candidate ids must be `org-` and must not contain `orgc-`,
     `orgd-`, or `orga-`.
6. Update `src/experiments/organization_harvest.py` to pass the summary into
   `project_organization_layers` and into the final analysis object.
7. Update `src/analysis/metric_service.py` to build the summary before layers and
   pass it through.

### Required Interfaces and Contracts

- Objective rows are counts only. They never include a decision/action id or an
  owner id.
- Subjective rows remain owner-local and may include counts but not peer details.
- The analytical summary is detached and may be published.
- `operation_action_count` is an observed action count, not an organization
  capability or throughput.
- Existing layer separation behavior for V4-03 rows is unchanged.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1: objective state, owner-scoped
  belief, and retrospective analysis are different authorities.
- V4-03 plan decision 8 and Task 11 tests.
- Original Request: "Keep objective physical possession separate from
  subjective/legal ownership."

### Error Handling and Logging

- A summary with an `orgc-` id raises `organization_layer_leak`; the offending
  field name is logged at ERROR with a safe code only.
- Missing operation rows leave the new counts at 0; they are not treated as a
  leakage or a failure.

### Tests

- `tests/unit/test_organization_operations_analysis.py`:
  - objective rows contain no organization/decision/action ids;
  - subjective rows use `orgc-` and count owner operations;
  - analytical summary uses `org-` only;
  - a deliberately leaked `orgc-` in the summary raises `organization_layer_leak`;
  - an empty summary is legal and yields zero counts.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_analysis.py tests/unit/test_organization_layers.py -q`

### Acceptance Criteria

- The three layers remain distinct.
- Operations add counts to objective/subjective rows and a detached summary.
- No owner-local provenance id reaches the objective layer.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_analysis.py tests/unit/test_organization_layers.py -q`
- Expected: pass.

## Task 12: Add two metric families and raise the catalog to 146

### Intent

Measure operational coverage and authority/disagreement without changing any of
the four V4-03 families. The catalog moves 144 → 146 by appending exactly two
families.

### Implementation Steps

1. In `src/analysis/specifications.py`:
   - set `METRIC_FAMILY_COUNT = 146`;
   - add `MetricFamilyId.ORGANIZATION_OPERATIONS = "organization_operations"` and
     `MetricFamilyId.ORGANIZATION_OPERATION_AUTHORITY = "organization_operation_authority"`;
   - add `_spec_organization_operations()` and
     `_spec_organization_operation_authority()` after the four V4-03 specs;
   - append them to `_BUILDERS`;
   - keep every existing family id, order, version, and value-key set unchanged.
2. `organization_operations@1` value keys (exact set):
   `as_of_tick`, `control_count`, `storage_count`, `record_keeping_count`,
   `admission_count`, `departure_count`, `assignment_count`,
   `procedure_action_count`, `commitment_count`, `decision_count`,
   `action_count`, `contested_operation_count`, `orphaned_operation_count`,
   `provenance_known_count`, `operation_coverage_ratio`.
   `control_count` counts `resource_control` only; storage and record keeping are
   counted by their own keys.
3. `organization_operation_authority@1` value keys (exact set):
   `as_of_tick`, `authority_self_authored_count`, `authority_role_count`,
   `authority_decision_count`, `authority_procedure_count`,
   `authority_observation_count`, `authority_unknown_count`,
   `resource_contest_count`, `membership_contest_count`,
   `authority_contest_count`, `procedure_contest_count`, `orphaned_count`,
   `mean_owner_support`.
   `resource_contest_count` covers `resource_control`; `membership_contest_count`
   covers admission/departure/role assignment; `authority_contest_count` covers
   decisions with unknown/contested authority; `procedure_contest_count` covers
   procedure actions.
4. Add `compute_organization_operations_metric(summary, *, run_id,
   input_revision, tick=None)` and
   `compute_organization_operation_authority_metric(summary, *, run_id,
   input_revision, tick=None)` in `organization_metrics.py`, returning
   `MetricDocument` through the existing `_document` helper. Re-export both from
   `analysis/__init__.py`.
5. Availability:
   - `ABSENT` when the summary is `None`, the final window has no candidates, or
     there are no operation rows;
   - `PARTIAL` when history is truncated, any candidate lacks operation evidence,
     coverage ratio is `< 1`, or orphaned operations exist;
   - `COMPLETE` otherwise.
6. In `metric_service.py`, add `organization_operation_rows: Sequence[object] |
   None = None` to `AnalysisInputs`; build the summary before layers; call both
   metrics with `_safe`.
7. In `experiments/collectors.py`, pass
   `organization_operation_rows=harvest_organization_operation_rows(...)` when
   `organization_operation_ledgers` is present.
8. Do not add a composite score, capacity, prevalence, probability, or prediction
   key.

### Required Interfaces and Contracts

- The new families append after `organization_lineage@1`; the previous 144
  specifications are byte-for-byte unchanged in id/order/version/value keys.
- Both families are scalar-only; no graph strings or payload surrogates.
- `operation_coverage_ratio` is covered candidates / final-window candidates;
  `None` when there are no candidates.
- `mean_owner_support` is the mean of owner-local support counts, never a
  population consensus.
- `provenance_known_count` counts records whose provenance is not
  `unknown_authority`.
- The two families are `ABSENT` for flags-off runs and for runs with no operation
  ledger.

### Requirement Evidence

- V4-03 metric catalog 140 → 144 precedent and exact `value_keys` discipline.
- `.ai-factory/ARCHITECTURE.md` versioned extension contract: accepted-set and
  exact-key-set evolution.
- Original Request: provenance and disagreement must be observable.

### Error Handling and Logging

- Metric assembly is wrapped by the existing `_safe` helper; one failing family
  becomes an unavailable document, not a run failure.
- Log INFO `organization_operation_metrics operations=%s authority=%s` with
  availability tokens only.

### Tests

- `tests/unit/test_organization_operations_metrics.py`:
  - both families validate at exact value-key sets and `@1`;
  - empty summary → `ABSENT`;
  - one candidate with operations → expected counts and `COMPLETE`;
  - contested records populate the four contest keys;
  - truncated history/orphaned operations → `PARTIAL`;
  - no composite score key exists.
- `tests/unit/test_organization_operations_catalog.py`:
  - `METRIC_FAMILY_COUNT == 146`;
  - the last two specs are the new families and the preceding four are the V4-03
    families;
  - the first 144 family ids/versions are unchanged.
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_metrics.py tests/unit/test_organization_operations_catalog.py -q`

### Acceptance Criteria

- The catalog is exactly 146.
- Existing families are unchanged.
- Operations and authority/disagreement are measurable with explicit coverage.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_metrics.py tests/unit/test_organization_operations_catalog.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: operation rows create new candidates or change lineage.
  Mitigation: the summary consumes `assignment` and only joins to existing
  candidates; tests assert status/members/anchors/lineage are unchanged.
- Risk: owner-local ids leak into the objective or published layers.
  Mitigation: layer separation checks `orgc-`/`orgd-`/`orga-` explicitly.
- Risk: the metric catalog changes existing families.
  Mitigation: append-only specs and a test that pins the first 144.
- Risk: a missing operation ledger is treated as zero capability.
  Mitigation: `ABSENT`/`PARTIAL` availability and no zero-fill.

## Phase Completion Checklist

- Every Task 9-12 acceptance criterion is met.
- Operation rows, summaries, layers, and two families work end to end in
  detached analysis.
- The catalog is 146 and existing families are untouched.
- `index.md` task checkboxes are updated immediately after verified completion.
