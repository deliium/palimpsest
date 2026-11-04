# Phase 3: Detached Analysis, Candidates, and Metrics

Plan: [index.md](index.md)
Tasks: 10-13
Depends on: Phase 2 / Task 9

## Objective

Build a detached, read-only evidence analysis stack: normalized owner rows,
objective anchors from committed events, deterministic cross-owner candidates
with forward-only lineage, three strictly separated layers, researcher-only
objective alignment, and three appended metric families (catalog 154 → 157).

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/dispute_contract.py` | policy/identity versions 18-19; prefixes 20-25; owner-local prefixes 31-41; foreign prefixes 45-54; statuses 90-118; errors 121-130; coverage 137-169 | Contract precedent for a new analysis family |
| `src/analysis/disputes.py` | row types 117-418; `DisputeHarvestRows` 421-455; `harvest_dispute_rows` 491-723 | Row/harvest shape and pruned-coverage derivation |
| `src/analysis/dispute_evidence.py` | anchor kinds 37-47; `DisputeObjectiveAnchorRow` 115-148; event mapping 234-357; windows 372-462 | Objective anchor mapping and window bounds |
| `src/analysis/dispute_detection.py` | member claim 57-70; candidate 73-119; statuses 122-164; detection 267-325 | Candidate detection precedent |
| `src/analysis/dispute_identity.py` | thresholds 38-39; records 67-152; assignment 248-389 | Forward-only identity and split/merge |
| `src/analysis/dispute_lineage.py` | alignment 93-99; anchors 353-396; summary 232-338; derive 514-611; validation 614-649 | Researcher-only alignment precedent |
| `src/analysis/dispute_layers.py` | row types 78-181; projection 365-395; separation 414-456 | Hard three-layer leakage guard |
| `src/analysis/dispute_metrics.py` | `_document` 67-102; three compute functions 105-264 | Metric document shape |
| `src/analysis/specifications.py` | count 53; family ids 229-231; dispute builders 6835-7050; `_BUILDERS` 7205-7207; validation 7229-7262 | Where three families are appended |
| `src/analysis/metric_service.py` | inputs 315-316; dispute block 1629-1706 | Where evidence assembly is dispatched |
| `src/experiments/collectors.py` | dispute input 829-849; committed events 176-178 | Where evidence inputs are populated |
| `tests/unit/test_dispute_catalog.py` | first-151 digest 20-65 | Catalog append test precedent |
| `tests/architecture/test_dispute_boundaries.py` | pins 403-466 | Boundary pin precedent |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/evidence_testimony_contract.py` | create | Policy/identity versions, prefixes, enums, coverage, errors, digests |
| `src/analysis/evidence_testimony_rows.py` | create | Row dataclasses and `harvest_evidence_rows` |
| `src/analysis/evidence_testimony_objective.py` | create | Objective anchor kinds, event mapping, windows |
| `src/analysis/evidence_testimony_detection.py` | create | Cross-owner candidates |
| `src/analysis/evidence_testimony_identity.py` | create | Forward-only lineage and split/merge |
| `src/analysis/evidence_testimony_alignment.py` | create | Researcher-only alignment summaries |
| `src/analysis/evidence_testimony_layers.py` | create | Three-layer projection and leakage guard |
| `src/analysis/evidence_testimony_metrics.py` | create | Three metric documents |
| `src/analysis/specifications.py` | modify | Family ids, three builders, count 157 |
| `src/analysis/metric_service.py` | modify | `MetricComputationInputs` fields and dispatch |
| `src/analysis/__init__.py` | modify | Public facade exports for the evidence analysis |
| `src/experiments/collectors.py` | modify | Populate evidence rows/anchors |
| `tests/unit/test_evidence_testimony_analysis.py` | create | Rows, windows, candidates, identity |
| `tests/unit/test_evidence_testimony_layers.py` | create | Layer separation and alignment |
| `tests/unit/test_evidence_testimony_metrics.py` | create | Metric values and availability |
| `tests/unit/test_evidence_testimony_metric_service.py` | create | Completed-run assembly and collectors |
| `tests/unit/test_evidence_testimony_catalog.py` | create | 157 catalog, first 154 unchanged, new families last |
| `tests/unit/evidence_testimony_helpers.py` | modify | Synthetic ledgers/rows used by the above |
| `.ai-factory/DESCRIPTION.md` | modify | Current pin 154 → 157 (historical V4-07 statements stay) |
| `.ai-factory/ARCHITECTURE.md` | modify | Baseline table and current pin 154 → 157 (historical seam text stays) |
| `docs/architecture.md` | modify | Current pin 154 → 157 |
| `docs/disputes.md` | modify | Current pin 154 → 157 (historical 151 → 154 statement stays) |
| `docs/analysis-metrics.md` | modify | Closed catalog cardinality 154 → 157 |
| `tests/unit/test_dispute_docs.py` | modify | Global catalog count pin 154 → 157 |
| `tests/unit/test_formal_rule_docs.py` | modify | Global catalog count strings 154 → 157 |
| `tests/unit/test_organization_docs.py` | modify | Global catalog count strings 154 → 157 |
| `tests/unit/test_organization_operations_docs.py` | modify | Global count assertion and strings 154 → 157 |
| Every existing test module that hard-codes the 154 catalog pin (enumerated in Task 13) | modify | Replace only the catalog-count assertion with 157 |

