# Phase 7: Invariants, End-to-End Evidence, and Regression

Plan: [index.md](index.md)
Tasks: 19-21
Depends on: Phase 6 / Tasks 17-18

## Objective

Prove the V4-04 authority claims with executable boundaries, prove the full
operational path with a detached end-to-end fixture, and execute the complete
V1–V4 regression and qualification lanes. A required lane that cannot run is
recorded as `unexecuted` with its prerequisite; it is never a skip-pass.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_organization_boundaries.py` | 93-315 | The V4-03 boundary suite is the template; V4-04 adds a sibling suite rather than weakening it. |
| `tests/unit/test_organization_end_to_end.py` | `_config` 27-60; round trip 62-106 | The V4-04 E2E follows the real runner → harvest → snapshot → store path. |
| `tests/unit/test_organization_determinism.py` | deterministic twin pattern | Add operation-level twin assertions. |
| `tests/unit/test_organization_isolation.py` | owner isolation pattern | Add operation owner isolation. |
| `src/simulation/v4_architecture.py` | owned registry 103-121 | The flag/context split is already pinned. |
| `src/simulation/versioning.py` | reuse set 99-120; reservations 124-139 | No write pair may be allocated. |
| `src/world/models.py` | `Item` 114-139; `Resource` 141-153; `AgentBody` 189-230 | Objective possession has placement/inventory, never an organization owner field. |
| `src/world/production.py` | `Structure` 398-424 | `stored_quantity` is the only objective storage amount. |
| `src/world/artifacts.py` | `InformationArtifact` 314-350 | Custody is `holder_id`/`location_id`/`custodian_repository_id`. |
| `src/world/repositories.py` | `KnowledgeRepository` 148-280 | Access is a mode/founder list, not an organization permission. |
| `src/api/routes/organization.py` | route decorators | Five GET decorators, no write verb. |
| `clients/research-ui/src/api/organizations.ts` | read client | No write call. |
| `docs/development.md` | verification commands 600-615 | The canonical lane commands live here. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_organization_operations_boundaries.py` | create | Authority, dependency, no-teleport, no-owner-field, pin, and route checks. |
| `tests/unit/test_organization_operations_determinism.py` | create | Hypothesis identity/ordering/disagreement properties. |
| `tests/unit/test_organization_operations_isolation.py` | create | Owner-only update and no peer/world reads. |
| `tests/unit/test_organization_operations_end_to_end.py` | create | Harvest → v2 snapshot → store → API/UI read path. |
| `tests/unit/test_organization_operations_regression.py` | create | Focused V1–V4 gate that executes the new families and preserves old pins. |
| `tests/architecture/test_organization_boundaries.py` | modify | Intentional 144 → 146 and current-write v2 pin updates only. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Intentional 144 → 146 pin only. |
| `tests/unit/test_organization_catalog.py` | modify | Intentional 144 → 146 and last-two family order. |
| `tests/unit/test_organization_publication.py`, `test_organization_api.py`, `test_organization_end_to_end.py`, `test_organization_docs.py` | modify | Current-write schema v2, five routes, 146; keep v1 fixture coverage. |
| `docs/development.md` | modify only in Task 22 | Add the new test commands during the docs checkpoint. |

## Task 19: Add the operational boundary and determinism suite

### Intent

Make every negative claim executable: no organization actor, no treasury, no
teleport, no objective ownership, no peer ledger, no new command/event/migration,
and deterministic provenance.

### Implementation Steps

1. Create `tests/architecture/test_organization_operations_boundaries.py` with
   `pytestmark = pytest.mark.architecture` and module globs:
   - `COGNITION_OPERATION_MODULES = src/agents/cognition/organization_operation*.py`
   - `ANALYSIS_OPERATION_MODULES = src/analysis/organization_operation*.py`
   - `SIMULATION_OPERATION_MODULES = src/simulation/organization_*.py`
   - `PERSISTENCE_OPERATION_MODULES = src/persistence/organization_filesystem.py`
   - `API_OPERATION_MODULES = src/api/routes/organization.py`,
     `src/api/organization_schemas.py`, `src/api/organization_cursor.py`
   - `BRIDGE_OPERATION_MODULES = src/experiments/organization_harvest.py`,
     `src/experiments/organization_publication.py`
   - `RUNNER_OPERATION_MODULES = src/research_runner/organization_composition.py`
