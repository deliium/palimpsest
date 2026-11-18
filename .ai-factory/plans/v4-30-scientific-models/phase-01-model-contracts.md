# Phase 1: Hypotheses, forecasts, and predictive accounting

Plan: [index.md](index.md)
Tasks: 1–4
Depends on: none

## Objective

Introduce a pure, owner-scoped scientific-model contract with immutable prior
forecasts, deterministic probability semantics, and honest observation limits.
Do not widen legacy hypothesis outcomes or reinterpret their confidence.

## Current-Code Evidence

| Path | Symbols / relevant section | Why it matters |
| --- | --- | --- |
| `src/agents/cognition/world_model.py` | `CausalOutcome`, `CausalHypothesis`, `SeasonSuccessorTable`, `CausalWorldModel` | Existing causal outcomes are danger/help/search success/failure, not arbitrary physical quantities. Season history is observed, not an imported calendar. |
| `src/agents/cognition/experimentation.py` | `HypothesisClaim`, `ExperimentHypothesis`, `confidence_milli_from_masses`, `HypothesisConditionSlot` | Experimental source claims and support-ratio confidence must remain unchanged. |
| `src/world/observations.py` | `ObservedResource`, `ObservedOccurrence`, `Observation.season` | Local quantity and redacted occurrence facts are available; regeneration/maxima are omitted. |
| `src/world/experimentation.py` | `ExperimentProcessToken`, `ExperimentOutcomeClass` | Production experiments already have five categorical outcomes. |
| `src/world/environment.py` | module authority contract | Calendar/yield rules are engine-only inputs. |

## Files to Change

