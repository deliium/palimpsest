# Phase 3: Narrative, vocabulary and technology continuity

Plan: [index.md](index.md)  
Tasks: 7–9  
Depends on: Tasks 1–4; Task 6 for vocabulary group comparisons

## Objective

Measure cultural forms in their own representations, without renaming generic audit statistics or correcting agents against objective truth.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/analysis/cultural_narrative_metrics.py` | `compute_cultural_narrative_lineage` | Existing final-snapshot persistence does not reliably establish ancestry-specific baseline survival. Keep its historical outputs unchanged. |
| `src/analysis/generational_narratives.py` | `compute_generational_narrative_continuity` | Existing active-lineage continuity is not an unbiased baseline-cohort survival estimate. |
| `src/analysis/semantic_drift_metrics.py` | `SemanticAnalysisInputs`, `compute_semantic_divergence` | Meaning/referent divergence is different from vocabulary inventory divergence. |
| `src/analysis/technique_lifecycle.py` | `classify_technique_lifecycle`, `_entries` | Distinguishes knowledge holders, records and performability. |
| `src/analysis/technique_lifecycle_metrics.py` | `assemble_technique_lifecycle_metrics` | Reuse lifecycle semantics without a new technology tree. |
| `src/experiments/composition.py` | `durable_record_harvest_from_run`, `knowledge_genealogy_harvest_from_run` | Existing detached knowledge/record conversion seam. |

## Files to Change

Create `src/analysis/cultural_narrative_survival.py`, `src/analysis/cultural_vocabulary_differentiation.py`, `src/analysis/cultural_technology_continuity.py`; extend `src/experiments/cultural_evidence.py` with source adapters. Create matching `tests/unit/test_cultural_narrative_survival.py`, `test_cultural_vocabulary_differentiation.py`, `test_cultural_technology_continuity.py`.

## Task 7: Implement baseline-cohort narrative persistence

### Intent

An unrelated surviving story must never stand in for a lost baseline narrative.

### Implementation Steps

1. Implement `compute_cultural_narrative_survival(inputs)`. Baseline consists of active narrative variants at the exact requested baseline boundary, with owner-local identity and exact representation digest. Do not select the first complete or nonempty snapshot. Complete-empty baseline gives count 0 and null retention; missing baseline is unknown. Use the exact requested/resolved end boundary with no nearest-boundary fallback. Separate owner retention from cross-owner lineage continuity.
2. Build ancestry edges only from explicit narrative parent/merge/lineage evidence; qualify every local ID by owner. Shared text/digest alone is not ancestry. Validate acyclicity and temporal direction; missing parent history yields unresolved ancestry.
3. A baseline variant survives at endpoint if the same active variant or a resolved active descendant exists. Branching counts the baseline once. Merging can preserve several baseline ancestors only when the explicit merge edges support each. Unrelated active variants cannot rescue lost roots.
4. Report `endpoint_persistence`, `continuous_persistence`, `baseline_variant_count`, `surviving_baseline_count`, `unresolved_baseline_count`, witnessed generation span and observed duration lower bounds. Use the full baseline denominator; null exact rates if unresolved baseline histories prevent classification, while reporting known counts. Mark left/right censoring and gaps.
5. Cross-owner/multigeneration survival requires explicit lineage evidence and numeric generation mapping; do not use lexical generation sorting or survivor-only cohorts. Do not change the existing narrative metric families' algorithms under `@1`.

### Required Interfaces and Contracts

New family `cultural_narrative_survival@1`. Narrative persistence is representational continuity, never historical accuracy or guaranteed agreement. An admitted child's empty ledger is empty, not inherited ancestral knowledge.

### Requirement Evidence

User: narrative persistence/provenance; existing architecture owner-scoping and blank-slate admission. New-family separation prevents silent correction of legacy reproducibility contracts.

### Error Handling and Logging

Cycles/conflicting parents fail with safe codes; missing ancestors censor, rather than reject otherwise valid evidence. Logs contain lineage and unresolved counts only.

### Tests

Baseline A lost while B survives; A→A1 branch; explicit merge; same digest without ancestry; absent history; dead founder with evidenced receiver descendant; same local IDs owned by different agents; numeric generations 2 and 10; cycle rejection; nonzero predefined baseline, empty/missing baseline and early stop before requested endpoint. Compare known 1/2 survival with hand calculation.

### Acceptance Criteria and Verification

Only supported descendants satisfy survival and every result retains its baseline cohort. Run `uv run pytest tests/unit/test_cultural_narrative_survival.py tests/unit/test_cultural_narrative_metrics.py --cov=analysis --cov-report=term`.

## Task 8: Implement vocabulary inventory divergence

### Intent

Quantify different vocabularies separately from different meanings assigned to a shared term.

### Implementation Steps

1. Implement `compute_cultural_vocabulary_differentiation(inputs)`. Adapt naming ledgers into owner/label-token inventory rows using the existing active status semantics; retired and merged aliases do not count twice. Do not parse location names or generated labels into supposed meaning.
2. Aggregate deduplicated owner-label carrier incidences by explicit group/boundary. Compute pairwise JS divergence over label inventory distributions, Jaccard vocabulary distance between group label sets, richness, shared-label count and union size.
3. Reuse Task 6's membership/cohort policy for temporal deltas. A known empty versus nonempty vocabulary has set distance 1; both-empty set distance is null with `empty_union`. JS remains null whenever either distribution lacks mass.
4. Keep existing semantic-referent divergence untouched; document that homonyms may produce low vocabulary distance and high meaning divergence, while synonyms may produce the opposite. Outputs must label the representation `label_inventory`.

### Required Interfaces and Contracts

New family `cultural_vocabulary_differentiation@1`, vocabulary dimension only. Unknown naming channel is absent, not zero divergence. Owner evidence pointers resolve each counted label binding/status revision.

### Requirement Evidence

User: vocabulary divergence; existing `LabelBinding` contract and semantic-drift separation. Verify known-empty, disabled and homonym/synonym combinations.

### Error Handling and Logging

Unknown status or conflicting binding versions fails safely. Missing inventory or memberships produces unavailable rows. Metadata counts only.

### Tests

Identical/disjoint/overlapping label sets; repeated bindings; retired/merged aliases; same label/different referent; different label/same referent; absent versus empty naming; membership churn excluded. Reordering must preserve canonical output.

### Acceptance Criteria and Verification

Vocabulary and meaning divergence are observably distinct and correctly labeled. Run `uv run pytest tests/unit/test_cultural_vocabulary_differentiation.py --cov=analysis --cov-report=term`.

## Task 9: Implement technology retention and loss

### Intent

Separate living practical knowledge, archival preservation and objective ability to perform a technique.

### Implementation Steps

1. Implement `compute_cultural_technology_continuity(inputs)`. At the exact requested baseline collect distinct practical content keys supported by active living-owner entries. Never silently shift an empty/missing baseline. Complete-empty baseline yields count 0 and null retention; missing baseline or requested endpoint yields unknown retention. Keep exact variant digests alongside the key; do not use skill level or `feature:production_technique` audit tokens as substitutes.
2. Living retention is baseline keys with at least one active living holder at endpoint / baseline keys. Exact-variant retention uses baseline variant digests separately. Per-generation retention uses witnessed holders in that numeric generation, not an assumed parent→child transfer.
3. Living loss is a complete positive→zero living-holder transition with a nonempty eligible population. Archive states are independent: `preserved`, `absent`, or `unknown`, based on intact linked record evidence at that boundary. Global loss is reportable only with complete living and complete relevant archival coverage and no living holder or intact linked record. Otherwise publish living loss and unknown global loss.
4. Reuse technique-lifecycle semantics for record integrity, known holders and resource/capability limitations. Unavailable materials or a failed production action do not imply forgotten knowledge. Provide `not_performable` separately only when existing lifecycle evidence proves it.
5. Use `durable_record_harvest_from_run` and effect-complete committed record events to construct boundary archive states where possible. If only endpoint records exist, earlier archive states stay unknown. Validate record→technique links; an unrelated intact record does not rescue a technique.
6. Reappearance is a new living episode; label it rediscovery only when the existing knowledge origin/provenance supports independent discovery. Preserve holder, record, lineage and loss-transition evidence pointers.

### Required Interfaces and Contracts

New family `cultural_technology_continuity@1`. Publish baseline count, living/key/variant retention, living-loss count/share, archive-preserved count, global-loss count/share and excluded-unknown counts separately. Empty baseline yields null retention, not perfect retention. No technology tree or registry, capability ownership, event or schema change.

### Requirement Evidence

User: technology retention/loss; architecture distinguishes physical records, practical knowledge and objective capabilities. Test living-off/archive-on and living-on/materials-off explicitly.

### Error Handling and Logging

Invalid record links fail structural validation. Incomplete archive history censors global loss rather than inventing records. Logs contain counts/reason codes only.

### Tests

Living holder survives; holder dies but intact linked record survives; both disappear; unknown record inventory; record unrelated; damaged record; no materials while knowledge persists; variant mutates but content key retained; knowledge passes to a later-generation nonkin owner; empty/missing baseline; predefined nonzero baseline after acquisition; early stop before requested endpoint.

### Acceptance Criteria and Verification

Living loss never becomes global loss without archival evidence, and physical nonperformability is never knowledge loss. Run `uv run pytest tests/unit/test_cultural_technology_continuity.py --cov=analysis --cov-report=term`.

## Phase Risks and Mitigations

- Bounded histories omit ancestors: publish unresolved ancestry and censor rather than matching text.
- Record survival and cognition differ: retain two channels and independent denominators.
- Existing legacy formulas have limitations: introduce versioned new families and document differences; unrelated legacy bug fixes are out of scope.

## Phase Completion Checklist

Tasks 7–9 satisfy acceptance criteria and verification; progress lives only in `index.md`.
