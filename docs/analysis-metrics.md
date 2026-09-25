# Analysis Metrics (V1 Specifications)

[← Experiments](experiments.md) · [Memory reconstruction](memory-reconstruction.md) · [Back to README](../README.md)

Executable formula, population, and edge-case policy for all seventeen metric families lives in `analysis.specifications`. Implementations must consume these specs; they do not redefine denominators ad hoc.

## Catalog

| Family | Version ID | Evidence stages (primary) |
| --- | --- | --- |
| `resource_inequality` | `resource_inequality@1` | objective event/state |
| `cooperation` | `cooperation@1` | objective events + action resolution |
| `conflict` | `conflict@1` | objective events + action resolution |
| `survival` | `survival@1` | objective event/state |
| `goal_completion` | `goal_completion@1` | goal transitions |
| `repeated_conventions` | `repeated_conventions@1` | objective events + action resolution |
| `behavioral_specialization` | `behavioral_specialization@1` | objective events + action resolution |
| `memory_drift` | `memory_drift@1` | agent-visible + memory stages |
| `memory_dynamics` | `memory_dynamics@1` | V2 recall audits (reconstruction stage) |
| `offline_consolidation` | `offline_consolidation@1` | harvested sleep-consolidation audits |
| `belief_accuracy` | `belief_accuracy@1` | belief revision (ClaimTruthSpec only) |
| `false_belief_persistence` | `false_belief_persistence@1` | belief revision + truth specs |
| `relationship_stability` | `relationship_stability@1` | relationship revisions |
| `trust_network_structure` | `trust_network_structure@1` | relationships (+ optional interactions) |
| `group_community_structure` | `group_community_structure@1` | nonnegative trust projection |
| `knowledge_diffusion` | `knowledge_diffusion@1` | delivery / traces / beliefs / reconstruction |
| `rumor_distortion` | `rumor_distortion@1` | multi-hop structured content |

Catalog version: `metric-catalog-v1`. Document schema: `MetricDocument` schema `1`.

`memory_dynamics@1` values: `recall_accuracy`, `source_confusion`, `memory_survival`, `interference`, `confidence_calibration`. Assembled only when `MetricComputationInputs.memory_dynamics_report` is present (in-run V2 audit export). REFERENCE / V1 reconstructive arms leave the family absent.

`offline_consolidation@1` values: `consolidation_invocations`, `traces_strengthened`, `traces_soft_forgotten`, `patterns_merged`, `belief_revisions`, `relationship_revisions`, `goal_transitions`. Assembled only when `offline_consolidation_report` is present. A missing report does not change V1 catalog assembly. Assembly logs `offline_consolidation_metrics_assembled` with the family id and value keys only.

### Supporting formulas (not a separate family)

`action_resolution_rates@1` defines attempted / applied / rejected / conflicted rates **only** from `ActionResolution` evidence. Never infer rejected attempts from absent world events. Task 11 implementations reuse this shared spec beside cooperation/conflict occurrence rates.

## Shared policies

- **Numerical:** `analysis.numerical` — float64 intermediates, sort-before-reduce, banker's quantization to 12 decimal places, signed-zero normalization, canonical quantized output (not BLAS bit-identity).
- **pandas:** `NA` is unknown; never coerce to zero; sort keys; stable mergesort ties.
- **SciPy:** empty/single-sample distributions → `unknown`; never coerce empty entropy/divergence to zero.
- **NetworkX:** lexicographic node order; community algorithm `networkx.community.greedy_modularity_communities` on a nonnegative projection with deterministic tie-break.
- **Availability:** missing or unobservable evidence is `unknown`, never silent zero/false.
- **Deceased agents:** excluded from living opportunity denominators; survival and goal death outcomes use objective death evidence; post-death no-action ticks are expected.
- **Self-edges:** relationship self-targets forbidden; graph self-loops dropped; self-communication counted separately from dyadic cooperation.
- **Action vocabulary (V1):** move, search, take, drop, give, eat, drink, sleep, talk, ask, tell, help, attack, flee, wait. Cooperation and conflict kinds stay disjoint.
- **Motifs:** contiguous n-grams (n∈{2,3}), optional explicit gap policy, `min_support=2`, sorted by `(-support, motif_id)`. No culture/role labels.
- **Adoption stages:** `world_delivery`, `receiver_trace`, `belief_candidate`, `belief_activation`, `reconstruction`, `retell`. Prefer explicit transmission roots; never invent parents from hop order.
- **Evidence-stage dedup:** corroboration by lineage root within a stage; never collapse stages into one narrative class.
- **Signed trust:** values in `[-1, 1]`; community detection uses `w = max(trust, 0)` only.
- **Resource measures:** inventory count/load, extraction, transfer, consumption-access — never labeled “wealth”.
- **Belief accuracy:** only claims covered by analysis-only `ClaimTruthSpec`; unevaluable claims stay out of the denominator.

## Empty / one / all-zero / unknown

Each `MetricSpecification` records explicit `empty_case`, `one_case`, `all_zero_case`, and `unknown_case` strings. Known-answer coverage lives in `tests/unit/metric_fixtures.py` (reference-scenario-shaped cases plus small degenerates).

## API surface

```python
from analysis import (
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
    action_resolution_rate_spec,
)

validate_metric_catalog()
spec = metric_specification("resource_inequality")
print(spec.version_identifier, spec.formulas["gini"])
```

Validation errors expose only `metric_family`, `algorithm_version`, and a stable `reason_code`.

## Logging

Specification and model code is log-free. Metric implementations emit DEBUG metadata (family, version, counts, duration) without evidence payloads.

## Tests

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_metric_specifications.py \
  tests/unit/test_metric_properties.py \
  tests/unit/test_metric_determinism.py \
  tests/unit/test_metric_service.py \
  tests/unit/test_reference_scenario_e2e.py -q
```