## Task 10: Harvest evidence rows and objective anchors

### Intent

Normalize exported owner ledgers into detached rows and map committed objective
events into content-addressed anchors that analysis can compare later. Neither
step may read live cognition or write world state.

### Implementation Steps

1. Create `src/analysis/evidence_testimony_contract.py` with:
   - `EVIDENCE_ANALYSIS_POLICY_VERSION = "evidence-testimony-analysis.v1"`
   - `EVIDENCE_IDENTITY_VERSION = "evidence-testimony-identity.v1"`
   - analytical prefixes `evid-`, `evid-item-`, `evid-edge-`, `evid-pub-`;
   - `EVIDENCE_OWNER_LOCAL_PREFIXES = ("evs-", "evw-", "evi-", "evc-", "evx-",
     "eva-")`;
   - `EVIDENCE_FOREIGN_CANDIDATE_PREFIXES = ("disp-", "dispcl-", "dispres-",
     "frule-", "org-", "orgop-", "orgc-", "msoc-", "off-", "inst-", "med-")`;
   - `EVIDENCE_FORBIDDEN_RESULT_FIELDS = frozenset({"truth", "verified",
     "authenticated", "authentic", "forged", "fake", "proof", "verdict",
     "guilt", "guilty", "liable", "liability", "true_owner", "winner"})`;
   - `EvidenceCandidateStatus`: `convergent`, `contested`, `fragmented`,
     `isolated`, `unknown`;
   - `EvidenceLayer`: `objective`, `subjective`, `analytical`;
   - `EvidenceLineageKind`: `continued`, `transformed`, `split`, `merge`,
     `dissolved`, `emerged`;
   - closed analysis token frozensets that mirror cognition without importing
     it: `EVIDENCE_SOURCE_KINDS`, `EVIDENCE_PROVENANCE_CHANNELS`,
     `EVIDENCE_INTERPRETATIONS`, `EVIDENCE_CUSTODY_STATUSES`,
     `EVIDENCE_TRUST_BASES`, `EVIDENCE_CONFIDENCE_BANDS`;
   - `EvidenceAnalysisError`, `EvidenceCoverage` (`complete`/`partial`),
     `derive_evidence_candidate_id`, `evidence_edge_id`, validators, and
     `evidence_candidate_key`.
