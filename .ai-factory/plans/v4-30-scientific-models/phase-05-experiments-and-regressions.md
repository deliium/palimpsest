# Phase 5: Scientific demonstrations and adversarial regressions

Plan: [index.md](index.md)
Tasks: 17–20
Depends on: Tasks 1–16

## Objective

Demonstrate prior prediction and descriptive model comparison with real runner
artifacts, while preserving honest nulls, scientific boundaries and legacy runs.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
| --- | --- | --- |
| `src/experiments/replication_scenario.py` | `scientific_replication_scenario` | Explicit off-gate arms over existing science configuration. |
| `src/experiments/catalog.py` | `experiment_scientific_hypotheses`, `experiment_scientific_replication`, `experiment_measurement_instruments` | Public registration wrappers and safe metadata logging. |
| `tests/unit/test_environmental_dynamics_causal.py` | observed season learning tests | Season evidence must not import a hidden calendar. |
| `tests/unit/test_scientific_hypotheses_lifecycle.py`, `test_replication_checkpoint.py`, `test_measurement_recovery.py` | science lifecycle/recovery tests | Preserve old hypothesis and pending-state contracts. |
| `tests/unit/test_v1_regression_gate.py`, `test_v2_scientific_invariants.py` | flags-off gates | New science behavior cannot alter V1/off-path results. |
| `tests/architecture/test_v4_architecture_invariants.py`, `test_v4_context_registry.py` | authority and context pins | No additional V4 ownership/context slot. |
| `docs/development.md` | verification commands | Keep coverage and distinguish environment-gated checks. |

## Files to Change

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/experiments/scientific_models_scenario.py` | create | Reproducible off-gate scientific-model scenario. |
| `src/experiments/catalog.py`, `src/experiments/__init__.py` | modify | Explicit scenario wrapper/export; no changes to A–E. |
| `tests/unit/test_scientific_models_scenario.py` | create | Arm keysets, provenance and determinism. |
| `tests/unit/test_scientific_models_temporal.py` | create | Precommit, delayed evidence and revision attacks. |
| `tests/unit/test_scientific_models_compatibility.py` | create | Supported activation/codec combinations. |
| `tests/unit/test_scientific_models_properties.py` | create | Boundedness/idempotency/scoring properties. |
| `tests/integration/test_scientific_models_runner.py` | create | Real owner→forecast→future outcome→comparison run. |
| `tests/architecture/test_scientific_models_boundaries.py` | modify | Extend tests from Task 16 to no-oracle signatures and authority pins. |

## Task 17: Add an off-gate reproducible scientific-model experiment

### Implementation Steps

1. Add `SCIENTIFIC_MODELS_EXPERIMENT_ID = "scientific_models@1"`,
   `scientific_models_scenario(base, *, seed_matrix=None, max_ticks=96)`,
   and `experiment_scientific_models` catalog wrapper. Validate positive horizon
   at least 96, explicit seeds and compatible base config.
2. Define four arms: `models-science-off`, `models-season-resource`,
   `models-production`, `models-measurement-coexistence`.
   All use existing accepted runner fields. Off arm has science false;
   season/resource uses science prerequisites plus environmental dynamics and
   visible local resources; production uses known `BoundedExperimentationSpec`
   tool/material laws; coexistence additionally uses explicit measurement tools
   and the existing v57 measurement spec.
3. Declare all differing settings; share seed, stochastic identity, founder
   roster, comparable world layout, stop horizon and source-free initial owner
   state. These arms are mechanism demonstrations, not a one-factor causal
   contrast; do not label their differences causal treatment effects.
4. No preloaded correct model, source-hypothesis content, scripted discovery,
   guaranteed improvement or forced autonomous outcome. Production uses existing
   scientific action selection; no new action controller. Missing autonomous
   tests/models and unavailable disease are legal declared nulls.
5. For deterministic test-only mechanism coverage, use a trusted ordinary-command
   arbiter to schedule existing `Wait`/`Experiment` commands and a separate
   observation-derived source-building prefix. Declare it controlled, not
   autonomous. Include at least one deliberately wrong prior model and
   contradictory later outcomes. Do not require the empirical candidate to win.

### Contracts, Errors and Logging

Registration logs experiment ID/arm count only. Invalid base combinations fail
closed, never silently enable a reserved capability. Keep the experiment outside
V1 A–E/reference gate and avoid creating a new benchmark registry or matrix factor.

### Tests

Arm names/changed fields, exact config keysets, seed identity, no seeded owner
content, disease unavailable and deterministic twins. Run the public scenario
builder, not only synthetic ledger constructors.

### Acceptance Criteria and Verification

The catalog can construct reproducible demonstrations without scripting
scientific success or claiming controlled arms are emergent behavior.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_scenario.py -q`

## Task 18: Add adversarial temporal and provenance regressions

### Implementation Steps

1. Build a three-boundary test harness with concrete `ObservationProvenance`,
   pending commands and real finalization: observation `t` issues; finalization
   of tick `t` commits; eligible production event is `t+1`; observation `t+2`
   supplies the result. Assert the exact order and canonical payloads.
2. Attack with same-tick known outcome, observation `t+1`, late old occurrence,
   mismatched sample/receipt tick, source revision after issuance, changed
   current confidence, trimmed source history, replayed delivery, bystander
   reports, foreign owner and an adversarial resource-name token.
3. Test missing production action versus denied action versus matching completed
   experiment. Effective-command substitution must alter only the separate
   binding, not the issued distribution. An occurrence with operator only must
   not acquire invented process/operand details.
4. Test scoring mutation attacks: updated model parameters cannot change an old
   loss; one model missing a case cannot improve paired count by substitution;
   unknown outcomes cannot become failures; duplicate roots/receipts never
   increase n. Model predictions are not adopted from `hyp_v1`, `rep_v1` or
   `msr_v1` speech.
