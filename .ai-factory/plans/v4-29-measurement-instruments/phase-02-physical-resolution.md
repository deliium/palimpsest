# Phase 2: Physical resolution

Plan: [index.md](index.md)
Tasks: 5–8
Depends on: Tasks 1–4

## Objective

Resolve admitted physical measurements and imperfect calibration deterministically, while preserving portability, locality, conservation and ordinary tick costs.

## Current-Code Evidence

| Path | Symbols / evidence | Why it matters |
|---|---|---|
| `src/world/_state.py` | `WorldState`, `rebuild_world_state`, indexed `tool_marks` | Preserve sidecars on every state rebuild, not just bootstrap. |
| `src/simulation/bootstrap.py` | `WorldBootstrap`, `_materialize_world` | Initial records require defensive validation and materialization. |
| `src/simulation/runner.py` | `SimulationRunner.from_config`, bootstrap creation near 2584 | Runner is the concrete spec → world bridge. |
| `src/world/_physical.py` | `_ambient` near 719 | Reuse existing ambient derivation; do not invent a second climate model. |
| `src/world/_operations.py` | `_ExperimentOp`, command promotion near 1109 | New commands need private operation promotion. |
| `src/world/_rules.py` | `_evaluate_experiment`, `_apply_experiment` | Existing experiment resolution may run twice; sampling must not advance RNG. |
| `src/world/_experiment_apply.py` | `resolve_experiment`, `project_experiment_resolved` | Precedent for effect-complete resolved facts and replay. |
| `src/world/regions.py` | `RouteSpec.duration_ticks` | Travel time exists; physical route length does not. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/world/_state.py`, `src/simulation/bootstrap.py`, `src/simulation/runner.py`, `src/simulation/engine.py` | modify | Seed, copy, validate and retain instrument/reference state. |
| `src/world/_measurement.py` | create | Private sampling, scalar conversion, deterministic error, wear and calibration transitions. |
| `src/world/_ambient.py` | create | Shared private pure ambient calculation extracted without changing legacy arithmetic. |
| `pyproject.toml`, `tests/architecture/boundary_checker.py` | modify | Co-land protection/importer registration for the private modules introduced here. |
| `src/world/_physical.py`, `src/world/_perception.py`, `src/world/_replay.py` | modify | Reuse one ambient helper without changing old numeric outputs. |
| `src/world/_operations.py`, `src/world/_rules.py`, `src/world/events.py` | modify | Admission and effect-complete measurement/calibration events. |
| `tests/unit/test_measurement_bootstrap.py`, `tests/unit/test_measurement_resolution.py`, `tests/unit/test_measurement_calibration.py`, `tests/unit/test_measurement_admission.py` | create | Engine, math, physical-reference and denied-action coverage. |

## Task 5: Bootstrap item-keyed instrument and reference state

### Intent

A measurement tool is a physical portable TOOL item with persistent condition, not an invisible cognitive capability.

### Implementation Steps

1. Add ordered `instrument_states` and `measurement_references` tuples plus immutable item-ID indexes to `WorldState`, `rebuild_world_state`, and `WorldBootstrap`, absent/empty by default.
2. Validate IDs against existing TOOL items, disjoint instrument/reference/tool-mark roles, unit compatibility, initial timer epoch ≤ current tick, finite bounds and caps. Physical records never create items by themselves.
3. Route the resolved runner spec through `SimulationRunner.from_config` → `WorldBootstrap` → `_materialize_world` → `WorldEngine`; restore follows the same validation.
4. Carry sidecars through every rebuild, transfer, Drop/Take/Give, storing/retrieval and corpse custody. Changing placement never resets bias, damage, timer epoch or calibration.
5. When an anchored item is actually removed by an admitted consuming operation, remove its sidecar in the same effect-complete transition. Do not treat storage or holder death as removal. No dangling state may survive a commit.

### Required Interfaces and Contracts

No random tool assignment, automatic newborn tools, inherited reliability beliefs, or crafting recipe expansion. Physical instruments are supplied by explicit scenario items for this increment. Existing tool production remains unchanged.

### Requirement Evidence

Original Request: physical tools and objective damage/calibration. Architecture: engine mutation only, blank-slate newborns and effect-complete history.

### Error Handling and Logging

Invalid seeds/restores fail before the first tick with anchor/state reason codes. Log counts and safe IDs, never hidden parameters. No repair-on-read or silent sidecar dropping on invalid restore.

### Tests

Held and ground bootstrap, immutable copy, invalid anchors, transfer/store/death persistence, consumption cleanup and replayable cleanup, duplicate items, off-spec no-op. Instrument item cannot be consumed through unsupported TOOL-as-food paths.

### Acceptance Criteria

Physical state follows the same item for its whole physical lifetime; no ordinary placement operation resets reliability.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_bootstrap.py --cov=world --cov=simulation --cov-report=term-missing -q`

