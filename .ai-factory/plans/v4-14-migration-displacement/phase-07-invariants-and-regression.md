# Phase 7: Invariants, End-to-End Migration, and Regression

Plan: [index.md](index.md)
Tasks: 23-25
Depends on: Phases 1-6 / Tasks 1-22

## Objective

Prove the authority, isolation, determinism, and no-telepathy claims; run a
real in-process migration scenario through publication and all six routes; then
execute the full V1-V4 regression and qualification lanes with an honest
receipt.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `tests/architecture/test_borders_boundaries.py` | forbidden classes 36-49; path set 15-30; import scans 84-120; command scan 144-165 | Exact boundary-test pattern |
| `tests/architecture/test_analysis_isolation.py` | analysis import rules 79-264 | Analysis isolation pattern |
| `tests/architecture/test_v4_architecture_invariants.py` | 14 contexts / 12 flags and pins | Registry pins |
| `tests/unit/test_borders_determinism.py` | permutation and digest cases | Determinism test shape |
| `tests/unit/test_borders_e2e.py` | in-process publication and routes | E2E test shape |
| `tests/unit/test_regional_cross_feature_invariants.py` | arrival/benefit/replay 45-183 | Regional conservation pattern |
| `tests/unit/test_regional_verification_regressions.py` | route cost and grouped transport 114-256 | Regional regression pattern |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` | 180 pin |
| `src/world/_rules.py` | `COMMAND_RULE_MATRIX` | 43-command pin |
| `src/observer/version.py` | `SEMANTIC_EVENT_TYPES` | 73 observer semantic types |
| `src/simulation/persistence.py` | `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` | codec v20 |
| `src/world/events.py` | `EVENT_SCHEMA_REPLAY_V22` | replay v22 |
| `tests/integration/test_migrations.py` | Alembic head 0017 | migration pin |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/architecture/test_migration_displacement_boundaries.py` | create | Authority, import, forbidden-name, command, route, and pin boundaries |
| `tests/unit/test_migration_displacement_determinism.py` | create | Permutation, digest, ID, and ordering invariance |
| `tests/unit/test_migration_displacement_e2e.py` | create | In-process migration, publication, six routes |
| `index.md` | modify | Record the Task 25 verification receipt |

## Task 23: Add the migration-displacement boundary and determinism suite

### Intent

Make every architectural claim executable. The suite proves owner-only
authority, no objective refugee/migration object, no command path, no peer or
world ledger read, no grid/geometry, no identity mutation, and unchanged pins.

### Implementation Steps

1. Create `tests/architecture/test_migration_displacement_boundaries.py` with:
   - `MIGRATION_PATHS` covering:
     `src/agents/cognition/migration_displacement*.py`,
     `src/analysis/migration_displacement_*.py`,
     `src/simulation/migration_displacement_*.py`,
     `src/experiments/migration_displacement_*.py`,
     `src/persistence/migration_displacement_filesystem.py`,
     `src/research_runner/migration_displacement_composition.py`,
     `src/api/routes/migration_displacement.py`,
     `src/api/migration_displacement_schemas.py`,
     `src/api/migration_displacement_cursor.py`.
   - `FORBIDDEN_CLASSES`:
     `Refugee`, `RefugeeStatus`, `AsylumSeeker`, `DisplacedPerson`,
     `RefugeeCamp`, `ResettlementAuthority`, `MigrationRegistry`,
     `WaveRegistry`, `MigrationWave`, `CauseOracle`, `IntegrationOracle`,
     `AssimilationScore`, `WellbeingScore`, `ForcedMigrationClassifier`,
     `MigrationAuthority`, `MigrationExecutor`, `CountryOwner`, `Border`,
     `TerritoryRegistry`.
   - `FORBIDDEN_COMMANDS`:
     `Migrate`, `Evacuate`, `Resettle`, `Deport`, `Expel`, `Admit`,
     `Integrate`, `FleeTo`, `Defend`, `Guard`, `Protect`, `Block`, `Seize`,
     `Enforce`, `Claim`.
   - assert no migration module defines a forbidden class or command name.
   - assert no `agents/cognition/migration_displacement*.py` imports
     `world._state`, `world._perception`, `simulation.engine`,
     `simulation.bootstrap`, `AgentCommand`, `ActionSubmission`, `WorldEvent`,
     or a peer ledger; analysis modules may import public event classes such as
     `Moved`/`JourneyStarted`, but never the private event store.
   - assert `src/analysis/migration_displacement_*.py` does not import
     `agents.cognition`, `experiments`, `api`, `persistence`, or `observer`.
   - assert `src/simulation/migration_displacement_*.py` does not import
     `analysis`, `api`, `experiments`, `infrastructure`, `persistence`, or
     `observer`.
   - assert `src/api/routes/migration_displacement.py` imports no analysis.
   - assert no migration module contains `hash(`, `uuid`, `datetime.now`, or
     `time.time`.
   - assert no migration module contains a grid, coordinate, polygon, area, or
     region-to-border conversion.
   - assert `region_to_border`, `country_owner`, `sovereign`, `controller`,
     `territory_owner`, and `ownership` do not appear as fields.
