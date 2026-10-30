# Phase 3: Detached Analysis, Identity, Lineage, and Metrics

Plan: [index.md](index.md)
Tasks: 7-11
Depends on: Phase 2 / Task 6

## Objective

Turn exported owner-scoped organization ledgers into detached researcher
analysis: normalized evidence windows, overlapping cross-owner candidates,
stable analytical identities, three strictly separated layers, forward-only
split/merge lineage, four metric families, and a catalog at 144. Analysis remains
read-only and never feeds cognition, prompts, admission, or world state.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/offices.py` | `harvest_office_rows` 167-228; duck-typed ledger access | The pattern for consuming exported ledgers without importing `agents.cognition`. |
| `src/analysis/institutional_decay.py` | `institution_decay_rows_from_ledgers` 566+; `InstitutionTemporalRow` 95; `InstitutionWindowRow` 177 | Windowed row normalization from bounded owner history. |
| `src/analysis/institution_lineage.py` | `InstitutionLineageKind` 46-51; `InstitutionEpisode` 84; `compute_institution_lineage` 241 | Forward-only episode lineage and acyclicity validation precedent. |
| `src/analysis/macro_society_contract.py` | `MacroSocietyLane` 85-97; `MacroSocietyStatus` 125-131; `derive_macro_society_id` 241-264 | Closed analytical vocabulary and content-addressed identity. |
| `src/analysis/macro_society_detection.py` | `MacroSocietyCandidate` 92-125; `detect_macro_society_candidates` 243 | Overlapping candidate composition and overlap ids. |
| `src/analysis/macro_society_identity.py` | `MacroSocietyRecord` 46-90; `assign_macro_society_identities` 189 | Stable identity assignment across windows. |
| `src/analysis/macro_society_layers.py` | `MacroSocietyObjectiveRow` 44-64; `assert_layer_separation` 202 | Three-layer leakage checks. |
| `src/analysis/macro_society_lineage.py` | `MacroSocietyLineageEdge` 42-80; `derive_macro_society_lineage` 122; `build_macro_society_analysis` 313 | Lineage thresholds and deterministic digest. |
| `src/analysis/macro_society_metrics.py` | four compute functions 96-304 | Metric-document shape and availability semantics. |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53; `MetricFamilyId` 75-217; `_BUILDERS` 6202-6343; `validate_metric_catalog` 6364-6397 | Exact append-only catalog registration. |
| `src/analysis/models.py` | `MetricAvailability` 508-514; `MetricDocument` 584-710 | ABSENT/PARTIAL/UNKNOWN semantics. |
| `src/analysis/metric_service.py` | `MetricComputationInputs` 218-330; `assemble_metric_documents` 398 | Neutral row-bag and family assembly. |
| `src/experiments/collectors.py` | office/collective/institutional wiring 658-779 | Where exported ledgers become metric inputs. |
| `tests/unit/test_macro_society_*.py` | contract/detection/identity/layers/lineage/metrics | Exact test patterns to mirror. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/organizations.py` | create | Harvest owner ledgers into detached rows without importing cognition. |
| `src/analysis/organization_contract.py` | create | Closed analytical enums, coverage, IDs, errors. |
| `src/analysis/organization_evidence.py` | create | Window normalization and objective-anchor rows. |
| `src/analysis/organization_detection.py` | create | Cross-owner candidate composition with overlap/dispute/temporary handling. |
| `src/analysis/organization_identity.py` | create | Stable analytical ids and transitions. |
| `src/analysis/organization_layers.py` | create | Objective/subjective/analytical projection and leakage checks. |
| `src/analysis/organization_lineage.py` | create | Forward-only lineage and `OrganizationAnalysis`. |
| `src/analysis/organization_metrics.py` | create | Four metric documents. |
| `src/analysis/__init__.py` | modify | Export the public organization analysis, layer, lineage, and metric symbols. |
| `src/analysis/specifications.py` | modify | Four families appended; `METRIC_FAMILY_COUNT = 144`. |
| `src/analysis/metric_service.py` | modify | `organization_rows` input and family assembly. |
| `src/experiments/collectors.py` | modify | Harvest organization ledgers and pass rows to metrics. |
| `tests/unit/test_organization_harvest.py` | create | Row normalization and owner isolation. |
| `tests/unit/test_organization_detection.py` | create | Overlap, dispute, temporary, fragmentation. |
| `tests/unit/test_organization_analysis_identity.py` | create | Stable ids across windows and churn. |
| `tests/unit/test_organization_layers.py` | create | Three-layer leakage. |
| `tests/unit/test_organization_analysis_lineage.py` | create | Split/merge/continued/dissolved/emerged and acyclicity. |
| `tests/unit/test_organization_metrics.py` | create | Four families, availability, exact value keys. |
| `tests/unit/test_organization_catalog.py` | create | Catalog count 144 and append-only order. |

