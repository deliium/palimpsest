# Phase 3: Generational cohort analysis

Plan: [index.md](index.md)
Tasks: 8-9
Depends on: Phase 1 / Task 1; v55 result contract

## Objective

Add one detached, analysis-only metric family that turns finalized `PopulationProgress` into comparable generation/cohort counts and survival shares, then wire it through metric assembly and experiment collectors without changing any runtime authority.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/generational_models.py` | `CohortPopulationRow` (184), `GenerationPopulationRow` (230), `PopulationProgress` (262) | Objective source rows and consistency invariants already enforced. |
| `src/simulation/runner_models.py` | `SimulationRunnerResult.generational_progress` (6298-6300) | Result field available to collectors. |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` (53), `MetricFamilyId` (75), `_spec_regional_population` (4020), `_BUILDERS` (5777), `validate_metric_catalog` (5928) | Family registration, dynamic scalar keys, count pin. |
| `src/analysis/metric_service.py` | `MetricComputationInputs` (207), `_NON_CATALOG_FAMILIES` (191), optional blocks (1160+), `_safe` (399) | Input slice and assembly pattern. |
| `src/analysis/regional_population.py` | `compute_regional_population` (573), dynamic `region:<id>:...` keys (622-642) | Existing precedent for dynamic scalar keys. |
| `src/analysis/dependency_care_metrics.py` | `compute_dependency_survival` (92), `_document` helper pattern | MetricDocument construction and availability semantics. |
| `src/experiments/metric_collection.py` | `inputs_with_opt_in_metric_rows` (225) | Optional evidence attachment. |
| `src/experiments/collectors.py` | `assemble_arm_metric_bundle` (105), `generation_index_from_lifecycle_records` (84) | Per-arm assembly and existing generational map. |
| `src/analysis/matrix_metric_summary.py` | `build_matrix_metric_summary` (73) | Cross-condition/role distribution summary; no new paired layer. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/generational_cohort.py` | create | Compute the new metric from `PopulationProgress`. |
| `src/analysis/__init__.py` | modify | Export the metric function/version and add them to `__all__`. |
| `src/analysis/specifications.py` | modify | Register `generational_cohort_comparison@1`, add spec/builder, bump count to 130. |
| `src/analysis/metric_service.py` | modify | Add the input field, optional block, and safe assembly. |
| `src/experiments/metric_collection.py` | modify | Accept and attach `generational_progress`. |
| `src/experiments/collectors.py` | modify | Pass `runner_result.generational_progress` into metric inputs. |
| `tests/unit/test_generational_cohort_metrics.py` | create | Computation/availability/zero/serialization tests. |
| `tests/unit/test_generational_cohort_collectors.py` | create | Assembly and collector integration tests. |

## Task 8: Add the generational cohort comparison metric family

### Intent

Expose objective generation and cohort outcomes from the already-finalized population progress. The family is descriptive, not causal, and must not infer age, kinship, community, or institutional meaning.

### Implementation Steps

1. Create `src/analysis/generational_cohort.py` with module logger `analysis.generational_cohort` and constant:
   - `GENERATIONAL_COHORT_COMPARISON_METRIC_VERSION: Final[str] = "generational_cohort_comparison@1"`.
2. Implement:

```python
def compute_generational_cohort_comparison(
    progress: PopulationProgress,
    *,
    run_id: str,
    input_revision: str,
    window_end: int,
) -> MetricDocument: ...
```

3. Validate `type(progress) is PopulationProgress`, `run_id`/`input_revision` as stable ids, and non-negative exact `window_end`.
4. Resolve `spec = metric_specification(MetricFamilyId.GENERATIONAL_COHORT_COMPARISON)` and verify `spec.version_identifier == GENERATIONAL_COHORT_COMPARISON_METRIC_VERSION`; otherwise raise `ValueError("unsupported_metric_version")`.
5. Build values in deterministic order:
   - `"layer": "generational"`.
   - `"boundary_tick": progress.boundary_tick`.
   - `"admitted_total": progress.total_admitted`.
   - `"living_total": progress.living_population`.
   - `"dead_total": progress.total_deaths`.
   - `"max_generation_index": progress.max_generation_index_seen`.
   - `"generation_count": len(progress.generations)`.
   - `"cohort_count": len(progress.cohorts)`.
   - `"generation_span_ticks": max(entry_ticks) - min(entry_ticks)` over cohorts, or `0` when fewer than two cohorts.
   - `"post_founder_admitted_share": quantize_float(sum(admitted for gen>0) / total_admitted)` when `total_admitted > 0`, else `0.0`.
   - `"founder_living_share": quantize_float(living_gen0 / living_total)` when `living_total > 0`, else `0.0`.
   - `"cohort_generation_alignment_violations":` count of cohort rows whose `generation_index` is absent from the generation rows or whose cohort totals cannot be attributed to the same generation total; expected `0`. Implement as an explicit check against the generation row map, not a second population fold.
6. Add dynamic generation keys for every generation row, sorted by `generation_index`:
   - `f"generation:{n}:admitted"`
   - `f"generation:{n}:living"`
   - `f"generation:{n}:dead"`
   - `f"generation:{n}:survival_rate"` = `quantize_float(living / admitted)` when admitted > 0 else `0.0`.
7. Add dynamic cohort keys for every cohort row, sorted by `(generation_index, entry_tick, cohort_id)`:
   - `f"cohort:{id}:generation_index"`
   - `f"cohort:{id}:entry_tick"`
   - `f"cohort:{id}:admitted"`
   - `f"cohort:{id}:living"`
   - `f"cohort:{id}:dead"`
   - `f"cohort:{id}:survival_rate"` = `quantize_float(living / admitted)` when admitted > 0 else `0.0`.
8. Build a `MetricDocument` with:
   - `schema_version=METRIC_DOCUMENT_SCHEMA_VERSION`;
   - `metric_family=MetricFamilyId.GENERATIONAL_COHORT_COMPARISON.value`;
   - `algorithm_version=spec.algorithm_version`;
   - `library_versions=library_versions()`;
   - `evidence_stages=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE})`;
   - `population=spec.population`;
   - `denominator=spec.denominator`;
   - `coverage=MetricCoverage(observed=len(progress.cohorts) + len(progress.generations), expected=same, ratio=1.0)`;
   - `availability=MetricAvailability.PRESENT`;
   - `provenance=MetricProvenance(source_kind="population_progress", source_ids=(run_id,), notes_code="ok")`.
9. The empty case (`PopulationProgress` with zero generations/cohorts) is still present: totals are zeros, counts are zero, shares are `0.0`, and dynamic keys are absent. Do not emit `ABSENT` merely because the population is extinct or empty. A missing `PopulationProgress` is represented by omitting the family at the metric-service layer, not by inventing a document here.
10. Log `DEBUG generational_cohort_comparison_complete run_id=... generation_count=... cohort_count=... boundary_tick=...` and `INFO` only at the caller's aggregation boundary if needed. Never log survivor ids.

### Specification Registration

In `src/analysis/specifications.py`:

1. Add `GENERATIONAL_COHORT_COMPARISON = "generational_cohort_comparison"` to `MetricFamilyId`.
2. Add `_spec_generational_cohort_comparison()` returning `_base(...)` with:
   - `evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE})`;
   - `population="finalized_generational_population_progress"`;
   - `denominator="admitted_agents_and_completed_generation_boundary"`;
   - `denominator_kind=DenominatorKind.POPULATION_SIZE`;
   - `cohort_window="final completed boundary of a generational run"`;
   - `deceased_policy="dead remain in admitted/dead totals; living counts exclude them"`;
   - `zero_holding_policy="zero population is a present zero, not absent evidence"`;
   - `opportunity_vs_occurrence="admitted cohorts are occurrences; counts are censuses at finalization"`;
   - `self_edge_policy="not_applicable"`;
   - `censoring_policy="no mid-run extrapolation; uses finalized progress only"`;
   - formulas and the static `value_keys` list from steps 5-6 (dynamic `generation:`/`cohort:` keys are runtime keys, not spec entries, following `regional_population@1`);
   - `empty_case="present zero totals when progress exists; family omitted when progress absent"`;
   - `unknown_case="missing progress omits the family; never fabricate counts"`.
3. Append `_spec_generational_cohort_comparison` to `_BUILDERS`.
4. Bump `METRIC_FAMILY_COUNT` from `129` to `130`.
5. Keep every existing family id and ordering stable; append the new family after the V3-34 families.

### Required Interfaces and Contracts

- Dynamic keys are scalar-only: `int`, `float`, `bool`, or `str`. No nested maps.
- `generation_index` means admitted generation label, not age, kinship depth, or community.
- `cohort_id` is the admission cohort, not an observed activity cohort.
- The family never reads live world state, prompts, ledgers, or subjective evidence.

### Error Handling and Logging

- Wrong progress type, invalid run/revision, or negative window: `TypeError`/`ValueError` with stable validation messages.
- Unsupported metric version: `ValueError("unsupported_metric_version")`.
- Logging is bounded to counts and ids; no agent/body ids beyond the run id.

### Tests

Create `tests/unit/test_generational_cohort_metrics.py`:

- Build a `PopulationProgress` with founders plus two generations and two cohorts; assert every total, dynamic key, survival share, span, and founder/post-founder share.
- Extinction case: living 0, dead == admitted; present with zero living and survival 0.
- Single cohort: span 0 and present.
- Empty rows: generation/cohort counts 0; totals preserved; no dynamic keys.
- Invalid progress type and unsupported spec version fail.
- `validate_metric_catalog()` passes with count 130.
- `from analysis import GENERATIONAL_COHORT_COMPARISON_METRIC_VERSION, compute_generational_cohort_comparison` succeeds.
- Deterministic: two computations produce equal values and equal metric fingerprint.
- Serialization: the document roundtrips through `analysis.serialization`.

Command:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_cohort_metrics.py tests/unit/test_metric_specifications.py -q
```

