# Phase 5: Experiment and Certification Paths

Plan: [index.md](index.md)
Tasks: 15-17
Depends on: Phase 4 (Tasks 13-14)

## Objective

Register an off-gate `social_mobility@1` experiment, prove the full pipeline
in-process with real admission and real commands, and lock determinism,
cap-bound properties, and layer leakage before documentation.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/economic_inequality_scenario.py` | `ECONOMIC_INEQUALITY_EXPERIMENT_ID` (43), `_base` (46-66), `_access` (69-78), `_full` (81-92), scenario (95-139) | Arm composition and v56/v55 keyset pattern |
| `src/experiments/catalog.py` | `experiment_economic_inequality` (5734-5752), `OFF_GATE_MATRIX_EXPERIMENT_IDS` (2800-2839), `EXPERIMENT_A_V1_CONDITION_IDS` (244-246) | Registration points and off-gate matrix |
| `src/experiments/models.py` | `ExperimentCondition` (55-67), `ExperimentDefinition` (70-109) | Closed experiment value shape |
| `src/analysis/economic_inequality_analysis.py` | layer separation and caps | Bounds/leakage precedent |
| `tests/unit/test_economic_inequality_end_to_end.py` | real engine/commands/store/TestClient | End-to-end fixture pattern |
| `tests/unit/test_economic_inequality_determinism.py`, `_bounds.py`, `_leakage.py` | determinism/bounds/leakage precedent | Test shape to mirror |
| `tests/architecture/test_economic_inequality_boundaries.py` | module allowlist scan (13-22), simulation-module scan (63) | Boundary test pattern |
| `tests/architecture/test_economic_inequality_invariants.py` | catalog/commands/semantics pins (30-61) | Invariant pin pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/social_mobility_scenario.py` | create | Three arms over the accepted v56 seam |
| `src/experiments/catalog.py` | modify | `experiment_social_mobility` and off-gate id |
| `src/experiments/__init__.py` | modify | Export the experiment factory |
| `tests/unit/test_social_mobility_experiment.py` | create | Registration/off-gate/arm behavior |
| `tests/unit/test_social_mobility_end_to_end.py` | create | Real admission through real API |
| `tests/unit/test_social_mobility_determinism.py` | create | Identical bytes across hash seeds |
| `tests/unit/test_social_mobility_bounds.py` | create | Cap and prefix properties |
| `tests/unit/test_social_mobility_leakage.py` | create | Layer and token leakage guards |

## Task 15: Register off-gate `social_mobility@1`

### Intent
Provide a reproducible three-arm study that exercises genealogy-only,
education-bearing, and full economic/institutional mobility without entering the
V1 gate.

### Implementation Steps
1. Create `src/experiments/social_mobility_scenario.py`:
   - `SOCIAL_MOBILITY_EXPERIMENT_ID: Final[str] = "social_mobility@1"`.
   - `_base(config)`: start from `runner-config-v56` over the exact v55 family
     keyset; require population lifecycle, blank-slate initialization,
     `kinship`, finite tick horizon, and `generational_interval_entry`; disable
     all V4 economic flags; clear durable records, knowledge repositories,
     collective projects, structured commitments, subjective valuation.
   - `_kinship(config)`: add `durable_records`,
     `knowledge_repositories`, cultural provenance, and mentorship /
     developmental-learning modes; keep economic flags off.
   - `_full(config)`: kinship arm plus `organizations`, `markets_credit`,
     `infrastructure_networks`, `supply_chains`, `structured_commitments`,
     `subjective_valuation`, and deterministic representation/office modes.
   - `social_mobility_scenario(base, *, seed_matrix=None, max_ticks=96)`
     requires `max_ticks >= 96`, builds arms `sm-baseline`, `sm-kinship`,
     `sm-full` in that order, and sets a paired world group.
2. In `src/experiments/catalog.py`, add
   `experiment_social_mobility(base, *, seed_matrix=None, max_ticks=96)`
   delegating to the scenario and logging
   `experiment_registered experiment_id=social_mobility@1 arms=3`.
3. Append `"social_mobility@1"` to `OFF_GATE_MATRIX_EXPERIMENT_IDS`; do not add
   it to `EXPERIMENT_A_V1_CONDITION_IDS`.
4. Export `experiment_social_mobility` from `src/experiments/__init__.py` for
   parity with `experiment_credit_relationships`.

### Required Interfaces and Contracts
- Arms are ordered and unique; each is a valid v56 config.
- `sm-baseline` has no kinship evidence and therefore produces no
  `social_mobility_*` metric input or snapshot field.
- `max_ticks < 96` raises a stable setup error.

### Requirement Evidence
- Original Request multi-generation study; `runner-config-v56` accepted seam.
- `.ai-factory/ARCHITECTURE.md` off-gate experiment rule.

### Error Handling and Logging
- INFO `experiment_registered experiment_id=social_mobility@1 arms=3`.
- WARN `social_mobility_experiment_invalid_arm`.
- ERROR setup codes only; no config values in logs.

### Tests
- `tests/unit/test_social_mobility_experiment.py`: id in
  `OFF_GATE_MATRIX_EXPERIMENT_IDS`, absent from
  `EXPERIMENT_A_V1_CONDITION_IDS`, arm order, v56 schema, finite horizon,
  `sm-baseline` produces no analysis while `sm-kinship`/`sm-full` do (using the
  collector fixture).

