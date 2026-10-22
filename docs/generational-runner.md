# Generational Runner

[← Simulation runner](simulation-runner.md) · [Back to README](../README.md) · [Experiments →](experiments.md)

Multi-generation historical experiments run through the same authoritative
`WorldEngine` and `SimulationRunner` as every other configuration. The
generational features add a demographic entry calendar, explicit stop selectors,
reproducible archive metadata, and detached historical inspection. They do not
add a second tick loop or a durable subjective-restart mechanism.

## Configuration (`runner-config-v55`)

`runner-config-v55` is emitted only for a run that has an exact
`generational_run` sibling. It requires all of:

- an exact `population_lifecycle` with a positive `max_population`;
- the owned `V3CapabilityFlags.generational_population` flag;
- explicit `new_agent_initialization`;
- a finite `stop_policy.max_ticks`;
- `stop_policy.stop_on_all_agents_terminal=false`.

The rest of the document is the exact lower-family root selected by the other
active features, plus the v54 cognition keyset. v55 activation is independent of
institutional decay: every institutional cognition mode may be `disabled`. The
default runner write stays `runner-config-v4`; older schemas are decoded
strictly and are never silently transformed into v55.

Generational runs use `runner-result-v3`. The legacy result default stays v2,
and legacy v1/v2 result documents remain accepted. New SQL migrations,
commands, events, observer semantic types, capability flags, metric families,
API versions, and protocol identities are not introduced.

## Generation, cohort, and community

Founders are generation 0. A successful `generational_interval_entry`
admission at engine tick `t` is labeled:

```text
generation = 1 + (t - 1) // generation_length_ticks
```

An interval may admit several cohorts inside one generation. A cohort records
its admission tick and spawn stratum, so it is not the same thing as a
generation. Neither is a kinship generation or an analytical community:

- **Generation** is an experimental calendar from the absolute admission tick.
- **Cohort** is one admission event at one tick and spawn location.
- **Kinship** is objective genealogy only in gated kinship plans.
- **Community** is a detached analytical cluster sampled after finalization.

The policy never assigns parents, copies founder state, transfers knowledge,
affection, rights, or offices, and never fabricates institutional outcomes.
Entrants start from the explicit species initialization profile with empty
content.

## Admission, death, and capacity order

For tick `t` the engine runs normal command effects, then lifecycle/deaths, then
the demographic policy. Consequences:

- Deaths happen before capacity is measured.
- A capacity-denied scheduled slot disappears. Later labels still depend on the
  absolute tick, not on how many admissions succeeded.
- A death and an entry in the same tick are not extinction after admission.
- In-transit living agents count once in the population totals.
- `max_population` is an admission cap, not a stop threshold.

The demographic policy is deterministic and uses the run's explicit versioned
seed scopes. It is not biology, mating, or pedigree.

## Stop selectors and precedence

Built-in selectors are evaluated after the completed tick is finalized and after
admission. They are independent of admission-cap behavior. For a successful
simultaneous match the precedence is:

1. injected/trusted stop;
2. maximum ticks;
3. generation horizon;
4. population extinction;
5. population threshold;
6. experiment criterion.

All matched built-in reason codes are retained. A generation horizon compares
the highest **ever admitted** generation label with the configured target; it
is not an age, a completed generation, or a scheduled-but-denied cohort.
Extinction means zero objective living bodies after same-tick admission.
Because v55 runs disable runtime-terminal stopping, an empty population can
continue until a future scheduled cohort unless `stop_on_extinction=true`.

`population_threshold` is optional. Its comparator is inclusive:
`at_most` stops when `measured <= value`; `at_least` stops when
`measured >= value`. It is separate from the admission cap and never stops
before the boundary is committed.

Experiment-specific criteria are trusted, versioned, deterministic, read-only,
and evaluated only when no built-in selector already stopped the run and the
criterion cadence is due. Skipped criteria are marked unevaluated. Criterion
failures and post-finalization observer/sink failures do not roll back or retry
the committed tick; an API-facing failure is `FAILED`, not successful
scientific completion.

## Artifact layout

A generational attempt writes an append-only archive under the configured root:

```text
<artifact-root>/<run_id>/<attempt_id>/
  config.json                       # exact encoded runner config
  manifest.json                     # generational-run-manifest-v1
  completion.json                   # generational-completion-v1
  failure.json                      # generational-failure-v1, on failure only
  history/<boundary_tick:012d>.json # generational-history-v1
  community-samples/<boundary_tick:012d>.json
  recording-usage/                  # generational-recording-usage-v1 rows
```

`manifest.json` records source revision/digest, environment, provider identity,
config/scenario/cognition fingerprints, seed manifest, assignment, execution
recipe, and history policy. `completion.json` binds the manifest hash, validated
recording usage, final population progress, canonical history references, and
the full result document, including exact and replica-normalized trajectory
hashes. A required-artifact failure cannot be reported as success.

