# Phase 3: Detached Analysis, Candidates, and Metrics

Plan: [index.md](index.md)
Tasks: 10-13
Depends on: Phase 2 / Tasks 4-9

## Objective

Project exported dispute ledgers into detached, deterministic analysis: normalized
rows, objective anchors from committed history, windows, cross-owner candidates,
forward-only lineage, three strictly separated layers, and three additive metric
families. Analysis may know objective history; agents must not.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/formal_rules.py` | detached row dataclasses; `harvest_formal_rule_rows` 298-312 | Duck-typed ledger harvesting, sorting, duplicate rejection. |
| `src/analysis/formal_rule_evidence.py` | `FormalRuleObjectiveAnchorRow`, `FormalRuleWindowEvidence`, `build_formal_rule_windows` | Objective anchor/window pattern. |
| `src/analysis/formal_rule_detection.py` | `FormalRuleMemberClaim`, `FormalRuleCandidate`, `detect_formal_rule_candidates` | Cross-owner candidate detection pattern. |
| `src/analysis/formal_rule_identity.py` | `FormalRuleRecord`, `assign_formal_rule_identities` | Forward-only identity transitions. |
| `src/analysis/formal_rule_layers.py` | `FormalRuleObjectiveRow` 34; `FormalRuleSubjectiveRow` 42; `FormalRuleAnalyticalRow` 52; `project_formal_rule_layers` 81; leakage guards 226-303 | Three-layer separation pattern. |
| `src/analysis/formal_rule_lineage.py` | `FormalRuleLineageEdge`, `derive_formal_rule_lineage`, `summarize_formal_rules` | Lineage/summary pattern. |
| `src/analysis/formal_rule_metrics.py` | three metric functions | Family computation pattern. |
| `src/analysis/mediation.py` | `mediation_effect_rows_from_events` 461-502 | Event-to-detached-row projection with `entity_to_agent`. |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53; `MetricFamilyId` 75-228; `_BUILDERS` 6965-6984 | Append-only catalog registration. |
| `src/analysis/metric_service.py` | `MetricComputationInputs` 218-327; formal-rule block 1561-1625 | Input slice and assembly pattern. |
| `src/experiments/collectors.py` | formal-rule carry 817-826; `events` 176-179; `entity_to_agent` 670-672 | Harvester and objective-anchor wiring. |
| `src/world/events.py` | `take` 586; `give` 623; `attack` 827; `exchange_completed`; artifact/storage events | Objective anchor event kinds. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/disputes.py` | create | Detached row types and `harvest_dispute_rows`. |
| `src/analysis/dispute_evidence.py` | create | Objective anchors, windows, coverage. |
| `src/analysis/dispute_contract.py` | create | Analysis policy, candidate statuses, layers, lineage, ids. |
| `src/analysis/dispute_detection.py` | create | Candidate detection and disagreement counts. |
| `src/analysis/dispute_identity.py` | create | Forward-only candidate identity. |
| `src/analysis/dispute_lineage.py` | create | Lineage, summary, objective alignment classification. |
| `src/analysis/dispute_layers.py` | create | Three separated layers and leakage guards. |
| `src/analysis/dispute_metrics.py` | create | Three metric computations. |
| `src/analysis/specifications.py` | modify | Append three family ids/builders; count 154. |
| `src/analysis/metric_service.py` | modify | Add dispute inputs and assembly block. |
| `src/analysis/__init__.py` | modify | Export new analysis names. |
| `src/experiments/collectors.py` | modify | Harvest dispute rows and objective anchors. |
| `tests/unit/test_dispute_analysis.py` | create | Harvest/window/detection/lineage. |
| `tests/unit/test_dispute_layers.py` | create | Layer separation and leakage. |
| `tests/unit/test_dispute_metrics.py` | create | Metric values and availability. |
| `tests/unit/test_dispute_catalog.py` | create | Catalog count/order/value keys. |
| `tests/unit/test_dispute_metric_service.py` | create | Completed-run assembly. |

## Task 10: Harvest dispute rows and objective anchors

### Intent

Normalize exported ledgers without importing cognition, and build researcher-only
objective anchors from committed events. This is the only place where objective
history meets dispute evidence.

### Implementation Steps

