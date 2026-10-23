# Cultural Evolution Metrics

[← Analysis metrics](analysis-metrics.md) · [Back to README](../README.md) · [Research API →](research-api.md)

Opt-in, detached analysis of cultural continuity, transmission, and
differentiation. Capture and comparison never change simulation commands,
perception, world state, stop criteria, or owner memory, and there is no
composite culture score.

## Capture and artifacts

Capture is composition-only and default off. Matrix runs opt in with
`--cultural-metrics`; no runner schema, capability flag, event, command, or
migration changes.

```bash
uv run palimpsest-matrix --code-revision "$PALIMPSEST_CODE_REVISION" run \
  --matrix matrix.json \
  --manifest-root ./matrix-out \
  --cultural-metrics \
  --cultural-max-frames 10000 \
  --cultural-max-rows 1000000 \
  --cultural-baseline-boundary 0
```

`--cultural-end-boundary` is optional and defaults to the actual last finalized
boundary. Explicit cultural options require `--cultural-metrics`. Caps must be
positive integers; the baseline must be nonnegative and within the configured
tick horizon; an explicit end must be greater than the baseline and within the
horizon. Requested bounds are persisted; an early stop never rebases them.

Each completed cell may write two sibling sidecars under `cells/`:

- `<cell_id>.cultural-evidence.json` — `cultural-evolution-evidence-v1`,
  normalized owner-local evidence and coverage.
- `<cell_id>.cultural-metrics.json` — `cultural-cell-metrics-v1`, the bound
  evidence digest plus six encoded metric documents.

Both files are limited to 64 MiB, nested `rows_json` to 16 MiB, and JSON depth
to 32. Decoders reject duplicate keys at every level, non-finite numbers,
unknown keys/versions, invalid UTF-8, and symlinked or escaping paths. Identical
content is idempotent; a different complete pair is an artifact conflict, never
an overwrite. Legacy `.metrics.json` and `matrix-metric-summary-v1` keep their
original schemas and meaning.

Capture is not backfilled. With capture requested, a completed cell without a
verified matching pair fails preflight (`cultural_capture_missing` or
`cultural_capture_policy_mismatch`) without rerunning objective history and
without overwriting its completion. A sealed generational archive with lost
capture is not permission to rerun. Full recapture requires a fresh
manifest/run identity.

## Analysis windows and populations

The baseline is an exact boundary (default `0`). The endpoint is an exact
requested boundary or the resolved last finalized boundary; nearest-tick and
first-nonempty substitution never happen. A missing requested baseline leaves
cohort metrics unavailable; an empty baseline yields zero counts and null
cohort-retention shares. It is never silently rebased to the first nonempty
frame.

Living prevalence excludes deceased owners. Dead owners remain available as
provenance sources. Enabled, disabled, fresh-empty, restored-missing, partial
coverage, and complete-empty inventories remain distinct. Complete empty
inventories are known zero carriage; disabled or missing inventories are
unknown, not zero.

## Provenance model

Every measurement carries the scientific selector tuple (family, algorithm and
policy versions, formula key, dimension, representation, scope, partition,
groups, population basis, denominator code, exact window, units) and owner-level
evidence pointers. `row_id` is only a row identity and is never a cross-run
comparison key.

Important limits:

- `ledger_carriage` is retained owner inventory, not proof of psychological
  possession or recall.
- Local extinction means loss from the measured inventory population, not that
  no record or memory survives.
- Narrative ancestry follows explicit owner-qualified parent/merge evidence.
  Identical local IDs in different owners are not the same variant.
- Exact fidelity requires comparable single-source fingerprints and an
  attributable donor no later than acquisition. Declared mutation flags are not
  a substitute for comparable content.
- Vocabulary measures label inventories, not meaning. Translation and semantic
  drift are separate analyses.
- Technology retention measures living practical knowledge. A preserved record
  can prevent global loss while living retention still falls; knowledge is not
  proof of performability.

## Six families and fourteen requested areas

All six families are additive and omitted when capture is absent. Documents may
be PARTIAL while individual measurement rows remain complete.

### `cultural_trait_dynamics@1`

Trait frequency, persistence, extinction, and diversity over owner inventories.

- `trait_frequency`: carriers of an exact trait / eligible living owners at each
  boundary. Per-trait prevalence is a within-run series and is never averaged
  across different trait identities.
