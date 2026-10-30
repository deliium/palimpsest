# Phase 6: Invariants and Regression

Plan: [index.md](index.md)
Tasks: 14-15
Depends on: Phases 1-5 (Tasks 1-13)

## Objective

Prove that V4-01 is additive scaffolding: no command, event, observer semantic
type, metric family, migration, route, or client authority is added, and the
complete V3 regression surface still passes with V4 flags off.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT = 136` (53) | Metric pin. |
| `src/observer/version.py` | `SEMANTIC_EVENT_TYPES`, 73 entries | Observer semantic pin. |
| `src/world/events.py` | `EVENT_SCHEMA_REPLAY_V22` (max) | Event pin. |
| `src/simulation/persistence.py` | codec max `v20` | Codec pin. |
| `src/simulation/compatibility.py` | `ALEMBIC_HEAD_REVISION` | Migration pin. |
| `src/experiments/benchmark_suite.py` | `BENCHMARK_SCENARIO_COUNT = 16` | V2 benchmark pin. |
| `src/experiments/civilization_benchmark_models.py` | `V3_BENCHMARK_SCENARIO_COUNT = 30` | V3 benchmark pin. |
| `tests/architecture/boundary_checker.py` | `BOUNDED_PACKAGES`, `ALLOWED_IMPORTS` | Top-level package allowlist. |
| `tests/architecture/test_world_authority.py` | `FORBIDDEN_PACKAGES`, `AUTHORITY_NAMES` | Authority leak guard. |
| `tests/compose/acceptance.py` | `acceptance_required`, `require_prerequisite` | Required-mode fail-closed gate. |
| `docs/development.md` | verification command table (37-51), full lane examples (240-310) | Canonical commands for Task 15. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_v4_architecture_invariants.py` | create | Consolidated V4 scaffolding invariant gate. |
| `tests/architecture/boundary_checker.py` | modify only if a new V4 module needs an explicit allowlist entry | No new top-level package is allowed. |
| `tests/unit/test_v4_scaffolding_gate.py` | extend | Add the full-lane profile assertions if not already covered. |

## Task 14: Add the V4 architecture invariant suite

### Intent

One executable gate that fails if V4-01 drifts into behavior, adds an
unreserved wire surface, grants authority to a context that must not have it, or
lets a client gain a write path.

### Implementation Steps

1. Create `tests/architecture/test_v4_architecture_invariants.py` with
   `pytestmark = pytest.mark.architecture`.
2. Add pin assertions:
   - `RUNNER_SCHEMA_VERSION == "runner-config-v4"` and
     `RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"`; v56 accepted.
   - `EVENT_SCHEMA_REPLAY_V22 == 22`; `max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 22`;
     `"v21" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS`.
   - `METRIC_FAMILY_COUNT == 136`.
   - `len(SEMANTIC_EVENT_TYPES) == 73` and the `observer` facade re-exports the
     same tuple object from `observer.version`.
   - `OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"`;
     `SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)`.
   - `ALEMBIC_HEAD_REVISION == "0017"`; no `0018_*.py` under
     `alembic/versions`.
   - `BENCHMARK_SCENARIO_COUNT == 16`; `V3_BENCHMARK_SCENARIO_COUNT == 30`.
3. Add surface assertions:
   - The closed command count is 43:
     `len(COMMAND_RULE_MATRIX) == 43` from `world._rules` (the same symbol used
     by `tests/unit/test_mediation_invariants.py`). Assert that no V4 module
     defines a new command operation.
   - `set(V4_CONTEXT_BY_ID) == set(V4ContextId)`; every non-analysis context
     has exactly one flag and `societal_resilience` has none.
   - Every `V4CapabilityFlags` field is unowned:
     `V4CapabilityFlags(**{name: True}).unimplemented_enabled_names() == (name,)`.
   - `validate_write_pair_reservations()` and `validate_migration_sequence()`
     pass; `next_revision() == "0018"`; the context prerequisite graph is
     acyclic and every declared edge targets a known context.
   - No V4 flag is read by `simulation.runner`, `simulation.engine`,
     `simulation.agent_runtime`, or any `world` module except the capability
     gate. Use an AST scan for `v4_capability_flags` and assert the only
     production references are in `runner_models.py`, `runner_serialization.py`,
     `runner.py`, `compatibility.py`, `experiments/catalog.py`, and
     `experiments/matrix_schema.py`.