Expected: placement/lifetime invariants pass.

## Task 6: Implement fixed-point sampling and deterministic display error

### Intent

Precision and accuracy must be distinct; repeated readings can consistently be wrong.

### Implementation Steps

1. Implement private `sample_measurement_target(state, actor_id, instrument, target_id, quantity)` and `resolve_measurement(...)` in `_measurement.py`. Inputs contain engine-owned state; outputs are detached reading plus exact instrument-after state, never live mutation. Add frozen private `MeasurementSamplingIdentity` and `MeasurementRuleContext`: the former carries primitive seed/derivation/rules-fingerprint/optional stochastic-identity values; the latter carries tick, that identity, and immutable eligible target/reference/exit ID sets keyed by actor entity ID. Neither class imports simulation or is exposed to cognition.
2. Sample only the index's five existing physical quantities. Extract the existing ambient calculation into `world._ambient` as a shared private pure helper used by measurement, physiology, perception and restored projection; retain old rounding and arithmetic ordering for legacy callers. This leaf helper imports only public world scalar/environment contracts, never rules or measurement, avoiding a private-module cycle.
3. Convert finite source scalars once to bounded milli-units. Apply the exact error/quantization/wear formula in the index; implement signed half-away-from-zero rounding using integers.
4. Generate noise through an independent pure keyed digest using the index's exact sampling-identity/null representation and action fields. `SimulationRunConfig.stochastic_identity` may be absent for valid derivation-v1/v2 inputs; use JSON null, never `.value` on None or a fabricated stream identity. The engine extracts only primitives for `MeasurementSamplingIdentity`. Do not consume world/cognition RNG streams, depend on process hash, or change between admission evaluation and apply.
5. Resolve against the ordered current candidate state. A prior same-tick resource transfer/harvest can change the target sample; re-evaluating the same candidate is idempotent. Damage is applied once on commit, after sampling.
6. Do not install reading history in objective state. Immutable events retain readings; only finite current instrument/reference records belong in `WorldState`.
7. Give each detached reading `reading_id = "msr:" + operation.request_id.value`. Request identity already exists before rule evaluation; final event IDs do not. Readings carry no event ID during resolution. Their eventual actor observations provide the separately allocated opaque `source_event_id`, which becomes the direct-evidence root. Keep reading identity and event correlation separate in events/codecs/replay.
8. Co-land the private-module protection/importer updates specified in Task 4 before importing either new module. Run `lint-imports` and the boundary fixtures immediately, not only at Task 24.

### Required Interfaces and Contracts

Temperature reads local ambient Celsius, not body temperature. Duration is elapsed simulated ticks since this physical timer's epoch. Travel estimate is adjacent route duration under currently available route conditions, not a guaranteed arrival time or length. Amount/load units remain simulation units.

### Error Handling and Logging

Reject unsupported targets, missing route conditions, overflow and unit mismatches with closed codes. No fallback to remote/global data. Resolution logs action/quantity/IDs and success code only, never sampled/display/error values.

### Tests

Golden vectors for negative ties, zero, max bounds, bias with fine precision, coarse unbiased display, damage-driven precision loss, nonzero bias with zero noise, deterministic noise twins, double evaluation, ordered current-state sampling, existing RNG parity, and shared ambient parity. Include both absent stochastic identity and explicit paired identity, unchanged display across run-ID changes under shared sampling identity, stable request-derived reading ID, and a test proving resolution does not need a future event ID.

### Acceptance Criteria

Equivalent seed/state/action produces identical displayed reading and wear; a finer display can be less accurate than a coarse one.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_resolution.py tests/unit/physical/test_physiology.py --cov=world --cov-report=term-missing -q`

Expected: golden arithmetic and unchanged physiology cases pass.

## Task 7: Resolve imperfect physical-reference calibration

### Intent

Calibration is an observable physical adjustment against a fallible reference, not a truth reset.

### Implementation Steps

1. Implement `resolve_instrument_calibration(...)` in `_measurement.py`. Require own-held instrument and own-held or visibly local ground reference with the same unit.
2. Sample the reference's hidden physical value through the instrument's pre-adjustment raw response, using the same damage/noise/quantization rules and a calibration-specific deterministic noise namespace.
3. Replace correction with `nominal_reference_milli - raw_reference_display_milli`; increment calibration revision; record adjustment tick and damage-at-adjustment. Set physical calibration state to `adjusted`. A reference's nominal mark can be wrong and calibration may worsen future readings.
4. Do not clear intrinsic bias/error or repair damage. Apply one use's wear; if the post-use damage has crossed the index's stale threshold, state is `stale`. Timer adjustment also resets its epoch to the committed action tick, recorded in the event.
5. The visible outcome is adjustment attempted/completed and an ordinary scale mark, not objective accuracy, residual error or certification.

### Required Interfaces and Contracts

Reference truth values/corrections never enter cognition. References are ordinary portable physical items with explicit initial records, not a global standards registry. No free calibration without a reachable reference.

### Error Handling and Logging

Missing/unreachable/wrong-unit reference and broken tool are admitted-action denials, not repaired by defaults. Invalid calculations fail closed before any partial transition. Metadata-only `instrument_calibration_resolved` logging.

### Tests

Accurate versus biased reference; noisy reference; same-unit different quantity reference; wrong-unit denial; correction replacement not addition; no damage repair; timer reset; stale threshold; broken instrument denial; deterministic twins and failure atomicity. Include an example where successful calibration increases error.

### Acceptance Criteria

Calibration can improve or worsen accuracy; physical state records exactly what changed without promoting the owner's appraisal to fact.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_calibration.py --cov=world --cov-report=term-missing -q`