1. Create `src/analysis/disputes.py` with frozen slotted row types:
   - `DisputeOwnerRow(owner_id, case_count, claim_count, testimony_count,
     evidence_count, resolution_count, pruned_count, coverage, first_tick,
     last_tick)`.
   - `DisputeCaseRow(owner_id, case_ref, kind, subject_kind, subject_token,
     status, party_ids, first_tick, last_tick, coverage)`.
   - `DisputeClaimRow(owner_id, case_ref, claim_ref, claimant_id,
     respondent_id, role, claim_kind, polarity, subject_token, counters_claim_ref,
     evidence_count, first_tick, last_tick)`.
   - `DisputeTestimonyRow(owner_id, case_ref, claim_ref, testimony_ref,
     speaker_id, channel, root_ref, independently_evidenced, tick)`.
   - `DisputeEvidenceRow(owner_id, case_ref, claim_ref, evidence_ref,
     channel, reference_kind, reference_id, tick, independently_evidenced)`.
   - `DisputeRuleReferenceRow(owner_id, case_ref, claim_ref,
     rule_reference_ref, system_ref, rule_ref, version_number, applicability,
     interpretation, status)`.
   - `DisputeAuthorityReferenceRow(owner_id, case_ref, authority_ref,
     authority_kind, reference_id, strength, uncertainty, dissenting)`.
   - `DisputeMediationReferenceRow(owner_id, case_ref, mediation_ref,
     mediation_case_ref, recommendation_ref, response_ref, outcome_ref,
     link_status)`.
   - `DisputeResolutionRow(owner_id, case_ref, resolution_ref, proposer_id,
     source, terms_digest, status, first_tick, last_tick, expires_tick)`.
   - `DisputeResolutionResponseRow(owner_id, case_ref, resolution_ref,
     response_ref, party_id, kind, tick, terms_digest, active)`.
   - `DisputeHarvestRows(owners, cases, claims, testimony, evidence,
     rule_references, authority_references, mediation_references, resolutions,
     responses)`.
2. Add `harvest_dispute_rows(ledgers: Sequence[object], *, window_ticks: int = 100)
   -> DisputeHarvestRows`.
   - Accept any object with the ledger attributes; do not import
     `agents.cognition`.
   - Reject duplicate owner ids with `DisputeAnalysisError("dispute_duplicate_owner")`.
   - Sort every row by its stable key and deduplicate by id.
   - Preserve `coverage="partial"` when a ledger reports pruned rows. The
     `DisputeOwnerRow` carries `coverage` and the sum of all `pruned_*` counts so
     an enabled ledger with zero cases can still be distinguished from a
     partial/absent channel.
   - Preserve the exact fields each metric consumes: claim role/polarity,
     evidence count, testimony channel/root/independence, resolution status,
     accepted/rejected counts, and objective alignment counts. The metrics must
     read these fields directly rather than infer a nearby substitute.
   - Never copy claim text, evidence payloads, rule bodies, or mediation
     recommendations.
3. Create `src/analysis/dispute_evidence.py` with:
   - `DisputeObjectiveAnchorKind`: `item_transfer`, `resource_taken`, `harm`,
     `commitment_declaration`, `exchange_completion`, `record_creation`,
     `repository_entry`, `other`.
   - `DisputeObjectiveAnchorRow(reference_id, kind, tick, actor_id, target_id,
     item_token, quantity, event_kind)`.
   - `dispute_objective_anchor_rows_from_events(events, *,
     entity_to_agent: Mapping[str, str]) -> tuple[DisputeObjectiveAnchorRow, ...]`.
   - `DisputeWindowEvidence(start_tick, end_tick, owner_count, case_count,
     claim_count, testimony_count, evidence_count, objective_anchor_count,
     coverage)`.
   - `build_dispute_windows(rows, *, window_ticks, objective_rows=()) ->
     tuple[DisputeWindowEvidence, ...]`.
4. Map events by their `details.kind` or event `kind`:
   - `give` → `item_transfer` with actor, recipient, item token, quantity if
     present;
   - `take` → `resource_taken`;
   - `attack` → `harm`;
   - `commitment_declared` → `commitment_declaration`;
   - `exchange_completed` → `exchange_completion`;
   - `artifact_created` / `artifact_modified` → `record_creation`;
   - `item_stored` → `repository_entry`;
   - all other kinds → skipped, not `other`.
   Use `entity_to_agent` from the runner assignment, as
   `mediation_effect_rows_from_events` does. Missing mappings skip the row.
5. `reference_id` is a content-addressed digest over the mapped anchor fields
   (kind, tick, actor, target, item token, quantity), not a raw event id. Never
   include raw payloads, prompts, or hidden actor identities beyond the mapped
   agent ids.