All paths in this table are new unless marked modify.

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/agents/cognition/scientific_models.py` | create | Frozen types, policy, caps, validation, model-hypothesis lineage. |
| `src/agents/cognition/scientific_model_derivation.py` | create | Owner-observed regularity and experimental-hypothesis adapters. |
| `src/agents/cognition/scientific_model_prediction.py` | create | Immutable paired forecasts and deterministic distributions. |
| `src/agents/cognition/scientific_model_scoring.py` | create | Owner-local performance, calibration, paired comparison. |
| `src/agents/cognition/__init__.py` | modify | Explicit reviewed exports, not wildcard re-exports. |
| `tests/unit/test_scientific_models_contract.py` | create | Contract, caps, identity, ownership and invalid inputs. |
| `tests/unit/test_scientific_models_derivation.py` | create | Domain-specific admissible derivation. |
| `tests/unit/test_scientific_models_prediction.py` | create | Forecast freezing/distributions. |
| `tests/unit/test_scientific_models_scoring.py` | create | Exact arithmetic and comparable cohorts. |

## Task 1: Define typed model hypotheses, models, and bounded state

### Intent

Every executable model must derive from a recorded hypothesis, without forcing
season/resource claims into the legacy experiment or causal outcome enums.

### Implementation Steps

1. Add locked `SCIENTIFIC_MODELS_POLICY_VERSION = "scientific-models.v1"` and
   frozen `ScientificModelPolicy`, `ModelHypothesis`, `ModelHypothesisRevision`,
   `PredictiveModel`, `ModelRevision`, `ScientificModelLedger`, `ForecastCase`,
   `ModelPrediction`, `ModelObservedOutcome`, `ModelExecutionBinding`,
   `ModelPerformanceSummary`, `ModelComparison`, and `ModelCoverageNotice`.
2. A `ModelHypothesis` is an owner belief with target kind, explicit categorical
   claim, conditions, source kind, source references/revision digest,
   supporting/contradictory receipt references, creation tick and monotonic
   revision index. Sources are `observed_regularity` or
   `experiment_hypothesis`; optional causal links are provenance only.
   Models always reference an immutable model-hypothesis revision.
3. Lock target kinds: `season`, `resource_regeneration`,
   `production_outcome`, `disease_risk`. The resource target's estimand is
   explicitly `observed_net_quantity_change`, not true regeneration rate.
   Disease has capability status `unavailable_no_observable` and cannot issue a
   forecast or receive a score.
4. Identity uses SHA256 of canonical versioned material, owner identity and a
   monotonic local sequence where required; never global RNG, wall clock or
   built-in `hash()`. Model identity excludes growing evidence/performance;
   revision identity includes immutable source/parameter content.
5. Fixed owner bounds: 32 hypotheses, 64 models (two per hypothesis), 128
   pending cases, 512 terminal cases, 512 revision records, 256 derivation
   observation samples and 64 empirical context bins per model. The hypothesis
   budget includes all three active domains. A case contains exactly two
   candidate predictions. Never evict a pending case or a revision it pins.
   Prune oldest terminal cases/revisions by `(tick, id)` only when unpinned;
   increment explicit eviction counters and first-retained watermarks.
   If no legal eviction exists, refuse new admission with `retention_cap`.
   Empirical-bin exhaustion refuses unseen contexts, never merges them.
6. Validate exact integer types (reject bool), probability sums, finite quantities,
   owner consistency, categorical alphabets, increasing ticks/revisions, no
   duplicate IDs and no mutable nested collections. Counters are nonnegative
   integers; bounded collection caps do not reset monotonic sequences.
   Revision reasons are closed: `formulated`, `source_changed`,
   `parameter_updated`, `retired`. Source evidence references may become
   explicitly unavailable after sample retention; model/source revision
   references pinned by retained forecasts must remain closed. Missing opaque
   evidence is coverage, not permission to fabricate a receipt.
7. Bound nested state: eight source-lineage references and eight conditions per
   hypothesis/revision; 64 supporting and 64 contradictory evidence references
   per hypothesis/revision; the exact target alphabet (at most five entries) per
   probability vector; two opaque outcome references per case (sufficient to
   record ambiguous execution). Each empirical bin has one count per class.
   Arbitrary nested mappings/lists and unbounded audit trails are invalid.
8. Coverage is at most 128 aggregated `(reason_code, target_kind)` notices with
   first/last tick and occurrence count. Declare at most 32 closed reason codes
   and four target kinds so every key fits; repeats increment counters rather
   than append rows. Counters survive evidence eviction. Enforce nested limits
   in constructors, transitions and decoding, not just publication.
9. Model hypotheses/models have lifecycle status `active|suspended|retired`.
   Add revision reasons `suspended` and `resumed` to the existing closed set;
   distinguish lifecycle/source changes from parameter updates. Forecast state
   is independent of the current model's lifecycle status.

### Required Interfaces and Contracts

- `empty_scientific_model_ledger(owner_id) -> ScientificModelLedger`.
- New sidecar does not alter `CausalOutcome`, `HypothesisClaim`,
  `ExperimentOutcomeClass`, or legacy confidence arithmetic.
- Owner values are private runtime state. Published identifiers are separately
  tokenized in Phase 3. Public `repr` includes counts/IDs only.

### Error Handling and Logging

Use safe `scientific_model_*` error codes. DEBUG logs contain tick, counts,
target-kind enum and reason codes only; never conditions, target IDs as payload
surrogates, observations, claims, distributions, outcomes or state digests.
Malformed input fails closed; a capacity refusal is a coverage notice, not an
exception that aborts a world tick.

### Tests

Test foreign-owner references, unknown fields/enums, bool-as-int, bad sums,
NaN/inf, duplicate IDs, frozen nested values, pinned-history retention and
deterministic identities. Property-test caps and monotonic sequences.

### Acceptance Criteria and Verification

Every model has a source hypothesis revision; invalid disease predictions cannot
be represented; no legacy enum/confidence contract changes.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_contract.py -q`

## Task 2: Derive domain-specific hypotheses from admissible owner evidence

### Implementation Steps

1. Add `derive_model_hypotheses(ledger, observation, *, experiment_ledger,
   causal_world_model) -> ScientificModelLedger`. Accept detached owner-safe
   inputs only; validate all owners and process observations once per increasing
   observation key. Repeated keys are a no-op; out-of-order keys fail closed.
2. For season, retain consecutive owner-observed season samples. With at least
   two lag-two sample pairs for the same starting season, formulate the modal
   season-at-two-boundaries hypothesis (ties follow `Season` declaration order).
   A lag-two pair has samples at `s` and `s+2`, with `s+1` also observed.
   Missing season or skipped observation ticks do not create a transition.
   The claim is an empirical hypothesis, not a calendar fact; optional
   `SeasonSuccessorTable` links never supply hidden season length/order.
3. For a visible resource, retain `(entity, location, kind, unit, tick,
   quantity_milli)` observations. Convert through `Decimal(str(quantity))`
   using round-half-even at 1/1000 unit. Formulate a hypothesis after two
   lag-two pairs for the same resource identity/unit/location and starting
   conditions; all three intervening samples must identify that same resource.
   Target classes are `decrease`, `unchanged`, `increase`.
   This predicts net visible quantity change, potentially confounded by harvest,
   transfers or depletion. Never infer unobserved regeneration/maxima.
