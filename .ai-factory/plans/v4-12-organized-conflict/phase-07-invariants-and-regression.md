# Phase 7: Invariants, End-to-End Conflict, and Regression

Plan: [index.md](index.md)
Tasks: 22-24
Depends on: Phase 6

## Objective

Prove the organized-conflict contract with architecture and determinism tests,
exercise the complete in-process path with real ticks and existing commands, and
run the full V1-V4 regression and qualification lanes with an honest receipt.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_diplomacy_boundaries.py` | ownership 73-107; no command 134-160; no world read 163-172; forbidden symbols 175-201; routes 256-265; wire pins 268-286; existing pins 543-556 | Boundary test pattern |
| `tests/architecture/test_treaty_boundaries.py` | no authority 35-57; forbidden fields 60-84; pins 87-90; routes 101-108; world no-read 111-120; no command 123-139; analysis detachment 142-163; identity 166-184; bounds 187-204; no v2 207-214; observer 217-225 | Additional boundary pattern |
| `src/simulation/v4_architecture.py` | `validate_v4_contexts` 335-430 | Registry invariants |
| `src/simulation/runner_models.py` | `V4CapabilityFlags` 1115-1165; v56 gate 7996-8008 | Ownership and schema pins |
| `src/analysis/specifications.py` | count 53; tail 238-245; `_BUILDERS` 7978-7986; validation 8007-8032 | Catalog pins |
| `tests/unit/test_diplomacy_e2e.py` | full in-process path 368+; flags off 588; export 606 | E2E pattern |
| `tests/physical_helpers.py` | `PhysicalWorldFixture`, `two_location_fixture`, `dead_body`, `stressed_body` 64-299+ | World fixtures for real ticks |
| `tests/unit/physical/test_action_effects.py` | attack lethal 162-227; flee/search 228-240; help 97-161 | Command outcome fixtures |
| `tests/unit/test_regional_travel_actions.py` | grouped transport 137-170; flee 171-210 | Movement group fixtures |
| `tests/unit/test_death_corpse_custody.py` | attack death custody 166-212 | Capture fixture |
| `pyproject.toml` | pytest markers and coverage settings | Lane commands |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_organized_conflict_boundaries.py` | create | Full boundary/determinism suite |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Five owned flags |
| `tests/architecture/test_v3_baseline_inventory.py` | modify | 172 baseline |
| `tests/architecture/test_diplomacy_boundaries.py` | modify | Conflict ownership and route pins |
| `tests/architecture/test_treaty_boundaries.py` | modify | 172 pin |
| `tests/unit/test_organized_conflict_e2e.py` | create | In-process end-to-end scenario |
| `tests/unit/test_organized_conflict_determinism.py` | create | Repeated-run digest equality |
| `tests/unit/test_organized_conflict_catalog.py` | modify | 172 and first-168 guard |

## Task 22: Add the conflict boundary and determinism suite

### Intent

Make every architectural claim in the index executable: no war state, no army,
no registry, no command path in beliefs, no world/peer read, no identity
mutation, no new wire surface, and deterministic IDs.

### Implementation Steps

1. Create `tests/architecture/test_organized_conflict_boundaries.py`.
2. Ownership assertions:
   - `V4_OWNED_CAPABILITY_FLAGS` equals the five-flag set;
   - `organized_conflict` is owned and `unimplemented_enabled_names()` is empty;
   - `organized_conflict` alone fails with `v4_prerequisite_missing`;
   - `organized_conflict` + `diplomacy` constructs on v56;
   - v4/v55 fail with `v4_capability_requires_v56`;
   - no `runner-config-v57` string in `src/`.
3. Forbidden-object assertions over `src/agents/cognition/organized_conflict*`,
   `src/analysis/organized_conflict_*`, `src/simulation/organized_conflict_*`,
   `src/experiments/organized_conflict_*`, and
   `src/persistence/organized_conflict_*`:
   - no class named `WarState`, `ConflictRegistry`, `ArmyActor`, `Legion`,
     `Battalion`, `Battle`, `Front`, `VictoryOracle`, `LegitimacyOracle`,
     `ConflictAuthority`, or `ConflictExecutor`;
   - no `at_war`, `war_state`, `army`, `victory`, `defeat`, `winner`, `loser`,
     `legitimacy`, `score`, or `composite` field;
   - no `RelationScore`, `ViolenceScore`, `EscalationIndex`, or `OverallConflict`.
4. Command-path assertions:
   - `organized_conflict.py` and `organized_conflict_communication.py` do not
     contain `AgentCommand` construction;
   - `organized_conflict_actions.py` may import and construct only existing
     command classes (`Attack`, `Move`, `Flee`, `Help`, `Feed`, `Transport`,
     `Take`, `OpposePublicGood`, `Tell`), and contains no new command class;
   - no `submit`, `admit`, `resolve`, or `execute` call in any conflict module;
   - the screen returns only existing command types.
