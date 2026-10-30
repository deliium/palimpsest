# Phase 4: Metric Families and Catalog Registration

Plan: [index.md](index.md)
Tasks: 8-9
Depends on: Phase 2 (Tasks 3-5), Phase 3 (Tasks 6-7)

## Objective

Expose the analysis as four detached metric families with explicit denominators,
coverage, and absent/partial semantics, and register them so the catalog becomes
140 families. Nothing about runner configuration, events, or routes changes.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT = 136` (53), `MetricFamilyId` (75-215), society ids (172-174), `_base` (501), society specs (4315, 4364, 4429), `_BUILDERS` (6003-6140), `all_metric_specifications` (6143), `metric_specification` (6148), `validate_metric_catalog` (6161-6180) | Registration surface and the count/duplicate/set assertions. |
| `src/analysis/models.py` | `MetricAvailability` (508), `MetricCoverage` (518), `MetricProvenance` (551), `MetricDocument` (585) | Document contract every family must emit. |
| `src/analysis/serialization.py` | `encode_metric_document` (241), `decode_metric_document` (271), `metric_document_fingerprint` (354), `is_supported_metric_family` (39) | Canonical encoding and family admission. |
| `src/analysis/metric_service.py` | `MetricComputationInputs` (211), society fields (299-302), `MetricBundle` (324), `assemble_metric_documents` (390), `_safe` (406), society wiring (1349-1383) | Where a new input block and four `_safe` calls belong. |
| `src/analysis/__init__.py` | society import block (610-652), `__all__` (867+), compute names (1248+) | Facade export convention. |
| `tests/unit/test_metric_specifications.py` | `test_catalog_has_136_unique_families` (42-48) | Canonical catalog pin. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/macro_society_metrics.py` | create | Four metric documents from `MacroSocietyAnalysis`. |
| `src/analysis/specifications.py` | modify | Four enum members, four `_spec_*` builders, `_BUILDERS` entries, count 140. |
| `src/analysis/metric_service.py` | modify | `macro_society` input field and four assembly calls. |
| `src/analysis/__init__.py` | modify | Export metric functions. |
| `tests/unit/test_macro_society_metrics.py` | create | Family values, coverage, availability. |
| `tests/unit/test_metric_specifications.py` | modify | 140-family pin and name. |
| All catalog-count pin sites under `tests/unit/` | modify | 136 → 140. |

## Task 8: Emit the four macro-society metric documents

### Intent

Metrics are the researcher-facing summary of an analysis that may be large.
They must report estimands, denominators, and missing evidence honestly, without
turning a candidate into a measured objective fact.

### Implementation Steps

1. Create `src/analysis/macro_society_metrics.py` importing `analysis.models`,
   `analysis.serialization` values, `analysis.specifications`, and the contract,
   detection, identity, and lineage types from Tasks 2-7.
2. Implement `compute_macro_society_structure_metric(analysis, *, run_id, input_revision) -> MetricDocument`
   with values:
   - `candidate_count`: distinct records observed at the final window.
   - `largest_candidate_share`: largest final member count / final known persons,
     quantized, `0.0` when no persons.
   - `covered_person_count`: persons in at least one final candidate.
   - `overlap_person_count`: persons in at least two final candidates.
   - `fragment_person_count`: persons below candidate size in the final window.
   - `mean_candidate_members`: mean final member count.
   - `lane_presence_count`: lanes present in the final window.
   `population="living_and_dead_persons_with_detached_evidence"`,
   `denominator="known_person_count"`.
3. Implement `compute_macro_society_identity_alignment_metric(...)` with values:
   - `candidates_with_self_identification`
   - `self_identified_member_share`
   - `unrecognized_self_identified_group_count`
   - `territory_residence_agreement_share`
   - `layer_disagreement_count` (candidates whose territory token disagrees with
     region residence for at least half their members)
   Denominator: `candidate_count` for candidate-scoped values and
   `self_identified_member_count` for the share.
4. Implement `compute_macro_society_lineage_metric(...)` with values:
   - `continuation_count`, `transform_count`, `split_count`, `merge_count`,
     `dissolution_count`, `emergence_count`
   - `mean_continuation_jaccard` over `continued`/`transformed` edges
   - `lineage_window_count`
   Denominator: `lineage_edge_count`.
