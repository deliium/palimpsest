# Phase 8: Invariants, E2E, experiment

Plan: [index.md](index.md)
Tasks: 23-25
Depends on: Phases 1-7

## Objective

Lock architecture pins, prove an in-process E2E (including cognition starts),
and register the off-gate experiment `infrastructure_networks@1`.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `tests/architecture/test_v4_architecture_invariants.py` | pins | Update |
| `tests/unit/test_runner_config_v4_flags.py` | frozenset equality | Dual ownership |
| `src/experiments/catalog.py` | AW/AX registration | Experiment precedent |
| Borders/macro E2E unit tests | in-process pattern | E2E template |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/architecture/test_infrastructure_boundaries.py` | create | Boundaries/forbid/ownership |
| Architecture suites asserting owned=5 / metrics=184 / v21 absent | modify | Current pins |
| `tests/unit/test_infrastructure_end_to_end.py` | create | Full E2E |
| `src/experiments/catalog.py` (+ scenario module) | modify/create | Off-gate experiment |
| `tests/unit/test_infrastructure_experiment.py` | create | Experiment registration smoke |

## Task 23: Architecture invariants and pin sweeps

### Intent
Align every **current** pin with the V4-16 landing state.

### Implementation Steps
1. Update invariants:
   - metrics 188
   - `EVENT_SCHEMA_REPLAY_V23 == 23` accepted
   - `"v21"` accepted; epidemic `"v22"` codec string still unaccepted
   - commands 43; semantics 73; Alembic `0017`
   - owned flags frozenset size 6 including `infrastructure_networks`
   - both frozensets equal
   - unowned size 6
2. Boundary suite: forbid-list, analysis isolation, no supply_chains ownership,
   no auto-maintain scheduler, no `/v2`, protocol v1, explicit PUBLIC_GOOD
   membership.
3. Sweep current 184 / owned-5 pins across architecture tests.
4. Run ruff/mypy/import-linter on touched packages.

### Required Interfaces and Contracts
- Downstream checklist items covered by tests.

### Error Handling and Logging
- Pin drift fails closed.

### Tests
```
uv run pytest tests/architecture/test_v4_architecture_invariants.py \
  tests/architecture/test_infrastructure_boundaries.py \
  tests/architecture/test_analysis_isolation.py \
  tests/unit/test_runner_config_v4_flags.py -q
```

### Acceptance Criteria
- All current pins match landing; isolation/forbid green.

### Verification
- Architecture subset green.

## Task 24: In-process infrastructure E2E

### Intent
Unit-lane E2E covering cognition-proposed construction, effects, lifecycle,
publication, and six routes — not integration-only.

### Implementation Steps
1. Deterministic scenario: flag + collective_projects (+ production; optional
   public_goods arm).
2. Use cognition proposers (Task 6) and/or direct commands to build road +
   shelter + irrigation; complete; verify travel/capacity effects; decay;
   Repair road without public_goods; destroy one asset.
3. Metrics emit; dual-gate publish; hit all six routes.
4. Assert no score fields; publish failure injection leaves scientific status
   unchanged.
5. Place under `tests/unit/test_infrastructure_end_to_end.py`.

### Required Interfaces and Contracts
- Runs without PostgreSQL.
- Includes at least one cognition-proposed start when focus fixtures available;
  otherwise document direct-command arm **and** a separate cognition unit path
  already covered by Task 6 (E2E must still exercise road target completion).

### Error Handling and Logging
- Metadata-only; assert receipt codes on failure injection.

### Tests
- `uv run pytest tests/unit/test_infrastructure_end_to_end.py -q`

### Acceptance Criteria
- E2E green in unit lane; covers construct→effect→lifecycle→surfaces.

### Verification
- E2E command passes.

## Task 25: Off-gate experiment `infrastructure_networks@1`

### Intent
Register a reproducible off-V1-gate experiment for the owned channel.

### Implementation Steps
1. Add scenario module under `src/experiments/` composing v56 +
   `infrastructure_networks` + `collective_projects` (+ production as needed).
2. Register `infrastructure_networks@1` in `experiments/catalog.py` following
   AW/AX style; keep off the V1 regression gate.
3. Arms: control (flag off / channel inert) vs treatment (flag on) demonstrating
   at least one completed infra asset and one measurable effect (e.g. travel
   duration) without claiming capacity/prevalence.
4. Smoke test registration and flags-off V1 gate still green.

### Required Interfaces and Contracts
- Experiment does not own `supply_chains`.
- Not added to V1 A–E gate.

### Error Handling and Logging
- INFO `experiment_registered experiment_id=infrastructure_networks@1 …`.

### Tests
- `uv run pytest tests/unit/test_infrastructure_experiment.py tests/unit/test_v1_regression_gate.py -q`

### Acceptance Criteria
- Experiment registered and off-gate; V1 gate unaffected.

### Verification
- Experiment + V1 gate tests green.

## Phase Risks and Mitigations
- Risk: incomplete owned-flag pin sweep.
  Mitigation: ripgrep `len(V4_OWNED_CAPABILITY_FLAGS) == 5` and `184`.
- Risk: E2E skips cognition.
  Mitigation: Task 6 unit coverage required; E2E still exercises road targets.

## Phase Completion Checklist
- Tasks 23-25 done.