4. Add magic-actor assertions. Scan `src/**/*.py` for these tokens and fail on
   any hit: `OrganizationActor`, `WorldGovernment`, `CentralBank`,
   `GlobalOrganizationRegistry`, `GlobalLawRegistry`, `WarState`,
   `CivilizationActor`, `InstitutionActor`.
5. Add authority assertions:
   - `simulation/v4_architecture.py`, `simulation/versioning.py`,
     `simulation/migration_plan.py`, and `simulation/scale.py` import no
     `WorldState`, `WorldEngine`, `ActionSubmission`, `experiments`, `analysis`,
     `api`, `persistence`, `infrastructure`, or `observer` module.
   - Every `DETACHED_ANALYSIS` context lists only `analysis` and appears in
     `V4_ANALYSIS_ONLY_CONTEXTS`.
   - `simulation` still does not import `experiments` (reuse the existing
     architecture assertion rather than duplicating a weaker one).
6. Add client read-only assertions:
   - Godot `clients/godot-observer/scripts/net/*.gd` contains no
     `HTTPClient`/`HTTPRequest` write request (no `POST`, `PUT`, `PATCH`, or
     `DELETE` method selection).
   - In `clients/research-ui/src/`, the only permitted `'POST'` token is the
     existing `FetchOptions.method` type union in `src/api/client.ts`; assert
     that no `method: 'POST'` call site exists and that `getVersion` does not
     attach a capability header.
   - Godot `SUPPORTED_PROTOCOLS` contains only v1.
7. Add doc parity: `docs/v4-architecture.md` contains every `V4ContextId` value
   and every required section from Task 2; `docs/v4-versioning.md` and
   `docs/v4-migration-sequence.md` are linked from `docs/v4-architecture.md`
   once Task 16 creates them. Until then, the test checks only the architecture
   page.
8. Add negative tests using mutated local copies for the registry, reservation,
   and migration validators; assert the documented error codes.

### Required Interfaces and Contracts

- The invariant suite is read-only and deterministic.
- It must not assert on wall-clock timing, file mtimes, or optional tool
  availability.
- Failures name the exact violated pin and expected value.

### Requirement Evidence

- Original Request: "Preserve all V1–V3 invariants", "Godot is read-only",
  "organizations/institutions/civilizations must not become magical actors".
- `.ai-factory/ARCHITECTURE.md` current baseline table.

### Error Handling and Logging

- Test-only; use `pytest.fail` through normal assertions with explicit messages.
- No runtime logging changes.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_architecture_invariants.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_path_dependence_boundaries.py tests/architecture/test_world_authority.py tests/architecture/test_import_boundaries.py -q`

### Acceptance Criteria

- All pins hold; no V4 surface beyond the declared scaffolding exists.
- Every context has no forbidden authority and no forbidden actor symbol exists.
- Both clients remain read-only.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_architecture_invariants.py -q`
- Expected result: all tests pass, 0 failures.
- `uv run --frozen --python 3.12.14 lint-imports` reports 25 contracts kept,
  0 broken.

## Task 15: Execute the V3 regression lanes under V4 flags off

### Intent

Certify that V4-01 did not change V3 behavior. These are the same required lanes
used by V3-44, executed with V4 flags off; a skip is not a pass.

### Implementation Steps

1. Record source identity before running:
   - `git rev-parse HEAD` and `git status --porcelain`.
   - A deterministic SHA-256 tree digest over tracked plus untracked non-ignored
     first-party files, excluding the paths in `AGENTS.md`. Store receipts under
     a caller-rooted directory such as `/tmp/opencode/v4-01/regression/`; do not
     commit artifacts.
2. Default collection with coverage enabled:
   - `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term --junitxml=<root>/default.xml`
   - Expected: the V3-44 final baseline count plus only the new V4 tests; 0
     failures; the two documented opt-in stress skips may remain, and any new
     skip must be named and justified.