6. Windows are deterministic 100-tick buckets (or the supplied `window_ticks`),
   sorted by start tick, capped at 1024. A missing expected row sets
   `coverage="partial"`; it never fabricates an empty complete window.
7. Add `experiments/collectors.py` wiring:
   - after the formal-rule carry, read `arm.runner_result.dispute_ledgers`;
   - call `harvest_dispute_rows`;
   - build `entity_to_agent` and call
     `dispute_objective_anchor_rows_from_events(events or (), ...)`;
   - set `dispute_rows` and `dispute_objective_rows` on the metric inputs.
8. `analysis` must not import `agents.cognition`, `world`, `simulation`,
   `experiments`, `persistence`, or `api`.

### Required Interfaces and Contracts

```python
def harvest_dispute_rows(
    ledgers: Sequence[object],
    *,
    window_ticks: int = 100,
) -> DisputeHarvestRows: ...

def dispute_objective_anchor_rows_from_events(
    events: Sequence[object],
    *,
    entity_to_agent: Mapping[str, str],
) -> tuple[DisputeObjectiveAnchorRow, ...]: ...

def build_dispute_windows(
    rows: DisputeHarvestRows,
    *,
    window_ticks: int,
    objective_rows: Sequence[DisputeObjectiveAnchorRow] = (),
) -> tuple[DisputeWindowEvidence, ...]: ...
```

Compatibility invariants:

- Harvesting is read-only and independent of live services.
- Objective anchors are researcher-only; no cognition module may import
  `analysis.dispute_evidence`.
- Row ordering is stable across input permutations.

### Requirement Evidence

- Original Request "Research infrastructure knows objective history but agents do
  not."
- `.ai-factory/ARCHITECTURE.md` "analysis is read-only" and "Analysis results
  never feed live cognition, prompts, or memory."
- `src/analysis/formal_rules.py` 298-312; `src/analysis/formal_rule_evidence.py`;
  `src/analysis/mediation.py` 461-502.
- `src/experiments/collectors.py` 176-179, 670-672, 817-826.

### Error Handling and Logging

- Duplicate owner: `DisputeAnalysisError("dispute_duplicate_owner")`.
- Invalid row: `DisputeAnalysisError("dispute_invalid_row")`.
- Window overflow: cap at 1024 and append a coverage notice.
- DEBUG counts only: `dispute_harvest owners=%s claims=%s windows=%s`.
- Never log claim content, subject tokens, party ids, or evidence references.

### Tests

`tests/unit/test_dispute_analysis.py`:

- `test_harvest_is_order_independent_and_deduplicates`
- `test_duplicate_owner_fails_closed`
- `test_objective_anchors_map_give_take_attack_commitment_and_records`
- `test_missing_event_mapping_skips_without_fabricating`
- `test_windows_are_deterministic_and_mark_partial_coverage`
- `test_analysis_imports_no_cognition_or_live_service`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_analysis.py -q`.

### Acceptance Criteria

- Ledgers harvest into sorted detached rows.
- Objective anchors cover the closed event kinds.
- Missing evidence is explicit `partial`, never fabricated.
- No cognition/live-service import exists in analysis.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_analysis.py -q`
- Expected result: all tests pass.

## Task 11: Detect candidates and derive forward-only lineage

### Intent

Group owner-scoped cases into analytical dispute candidates without creating a
shared case registry, and derive deterministic lineage across windows.

### Implementation Steps

1. Create `src/analysis/dispute_contract.py`:
   - `DISPUTE_ANALYSIS_POLICY_VERSION = "dispute-analysis.v1"`;
   - `DISPUTE_IDENTITY_POLICY_VERSION = "dispute-identity.v1"`;
   - `DisputeCandidateStatus`: `emerging`, `active`, `contested`, `fragmented`,
     `apparently_resolved`, `dissolved`, `unknown`;
   - `DisputeLayer`: `objective`, `subjective`, `analytical`;
   - `DisputeLineageKind`: `continued`, `transformed`, `split`, `merge`,
     `dissolved`, `emerged`;
   - `DisputeCoverage(observed, expected, ratio)`;
   - `DisputeAnalysisError`;
   - `DISPUTE_CANDIDATE_ID_PREFIX = "disp-"`,
     `DISPUTE_PUBLISHED_CLAIM_PREFIX = "dispcl-"`,
     `DISPUTE_PUBLISHED_RESOLUTION_PREFIX = "dispres-"`,
     `DISPUTE_EDGE_ID_PREFIX = "disp-edge-"`,
     `DISPUTE_PUBLICATION_ID_PREFIX = "disp-pub-"`;
   - `derive_dispute_candidate_id(creation_digest)`,
     `dispute_edge_id(source, target, kind, tick)`,
     `dispute_candidate_key(material)`.
