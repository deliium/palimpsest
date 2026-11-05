# Phase 3: Detached Analysis, Candidates, and Metrics

Plan: [index.md](index.md)
Tasks: 11-14
Depends on: Phase 2

## Objective

Harvest treaty rows into detached token-only analysis, extend the existing
`dip-` candidate lineage with treaty version lineage, classify researcher-only
recollection alignment, and append four metric families. The catalog moves
from 164 to 168 while the first 164 families keep their IDs, order, versions,
and value keys.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/diplomacy_rows.py` | row types 57-230; `DiplomacyHarvestRows` 233-278; `harvest_diplomacy_rows` 292-517; token helpers imported from `diplomacy_contract` | Exact token-only harvest pattern to extend. |
| `src/analysis/diplomacy_layers.py` | `DiplomacyObjectiveRow` 33-38; `DiplomacySubjectiveRow` 42-46; `DiplomacyAnalyticalRow` 50-56; `assert_diplomacy_layer_separation` 71-100; `project_diplomacy_layers` 103+ | Three-layer separation and hard leakage guard. |
| `src/analysis/diplomacy_detection.py` | `DiplomaticRelationCandidate` 42-56; `detect_diplomacy_candidates` 58+ | Candidate detection by relation/lane evidence. |
| `src/analysis/diplomacy_identity.py` | `DiplomacyAnalysis` 36-52; `DiplomacyLineageEdge` 53-61; `assign_diplomacy_identities` 69-100; `derive_diplomacy_lineage` 101-163; `join_diplomacy_parties` 186+ | Stable `dip-` identity, forward-only lineage, read-only `org-`/`msoc-` joins. |
| `src/analysis/diplomacy_alignment.py` | `DiplomacyAlignmentStatus` 33-40; `DiplomacyEnvoyAlignmentRow` 42-52; `classify_diplomacy_envoy_alignment` 117-198; `summarize_diplomacy` 199-255 | Researcher-only alignment precedent and summary shape. |
| `src/analysis/diplomacy_metrics.py` | `compute_diplomatic_contact_structure` 130-170; `compute_diplomatic_instrument_outcomes` 171-224; `compute_diplomatic_envoy_alignment` 225-270; `compute_inter_society_relation_lanes` 271-319 | Exact metric document shape, coverage, and ratio quantization. |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53; `MetricFamilyId` 238-240; `_spec_diplomatic_*` 7380-7560; family tuple 7760-7762 | Catalog append pattern and exact value-key declarations. |
| `src/analysis/metric_service.py` | 321-323, 1884-1943 | Metric input fields, diplomacy analysis assembly, and document emission. |
| `src/experiments/diplomacy_harvest.py` | `DiplomacyHarvest` 31-42; `build_completed_run_diplomacy_harvest` 50-88 | Completed-run harvest bridge to extend. |
| `src/experiments/collectors.py` | 871-893 | Real completed-run assembly that must emit the new families. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/diplomacy_rows.py` | modify | Add treaty, version, declaration, recollection, anchor, and lineage row types; extend harvest and coverage. |
| `src/analysis/diplomacy_layers.py` | modify | Include treaty-induced status/lane counts in subjective rows; keep objective and analytical separation; add treaty rows to the leakage guard. |
| `src/analysis/diplomacy_detection.py` | modify | Treat treaty evidence as candidate evidence without changing `dip-` identity minting. |
| `src/analysis/diplomacy_identity.py` | modify | Add treaty version lineage edges; retain read-only `org-`/`msoc-` joins. |
| `src/analysis/diplomacy_alignment.py` | modify | Add treaty recollection alignment and summary counts. |
| `src/analysis/diplomacy_metrics.py` | modify | Add four compute functions and value-key documents. |
| `src/analysis/specifications.py` | modify | Add four `MetricFamilyId` members and specifications; set `METRIC_FAMILY_COUNT = 168`. |
| `src/analysis/metric_service.py` | modify | Wire treaty inputs, detection, alignment, layers, and documents. |
| `src/analysis/__init__.py` | modify | Export new public analysis symbols. |
| `src/experiments/diplomacy_harvest.py` | modify | Add treaty rows/lineage/alignment to the harvest object. |
| `src/experiments/collectors.py` | modify | Pass treaty harvest data into `MetricComputationInputs`. |
| `tests/unit/test_diplomacy_treaty_analysis.py` | create | Harvest, tokenization, coverage. |
| `tests/unit/test_diplomacy_treaty_layers.py` | create | Layer separation and leakage. |
| `tests/unit/test_diplomacy_treaty_identity.py` | create | Candidate joins and version lineage. |
| `tests/unit/test_diplomacy_treaty_alignment.py` | create | Researcher-only recollection alignment. |
| `tests/unit/test_diplomacy_treaty_metrics.py` | create | Four documents, exact keys, absence behavior. |
| `tests/unit/test_diplomacy_treaty_catalog.py` | create | 168 pin, first-164 preservation, no score keys. |