2. Add pin assertions:
   - `METRIC_FAMILY_COUNT == 180`;
   - four migration families at positions 177-180;
   - `len(COMMAND_RULE_MATRIX) == 43`;
   - `len(SEMANTIC_EVENT_TYPES) == 73`;
   - `len(V4_CONTEXTS) == 14`;
   - `len(V4_CAPABILITY_FLAGS) == 12`;
   - five owned flags exactly;
   - `EVENT_SCHEMA_REPLAY_V22 == 22` and codec `v20` accepted;
   - Alembic head `0017`, no `0018` file;
   - six migration routes registered;
   - six cursor purposes.
3. Create `tests/unit/test_migration_displacement_determinism.py`:
   - all row/token/candidate outputs are permutation invariant;
   - equal inputs produce equal IDs and digests;
   - changed confidence, route, cause, cluster, or tick changes the ID;
   - canonical JSON has sorted keys and no raw identities;
   - wave/cluster/outcome ordering is total;
   - no `hash()`, UUID, wall clock, or global RNG.
4. Add no-telepathy cases:
   - two owners with identical movements but no frames keep separate ledgers;
   - an analytical wave exists without shared cognition state;
   - a `MigrationDisplacementLedger` is owner-scoped and cannot be merged
     across owners;
   - same-root testimony is counted once.
5. Add no-command-path cases:
   - scan the migration modules for command constructors;
   - assert the bias helper returns a mapping, not a command;
   - assert no migration module calls an executor or admission function.

### Required Interfaces and Contracts

- A violation is a test failure, not a warning.
- The suite reads source text and ASTs only; it never imports private world
  authority.
- Existing boundary suites remain green.
- Pins are asserted, never weakened.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — no hard-coded Refugee category; no collective
  telepathy; research analytics only.
- Source: `.ai-factory/ARCHITECTURE.md` — Key Principle 1, capability
  ownership, versioned extension contract.
- Source: V4-13 `test_borders_boundaries.py`.
- Supported combinations: every forbidden name; every import direction; every
  pin; each no-telepathy case; each no-command case.

### Error Handling and Logging

- The test suite does not log payloads; assertion messages name the path and
  rule only.
- A missing migration file fails the test with a stable path list.
- A pin mismatch fails with the exact expected/actual value.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_migration_displacement_boundaries.py tests/unit/test_migration_displacement_determinism.py -q`
- Expected: all pass.

### Acceptance Criteria

- Every authority, isolation, forbidden-name, determinism, and pin claim is
  executable.
- No command, event, write pair, codec, migration, or route version is added.
- Existing boundary suites remain green.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_migration_displacement_boundaries.py tests/unit/test_migration_displacement_determinism.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_borders_boundaries.py tests/architecture/test_analysis_isolation.py -q`
- Expected: pass.

## Task 24: Add the in-process migration end-to-end scenario

### Intent