2. Create `src/analysis/evidence_testimony_rows.py` with frozen row types:
   `EvidenceSourceRow`, `EvidenceTestimonyRow`, `EvidenceItemRow`,
   `EvidenceCustodyRow`, `EvidenceContradictionRow`, `EvidenceEvaluationRow`,
   and `EvidenceHarvestRows` (rows + policy version + window bounds + coverage).
   Each row carries owner token (16-hex), closed enums, confidence band, tick,
   subject token, owner-local reference id, and an optional opaque correlation
   token only; no free text.
3. Implement `harvest_evidence_rows(ledgers, *, window_ticks=100)`:
   - reject duplicate owners and foreign types;
   - dedupe by owner + local id;
   - derive each source's `custody_status` from that owner's custody rows using
     the closed status values (analysis re-derives it from rows; it must not
     import `agents.cognition`);
   - derive `coverage="partial"` from any `pruned_*` counter or truncation
     notice;
   - sort rows by `(owner token, tick, local id)`.
4. Create `src/analysis/evidence_testimony_objective.py`:
   - `EvidenceObjectiveAnchorKind`: `artifact_created`, `artifact_modified`,
     `artifact_moved`, `artifact_destroyed`, `artifact_damaged`,
     `artifact_copied`, `repository_deposited`, `repository_retrieved`,
     `repository_maintained`, `transfer`, `harm`, `commitment_declared`,
     `communication`, `item_state`.
   - `EvidenceObjectiveAnchorRow` content-addressed by sha256 over
     kind/tick/actor/target/subject/quantity/correlation_token, plus a
     `correlation_token` field that carries the opaque event id for
     occurrence/communication anchors.
   - `evidence_objective_anchor_rows_from_events(events, entity_to_agent)`:
     whitelist exactly `ArtifactCreated`, `ArtifactModified`, `ArtifactMoved`,
     `ArtifactDestroyed`, `ArtifactDamaged`, `ArtifactCopied`,
     `RepositoryMemberDeposited`, `RepositoryMemberRetrieved`,
     `RepositoryMaintained`, `Given`, `Taken`, `Attacked`,
     `CommitmentDeclared`, `Talked`, `Asked`, `Told`, `ItemStored`, `Dropped`;
     project only the fixed token/quantity subset; drop rows with unresolvable
     actors/targets; dedupe and sort.
   - Communication anchors are keyed exactly: `subject_token =
     event.details.utterance.declared.communication_id`, `actor_token =
     speaker`, `target_token = listener`, `correlation_token =
     event.event_id.value`. Occurrence anchors use the same
     `correlation_token = event.event_id.value` so a remembered source can be
     aligned by its opaque correlation.
   - `EVIDENCE_MAX_WINDOWS = 1024`.
   - `build_evidence_windows(rows, *, window_ticks=100, objective_rows=()) ->
     tuple[EvidenceWindowEvidence, ...]`: aggregate counts per tick window; an
     empty window is explicitly `partial`, never synthesized.
5. Keep `analysis` imports limited to `analysis` and stdlib. Objective events
   are consumed as duck-typed committed values: match `type(event.details).__name__`
   and read only the fixed attributes/keys; never import `world`, an event
   store, or an engine.

### Required Interfaces and Contracts

- Objective anchors carry no event body, no request id, no world object, and no
  owner id.
- Owner rows carry no owner id, only the safe token.
- Missing evidence yields `coverage="partial"`; never a fabricated zero row.
- All ordering is deterministic; no wall clock, `hash()`, or unordered sets.

### Requirement Evidence

- Original Request "Provide research tooling to compare evidence with objective
  history".
- `.ai-factory/ARCHITECTURE.md` "analysis is read-only".
- `src/analysis/dispute_evidence.py` 234-462.

### Error Handling and Logging

- Invalid rows raise `EvidenceAnalysisError` with a closed code.
- WARN `evidence_analysis_partial owners=%s` (count only).
- DEBUG `evidence_rows_harvested sources=%s testimony=%s items=%s` (counts).

### Tests

