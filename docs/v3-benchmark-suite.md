# V3 generational civilization benchmark

[← V2 benchmark suite](v2-benchmark-suite.md) · [Back to README](../README.md) · [Development →](development.md)

The V3 suite (`v3-generational-civilization-benchmark-v1`) is the executable
end-to-end benchmark for generational civilization mechanisms. It contains
thirty small cases, two lanes per case, and a separate deterministic/small-
statistical qualification harness. It validates mechanisms, sourcing and
provenance; it does **not** require a government, money, religion, myth or
institution to emerge. A complete window with no phenomenon is a valid null.

## Registry and fixtures

| Request | Scenario id | Controlled checks | Unassisted research status |
| --- | --- | --- | --- |
| 1 | `v3-bench-01-blank-slate` | blank owner stores + population change | passes |
| 2 | `v3-bench-02-dependent-care` | dependency need/response window | passes |
| 3 | `v3-bench-03-intergenerational-teaching` | mentorship/developmental uptake | passes |
| 4 | `v3-bench-04-cultural-mutation` | cultural feature provenance/mutation | passes |
| 5 | `v3-bench-05-memory-layers` | historical memory layers | passes |
| 6 | `v3-bench-06-record-after-witnesses` | physical record + later reading | complete-window null (`no_record_observed`) |
| 7 | `v3-bench-07-false-record` | physically legal false record | complete-window null |
| 8 | `v3-bench-08-technology-discovery` | practical knowledge + lifecycle | complete-window null |
| 9 | `v3-bench-09-technology-diffusion` | transmission through record/teaching | complete-window null |
| 10 | `v3-bench-10-technology-loss` | holder/record loss after death | complete-window null |
| 11 | `v3-bench-11-technology-rediscovery` | independent rediscovery | complete-window null |
| 12 | `v3-bench-12-inheritance-practices` | corpse-custody succession | passes |
| 13 | `v3-bench-13-long-term-commitments` | commitment fulfillment/violation | complete-window null |
| 14 | `v3-bench-14-subjective-barter` | negotiated exchange | complete-window null |
| 15 | `v3-bench-15-candidate-exchange-medium` | exchange-function evidence | complete-window null |
| 16 | `v3-bench-16-collective-project` | collective work records | complete-window null |
| 17 | `v3-bench-17-public-good-patterns` | benefit/contribution records | complete-window null |
| 18 | `v3-bench-18-regional-migration` | WorldEngine journeys | passes |
| 19 | `v3-bench-19-isolated-divergence` | isolated contact/migration window | passes |
| 20 | `v3-bench-20-recontact-exchange` | re-contact + local uptake | passes |
| 21 | `v3-bench-21-vocabulary-divergence` | owner vocabulary divergence | passes |
| 22 | `v3-bench-22-generational-semantic-drift` | sense history/drift | passes |
| 23 | `v3-bench-23-cross-cultural-mistranslation` | translation hypotheses | complete-window null |
| 24 | `v3-bench-24-narrative-after-witnesses` | narrative after witness extinction | passes |
| 25 | `v3-bench-25-persistent-role` | institution-like role evidence | passes |
| 26 | `v3-bench-26-office-succession` | office claims + succession | passes |
| 27 | `v3-bench-27-institutional-persistence` | cross-generation persistence | passes |
| 28 | `v3-bench-28-institutional-decay` | measured weakening/collapse windows | passes |
| 29 | `v3-bench-29-founder-contingency` | sealed-prefix fork + no-op twin | passes (grouped) |
| 30 | `v3-bench-30-multigeneration-fork` | fast-cohort sealed-prefix fork | passes (grouped) |

Every case owns one immutable recipe. Independent cases 01–28 have a controlled
mechanism lane with declared ordinary-command milestones and an unassisted
research lane. Grouped cases 29–30 retain the Experiment BN protocol: sealed
common prefix, unchanged parent, independent children through normal admission,
and an explicit no-op/treatment contrast.

## Profiles, seeds and stops

| Profile | Ticks | Seeds | Founders | Entry / generation / lifespan | Cap |
| --- | --- | --- | --- | --- | --- |
| `smoke` | 96 | 23 | 4 | 8 / 16 / 24 | 12 |
| `research` | 192 | 11, 23, 37, 53, 71 | 4 | 8 / 16 / 24 | 12 |
| `visual` | 160 | 23 | 6 | 8 / 16 / 24 | 16 |