5. World/peer read assertions:
   - no `WorldState`, `WorldEvent`, `world._`, `simulation.engine`,
     `persistence`, or `api` import in cognition/analysis conflict modules;
   - `WorldEngine`, perception, admission, stop selectors, memory, prompts, and
     observer do not mention `organized_conflict` or `ConflictLedger`;
   - analysis does not import experiments, persistence, API, or cognition.
6. Identity assertions:
   - `organized_conflict_identity.py` does not call `mint`, `rename`, `split`,
     `merge`, or `dissolve` on `org-`/`msoc-`;
   - joins are read-only.
7. Snapshot/store/route pins:
   - `ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA == "organized-conflict-snapshot-v1"`;
   - `ORGANIZED_CONFLICT_STORE_SCHEMA == "organized-conflict-store-v1"`;
   - exactly six routes and six cursor purposes;
   - no `/v2` route, no `observer-protocol-v2`, no Godot mention.
8. Wire pins:
   - commands 43; observer semantic types 73; replay `EVENT_SCHEMA_REPLAY_V22`;
     codec `v20`; Alembic `0017`; no `0018`;
   - metric families 172; first 168 digest/order unchanged; no 168 current pin
     remains in tests or docs;
   - no new write pair (events 23-26 / codecs v21-v24 remain reserved).
9. Determinism assertions:
   - repeated construction of IDs/digests with the same inputs is equal;
   - rows are sorted;
   - no `hash()`, `uuid`, `random`, `time.time`, `datetime.now`, or wall-clock
     domain values in conflict modules.
10. Add `tests/unit/test_organized_conflict_determinism.py`:
    - run the same fixture twice with the same seed;
    - compare ledger digest, candidate IDs, lineage, snapshot digest, and metric
      values byte-for-byte.

### Required Interfaces and Contracts

The suite consumes public module constants and ASTs; it does not import private
world modules.

### Requirement Evidence

- Source: Original Request — no `world.at_war`, low-level mechanics, event-pattern
  analytics, differing interpretations.
- Source: `.ai-factory/ARCHITECTURE.md` "Anti-Patterns" and "Versioned Extension
  Contract".
- Supported combinations: every ownership, wire, snapshot, route, identity, and
  determinism claim.

### Error Handling and Logging

Tests only; no runtime logging. Failure messages name the offending file and
symbol, never a token or payload.

### Tests

- `tests/architecture/test_organized_conflict_boundaries.py`
- `tests/unit/test_organized_conflict_determinism.py`
- Command:
  `uv run pytest tests/architecture/test_organized_conflict_boundaries.py tests/unit/test_organized_conflict_determinism.py -q`

### Acceptance Criteria

- Every forbidden object and wire change is absent.
- Every ownership and prerequisite claim is asserted.
- Deterministic outputs match across repeated runs.
- No current 168 pin remains.

### Verification

- Command above.
- Expected: all pass.

## Task 23: Add the organized-conflict end-to-end scenario

### Intent

Exercise the real path: real engine ticks, real existing commands, real event
patterns, real owner interpretations, real publication, and all six routes,
without PostgreSQL.

### Implementation Steps

1. Create `tests/unit/test_organized_conflict_e2e.py`.
2. Build a fixture with two groups of three agents on a small two-location world:
   - group A: attacker, defender/helper, capturer;
   - group B: attacker, defender/helper, retreater.
3. Configure `runner-config-v56` with `diplomacy=True` and
   `organized_conflict=True`; set deterministic conflict and diplomacy modes.
4. Scenario A — individual violence:
   - one A attacker attacks one B target once;
   - assert one `Attacked` event, no `Died`;
   - analysis classifies `individual_violence`.
5. Scenario B — coordinated and persistent:
   - two A attackers attack the same B target across at least three windows;
   - B defender uses `Help`; B retreater uses `Flee`; A capturer takes a corpse
     item after a lethal attack;
   - A movement group uses `Move` to the adjacent location; one A uses `Help`;
   - assert `Attacked`, `Died`, `Fled`, `Helped`, `Taken`, and `Moved` events;
   - analysis classifies `coordinated_conflict` and
     `persistent_inter_group_conflict` for the two-side recurrent pattern.
6. Owner interpretations:
   - owner A interprets the episode as `coordinated_conflict`;
   - owner B interprets the same events as `defense`;
   - publish both; assert two interpretation rows and
     `owner_disagreement_count > 0`;
   - assert no reconciliation row and no truth/winner field.
7. Publication:
   - publish to a `tmp_path` root via the filesystem store;
   - assert `organized-conflict-snapshot-v1`, digest, row counts, and atomically
     readable bytes.
8. API:
   - build the FastAPI app with the reader and cursor key;
   - hit all six routes with `SUBJECTIVE_DEBUG`;
   - assert 200, pages, details, and cursor reuse;
   - unset the root and assert 503 `organized_conflict_disabled`;
   - request an unknown episode and plan and assert 404.
9. Non-interference and boundary assertions:
   - assert a conflict plan never blocks a physically possible command;
   - assert a physically impossible command is still rejected by existing rules;
   - assert a generic structure without a completed public-good project remains
     undamaged after a `structure_attack` plan;
   - assert a route remains usable and no blocked/closed route state exists
     after a `route_blocking` plan;
   - assert a living holder's item cannot be seized by `resource_capture`;
   - assert `defense` produces `Help`/`Attack`/`Move` with no damage mitigation;
   - assert no new event/command and the scientific result is unchanged.