- Extend `tests/unit/test_evidence_testimony_analysis.py`:
  - harvest dedupes and sorts;
  - duplicate owners are rejected;
  - pruned ledgers produce partial coverage;
  - each whitelisted event maps to the expected anchor kind and a stable
    content digest;
  - an unresolvable entity drops the anchor;
  - windows trim beyond 1024 and mark empty windows partial.
- Command: `uv run pytest tests/unit/test_evidence_testimony_analysis.py -q`.

### Acceptance Criteria

- Rows and anchors are reproducible from the same inputs.
- No live engine, cognition, or persistence object is imported.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_analysis.py -q`
- Expected: pass.

## Task 11: Detect candidates and derive forward-only lineage

### Intent

Group owner rows into cross-owner evidence candidates about the same subject and
track identity over windows without creating a global evidence registry.

### Implementation Steps

1. Create `src/analysis/evidence_testimony_detection.py`:
   - `EvidenceMemberItem(owner_token, local_ref, source_kind, interpretation,
     confidence_band)`.
   - `EvidenceCandidate(candidate_id, subject_token, source_kind_family,
     owner_tokens, item_count, source_count, testimony_count,
     contradiction_count, status, coverage, first_tick, last_tick,
     creation_digest)`.
   - Group key `(subject_token, source_kind_family)` where the family is
     `testimonial` for witness testimony/remembered event, `documentary` for
     written record/artifact, `agreement` for prior agreement, `reputational`
     for reputation, `physical` for physical state, `unknown` otherwise.
   - Status rules: `contested` when any retained contradiction; `convergent`
     when ≥2 owners with no contradiction; `fragmented` when ≥2 owners but all
     roots are shared/empty; `isolated` for one owner; `unknown` otherwise.
   - Coverage is `partial` when any member row is partial.
2. Create `src/analysis/evidence_testimony_identity.py`:
   - `EVIDENCE_IDENTITY_SPLIT_THRESHOLD = 0.4`,
     `EVIDENCE_IDENTITY_MERGE_THRESHOLD = 0.4`.
   - `EvidenceRecord`, `EvidenceTransition`, `EvidenceWindowSnapshot`,
     `EvidenceIdentityAssignment`.
   - `assign_evidence_identities(...)` produces `continued`, `transformed`,
     `emerged`, `dissolved`, `split`, `merge` transitions, forward-only and
     deterministic.
3. Expose `detect_evidence_window_candidates` and
   `assign_evidence_identities` for Task 12's public
   `derive_evidence_lineage`. Task 11 tests detection and identity directly;
   the public lineage composer is added in Task 12.
4. Never reuse a `disp-`, `frule-`, `org-`, `msoc-`, `off-`, `inst-`, or
   `med-` identity; candidates are always `evid-`.

### Required Interfaces and Contracts

- Candidate identity is creation-evidence based and stable across equal inputs.
- No candidate owns or mutates another context's identity.
- A candidate is an analytical object only; it never appears in cognition.

### Requirement Evidence

- Original Request "general social evidence model" + research tooling.
- `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; Key Principle 1.
- `src/analysis/dispute_detection.py` 57-325; `dispute_identity.py` 183-389.

### Error Handling and Logging

- Cycles, backward edges, or unknown endpoints raise
  `EvidenceAnalysisError("evidence_testimony_lineage_invalid")`.
- DEBUG `evidence_candidates_detected count=%s contested=%s` (counts only).

### Tests

- Extend `tests/unit/test_evidence_testimony_analysis.py`:
  - one owner yields `isolated`;
  - two owners yield `convergent` or `contested`;
  - shared roots without contradictions yield `fragmented`;
  - identity is stable and forward-only;
  - a split and a merge each produce the expected transition kinds;
  - no `disp-`/`frule-`/`org-` id appears in an evidence candidate.
- Command: `uv run pytest tests/unit/test_evidence_testimony_analysis.py -q`.

### Acceptance Criteria