Expected: imperfect-reference and atomicity cases pass.

## Task 8: Co-land admission, operations, costs and events

### Intent

Make both actions usable through the real `WorldEngine` trust pipeline.

### Implementation Steps

1. Introduce private `_MeasureOp`/`_CalibrateInstrumentOp` command promotion and rule branches. Channel absence rejects both with `MEASUREMENT_CHANNEL_OFF`; require alive, non-travelling actor, own-held unbroken instrument and correct quantity/target.
2. Enforce current locality plus the tick-start observation's eligibility boundary. Add `WorldEngine._measurement_rule_context(snap)` built from the already token-bound `snap.observation_batch`, not client-supplied IDs or a fresh evolving-state observation. Join each owner observation to its actor entity; freeze eligible current location, resource, own-held/visible ground item, visible reference and adjacent destination sets. Use the new reference appearance from Task 11 for autonomous reference recognition, while engine-side eligibility may join its private reference index to already visible item IDs. Missing cached observations fail closed; never grant eligibility by default.
3. Add optional `measurement_context` to `prepare_action_batch`, `evaluate_operation`, and `apply_operation`; carry the same validated context through initial applicability checks and ordered working-state checks. The engine also supplies primitive sampling identity and tick in that context. Require the target/reference to be eligible at tick start AND physically reachable in current working state. Own-held instrument possession is revalidated currently. No trusted eligibility/noise field is accepted on an agent command.
4. Charge one ordinary action/tick with the existing Wait-equivalent physiological cost, plus the instrument wear specified in the index. No extra command execution, target transfer, world clock advance or special science probability.
5. Add `MeasurementTaken` (`measurement_taken`) and `InstrumentCalibrated` (`instrument_calibrated`) effect-complete details to world events. Record displayed reading/calibration action identity and instrument before/after state; no sampled target value is necessary for replay. Keep the request-derived reading ID; let existing batch finalization allocate the actual event ID afterwards.
6. Capture occurrence context at resolution using ordinary actor/location audience machinery. Apply transitions only after successful admission. Failure emits the ordinary rejection result without reading or wear.
7. Do not repurpose `ExperimentResolved` or introduce `MeasurementReading` as an experiment success outcome.

### Required Interfaces and Contracts

Exactly-once wear, cost and event. Existing commands remain legal/illegal for their existing physical reasons; subjective trust and calibration beliefs never influence admission.

### Error Handling and Logging

Closed denials: channel off, actor unavailable, instrument not held, instrument broken, quantity mismatch, target inaccessible, reference inaccessible/unit mismatch. Return safe reason codes; do not embed state snapshots in exceptions.

### Tests

Real observe→submit→resolve for both commands; every denial; low visibility; guessed remote/private IDs; dead/travelling actors; same-tick placement changes; one action/cost/wear; no target mutation; no side effects on rejected or cancelled actions. Exercise engine→batch→rule context forwarding directly: an unseen target made available by an earlier action stays ineligible, and a tick-start-visible target removed/moved earlier becomes inaccessible. A missing/foreign context cannot grant measurement authority.

### Acceptance Criteria

Only engine-admitted commands produce readings/calibration transitions; no helper bypasses world authority.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_admission.py tests/unit/test_experiment_resolution.py --cov=world --cov=simulation --cov-report=term-missing -q`

Expected: measurement admission passes and categorical experimentation remains unchanged.

## Phase Risks and Mitigations

- Double sampling: pure keyed noise and prepared immutable transitions; mutate only once.
- Divergent ambient formula: shared helper with legacy golden parity.
- Truth leak through reachability: observation eligibility plus current-state physical validation.
- Instrument condition reset on transfer: invariant tests across existing item operations.

## Phase Completion Checklist

- All Tasks 5–8 satisfy their focused tests and acceptance criteria.
- Update progress only in `index.md`.