### Acceptance Criteria
- Experiment is off-gate and reproducible.
- Baseline arm is provably inert for social mobility.
- No new capability flag, runner schema, command, or migration.

### Verification
- `uv run pytest tests/unit/test_social_mobility_experiment.py -q`
- Expected result: pass.

## Task 16: Add in-process end-to-end coverage

### Intent
Prove the feature works over real objective behavior, not only synthetic rows,
and cover the cross-seam lessons from earlier V4 features.

### Implementation Steps
1. Create `tests/unit/test_social_mobility_end_to_end.py`:
   - Build a real `WorldEngine` admission loop with a multi-generation fixture
     using real `Craft`, `Build`, `Give`, `Move`, and `Talk` (or `Tell`)
     commands.
   - Commit real events, run the real
     `build_completed_run_social_mobility_analysis`, compose/finalize the real
     snapshot, publish through a real filesystem store, and read through a real
     FastAPI `TestClient`.
2. Cover:
   - all six domains present where evidence exists;
   - unresolved pairs when one side has no outcome row;
   - generation rows and lag rows for at least three generations;
   - snapshot round-trip;
   - dual-gate success and 503 failure;
   - collector injects a non-empty analysis;
   - paging spans at least three windows and rejects a cursor minted for
     another window;
   - cumulative publication bytes across at least three publications;
   - corrupt store returns 500;
   - summary `truncated` and coverage reflect every row family.
3. Assert `unavailable`/`insufficient_samples` appear honestly for sparse
   domains rather than zeros.

### Required Interfaces and Contracts
- No mocks for the engine, commands, events, snapshot, store, or API.
- Capture-only log assertions use safe tokens; never assert payload values.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md` representative real artifact rule.
- V4-24 end-to-end lessons (multi-window paging, cumulative bytes, corrupt
  store).

### Error Handling and Logging
- No production log changes.
- Tests assert bounded metadata only.

### Tests
- The named file with the cases above.

### Acceptance Criteria
- One test proves the complete path from admission to HTTP read.
- Sparse evidence is explicit, not zero-filled.
- Cursor and quota regressions fail if broken.

### Verification
- `uv run pytest tests/unit/test_social_mobility_end_to_end.py -q`
- Expected result: pass.

## Task 17: Add determinism, property bounds, and leakage coverage

### Intent
Lock byte determinism, bounded behavior, and the three-layer separation so a
later change cannot smuggle class labels or raw owner ids into the artifact.

### Implementation Steps
1. `tests/unit/test_social_mobility_determinism.py`: run the same seed and
   fixture twice with different `PYTHONHASHSEED` values; assert identical
   snapshot bytes, digest, publication id, and row order.
2. `tests/unit/test_social_mobility_bounds.py`: Hypothesis properties for
   owner/event/pair/domain/generation/lag caps, monotone prefix stability,
   statistic ranges (`rank_correlation_milli` -1000..1000, shares 0..1000,
   mean change 0..1000), and `insufficient_samples` below the pair threshold.
3. `tests/unit/test_social_mobility_leakage.py`:
   - objective rows never carry owner-claim fields, organization tokens, or
     practical-knowledge fields;
   - owner rows never carry custody fields, item ids, or raw quantities from
     committed events;
   - analytical rows carry no raw owner ids or generation labels beyond the
     integer index;
   - snapshot rows carry no owner ids, no pair tokens, no lineage tokens, and
     no forbidden keys (`class`, `wealth`, `rank`, `score`, `prestige`,
     `merit`);
   - metric documents reject the same forbidden keys in values and notes.

### Required Interfaces and Contracts
- Determinism includes set/frozenset input ordering and dict key ordering.
- Cap truncation keeps a deterministic prefix, never a random sample.
- Leakage guards fail closed with a stable reason code.

### Requirement Evidence
- Original Request "Do not encode social classes".
- `.ai-factory/ARCHITECTURE.md` Key Principle 1 (three authorities) and
  Key Principle 2 (determinism).

### Error Handling and Logging
- No new production logs.
- Tests assert metadata-safe behavior only.

### Tests
- The three named files.

### Acceptance Criteria
- Identical inputs produce identical bytes across hash seeds.
- Every cap property holds.
- No raw owner id or class vocabulary can reach the snapshot.

### Verification
- `PYTHONHASHSEED=0 uv run pytest tests/unit/test_social_mobility_determinism.py -q`
- `PYTHONHASHSEED=12345 uv run pytest tests/unit/test_social_mobility_determinism.py -q`
- `uv run pytest tests/unit/test_social_mobility_bounds.py tests/unit/test_social_mobility_leakage.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: the generational fixture needs many ticks and slows tests.
  Mitigation: use the smallest fixture that yields three generations and cap
  the study window; keep scale work out of unit tests.
- Risk: hash-seed determinism fails because a dict iteration leaks into rows.
  Mitigation: sort every token/cap/enum collection and test under two seeds.
- Risk: leakage guard is bypassed by a metric payload.
  Mitigation: assert forbidden keys in both rows and metric documents.

## Phase Completion Checklist
- Every Task in this phase satisfies its acceptance criteria.
- Experiment, E2E, determinism, bounds, and leakage tests pass.
- `index.md` Task 15-17 checkboxes are updated after verification.
