# Phase 4: Controlled Experiments and Qualification

Plan: [index.md](index.md)  
Tasks: 5–6  
Depends on: Phase 3 / Task 4

## Objective

Demonstrate elicitability, deterministic pairing, and replay without modifying a live world from the experiment harness. Document the limits of the simulated physical mechanics.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/experiments/models.py` | `ExperimentDefinition`, `ExperimentCondition`, `ExperimentSeedMatrix` | Reuse the existing paired layout, seed, and stochastic identity checks. |
| `src/experiments/coordinator.py` | `materialize_assignments`, `ExperimentCoordinator.run_all` | Each condition gets a different durable run ID even when it shares a stochastic identity. |
| `src/experiments/disease_scenario.py` | `disease_mechanics_scenario` | Existing executable fixture for the fictional-condition lane. |
| `src/experiments/commons_governance_scenario.py` | `commons_governance_two_pools_scenario` | Real ecology fixture for independent-stock and latest-runner-family qualification. |
| `src/experiments/catalog.py`, `src/experiments/__init__.py` | existing off-gate wrappers and exports | Register an opt-in experiment, not part of A–E. |
| `docs/development.md` | Python verification commands and migration/test gates | Keep the pinned runtime and coverage settings. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/experiments/disaster_scenario.py` | Create | Strict paired definition builder over a validated base. |
| `src/experiments/catalog.py`, `src/experiments/__init__.py` | Modify | Register and export `experiment_disasters` and the scenario builder. |
| `tests/unit/test_disaster_experiments.py` | Create | Six paired mechanics runs, seeded qualification, identity and provenance checks. |
| `docs/disasters.md` | Create | Configuration examples, trigger/replay semantics, reproduction and limitations. |
| `README.md`, `AGENTS.md`, `docs/configuration.md`, `docs/architecture.md`, `docs/development.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` | Update relevant sections | Index, current compatibility baseline, verification, and M8 ownership. |

## Task 5: Qualify scheduled and seeded experiments

### Intent

Make a controlled injection an auditable configuration intervention rather than an experiment-only write path.

### Implementation Steps

1. Add `disasters_scenario(base, *, treatment_entry, seed_matrix=None) -> ExperimentDefinition`. Require a valid v63 base with one rule, zero spontaneous probability and an empty schedule, a finite common tick cap beyond the injection tick, and treatment entry matching that rule. Fail closed on an incompatible base or entry; never silently rewrite the base horizon or enable sibling features.
2. Build `control` and `scheduled-shock` arms by replacing only the immutable schedule in the latter and validating both configurations through the ordinary runner seam. Preserve all other fields, the world/layout, founder roster, `seed`, stochastic identity, existing feature flags, and stop policy. Use `disasters@1` and a stable paired world group. With no seed matrix, use `ExperimentSeedMatrix(seeds=(base.seed,))`.
3. Register `disasters@1` where existing off-gate IDs are listed, add `experiment_disasters` using the existing wrapper pattern, and export both factories. Use the existing programmatic runner and authoritative event export; add no matrix grammar, research HTTP mutation endpoint, analytics metric, or custom experiment result schema.
4. Run a deterministic six-kind qualification matrix through `ExperimentCoordinator.run_all`; each kind gets its own matched control/treatment pair. Use the coordinator's ordinary distinct run IDs and assert equal stochastic identity and numeric seed. Derive measured physical prefixes from `ExperimentArmResult.committed_events` and the paired bootstrap through the last finalized tick before injection; compare ordered `(tick, effect kind, stable scenario target, before/after physical values)` tuples and detached physical state. Keep pre-treatment commands fixed by the trusted fixture where autonomous choices could confound the comparison; those commands still go through ordinary admission. Compare static scenario identities directly; for runtime-created infrastructure, compare its kind, topology, and condition instead of its run-scoped asset ID. Do not compare whole snapshot bytes, hashes, cause/event IDs, or assignment metadata across arms. Stop at the declared horizon, not at a desired outcome.
5. Separately run the same spontaneous-only configuration under the same explicit run ID and stochastic identity twice in isolated stores and require byte equality for canonical objective event output and checkpoint state with identical snapshot identity. Then compare a frozen fixture with a different known seed and a different trigger trace. Use Task 1's positive and negative vectors; arbitrary seeds need not diverge.

### Required Interfaces and Contracts

- The treatment input is a typed scheduled entry from the normal runner document. There is no callable that shocks a running engine.
- A scheduled event's objective receipt distinguishes `scheduled` from `spontaneous`; a skipped scheduled receipt is not an applied event. Compare ordinary stock/capacity/route effects, not narrative outcomes. Disease qualification inspects trusted objective evidence only; individual disease state is not published as a new surface.
- Report seed, paired arm, configured tick, finalized tick and a safe outcome code in test evidence; do not claim population-scale effects, statistical significance, or a real disaster model from the fixture.

### Requirement Evidence