## Task 7: Harvest owner ledgers into detached organization rows

### Intent

Expose the exported owner ledgers to the analysis package without coupling
`analysis` to `agents.cognition`. The harvest is a pure, bounded read of the
`RunnerResult` ledger tuple.

### Implementation Steps

1. Create `src/analysis/organizations.py` with a module docstring stating:
   detached post-run rows only; owner-local ids stay owner-local; missing or
   pruned evidence is absent/partial, never zero; nothing feeds cognition.
2. Define frozen row dataclasses:
   - `OrganizationOwnerRow`: `owner_id`, `concept_count`, `lineage_count`,
     `notices`, `policy_version`.
   - `OrganizationConceptRow`: `owner_id`, `organization_id`, `creation_tick`,
     `status`, `temporal_scope`, `strength`, `member_evidence_count`,
     `structural_channel_count`, `first_tick`, `last_tick`,
     `predecessor_ids`, `structural_signature`.
   - `OrganizationMemberRow`: `owner_id`, `organization_id`, `member_id`,
     `status`, `basis`, `temporal_scope`, `first_tick`, `last_tick`,
     `expires_tick`, `strength`, `channels`, `independently_evidenced`.
   - `OrganizationRoleRow`, `OrganizationGoalRow`,
     `OrganizationResourceRow`, `OrganizationProcedureRow`,
     `OrganizationRecordRow`, `OrganizationCommitmentRow`,
     `OrganizationIdentityRow`, `OrganizationWindowRow`,
     `OrganizationLineageRow`.
3. Implement `harvest_organization_rows(ledgers)`:
   - accept any sequence of objects with the documented ledger attributes
     (`owner_id`, `concepts`, `lineage`, `policy_version`);
   - reject a ledger whose owner does not match its owner row;
   - reject duplicate `(owner_id, organization_id)` pairs;
   - sort rows by `(owner_id, organization_id, first_tick, member_id/anchor_id)`;
   - fail closed on negative/bool ticks, unsorted member ids, cap overflow, or a
     missing policy version with stable `OrganizationAnalysisError` codes.
4. Provide `harvest_organization_snapshot(runner_result)` that reads
   `runner_result.organization_concept_ledgers` defensively with `getattr`; an
   absent/empty tuple yields an empty harvest, not an error.
5. Export the public harvest row types and
   `harvest_organization_rows`/`harvest_organization_snapshot` through
   `src/analysis/__init__.py`, matching the existing macro-society facade.
6. Tests:
   - representative ledger harvests to exact row counts and order;
   - foreign-owner ledger rejected;
   - duplicate concept id rejected;
   - empty/None ledger yields empty rows;
   - module does not import `agents.cognition` (AST check).

### Required Interfaces and Contracts

```python
def harvest_organization_rows(
    ledgers: Sequence[object],
) -> tuple[OrganizationHarvestRows, ...]: ...

@dataclass(frozen=True, slots=True)
class OrganizationHarvestRows:
    owner: OrganizationOwnerRow
    concepts: tuple[OrganizationConceptRow, ...]
    members: tuple[OrganizationMemberRow, ...]
    roles: tuple[OrganizationRoleRow, ...]
    goals: tuple[OrganizationGoalRow, ...]
    resources: tuple[OrganizationResourceRow, ...]
    procedures: tuple[OrganizationProcedureRow, ...]
    records: tuple[OrganizationRecordRow, ...]
    commitments: tuple[OrganizationCommitmentRow, ...]
    identities: tuple[OrganizationIdentityRow, ...]
    windows: tuple[OrganizationWindowRow, ...]
    lineage: tuple[OrganizationLineageRow, ...]
```