4. For production, derive from the owner's non-retired, non-superseded
   `ExperimentHypothesis` with a predicted outcome and process in
   `harvest/craft/build/repair/store`. Freeze operator, exact observed operand
   IDs, process, conditions and source revision. Do not claim a numeric yield or
   predict arbitrary ordinary `Craft` completion from an experiment claim.
5. Use a canonical condition subset of location, season, weather and day phase,
   copied only when present; missing required conditions are unsatisfied.
   Resource adds resource identity/unit; production adds the full exact claim.
   Source confidence remains metadata and is never used as a probability.
   A changed modal claim/source revision appends a model-hypothesis revision.
6. Return an unavailable disease notice; generic danger/health/hazard facts are
   not disease evidence. Do not add a disease model or activate `epidemics`.
   No speech decoder, automatic testimony adoption or global hypothesis store
   is introduced by V4-30.
7. Reconcile derived models before new issuance. Missing retained experimental
   sources, unavailable required observations and unsatisfied current required
   conditions suspend issuance with an explicit reason, never delete an issued
   case. The same active source with satisfied conditions resumes the same
   model IDs and appends a `resumed` revision. Explicitly retired/superseded
   sources permanently retire their models; replacement sources create successor
   hypothesis/model identities with lineage, not resurrection.
8. Changed source prediction/condition values append a source/model revision
   before issuance. Keep model identity for the same source identity, target,
   unit, horizon and predictor variant; condition values belong to revisions and
   empirical context keys. Changed target identity, unit, horizon or condition-slot
   definition creates a new identity; incompatible contexts inherit no counts.
   Observed-regularity sources suspend while their required target/context is
   absent, otherwise revise from eligible lag-two evidence. Never look up a
   current source to rewrite/cancel an existing forecast: it may still settle
   after source loss or retirement.

### Contracts, Errors and Logging

No adapter receives `EnvironmentalDynamicsSpec`, `ProductionCatalog`,
`WorldState`, event repositories or objective law rows. An absent source means
`source_missing`; an ambiguous/changed identity is `not_comparable`, not invented
training evidence. Log counts/reasons, never source payloads.

### Tests

Use real `ObservedResource` and `Observation.season` objects plus a real
`ExperimentHypothesis` fixture. Cover two-pair thresholds, missing/occluded
resources, unknown unit, interventions causing net decreases, source revision,
retired hypotheses, no calendar access and disease unavailable.
Test active→suspended→resumed, active→retired, successor lineage, condition/unit
changes and source eviction while a case is pending. Retired models cannot
issue again; existing cases retain their frozen source payload.

### Acceptance Criteria and Verification

All supported domains originate in explicitly retained, fallible hypotheses;
no legacy source is falsely retyped into an unrelated predictive claim.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_derivation.py -q`

## Task 3: Freeze prior predictions and deterministic predictive distributions

### Implementation Steps

1. Create two candidates per admitted hypothesis:
   `hypothesis_baseline_v1` and `empirical_context_v1`. Baseline assigns weight
   2 to the source claim and 1 to every other class. Empirical assigns weight
   `past_resolved_count[class] + 1` in the exact origin context; zero samples
   yield a uniform distribution. Neither uses source support-ratio confidence.
2. Normalize weights to 1000 with integer largest-remainder allocation; remainder
   ties and argmax ties follow the fixed target alphabet. Confidence is the
   probability milli of the chosen class. Alphabets are four `Season` values,
   three resource-change values, or five `ExperimentOutcomeClass` values in
   declaration order. Probabilities are subjective estimates, not world chances.
3. `issue_model_forecasts(ledger, observation) -> ScientificModelLedger`
   deterministically selects at most one eligible hypothesis per owner/tick,
   round-robin over stable hypothesis IDs using a retained cursor. Emit one
   common case with both candidate forecasts or neither; never admit only the
   better-looking model. Cases pin model/source revisions and parameter digests.
   Eligibility requires active source/model status, matching owner and satisfied
   current required conditions. Enforce one issuance per integer tick even if
   an invalid caller supplies a second increasing revision key at that tick;
   suppress the second issuance without advancing the cursor.
4. Freeze source observation tick `t`, input observation key, training high-water
   mark, origin conditions, source revision, target identity/unit, both
   distributions and point predictions. Candidate is committed only after
   ordinary finalization of tick `t`. Set
   `committed_after_tick=t`, `target_observation_tick=t+2`.
   For production the exact eligible execution tick is `t+1`.
5. This deliberately skips the immediately following observation at `t+1`:
   its physical outcome already exists when tick `t` finalizes. Predictions
   never target the resolving tick or an event received later with an old tick.
   An aborted preparation leaves no committed case.
6. New source/model revisions affect only future cases. Replayed issuance with
   the same observation key/case ID is an exact no-op; changed bytes for that
   identity are corruption. No command is created, replaced or submitted.

### Contracts, Errors and Logging

Forecasts carry `issued_observation_tick`, `committed_after_tick`,
`target_observation_tick`, source/model revision IDs and a frozen training
watermark. Reject a distribution trained on its target or future receipts.
Emit only metadata `forecast_issued`/`forecast_suppressed` counts and codes.

### Tests

Exact distributions and remainder allocation; source confidence 0 versus 1000
does not alter probabilities; both models share a case; source/model revision
cannot rewrite a forecast; same-tick and next-boundary targets rejected;
deterministic fair selection and capacity admission.

### Acceptance Criteria and Verification

A serialized case is independently sufficient to identify what was predicted,
with what confidence, from which model version, before which future outcome.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_prediction.py -q`