All profiles disable competing generation caps, extinction stops, population
thresholds and experiment criteria. A run is complete only when it commits the
declared horizon. Case 30 declares faster cohort labels (interval 2, generation
4) and a 12-tick sealed prefix. Profiles are fixtures, not capacity claims; do
not add seeds or extend horizons after inspecting outcomes.

Descendants use `species_default_civilization_learner_v1`, a v55-only,
content-empty pack: modes are on, every owner store starts empty, and no
founder content is copied.

## CLI and source identity

```bash
uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark list

uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark run \
  --profile smoke --lane mechanism \
  --output /tmp/palimpsest/benchmark/mechanism \
  --timeout-seconds 300 \
  --code-revision "$PALIMPSEST_V3_SOURCE_REVISION" \
  --source-artifact-digest "$PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST"

uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark run \
  --profile research --lane research \
  --output /tmp/palimpsest/benchmark/research \
  --timeout-seconds 300 \
  --code-revision "$PALIMPSEST_V3_SOURCE_REVISION" \
  --source-artifact-digest "$PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST"

uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark verify \
  --output /tmp/palimpsest/benchmark/mechanism --require-complete \
  --code-revision "$PALIMPSEST_V3_SOURCE_REVISION" \
  --source-artifact-digest "$PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST"
```

Supply exactly one source assertion: `--source-clean` for a verified clean
snapshot, or a canonical 64-hex `--source-artifact-digest` for an archived
working tree. Never infer cleanliness from the revision alone.

`verify` checks the canonical suite and every referenced run artifact. With
`--require-complete` it also requires every run to pass all required checks.
That strict mode is correct for the controlled mechanism suite. Unassisted
research suites may retain legal nulls, so their integrity can be verified
without `--require-complete`; the resulting `benchmark_suite_status=incomplete`
is an explicit scientific outcome, not a skipped lane.

`run` exits `0` only when every selected run passes; research selections with
legal nulls exit `1` after publishing the complete artifact set.

## Artifacts and comparison

Sibling artifacts use `civilization-benchmark-run-v1` and
`civilization-benchmark-suite-v1`. They record execution, horizon, coverage,
evidence availability, checks with qualified sources, phenomenon state,
publication status, intervention receipts and a canonical hash. They never
replace runner/result/archive schemas and never feed cognition, prompts or stop
selectors.

`experiments.civilization_benchmark_comparison` composes scalar outcomes:

- descriptive summaries keep raw observations and excluded-cell denominators;
- numeric seeds are independent blocks; duplicates within a block are averaged;
- missing pairs are recorded, and no interval is produced without two complete
  paired blocks; n=1 is descriptive;
- pointwise Student-t intervals only, no family-wise claim and no positive-effect
  gate;
- founder-roster treatments treat whole-population observations as descriptive
  only; initializer-pack differences require a composite treatment and every
  changed mode declared;
- grouped fork outcomes delegate to the existing path-dependence estimator.

## Qualification harness

```bash
PALIMPSEST_V3_SOURCE_REVISION=<revision> \
PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST=<sha256> \
PALIMPSEST_V3_BENCHMARK_ROOT=/tmp/palimpsest/benchmark \
uv run --frozen --python 3.12.14 pytest -m 'integration and scale' \
  tests/benchmarks/test_v3_civilization_benchmark.py -q
```

The harness runs mechanism smoke, research smoke, an exact-identity twin in a
separate namespace, and the five-seed research profile. It writes
`qualification-matrix.json` with per-scenario execution/evidence/phenomenon
states, the nineteen original completion criteria, external gate statuses and
known limitations. Synthetic test identities are labeled and are never release
attestations.

## Qualification snapshot (2026-10-30)

Source identity: committed revision `8f050a90f90190009163f4956ab9cc69edbdd0d6`
plus executable-source digest
`fef95f48f5a3d461fea6325953b64b265c936a514d0f012986f7eb1e8d3d0fe7`
(`source_clean=false`; 2,207 first-party source/test/client/runtime files).
Harness output is written beneath a caller-chosen root and is not committed.
Treat that root as ephemeral: regenerate the matrix and the sibling artifacts it
references by re-running the harness command above.