- Row ids are preserved strings; no new identity is minted here.
- No `agents.cognition`, `simulation` engine, or `experiments` import.
- Missing optional aspects are empty tuples, not synthesized rows.

### Requirement Evidence

- Original request: all nine organization aspects must be represented.
- `.ai-factory/ARCHITECTURE.md` "Dependency Rules": `analysis` may read
  `world`/`simulation`/`memory` contracts; it must not import cognition.
- `.ai-factory/ARCHITECTURE.md` "Important V3 seams": detached analysis consumes
  exported ledgers after the run.

### Error Handling and Logging

- `OrganizationAnalysisError` with codes
  `organization_row_owner_mismatch`, `organization_row_duplicate`,
  `organization_row_invalid_tick`, `organization_row_invalid_order`,
  `organization_row_cap`.
- INFO `organization_harvest owners=%s concepts=%s members=%s` (counts only).
- Never log member ids, labels, or owner content.

### Tests

- `uv run pytest tests/unit/test_organization_harvest.py -q`
- `uv run pytest tests/architecture/test_organization_boundaries.py -q -k analysis_imports`
- Expected: pass.

### Acceptance Criteria

- Exported ledgers become detached rows without a cognition import.
- Ordering and owner isolation are deterministic.
- Empty evidence is represented as empty rows.

### Verification

- `uv run python -c "import ast, pathlib; t=ast.parse(pathlib.Path('src/analysis/organizations.py').read_text()); print('agents.cognition' in pathlib.Path('src/analysis/organizations.py').read_text())"`
- Expected: `False`

## Task 8: Detect overlapping cross-owner organization candidates

### Intent

Compose owner beliefs into researcher-level candidates without collapsing
overlap, forcing a partition, or treating a belief as a roster. Candidates may
be recognized, disputed, temporary, fragmented, or dissolved.

### Implementation Steps

1. Create `src/analysis/organization_contract.py` with duplicate analytical
   enums whose values exactly match Phase 1:
   `OrganizationCandidateStatus`, `OrganizationMembershipStatus`,
   `OrganizationTemporalScope`, `OrganizationLayer`, `OrganizationLineageKind`.
   Add `OrganizationCoverage`, `OrganizationAnalysisError`, and the id helpers
   below. Add a test that the string sets match the cognition contract without
   importing it at runtime.
2. Create `src/analysis/organization_evidence.py`:
   - `OrganizationWindowEvidence`: `window_index`, `start_tick`, `end_tick`,
     `owner_rows`, `known_person_ids`, and channel presence.
   - `build_organization_windows(harvest, window_ticks)` groups rows into
     fixed windows by absolute tick. A window is present when at least one
     owner row or one objective anchor exists; missing channels are reported in
     `lane_presence`.
   - `OrganizationObjectiveAnchorRow`: `anchor_kind`, `anchor_id`, `first_tick`,
     `last_tick`, `reference_count`, `resolved` (`True` when referenced by at
     least one owner concept, `False` when the reference is unresolved).
3. Create `src/analysis/organization_detection.py`:
   - `OrganizationMemberClaim`: member id, status, basis, temporal scope,
     owners, channels, dispute reasons.
   - `OrganizationCandidate`: internal candidate key, member claims, role/goal/
     resource/procedure/record/commitment/identity anchors, status, temporal
     scope, window indexes, overlap member ids.
   - `detect_organization_candidates(windows, known_person_ids=())`:
     - group owner concepts that share at least one member (Jaccard >= 0.5) or
       at least one objective anchor;
     - preserve every owner concept as a subjective contribution, but emit one
       analytical candidate per connected evidence group;
     - a person may appear in multiple candidates; populate
       `overlap_member_ids` rather than removing the person;
     - a member with contradictory statuses across owners is `disputed`;
     - a member referenced only by a role/goal/record anchor is `unknown`;
     - a candidate with any temporary member or temporary goal is `temporary`
       unless all members are ongoing;
     - a candidate split across disconnected evidence groups remains two
       candidates with `fragmented` provenance, never one forced merge;
     - candidates with no self-identification are legal and carry
       `self_identified=False`.
   - candidates are sorted by `(first_tick, sorted member ids, sorted anchors)`.