5. Freeze a case, restart after world commit and before acknowledgment, then
   settle its later outcome. Compare with uninterrupted execution and assert
   cognition/provider was not called during pending recovery.
6. Suspend, resume, retire and replace sources between issuance and target.
   Old forecasts settle from pinned payloads; inactive sources cannot issue;
   resumption cannot fill a missed target retrospectively. Include a
   loop-boundary command modifier to prove binding consumes the final
   `loop_result.command`, not the pre-loop argument.

### Errors, Logging and Tests

Malformed chronology/reference payloads fail safe validation. Legitimate missing
observations report unavailable. Captured logs must not contain adversarial
sentinels. Tests use no live provider or hidden-law access in cognition.

### Acceptance Criteria and Verification

Every scored case demonstrates immutable prior commitment, later observation
and exactly-once accounting under both normal and adversarial paths.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_temporal.py tests/unit/test_scientific_models_recovery.py -q`

## Task 19: Lock the supported configuration and compatibility matrix

### Implementation Steps

1. Encode the index's supported-combination table as parameterized tests:
   science off; science on/v56 without measurement; science on/v57 with
   measurement; science prerequisite failure; optional environmental facts
   absent; optional production sources absent; unavailable disease; read store
   independently enabled/disabled.
2. Existing science activation owns V4-30 runtime behavior: no
   `scientific_models` capability slot, mode, runner sibling or v58. No new world
   command, event, observation field, replay pair or domain envelope is needed.
   Measurements still select replay28/v26; travel/infrastructure/prior runs retain
   their feature-selected pairs.
3. Assert finalization v1/v2/v3 remain accepted with exact old keysets/bytes;
   predictive candidate selects v4; no candidate leaves old selection unchanged.
   Predictive leaf state and publication versions are independent of runner and
   world replay versions.
4. Preserve V1 flags-off history, prior catalog prefix, unowned capability errors,
   import boundaries, API/protocol identity, `prepare_parallel=False`, and
   blank-slate admissions. No SQL migration or excluded dependency.
   Pin the new store in all blank-slate enumerations and the benchmark map.
   Actual populated new-owner content must reject admission; a pristine empty
   frozen ledger passes. The composition-only result field adds no keys to
   legacy runner-result wire documents.

### Errors, Logging and Tests

Prerequisite/unknown version errors retain existing fail-closed semantics.
Assert no predictive log or state appears science-off. When a historical pin
test encodes the current catalog count, update only the current count; never
rewrite an old wire fixture to erase supported history.

### Acceptance Criteria and Verification

All table rows have executable evidence and no new behavior slips onto a
legacy/science-off path.

- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_compatibility.py tests/unit/test_compatibility_matrix.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py -q`
- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_v4_context_registry.py -q`

## Task 20: Verify scientific arithmetic, boundedness and a real runner artifact

### Implementation Steps

1. Add Hypothesis tests over valid categorical distributions and observation
   sequences: normalized probability sum 1000; Brier range; exact zero for a
   perfect point forecast; nonnegative calibration; idempotent duplicates;
   stable IDs/revision monotonicity; no owner aliasing; all collection caps.
2. Exercise retention with pinned pending forecasts and source history trimming.
   Verify terminal-case eviction changes retained-cohort counts/watermarks but
   never resets empirical training counts or pretends to preserve lifetime
   score coverage. If empirical context bins fill, unseen contexts are skipped
   with coverage rather than merged.
   Saturate nested evidence references and notice keys too; assert limits and
   surfaced omissions. Snapshot caps retain complete pairs/required revisions
   and compute retained-cohort scores, not pre-cap denominators.
3. Complete a real runner using the scenario from Task 17 and the controlled
   mechanism prefix. Obtain at least three eligible paired production cases
   with observed categorical outcomes; also exercise actual season/resource
   observations. Publish one real snapshot and independently recompute its
   paired Brier/calibration from prior prediction/outcome rows.
   Span at least two issuance windows. Discard the live runner and exercise
   completed result → real collector → real builder → metric documents; assert
   all six families and exact counts, with normalized analysis passed once.
   Then publish/read through actual `create_app` attachment. Optional missing
   global event capture must not erase owner-only predictive analysis.
4. Check known-empty/unassisted-null artifacts separately from controlled
   mechanism success. Legal failure to form a model is scientifically valid;
   it must not satisfy a test that claims model performance was exercised.
5. Run deterministic twins and a fork differing only after forecast commitment.
   Prefix forecasts remain equal; changed child outcomes may produce different
   losses without modifying the parent's stored predictions.

### Errors, Logging and Tests

Integration uses existing in-memory runtime/engine seams; mark as integration
without assuming PostgreSQL. No raw fixture payloads in operational logs.
Report explicit unexecuted prerequisites for any optional scale/browser lane;
do not turn skips into passes.

### Acceptance Criteria and Verification

At least one genuine runner-derived artifact proves the full scientific
forecast→later observed outcome→paired comparison contract, beyond unit
arithmetic fixtures.

- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_properties.py -q`
- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m integration tests/integration/test_scientific_models_runner.py tests/integration/test_scientific_models_store_api.py -q`

## Phase Risks and Mitigations

- Controlled demonstrations may look like emergence: declare mechanism versus
  unassisted evidence in tests/docs and retain honest nulls.
- Domain examples exceed existing physics: resource is a net-change estimand,
  production is categorical experimental outcome, disease remains unavailable.
- High-level green tests may miss selection bias: assert matched case IDs and
  denominator exclusions explicitly.

## Phase Completion Checklist

- Scenario, adversarial, compatibility, property and real-artifact lanes pass.
- No skipped lane is recorded as executed or certified.
- Update progress only in `index.md`.
