# Phase 7: Invariants, End-to-End Borders, and Regression

Plan: [index.md](index.md)
Tasks: 23-25
Depends on: Phase 2 / Tasks 4-10, Phase 3 / Tasks 11-15, Phase 4 / Tasks 16-17, Phase 5 / Tasks 18-19, Phase 6 / Tasks 20-22

## Objective

Prove the authority claims with an architecture/determinism suite, run a real
in-process border end-to-end scenario with real ticks, commands, publication, and
all six routes, then execute the full V1-V4 regression and qualification lanes.
Any required lane that cannot run is recorded as `unexecuted` with its
prerequisite and blocks certification.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `tests/architecture/test_v4_architecture_invariants.py` | registry, pins, magic-actor scan | Must stay green |
| `tests/architecture/test_diplomacy_boundaries.py` | forbidden classes 183-210; no command path 142-171 | Boundary-suite pattern |
| `tests/architecture/test_treaty_boundaries.py` | forbidden classes 35-51; route count 101; frame bounds 187 | Boundary-suite pattern |
| `tests/architecture/test_organization_boundaries.py` | read-only analysis 118; no world authority 188; route GET-only 296 | Boundary-suite pattern |
| `tests/architecture/test_organized_conflict_boundaries.py` (if present) | V4-12 authority, route, determinism assertions | Closest V4 precedent |
| `tests/unit/test_organized_conflict_e2e.py` | real ticks, publication, six routes, no PostgreSQL | E2E pattern |
| `tests/unit/test_borders_*.py` | focused border suites | Must all stay green |
| `docs/development.md` | test and qualification commands | Exact lane commands |
| `src/simulation/world_engine` contract | `WorldEngine` sole mutation authority | No border read/effect |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/architecture/test_borders_boundaries.py` | create | Authority, import, class, route, pin, and leak checks |
| `tests/unit/test_borders_determinism.py` | create | Deterministic ids/digest/order/caps |
| `tests/unit/test_borders_e2e.py` | create | Real-tick in-process scenario |
| `index.md` | modify | Verification receipt rows after Task 25 |

## Task 23: Add the border boundary and determinism suite

### Intent

Make every non-negotiable authority claim executable. The suite must fail if a
future change adds an objective border/ownership field, a command path, a
peer-ledger read, a new event/command/migration, a raw-id publication, a score/
oracle, or a write route.

### Implementation Steps

1. Create `tests/architecture/test_borders_boundaries.py`:
   - `_BORDER_PATHS` covers:
     `src/agents/cognition/borders*.py`, `src/analysis/borders*.py`,
     `src/simulation/borders*.py`, `src/experiments/borders*.py`,
     `src/persistence/borders_filesystem.py`,
     `src/research_runner/borders_composition.py`,
     `src/api/routes/borders.py`, `src/api/borders_schemas.py`,
     `src/api/borders_cursor.py`.
   - `test_no_objective_border_or_owner_field_exists`:
     scan `src/world/` for `country_owner`, `sovereign`, `territory_owner`,
     `controller`, `border_owner`, `ownership`; assert absent.
   - `test_no_authority_or_registry_class_exists`:
     parse every border path and assert no class named `Border`,
     `CountryOwner`, `Sovereignty`, `TerritoryRegistry`, `BorderRegistry`,
     `BorderAuthority`, `BorderExecutor`, `WarState`, `LegitimacyOracle`,
     `TruthEngine`, `WinnerOracle`.
   - `test_no_command_construction_or_resolution`:
     AST scan for calls to `Attack(`, `Move(`, `Take(`, `Give(`, `Flee(`,
     `Help(`, `Feed(`, `Transport(`, `Wait(` anywhere in the border cognition/
     analysis/simulation modules. Allow `Tell(`, `Ask(`, and `Talk(` only inside
     `borders_communication.attach_border_relation`, where the helper must
     return the same command type with the frame appended; assert no new
     command type and no submission/resolution call exists.
   - `test_world_and_perception_never_read_border_ledgers`:
     `src/world/`, `src/simulation/engine.py`, `src/simulation/perception.py`,
     `src/observer/` contain no `borders` import or `BorderLedger` reference.
   - `test_analysis_modules_are_detached`:
     `src/analysis/borders*.py` do not import `agents.cognition`,
     `experiments`, `api`, `persistence`, `observer`, or `simulation` runtime.
   - `test_no_peer_ledger_read`:
     `apply_borders_update` has no parameter for another owner's ledger and no
     `require_owner_*` call for `organization`, `diplomacy`, `formal_rule`,
     `dispute`, `evidence`, `representation`, `conflict`, or `territory` other
     than the owner's own `territorial_claims`.
   - `test_snapshot_and_api_do_not_rebuild_analysis`:
     `src/simulation/borders_*` and `src/api/routes/borders.py` do not import
     `analysis`, `experiments`, or `agents.cognition`.
   - `test_exactly_six_get_routes`: parse the router; assert six `@router.get`
     and zero post/put/patch/delete.
   - `test_no_v2_route_or_protocol`: no `/v2` and no `observer-protocol-v2` in
     border paths.
   - `test_pins_are_unchanged`: commands 43, observer semantic types 73,
     replay `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, Alembic `0017`, 14 contexts,
     12 flags, 5 owned flags, metric catalog 176, six border routes.
   - `test_no_score_or_oracle_result_field`: forbidden field set is disjoint
     from every snapshot/API schema.
   - `test_godot_and_ui_are_read_only`: no POST/PUT/PATCH/DELETE in
     `clients/research-ui/src/api/borders.ts`; Godot `session.gd` border
     requests use GET and never put a token in a URL.
   - `test_no_raw_ids_in_publication`: snapshot rows, API schemas, UI types, and
     Godot payloads reject `AgentId`, `EntityId`, `EventId`, `RunId` fields.
   - `test_snapshot_summary_and_candidate_refs_resolve`: summary counts equal
     row lengths and every lineage/alignment candidate token resolves.
2. Create `tests/unit/test_borders_determinism.py`:
   - `test_identical_inputs_produce_identical_ids_digest_and_order`
   - `test_location_set_permutations_produce_the_same_domain_id`
   - `test_frame_order_permutations_produce_the_same_ledger_digest`
   - `test_repeated_update_is_idempotent`
   - `test_caps_are_deterministic_under_pressure`
   - `test_no_hash_uuid_or_wall_clock_symbol`
   - `test_canonical_snapshot_bytes_are_stable`
   Use Hypothesis for location permutations and frame permutations.
3. Command:
   `uv run --frozen --python 3.12.14 pytest tests/architecture/test_borders_boundaries.py tests/unit/test_borders_determinism.py -q`
4. Expected: all pass.

### Required Interfaces and Contracts

- The suite is read-only and offline.
- It asserts the absence of forbidden symbols, not a naming convention.
- It distinguishes the owner's own `territorial_claims` input from a peer
  ledger read.
- It asserts pins; no pin is weakened.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — no objective CountryOwner, no grid, four layers.
- Source: `.ai-factory/ARCHITECTURE.md` — Key Principles 1-5, "anti-patterns",
  "Objective authority and runtime".
- Source: V4-12 boundary suite precedent.
- Supported combinations: every forbidden symbol/route/pin is a separate test.

### Error Handling and Logging

- The suite is a test file; failures report the exact path and symbol.
- No application logging change.

### Tests

- The two files above.
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/architecture/test_borders_boundaries.py tests/unit/test_borders_determinism.py -q`
- Expected: all pass.

### Acceptance Criteria

- No objective border/owner field exists.
- No command construction/resolution path exists.
- No peer ledger read exists.
- No new event/command/migration/route/protocol exists.
- Pins are unchanged except 172 -> 176 and the six new routes/store/snapshot.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_borders_boundaries.py tests/unit/test_borders_determinism.py -q`
- Expected: pass.

## Task 24: Add the in-process border end-to-end scenario

### Intent

Prove the feature works with real `WorldEngine` ticks, real commands, real owner
carry, real publication, and all six routes, without PostgreSQL. The scenario is
part of the focused/unit lane, never an integration-only prerequisite.

### Implementation Steps

1. Create `tests/unit/test_borders_e2e.py` using the existing WorldEngine test
   fixtures:
   - Build a small world with at least three connected locations (`loc-a`,
     `loc-b`, `loc-c`), two agents, food/water, and a runner config on
     `runner-config-v56` with `v4_capability_flags.organizations=True` and
     deterministic territorial/organization modes.
   - Use real ticks:
     1. Agent A sleeps at `loc-a`, then `loc-b`; Agent B sleeps at `loc-c`.
     2. A forms a domain over `loc-a`/`loc-b`; B claims `loc-b`/`loc-c`.
     3. A sends a `bdr_v1` claim and proposal to B via `Tell`; B sends an
        acceptance via `Tell`.
     4. A observes B's physical use of `loc-b`; A retains an overlap/dispute
        and an agreement row.
     5. A sends an access expectation; B retains it as testimony.
     6. A attempts a physically possible `Move` into B's claimed location; it is
        admitted by ordinary world rules (no enforcement).
     7. A attempts a physically impossible move; existing rules reject it.
     8. Complete the run.
   - Export `border_ledgers`; assert owner-order and no None for enabled owners.
   - Build the harvest; publish to a temporary root; read the store.
   - Use `TestClient` with debug credentials and `PALIMPSEST_BORDERS_ROOT`/
     cursor key to call all six routes.
   - Assert:
     - summary reports four layers and counts;
     - claims page/detail return the domain and overlap;
     - agreements page/detail return the agreement with `apparent_acceptance` or
       `recognized`;
     - control page returns physical and analytical rows with `layer` filter;
     - no route returns a raw agent/location id, frame body, or evidence body;
     - no row contains a winner/sovereignty/legitimacy/score field.
   - Assert the objective event log contains no border field and no new event
     class.
2. Keep the test network-free and PostgreSQL-free. Use a temporary directory
   (`tmp_path`) for the store.
3. Add a deterministic twin assertion: rerun the same scenario with the same
   seed and inputs; assert identical border ledger digests and snapshot digest.
4. No test may be marked `integration`.
5. Command:
   `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_e2e.py -q`
6. Expected: all pass.

### Required Interfaces and Contracts

- Real `WorldEngine`, real `AgentRuntime`, real commands.
- Real publication store and all six routes.
- No PostgreSQL.
- No mocked border authority.
- Deterministic twin digest equality.
- Physical commands are still admitted/rejected by existing world rules, not by
  border beliefs.

### Requirement Evidence (when reconciliation applies)

- Source: Plan Settings — full strategy; original request — four layers.
- Source: `tests/unit/test_organized_conflict_e2e.py`.
- Supported combinations: claims, overlap, agreement, access expectation,
  physical use, retreat/denial does not block, publication, routes; all in one
  scenario.

### Error Handling and Logging

- The test uses deterministic fakes only.
- Any publication/store failure fails the test; it is not swallowed.
- No raw ids in assertion messages.

### Tests

- `tests/unit/test_borders_e2e.py`
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_e2e.py -q`
- Expected: all pass.

### Acceptance Criteria

- The scenario runs in-process without PostgreSQL.
- All four layers are produced from real ticks.
- All six routes serve the published snapshot.
- Border beliefs never block a physically possible command.
- Deterministic twin digests match.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_e2e.py -q`
- Expected: pass.

## Task 25: Execute the full V1-V4 regression and qualification lanes

### Intent

Run every required lane, record a truthful receipt, and never convert a missing
prerequisite into a skip-pass. Certification is allowed only when every required
lane is `executed_passed`.

### Implementation Steps

1. Execute the Python lanes with coverage:
   ```bash
   uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit tests/architecture -q
   ```
2. Execute the focused V4-13 suite:
   ```bash
   uv run --frozen --python 3.12.14 pytest \
     tests/unit/test_borders_*.py \
     tests/unit/test_borders_e2e.py \
     tests/architecture/test_borders_boundaries.py -q
   ```
3. Execute static gates:
   ```bash
   uv run --frozen --python 3.12.14 ruff check src tests
   uv run --frozen --python 3.12.14 mypy src tests
   uv run --frozen --python 3.12.14 lint-imports
   ```
4. Execute integration lanes when a disposable PostgreSQL/pgvector instance is
   available:
   ```bash
   PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m "integration and not scale" -q
   PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/benchmarks/ -q
   ```
   The database must be named with `palimpsest_test`; ambiguous targets fail
   closed.
5. Execute Compose configuration and the optional Compose/browser lane:
   ```bash
   docker compose config --quiet
   uv run --frozen --python 3.12.14 pytest -m compose -q
   ```
   The browser lane requires Docker, a real browser driver, and a source-attested
   image.
6. Execute the Godot 4.7.2 protocol suite:
   ```bash
   "${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd
   ```
   Expected: `godot_protocol_tests failed=0`.
7. Execute benchmark/scale:
   ```bash
   PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/benchmarks/ -q
   PALIMPSEST_V4_SCALE_IDS=10000 uv run --frozen --python 3.12.14 pytest tests/benchmarks/test_v4_scale_contract.py -q
   ```
8. Execute Research UI:
   ```bash
   cd clients/research-ui
   npx pnpm@10.34.9 test --run
   npx pnpm@10.34.9 check
   npx pnpm@10.34.9 build
   ```
9. Update the verification receipt in `index.md`:
   - every required lane is exactly one of `executed_passed`, `executed_failed`,
     `unexecuted`;
   - an `unexecuted` lane records its missing prerequisite;
   - never mark a skipped prerequisite as passed.
10. If any required lane fails or is unexecuted, leave certification
    `not certified` and report the exact lane/prerequisite. Do not weaken a test
    or a pin to force a pass.

### Required Interfaces and Contracts

- Receipt states: `executed_passed`, `executed_failed`, `unexecuted`.
- Required lanes: unit+architecture with coverage, focused V4-13, in-process
  E2E, V1-V4 regression, documentation parity, Ruff, Mypy, import-linter,
  integration, integration-scale, Compose config, Compose/browser, Godot,
  benchmark/scale, Research UI tests/check/build.
- Missing prerequisites are recorded, not hidden.
- No test marker is changed to make a lane green.

### Requirement Evidence (when reconciliation applies)

- Source: Plan Settings — full strategy.
- Source: `docs/development.md` commands.
- Source: V4-11/V4-12 qualification receipts.
- Supported combinations: each lane recorded independently; a failure blocks
  certification.

### Error Handling and Logging

- Capture a bounded summary of each lane (pass/fail counts, duration, missing
  prerequisite). Do not paste full logs into the plan.
- A failure names the command and the first safe error code.
- No credentials, DSNs, tokens, or payloads are recorded.

### Tests

- This task is the qualification run; it does not add unit tests.
- Commands: the exact lanes above.
- Expected: every required lane `executed_passed` for certification.

### Acceptance Criteria

- Every required lane has a truthful receipt.
- The focused suite and E2E are in the unit lane.
- Any unexecuted lane blocks certification.
- The report states the final certification outcome.

### Verification

- Re-read `index.md` receipt after updating.
- `git status --short` shows only intended plan/implementation/doc files; no
  roadmap edit.
- Expected: receipt is complete and consistent with the commands run.

## Phase Risks and Mitigations

- Risk: a missing PostgreSQL/Docker/Godot prerequisite is reported as a pass.
  Mitigation: the receipt uses `unexecuted` with the prerequisite; Task 25
  forbids skip-pass.
- Risk: the E2E is moved to integration to hide a failure.
  Mitigation: Task 24 asserts no `integration` marker and runs in the unit lane.
- Risk: a boundary test only checks names, not behavior.
  Mitigation: Task 23 includes AST scans, route counts, pin assertions, and
  behavior tests for command admission.
- Risk: coverage is disabled to save time.
  Mitigation: the unit+architecture command includes `--cov`.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass or are truthfully recorded as unexecuted
  with a prerequisite.
- `index.md` task checkboxes are updated immediately after verified completion.
