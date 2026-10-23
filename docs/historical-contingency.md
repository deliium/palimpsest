# Historical Contingency Experiments

[← Generational runner](generational-runner.md) · [Back to README](../README.md) · [Experiments →](experiments.md)

Experiment BN (`historical_contingency@1`) studies forked histories. A common
generational prefix runs to a finalized boundary `F`, each arm becomes an
independent replay child, a small ordinary command is applied, and every child
continues to the same absolute horizon `H`. Outcomes are compared only across
repeated numeric-seed blocks.

This protocol does not claim causality from one run. It is opt-in research
surface; default runner/result writes remain `runner-config-v4` /
`runner-result-v2`.

## Shipped surface

| Surface | Contract |
|---|---|
| CLI | `palimpsest-matrix path-dependence run\|resume\|inspect\|compare` |
| Provider | Deterministic fake only |
| Fork shape | Bounded static star: one parent boundary per configured `F` |
| Artifact root | `<root>/<ensemble-id>/...` |
| Schemas | `path-dependence-{ensemble,prefix,branch,outcomes,comparison}-v1` |
| Runner pins | Latest `runner-config-v55`; no runner v56 |
| Catalog pins | 43 commands, 73 observer semantic types, 136 metric families, Alembic `0017` |

The path-dependence schemas are research siblings. They do not widen runner
configuration, legacy generational manifests, SQL branch lineage, `/v1`, or the
observer protocol.

## Recipe

The shipped fixture is `bn-food-opportunity-v1`:

- common history with named possessed food, co-located founders, declared benign
  physical rules, regenerating resources, and pre-`F` setup commands;
- `share` arm: admitted `Give` of the named food to the recipient;
- `withhold` arm: `Wait` for that actor/tick;
- smoke profile `F=4`, `H=36`; long profile `F=100`, `H=1100`.

These are deliberate fixture conditions, not defaults for arbitrary social
experiments. They make the demonstration executable; they do not install norms,
trust, institutions, technology, or narratives. Zero and unknown effects are
valid results.

```python
from experiments.path_dependence_scenario import historical_contingency_scenario

spec = historical_contingency_scenario(seed=23, profile="smoke")
```

## Artifact tree

```text
<artifact-root>/<ensemble-id>/
  ensemble.json
  prefixes/<parent-id>/<attempt-id>/fork-<F>/prefix.json
  branches/<child-id>/<attempt-id>/
    preparation.json
    branch.json
    outcomes.json
    completion.json   # or failure.json
  comparisons/<comparison-id>.json
```

Publication order is immutable ensemble and slot assignment first; sealed
eligible/ineligible prefix; preparation before child materialization; branch
result and outcomes; completion last. A technical failure publishes failure, not
completion. Completion and failure are mutually exclusive.

`F` appears in every prefix path and digest. Two `F` values under one parent
never overwrite each other.

## CLI

```bash
# Seal the design and execute the fake-only ensemble
uv run palimpsest-matrix path-dependence run \
  --spec path-dependence.json \
  --artifact-root artifacts \
  --code-revision "$PALIMPSEST_CODE_REVISION" \
  --source-artifact-digest "$SOURCE_DIGEST"

# Read-only lineage inventory
uv run palimpsest-matrix path-dependence inspect \
  --ensemble artifacts --ensemble-id "$ENSEMBLE_ID"

# Classify planned slots; --database checks objective presence
uv run palimpsest-matrix path-dependence resume \
  --ensemble artifacts --ensemble-id "$ENSEMBLE_ID" [--database]

# Write paired pointwise comparisons
uv run palimpsest-matrix path-dependence compare \
  --ensemble artifacts --ensemble-id "$ENSEMBLE_ID"
```

`run` currently composes the deterministic fake-only execution path. Production
PostgreSQL composition is available through the research-runner composition
module; database-backed durability remains an explicit verification gap unless
executed with `PALIMPSEST_TEST_DATABASE_URL`.

## Lineage and resume

- A completed sealed child is adopted; it is not rerun.
- A sealed eligible prefix plus a never-created original child `RunId` permits
  deterministic parent reconstruction and one launch of that exact slot.
- An existing child without valid completion is `failed_partial`. It is not
  appended to, deleted, or replaced by a new `RunId`.
- A sealed ineligible prefix is retained with its denominator; it is never
  repaired by outcome-driven reseeding.
- Process loss never implies durable subjective restart. Full fork state is
  process-local; reconstruction re-executes the deterministic prefix and checks
  the complete-state digest before launch.

## Outcome domains

| Selector | Domain | Unit / denominator | Zero policy |
|---|---|---|---|
| `norms.active_beliefs` | Norms | active owner norm beliefs at endpoint | known zero only with complete enabled-owner coverage |
| `norms.belief_persistence` | Norms | adjacent complete readings | unavailable below two readings |
| `relationships.mean_abs_delta` | Relationships | directed revision deltas in `[start,end)` | unavailable without an in-window delta |
| `institutions.persistent_candidates` | Institutions | detached persistent candidates | known zero only with complete six-lane search witness |
| `technology.living_retention` | Technology | `F` practical-knowledge baseline to exact endpoint | disabled/unknown baseline is not zero |
| `narratives.endpoint_persistence` | Cultural narratives | `F` narrative baseline to exact endpoint | missing baseline is not zero |
| `inequality.resource_gini` | Inequality | living agents' portable-item counts | empty living population is unavailable |
| `inequality.resource_theil` | Inequality | same holdings and denominator | empty living population is unavailable |
| `cooperation.applied_rate` | Cooperation | applied action events in `[start,end)` | no applied actions is unavailable |

Resource Gini is not a wealth score. Cooperation is not altruism. Institution
candidates are analytical classifications, never objective offices.

## Inference

Pair treatment minus control within a matched prefix/`F`/replicate. Average
within each numeric seed. Each distinct numeric seed contributes one independent
block; replicas, duplicate seed labels, agents, ticks, edges, and generations do
not increase `n`.

For `n >= 2`, report equal-weight mean, sample SD, SE, `df = n - 1`, and a
two-sided pointwise 95% Student-t interval. For `n = 1`, report a descriptive
mean only. No p-values, winner ranking, or familywise claim are produced.
`causal_claim` is always `false`.

Mixed post-`F` run-ID channel manifests are allowed but explicitly qualified;
they are not advertised as common-random-number isolation.

## Limitations

- Provider state continuation for live or recorded LLM forks is unsupported.
- Nested/adaptive fork trees, automatic intervention search, and durable
  full-subjective checkpoint wire formats are deferred.
- Sparse institutions and cultural baselines produce honest unknowns.
- The fixture conditions eligibility on founder opportunity; report both the
  eligibility denominator and complete-pair attrition.
- Newborn institution concepts remain disabled under the existing developmental
  species profile where applicable.

## See Also

- [Generational runner](generational-runner.md) — `runner-config-v55`, cohorts, archives, historical inspection
- [Cultural evolution metrics](cultural-evolution-metrics.md) — repeated-seed blocks and paired contrasts
- [Experiments](experiments.md) — trusted catalog, Matrix runner, off-gate experiment policy