## Task 11: Harvest treaty rows and keep three layers separate

### Intent

Turn exported treaty beliefs into detached, token-only rows. The analysis layer
must never receive raw agent IDs, treaty IDs as raw subjects, participant
anchors, terms digests as payloads, or peer-private institutional-memory
content.

### Implementation Steps

1. In `diplomacy_rows.py`, add these frozen row types, each built only from
   `diplomacy_agent_token`, `diplomacy_party_token`,
   `diplomacy_subject_token`, and bounded `require_diplomacy_token` values:
   - `DiplomacyTreatyRow`: `owner_token`, `treaty_id` (as a record ID), 
     `relation_id`, `party_tokens`, `subject_token`, `current_version_id`,
     `opened_tick`, `last_tick`, `provenance`.
   - `DiplomacyTreatyVersionRow`: `owner_token`, `version_id`, `treaty_id`,
     `version_index`, `parent_version_ids`, `change_kind`,
     `party_tokens`, `provision_kinds`, `terms_digest`, `record_refs`,
     `institutional_memory_refs`, `effective_tick`, `end_tick`,
     `proposer_party_token`, `proposer_envoy_token`, `provenance`.
   - `DiplomacyTreatyDeclarationRow`: `owner_token`, `treaty_id`,
     `version_id`, `party_token`, `envoy_token`, `act`, `declared_tick`,
     `provenance`.
   - `DiplomacyTreatyRecollectionRow`: `owner_token`, `treaty_ref`,
     `version_ref`, `subject_token`, `basis`, `stance`,
     `claimed_terms_digest`, `confidence`, `first_tick`, `last_tick`,
     `provenance`.
   - `DiplomacyTreatyMisrepresentationRow`: `owner_token`, `version_id`,
     `kind`, `observed_tick`, `envoy_token`, `party_token`, `provenance`.
   - `DiplomacyTreatyAnchorRow`: `owner_token`, `version_id`,
     `record_anchor_count`, `institutional_memory_anchor_count`,
     `has_record_anchor`, `has_institutional_memory_anchor`,
     `has_any_anchor`.
   - `DiplomacyTreatyLineageRow`: `owner_token`, `treaty_id`,
     `parent_version_id`, `child_version_id`, `change_kind`, `tick`.
2. Extend `DiplomacyHarvestRows` with the matching tuple fields and include
   them in `has_any_rows()` and exact-type validation. Append every new field
   with an empty-tuple default so existing positional and keyword constructors
   remain valid. Keep every existing field and default unchanged.
3. Extend `harvest_diplomacy_rows`:
   - tokenize the owner and parties exactly as V4-10 does;
   - tokenize `subject_kind` into a stable subject token using the existing
     `diplomacy_subject_token` helper on the closed enum value;
   - preserve `treaty_id`/`version_id`/`parent_version_ids` as record IDs
     because they are content-addressed and contain no owner content;
   - tokenize envoy refs with `diplomacy_agent_token`;
   - keep `record_refs` as opaque anchor tokens and
     `institutional_memory_refs` as opaque 64-hex tokens;
   - never include free-text terms because none exist;
   - set coverage to `partial` when any treaty notice, pruned row, or
     unresolved anchor is present.
4. In `diplomacy_layers.py`:
   - add treaty status counts and provision-kind counts to
     `DiplomacySubjectiveRow` through new fields
     `treaty_status_counts` and `treaty_subject_counts`, appended with
     empty-tuple defaults so existing constructors remain valid;
   - add treaty/version/lineage counts to the analytical row only from
     deduplicated tokens;
   - extend `assert_diplomacy_layer_separation` so objective rows may not
     contain `owner_token`, `treaty_id`, `version_id`, `party_token`,
     `candidate_id`, or `organization_candidate_ids`;
   - reject any row containing `DIPLOMACY_FORBIDDEN_RESULT_FIELDS`
     (`score`, `relation_score`, `trust`, `rank`, `valence`, `index`,
     `composite`, `overall_relation`, `bilateral_score`, `mean_score`, and the
     existing truth/verified/legitimate names).