2. Dependency checks:
   - analysis operation modules do not import `agents`, `experiments`, `api`,
     `persistence`, `infrastructure`, or `observer`;
   - simulation operation modules do not import `analysis`, `api`,
     `persistence`, `infrastructure`, `experiments`, or `observer`;
   - persistence/API do not import `analysis` or `agents.cognition`;
   - bridge/runner do not import `api`.
3. Authority checks:
   - no class name in `MAGIC_ACTOR_TOKENS` or
     `{OrganizationActor, OrganizationTreasury, OrganizationRegistry,
     GlobalOrganizationRegistry, ResourcePool, CentralBank, WorldGovernment,
     Ministry}`;
   - no `WorldState`, `WorldEngine`, `ActionSubmission`, `TickToken`, `EventStore`,
     `PhysicalRules`, or `AgentCommand` symbol in operation cognition/analysis
     modules;
   - no class ending in `Command`/`Event`;
   - no method/function named `teleport`, `teleport_resources`, `execute`,
     `execute_action`, `transfer_resources`, or `move_resources` in operation
     modules;
   - `apply_organization_operation_update` parameters contain no `peer`,
     `other_owner`, `all_ledgers`, `runtimes`, `world_state`, or `event_store`.
4. Objective-possession separation:
   - scan `src/world/models.py`, `production.py`, `artifacts.py`,
     `repositories.py` for `organization` and for an `owner_id`/`ownership` field
     on `Item`, `Resource`, `Structure`, `InformationArtifact`,
     `KnowledgeRepository`; assert none;
   - scan every `src/world/**/*.py` for `organization_operation`; assert none;
   - assert objective placement fields (`holder_id`, `location_id`,
     `custodian_repository_id`, `stored_quantity`) remain the only custody/storage
     fields.
5. Pin checks:
   - events max 22; codec v20 accepted and v21 not; commands 43; observer
     semantics 73; metric families 146; Alembic `0017` and no `0018_*.py`;
   - `runner-config-v56` accepted, no `v57`; `organizations` owned; other eleven
     unowned/fail-closed;
   - 14 contexts / 12 flags / `v4-context-map-v2`; four reservations; no
     `organizations` reservation;
   - `observer-protocol-v1`; four advertised/six reserved capabilities;
     `organization_rows` reserved.
6. Update the existing pin assertions that intentionally change, without
   weakening any other assertion:
   - `tests/architecture/test_organization_boundaries.py`: 144 → 146; schema
     expectations v1 → v2 where the test writes a current artifact;
   - `tests/architecture/test_v4_architecture_invariants.py`: 144 → 146;
   - `tests/unit/test_organization_catalog.py`: 144 → 146 and the new last-two
     family order;
   - `tests/unit/test_organization_publication.py`,
     `tests/unit/test_organization_api.py`,
     `tests/unit/test_organization_end_to_end.py`: current-write schema v2;
     keep explicit v1 fixture coverage;
   - `tests/unit/test_organization_docs.py`: 144 → 146 and five routes;
   - any other exact `organization-snapshot-v1` current-write assertion.
7. Surface checks:
   - the organization router contains only GET decorators (five routes);
   - the Research UI organization client contains no POST/PUT/PATCH/DELETE;
   - the snapshot codec imports no analysis module;
   - the persistence/API modules import no analysis.
8. Create `tests/unit/test_organization_operations_determinism.py`:
   - Hypothesis strategies generate control/admission/assignment/procedure/
     decision/action records;
   - same material → same `orgd-`/`orga-`/`orgop-` id;
   - changing any material field changes the id;
   - sorted input permutations produce the same ledger rows/ids;
   - conflicting stances produce `disputed` with both sides retained;
   - no `hash()`/`uuid`/wall-clock usage in the module source.
9. Create `tests/unit/test_organization_operations_isolation.py`:
   - the update reads only the owner observation and prepared owner ledgers;
   - a peer ledger or world-state object is rejected/not accepted;
   - an owner's operation ledger never contains another owner's id;
   - a foreign-owner checkpoint fails.

### Required Interfaces and Contracts

- The V4-03 boundary suite is not weakened; the new suite is additive.
- The no-teleport check is semantic and textual: no operation module may name a
  method that moves resources or executes actions.