4. Tests:
   - one person in two candidates → both retained and listed in
     `overlap_member_ids`;
   - owner A says member, owner B says not → `disputed`;
   - role/goal-only member → `unknown`;
   - temporary claim → `temporary`, and after expiry → `former`;
   - disconnected evidence → two candidates, not one;
   - no self-identification → valid candidate with `self_identified=False`;
   - unknown person ids are rejected only when `known_person_ids` is supplied.

### Required Interfaces and Contracts

```python
def detect_organization_candidates(
    windows: Sequence[OrganizationWindowEvidence],
    *,
    known_person_ids: Sequence[str] = (),
) -> OrganizationDetectionResult: ...

@dataclass(frozen=True, slots=True)
class OrganizationDetectionResult:
    windows: tuple[OrganizationWindowResult, ...]
    candidates: tuple[OrganizationCandidate, ...]
    overlap_person_ids: tuple[str, ...]
    lane_presence: tuple[tuple[str, bool], ...]
    coverage: OrganizationCoverage
```

- Membership is never a partition.
- No candidate is promoted to an objective entity.
- A missing lane is recorded, not treated as "no organization".
- Unknown evidence produces `unknown`/`partial`, never a zero count.

### Requirement Evidence

- Original request: "Membership may be: explicit, disputed, unknown, overlapping,
  temporary."
- Original request: "Organizations must be general enough that different
  structures emerge from the same low-level mechanics."
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1: objective, subjective, and
  analytical authorities stay separate.
- V4-02 precedent: overlapping candidates and explicit overlap ids.

### Error Handling and Logging

- Codes `organization_window_invalid`, `organization_unknown_person`,
  `organization_detection_empty`.
- DEBUG `organization_detection windows=%s candidates=%s overlap=%s` (counts).
- Never log person sets.

### Tests

- `uv run pytest tests/unit/test_organization_detection.py -q`
- Hypothesis property: adding a duplicate owner row does not change the
  candidate set.
- Expected: pass.

### Acceptance Criteria

- Overlap, dispute, unknown membership, temporary membership, and absent
  self-identification are all representable.
- Detection is order-independent and deterministic.

### Verification

- `uv run pytest tests/unit/test_organization_detection.py -q -k overlap`
- Expected: pass.

## Task 9: Assign stable analytical organization identities

### Intent

Mint a stable `org-` id from creation evidence so researcher views survive
membership churn but split children and merge results receive new ids.

### Implementation Steps

1. In `src/analysis/organization_identity.py`, define
   `OrganizationRecord`, `OrganizationTransition`,
   `OrganizationIdentityAssignment`, and
   `assign_organization_identities(windows, candidates)`.
2. Mint `org-<16hex>` from
   `sha256("organization-identity.v1" + creation_tick + sorted founding member
   ids + sorted structural anchor kinds/ids)`. Never use the current member set
   alone, a mutable counter, `hash()`, UUID, or wall-clock.
3. Continuation rule: a candidate in the next window inherits the prior id when
   member Jaccard >= 0.5 and at least one shared anchor kind; otherwise it is a
   new record. A split child or merge result always gets a new id.
4. Store per-window candidate-to-record assignments, raw transition pairs, and
   coverage. Do not discard raw pairs; lineage classifies them later.
5. Validate monotonic window indexes, known candidate keys, unique record ids,
   and no id reuse across a split/merge.
6. Tests:
   - permutation of member/anchor order does not change ids;
   - small churn (one member of five) keeps the id;
   - large churn (majority replaced) mints a new id;
   - split children and merge results get new ids;
   - empty/one-window inputs are valid;
   - `PYTHONHASHSEED=0/1` produce identical ids.

### Required Interfaces and Contracts

```python
def derive_organization_id(
    *,
    creation_tick: int,
    founding_member_ids: Sequence[str],
    structural_anchors: Sequence[str],
) -> str: ...

def assign_organization_identities(
    windows: Sequence[OrganizationWindowResult],
    *,
    policy_version: str = "organization-identity.v1",
) -> OrganizationIdentityAssignment: ...
```

- Analytical id grammar `^org-[0-9a-f]{16}$`.
- Owner-local `orgc-` ids are never reused as analytical ids.
- A record stores `organization_id`, `creation_tick`, `first_tick`, `last_tick`,
  `status`, `member_ids`, `anchor_signature`, `window_indexes`.

