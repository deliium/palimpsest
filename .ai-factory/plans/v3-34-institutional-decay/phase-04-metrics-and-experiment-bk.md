# Phase 4: Metrics and Experiment BK

Plan: [index.md](index.md)
Tasks: 10–12
Depends on: Tasks 7–9

## Objective

Publish scientifically bounded decay/lifecycle/lineage metrics and reproducible opportunity treatments, without scripting institutions to stabilize or collapse.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `src/analysis/specifications.py` | `MetricFamilyId`, `_spec_institutional_memory_*`, `METRIC_FAMILY_COUNT = 126` | Closed versioned catalog/spec registration. |
| `src/analysis/metric_service.py` | `MetricComputationInputs`, institution/office/memory assembly | Central ordered metric document assembly and absent-input behavior. |
| `src/analysis/models.py` | `MetricDocument.__post_init__` near 677–695 | Metric values accept scalars only, not nested lists/maps. |
| `src/analysis/serialization.py` | `_encode_values`, `_decode_values`, `encode_metric_document` | Existing wire codec preserves scalar/string values; do not widen it for one feature. |
| `src/experiments/collectors.py` | `assemble_arm_metric_bundle`, memory collection near 715 | Completed-run exports flow into detached metrics. |
| `src/experiments/institutional_memory_scenario.py` | `institutional_memory_scenario`, `assert_institutional_memory_structure` | BJ opportunity arms and structural-only arbiter. |
| `src/experiments/catalog.py` | BJ catalog wrapper | Off-V1-gate registration pattern. |
| `tests/unit/test_experiment_bj.py` | completed-result collection and real teaching/learning case | Existing representative end-to-end research path. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/institutional_decay_metrics.py` | create | Three new metric document assemblers. |
| `src/analysis/specifications.py` | modify | Families/specs/version/coverage definitions; count 129. |
| `src/analysis/metric_service.py` | modify | New detached inputs and ordered assembly. |
| `src/analysis/__init__.py` | modify | Public metric contracts. |
| `src/experiments/collectors.py` | modify | Collect temporal exports, context and lineage safely. |
| `src/experiments/composition.py` | modify | Compose new metric inputs from completed-run evidence. |
| `src/experiments/institutional_decay_scenario.py` | create | BK opportunity experiment and structural arbiter. |
| `src/experiments/catalog.py` | modify | `institutional_decay@1` registration, off V1 gate. |
| `src/experiments/__init__.py` | modify | Explicit scenario exports. |
| `tests/unit/test_institutional_decay_metrics.py` | create | Availability, denominators, serialization and count pins. |
| `tests/unit/test_experiment_bk.py` | create | Arms, reproducibility and collection. |
| `tests/unit/test_metric_specifications.py` | modify | Add new pinned family specs/count expectations. |

## Task 10: Register three versioned metric families

### Intent

Report requested dimensions and outcomes with honest evidence denominators, not an institution-health score or unsupported causal probabilities.

### Implementation Steps

1. Add families `institutional_decay@1`, `institution_lifecycle@1`, `institution_lineage@1` to `MetricFamilyId`/spec builders. Raise the current family count **126 → 129**; preserve historical family versions and values. Add specs to the registered ordered factory list and update only current catalog-count tests.
   Existing current-count assertions to update (only `METRIC_FAMILY_COUNT` / current catalog length expectations, not phenomenon semantics) are in `tests/unit/test_metric_specifications.py`, `test_institutional_memory_metrics.py`, `test_knowledge_genealogy_metrics.py`, `test_subjective_value_metrics.py`, `test_historical_memory_metrics.py`, `test_technique_lifecycle_metrics.py`, `test_dependency_care_metrics.py`, `test_developmental_learning_metrics.py`, `test_cultural_feature_metrics.py`, `test_mentorship_metrics.py`, `test_possession_succession_metrics.py`, `test_collective_project_metrics.py`, `test_bounded_experiment_metrics.py`, `test_structured_commitments_metrics.py`, `test_cultural_narrative_metrics.py`, `test_public_good_metrics.py`, `test_translation_rows.py`, `test_regional_demographics.py`, `test_v3_knowledge_genealogy_regression.py`, `test_v3_durable_records_regression.py`, `test_v3_knowledge_repositories_regression.py`, and `test_mediation_invariants.py` (all bare filenames in this sentence are under `tests/unit/`). Include those assertion-only edits in this task's file set.
2. `institutional_decay@1`: five separate dimension trajectories/counts/ratios, comparable-cohort window deltas, legitimacy-strength trajectory, nonexclusive mechanism association counts, observed-cohort/unknown/disabled/not-applicable/pruned denominators, and coverage intervals. Compute these once from Task 7's raw-set windows, not by averaging rolling ratios. Do not average five dimensions into a health scalar or assert mechanism causation.
3. `institution_lifecycle@1`: scoped emerging/stable/weakening/collapsed counts, transitions with confirmation and last-active ticks, observed episode durations, right-censoring/coverage termination counts, and recovery observations. Denominators include prior-stable eligible episodes for collapse, not all agents or all candidates. No event-free run must invent a collapse rate denominator; encode unavailable or zero with a real nonzero denominator appropriately.
4. `institution_lineage@1`: confirmed transformed/split/reappeared edges, root/episode counts, separate continued-edge count, parent/child continuity panels, actual versus declared-only knowledge transfer paths, ambiguity/unresolved/pruning counts, and a deterministic graph bounded by retained input/witness history. Distinguish observed episodes from identity-only pruned stubs; neither a stub nor a continued edge inflates confirmed transform/split/reappearance counts. No arbitrary clipping without coverage metadata.
5. Implement assemblers in `institutional_decay_metrics.py` using existing `MetricDocument`, coverage, provenance, numerical quantization and specification fingerprint patterns. Pin policy/threshold versions and input revision. `MetricDocument.values` is **scalar-only**. Use the exact structured-output string contract below; never insert a list/map/dataclass into values, broaden `MetricDocument`, or widen the common metric wire schema. `None` input is absent; enabled empty is observable no-pattern/no-transition evidence, not a disabled channel; all-pruned is partial/unavailable.

### Scalar Metric and Structured Research Output Contract

Keep counts, finite quantized ratios, availability flags and policy identifiers as ordinary scalar metric values. Preserve detailed research data in canonical JSON **strings**, using these exact keys and inner schema identifiers:

| Family | String key | Inner `schema_version` and contents |
|---|---|---|
| `institutional_decay@1` | `dimension_trajectories_json` | `institution-dimension-trajectories-v1`: five named dimension panels, per-window numerator/denominator/availability, cohort exclusions, observation/source intervals and legitimacy trajectory. |
| `institutional_decay@1` | `mechanism_evidence_json` | `institution-mechanism-evidence-v1`: nonexclusive association panels, evidence class/interval and exclusion counts; no causal-effect estimate. |
| `institution_lifecycle@1` | `episodes_json` | `institution-lifecycle-episodes-v1`: scoped episode IDs, states/transitions, activity/confirmation ticks, censoring and threshold policy. |
| `institution_lineage@1` | `lineage_graph_json` | `institution-lineage-graph-v1`: stable observed nodes, explicit pruned predecessor stubs, canonical edges with method/confidence/confirmation evidence, and retained-history coverage. |

Implement serialization helpers in the **new feature metrics module**, not the shared codec. Serialize primitive projections with `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)` after applying the existing quantization policy. Sort arrays by stable node/edge IDs or `(owner, pattern, window_end, dimension)` as appropriate; canonicalize set-derived members before encoding. Inner payloads include `as_of_tick`, `input_revision` and coverage/pruning metadata. Empty enabled payloads use valid schema-tagged empty arrays; absent input uses `None` rather than a fabricated empty complete history. These strings are research payloads and must never be logged or consumed by cognition. No new API, filesystem export service or wire-result field is introduced.

### Required Interfaces and Contracts

Analysis data never enters cognition. Family count 129 is the only closed catalog-count change. Commands 43, observer semantic types 73, latest selected replay V22/codec v20 and Alembic 0017 stay unchanged. The graph is research output, not an observer protocol extension or an authority registry.

### Requirement Evidence

User tracking/outcomes/lineage; architecture metric/version/reproducibility boundaries; existing institutional memory metric availability/provenance pattern.

### Error Handling and Logging

Malformed source results fail closed with codes. Valid absent/partial evidence yields appropriately marked documents. Log family/version/input-count/availability only; graph/evidence payloads are not logged.

### Tests

`test_institutional_decay_metrics.py`: all families/fingerprints; known-answer support `2/3`, participation `2/3`, repetition `3/4`, succession `1/2`, knowledge `2/3` from raw evidence, not substitute counts or twice-smoothed ratios; quantized finite numbers; absent/disabled/empty/pruned; no unsupported causal rate; high-water truncation; observed graph nodes versus pruned stubs; deterministic inner JSON and outer metric bytes; catalog count 129. For every family call actual `encode_metric_document` and `decode_metric_document`, parse each JSON-string value with `json.loads`, assert its exact inner schema/IDs/coverage and roundtrip equality, and prove a nested map/list remains invalid in the shared `MetricDocument`/codec. Extend specification tests with exact string keys, units/population/exclusions and unchanged legacy specs.

### Acceptance Criteria

Three discoverable versioned families encode all five dimensions, all six outcomes and lineage with source coverage. No new scalar, invented denominator or world identity.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_metrics.py tests/unit/test_metric_specifications.py tests/unit/test_institutional_memory_metrics.py -q`