Exercise the feature with real ticks, ordinary commands, resource scarcity, an
environmental hazard, a conflict, an opportunity, a social cluster, a cause
frame, publication, and all six routes, without PostgreSQL. The scenario must
prove that waves emerge from independent decisions, not shared telepathy.

### Implementation Steps

1. Create `tests/unit/test_migration_displacement_e2e.py` with a deterministic
   fixture:
   - a region topology with at least three regions and adjacent routes;
   - at least four founders with different needs, relationships, and kinship;
   - run-level `regions_migration` with `cognition_mode=DETERMINISTIC`;
   - `multi_polity_migration` and `organizations` enabled;
   - `institution_concept_mode=DETERMINISTIC` (or the owned institution seam
     required so institution cause evidence is available — not optional);
   - resource scarcity at origin (depleted resource and a need deficit);
   - an environmental hazard at origin;
   - a conflict event or hostile observation at origin;
   - an opportunity at destination (resource or collective project);
   - a kinship/social cluster spanning at least two movers;
   - no shared wave object and no pre-seeded wave.
2. Drive real ticks:
   - let agents independently select ordinary `Move`/`Transport`/`Flee`
     commands through real `WorldEngine` admission;
   - deliver at least one `mdp_v1` route/cause frame from one mover to another
     via real speech attach/delivery;
   - keep at least one mover without the frame to prove independent movement.
3. Assert:
   - origin, route, and destination are tracked in owner rows and objective
     movement rows;
   - cause evidence includes resource scarcity, environmental hazard, conflict,
     opportunity, social network, **and institution** (all six drivers);
   - the analytical wave has at least two independent participants;
   - displacement-like classification is present only with independent causal
     evidence;
   - integration outcomes include at least one settled/transient/returned/onward
     case;
   - the two movers without a frame still form an analytical wave but do not
     share a ledger;
   - no agent receives another owner's raw ledger or cause content;
   - the real completed-run collector → `metric_service` /
     `assemble_arm_metric_bundle` path emits all four migration metric
     documents.
4. Publish:
   - build the completed-run harvest;
   - publish to a temporary `PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT`;
   - create the FastAPI test client with the reader and cursor codec;
   - call all six routes and assert 200, tokens only, and cursor reuse on the
     same binding;
   - reuse a cursor after changing run/publication/digest/purpose/filter and
     assert 400 `migration_displacement_cursor_invalid`.
5. Call the routes once with the reader unset and assert 503
   `migration_displacement_disabled`; call an unknown wave and assert 404.
6. Assert no PostgreSQL, Docker, network, or external provider is required.
7. Keep the test deterministic across two runs with the same seed.

### Required Interfaces and Contracts

- The E2E runs in the focused/unit lane and is never reported as
  integration-only.
- It uses real `WorldEngine` admission and real committed events.
- It uses the real filesystem store and real API routes, not fakes, for the
  publication/read path.
- It may use deterministic fake cognition providers; it must not call an
  external LLM.
- A missing publication is `disabled`/`unavailable`, never a fabricated success.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — six causes, origin/route/destination, clusters,
  integration outcomes, waves without telepathy.
- Source: Plan Settings — focused in-process E2E without PostgreSQL.
- Source: `tests/unit/test_borders_e2e.py`.
- Supported combinations: with/without frame; two independent movers; one
  mover; scarce/hazard/conflict/opportunity/social/institution causes;
  settled/transient/returned/onward outcomes; cursor reuse; cursor binding
  change 400; disabled/404 routes; real metric assembly.

### Error Handling and Logging

- The test logs counts only; it never prints tokens, routes, causes, frames, or
  participant ids.
- A failed assertion identifies the layer and row count, not the payload.
- A missing publication fails with the receipt status.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_e2e.py -q`
- Expected: 2 passed (full and disabled/404 path), no PostgreSQL.

### Acceptance Criteria

- The scenario exercises real ticks, commands, publication, and six routes.
- Waves form without shared cognition state.
- The test is deterministic and PostgreSQL-free.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_e2e.py -q`
- `rg -n "postgres|asyncpg|testcontainers|docker" tests/unit/test_migration_displacement_e2e.py` — expected: no matches.
- Expected: pass.