### Requirement Evidence

- Original request: "historical lineage"; stable researcher identity is required
  to track an organization across time.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 2: deterministic identity.
- V4-02 `derive_macro_society_id` precedent.

### Error Handling and Logging

- Codes `organization_identity_invalid`, `organization_identity_reuse`,
  `organization_identity_window`.
- INFO `organization_identity records=%s transitions=%s` (counts).

### Tests

- `uv run pytest tests/unit/test_organization_analysis_identity.py -q`
- Expected: pass.

### Acceptance Criteria

- Identity is stable under ordinary churn and new under split/merge.
- No mutable counter, UUID, or `hash()` exists.

### Verification

- `uv run pytest tests/unit/test_organization_analysis_identity.py -q -k permutation`
- Expected: pass.

## Task 10: Project three layers and derive forward-only lineage

### Intent

Separate objective structure counts, owner-scoped subjective claims, and
analytical candidates into distinct types, then derive deterministic
`continued`/`transformed`/`split`/`merge`/`dissolved`/`emerged` lineage.

### Implementation Steps

1. Create `src/analysis/organization_layers.py`:
   - `OrganizationObjectiveRow`: `window_index`, `tick`, `member_count`,
     `role_count`, `goal_count`, `resource_count`, `procedure_count`,
     `record_count`, `commitment_count`, `identity_count`,
     `resolved_anchor_count`, `unresolved_anchor_count`. Counts only; no ids.
   - `OrganizationSubjectiveRow`: `owner_id`, `organization_id` (`orgc-`),
     `member_count`, `status`, `temporal_scope`, `self_identified`. No `org-` id.
   - `OrganizationLayerView`: three tuples plus `coverage`.
   - `project_organization_layers(analysis, owner_rows)`.
   - `assert_organization_layer_separation(view)`: fail closed if an objective
     row contains any `org-`/`orgc-` id, or a subjective row contains an `org-`
     id, or an analytical candidate carries an `orgc-` id as its own identity.
2. Create `src/analysis/organization_lineage.py`:
   - `OrganizationLineageEdge`: `kind`, optional `from_id`/`to_id`, `tick`,
     optional `jaccard`, `containment`, `policy_note`.
   - `OrganizationAnalysis`: `policy_version`, `windows`, `records`, sorted
     `edges`, optional `layer_view`, `coverage`, `determinism_digest`.
   - `derive_organization_lineage(assignment, layer_view=None)`:
     - `continued` when one prior record maps to one current with Jaccard >= 0.5;
     - `transformed` when one-to-one with Jaccard >= 0.75 but anchor signature
       changed;
     - `split` when one prior maps to two or more current with containment
       >= 0.4;
     - `merge` when two or more prior map to one current with containment
       >= 0.5;
     - `dissolved` when a prior has no current successor;
     - `emerged` when a current has no prior predecessor.
   - `validate_organization_lineage`: edges monotone in ticks, endpoints known,
     no cycles, only `emerged` may have `from_id=None`, only `dissolved` may have
     `to_id=None`.
   - `build_organization_analysis(...)` returns the digest-bearing analysis.
3. Export `OrganizationObjectiveRow`, `OrganizationSubjectiveRow`,
   `OrganizationLayerView`, `OrganizationAnalysis`, `OrganizationLineageEdge`,
   `project_organization_layers`, `derive_organization_lineage`,
   `validate_organization_lineage`, and `build_organization_analysis` through
   `src/analysis/__init__.py`.
4. Add a Hypothesis property: generated acyclic transitions always produce an
   acyclic validated graph; adding a backward edge raises
   `organization_lineage_cycle`.
5. Tests:
   - objective rows contain no ids;
   - subjective rows never carry `org-`;
   - candidate ids never equal `orgc-` ids;
   - each lineage kind is produced by its fixture;
   - split children/merge results use new ids;
   - missing windows produce `partial`, not zero.

### Required Interfaces and Contracts

```python
def project_organization_layers(
    analysis: OrganizationIdentityAssignment,
    owner_rows: Sequence[OrganizationHarvestRows],
) -> OrganizationLayerView: ...

def derive_organization_lineage(
    assignment: OrganizationIdentityAssignment,
    *,
    layer_view: OrganizationLayerView | None = None,
) -> OrganizationAnalysis: ...
```