Expected: new family specs and unchanged legacy family metrics pass.

## Task 11: Integrate completed-run collection

### Intent

Ensure metrics consume the real runtime history and optional existing evidence rather than only hand-built analysis fixtures.

### Implementation Steps

1. Add optional detached temporal/context inputs to `MetricComputationInputs` (not cognition ledger types). Validate raw input states and call window aggregation, lifecycle, lineage, then metric assembly once in that order after existing institution/memory assembly. Reuse the same window/lifecycle results for all three families; do not recompute a rolling window over another family's ratios. Build lineage from the same high-water-bounded rows and retained absolute witnesses, not a separate inferred history.
2. In `assemble_arm_metric_bundle`, inspect the assignment's enabled decay owners and completed result exports. Decay off → no fabricated sample input; enabled zero-pattern owners → explicit empty covered input with expected-owner count. Preserve `None` versus empty semantics even when the result's default tuple is empty. A missing enabled owner export is partial/error evidence, not a zero-support institution.
3. Compose via Task 7 adapters; join existing final office/memory exports only where their retained intervals/provenance justify it. Do not use the final ledger state to fill historical gaps. Bound objective event context by completed run/evidence high-water and use known initial plus admitted owner identities.
4. Verify legacy collectors still return their prior family values (aside from the addition of the three new absent/available documents under the existing catalog convention). Run the real scalar metric codec on collected new documents, preserving structured data as the specified JSON strings through encode/decode. Do not change BF/BG/BJ arms, shared metric value types or unrelated collector grouping.