5. Implement `compute_macro_society_membership_dispute_metric(...)` with values:
   - `disputed_member_count`, `disputed_candidate_count`,
     `overlap_member_count`, `contested_candidate_count`,
     `unresolved_fragment_count`, `contested_share`
   Denominator: `known_person_count`.
6. Each document:
   - `schema_version=METRIC_DOCUMENT_SCHEMA_VERSION`, `algorithm_version="1"`,
     `library_versions=default_library_versions()`, `evidence_stages` containing
     `OBJECTIVE_EVENT_STATE` and `AGENT_VISIBLE_PROJECTION` for alignment,
     `OBJECTIVE_EVENT_STATE` for structure and lineage, and both plus
     `BELIEF_REVISION_TESTIMONY` for dispute.
   - `availability=ABSENT` with `values={}` when there is no window at all;
     `PARTIAL` when any lane or window has missing coverage; `PRESENT` otherwise.
   - `provenance=MetricProvenance(source_kind="macro_society_analysis", source_ids=(run_id,), notes_code=None)`
     — never member ids.
   - Values quantized with `quantize_float`; graph-derived floats are
     deterministic.
7. Export the four `compute_*_metric` functions from `src/analysis/__init__.py`.

### Required Interfaces and Contracts

- No family reports a "confidence" or probability; statuses are descriptive.
- Absence is never coerced to zero: `ABSENT` documents carry no values.
- Every value key declared in the spec is emitted when `PRESENT`/`PARTIAL`.
- Documents decode with `decode_metric_document` and fingerprint deterministically.

### Error Handling and Logging

- Reuse `MacroSocietyError` for contract violations; metric functions do not add
  new codes.
- `_LOG.debug("macro_society_metric family=%s availability=%s candidates=%s", ...)`
  — counts only.

### Tests

`tests/unit/test_macro_society_metrics.py`:
- A two-window fixture with one split and one merge produces the expected counts
  in all four families.
- Empty analysis yields `ABSENT` and empty values for all four.
- A window with only one lane yields `PARTIAL` for structure and alignment.
- Values match independently computed expectations.
- `encode_metric_document` → `decode_metric_document` round-trips each document.
- Fingerprints are stable across repeated calls.

### Acceptance Criteria

- Four documents are constructible from one analysis object.
- No document contains person ids, owner ids, or token ids.
- Denominators and value keys match the specs added in Task 9 exactly.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_metrics.py -q`

## Task 9: Register four families and raise the catalog to 140

### Intent

Registration is the compatibility contract: the catalog is closed, counted, and
validated. Raising the count is a deliberate, single, reviewable change across
every pin site rather than an incidental side effect.

### Implementation Steps

1. In `src/analysis/specifications.py`:
   - Add `MACRO_SOCIETY_STRUCTURE = "macro_society_structure"`,
     `MACRO_SOCIETY_IDENTITY_ALIGNMENT = "macro_society_identity_alignment"`,
     `MACRO_SOCIETY_LINEAGE = "macro_society_lineage"`,
     `MACRO_SOCIETY_MEMBERSHIP_DISPUTE = "macro_society_membership_dispute"`
     to `MetricFamilyId`.
   - Add `_spec_macro_society_structure()`, `_spec_macro_society_identity_alignment()`,
     `_spec_macro_society_lineage()`, `_spec_macro_society_membership_dispute()`
     using `_base(...)` with the value keys, denominators, censoring, and
     opportunity-vs-occurrence text from Task 8. Explicitly state
     `"candidates are overlapping analytical labels, not an objective census or
     an exclusive partition"` in `opportunity_vs_occurrence`.
   - Append the four builders to `_BUILDERS` in that order.
   - Set `METRIC_FAMILY_COUNT = 140`.
2. In `src/analysis/metric_service.py`:
   - Add `macro_society: MacroSocietyAnalysis | None = None` to
     `MetricComputationInputs` next to the society fields.
   - In `assemble_metric_documents`, add four guarded `_safe("<family>", ...)`
     calls in the same order as the builders, each skipped when the input is
     `None`.