- Layers are distinct frozen types, not one row with an `authority` string.
- Lineage is forward-only and acyclic.
- The digest is canonical JSON over the analysis excluding the digest field.

### Requirement Evidence

- Original request: "historical lineage"; "An Organization must not receive an
  independent omniscient cognition engine."
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1.
- V4-02 layer-separation and lineage precedents.

### Error Handling and Logging

- Codes `organization_layer_leak`, `organization_lineage_cycle`,
  `organization_lineage_unknown_endpoint`, `organization_lineage_tick`.
- WARN `organization_lineage_incomplete code=%s` for missing windows.
- INFO `organization_analysis records=%s edges=%s windows=%s`.

### Tests

- `uv run pytest tests/unit/test_organization_layers.py tests/unit/test_organization_analysis_lineage.py -q`
- Expected: pass.

### Acceptance Criteria

- Three layers are distinct and leakage is a hard failure.
- All six lineage kinds are deterministic and validated.

### Verification

- `uv run pytest tests/unit/test_organization_layers.py -q -k leak`
- Expected: pass.

## Task 11: Emit four metric families and raise the catalog to 144

### Intent

Give researchers measurable, bounded organization indicators without claiming
capacity, prevalence, or predictive power. Four append-only families cover
formation, membership, structure, and lineage.

### Implementation Steps

1. In `src/analysis/organization_metrics.py`, implement:
   - `compute_organization_formation_metric(analysis, *, run_id,
     input_revision, tick=0)` with value keys `candidate_count`,
     `recognized_count`, `temporary_count`, `multi_channel_candidate_count`,
     `mean_structural_channels`, `window_count`, `coverage_ratio`,
     `as_of_tick`.
   - `compute_organization_membership_metric(analysis, *, run_id,
     input_revision, tick=0)` with value keys `member_belief_count`,
     `explicit_count`, `perceived_count`, `disputed_count`, `unknown_count`,
     `former_count`, `overlap_member_count`, `temporary_member_count`,
     `unresolved_member_count`, `as_of_tick`.
   - `compute_organization_structure_metric(analysis, *, run_id,
     input_revision, tick=0)` with value keys `role_count`, `goal_count`,
     `resource_count`, `procedure_count`, `record_count`, `commitment_count`,
     `identity_count`, `candidates_with_roles`, `candidates_with_goals`,
     `candidates_with_records`, `mean_structural_channels`, `as_of_tick`.
   - `compute_organization_lineage_metric(analysis, *, run_id,
     input_revision)` with value keys `continuation_count`, `transform_count`,
     `split_count`, `merge_count`, `dissolution_count`, `emergence_count`,
     `mean_continuation_jaccard`, `lineage_window_count`, `as_of_tick`.
   - Each document uses `MetricAvailability.ABSENT` with `values={}` when there
     are no windows/candidates; `PARTIAL` when lane coverage is incomplete or
     history was truncated; `PRESENT` otherwise. Use the shared
     `MetricDocument`, `MetricCoverage`, and `MetricProvenance` types.
2. In `src/analysis/specifications.py`:
   - append `ORGANIZATION_FORMATION`, `ORGANIZATION_MEMBERSHIP`,
     `ORGANIZATION_STRUCTURE`, `ORGANIZATION_LINEAGE` to `MetricFamilyId`;
   - add one `_spec_organization_*` builder per family with `_base(...)`,
     `family_id`, evidence inputs, population, denominator, quantization,
     formulas, and exactly the `value_keys` above;
   - append the four builders to `_BUILDERS` after the four macro-society
     builders;
   - change `METRIC_FAMILY_COUNT` from `140` to `144`.
3. In `src/analysis/metric_service.py`:
   - add `organization_rows: tuple[OrganizationHarvestRows, ...] = ()` to
     `MetricComputationInputs`;
   - in `assemble_metric_documents`, when rows are present, build windows,
     candidates, identities, layers, and analysis once, then append the four
     documents.
4. In `src/experiments/collectors.py`, after the institutional-decay block,
   read `runner_result.organization_concept_ledgers` defensively and set
   `organization_rows=harvest_organization_rows(ledgers)`.
5. Export the four metric compute functions and the organization analysis
   helpers through `src/analysis/__init__.py`.
