# Phase 4: Experiment, compatibility gates, and documentation

Plan: [index.md](index.md)  
Tasks: 7–9  
Depends on: Phase 3 / Task 6

## Objective

Exercise the mechanics in a reproducible off-gate experiment, prove durable restoration and legacy parity, and document the feature without suggesting the model represents real disease.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
| --- | --- | --- |
| `src/experiments/catalog.py` | `experiment_measurement_instruments`, `OFF_GATE_MATRIX_EXPERIMENT_IDS`, `v1_regression_profile` | Existing opt-in experiment registration and baseline separation |
| `src/experiments/science_diffusion_scenario.py` | `science_diffusion_scenario`, `ExperimentSeedMatrix` | Typed paired-arm composition |
| `src/simulation/replay.py`, `tests/integration/test_runner_finalization_recovery.py` | `ReplayService.replay`, `open_durable`, repository fixture | Objective continuation seam; the existing runner test supplies repository setup, not a new subjective recovery contract |
| `docs/development.md` | Verification lanes | Pinned Python, coverage-enabled tests, disposable integration target |

## Files to Change

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/experiments/disease_scenario.py` | Create | Trusted paired fixture builder |
| `src/experiments/catalog.py`, `src/experiments/__init__.py` | Modify | Off-gate registration and public experiment facade |
| `tests/unit/test_disease_scenario.py` | Create | Pairing, twin-run reproducibility, and positive-control transitions |
| `tests/integration/test_disease_durable_replay.py` | Create | Durable historical read and process-loss recovery |
| `docs/disease-mechanics.md`, `docs/configuration.md`, `docs/architecture.md`, `docs/development.md`, `README.md` | Create/modify | Mandatory `/aif-docs` checkpoint and documentation discoverability |
| `.ai-factory/ARCHITECTURE.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ROADMAP.md` | Modify during implementation | Update current pins and ownership, then mark only this M8 slice delivered |

## Task 7: Register a paired synthetic experiment

### Intent

Demonstrate controllable, reproducible behavior without adding a metric family or changing a baseline.

### Implementation Steps

1. Add `disease_mechanics_scenario(base, *, seed_matrix=None)` with experiment ID `disease_mechanics@1`; expose `experiment_disease_mechanics` following `experiment_measurement_instruments` and add the ID to `OFF_GATE_MATRIX_EXPERIMENT_IDS`. Use existing `ExperimentDefinition`, `ExperimentCondition`, seed matrix, and off-gate validation.
2. Use a bounded deterministic fixture with the existing infrastructure-network config prerequisite: synthetic founders with two settled together and one remote; the lexically first colocated founder starts latent. Use `Wait` through an existing deterministic test policy, a finite eight-tick horizon, no early stop, no LLM; the catalog config uses ordinary simulation composition. Do not script post-bootstrap infection, symptoms, or recovery.
3. Use `no-transmission` and `contact-enabled` conditions. Keep disease enabled in both, with equal seeds, founder roster, topology, stochastic comparison identity, and schedule. Set exposure and symptom milli to 1000, mortality to 0, latent duration to one tick, active duration to two ticks, and immunity on. Change only transmission milli (0 vs 1000). Replay authoritative state during fixture checks; do not add an HTTP disease-state route or public metric.

### Contracts / evidence

- The original request asks for configuration and determinism. Use run-level config only; retain the existing V1 gates A–E and off-path bytes. Mechanism fixture success does not imply emergence or medical validity.
- Reject an incompatible base with a typed validation error; log experiment ID, arm count, and safe reason only. Never log founder condition or transition details.

### Tests, acceptance, and verification

- In `tests/unit/test_disease_scenario.py`, verify the canonical configurations differ only at `disease_mechanics.transmission_chance_milli` (condition IDs are outside runner config). Run each arm twice in isolated stores with the same `RunId`, `WorldId`, seed, and command/request IDs for exact bytes and digests within that arm. Compare semantic outcomes, not hashes, across arms: only the contact-enabled arm's colocated susceptible changes state, while its remote agent stays susceptible. Verify off-gate registration and unchanged V1 case IDs.
- Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_disease_scenario.py tests/unit/test_v1_regression_gate.py -q`.