10. Run twice with the same seed and compare snapshot digest.

### Required Interfaces and Contracts

The E2E uses public runner, store, and API composition only. It does not call
private analysis helpers except the public harvest/compute functions.

### Requirement Evidence

- Source: Original Request — all eight primitives, event-pattern analytics,
  individual vs persistent, differing interpretations.
- Source: `tests/unit/test_diplomacy_e2e.py` 368+ — in-process pattern.
- Supported combinations: individual; coordinated; persistent inter-group;
  defense; retreat; capture; movement; assistance; publication; routes.

### Error Handling and Logging

- Tests assert safe error codes, not payloads.
- On failure, print only counts and classifications, never ids or frame bodies.

### Tests

- `tests/unit/test_organized_conflict_e2e.py`
- Command: `uv run pytest tests/unit/test_organized_conflict_e2e.py -q`
- Expected: runs without `PALIMPSEST_TEST_DATABASE_URL` and without Docker.

### Acceptance Criteria

- The E2E runs in the focused/unit lane without PostgreSQL.
- Real existing commands produce the expected events.
- Analysis distinguishes individual, coordinated, and persistent inter-group.
- Two owner interpretations coexist.
- Publication and all six routes work.
- Generic structures remain undamaged, routes remain usable, living-holder
  seizure stays impossible, and defense grants no mitigation.
- No new event or command exists.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_e2e.py -q`
- Expected: all pass in the unit lane.

## Task 24: Execute the full V1-V4 regression and qualification lanes

### Intent

Run every required lane after the invariant and E2E gates, record exactly one
state per lane, and never convert a missing prerequisite into a skip-pass.

### Implementation Steps

1. Run the focused V4-12 suite:
   `uv run pytest tests/unit/test_organized_conflict_*.py tests/architecture/test_organized_conflict_boundaries.py -q`.
2. Run the full Python unit + architecture suite with coverage enabled:
   `uv run pytest tests/unit tests/architecture --cov=src --cov-report=term-missing`.
3. Run static gates:
   - `uv run ruff check src tests`
   - `uv run mypy src tests`
   - `uv run lint-imports`
4. Run the non-scale integration lane against a disposable
   PostgreSQL/pgvector database whose name contains `palimpsest_test`:
   `PALIMPSEST_TEST_DATABASE_URL=... uv run pytest -m "integration and not scale" -q`.
5. Run `docker compose config --quiet`.
6. Run Compose/browser acceptance only with a source-attested image and a real
   browser driver; otherwise record `unexecuted` with the missing prerequisite.
7. Run the pinned Godot 4.7.2 headless protocol suite.
8. Run the benchmark/scale lane or record `unexecuted` with the missing
   prerequisite.
9. Run Research UI lanes: `npx pnpm@10.34.9 test`, `npx pnpm@10.34.9 check`,
   `npx pnpm@10.34.9 build`.
10. Run documentation parity after Task 25; if docs are not yet updated, record
    `unexecuted` and rerun after Task 25.
11. Update the Verification Receipt in `index.md` with exactly one state and
    evidence per lane. Any failed or unexecuted required lane blocks
    certification.

### Required Interfaces and Contracts

Required lanes and their prerequisites are exactly those in the index receipt.
A lane with a missing prerequisite is `unexecuted`, never `executed_passed`.

### Requirement Evidence

- Source: Plan Settings — full strategy with coverage.
- Source: `.ai-factory/ARCHITECTURE.md` "Tests" — unit tests network-free;
  integration uses disposable `palimpsest_test` databases.
- Supported combinations: executed pass/fail; unexecuted with prerequisite.

### Error Handling and Logging

- Record bounded command output, counts, and safe reason codes only.
- Never paste prompts, payloads, tokens, DSNs, or full logs.
- A failed lane records the first safe failure code and the command.

### Tests

- The commands above.
- Expected: all executed lanes pass; unexecuted lanes carry a prerequisite.

### Acceptance Criteria

- Every required lane has exactly one state.
- No lane is a skip-pass.
- The receipt records coverage and all client/benchmark outcomes.
- Certification is withheld if any required lane is unexecuted.

### Verification

- Re-read the index receipt and confirm each lane state and evidence.
- Expected: receipt is complete and internally consistent.

## Phase Risks and Mitigations

- Risk: the E2E requires PostgreSQL or Docker.
  Mitigation: use in-process fixtures and a temp filesystem root only.
- Risk: a boundary test catches a legitimate import.
  Mitigation: keep the command screen in a dedicated actions module; keep
  analysis free of cognition/experiments imports.
- Risk: determinism fails due to wall clock or unordered sets.
  Mitigation: sorted rows, canonical JSON, injected ticks, no wall clock.
- Risk: a required lane is silently skipped.
  Mitigation: explicit `unexecuted` state with prerequisite.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