6. Update every pin that asserts 140 to 144. At minimum:
   `tests/architecture/test_v3_baseline_inventory.py`,
   `tests/architecture/test_path_dependence_boundaries.py`,
   `tests/architecture/test_v4_architecture_invariants.py`,
   `tests/unit/test_bounded_experiment_metrics.py`,
   `tests/unit/test_collective_project_metrics.py`,
   `tests/unit/test_cultural_evolution_metric_service.py`,
   `tests/unit/test_cultural_feature_metrics.py`,
   `tests/unit/test_cultural_metrics_end_to_end.py`,
   `tests/unit/test_cultural_narrative_metrics.py`,
   `tests/unit/test_dependency_care_metrics.py`,
   `tests/unit/test_developmental_learning_metrics.py`,
   `tests/unit/test_generational_cohort_metrics.py`,
   `tests/unit/test_historical_memory_metrics.py`,
   `tests/unit/test_institutional_memory_metrics.py`,
   `tests/unit/test_knowledge_genealogy_metrics.py`,
   `tests/unit/test_macro_society_catalog.py`,
   `tests/unit/test_mediation_invariants.py`.
6. Tests:
   - each family validates and declares exactly its emitted keys;
   - empty analysis yields `ABSENT` and `{}` values;
   - missing lane coverage yields `PARTIAL`;
   - counts match fixtures for explicit/perceived/disputed/unknown/former and
     role/goal/resource/procedure/record/commitment/identity;
   - catalog validates at 144 and preserves existing family order/ids;
   - no existing family's `value_keys`, order, or algorithm version changed.

### Required Interfaces and Contracts

- `METRIC_FAMILY_COUNT == 144`.
- The four new families are appended after
  `macro_society_membership_dispute`; existing families never move.
- Version identifiers are `organization_formation@1`,
  `organization_membership@1`, `organization_structure@1`,
  `organization_lineage@1`.
- No composite "organization score" family exists.
- Metrics remain analysis-only and are never read by cognition or world code.

### Requirement Evidence

- Original request: the nine aspects must be observable to researchers.
- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract": metric families
  append; existing families keep ids/order/version/value keys.
- V4-02 catalog precedent 136 -> 140.

### Error Handling and Logging

- Codes `organization_metric_invalid`, `organization_metric_keys`.
- WARN `organization_metric_partial family=%s reason=%s` with codes only.
- INFO `organization_metrics documents=4 catalog=144`.

### Tests

- `uv run pytest tests/unit/test_organization_metrics.py tests/unit/test_organization_catalog.py -q`
- `uv run pytest tests/architecture/test_v4_architecture_invariants.py -q -k metric`
- `uv run python -c "from analysis.specifications import validate_metric_catalog, METRIC_FAMILY_COUNT; validate_metric_catalog(); print(METRIC_FAMILY_COUNT)"`
- Expected: `144`.

### Acceptance Criteria

- Four families are registered, bounded, and exact.
- Catalog is 144 and existing families are untouched.
- Empty/partial/unknown evidence is not coerced to zero.

### Verification

- `uv run python -c "from analysis.specifications import all_metric_specifications as a; print([s.version_identifier for s in a()][-4:])"`
- Expected: the four `organization_*@1` identifiers.

## Phase Risks and Mitigations

- Risk: analysis imports cognition to read ledger types.
  Mitigation: duck-typed harvest and an AST test.
- Risk: candidate detection forces a partition.
  Mitigation: overlap is explicit; each owner contribution is retained; tests
  assert one person can appear in two candidates.
- Risk: catalog edit reorders existing families.
  Mitigation: append-only builders and a test that the tail is exactly the four
  new families.
- Risk: metrics imply prevalence or capacity.
  Mitigation: names describe detached candidate counts under stated coverage;
  no probability, capacity, or prediction key.
- Risk: lineage cycles from a split/merge fixture.
  Mitigation: monotone ticks and `validate_organization_lineage`; Hypothesis
  property.

## Phase Completion Checklist

- Every Task 7-11 acceptance criterion is met.
- Harvest, detection, identity, layer, lineage, metric, and catalog tests pass.
- Metric catalog is 144; existing families are unchanged.
- No analysis module feeds cognition or imports peer state.
- `index.md` checkboxes are updated immediately after verified completion.