- Cross-owner candidates never merge owners' beliefs into one truth.
- Lineage is acyclic and forward-only.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_analysis.py -q`
- Expected: pass.

## Task 12: Project layers and researcher-only objective alignment

### Intent

Keep objective counts, owner rows, and analytical candidates in three separate
types, and compute a researcher-only alignment of evidence with committed
history without leaking it into cognition.

### Implementation Steps

1. Create `src/analysis/evidence_testimony_layers.py`:
   - `EvidenceObjectiveRow` (integer counts only: source_count, testimony_count,
     record_count, artifact_count, custody_link_count, contradiction_count,
     evaluation_count, window_count).
   - `EvidenceSubjectiveRow` (safe owner token, closed kind counts, confidence
     band counts, custody status counts).
   - `EvidenceAnalyticalRow` (`evid-` candidate, subject token, status counts).
   - `EvidenceLayerView`.
   - `project_evidence_layers(rows, analysis, summary, windows=(), objective_rows=())`.
   - `assert_evidence_layer_separation(view)`:
     - no owner id/owner token/candidate id in objective rows;
     - no owner id in analytical rows;
     - subjective references are never `evid-`;
     - analytical subject is never an owner-local prefix;
     - no forbidden result field (`truth`, `verified`, `authenticated`,
       `authentic`, `forged`, `fake`, `proof`, `verdict`, `guilt`, `guilty`,
       `liable`, `liability`, `true_owner`, `winner`).
2. Create `src/analysis/evidence_testimony_alignment.py`:
   - `EvidenceObjectiveAlignment`: `consistent`, `unresolved`, `inconsistent`,
     `not_applicable`.
   - `EvidenceCustodyAlignment`: `matches`, `partially_matches`, `mismatches`,
     `unknown`, `not_applicable`.
   - `classify_evidence_objective_alignment(row, anchors)`:
     - `witness_testimony`: match `communication` anchors by
       `subject_token` = `communication_id` and tick; same speaker/listener →
       consistent, different actor at the same communication id → inconsistent,
       absent → unresolved;
     - `written_record`/`artifact`: match artifact anchors by subject token and
       lifecycle tick; matching author/created tick → consistent, existence
       contradicted (destroyed before claim) or author mismatch → inconsistent,
       absent → unresolved;
     - `physical_state`: match transfer/harm/item-state anchors by subject and
       holder/location; matching → consistent, different holder/location at the
       claim tick → inconsistent, absent → unresolved;
     - `prior_agreement`: match commitment anchors by parties/kind/tick;
       matching → consistent, contradicting parties/kind → inconsistent,
       absent → unresolved;
     - `reputation`: `not_applicable`;
     - `remembered_event`: match occurrence anchors by `correlation_token` and
       tick; matching → consistent, differing actor/tick → inconsistent, absent
       → unresolved;
     - `unknown`: `not_applicable`.
   - `classify_custody_alignment(chain, anchors)`: compare each claimed link to
     artifact/repository anchors at the same tick; all matched → `matches`, some
     matched → `partially_matches`, any explicit opposite → `mismatches`, no
     anchor → `unknown`, not applicable → `not_applicable`.
   - `EvidenceAnalysis`, `EvidenceAnalysisSummary` with numerators and
     denominators for every metric value; `summarize_evidence`,
     `evidence_analysis_digest`.
3. Alignment never emits a verdict, authenticity, guilt, liability, or a
   "correct account" field. It only classifies the relationship for researchers.

### Required Interfaces and Contracts

- `derive_evidence_lineage` returns candidates, edges, alignment, custody
  alignment, and summary; all values are detached.
- The summary exposes every numerator and denominator needed by the three
  families, including applicable/classifiable item counts and applicable custody
  chain counts, so ratios are never computed over `not_applicable` rows.
- `assert_evidence_layer_separation` is a hard `assert`-style guard called by
  projection and publication.
- Objective alignment is never imported by `agents.cognition`, `simulation`
  runtime, `api`, `observer`, or `research_runner` execution paths.

### Requirement Evidence

- Original Request "without leaking truth into cognition".
- `.ai-factory/ARCHITECTURE.md` Key Principle 1; "analysis is read-only".
- `src/analysis/dispute_layers.py` 414-456; `dispute_lineage.py` 370-396.

### Error Handling and Logging

- Layer leakage raises `EvidenceAnalysisError("evidence_testimony_layer_leak")`.
- WARN `evidence_alignment_partial candidates=%s` (count only).
- Never log subject tokens or classifier inputs.

### Tests

- Create `tests/unit/test_evidence_testimony_layers.py`:
  - objective rows contain only ints and no owner/candidate fields;
  - analytical rows contain no owner id;
  - a subjective row with `evid-` or an analytical row with `evs-` raises the
    leak error;
  - each source kind classifies as expected for consistent/unresolved/
    inconsistent/not_applicable;
  - custody alignment covers all five statuses;
  - no forbidden result field exists anywhere in the view;
  - cognition modules do not import the alignment module (AST assertion).
- Command: `uv run pytest tests/unit/test_evidence_testimony_layers.py -q`.

### Acceptance Criteria

- Three layers are structurally distinct and cannot be collapsed.
- Alignment is researcher-only and explicitly non-verdict.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_layers.py -q`
- Expected: pass.

