# Scientific models

Owner-scoped predictive models, frozen prior forecasts, observed outcomes,
calibration and descriptive model comparison. Models are fallible beliefs. They
never mutate the world, never install truth and never create or replace an
`AgentCommand`.

## Activation

Scientific models deepen the owned `science` V4 capability. They activate only
when the existing science prerequisites are present:

- `predictive_world_model` enabled;
- a `bounded_experimentation` spec;
- `V4CapabilityFlags.science`.

`science=False` is inert: no model state, no predictive metric input, no pending
v4 payload. There is no `scientific_models` capability flag, per-agent mode,
runner sibling or `runner-config-v58`. The latest opt-in runner remains
`runner-config-v57`; default runner/result stay v4/v2.

## Model hypotheses

`ModelHypothesis` is an owner belief about an observable regularity. Sources are
`observed_regularity` or `experiment_hypothesis`; optional causal links are
provenance only. Target kinds are closed:

- `season` — the season at two future observation boundaries;
- `resource_regeneration` — **observed net visible quantity change** over those
  boundaries, not an isolated regeneration rate;
- `production_outcome` — the categorical result of an existing `Experiment`
  execution;
- `disease_risk` — unavailable; no disease observable exists, so no disease
  hypothesis, forecast or score can be constructed.

Season and resource hypotheses condition on stable source conditions (season and
location). Production hypotheses keep the full owner-visible action-time
condition set for comparability.

Lifecycle is `active | suspended | retired`. Temporary source loss suspends
issuance without deleting issued cases; restoration resumes the same identity.
Explicitly retired or superseded sources retire permanently; replacements create
successor identities with lineage. Issued forecasts keep their frozen content.

## Two candidate predictors

Every case carries exactly two candidates, admitted together or not at all:

- `hypothesis_baseline_v1`: weight 2 for the source claim and 1 for every other
  class in the target alphabet;
- `empirical_context_v1`: past resolved counts in the exact origin context with
  Laplace `+1` smoothing; zero samples yield a uniform distribution.

Integer largest-remainder allocation produces probabilities summing to exactly
1000 milli. Predictive confidence is the chosen class's probability. Legacy
experiment-hypothesis confidence remains a support ratio and is never used as a
probability.

## Issuance, commitment, target and receipt

An observation at tick `t` creates a detached candidate; ordinary finalization
after tick `t` commits it. The case records:

- `issued_observation_tick = committed_after_tick = t`;
- `target_observation_tick = t + 2`;
- a frozen training high-water mark not after `t`;
- frozen source/model revisions, distributions, alphabet and parameters.

The immediately following observation `t+1` is intentionally not scored: its
physical facts already exist by finalization. At most one case is issued per
owner per integer tick; repeated observation keys are no-ops. No command is
created, replaced or submitted.

Season settles from `Observation.season` at the exact target boundary. Resource
settles from the same visible entity, location, kind and unit; the outcome stores
the private start/end milli values and the direction class. Production requires a
separate owner `ModelExecutionBinding` for the final effective `Experiment`
command at `t+1` plus exactly one matching actor occurrence observed at `t+2`.

Outcome states are `pending`, `scored` (observed), `unavailable`,
`not_attempted` and `not_comparable`. Missing, occluded, late, foreign-actor,
bystander-redacted, denied or ambiguous evidence never becomes a failure or a
zero-loss sample. Pending forecasts stay right-censored.

## Performance

Scoring uses the frozen distribution:

- per-case Brier numerator `sum((p_milli[k] - 1000*[k=y])^2)`, in `[0, 2000000]`;
- mean Brier millionths via half-even rounding; smaller is better;
- hit count/share;
- ten confidence bins and a calibration gap over observed confidence, not
  hypothesis support.

Comparisons are paired over identical case IDs, owner, target, context, unit and
horizon. At least three paired outcomes are required for descriptive
`lower_loss_a`, `lower_loss_b` or `tied`; otherwise `insufficient_samples`.
There is no significance claim, pooled science score, owner ranking, universal
winner, truth value or causal claim. Performance covers the retained cohort only
and is never called lifetime accuracy.

## Caps, retention and revisions

Per owner: 32 hypotheses, 64 models, 128 pending cases, 512 terminal cases, 512
revision records, 256 derivation samples, 64 empirical bins per model, 128
aggregated coverage notices, 4096 summaries and 2048 comparisons. Nested arrays
are bounded too (8 source refs, 8 conditions, 64 evidence refs per revision, two
candidate predictions, two opaque outcome refs).

