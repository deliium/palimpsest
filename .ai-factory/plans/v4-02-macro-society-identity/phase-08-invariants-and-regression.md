# Phase 8: Invariants and Regression

Plan: [index.md](index.md)
Tasks: 17-18
Depends on: Phases 1-7 (Tasks 1-16)

## Objective

Make the authority claims executable: analysis-only ownership, no world
authority, no magic actor, no capability flag, no event or command, deterministic
identity, and a green V1-V4 regression surface with every required lane actually
executed.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_lineage_explorer_boundaries.py` | simulation/API/persistence import restrictions, GET-only route scan | Direct template for the macro-society boundary suite. |
| `tests/architecture/test_analysis_isolation.py` | analysis import and authority rules | Existing analysis isolation gate to extend. |
| `tests/architecture/test_v4_architecture_invariants.py` | pins, magic-actor token scan, allowed V4 flag references | Must admit the new modules without weakening the scan. |
| `tests/architecture/test_v4_context_registry.py` | 14-context registry assertions from Task 1 | Registry parity gate. |
| `tests/unit/test_v1_regression_gate.py` | V1 A-E flags-off gate | Must stay green. |
| `tests/unit/test_v2_scientific_invariants.py` | V2 scientific invariants | Must stay green. |
| `tests/unit/test_alembic_head_pin.py` | `0017` pin | Must stay green; V4-02 adds no migration. |
| `tests/unit/test_metric_specifications.py` | 140-family pin from Task 9 | Catalog gate. |
| `tests/compose/acceptance.py` | required-mode skip accounting | A skip is not a pass. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_macro_society_boundaries.py` | create | Authority, import, magic-actor, route, and flag-absence gates. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Admit the new modules explicitly; keep the magic-actor scan strict. |
| `tests/unit/test_macro_society_determinism.py` | create | Hypothesis determinism and invariance properties. |
| `tests/unit/test_macro_society_end_to_end.py` | create | Harvest → snapshot → store → API read. |
| `tests/compose/test_generational_research_ui_browser.py` | modify | Macro-society panel acceptance assertions (required-mode aware). |

## Task 17: Add the macro-society boundary and determinism suite

### Intent

Boundary tests fail when a future change gives the analysis world authority,
adds a capability flag, or lets a client derive identity. Determinism tests fail
when ordering, hashing, or floating-point behavior becomes environment-dependent.

### Implementation Steps

1. Create `tests/architecture/test_macro_society_boundaries.py` with these gates:
   - **Analysis imports:** every `src/analysis/macro_society_*.py` module imports
     only `analysis.*`, `world.identifiers`, the standard library, `numpy`, and
     `networkx`. Any import of `simulation`, `persistence`, `api`, `experiments`,
     `observer`, `infrastructure`, or `world._*` fails.
   - **Simulation imports:** every `src/simulation/macro_society_*.py` module does
     not import `analysis`, `experiments`, `api`, `persistence`, `observer`, or
     `infrastructure`.
   - **Persistence imports:** `src/persistence/macro_society_filesystem.py` does
     not import `analysis`, `experiments`, `api`, or `observer`.
   - **API imports:** `src/api/routes/macro_society.py` and
     `src/api/macro_society_cursor.py` do not import `analysis` or `experiments`.
   - **GET-only:** the AST of the route module contains exactly four `get`
     decorators and no `post`/`put`/`patch`/`delete`.
   - **No world authority:** no macro-society module contains `WorldEngine`,
     `WorldState`, `ActionSubmission`, `AgentCommand`, `WorldEvent`, or
     `ActionRequest` tokens.
   - **No capability flag:** no macro-society module references
     `v4_capability_flags`, `V4CapabilityFlags`, `runner-config-v57`, or any V4
     flag name; `V4CapabilityFlags().any_enabled()` remains false.
   - **No magic actor:** source scan rejects `class Nation`, `class Country`,
     `class Civilization`, `class Government`, `class Society`, `class Polity`,
     `class Tribe`, `class Empire`, `class State` definitions and any
     `register_society`/`society_registry` symbol.
   - **No event or migration:** `src/world/events.py` event count, replay
     version, codec version, and `ALEMBIC_HEAD_REVISION` equal the V4-02 baseline
     captured in the test.
   - **No observer change:** `OBSERVER_CAPABILITIES`,
     `SUPPORTED_OBSERVER_PROTOCOLS`, and `OBSERVER_LAYOUT_SCHEMA_VERSION` equal
     the pre-existing values.
2. Extend `tests/architecture/test_v4_architecture_invariants.py`:
   - Add `analysis.macro_society_*` and `simulation.macro_society_*` to the
     module allowlists it already scans, without relaxing any existing rule.
   - Keep the allowed flag-reference set unchanged (macro-society modules must
     not reference flags).
3. Create `tests/unit/test_macro_society_determinism.py` with Hypothesis
   properties:
   - Permuting persons, edges, tokens, windows, and candidates never changes
     ids, candidate keys, statuses, lineage edges, or the determinism digest.
   - Re-running detection and identity assignment on the same evidence yields
     byte-identical `MacroSocietyAnalysis` JSON.
   - Adding a disjoint candidate never changes an existing candidate's id.
   - Jaccard thresholds are respected at the boundary values
     (`0.4999`, `0.5`, `0.5001`, `0.7499`, `0.75`) using quantized floats.
   - Lineage edges remain acyclic for arbitrary generated window sequences.