- Original Request: seeded reproducibility and controlled experiment injection. Existing `ExperimentDefinition` contract provides paired identity; the new override is only the schedule.
- End-to-end cases reuse the existing disease experiment and the two-pool commons scenario, not only newly invented fixtures. Compose the existing disease contact-enabled arm with one managed renewable stock at the remote location (the fixture has no stock), explicit ecology/environmental settings and the existing `supply_chains` prerequisite. Use ordinary exposure chance zero in both members of the new pair so the extra opportunity is testable, retaining the existing founder/condition layout and transmission gate. Add the v63 surge rule at the existing settled location after its founder becomes active. Upgrade the existing two-pool commons arm by adding the v63 collapse rule on one managed pool; assert the second pool follows its ordinary trajectory until any ordinary downstream interaction. The original runner bytes and experiment registrations must remain unchanged.

### Error Handling and Logging

- Stable `disasters_experiment_base_invalid` / `disasters_experiment_schedule_invalid` codes for invalid factories; no document or target dumps. INFO registration can use experiment ID and arm count only.

### Tests

- `test_disaster_experiments.py`: six positive scheduled receipts, zero spontaneous events in both arms, equivalent physical prefixes under distinct durable IDs, measured deltas and non-target isolation, continuation/replay parity, skipped intervention, byte-equal same-identity twins and frozen contrasting seeds, condition fingerprints differ while stochastic identity matches, V1 gate excludes `disasters@1`.
- For treatment that is legitimately too late because of terminal stop, the general runner records no injection beyond its horizon; the reference paired fixture opts out of runtime-terminal stopping and must reach the injected tick.

### Acceptance Criteria

- Each shock is observed through ordinary execution and selected by configured input; the matched control has no shock. No test helper or experiment code directly changes objective state.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_disaster_experiments.py tests/unit/test_v1_regression_gate.py -q`

## Task 6: Document contracts and run release gates

### Intent

Make the feature reproducible and document exactly what the qualification establishes.

### Implementation Steps

1. Through the mandatory `$aif-docs` checkpoint, add docs with one exact programmatic configuration example for each kind, a zero-probability scheduled pair and a nonzero seeded example, the consumed-tick convention, trigger order, validation and bounds, baseline and recovery behavior, and a replay/checkpoint procedure. Explain finite one-shot pulses, no hazard propagation or geographic/biological realism, and what counts as skipped, applied, or absent.
2. Update the index, configuration and architecture compatibility notes. In project context, claim `disasters` as the final V4 flag only after replay and gates pass, correct the missing `ecological_feedback` entry in the architecture ownership enumeration, and retain prior dated pins and open V2/V3 flags. Record M8 delivery with verification evidence through the roadmap workflow; do not infer unrelated roadmap closure.
3. Check schema, canonical examples, read-only clients, no migration (`0017` stays), default runner/result v4/v2, 45 commands, 73 observer semantic kinds, 275 metric families, and unchanged `/v1` and `observer-protocol-v1`. Record verification results in the plan ledger only after commands pass.

### Required Interfaces and Contracts

- Documentation describes renewable or repairable stock/infrastructure under existing policies; no new recovery oracle, guarantee, or authoritative institutional labels. No real-world targets or organism parameters.
- A version change is only applied to the opt-in path and the necessary objective codec/checkpoint/projection path. No new SQL migration without a demonstrated persistence need; this plan relies on existing schema-tagged journal/checkpoint payloads.

### Requirement Evidence

- `.ai-factory/ROADMAP.md`, M8 Next Plans: last owned reserved pair, V4 invariants and appropriate authority. `.ai-factory/ARCHITECTURE.md`, Versioned Extension Contract: strict schemas, legacy replay, flags-off invariants.

### Error Handling and Logging

- A failed or skipped required gate is not qualification. Capture test name, reason code and tool exit only; examples use fictional generic IDs and omit private state, credentials and raw logs.

### Tests

- Validate documented examples with config/replay tests; no network or live database required. Existing architecture/import, V1/V2/V3, Alembic and prior-channel gates remain on; do not downgrade assertions for an enabled capability if only the old behavior should stay pinned.

### Acceptance Criteria

- Every test/verification gate below passes, documentation examples validate, and no legacy compatibility or ownership claim is made from an unexecuted check.

### Verification

- `uv run --frozen --python 3.12.14 pytest`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- `uv run --frozen --python 3.12.14 lint-imports`
- Check `git diff --check`, and check that no migration, new route/command, or client protocol change is included.

## Phase Risks and Mitigations

- Paired results can be misleading if initialization or stochastic identity differs. Construct arms by replacing the schedule only and assert pre-treatment equality of physical evidence, not equality of run envelopes.
- A deterministic mechanism example does not establish typical frequency or outcomes. Keep the documented claims bounded to executed mechanisms and configured probabilities.

## Phase Completion Checklist

- [x] Both tasks meet their acceptance criteria, verification is recorded, and the corresponding checkboxes in `index.md` are updated.

### Verification ledger (Task 6)

- `pytest`: 13356 passed, 5 skipped, 180 deselected
- `ruff check src tests`: clean
- `mypy src tests`: clean (3165 files)
- `lint-imports`: 25 contracts kept
- `git diff --check`: clean
- No Alembic `0018`; `/v1` and `observer-protocol-v1` unchanged; twelve V4 flags owned