### Acceptance Criteria

- One new analysis-only family exposes generation/cohort counts with explicit zero/absent semantics.
- The family cannot receive live state or feed cognition.
- The catalog count is 130 and every existing family remains unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_cohort_metrics.py tests/unit/test_metric_specifications.py -q`
- Expected: all pass; `family_count_mismatch` and `family_set_mismatch` do not occur.

## Task 9: Wire generational progress into metric assembly and collectors

### Intent

Make the new family appear automatically for generational experiment arms, remain absent for legacy arms, and preserve deterministic assembly behavior.

### Implementation Steps

1. Modify `src/analysis/metric_service.py`:
   - Import `PopulationProgress` from `simulation.generational_models` and `compute_generational_cohort_comparison` from `analysis.generational_cohort`.
   - Add `generational_progress: PopulationProgress | None = None` to `MetricComputationInputs`.
   - In the optional-block map, add `"generational_cohort_comparison": inputs.generational_progress is not None`.
   - After the block is selected, bind `progress = inputs.generational_progress`; when it is not `None`, call `_safe("generational_cohort_comparison", lambda: compute_generational_cohort_comparison(progress, run_id=run_id, input_revision=revision, window_end=window_end))`. The local binding is required for strict mypy narrowing. Keep the family out of `_NON_CATALOG_FAMILIES`; it is a catalog family.
   - Do not change `compare_metric_documents` compatibility rules.
2. Modify `src/experiments/metric_collection.py`:
   - Add `generational_progress: object | None = None` to `inputs_with_opt_in_metric_rows`.
   - Include it in the final `replace(inputs, ...)`.
3. Modify `src/experiments/collectors.py`:
   - In `assemble_arm_metric_bundle`, read `generational_progress = getattr(arm.runner_result, "generational_progress", None)`.
   - Pass it to `inputs_with_opt_in_metric_rows`.
   - Do not create a report or new arm attribute; the result field is authoritative.
4. Verify non-generational arms have `generational_progress is None` and therefore do not emit the family.
5. Verify a generational arm with progress reaches `collect_catalog_metrics` and the resulting collector document includes the family availability/fingerprint via `collector_fields_from_documents`.
6. Cross-arm comparison needs no new code: `matrix_metric_summary` groups the new numeric keys by condition and `group_role`. Document this in Task 12.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class MetricComputationInputs:
    ...
    generational_progress: PopulationProgress | None = None

def inputs_with_opt_in_metric_rows(
    inputs: MetricComputationInputs,
    *,
    ...,
    generational_progress: object | None = None,
) -> MetricComputationInputs: ...
```