3. Update every catalog pin. At minimum:
   - `tests/unit/test_metric_specifications.py` (rename
     `test_catalog_has_140_unique_families`, assert `140`, assert the family set
     equals `frozenset(MetricFamilyId)`).
   - `tests/unit/test_cultural_evolution_metric_service.py` (81-82).
   - `tests/unit/test_dependency_care_metrics.py` (30-31).
   - `tests/unit/test_developmental_learning_metrics.py` (33-34).
   - `tests/unit/test_historical_memory_metrics.py` (68).
   - `tests/unit/test_knowledge_genealogy_metrics.py` (48).
   - `tests/unit/test_regional_demographics.py` (622-623).
   - `tests/unit/test_technique_lifecycle_metrics.py` (35).
   - `tests/unit/test_institutional_memory_metrics.py` (189).
   - `tests/unit/test_subjective_value_metrics.py` (30).
   - `tests/unit/test_translation_rows.py` (136).
   - `tests/unit/test_public_good_metrics.py` (28).
   - `tests/unit/test_structured_commitments_metrics.py` (50).
   - `tests/unit/test_v3_knowledge_genealogy_regression.py` (38).
   - `tests/unit/test_v3_durable_records_regression.py` (44).
   - `tests/unit/test_generational_cohort_metrics.py` (157).
   Run `grep -rn "METRIC_FAMILY_COUNT\|== 136" tests/unit` and update every
   remaining literal; do not weaken an assertion into a `>=` check.
4. Add `tests/unit/test_macro_society_catalog.py` asserting:
   - `metric_specification(MetricFamilyId.MACRO_SOCIETY_STRUCTURE).family_id`
     matches, `value_keys` equal Task 8's keys, and
     `algorithm_version == "1"`.
   - `validate_metric_catalog()` passes and `len(all_metric_specifications()) == 140`.
   - The four new ids are contiguous at the end of the enum and appear last in
     `_BUILDERS` order (no reordering of existing families).
   - `is_supported_metric_family("macro_society_lineage")` is true and an unknown
     name is false.

### Required Interfaces and Contracts

- `MetricFamilyId` remains closed; unknown names still fail closed.
- Existing family ids, order, versions, and value keys are unchanged.
- `METRIC_FAMILY_COUNT` is the only count constant; no second source of truth.
- Runner config, events, replay, codecs, routes, and Alembic are untouched.

### Error Handling and Logging

- `validate_metric_catalog` keeps `family_count_mismatch` and
  `family_set_mismatch`; no new codes.
- No logging change in `specifications.py`.

### Tests

- `tests/unit/test_macro_society_catalog.py` (new, above).
- Every updated pin file must pass unchanged assertions at 140.
- `tests/unit/test_objective_metrics.py::test_objective_families_match_spec_versions`
  still passes for all families including the new ones.

### Acceptance Criteria

- Catalog validates at 140 with a closed family set.
- Four new specs describe denominators and censoring without claiming a census.
- No existing family changed value keys or version.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_catalog.py tests/unit/test_metric_specifications.py tests/unit/test_objective_metrics.py -q`
- `grep -rn "== 136\|METRIC_FAMILY_COUNT = 136" tests src` returns no matches.
- `uv run --frozen --python 3.12.14 pytest tests/unit -q` (catalog-sensitive set)

## Phase Risks and Mitigations

- Risk: a catalog pin is silently relaxed to `>= 136`.
  Mitigation: the verification grep plus a review rule that assertions stay
  exact; Task 18 re-runs the whole unit lane.
- Risk: metric values re-derive detection and drift from it.
  Mitigation: metrics consume `MacroSocietyAnalysis` only; no graph work in the
  metric module.
- Risk: the four families are mistaken for a capacity or prevalence claim.
  Mitigation: spec text states candidates are analytical labels with explicit
  coverage; no "society count" is presented as objective population.

## Phase Completion Checklist

- Every Task 8-9 acceptance criterion is satisfied.
- Catalog is exactly 140 with four appended families.
- All catalog-sensitive unit tests pass with exact assertions.
- `index.md` task checkboxes are updated immediately after verified completion.