5. In `diplomacy_harvest.py`, add `treaties`, `treaty_versions`,
   `treaty_declarations`, `treaty_recollections`, `treaty_lineage`, and
   `treaty_alignment` to `DiplomacyHarvest`, populated by the extended harvest
   and alignment functions.
6. In `collectors.py`, pass the treaty harvest rows through
   `MetricComputationInputs` without re-reading ledgers or analysis objects.

### Required Interfaces and Contracts

- Analysis rows contain only tokens and content-addressed record IDs.
- `terms_digest` is a 64-hex canonical digest, not a payload; it is never
  rendered as text or used as a score.
- `record_refs` and `institutional_memory_refs` are opaque anchors. Analysis
  may count them, never resolve peer anchors into private content.
- Objective rows remain event-derived counts; owner rows remain subjective;
  analytical rows remain candidate-level. No row type mixes the layers.
- Coverage is explicit: complete only when every owner ledger was exported and
  no notices/pruning occurred.
- Type the new row tuples concretely. Where an existing port exposes
  `tuple[object, ...]`, narrow with `cast`/`isinstance` before reading fields;
  do not add `# type: ignore`.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` Key Principle 1 and "analysis is read-only".
- V4-08/V4-09 three-layer precedent and V4-10 `diplomacy_rows`/`layers`.
- Original Request "records, participants, recognized representatives,
  institutional memory, agent beliefs" requires each dimension to be visible
  to analysis without collapsing into one truth model.

### Error Handling and Logging

- Invalid row shapes raise `DiplomacyAnalysisError("diplomacy_invalid_row")`.
- Log `treaty_rows_harvested owners=%s treaties=%s versions=%s` at DEBUG with
  counts only.
- Never log owner tokens, treaty/version IDs, participants, records,
  institutional-memory refs, digests, or confidence values.

### Tests

`tests/unit/test_diplomacy_treaty_analysis.py`:

- Harvest two owners with treaties, versions, declarations, recollections,
  misrepresentations, anchors, and lineage; assert token-only rows.
- Assert raw agent IDs, free-text subjects, terms, record contents, and
  institutional-memory content never appear.
- Assert exact row ordering by `(owner_token, tick, id)`.
- Assert coverage is `partial` with notices/pruning and `complete` without.
- Assert `has_any_rows()` is true for treaty-only ledgers.
- Assert each existing constructor (`DiplomacyHarvestRows()`,
  `DiplomacySubjectiveRow(...)`, `DiplomacyAnalysisSummary(...)`) still works
  without treaty fields and reports empty/zero treaty values.

`tests/unit/test_diplomacy_treaty_layers.py`:

- Project objective, subjective, and analytical rows.
- Attempt each cross-layer leak and assert `diplomacy_layer_leak`.
- Assert treaty counts appear only in subjective/analytical rows.
- Assert no forbidden score/truth field exists.

### Acceptance Criteria

- Treaty beliefs harvest into detached token-only rows.
- Three layers remain separate with a hard leakage guard.
- Coverage is explicit.
- No raw private content is published.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_analysis.py tests/unit/test_diplomacy_treaty_layers.py tests/unit/test_diplomacy_layers.py -q`
- Expected: all tests pass.

## Task 12: Extend candidates lineage and read-only identity joins

### Intent

Make treaty evidence participate in the existing `dip-` candidate analysis and
add version lineage without minting, renaming, splitting, merging, or dissolving
any `org-` or `msoc-` identity.

### Implementation Steps

1. In `diplomacy_detection.py`, include treaty participation and accepted
   versions as candidate evidence for the relation pair. Do not change the
   candidate ID formula or the existing lane evidence rules.
2. In `diplomacy_identity.py`, add `TreatyVersionLineageEdge` with
   `edge_id`, `treaty_id`, `from_version_id`, `to_version_id`, `change_kind`,
   `tick`, and `derive_treaty_version_lineage(rows)`. Use
   `dip-edge-<hex>` identity; content-address and sort deterministically.
3. Extend `join_diplomacy_parties` to return treaty participant joins against
   existing `org-` and `msoc-` candidates through owner-safe `orgc-` and region
   anchors. The join is read-only: return candidate IDs and party tokens only.
4. Ensure no code path calls an identity mint/rename/split/merge/dissolve
   helper. Build an AST test that scans analysis treaty modules for those
   call names.