## Task 13: Add three metric families and raise the catalog to 157

### Intent

Append three evidence metric families, wire them through real completed-run
assembly, and update every hard-coded catalog pin without changing any existing
family.

### Implementation Steps

1. `src/analysis/specifications.py`:
   - Add `MetricFamilyId.EVIDENCE_SOURCE_STRUCTURE`,
     `EVIDENCE_PROVENANCE_CONTINUITY`, `EVIDENCE_OBJECTIVE_ALIGNMENT`.
   - Add `_spec_evidence_source_structure`,
     `_spec_evidence_provenance_continuity`, `_spec_evidence_objective_alignment`
     following `_spec_dispute_claim_structure` (6835-6904).
   - Append the three builders to `_BUILDERS` (7205-7207).
   - Set `METRIC_FAMILY_COUNT = 157`.
   - Value keys exactly:
     - `EVIDENCE_SOURCE_STRUCTURE`: `candidate_count`, `source_count`,
       `source_kind_histogram`, `testimony_count`, `item_count`,
       `interpretation_histogram`, `confidence_band_histogram`,
       `multi_owner_candidate_ratio`, `uncorroborated_item_ratio`.
     - `EVIDENCE_PROVENANCE_CONTINUITY`: `provenance_channel_histogram`,
       `independent_root_ratio`, `communicated_testimony_ratio`,
       `custody_link_count`, `custody_complete_ratio`,
       `custody_incomplete_count`, `custody_conflicting_count`,
       `missing_provenance_ratio`.
     - `EVIDENCE_OBJECTIVE_ALIGNMENT`: `aligned_item_count`, `consistent_count`,
       `unresolved_count`, `inconsistent_count`, `not_applicable_count`,
       `consistency_ratio`, `custody_match_count`, `custody_mismatch_count`,
       `custody_unknown_count`.
   - Denominator contract (must match the summary and `DenominatorKind`):
     - `EVIDENCE_SOURCE_STRUCTURE`: denominator
       `evidence_items_with_owner_source`; `multi_owner_candidate_ratio` =
       candidates with at least two owner tokens / all candidates;
       `uncorroborated_item_ratio` = active uncorroborated items / active items.
     - `EVIDENCE_PROVENANCE_CONTINUITY`: `independent_root_ratio` = testimonies
       with a distinct non-empty `root_ref` / testimonies with any root;
       `communicated_testimony_ratio` = communicated testimony / all testimony;
       `custody_complete_ratio` = `complete_belief` sources / applicable custody
       sources; `missing_provenance_ratio` = sources with a missing-provenance
       notice / all sources.
     - `EVIDENCE_OBJECTIVE_ALIGNMENT`: `consistency_ratio` = (`consistent` +
       `unresolved` + `inconsistent`) / aligned items excluding
       `not_applicable`; custody ratios use only sources whose custody status is
       applicable and aligned.