## Task 4: Implement observation-relative calibration, revision and comparison

### Implementation Steps

1. Add pure `score_model_prediction(prediction, observed_class)` and
   `compare_model_predictions(cases, model_a, model_b)`. Outcome scoring uses
   the frozen distribution, never current model parameters. `unexpected` is an
   ordinary fifth class here; leave legacy hypothesis contradiction semantics
   untouched.
2. Keep exact per-case Brier numerator
   `sum((p_milli[k] - 1000 * indicator(k == y)) ** 2)` in `[0, 2000000]`.
   Report `mean_brier_millionths = round_half_even(sum_numerators / n)`;
   smaller is better. Also report hit count and `hit_share_milli`. No log-loss,
   p-values, scientific quality score or cross-domain scalar is introduced.
3. Ten confidence bins: `min(confidence_milli // 100, 9)`.
   Store count, sum-confidence-milli and hit count per bin. Calibration gap milli
   is `round_half_even(sum(abs(1000*hits_bin - sum_confidence_bin)) / n)`.
   Empty denominators return unavailable/null, never zero.
4. Comparison is paired on the intersection of identical case IDs, target,
   owner, context definition, unit, horizon and outcome channel; score both
   candidates against the same outcome. Publish paired count, exclusions,
   per-model loss and signed `a_minus_b_brier_millionths`. At least three
   paired outcomes are required for a descriptive `lower_loss_a`,
   `lower_loss_b`, or `tied`; otherwise `insufficient_samples`.
   Never compare owners or target kinds as a ranking.
5. After resolving/scoring old cases, append an immutable model revision for
   empirical count updates; maintain separate revision and case sequences.
   Performance changes are not automatic hypothesis truth promotion. Existing
   pending predictions remain pinned to old parameters. Keep owner comparison
   available in its sidecar; do not feed detached analysis back to cognition or
   change action selection.
   Persist summaries and comparisons keyed by target/context/unit/horizon and
   model pair, recomputing them from the retained terminal cohort after scoring
   or eviction. Cap performance summaries at `64*64=4096` and pair comparisons
   at `32*64=2048`, derived from the model/hypothesis and context caps; no
   independent unbounded comparison registry. An unavailable context gets a
   coverage notice, never an implicit pooled summary.
6. Summaries cover the retained case cohort only. Include evicted/missing,
   pending, unavailable, not-attempted and not-comparable counts separately.
   Do not report these statistics as lifetime accuracy after eviction.

### Error Handling and Logging

Reject out-of-alphabet outcomes, mixed cohorts and mutated case records.
Missing outcomes never count as failures or zero-loss samples. DEBUG contains
scored/revised counts and safe codes only, not predictions/outcomes/loss vectors.

### Tests

Hand-computed perfect/wrong/uniform forecasts, 1000-confidence last bin, exact
ties and rounding, class-count-dependent Brier range, sample thresholds,
selective missingness and different cohort/horizon/unit exclusions. Verify
calibration is computed over predictive confidence, not hypothesis support.

### Acceptance Criteria and Verification

Both an agent and a researcher can compare two models on the same prior
forecasts without asserting truth, causality, or universal scientific quality.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_scoring.py -q`

## Phase Risks and Mitigations

- Resource increase is not proof of regeneration: preserve the exact net-change
  estimand in every type/export/UI label.
- Small cohorts can mislead: minimum count, retained-window label and paired
  exclusions accompany every comparison.
- Additional hypothesis types can blur authority: they are owner beliefs in a
  new sidecar, never world contracts or changes to legacy source enums.

## Phase Completion Checklist

- Each task satisfies its contract and focused tests.
- No world authority import or legacy confidence reinterpretation was added.
- Update task checkboxes only in `index.md` after verified completion.