5. Extend `DiplomacyAnalysis` with `treaty_count`, `version_count`,
   `accepted_version_count`, and `lineage_edge_count` fields. Keep existing
   fields and order; append new fields with defaults so existing constructors
   remain valid.

### Required Interfaces and Contracts

- `dip-` candidates remain relation-pair candidates; treaty evidence does not
  mint a second candidate namespace.
- Version lineage edges are analytical records, not owner beliefs, and never
  feed cognition.
- `org-` and `msoc-` IDs are analysis-only and are never written back.
- A missing organization/macro identity leaves the join unresolved; it never
  invents one.

### Requirement Evidence (when reconciliation applies)

- Original Request "Track versions and lineage".
- `.ai-factory/ARCHITECTURE.md` V4-02/V4-03 analysis-only identity seams.
- `src/analysis/diplomacy_identity.py` 69-226.

### Error Handling and Logging

- Invalid edges raise `DiplomacyAnalysisError("diplomacy_invalid_row")`.
- Log `treaty_lineage_derived edges=%s` at DEBUG. Never log edge IDs,
  version IDs, or participant tokens.

### Tests

`tests/unit/test_diplomacy_treaty_identity.py`:

- Build a version DAG with original, amendment, renewal, accession, and
  withdrawal; assert edges, ticks, and ordering.
- Assert candidate identity is unchanged when only treaty evidence differs.
- Assert `org-`/`msoc-` joins resolve only through owner-safe anchors and are
  read-only.
- Assert no mint/rename/split/merge/dissolve call exists.
- Assert no `msoc-` or `org-` token is mutated or fabricated.

### Acceptance Criteria

- Treaty evidence extends candidates and lineage deterministically.
- Identity joins remain read-only.
- No analytical identity is minted or changed.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_identity.py tests/unit/test_diplomacy_identity.py -q`
- Expected: all tests pass.

## Task 13: Classify researcher-only treaty recollection alignment

### Intent

Represent "misremember" without putting truth into cognition. A researcher-only
classifier compares an owner's recollection claim to a retained version digest
and reports `consistent`, `unresolved`, `inconsistent`, or `not_applicable`.

### Implementation Steps

1. In `diplomacy_alignment.py`, add `TreatyRecollectionAlignmentRow` with
   `owner_token`, `treaty_ref`, `version_ref`, `subject_token`,
   `claimed_terms_digest`, `status`, and `basis`. Reuse
   `DiplomacyAlignmentStatus`; do not create a second status enum.
2. Add `classify_treaty_recollection_alignment(rows: DiplomacyHarvestRows,
   versions: Sequence[object] = ()) -> tuple[...]`:
   - first add `"treaty": frozenset({"negotiate", "decide"})` to the local
     `_SCOPE_COVERAGE` map and `"treaty"` to `_LONG_RUNNING` so researcher
     alignment uses the same matrix as cognition;
   - `ignore` and `renew` stances with no claimed digest are
     `not_applicable`;
   - `remember`/`reinterpret` with no claim or no local version are
     `unresolved`;
   - a claimed digest equal to the local version digest is `consistent`;
   - a claimed digest different from the local version digest is
     `inconsistent`;
   - a local version with a different subject kind is `inconsistent` only when
     both subject tokens are present; otherwise `unresolved`.
3. Extend `DiplomacyAnalysisSummary` with `treaty_count`,
   `treaty_version_count`, `treaty_accepted_count`,
   `recollection_count`, `recollection_consistent_count`,
   `recollection_unresolved_count`, `recollection_inconsistent_count`,
   `recollection_not_applicable_count`, and
   `recollection_aligned_count`. Append every new field with a zero default so
   existing constructors remain valid; keep existing fields and order.
4. Extend `summarize_diplomacy` to compute those counts from treaty rows and
   alignment rows.
5. Add an architecture test that `TreatyRecollectionAlignmentRow` and
   `DiplomacyAlignmentStatus` are absent from `src/agents`, `src/world`, and
   `src/observer`.

### Required Interfaces and Contracts

- Alignment is a researcher classification, not a truth verdict.
- `inconsistent` means "the claim differs from the retained record", not
  "the agent lied".
- A missing record is `unresolved`, never `inconsistent`.
- Alignment never reaches cognition, prompts, memory, world state, stop
  selectors, observer semantics, or the Godot client.
- No `misremembered`, `false`, `lie`, `guilty`, or `truth` field exists.

### Requirement Evidence (when reconciliation applies)

- Original Request "misremember them" and "WorldEngine does not magically
  enforce them".
- `.ai-factory/ARCHITECTURE.md` "analysis is read-only" and V4-08/V4-09
  researcher-only alignment precedent.
- `src/analysis/diplomacy_alignment.py` 33-255.

### Error Handling and Logging

- Invalid status raises `DiplomacyAnalysisError("diplomacy_invalid_row")`.
- Log `treaty_recollection_alignment consistent=%s unresolved=%s
  inconsistent=%s` at DEBUG with counts only.

### Tests

`tests/unit/test_diplomacy_treaty_alignment.py`:

- Equal digest -> `consistent`; different digest -> `inconsistent`; absent
  version/digest -> `unresolved`; ignore/renew without claim ->
  `not_applicable`.
- Subject mismatch -> `inconsistent` when both tokens are present, otherwise
  `unresolved`.
- Alignment rows contain no truth/lie/guilt field.
- Alignment symbols are absent from cognition/world/observer.
- Summary counts match rows and ratios remain unquantized counts (quantized
  only where a metric document requires it).

### Acceptance Criteria

- Recollection alignment is researcher-only and closed.
- Misremembering is represented as a record-relative classification.
- No truth field or enforcement path exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_alignment.py tests/unit/test_diplomacy_analysis.py -q`
- Expected: all tests pass.