2. Create `src/analysis/dispute_detection.py`:
   - `DisputeMemberClaim(owner_id, case_ref, claim_ref, claimant_id,
     respondent_id, role, claim_kind, polarity, subject_token, tick)`.
   - `DisputeCandidate(candidate_key, kind, subject_token, party_ids, owner_ids,
     case_refs, claim_refs, status, first_tick, last_tick,
     disagreement_count, resolution_count, coverage)`.
   - `detect_dispute_candidates(rows, windows) -> tuple[DisputeCandidate, ...]`.
   - Group by exactly `(subject_token, party_set_digest)`. A different party
     set is a separate candidate; never merge by subject alone. The candidate
     `kind` is the first non-`other` case kind in the group, otherwise `other`;
     refining a case kind does not split the candidate.
   - `disagreement_count` counts opposite `polarity` pairs for the same
     `claim_kind` and `subject_token`; `uncertain` is not an opposite.
   - Candidate status derives from member case statuses: any `contested` →
     `contested`; all `apparently_resolved` → `apparently_resolved`; multiple
     owner cases with incompatible statuses → `fragmented`; only withdrawn/
     expired → `dissolved`; otherwise `active` or `emerging`.
3. Create `src/analysis/dispute_identity.py`:
   - `DisputeRecord(candidate_key, creation_digest, first_tick, last_tick, ...)`.
   - `DisputeTransition(source, target, kind, tick)`.
   - `DisputeWindowSnapshot(start_tick, end_tick, candidates)`.
   - `DisputeIdentityAssignment(candidates, transitions)`.
   - `assign_dispute_identities(windows) -> DisputeIdentityAssignment`.
   - Candidate ids are minted from creation evidence only: sorted
     `(owner_id, case_ref, first_tick)` plus the grouping key. A later member or
     status change never changes the id.
   - Transition rules: same key → `continued`; same candidate with a changed
     subject/kind but overlapping parties → `transformed`; one candidate becoming
     two → `split`; two becoming one → `merge`; disappearance → `dissolved`;
     first appearance → `emerged`.
4. Create `src/analysis/dispute_lineage.py`:
   - `DisputeLineageEdge(edge_id, source, target, kind, tick)`.
   - `DisputeCandidateDevelopment(candidate_id, first_tick, last_tick,
     status, case_count, claim_count, counterclaim_count)`.
   - `DisputeCandidateAlignment(candidate_id, supported_claims,
     unresolved_claims, inconsistent_claims, not_applicable_claims,
     objective_anchor_count)`.
   - `DisputeCandidateResolution(candidate_id, proposed, partially_accepted,
     apparently_accepted, contested, withdrawn, expired, mediation_linked)`.
   - `DisputeAnalysis(candidates, transitions, development, alignment,
     resolution)`.
   - `DisputeAnalysisSummary(candidate_count, active_count, contested_count,
     apparently_resolved_count, claim_count, counterclaim_count,
     testimony_count, evidence_count, resolution_count, accepted_count,
     rejected_count, coverage)`.
   - `derive_dispute_lineage(rows, windows)`, `validate_dispute_lineage`,
     `summarize_disputes`, `dispute_analysis_digest`.
5. Add `classify_dispute_objective_alignment(claim, anchors) ->
   DisputeObjectiveAlignment`:
   - `not_applicable` for `term_meaning`, `promise_broken`, and `other` claims
     without an objective anchor;
   - `supported` when an anchor shares the claim kind, actor/target orientation,
     and item token;
   - `inconsistent` when only an opposite-orientation anchor for the same item
     and window exists;
   - `unresolved` otherwise.
   This is a researcher-only classification; no `verdict`, `false`, `guilty`, or
   `liable` member exists.
6. Never create, split, merge, dissolve, or re-identify a formal-rule,
   organization, macro-society, office, institution, or mediation candidate.

### Required Interfaces and Contracts

