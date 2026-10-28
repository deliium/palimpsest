# Phase 5: Coordination, regional contact and language

Plan: [index.md](index.md)
Tasks: 10–11
Depends on: Tasks 1–9

## Objective

Implement scenarios 16–23 with physical coordination and real contact boundaries. Distinguish labels, meanings, transmission and analytical society candidates.

## Current-Code Evidence

| Path | Symbols / cases | Why it matters |
| --- | --- | --- |
| `src/experiments/catalog.py` | `experiment_aw_collective_projects`, `experiment_ax_public_goods` | Objective contributions and benefits, not leadership or moral roles |
| `src/experiments/regional_migration_scenario.py` | `regional_migration_scenario`, `regional_migration_arbiter` | Journeys and route-evidence treatments |
| `src/experiments/multiple_societies_scenario.py`, `src/experiments/cultural_contact_scenario.py` | scenario/arbiter builders | Isolation versus contact, detached candidate communities |
| `src/experiments/symbolic_language_scenario.py`, `src/experiments/semantic_drift_scenario.py`, `src/experiments/translation_scenario.py` | scenario/arbiter builders | Owner-local symbolic, sense-history and translation evidence |
| `tests/unit/test_regional_cross_feature_invariants.py` | arrival benefits and every-prefix replay | Cross-feature integration oracle |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/civilization_benchmark_coordination.py` | create | Cases 16–17 |
| `src/experiments/civilization_benchmark_regions.py` | create | Cases 18–20 |
| `src/experiments/civilization_benchmark_language.py` | create | Cases 21–23 |
| `src/experiments/civilization_benchmark_suite.py` | modify | Register recipes/selectors |
| `tests/unit/test_v3_benchmark_coordination.py`, `tests/unit/test_v3_benchmark_regions.py`, `tests/unit/test_v3_benchmark_language.py` | create | Actual physical/contact and owner-evidence tests |

## Task 10: Exercise collective work, public goods, migration and re-contact

### Intent

Make coordination and co-presence opportunities observable without installing a leader, public-good virtue, political society or shared culture.

### Implementation Steps

1. Compose project/public-good physical specs, materials and ordinary commands. Controlled schedules may start/contribute/maintain/use a project, but do not preseed skill ledgers (some existing isolated command tests do). Acquire any required skill through ordinary experience first; failures remain visible.
2. Build two initially disconnected or route-blocked regions using `RegionsMigrationSpec`, named routes and exact spawn mapping. For isolation windows, no valid route/contact/delivery joins the populations. For contact treatment, enable the declared route opportunity and use ordinary WorldEngine journey commands, with applied start/arrival events and capacity/death cancellation checks.
3. Inspect knowledge inventories before and after actual contact/delivery. Global analytical similarity never becomes an exposure channel. Re-contact does not clone ledgers or synchronize beliefs; recipient acquisition must have a local source.
4. Measure detached society/culture/community classifiers and contact/project/public-good metrics with exact windows and eligible denominators. Do not label an individual a permanent free rider or infer polity membership from region placement.

### Required Interfaces and Contracts

| # / suffix | Required controlled evidence | Autonomous output / control |
| --- | --- | --- |
| 16 `collective-project` | Applied start and contributions by at least two eligible owners, actual progress/material changes; shortage/rejection control | Coordination and completion/failure; project opportunities off/on |
| 17 `public-good-patterns` | Contributions and benefits recorded independently; eligible noncontributor can benefit when rules permit | Contribution/benefit/free-riding episode patterns and uncertainty; upkeep/cost contrast, no moral identities |
| 18 `regional-migration` | Journey start, pending state, arrival or valid cancellation via engine; no coordinate teleport | Migration counts/outcomes; route evidence absent/present |
| 19 `isolated-divergence` | Separate exposure histories, zero cross-region delivery during isolation; independent owner roots | Cultural divergence with actual inventories/coverage; isolated versus connected opportunity, no required divergence |
| 20 `recontact-exchange` | Valid journey followed by actual communication/teaching/trade, new owner-local uptake only after exposure | Exchange/retention/convergence or nonconvergence; continued isolation versus reopened contact |

Repeated exposure/teaching and exchange use existing commands/relations; no synthetic `Teach` action. Preserve command/event counts and observer semantics.

### Requirement Evidence

Original Request scenarios 16–20; `docs/architecture.md` — regional migration contract; `docs/configuration.md` — exact regional spec; `tests/unit/test_regional_travel_lifecycle.py`.

### Error Handling and Logging

Invalid route, full arrival location, dead traveller and missing material produce normal rejected/cancelled outcomes; no fallback teleport or forced contribution. Required applied-action absence fails fixture coverage. Safe logs contain counts, IDs and reason codes, not dialogue or cultural values.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_coordination.py tests/unit/test_v3_benchmark_regions.py tests/unit/test_regional_travel_replay.py tests/unit/test_regional_cross_feature_invariants.py -q`.