3. PostgreSQL integration lane against a fresh disposable database whose name
   contains `palimpsest_test`:
   - `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m 'integration and not scale' --cov --cov-report=term --junitxml=<root>/integration.xml`
   - Expected: every executable test passes, 0 failures, 0 skips. A skipped
     database lane is not a pass.
4. Compose/browser lane with required acceptance:
   - Build or reuse a source-matched image and set
     `PALIMPSEST_API_IMAGE=<image>`.
   - `PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1 PALIMPSEST_API_IMAGE=<image> uv run --frozen --python 3.12.14 pytest -m compose --cov --cov-report=term --junitxml=<root>/compose.xml`
   - Expected: every required browser/stack test passes with 0 skips; a missing
     Docker CLI, Playwright, or image is a failure, not a skip.
5. Godot lane with the pinned archive:
   - Verify the archive SHA-512 against
     `clients/godot-observer/export/pins.env`.
   - `"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit`
   - `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`
   - Expected: 48 suites (47 V3 + 1 V4), `godot_protocol_tests failed=0`.
6. Research UI lane in the pinned Node/pnpm toolchain:
   - `cd clients/research-ui && pnpm install --frozen-lockfile && pnpm test && pnpm check && pnpm build`
   - Expected: all tests pass, 0 errors/warnings, build exit 0.
7. V3 benchmark harness (mechanism + research qualification) against the
   disposable database:
   - `uv run --frozen --python 3.12.14 pytest -m 'integration and scale' tests/benchmarks/test_v3_civilization_benchmark.py -q`
   - Expected: 4 passed, 0 failed, 0 skipped. This is a regression of the V3
     harness, not a new V4 claim; it may be long-running.
8. Static gates:
   - `uv run --frozen --python 3.12.14 ruff check src tests`
   - `uv run --frozen --python 3.12.14 mypy src tests`
   - `uv run --frozen --python 3.12.14 lint-imports`
   - `git diff --check`
   - Expected: clean / 0 errors / 25 contracts kept / no whitespace errors.
9. Write `<root>/summary.md` with: source identity, each command, exit code,
   passed/failed/skipped counts, and explicit notes for every skip. Do not
   convert a skip into a pass and do not weaken an assertion to get green.

### Required Interfaces and Contracts

- V4 flags remain off in every lane; the default config is v4.
- No test count, assertion, cap, or workload may be relaxed after observing a
  failure. A failure blocks the task.
- The Compose lane is source-matched; prior-image evidence is not accepted.
- The V3-44 stress probes
  (`PALIMPSEST_V3_PUBLICATION_SCALE_FRAMES`,
  `PALIMPSEST_V3_INCREMENTAL_SCALE_BOUNDARIES`) are opt-in measurement lanes,
  not required-gate passes; if executed, report them separately.

### Requirement Evidence

- Original Request: "V3 regression suite", "Preserve all V1–V3 invariants".
- `tests/compose/acceptance.py` required-mode contract.
- `docs/development.md` canonical verification commands.

### Error Handling and Logging

- Test output is captured to files; the summary contains counts, not payloads.
- Never print credentials, DSNs, tokens, prompts, or private content.
- Failures keep their original logs; do not post-process them into passes.

### Tests

- The commands in Implementation Steps 2-8 are the tests.

### Acceptance Criteria

- Default, integration, Compose/browser, Godot, Research UI, benchmark, and
  static lanes all execute and pass with 0 unexplained skips.
- V3-44 pins and behavior are unchanged.
- Any failure is reported as a blocker, not hidden.

### Verification

- `cat <root>/summary.md` shows every lane with exit code 0 and zero failures.
- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_architecture_invariants.py -q`
  passes on the same source digest.

## Phase Risks and Mitigations

- Risk: the V3 baseline count is treated as a target to edit.
  Mitigation: the invariant suite pins semantics, not a mutable total; any
  count change must be explained by named new V4 tests.
- Risk: a long lane times out and is reported as passing.
  Mitigation: the summary records timeout as a failure with the observed
  progress; rerun with a larger explicit budget rather than shrinking the lane.
- Risk: an architecture test duplicates an existing weaker check.
  Mitigation: reuse existing imports/helpers where available; new assertions
  must add a V4-specific invariant.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