- Objective possession remains `holder_id`/`location_id`/`stored_quantity`; an
  organization control belief is never a world field.
- Determinism means identical evidence → identical bytes/ids, not identical wall
  clock or process state.

### Requirement Evidence

- Original Request: "Do not allow an Organization object to teleport resources or
  execute physical actions. Agent-mediated actions must produce all physical
  effects."
- Original Request: "Keep objective physical possession separate from
  subjective/legal ownership."
- `.ai-factory/RULES.md` axioms 1-5 and `.ai-factory/ARCHITECTURE.md` Key
  Principles 1-2.

### Error Handling and Logging

- The suite fails with the file/symbol and expected/actual value; no payloads.
- No production logging change.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_organization_operations_boundaries.py tests/unit/test_organization_operations_determinism.py tests/unit/test_organization_operations_isolation.py -q`
- Expected: pass.

### Acceptance Criteria

- Every authority, dependency, no-teleport, no-owner-field, and pin claim is
  executable.
- Determinism and disagreement properties pass.
- The V4-03 suite still passes.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_organization_operations_boundaries.py tests/architecture/test_organization_boundaries.py tests/unit/test_organization_operations_determinism.py tests/unit/test_organization_operations_isolation.py -q`
- Expected: pass.

## Task 20: Add the operational end-to-end scenario

### Intent

Prove the real path from owner beliefs to publication and inspection, including
disagreement and the flags-off passthrough, without granting the organization any
world authority.

### Implementation Steps

1. Create `tests/unit/test_organization_operations_end_to_end.py` using the
   V4-03 E2E config pattern:
   - a `runner-config-v56` config with `V4CapabilityFlags(organizations=True)`;
   - one or two agents, a location, a repository/collective project or a store;
   - enough ticks for observation.
2. Build owner operation ledgers by calling the real
   `apply_organization_operation_update` with prepared concept/office/decision/
   commitment/possession inputs. Do not hand-construct records that the update
   cannot produce.
3. Build a completed-run harvest with the real
   `build_completed_run_organization_harvest` where possible; if the scenario
   cannot naturally produce speech/actions in the tick budget, use a typed
   `RunnerResult`-compatible fixture carrying the real ledgers and document why.
4. Compose `organization-snapshot-v2` with
   `build_organization_harvest_result`; publish to `tmp_path` with
   `create_organization_publisher`; read with `create_organization_reader`.
5. Assert:
   - summary schema is v2 and `operation_count > 0`;
   - candidate detail contains operations;
   - operations page filters by domain and candidate;
   - all operation ids are `orgop-`; no `orgc-`/`orgd-`/`orga-`/owner ids appear
     in the encoded artifact;
   - objective rows contain no organization ids;
   - the scientific result/objective hash is unchanged by publication.
6. Add a disagreement variant: two owners with incompatible admission/control
   claims; both operations are published with contested counts; neither is
   dropped.
7. Add a flags-off variant: no operation ledger, no operation metrics, no
   publication; the run trajectory is unchanged versus the V4-03 baseline.
8. Add a deterministic twin: same seed/config → identical snapshot bytes and
   publication id.
9. Add an API-level read test using the FastAPI test client and a temporary
   `PALIMPSEST_ORGANIZATION_ROOT`; assert the fifth route returns the published
   operations and requires `SUBJECTIVE_DEBUG`.
10. Add a Research UI assertion by extending the panel test fixture (the vitest
    lane runs in Task 21).

### Required Interfaces and Contracts

- The organization never executes a command; the scenario's physical effects are
  ordinary commands.
- Publication never changes the scientific result.
- Disagreement is preserved, not resolved by the analysis.
- The artifact is v2; v1 fixtures remain readable.
- The E2E test must not require Docker/PostgreSQL.

### Requirement Evidence

- Original Request: "Agent-mediated actions must produce all physical effects";
  "Record provenance of decisions and actions."
- V4-03 E2E pattern.
- `.ai-factory/ARCHITECTURE.md` "Read-only presentation" and publication
  isolation.

### Error Handling and Logging

- The test uses safe codes for disabled/missing/failed states.
- No payload assertions log private content; assertions inspect counts/ids only.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_end_to_end.py -q`
- Expected: pass.

### Acceptance Criteria

- The full operational path works and is deterministic.
- Disagreement and flags-off behavior are proven.
- No world authority is created.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_end_to_end.py -q`
- Expected: pass.