2. Create `src/analysis/evidence_testimony_metrics.py` with
   `compute_evidence_source_structure`,
   `compute_evidence_provenance_continuity`, and
   `compute_evidence_objective_alignment`, each building a `MetricDocument`
   with `availability=ABSENT` when no evidence rows exist and a zero-count
   `PRESENT` document when an enabled ledger is empty.
3. `src/analysis/metric_service.py`:
   - Add `MetricComputationInputs.evidence_rows: object | None = None` and
     `evidence_objective_rows: object | None = None` beside disputes (315-316).
   - Add an `if inputs.evidence_rows is not None:` block beside the dispute
     block (1629-1706) that harvests, windows, derives lineage, summarizes,
     projects layers, and `_safe`-dispatches the three families.
4. `src/experiments/collectors.py`: populate both inputs at 829-849 using
   `getattr(arm.runner_result, "evidence_ledgers", None)` and the same `events`
   value the dispute branch already uses (176-178) with `window_ticks=100`.
   When the ledger field is absent or empty, leave both inputs unset; never
   raise and never fabricate rows. Build `entity_to_agent` exactly as the
   dispute branch does.
5. Update every hard-coded catalog pin. Required files (replace `154` with
   `157` only in the catalog-count assertion; do not change other numbers):
   `tests/architecture/test_dispute_boundaries.py`,
   `tests/architecture/test_formal_rule_boundaries.py`,
   `tests/architecture/test_organization_agency_boundaries.py`,
   `tests/architecture/test_organization_boundaries.py`,
   `tests/architecture/test_organization_operations_boundaries.py`,
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
   `tests/unit/test_dispute_catalog.py`,
   `tests/unit/test_formal_rule_catalog.py`,
   `tests/unit/test_formal_rule_regression.py`,
   `tests/unit/test_generational_cohort_metrics.py`,
   `tests/unit/test_historical_memory_metrics.py`,
   `tests/unit/test_institutional_memory_metrics.py`,
   `tests/unit/test_knowledge_genealogy_metrics.py`,
   `tests/unit/test_macro_society_catalog.py`,
   `tests/unit/test_mediation_invariants.py`,
   `tests/unit/test_mentorship_metrics.py`,
   `tests/unit/test_metric_specifications.py`,
   `tests/unit/test_organization_agency_metrics.py`,
   `tests/unit/test_organization_agency_regression.py`,
   `tests/unit/test_organization_catalog.py`,
   `tests/unit/test_organization_operations_catalog.py`,
   `tests/unit/test_organization_operations_regression.py`,
   `tests/unit/test_possession_succession_metrics.py`,
   `tests/unit/test_public_good_metrics.py`,
   `tests/unit/test_regional_demographics.py`,
   `tests/unit/test_structured_commitments_metrics.py`,
   `tests/unit/test_subjective_value_metrics.py`,
   `tests/unit/test_technique_lifecycle_metrics.py`,
   `tests/unit/test_translation_rows.py`,
   `tests/unit/test_v3_durable_records_regression.py`,
   `tests/unit/test_v3_knowledge_genealogy_regression.py`,
   `tests/unit/test_v3_knowledge_repositories_regression.py`.
   Also update `tests/unit/test_organization_operations_docs.py`'s global
   count assertions and the documentation-string pins in
   `tests/unit/test_dispute_docs.py`, `tests/unit/test_formal_rule_docs.py`,
   `tests/unit/test_organization_docs.py`, and
   `tests/unit/test_organization_operations_docs.py` to 157.