## Task 14: Add four metric families and raise the catalog to 168

### Intent

Append treaty observability to the closed metric catalog without changing the
first 164 families. The four families cover structure, version lineage,
recollection alignment, and anchor coverage.

### Implementation Steps

1. In `specifications.py`, add `MetricFamilyId` members:
   - `TREATY_STRUCTURE = "treaty_structure"`
   - `TREATY_VERSION_LINEAGE = "treaty_version_lineage"`
   - `TREATY_RECOLLECTION = "treaty_recollection"`
   - `TREATY_ANCHOR_COVERAGE = "treaty_anchor_coverage"`
2. Add four `_spec_treaty_*` functions following the existing `_spec_*`
   pattern. Exact value keys:
   - `treaty_structure@1`: `treaty_count`, `participant_count`,
     `multi_party_count`, `apparently_accepted_count`, `suspended_count`,
     `terminated_count`, `expired_count`, `superseded_count`,
     `subject_kind_histogram`, `participant_count_histogram`, `coverage`.
   - `treaty_version_lineage@1`: `version_count`, `original_count`,
     `amendment_count`, `renewal_count`, `accession_count`,
     `withdrawal_count`, `suspension_count`, `termination_count`,
     `lineage_edge_count`, `max_lineage_depth`, `renewal_ratio`, `coverage`.
   - `treaty_recollection@1`: `recollection_count`, `remember_count`,
     `reinterpret_count`, `ignore_count`, `renew_count`,
     `basis_histogram`, `consistent_count`, `unresolved_count`,
     `inconsistent_count`, `not_applicable_count`,
     `aligned_recollection_count`, `consistency_ratio`,
     `inconsistency_ratio`, `coverage`.
   - `treaty_anchor_coverage@1`: `version_count`, `record_anchor_count`,
     `institutional_memory_anchor_count`, `versions_with_record_anchor`,
     `versions_with_institutional_memory_anchor`, `versions_without_any_anchor`,
     `record_anchor_coverage_ratio`, `institutional_memory_coverage_ratio`,
     `coverage`.
   No family may contain `score`, `relation_score`, `trust`, `rank`,
   `valence`, `index`, `composite`, `mean_score`, `overall_relation`,
   `truth`, `verified`, or `legitimate`.
3. Add `compute_treaty_structure`, `compute_treaty_version_lineage`,
   `compute_treaty_recollection`, and `compute_treaty_anchor_coverage` to
   `diplomacy_metrics.py`. Use `_document`, `_availability`, `_coverage`,
   `_ratio`, and `_counts` exactly as the V4-10 compute functions do. Ratios
   are quantized to the same precision as existing metrics; counts are
   integers; histograms are canonical JSON strings sorted by closed value.
4. Append the four specifications to the family tuple after
   `inter_society_relation_lanes@1`, set `METRIC_FAMILY_COUNT = 168`, and
   update `validate_metric_catalog`.
5. In `metric_service.py`, extend `MetricComputationInputs` with
   `diplomacy_treaty_rows` and `diplomacy_treaty_alignment` optional fields;
   pass harvested treaty rows through detection, identity, layers, alignment,
   and the four compute functions; append all four documents only when the
   diplomacy ledger exists.