- `endpoint_persistence`: baseline-cohort traits present at the exact endpoint /
  fixed baseline cohort.
- `continuous_persistence`: baseline-cohort traits present at every complete
  intermediate boundary / fixed baseline cohort, censored on gaps.
- `extinction_transition`: positive prevalence at boundary `b` and zero at the
  next complete `b+1`.
- `richness`, `shannon_entropy`, `effective_diversity`, `simpson_diversity`:
  distinct carrier traits or carrier-incidence distributions at one boundary.

### `cultural_evolution_transmission@1`

Transmission fidelity and horizontal/intergenerational/kin-vertical
classification for attributable acquisition edges.

- `exact_fidelity`: comparable single-source edges with equal source/target
  content; `mutation_rate` is the changed share.
- `declared_mutation_share`, `recombination_share`.
- `horizontal_share`, `forward_intergenerational_share`,
  `reverse_intergenerational_share`, `unknown_generation_share`.
- `vertical_kin_share`: forward/known intergenerational edges also marked
  kin-vertical.
- Counts keep ambiguous, unknown, independent-rediscovery, artifact, mutation,
  recombination, and kin-vertical edges separate with explicit denominators.
  Every share names whether its denominator is attributable acquisitions or
  comparable single-source edges.

Modality alone does not prove a donor edge. Kin-vertical means explicit
genealogy plus attribution, not affection, inheritance rights, or automatic
knowledge transfer.

### `cultural_population_structure@1`

Between-group divergence and within-group convergence for an optional, explicit
group basis.

- `between_group_js_divergence`: Jensen-Shannon divergence in nats over trait
  carrier distributions for a group pair at each boundary.
- `within_group_pairwise_distance`: mean Jaccard distance across eligible owner
  pairs in a group.
- `within_group_convergence`: distance change on identical owner pairs present
  at both endpoints. Both-empty-at-either-end pairs are excluded from both
  means with explicit counts. `within_group_excluded_pair_count`,
  `within_group_baseline_empty_pair_count`,
  `within_group_endpoint_empty_pair_count`, `within_group_cohort_size`,
  `within_group_entrant_count`, and `within_group_exit_count` expose the
  excluded pairs and membership churn.

Global trait metrics remain available without groups. Dynamic community labels
are not treated as stable cross-run selectors.

### `cultural_narrative_survival@1`

Baseline-cohort narrative persistence through explicit owner-local ancestry.

- `baseline_variant_count`, `surviving_baseline_count`,
  `unresolved_baseline_count`.
- `endpoint_persistence`, `continuous_persistence`.
- `witnessed_generation_span`, `observed_duration`.

Branching and merging follow declared parent evidence. A retelling by the same
root does not create independent support, and no truth field exists.

### `cultural_vocabulary_differentiation@1`

Vocabulary inventory divergence, separate from semantics.

- `group_vocabulary_richness`.
- `between_group_vocabulary_js`, `between_group_vocabulary_jaccard`.
- `between_group_shared_label_count`, `between_group_label_union_size`.
- `within_group_vocabulary_convergence` on fixed owner pairs.

Only active unmerged terminology bindings enter the inventory. Candidates and
retired bindings are counted separately.

### `cultural_technology_continuity@1`

Living retention, archival survival, and technology loss.

- `baseline_content_key_count`, `living_retention`,
  `exact_variant_retention`.
- `living_loss_count`, `living_loss_share`.
- `technology_preserved_count`, `technology_absent_count`,
  `technology_unknown_count`.
- `global_loss_count`, `global_loss_share`.
- `not_performable_count` remains explicit unknown unless performability
  evidence exists.

Archival preservation prevents global loss but does not restore living
retention. Unknown archive coverage cannot prove global loss.

## Repeated-run comparison

Aggregate verified cell artifacts into a sibling comparison document:

```bash
uv run palimpsest-matrix --code-revision "$PALIMPSEST_CODE_REVISION" aggregate \
  --matrix matrix.json \
  --manifest-root ./matrix-out \
  --cultural-summary \
  --cultural-contrast record_availability-absent:record_availability-present \
  --confidence 0.95
```