## Task 8: Verify durability, compatibility, and trust boundaries

### Intent

Prove that the disease channel survives real storage and restore without entering agent-facing surfaces, and that off-path runs still match existing artifacts.

### Implementation Steps

1. In `tests/integration/test_disease_durable_replay.py`, reuse disposable-DB setup from `tests/integration/test_runner_finalization_recovery.py`. Write an older checkpoint and a tail containing at least one latent and one symptom boundary; recreate the replay service with fresh repository interfaces to the same DB. `ReplayService.replay` without policy must restore both historical and head observations as read-only. At the head, pass the verified persisted policy and use `ReplayService.open_durable` plus recorded commands to continue; compare to an uninterrupted objective twin with the same run and command identities. Check mismatched policy rejection, preserved redaction, and Alembic `0017`. Do not use pending-subjective recovery as a substitute for objective restore.
2. Verify disease with neither, either, and both inherited travel/instrument channels using real existing fixture composition and ordinary commands. Verify prior checkpoint/event pairs using representative measurement and infrastructure fixtures, and V1 golden runner/result bytes. Run the V4 scaffolding/registry/version gates and scientific invariants.
3. Record lanes actually executed and report missing infrastructure as unexecuted, not passed. No database credentials, private event payloads, participant condition, or observation dumps in logs.

### Contracts / evidence

- `.ai-factory/ROADMAP.md` M8 requires a proven replay/migration trigger; `RULES.md` requires disposable named test DBs. Corrupt payloads must fail closed, not be treated as missing disease.
- Preserve `/v1` and `observer-protocol-v1`; keep existing trusted event/checkpoint reads separate from owner-visible observation. This is not certification of browser, scale, or prevalence.

### Tests, acceptance, and verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_disease*.py tests/unit/test_measurement_replay.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_compatibility_matrix.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_versioning_reservations.py tests/unit/test_v4_scaffolding_gate.py tests/unit/test_alembic_head_pin.py tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_v4_context_registry.py -q`
- `uv run --frozen --python 3.12.14 pytest` with coverage enabled; `uv run --frozen --python 3.12.14 ruff check src tests`; `uv run --frozen --python 3.12.14 mypy src tests`; `uv run --frozen --python 3.12.14 lint-imports`.
- With a configured disposable `PALIMPSEST_TEST_DATABASE_URL` whose DB name matches project rules: `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_disease_durable_replay.py -q`.
- Acceptance: enabled replay and recovery match live outcomes; previously accepted versions remain readable; the V1 gate remains unchanged; no unexecuted lane is reported as passed.

## Task 9: Complete the mandatory documentation checkpoint

### Intent

Make the opt-in mechanics reproducible and clearly limited.

### Implementation Steps

1. Use `/aif-docs` to create `docs/disease-mechanics.md` with the exact config keyset, valid/invalid gate combinations, paired synthetic fixture, boundary ordering, symptom/contact visibility, version selection, and trusted replay versus agent observation. State the known limitations: single fictional condition, no real pathogen, no epidemiological calibration or forecasting, no route or presentation overlay, and no diagnosis or infection-state access for agents.
2. Link the page from `README.md` and relevant `docs/configuration.md`, `docs/architecture.md`, and `docs/development.md` sections. Update current pins and ownership in AI Factory context once proven. Keep M8 open for `ecological_feedback` and `disasters`.
3. Validate the documented JSON with the strict decoder in the Task 1 tests; update examples if validation rejects one. Do not log examples containing credentials or private participant state.

### Contracts / evidence

- Docs are mandatory by configured plan settings. Reconcile stale roadmap historical counts against the V4-33 current baseline without rewriting historical references.

### Tests, acceptance, and verification

- Compare every documented version, flag combination, and fixture invocation against the passing Task 1/7 tests; run `git diff --check`. Verify all added relative documentation links resolve and acceptance receipts distinguish executed and skipped lanes.

## Phase Risks and Mitigations

- Durability regressions can pass a pure replay unit test: retain the real repository integration case and report skipped coverage explicitly.
- A paired fixture can accidentally vary stochastic identity: assert constructor parity before asserting the scientific outcome.

## Phase Completion Checklist

- Verify Tasks 7–9 and update only `index.md` progress after each success.