```python
def detect_dispute_candidates(
    rows: DisputeHarvestRows,
    windows: Sequence[DisputeWindowEvidence],
) -> tuple[DisputeCandidate, ...]: ...

def assign_dispute_identities(
    windows: Sequence[DisputeWindowSnapshot],
) -> DisputeIdentityAssignment: ...

def derive_dispute_lineage(
    rows: DisputeHarvestRows,
    windows: Sequence[DisputeWindowEvidence],
) -> DisputeAnalysis: ...
```

Compatibility invariants:

- Candidate ids are `disp-` + 16 hex chars.
- Lineage is forward-only and acyclic.
- No candidate is a shared case file or an authoritative dispute.
- Objective alignment is classification, not truth.

### Requirement Evidence

- Original Request "Represent claims made by parties separately" and "Research
  infrastructure knows objective history but agents do not."
- `.ai-factory/ARCHITECTURE.md` Key Principle 1; "analysis is read-only".
- `src/analysis/formal_rule_detection.py`; `src/analysis/formal_rule_identity.py`;
  `src/analysis/formal_rule_lineage.py`.

### Error Handling and Logging

- Invalid grouping key: `DisputeAnalysisError("dispute_invalid_candidate")`.
- Duplicate candidate id: `DisputeAnalysisError("dispute_duplicate_id")`.
- Acyclic validation failure: `DisputeAnalysisError("dispute_lineage_cycle")`.
- DEBUG counts only; never log party sets, subject tokens, or claim content.

### Tests

`tests/unit/test_dispute_analysis.py` (continued):

- `test_candidates_group_by_subject_and_party_set`
- `test_overlapping_subjects_with_different_parties_stay_separate`
- `test_opposite_claims_increment_disagreement_without_merging`
- `test_candidate_identity_is_creation_evidence_stable`
- `test_lineage_continued_transformed_split_merge_dissolved_emerged`
- `test_objective_alignment_has_no_verdict_member`
- `test_dispute_analysis_does_not_change_other_context_identities`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_analysis.py -q`.

### Acceptance Criteria

- Cross-owner cases group only by kind, subject, and party set.
- Opposing claims increase disagreement without merging.
- Candidate identity is stable across later members.
- Lineage is forward-only and acyclic.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_analysis.py -q`
- Expected result: all tests pass.

## Task 12: Project the three dispute layers

### Intent

Keep objective counts, owner claims, and analytical summaries as distinct types
with hard leakage checks.

### Implementation Steps

1. Create `src/analysis/dispute_layers.py` with:
   - `DisputeObjectiveRow(tick, observed_occurrence_count,
     observed_transfer_count, observed_harm_count, observed_commitment_count,
     observed_record_count, observed_communication_count)`.
   - `DisputeSubjectiveRow(owner_token, case_ref, status, claim_count,
     counterclaim_count, testimony_count, evidence_count, rule_reference_count,
     resolution_count, coverage)`.
   - `DisputeAnalyticalRow(candidate_id, kind, subject_token, party_count,
     owner_count, claim_count, counterclaim_count, testimony_count,
     evidence_count, resolution_count, disagreement_count,
     objective_supported_count, objective_unresolved_count,
     objective_inconsistent_count, status, coverage)`.
   - `DisputeLayerView(objective, subjective, analytical, digest)`.
2. `project_dispute_layers(rows, analysis, summary, *, windows=())`:
   - build objective rows from `DisputeObjectiveAnchorRow` counts per tick;
   - build subjective rows from each owner's harvested rows; `owner_token` is a
     deterministic safe token, never a claim or party id;
   - build analytical rows from candidates and alignment/resolution summaries;
   - sort deterministically and deduplicate.
3. `assert_dispute_layer_separation(view)`:
   - no `dsc-`, `dcl-`, `dts-`, `dev-`, `drf-`, `dmr-`, `dar-`, `drs-`, `drp-`
     token in an objective or analytical row;
   - no `owner_id`/`owner_token` in an objective row;
   - no raw claim/evidence/rule/mediation content in any row;
   - no `disp-` id in an objective row;
   - no `verdict`, `guilty`, `liable`, `true_owner`, or `winner` field.
4. `dispute_layer_digest(view)` canonicalizes sorted rows.
5. `require_dispute_owner_token(value)` accepts only a 16-hex safe token.
6. The layers are analysis-only; nothing here is imported by cognition or API
   directly. The publication bridge in Phase 5 reads these rows.

### Required Interfaces and Contracts