6. In `experiments/collectors.py`, pass the treaty harvest rows and alignment
   into `MetricComputationInputs` so real completed-run assembly emits all
   four documents.
7. Sweep every current 164 pin to 168:
   - `src/analysis/specifications.py` count;
   - 77 `== 164` occurrences in tests plus current `164` prose lines in
     `docs/` and `.ai-factory/`;
   - current doc lines in `docs/analysis-metrics.md`, `docs/architecture.md`,
     `docs/disputes.md`, `docs/evidence-testimony.md`,
     `docs/delegation-representation.md`, `docs/diplomacy.md`,
     `.ai-factory/ARCHITECTURE.md`, and `.ai-factory/DESCRIPTION.md`.
   Do not rewrite historical revision statements such as "160 -> 164",
   "the first 154 keep", or fixed historical digests. Update only current-pin
   assertions and current-count prose.
8. Add a stale-pin guard test that scans current catalog assertions and
   current-pin doc lines for `164` and fails if any remains, while explicitly
   allowing historical revision statements and the first-154 digest pin.

### Required Interfaces and Contracts

- Catalog is exactly 168 families.
- The first 164 keep ID, order, version, and value keys.
- The four new families are appended last.
- Every family has an explicit population, denominator, denominator kind,
  cohort window, deceased policy, zero-holding policy, opportunity-vs-
  occurrence statement, self-edge policy, censoring policy, formulas, value
  keys, empty case, and unknown case.
- No family exposes a composite, bilateral score, truth, legitimacy, or
  enforcement value.
- Missing treaty input yields an absent family; an enabled empty ledger yields
  a present family with zero counts.

### Requirement Evidence (when reconciliation applies)

- Original Request "Track versions and lineage" and "Later generations may
  remember them, misremember them, reinterpret them, ignore them, renew them".
- `.ai-factory/ARCHITECTURE.md` "analysis is read-only" and metric catalog
  append-only contract.
- `src/analysis/specifications.py` 53, 7380-7762.

### Error Handling and Logging

- Catalog drift raises the existing validation error.
- Log `treaty_metrics_emitted families=4 catalog=168` at INFO with no owner
  or treaty identifiers.
- Do not log metric values, digests, or anchors.

### Tests

`tests/unit/test_diplomacy_treaty_metrics.py`:

- Exact value keys and allowed value types for each family.
- Absent inputs -> no values; empty ledger -> zero counts.
- Hand-built treaty/version/recollection/anchor rows produce expected counts
  and ratios.
- Completed-run assembly emits all four treaty documents.
- No forbidden score/truth key exists.

`tests/unit/test_diplomacy_treaty_catalog.py`:

- `METRIC_FAMILY_COUNT == 168`.
- First 164 IDs/order/versions unchanged against a captured tuple.
- Four treaty families are last.
- No test or current-pin doc line asserts 164.
- Historical revision statements and first-154 digest remain.
- `test_diplomacy_catalog.py` expected 164 assertions are updated to 168.

### Acceptance Criteria

- Catalog is exactly 168.
- Four treaty families append with exact keys.
- Real completed-run assembly emits them.
- No stale current 164 pin remains.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_metrics.py tests/unit/test_diplomacy_treaty_catalog.py tests/unit/test_diplomacy_metrics.py tests/unit/test_diplomacy_catalog.py -q`
- `rg -n "== 164" tests` returns no current-pin match.
- Expected: all tests pass.

## Phase Risks and Mitigations

- Risk: Tokenizing treaty IDs accidentally exposes owner content.
  Mitigation: IDs are content-addressed; owners and parties are hashed;
  record anchors stay opaque; raw subject strings are never row fields.
- Risk: Version lineage is treated as candidate identity.
  Mitigation: version edges use `dip-edge-`; candidates remain relation pairs.
- Risk: Metric sweep rewrites historical seams.
  Mitigation: explicit allowlist for historical revision statements and the
  first-154 digest; guard test checks current pins only.
- Risk: `misremember` leaks into cognition.
  Mitigation: alignment lives in `analysis.diplomacy_alignment` and the
  architecture test scans cognition/world/observer.

## Phase Completion Checklist

- Every Task 11-14 acceptance criterion is met.
- Treaty rows harvest as tokens and keep three layers separate.
- Version lineage is analytical and read-only.
- Four families are appended and the catalog is 168.
- Every current 164 pin is swept; historical statements remain.
- `index.md` checkboxes are updated only after verification passes.