6. Update the current-pin documentation strings to 157 while preserving
   historical statements:
   - `.ai-factory/DESCRIPTION.md`: the current "metric families 154" line only;
     the V4-07 "families 151 → 154" sentence stays.
   - `.ai-factory/ARCHITECTURE.md`: the baseline table row and the current
     "154 metric families" pin; the V4-07 "151 -> 154" sentence stays.
   - `docs/architecture.md`: the two current-pin "154 metric families" lines.
   - `docs/disputes.md`: the current-pin "154 metric families" line; the
     "catalog grows from 151 to 154" sentence stays.
   - `docs/analysis-metrics.md`: the closed catalog cardinality line.
   - Do not edit `.ai-factory/ROADMAP.md`; its 154 references are historical.
7. Update `tests/unit/test_dispute_catalog.py` and
   `tests/unit/test_formal_rule_regression.py` ordering assertions so the last
   six families are the three dispute families followed by the three evidence
   families, and pin the first 154 with a new `FIRST_154_DIGEST` computed from
   the exact tuple material.
8. Create `tests/unit/test_evidence_testimony_catalog.py`:
   - `METRIC_FAMILY_COUNT == 157`, 157 unique families;
   - the three evidence families are last and versioned at 1;
   - the first 154 digest is unchanged;
   - the three value-key tuples are exact;
   - `validate_metric_catalog()` returns 157.
9. Create `tests/unit/test_evidence_testimony_metrics.py` and
   `tests/unit/test_evidence_testimony_metric_service.py`:
   - absent inputs → `ABSENT`;
   - enabled empty ledger → `PRESENT` with zeros;
   - each alignment class increments the matching value;
   - ratio denominators exclude `not_applicable` rows and non-applicable
     custody chains;
   - completed-run assembly emits exactly three evidence documents.
10. `src/analysis/__init__.py`: export the evidence contract, row, detection,
    identity, alignment, layer, and metric entry points and add them to
    `__all__`, mirroring the dispute exports at 184-216. Deep imports must not
    be required by `metric_service`, `experiments`, or tests.

### Required Interfaces and Contracts

- Existing family ids, order, versions, and value keys for the first 154 are
  byte-identical.
- The three new families are analysis-only and never read at runtime.
- `MetricComputationInputs` and collectors accept the new inputs without
  changing dispute, formal-rule, or organization assembly.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; "Versioned Extension
  Contract" requirement 1.
- `src/analysis/specifications.py` 52-53, 229-231, 7205-7207.
- `src/analysis/metric_service.py` 1629-1706; `src/experiments/collectors.py`
  829-849.

### Error Handling and Logging

- A metric computation failure is isolated by `_safe` and does not abort other
  families.
- INFO one line per generated evidence family with availability and coverage
  only; never values, tokens, or ids.

### Tests

- Commands:
  - `uv run pytest tests/unit/test_evidence_testimony_catalog.py tests/unit/test_evidence_testimony_metrics.py tests/unit/test_evidence_testimony_metric_service.py -q`
  - `uv run pytest tests/unit/test_metric_specifications.py tests/unit/test_dispute_catalog.py tests/unit/test_formal_rule_regression.py -q`
  - `uv run pytest tests/architecture -q`

### Acceptance Criteria

- The catalog is exactly 157 with deterministic ordering.
- Real completed-run assembly emits all three documents from actual ledger data.
- No existing family changes.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_catalog.py tests/unit/test_evidence_testimony_metrics.py tests/unit/test_evidence_testimony_metric_service.py tests/unit/test_metric_specifications.py -q`
- Expected: pass; 157 families.

## Phase Risks and Mitigations

- Risk: bulk catalog pin updates miss a module.
  Mitigation: Task 13 enumerates every path from the repository grep and the
  final verification reruns the whole unit + architecture suite.
- Risk: objective alignment becomes a truth oracle.
  Mitigation: closed four-value enum, forbidden result fields, and hard layer
  separation; Task 20 scans for forbidden symbols.
- Risk: windows or candidates allocate unbounded memory.
  Mitigation: 1024-window cap, row caps, and partial coverage notices.

## Phase Completion Checklist

- Every Task 10-13 in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