4. Create `tests/unit/test_macro_society_end_to_end.py`:
   - Build a six-window fixture with an emergence, a split, a merge, and a
     dissolution.
   - Run detection → identity → lineage → metrics → harvest mapping → encode →
     publish to a temporary root → read via the filesystem reader.
   - Assert the API route layer (with a stub app and the real reader) returns the
     same summary, candidate page, and lineage page.
   - Assert no output contains a person id in the objective layer and no
     candidate id in the subjective layer.

### Required Interfaces and Contracts

- The suite reads the baseline constants from the modules themselves; it must not
  duplicate a second copy of the pin values.
- A missing module is a failure, not a skip.
- No test depends on network, Docker, or PostgreSQL.

### Error Handling and Logging

- Tests only; no runtime logging changes.

### Tests

- The new suites above.
- `tests/architecture/test_analysis_isolation.py` still passes (extended scan).

### Acceptance Criteria

- Every authority claim in the registry has a failing test if violated.
- Determinism holds under permutation and repeated runs.
- End-to-end read path works without Docker.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_macro_society_boundaries.py tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_v4_context_registry.py tests/architecture/test_analysis_isolation.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_determinism.py tests/unit/test_macro_society_end_to_end.py -q`

## Task 18: Execute the full V1-V4 regression and qualification lanes

### Intent

Planning is not evidence. Every required lane either executes and passes or is
reported as unexecuted with its blocking prerequisite; a skip is never certified
as a pass.

### Implementation Steps

1. Run the static and unit lanes:
   - `uv run --frozen --python 3.12.14 ruff check src tests`
   - `uv run --frozen --python 3.12.14 mypy src tests`
   - `uv run --frozen --python 3.12.14 pytest`
   Record pass counts and any failure with the owning task.
2. Run the compatibility and regression lanes explicitly:
   - `uv run --frozen --python 3.12.14 pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_alembic_head_pin.py tests/unit/test_metric_specifications.py -q`
   - `uv run --frozen --python 3.12.14 pytest tests/unit/test_v3_*_regression.py -q`
   - `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_* tests/unit/test_observer_* -q`
3. Run the integration lanes that need no external service:
   - `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_agent_runtime_world_engine.py -q`
4. Run the Compose and browser lanes in required mode:
   - `uv run --frozen --python 3.12.14 pytest -m compose`
   - `uv run --frozen --python 3.12.14 pytest -m compose tests/compose/test_generational_research_ui_browser.py tests/compose/test_research_ui_wiring.py`
   If Docker, a browser driver, or the source-matched release image is absent,
   record the lane as `unexecuted` with the missing prerequisite and the exact
   command. Do not convert it to a skip-pass.
5. Run the Research UI build and unit lane:
   - `pnpm --dir clients/research-ui build`
   - `pnpm --dir clients/research-ui test`
6. Run the pinned Godot suite documented in `docs/development.md` even though no
   Godot file changed; a failure is a regression to investigate, not a new
   feature.
7. Run the benchmark regression lane relevant to analysis scale:
   - `uv run --frozen --python 3.12.14 pytest tests/benchmarks/test_v4_scale_contract.py -q`
     (unset `PALIMPSEST_V4_SCALE_IDS` reports the lane as skipped by design; that
     is not a capacity claim and not a V4-02 gate).
8. Produce a receipt table in the phase output (and later in Task 20) with:
   lane, command, executed/skipped/unexecuted, result, and prerequisite for any
   unexecuted lane.

### Required Interfaces and Contracts

- A required lane must execute; absence of a prerequisite is reported.
- Coverage remains enabled for Python lanes as configured by the project's
  existing coverage settings; do not disable it to shorten a run.
- No pin is updated to make a lane pass; a failing pin means the implementation
  regressed.

### Error Handling and Logging

- Capture `PALIMPSEST_LOG_LEVEL=INFO` output only for failing lanes; do not dump
  verbose logs into the receipt.
- Record error codes, not stack traces with payload data.

### Tests

- All lanes above.
- `grep -rn "== 136\|METRIC_FAMILY_COUNT = 136" tests src` returns nothing.
- `grep -rn "runner-config-v57\|v4_capability_flags\." src/analysis/macro_society_* src/simulation/macro_society_* src/api/routes/macro_society.py` returns nothing.

### Acceptance Criteria

- Static gates, unit, architecture, and the no-service integration lane pass.
- Compose/browser and Godot lanes are either passing or explicitly unexecuted
  with prerequisites; no required lane is silently skipped.
- Catalog, pins, and flags remain exactly as declared.

### Verification

- The receipt table is complete and reproducible from the recorded commands.
- Expected result: every executed lane passes; every unexecuted lane names its
  blocker.

## Phase Risks and Mitigations

- Risk: a broad `pytest` run hides a lane because of marker defaults.
  Mitigation: run each lane's explicit command and record it separately.
- Risk: determinism tests pass only for the chosen seed.
  Mitigation: Hypothesis seeds plus explicit `PYTHONHASHSEED` variation in Task
  17.
- Risk: Compose absence is quietly recorded as success.
  Mitigation: three-state receipt (`executed/skipped/unexecuted`) and no green
  claim without execution.

## Phase Completion Checklist

- Every Task 17-18 acceptance criterion is satisfied.
- Boundary gates fail when authority is violated.
- Every required lane has an explicit receipt state.
- `index.md` task checkboxes are updated immediately after verified completion.