`--cultural-summary` writes `cultural-metric-comparison.json`
(`cultural-metric-comparison-v1`). `--cultural-contrast` and `--confidence`
require `--cultural-summary`. Contrasts use explicit condition IDs; no role
combination is selected implicitly. A contrast must differ in exactly one
declared matrix factor, verified by re-materializing both expected conditions
through the registered factor applicators from the same matrix base and
comparing complete canonical config fingerprints. Hidden extra mutations and
multi-factor contrasts fail with `comparison_factor_mismatch`.

### Inference units

The inferential unit is an independent numeric-seed block, never an agent, tick,
acquisition edge, or trait. Repeated seed ordinals and replicas sharing one
numeric seed are averaged into one block before inference. Raw cell count,
duplicate/repeat count, block membership, and independent block count are all
reported.

For `n` seed blocks with `n >= 2`, the mean confidence interval is

```text
mean +/- t((1 + confidence) / 2, n - 1) * sample_sd / sqrt(n)
```

with `ddof=1`, method `student_t_seed_block_mean`, and the assumptions
`independent_numeric_seed_blocks`, `approximately_well_behaved_seed_block_means`,
and `within_run_census_not_resampled`. For `n = 1`, the mean is present but the
SD/CI are null (`insufficient_independent_seeds`); for `n = 0` everything is
null. A constant sample has a degenerate zero-width interval. Intervals are not
clipped to `[0, 1]`.

Example: seed-block means `1, 2, 3` give mean `2`, sample SD `1`, `df = 2`, and a
95% interval of approximately `[-0.484, 4.484]` for a count estimand. Three seeds
validate the calculation; they do not establish empirical coverage.

Within-run frequencies are censuses over observed inventories and receive no
binomial interval by default. The existing exact binomial helper remains for its
original Bernoulli estimands. Legacy `p05`/`p95` values remain empirical
percentile ranges, not confidence intervals.

### Paired contrasts

A requested contrast pairs eligible cells by `(seed_ordinal, replicate_index)`
within the same matrix, additionally checking equal numeric seed and compatible
provider/design identities. Treatment-minus-control differences are formed
before seed blocking; the same Student-t interval is applied to block deltas.
Missing one arm excludes that pair and is reported; no independent-arm
substitution or invented zeros are used.

`pairing_basis=seed_ordinal_replicate` is a blocking convention, not a claim of
common random numbers. `shared_stream_status` is `shared`, `mixed`, or `unknown`
from actual channel selectors. A sampled channel scoped to different durable run
IDs is not shared even with equal seed; reserved/ignored or absent channels do
not create an alignment violation. `mixed` still permits a descriptive paired
seed-block difference and its interval when the controlled-provider and design
criteria hold.

Default inferential eligibility requires deterministic fake or validated
immutable replay usage. Live, record, cache, or untracked custom factories
remain descriptive-only and report `uncontrolled_provider_variation`; a
recording directory alone does not prove determinism. No simulation seed, run
ID, stream, or config is rewritten to improve pairing.

There are no p-values, multiple-testing corrections, composite culture scores,
automatic causal claims, or significance guarantees. Per-trait prevalence and
owner-local lineage detail remain within-run; there is no arbitrary trait
alignment across runs.

## Artifact integrity

A pair is reusable or adoptable only when objective completion is valid and the
evidence/metric identities, matrix/cell/config/run IDs, source revision, capture
caps, requested window, evidence digest, and canonical bytes all match. A
truthful partial or failed-capture pair is valid evidence, not I/O corruption.
Corruption, conflicting content, stale fingerprints, or a missing requested pair
fail the research operation without altering already committed ticks or sealed
archives. Readers reject symlinks and escaping paths under the manifest root.

Logs report safe cell IDs, counts, availability, and reason codes only. They
never include labels, messages, memories, prompts, fingerprints used as payload
surrogates, or evidence payloads.

## See also

- [Experiments](experiments.md) — matrix CLI, sidecars, generational comparison
- [Analysis metrics](analysis-metrics.md) — metric documents and numerical policy
- [Generational runner](generational-runner.md) — archives and historical inspection
- [Architecture](architecture.md) — authority boundaries and extension rules

## Path-dependence outcomes

Historical-contingency experiments reuse the repeated-seed numerical policy and several existing analysis calculators; see [Historical contingency](historical-contingency.md). They add comparison projections, not new metric families.