Pending cases and the revisions they pin are never evicted. Oldest terminal
cases and unpinned revisions are pruned by `(tick, id)`; counters and first-
retained watermarks record eviction. A cap refusal is coverage, not a tick
failure. Empirical-bin exhaustion refuses unseen contexts rather than merging
them.

## Recovery and exports

`scientific-model-state-v1` is a strict canonical codec with owner, policy and
revision-closure validation. Pending subjective transitions use
`finalization-command-v4`, which requires predictive state while keeping the
other science sidecars nullable and correlated. v1/v2/v3 payloads are unchanged
and forbid predictive state. Runtime checkpoints carry the committed ledger;
forks include its digest; retired-owner exports and
`SimulationRunnerResult.scientific_model_ledgers` expose owner-ordered state.
Newborns start empty and admission rejects populated predictive state.

## Detached analysis

`analysis.scientific_models_*` consumes only completed-run tokenized facts:
hypotheses, models, prior predictions, observed outcomes, revisions and
coverage. It verifies closure, temporality, probability sums and deduplication,
uses 32-tick issuance windows (latest 512 retained), and recomputes Brier,
calibration and paired comparison independently of cognition. Six append-only
families occupy catalog positions 256–261:

- `scientific_model_structure`
- `scientific_model_predictions`
- `scientific_model_observed_outcomes`
- `scientific_model_calibration`
- `scientific_model_revisions`
- `scientific_model_comparison`

Detailed group values live in the snapshot rows; catalog values are counts, not
pooled performance. No analysis input means no predictive family emission.

## Publication, store and reads

`scientific-models-snapshot-v1` carries reference-closed case bundles and whole-
group derived rows with explicit coverage. Publication is programmatic and
opt-in via `experiments.scientific_models_publication`; receipts are closed to
`published`, `disabled`, `missing`, `quota_exceeded` and `corrupt`, and never
change the scientific status. `scientific-models-store-v1` writes atomically
(child before manifest, cumulative per-run quotas, digest verification) and
readers never create, repair or delete.

Settings are paired and optional:

- `PALIMPSEST_SCIENTIFIC_MODELS_ROOT`;
- `PALIMPSEST_SCIENTIFIC_MODELS_CURSOR_KEY` (at least 32 UTF-8 bytes).

Neither means disabled; exactly one is invalid. Eight GET-only routes live under
`/v1/simulations/{run_id}/scientific-models` (summary plus models, predictions,
outcomes, calibration, revisions, comparisons, coverage) and require
`SUBJECTIVE_DEBUG`. Cursors are snapshot-pinned, bind run/publication/digest/
section/filters/limit, and never fall back to a newer latest publication. Errors
distinguish disabled (503), unknown run/publication (404), corruption (500),
malformed or mismatched cursor/filters (400) and expiry (410).

The Research UI adds a read-only **Scientific models** panel that labels
predictive probability, owner-observed outcome, retained-cohort calibration,
lower loss on paired observations and net resource change (not isolated
regeneration). It adds no edit, replay, experiment trigger or tick control.

## Experiment

`scientific_models@1` is an off-gate experiment with four shared-layout arms:
`models-science-off`, `models-season-resource`, `models-production` and
`models-measurement-coexistence`. Arms share seed, stochastic identity, roster,
layout and horizon (minimum 96 ticks). There are no preloaded models, scripted
success or guaranteed improvement; autonomous nulls are legal.

## Limitations

Disease is unavailable. Resource performance is net observed change, not a
physical regeneration rate. Production covers only existing categorical
experiments. Comparison is descriptive over retained owner-observed matched
cases. Predictive models are not objective truth, and no durable subjective
restart or capacity claim is made.

## Verification

```bash
uv run --frozen --python 3.12.14 pytest -q tests/unit/test_scientific_models_*.py
uv run --frozen --python 3.12.14 pytest -q -m integration tests/integration/test_scientific_models_runner.py
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

## See also

- [Scientific hypotheses](scientific-hypotheses.md)
- [Scientific replication](scientific-replication.md)
- [Measurement instruments](measurement-instruments.md)
- [Configuration](configuration.md)
- [Persistence](persistence.md)