Test actual multi-owner contribution, noncontributor benefit, project failure, route rejection/cancellation, no knowledge flow while isolated, post-contact fresh uptake and continued disagreement. Compare altered presentation layouts with identical objective results.

### Acceptance Criteria

Cases 16–20 prove ordinary action/contact mechanisms. Candidate groups/divergence/free-riding may remain undetected without invalidating the research run.

## Task 11: Exercise vocabulary divergence, semantic drift and mistranslation

### Intent

Symbolic resemblance is not semantic identity, and translation confidence is not ground truth.

### Implementation Steps

1. Compose deterministic naming plus symbolic language for cases 21–22 and translation for 23. Use the explicit new empty learner pack where descendant modes are required. Do not transfer a founder vocabulary or mutate a label ledger directly.
2. Use bounded actual `Talk`/`Ask`/`Tell` relations following existing symbolic/translation arbiter formats, including the existing `call` relation pattern. Present repeated local referents/contexts and later co-presence; all relation content and setup schedules are versioned recipe inputs.
3. Record retained owner sense history and source witnesses before/after cohort turnover. Compute semantic stability/drift/divergence and translation metrics through existing analysis composition. Label changes without sense evidence do not count as semantic drift.
4. For controlled mistranslation, supply genuinely ambiguous/conflicting valid-channel examples, not an injected incorrect mapping. Assert that uncertainty/conflicting hypotheses remain representable and later evidence can revise them. Positive wrong-mapping detection is also tested on explicitly synthetic detached policy fixtures; do not count those as autonomous errors.

### Required Interfaces and Contracts

| # / suffix | Mechanism check | Research output / comparison |
| --- | --- | --- |
| 21 `vocabulary-divergence` | Independent owner vocabularies from local exposure; symbol histories and roots do not collapse across regions | Symbol/form differentiation; isolated versus connected exposure |
| 22 `generational-semantic-drift` | Actual entrant learning, retained sense revisions and time/cohort-qualified source evidence | Semantic change/persistence and divergence, not just spelling; stable versus changing valid context |
| 23 `cross-cultural-mistranslation` | Translation hypothesis derives from addressed/co-present evidence; ambiguous/incorrect/revised mappings remain subjective | Translation error/uncertainty/revision rates; naming-only versus translation-enabled arms |

No world dictionary, shared language pack or truth correction is created. Detached analytical alignment may compare referents after the run but never feeds prompts/cognition.

### Requirement Evidence

Original Request scenarios 21–23 and no magical knowledge sharing; `.ai-factory/ARCHITECTURE.md` — symbolic, semantic and translation seams.

### Error Handling and Logging

Missing sense history yields partial/unknown drift, not stability; no contact evidence means no justified translation uptake. Reject foreign-owner lineage or unsupported relation shape. Log history/ambiguity counts only, never labels, utterances or relation payloads.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_language.py tests/unit/test_v3_benchmark_newborn_profile.py -q`.

Test isolated equal-form/different-root words, spelling-only versus sense change, descendant acquisition without copied content, retained-history truncation, ambiguous mappings, valid revision and missing evidence. Policy fixtures test false-positive/negative detection separately from real execution.

### Acceptance Criteria

Cases 21–23 expose measurable semantics and uncertainty without asserting that languages must diverge or translation must fail.

## Phase Risks and Mitigations

- Disconnected layouts are an intentional treatment, not a single-factor policy-only pair: label comparison provenance exactly.
- A region can contain multiple analytical groups: never use region ID as a cultural membership truth label.

## Phase Completion Checklist

- Verify Tasks 10–11; update index only.
- Keep source histories and missing-coverage semantics intact.