## Task 25: Execute the full V1-V4 regression and qualification lanes

### Intent

Run every required lane, record exactly one state per lane, and block
certification on any missing prerequisite. Task completion is not
certification.

### Implementation Steps

1. Run the full Python lane with coverage:
   `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit tests/architecture -q`
2. Run the focused V4-14 suite:
   `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_*.py tests/architecture/test_migration_displacement_boundaries.py -q`
3. Run the focused E2E:
   `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_e2e.py -q`
4. Run documentation parity:
   `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_docs.py tests/unit/test_*_docs.py -q`
5. Run static gates:
   - `uv run --frozen --python 3.12.14 ruff check src tests`
   - `uv run --frozen --python 3.12.14 mypy src tests`
   - `uv run --frozen --python 3.12.14 lint-imports`
6. Run Compose configuration:
   `docker compose config --quiet`
7. Run integration and optional lanes when prerequisites exist:
   - `uv run --frozen --python 3.12.14 pytest -m "integration and not scale" -q`
   - `uv run --frozen --python 3.12.14 pytest -m "integration and scale" -q`
   - `uv run --frozen --python 3.12.14 pytest -m compose -q`
   - Godot 4.7.2 protocol and migration overlay suites;
   - benchmark/scale harness;
   - Research UI `npx pnpm@10.34.9 test --run`, `check`, `build`.
8. Update the receipt in `index.md`:
   - every lane is `executed_passed`, `executed_failed`, or `unexecuted`;
   - an `unexecuted` lane carries its missing prerequisite;
   - do not convert a skip into a pass;
   - do not reuse a prior coverage baseline.
9. If a lane fails, fix the implementation or record `executed_failed`; do not
   weaken a pin or assertion.
10. Keep the scientific result unchanged by any publication or presentation
    failure.

### Required Interfaces and Contracts

- Required lanes: unit+architecture+coverage, focused suite, E2E, regression
  selection, docs parity, Ruff, Mypy, import-linter, Compose config,
  integration, integration-scale, Compose/browser, Godot, benchmark, Research UI
  tests/check/build.
- A missing PostgreSQL/pgvector instance, browser driver, Godot binary, or
  benchmark harness leaves the lane `unexecuted` with the prerequisite.
- Certification requires every required lane `executed_passed`.

### Requirement Evidence (when reconciliation applies)

- Source: Plan Settings — full strategy.
- Source: `.ai-factory/ARCHITECTURE.md` — tests and verification requirements.
- Source: V4-13 verification receipt precedent.

### Error Handling and Logging

- Record only counts, statuses, and safe codes in the receipt.
- Never paste tokens, payloads, prompts, credentials, DSNs, or bodies.
- A failure records the command, exit status, and a bounded error summary.

### Tests

- The lane commands above.
- Expected: all required lanes pass; external lanes either pass or are recorded
  `unexecuted` with a prerequisite.

### Acceptance Criteria

- Every required lane has a truthful state.
- No lane is reported as integration-only when it is unit-capable.
- Certification is withheld if any required lane is unexecuted or failed.

### Verification

- `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit tests/architecture -q`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- `uv run --frozen --python 3.12.14 lint-imports`
- `docker compose config --quiet`
- Expected: pass or a truthful `unexecuted` receipt.

## Phase Risks and Mitigations

- Risk: a boundary test only scans a subset of files.
  Mitigation: Task 23 uses explicit globs for every new module and test.
- Risk: the E2E uses a fake store and hides integration bugs.
  Mitigation: Task 24 uses the real filesystem store and real API routes.
- Risk: a required lane is skipped silently.
  Mitigation: Task 25 records `unexecuted` with a prerequisite and blocks
  certification.
- Risk: a failed lane is hidden by a green focused suite.
  Mitigation: Task 25 records each lane separately; Task 27 audits the receipt.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