Seed metadata preserves the actual versioned scopes. World/environment use
stochastic identity; demography, initialization, and lifespan retain run-ID
scoping; innovation uses configured deterministic material. Exact reproduction
therefore requires the same **complete identity**, not merely the same root seed
with a new run ID. Changing that scoping needs a later versioned identity
contract; the generational feature does not silently unify it.

## Historical inspection, not restart

Enable `historical_checkpoint_cadence_ticks` only together with a matching
durable runner checkpoint cadence and a historical reader. At each cadence
boundary the archive records the committed revision, objective commit hash,
snapshot reference, and finalized population evidence. Generation-change or
terminal samples may reference the nearest earlier snapshot and fold the journal
to the exact boundary; cadence samples require an exact boundary snapshot.

Historical seek reconstructs the advertised objective boundary and population
state. It does **not** restore memories, beliefs, relationships, office ledgers,
runtime rosters, or pending subjective work. There is no durable subjective
restart bundle. With no historical cadence, the archive still has final
provenance and results but must not claim historical availability.

## Reproducibility and LLM replay

Exact external-LLM reproduction requires a deterministic fake or immutable
recorded outputs. Replay usage is recorded only after prompt/schema compatibility
and structured-output validation, and usage rows are ordered canonically, not by
asynchronous return order. Recording roots, namespaces, and lookup modes are
composition inputs; their paths never enter config fingerprints or metadata.

`--recording-root`, `--recording-artifact-id`, `--recording-namespace`, and
`--recording-lookup-mode` must be supplied together. A deterministic-fake
configuration rejects them. Namespace reuse across independent cells must be
explicit.

Source identity needs `--code-revision` plus either `--source-clean` or
`--source-artifact-digest <sha256>`. A revision string alone cannot identify a
dirty working tree.

## CLI

Run one configuration with the ordinary runner and archive its results:

```bash
cat > recipe.json <<'JSON'
{
  "recipe_id": "plain-generational",
  "version": "1",
  "params": {},
  "intervention_id": null,
  "intervention_version": null,
  "intervention_params": null
}
JSON

PALIMPSEST_DATABASE_URL='postgresql+asyncpg://.../palimpsest' \
uv run --frozen palimpsest-matrix generational \
  --config run-v55.json \
  --execution-recipe recipe.json \
  --artifact-root artifacts \
  --run-id gen-001 \
  --code-revision "$(git rev-parse HEAD)" \
  --source-clean
```

The recipe file is the exact six-key nested descriptor, resolved by the closed
registry (`plain-generational` or `bl-diagnostic`), not an import path. If the
config has no `experiment`, the command assigns the explicit ad-hoc identity
`generational_runner_ad_hoc@1` / `standalone`. Named config metadata never
installs an intervention by itself.

Matrix runs and resumes accept the same archive/recipe/source options for
expanded generational cells:

```bash
uv run --frozen palimpsest-matrix run \
  --matrix matrix.json \
  --manifest-root runs/matrix-001 \
  --generational-artifact-root artifacts \
  --execution-recipe recipe.json \
  --code-revision "$(git rev-parse HEAD)" \
  --source-clean
```

Exit codes are `0` for a valid scientific stop with all required artifacts, `1`
for execution/orchestration failure, and `2` for preflight, usage, or integrity
conflicts.

Matrix resume is not subjective continuation. It may adopt a fully verified
completed archive without constructing a runner, or rerun a non-durable cell
from origin in a new attempt directory with an unchanged scientific `run_id`.
An incomplete durable `RunId` already present in the same persistence
destination is non-retryable (`durable_origin_rerun_unsupported`); deleting or
relabeling the original run is not a resume. Reproducing into a fresh, isolated
persistence destination is a separate explicit operator action.

## Cost and limits

Complete historical world state, evidence, and finalized receipts remain
retained for the whole run. Memory and storage therefore grow with history size.
Optional full-history channels may dominate cost. The implementation avoids
per-tick prefix copying or prefix scans, but it does not claim constant memory,
bounded disk, or linear runtime for every channel.

## Verification

The opt-in long-horizon proof requires a disposable `palimpsest_test` database:

```bash
PALIMPSEST_TEST_DATABASE_URL=postgresql+asyncpg://.../palimpsest_test \
uv run --frozen --python 3.12.14 pytest -m 'integration and scale' \
  tests/integration/test_generational_scale.py -q
```

It exercises 100000 ticks, one entrant per 1000 ticks, empty-population gaps,
99 due cohorts, snapshot/history cadence, exact final hashes, historical seek
parity, deterministic twins, and indexed finalized-receipt membership across
checkpoint recovery. A skipped database or scale gate is a verification gap,
not a passing durability check.

## See also

- [Simulation runner](simulation-runner.md) — runner lifecycle and identities
- [Configuration](configuration.md) — exact schema gates
- [Experiments](experiments.md) — Experiment BL and matrix composition
- [Persistence](persistence.md) — durable runs, snapshots, and replay
- [LLM providers](llm-providers.md) — recording and replay