| Lane | Result |
| --- | --- |
| Mechanism smoke, seed 23 | 30/30 completed 96 ticks, complete evidence, all required checks pass |
| Research smoke, seed 23 | 30/30 completed; 17 pass, 13 legal nulls |
| Research profile, seeds 11/23/37/53/71 | 150/150 completed 192 ticks; same 13 null families |
| Deterministic twins | identical ordered artifact hashes, separate namespace |
| Grouped forks 29/30 | sealed prefix, unchanged parent, child continuation observed |
| Comparison | descriptive seed-block summaries; no forced contrast or effect |
| 10k generational / evidence-rich | completed |
| 10k flags-off control | timed out at 2,189 ticks |
| 100k generational | completed 100,000 ticks with zero living owners |
| 100k evidence-rich / flags-off | timed out at 90,765 / 8,158 |
| Historical queries | 3/3 passed |

The nineteen completion criteria in `qualification-matrix.json` show fourteen
verified by passing mechanism lanes and five external gates that require the
full regression/client/image lanes. Those external gates are not inferred from
this harness; the final verification below executes them.

## Final verification (2026-10-30)

All required Task 23 lanes executed on the same working-tree archive:

| Gate | Result |
| --- | --- |
| Default collection | 6,716 passed, 0 failed, 2 opt-in stress-probe skips, 135 deselected, 78% coverage, 1,934.54 s |
| PostgreSQL integration | 93 passed, 0 failed, 0 skipped, 112.70 s |
| Compose/browser | 19 passed, 0 failed, 0 skipped, 384.80 s against `palimpsest-api:v3-44-task23` |
| Godot 4.7.2 protocol | 47 suites passed, 0 failed; pinned archive SHA-512 matched |
| Research UI | 45 files / 231 tests passed; 0 Svelte errors/warnings; build ok |
| Static gates | Ruff clean, mypy 0 errors across 1,654 files, 25 import contracts kept, whitespace clean |
| Benchmark harness | 4 passed, 0 failed, 0 skipped, 1,455.16 s |
| Historical queries | 3 passed, 0 failed, 0 skipped |

Release image `palimpsest-api:v3-44-task23` has image ID
`sha256:532695b563b9dc6b0da96bd677d38bce94eccc33922ceaf5b337b759f5fd4b87`
and labels revision `8f050a90f90190009163f4956ab9cc69edbdd0d6`, source digest
`fef95f48f5a3d461fea6325953b64b265c936a514d0f012986f7eb1e8d3d0fe7`,
`source-clean=false`. The two default skips are the documented opt-in
publication-RSS and 5,000-boundary checkpoint probes, executed separately in
Task 21; they are not counted as required-gate passes.

## Measured envelope and limits

The V3-43 lanes remain separate measurement lanes:

| Workload | 10k | 100k |
| --- | --- | --- |
| Generational | completed | completed ticks with zero living owners (throughput, not sustained capacity) |
| Evidence-rich | completed | timed out at 90,765 ticks |
| Flags-off control | timed out at 2,189 ticks | timed out at 8,158 ticks |

Historical-query measurements pass separately. Do not infer universal 100k
capacity, dense evidence-rich completion or long-term survival from tick
completion alone. Supported claims stop at the verified workload and the actual
population/evidence counters.

## Release use

End users need only a container runtime and a browser. The release image builds
Godot Web and the Research UI SPA in pinned stages and serves both as static
assets; no local Godot installation, editor, manual Web export or frontend build
is required. Presentation, benchmarks and research inspection never advance the
simulation or grant capture/truth authority. See [Godot observer](godot-observer.md)
and [Research UI](research-ui.md).

## See Also

- [V2 benchmark suite](v2-benchmark-suite.md) — legacy sixteen-scenario composition gates
- [Generational runner](generational-runner.md) — v55 lifecycle, stop selectors and archives
- [Historical contingency](historical-contingency.md) — sealed-prefix fork protocol
- [Long-horizon scalability](long-horizon-scalability.md) — measured scale envelope
- [Development](development.md) — exact verification commands

Current catalog: 212 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