```python
def project_dispute_layers(
    rows: DisputeHarvestRows,
    analysis: DisputeAnalysis,
    summary: DisputeAnalysisSummary,
    *,
    windows: Sequence[DisputeWindowEvidence] = (),
) -> DisputeLayerView: ...

def assert_dispute_layer_separation(view: DisputeLayerView) -> None: ...
```

Compatibility invariants:

- Objective rows contain aggregate counts only.
- Subjective rows carry safe owner tokens and counts, not claim text.
- Analytical rows use `disp-` ids and counts.
- Leakage is a hard failure.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` Key Principle 1 and "three separated layers"
  precedent in V4-03 through V4-06.
- `src/analysis/formal_rule_layers.py` 34-81, 226-303.

### Error Handling and Logging

- Leakage: `DisputeAnalysisError("dispute_layer_leak")`.
- Invalid owner token: `DisputeAnalysisError("dispute_owner_token")`.
- DEBUG: `dispute_layers objective=%s subjective=%s analytical=%s`.

### Tests

`tests/unit/test_dispute_layers.py`:

- `test_objective_rows_are_aggregate_counts_only`
- `test_subjective_rows_never_expose_owner_local_ids_as_objective`
- `test_analytical_rows_use_candidate_ids_only`
- `test_layer_leakage_fails_closed`
- `test_layer_digest_is_order_independent`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_layers.py -q`.

### Acceptance Criteria