### Required Interfaces and Contracts

`simulation` imports no analysis/experiments code. `analysis` imports no cognition. Adapters reside in experiments; simulation exports only its own detached in-process state. Historical versioned result JSON is not widened to persist these snapshots automatically.

### Requirement Evidence

Architecture dependency allowlists; user reproducible tracking requirement; representative BJ collection pattern. Count changes are additive, old classifications remain versioned and unchanged.

### Error Handling and Logging

Reject contradictory typed rows or future event joins; report missing enabled owner/snapshot history as partial coverage. INFO collector completion logs counts/availability, never source payloads.

### Tests

Extend `test_institutional_decay_composition.py` and `test_institutional_decay_metrics.py`: actual completed runner result → raw projection → one window aggregation → three metric documents → canonical outer encode/decode → parsed inner JSON with unchanged node IDs/values; mixed/admitted owners; disabled versus enabled-empty; missing exports; lost history/pruned stubs; unchanged BF/BJ family values and shared metric schema; no final-state interpolation; equal as-of classification from a prefix and equivalent retained evidence at the same high-water (incomparable pruned histories must instead disclose their coverage difference).

### Acceptance Criteria

Real completed-run evidence reaches all three families; legacy metrics are not silently reinterpreted and absent evidence remains explicit.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_composition.py tests/unit/test_institutional_decay_metrics.py tests/unit/test_experiment_bj.py -q`

Expected: completed-run collection and representative existing BJ cases pass.

## Task 12: Add non-scripted Experiment BK

### Intent

Compare renewal/weakening opportunities without a scheduled collapse, fabricated institution, seeded institution ledger, or success criterion that forces an outcome.

### Implementation Steps

1. Create `institutional_decay_scenario(seed=23, max_ticks=32, seed_matrix=None, base=None)`, `experiment_bk_institutional_decay(...)`, and `assert_institutional_decay_structure(...)`. Follow BJ's factory/catalog/export pattern and derive reference opportunities from `institutionalization_scenario`/BJ composition, not copied runtime ledgers.
2. Register `institutional_decay@1` as Experiment BK off the V1 A–E gate. Use six fixed arms: `bk-baseline` (unchanged BF baseline); `bk-decay-off` (v53 memory/office/concept composition); `bk-decay-on` (identical config except v54 + decay mode); `bk-record-opportunities` (BJ's record-reading/empty learner opportunities plus decay); `bk-teaching-opportunities` (BJ teaching opportunities plus decay); `bk-limited-opportunities` (BJ limited opportunities plus decay). Preserve native root siblings and same-owner prerequisites through Task 2 validators.
3. Pair off/on seeds, initial world, agents, objective lifecycle/resources and stochastic identity. Opportunity arms may change only declared existing opportunities (artifacts, repositories, teaching/mentorship); emit explicit treatment labels. Off/on behavior may differ after enabling attrition, so compare reproducibility within treatment, not falsely assert identical treatment trajectories.
4. Do not schedule deaths, resource shocks, office abandonment, record destruction, competing institutions, cultural change or a "collapse tick". Existing physiology/lifecycle/environment/agent choices may produce such evidence naturally. Synthetic ordered evidence in analysis tests proves rare classification outcomes; experiment acceptance does not demand all outcomes occur for seed 23.
5. Structural arbiter checks owners, empty initial decay/knowledge content, mode/schema consistency, bounded ordered samples/receipts, safe lineage IDs and coverage flags. It must not assert that any institution emerged, collapsed, split or recovered. Existing newborn profiles remain decay-disabled; report admitted owner mode/coverage honestly instead of assuming inherited cognition.
6. Run repeated small-seed completed experiments and collect all three families. Include a representative configured record/teaching opportunity arm so the end-to-end path exercises real artifacts/delivery and existing institutional memory, not only synthetic rows.

### Required Interfaces and Contracts

No new capability flag, command, event, API route, observer semantic, persistence migration, species profile or predefined institution type. Default max_ticks 32 permits evidence windows but guarantees no social outcome. Standard reproducibility settings and network-free fakes remain in force.

### Requirement Evidence

User prohibition on scripting collapse; existing BJ opportunity-only arms and structural arbiter; M7 no scripted civilization outcomes.

### Error Handling and Logging

Reject incompatible base configs with existing safe validation, not silent stripping of feature settings. INFO experiment ID/arm count/tick cap/agent count; no payloads. Empty results are valid research outcomes, not errors to be patched with scripts.

### Tests

`test_experiment_bk.py`: exact arms/schema/mode/prerequisites; off/on world/seed equality; empty initial state; unchanged BJ definition; no collapse schedule or scripted command plan; repeatability for at least two seeds at small tick caps; structural arbiter accepts zero-collapse runs; completed collection/fingerprints; real record/teaching opportunity path; off-gate registration. Test feature demonstrations with controlled agent choices separately from the opportunity experiment, never label them spontaneous population-wide collapse.

### Acceptance Criteria

BK is reproducible, catalogued and scientifically neutral about outcomes. All tracked channels and new documents are reachable through real completed experiments.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bk.py tests/unit/test_experiment_bj.py tests/unit/test_institutional_decay_composition.py -q`

Expected: structural/reproducibility/collector cases pass without live services.

## Phase Risks and Mitigations

- A short deterministic experiment may never form/collapse an institution: accept null outcomes and prove classifiers with explicit evidence fixtures.
- Final ledgers hide temporal gaps: collect retained samples only and propagate expected-owner/coverage metadata.
- Catalog count updates can accidentally rewrite legacy specifications: add three specs and update only current-count pins.

## Phase Completion Checklist

- Tasks 10–12 meet their acceptance criteria and all commands pass.
- Update only `index.md` task progress after verification.