## Task 21: Execute the full V1-V4 regression and qualification lanes

### Intent

Produce an honest, three-state qualification receipt. Every required lane either
passes with evidence or is recorded as unexecuted with its prerequisite.

### Implementation Steps

1. Run the unit + architecture suite with coverage:
   `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term`.
2. Create `tests/unit/test_organization_operations_regression.py` with focused
   assertions: 146 metric families; the two operation families at the end; five
   GET-only organization routes; v1/v2 snapshot acceptance; no
   `runner-config-v57`; 14 contexts / 12 flags / `v4-context-map-v2`; and the
   exact value keys of `organization_operation_authority@1`.
3. Run the focused V1–V4 gates:
   `tests/unit/test_v1_regression_gate.py`,
   `tests/unit/test_v2_scientific_invariants.py`,
   `tests/unit/test_organization_*.py`,
   `tests/architecture/test_organization_*.py`,
   `tests/architecture/test_v4_*.py`.
4. Run static gates:
   `uv run --frozen --python 3.12.14 ruff check src tests`,
   `uv run --frozen --python 3.12.14 mypy src tests`,
   `uv run --frozen --python 3.12.14 lint-imports`.
5. Run the Research UI lane with the pinned local executables:
   `cd clients/research-ui && node_modules/.bin/vitest run`,
   `cd clients/research-ui && node_modules/.bin/svelte-check --tsconfig ./tsconfig.json`.
6. Run `docker compose config --quiet`.
7. Run the integration lane against a disposable `palimpsest_test` PostgreSQL with
   pgvector:
   `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m integration`;
   if no host-reachable instance exists, record `unexecuted` with that
   prerequisite.
8. Run the Compose/browser acceptance lane from `docs/development.md`:
   `docker compose config --quiet`, then the pinned Compose browser file with
   `PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL` and
   `PALIMPSEST_COMPOSE_RESEARCH_RUN_ID`; if Docker or the browser driver is
   unavailable, record `unexecuted`.
9. Run the pinned Godot 4.7.2 suite with `GODOT_BIN`:
   `"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit`
   and
   `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`;
   if unset, record `unexecuted` with `godot-4.7.2`.
10. Run the opt-in benchmark/scale regression lane:
   `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m "integration and scale" tests/benchmarks/ -q`;
   if not selected, record `unexecuted` with the opt-in prerequisite.
11. Record a table with one state per lane:
    `executed_passed`, `executed_failed`, or `unexecuted` + prerequisite.
    Never write "skipped pass". Include test counts, coverage, and any failures.

### Required Interfaces and Contracts

- Python lanes keep coverage enabled.
- Integration tests use disposable names containing `palimpsest_test` and fail
  closed on ambiguous migration targets.
- No lane is silently omitted; a missing prerequisite is explicit.
- The receipt is stored in the final plan entrypoint by Task 23.

### Requirement Evidence

- Plan Settings: "Testing: yes; full strategy".
- `docs/development.md` verification commands.
- `.ai-factory/ARCHITECTURE.md` requirement 3: keep V1/V2 gates green.

### Error Handling and Logging

- Summarize command output; do not dump full logs or payloads.
- Report a failing lane with the first failing test/command and the safe code.

### Tests

- All commands above.
- Expected: unit/architecture/static/UI/compose-config pass; any missing
  integration/Compose/Godot/benchmark lane is recorded `unexecuted`.

### Acceptance Criteria

- Every required lane has one of the three states.
- No skip-pass is recorded.
- Failures are fixed or the lane is recorded and certification is withheld.

### Verification

- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- Expected: unit/architecture/static pass; receipt complete.

## Phase Risks and Mitigations

- Risk: boundary tests only check imports and miss semantic authority.
  Mitigation: add no-teleport/no-owner-field/method-name checks and objective
  model scans.
- Risk: the E2E uses hand-built records that the update cannot produce.
  Mitigation: build through `apply_organization_operation_update`; document any
  typed fixture seam.
- Risk: a missing lane is reported as a pass.
  Mitigation: three-state receipt and explicit prerequisites.

## Phase Completion Checklist

- Every Task 19-21 acceptance criterion is met.
- Boundaries, determinism, isolation, and E2E pass.
- The regression receipt is complete and honest.
- `index.md` task checkboxes are updated immediately after verified completion.