- Three distinct row types exist.
- Objective rows contain no owner or candidate ids.
- Analytical rows contain no owner-local ids.
- Leakage fails closed.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_layers.py -q`
- Expected result: all tests pass.

## Task 13: Add three metric families and raise the catalog to 154

### Intent

Append three analysis-only families without changing any existing family. The
objective-alignment values are researcher-facing and never feed agents.

### Implementation Steps

1. In `src/analysis/specifications.py`:
   - add members `DISPUTE_CLAIM_STRUCTURE = "dispute_claim_structure"`,
     `DISPUTE_TESTIMONY_INDEPENDENCE =
     "dispute_testimony_independence"`, and
     `DISPUTE_RESOLUTION_ALIGNMENT = "dispute_resolution_alignment"` to the
     `MetricFamilyId` enum after `FORMAL_RULE_RESPONSE`;
   - set `METRIC_FAMILY_COUNT = 154`;
   - add `_spec_dispute_claim_structure`, `_spec_dispute_testimony_independence`,
     and `_spec_dispute_resolution_alignment` using `_base(...)`; append them to
     `_BUILDERS` after `_spec_formal_rule_response`;
   - declare exact value keys and policies.
2. `_spec_dispute_claim_structure` value keys:
   `candidate_count`, `case_count`, `claim_count`, `counterclaim_count`,
   `counterclaim_ratio`, `claim_kind_histogram`, `polarity_histogram`,
   `rule_referenced_case_ratio`, `evidence_backed_claim_ratio`,
   `multi_party_case_ratio`, `unresolved_case_ratio`.
   Define `counterclaim_ratio` as counterclaims / claims;
   `rule_referenced_case_ratio` as cases with at least one rule reference /
   cases with claims; `evidence_backed_claim_ratio` as claims with at least one
   evidence reference / claims; `multi_party_case_ratio` as cases with more than
   two parties / cases with claims; and `unresolved_case_ratio` as cases with
   status `open`, `evidence_gathering`, or `contested` / cases with claims.
3. `_spec_dispute_testimony_independence` value keys:
   `testimony_count`, `direct_testimony_ratio`, `communicated_testimony_ratio`,
   `distinct_root_count`, `shared_root_duplicate_ratio`,
   `independently_evidenced_ratio`, `contradictory_testimony_ratio`,
   `claim_without_testimony_ratio`.
   Define `contradictory_testimony_ratio` as testimony rows attached to claims
   that have both `affirm` and `deny` counterparts divided by testimony rows;
   `claim_without_testimony_ratio` as claims with no testimony divided by
   claims. Shared-root duplicates never count as independent evidence.
4. `_spec_dispute_resolution_alignment` value keys:
   `resolution_count`, `proposed_resolution_count`,
   `apparently_accepted_resolution_count`, `contested_resolution_count`,
   `accepted_party_ratio`, `rejected_party_ratio`,
   `mediation_linked_resolution_ratio`, `objective_supported_claim_ratio`,
   `objective_unresolved_claim_ratio`, `objective_inconsistent_claim_ratio`,
   `agreement_alignment_ratio`.
   Define `agreement_alignment_ratio` as candidates with at least two owner
   resolutions sharing one `terms_digest` divided by candidates with at least
   two owner resolutions. Define each `objective_*_ratio` as claims in that
   classification divided by claims with an objective anchor; claims with no
   anchor are excluded from the denominator, not counted as inconsistent. The
   `objective_*` values are explicitly documented as researcher-only.
5. Create `src/analysis/dispute_metrics.py`:
   - `compute_dispute_claim_structure(summary, layers) -> MetricDocument`;
   - `compute_dispute_testimony_independence(summary, rows) -> MetricDocument`;
   - `compute_dispute_resolution_alignment(summary, analysis, layers) ->
     MetricDocument`.
   Each returns the existing `MetricDocument` shape with `present`, `partial`, or
   `absent` availability and coverage. `dispute_rows is None` (no ledger or
   channel) is `ABSENT`; a present ledger with zero cases is `PRESENT` with zero
   counts and `coverage=complete`; partial windows or pruned rows are `PARTIAL`.
   No denominator is fabricated. Each function writes its exact numerator and
   denominator values, not a nearby substitute, and the known-answer test checks
   those values directly.
6. In `src/analysis/metric_service.py`:
   - add `dispute_rows: object | None = None` and
     `dispute_objective_rows: Sequence[object] | None = None` to
     `MetricComputationInputs`;
   - add a block after the formal-rule block that harvests, builds windows,
     derives candidates/identity/lineage, summarizes, projects layers, and
     appends the three documents with `_safe(...)`.
7. In `src/experiments/collectors.py`, carry the dispute rows and objective rows
   from Task 10 into the inputs.
8. In `src/analysis/__init__.py`, import and export the new public names.
9. Update only the intentional catalog pin from 151 to 154. Do not reorder or
   rename any existing family.

#### Catalog-count update set

Every exact catalog-count assertion must move from 151 to 154, and every
"last family" assertion must move from the formal-rule families to the three
dispute families. Historical seed literals such as `seed=151` are not catalog
counts and must not change.

Update these files where they assert `METRIC_FAMILY_COUNT`, `len(specs)`,
`len(all_metric_specifications())`, `len(validate_metric_catalog())`, or a
`151` catalog count:

```text
tests/architecture/test_formal_rule_boundaries.py
tests/architecture/test_organization_agency_boundaries.py
tests/architecture/test_organization_boundaries.py
tests/architecture/test_organization_operations_boundaries.py
tests/architecture/test_path_dependence_boundaries.py
tests/architecture/test_v4_architecture_invariants.py
tests/unit/test_bounded_experiment_metrics.py
tests/unit/test_collective_project_metrics.py
tests/unit/test_cultural_evolution_metric_service.py
tests/unit/test_cultural_feature_metrics.py
tests/unit/test_cultural_metrics_end_to_end.py
tests/unit/test_cultural_narrative_metrics.py
tests/unit/test_dependency_care_metrics.py
tests/unit/test_developmental_learning_metrics.py
tests/unit/test_formal_rule_catalog.py
tests/unit/test_formal_rule_regression.py
tests/unit/test_generational_cohort_metrics.py
tests/unit/test_historical_memory_metrics.py
tests/unit/test_institutional_memory_metrics.py
tests/unit/test_knowledge_genealogy_metrics.py
tests/unit/test_macro_society_catalog.py
tests/unit/test_mediation_invariants.py
tests/unit/test_mentorship_metrics.py
tests/unit/test_metric_specifications.py
tests/unit/test_organization_agency_metrics.py
tests/unit/test_organization_agency_regression.py
tests/unit/test_organization_catalog.py
tests/unit/test_organization_operations_catalog.py
tests/unit/test_organization_operations_docs.py
tests/unit/test_organization_operations_regression.py
tests/unit/test_possession_succession_metrics.py
tests/unit/test_public_good_metrics.py
tests/unit/test_regional_demographics.py
tests/unit/test_structured_commitments_metrics.py
tests/unit/test_subjective_value_metrics.py
tests/unit/test_technique_lifecycle_metrics.py
tests/unit/test_translation_rows.py
tests/unit/test_v3_durable_records_regression.py
tests/unit/test_v3_knowledge_genealogy_regression.py
tests/unit/test_v3_knowledge_repositories_regression.py
```

Also update the docs-count assertions in:

```text
tests/unit/test_formal_rule_docs.py
tests/unit/test_organization_docs.py
tests/unit/test_organization_operations_docs.py
```

In `test_formal_rule_regression.py` and
`test_organization_operations_regression.py`, preserve the "first 151 families
unchanged" assertion and change only the tail expectation to:

```text
dispute_claim_structure
dispute_testimony_independence
dispute_resolution_alignment
```

Any test that indexes the tail of `all_metric_specifications()` with negative
slices (for example `[-7:-5]`, `[-5:-3]`, or `[-3:]`) must recompute those
offsets for 154. Keep the first 151 families and their order unchanged; move
only the reported tail positions. In particular, the formal-rule families move
from `[-3:]` to `[-6:-3]`, and the three dispute families occupy `[-3:]`.

Do not change a test that uses `151` as a seed, tick, port, or unrelated count.
Run `grep -rn "151" tests` after the edit and justify every remaining occurrence
in the Task 22 receipt as either unchanged historical text or a non-catalog
literal.

### Required Interfaces and Contracts

```python
def compute_dispute_claim_structure(summary: DisputeAnalysisSummary, layers: DisputeLayerView) -> MetricDocument: ...
def compute_dispute_testimony_independence(summary: DisputeAnalysisSummary, rows: DisputeHarvestRows) -> MetricDocument: ...
def compute_dispute_resolution_alignment(summary: DisputeAnalysisSummary, analysis: DisputeAnalysis, layers: DisputeLayerView) -> MetricDocument: ...
```

Compatibility invariants:

- The first 151 family ids, order, versions, and value keys are byte-identical.
- New families are `@1`.
- The three documents are emitted by real completed-run assembly.
- Objective alignment values are analysis-only and never enter cognition.

### Requirement Evidence

- Original Request "Research infrastructure knows objective history but agents do
  not."
- `src/analysis/specifications.py` 52-53, 226-228, 6965-6984.
- `src/analysis/metric_service.py` 218-327, 1561-1625.
- `src/experiments/collectors.py` 817-826.
- `.ai-factory/patches/2026-10-23-15.37.md`: empty/unknown coverage and nested
  JSON hardening.
- `.ai-factory/patches/2026-10-09-14.46.md`: store the named quantity and assert
  it in a known-answer test instead of substituting a nearby count.

### Error Handling and Logging

- Insufficient evidence: `ABSENT`, not an error.
- Partial windows: `PARTIAL` with coverage.
- Metric computation failure is isolated by `_safe(...)`; the remaining catalog
  still assembles.
- INFO: `dispute_metric family=%s availability=%s`; never log values that reveal
  claim content.

### Tests

`tests/unit/test_dispute_metrics.py`:

- `test_absent_partial_present_availability`
- `test_claim_structure_values`
- `test_testimony_independence_excludes_shared_roots`
- `test_known_answer_two_direct_one_retold_and_one_inconsistent_claim`
- `test_present_zero_counts_for_enabled_empty_ledger`
- `test_absent_when_no_dispute_channel`
- `test_resolution_alignment_values`
- `test_objective_alignment_is_researcher_only`
- `test_metrics_are_deterministic`

`tests/unit/test_dispute_catalog.py`:

- `test_metric_catalog_count_is_154`
- `test_first_151_families_are_unchanged`
- `test_three_dispute_families_are_last_and_versioned_at_1`
- `test_dispute_value_keys_are_exact`

`tests/unit/test_dispute_metric_service.py`:

- `test_completed_run_assembly_emits_three_documents`
- `test_collector_carries_dispute_rows`
- `test_missing_dispute_rows_leave_families_absent`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_metrics.py tests/unit/test_dispute_catalog.py tests/unit/test_dispute_metric_service.py -q`.

### Acceptance Criteria

- Catalog count is exactly 154.
- The first 151 families are unchanged.
- Real completed-run assembly emits all three families.
- Objective alignment never feeds cognition.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_metrics.py tests/unit/test_dispute_catalog.py tests/unit/test_dispute_metric_service.py -q`
- Expected result: all tests pass.

## Phase Risks and Mitigations

- Risk: Objective alignment becomes a justice oracle.
  Mitigation: Task 11 classification vocabulary and Task 12/20 leakage/no-verdict
  tests; no cognition import path.
- Risk: Cross-owner grouping merges distinct disputes.
  Mitigation: Task 11 group key includes the party set.
- Risk: Candidate ids drift with later members.
  Mitigation: Task 11 creation-evidence identity test.
- Risk: Metric catalog reorders legacy families.
  Mitigation: Task 13 first-151 byte-identical test.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