- The input is detached and read-only.
- The family is emitted only when progress is present.
- No runtime, cognition, admission, or persistence behavior changes.

### Error Handling and Logging

- If assembly raises inside the family, `_safe` re-raises with the existing metadata-only `metric_family_failed` log.
- Missing progress is not an error; the family is simply absent.
- No payload logs.

### Tests

Create `tests/unit/test_generational_cohort_collectors.py`:

- `assemble_metric_documents` with a valid progress includes `generational_cohort_comparison` with `PRESENT`.
- The same inputs with `generational_progress=None` omit the family and keep all other documents unchanged.
- `inputs_with_opt_in_metric_rows` replaces only the new field.
- A short BM/generational arm with fake cognition and `max_ticks=8` produces the family through `assemble_arm_metric_bundle`.
- A non-generational reference arm does not contain the family.
- `collect_catalog_metrics` includes the family fingerprint prefix and availability.
- Determinism: two assemblies produce equal fingerprints.

Commands:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_cohort_collectors.py tests/unit/test_experiment_metrics.py -q
uv run --frozen --python 3.12.14 mypy src/analysis/generational_cohort.py src/analysis/metric_service.py src/experiments/metric_collection.py src/experiments/collectors.py
```

### Acceptance Criteria

- Generational arms automatically emit the new family; legacy arms do not.
- Collector metadata stays payload-free and deterministic.
- No new runtime dependency or authority path exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_cohort_collectors.py tests/unit/test_experiment_metrics.py -q`
- `uv run --frozen --python 3.12.14 mypy src/analysis/generational_cohort.py src/analysis/metric_service.py src/experiments/metric_collection.py src/experiments/collectors.py`
- Expected: tests and typing pass; no count mismatch.

## Phase Risks and Mitigations

- Risk: dynamic keys are confused with nested payloads.
  Mitigation: scalar-only dynamic keys following `regional_population@1`; serialization tests enforce scalar values.
- Risk: the new family is emitted for legacy runs because `generational_progress` is accidentally defaulted.
  Mitigation: default `None`; optional block and absence test.
- Risk: count pins fail in 22 files.
  Mitigation: Task 8 updates the canonical count; Task 11 sweeps every `METRIC_FAMILY_COUNT` reference and runs the full catalog test.
- Risk: cohort/generation totals disagree.
  Mitigation: rely on `PopulationProgress` consistency validation and report `cohort_generation_alignment_violations`; never recompute a competing truth.

## Phase Completion Checklist

- Tasks 8-9 acceptance criteria are met.
- `generational_cohort_comparison@1` is registered, counted, assembled, and collector-visible.
- Non-generational bundles are unchanged.
- `index.md` checkboxes are updated immediately after verified completion.
