# Phase 7: Invariants and Regression

Plan: [index.md](index.md)
Tasks: 19-20
Depends on: Phase 6 / Task 18

## Objective

Prove the authority, determinism, compatibility, and read-only claims with an
architecture/boundary suite, then execute the full V1-V4 regression,
integration, Compose/browser, Godot, Research UI, benchmark, and static gates.
A required lane that cannot execute is recorded as unexecuted, never as a pass.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_macro_society_boundaries.py` | analysis/simulation/persistence/API isolation, magic actors, GET-only, pins | Exact boundary-suite pattern to extend. |
| `tests/architecture/test_v4_architecture_invariants.py` | pins 120-130; flag allowlist 203-209; magic actors 212-219; V4 authority 222-234 | Must include the new organization modules and ownership. |
| `tests/architecture/test_v4_context_registry.py` | 99-177 | Registry remains 14/12. |
| `tests/unit/test_macro_society_determinism.py` | Hypothesis/permutation determinism | Pattern for organization determinism. |
| `tests/unit/test_v1_regression_gate.py`, `tests/unit/test_v2_scientific_invariants.py` | flags-off gate | Must stay green. |
| `docs/development.md` | test/lint/type/client/Godot/Compose commands | Exact verification commands. |
| `tests/compose/acceptance.py` | three-state receipt | Required-lane reporting. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_organization_boundaries.py` | create | Authority, imports, magic actors, pins, read-only, no peer reads, schema independence. |
| `tests/unit/test_organization_determinism.py` | create | Permutation, `PYTHONHASHSEED`, idempotence, Hypothesis lineage acyclicity. |
| `tests/unit/test_organization_end_to_end.py` | modify | Add flag-on run -> harvest -> publish -> API read. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Include organization modules in the flag allowlist/actor scan; assert ownership and pins. |
| `tests/architecture/test_v4_context_registry.py` | modify | Only if ownership changes an assertion; registry count/order stays 14/12. |
| `tests/unit/test_v3_baseline_inventory.py` and other 140 pins | modify | Metric count 144. |

## Task 19: Add the organization boundary and determinism suite

### Intent

Make every authority and compatibility claim executable. The suite must fail if a
later change turns an organization into an actor, a registry, a peer-state
reader, a command source, a migration, or a non-deterministic identity.

### Implementation Steps

1. Create `tests/architecture/test_organization_boundaries.py` with these
   assertions:
   - **Analysis isolation:** `src/analysis/organization_*.py` and
     `src/analysis/organizations.py` import no `agents.cognition`,
     `experiments`, `api`, `persistence`, `infrastructure`, or `observer`.
   - **Simulation isolation:** `src/simulation/organization_*.py` import no
     `analysis`, `experiments`, `api`, `persistence`, `infrastructure`, or
     `observer`.
   - **Persistence isolation:** `src/persistence/organization_filesystem.py`
     imports no `analysis`, `experiments`, `api`, `observer`, or
     `agents.cognition`.
   - **API isolation:** `src/api/routes/organization.py`,
     `organization_schemas.py`, and `organization_cursor.py` import no
     `analysis`, `experiments`, or `agents.cognition`.
   - **Runner isolation:** `src/research_runner/organization_composition.py`
     imports no `api`.
   - **No magic actors:** the tokens `OrganizationActor`,
     `GlobalOrganizationRegistry`, `OrganizationRegistry`, `WorldGovernment`,
     `CentralBank`, `Treasury`, `Ministry`, `InstitutionActor`,
     `CivilizationActor`, `Country`, `Nation`, `Empire`, `Polity`, and `Tribe`
     do not appear as `class` definitions anywhere in `src/`.
   - **No organization commands:** no organization module contains
     `AgentCommand`, `class *Command`, or a `COMMAND_RULE_MATRIX` entry.
   - **No world authority:** `src/agents/cognition/organization_*.py` and
     `src/analysis/organization_*.py` contain no `WorldState`, `WorldEngine`,
     `ActionSubmission`, `TickToken`, `EventStore`, or
     `PhysicalRules` reference.
   - **No peer reads:** the organization update accepts only
     `owner_id`, `observation`, `prior`, and prepared owner ledgers; AST checks
     reject parameters/attributes named `peer`, `other_owner`, `all_ledgers`,
     `runtimes`, or `world_state`.
   - **No objective feedback:** `src/world/`, `src/simulation/perception.py`,
     `src/simulation/runner_models.py` stop selectors, and
     `src/simulation/agent_runtime.py` admission paths contain no
     `organization_concept` read except the runtime's own ledger carry/commit.
   - **No flag literal outside allowlist:** `"v4_capability_flags"` appears only
     in the existing `ALLOWED_FLAG_REFERENCES`; add new modules to the allowlist
     only if they must reference it.
   - **Pins:** `EVENT_SCHEMA_REPLAY_V22 == 22`, max accepted event 22,
     `"v20"` accepted and `"v21"` not accepted, `len(COMMAND_RULE_MATRIX) == 43`,
     observer semantic types `73`, `METRIC_FAMILY_COUNT == 144`,
     `BENCHMARK_SCENARIO_COUNT == 16`, `V3_BENCHMARK_SCENARIO_COUNT == 30`,
     Alembic head `0017`, no `0018_*.py`, `next_revision() == "0018"`,
     `RUNNER_SCHEMA_VERSION == "runner-config-v4"`,
     `RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"`,
     `RUNNER_SCHEMA_VERSION_V56` accepted, `"runner-config-v57"` absent.
   - **V4 registry:** 14 contexts, 12 flags, `v4-context-map-v2`, analysis-only
     set unchanged, four reservations unchanged, `organizations` owned and the
     other eleven unowned.
   - **Observer:** `SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)`,
     four advertised and six reserved capabilities, `/version` payload keys
     unchanged, `organization_rows` still reserved.
   - **Read-only:** every route in `src/api/routes/organization.py` uses
     `@router.get`; the Research UI organization client contains no
     POST/PUT/PATCH/DELETE.
   - **Schema independence:** `simulation/organization_models.py` and
     `organization_codec.py` import no analysis type; the snapshot contains no
     `orgc-` candidate identity.
   - **No new persistence contract:** no SQLAlchemy/Alembic import in the
     organization filesystem store; no migration file exists.
2. Create `tests/unit/test_organization_determinism.py`:
   - same input with permuted member/anchor/owner row order produces identical
     canonical ledgers, analyses, snapshots, digests, and publication ids;
   - `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1` subprocess runs produce identical
     digests;
   - repeated publication of identical bytes is idempotent;
   - Hypothesis property: generated acyclic lineage transitions validate;
     inserting a backward edge raises `organization_lineage_cycle`;
   - Hypothesis property: layer projection never leaks an `org-` id into an
     objective or subjective row.
3. Extend `tests/unit/test_organization_end_to_end.py` with a flag-on fixture:
   - build a v56 config with `organizations=True` and at least one evidence mode;
   - run a short deterministic scenario with explicit claims and a collective
     project;
   - export `RunnerResult`, build the harvest, publish to a temporary root, read
     through the API reader, and assert summary/candidate/lineage match;
   - assert the scientific result and exit status are unchanged when the
     publication root is unwritable.
4. Extend `tests/architecture/test_v4_architecture_invariants.py`:
   - ownership split for `organizations`;
   - add `organization_*` to the flag-reference allowlist only if needed;
   - include the new magic-actor tokens in the scan;
   - assert metric 144 and the unchanged pins.
5. Run the suite; fix every failure before Task 20.

### Required Interfaces and Contracts

- The suite is read-only and uses static AST/regex checks plus public APIs.
- No test may create a database, network call, or real browser.
- Determinism subprocesses use the repository's `uv run` interpreter and a
  temporary directory under `/tmp/opencode`.
- Required-lane receipts use `executed_passed`, `executed_failed`, or
  `unexecuted` with a prerequisite string.

### Requirement Evidence

- Original request: "An Organization must not receive an independent omniscient
  cognition engine"; "All organization activity ultimately occurs through
  agents, records, roles and recognized procedures."
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-4; "Dependency Rules";
  "Anti-Patterns".
- `.ai-factory/RULES.md` axioms 1, 3, 5, 6.

### Error Handling and Logging

- Test failures report the file, symbol, and reason code only.
- No production logging change.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_organization_boundaries.py tests/unit/test_organization_determinism.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_v4_context_registry.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_end_to_end.py -q`
- Expected: pass.

### Acceptance Criteria

- Every authority, determinism, pin, and read-only claim has an executable
  assertion.
- The suite fails on a magic actor, peer read, command, event, migration, or
  non-deterministic identity.
- End-to-end publication works through the public ports.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_organization_boundaries.py -q`
- Expected: pass.

## Task 20: Execute the full V1-V4 regression and qualification lanes

### Intent

Certify the feature against the project's complete gate set. No required lane is
silently skipped; a missing prerequisite is reported as unexecuted with the
blocker.

### Implementation Steps

1. Run the Python unit and architecture suites with coverage:
   `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term`.
2. Run the V1/V2/V3/V4 focused gates from `docs/development.md`, including:
   - `tests/unit/test_v1_regression_gate.py`
   - `tests/unit/test_v2_scientific_invariants.py`
   - `tests/unit/test_runner_config_v4_flags.py`
   - `tests/unit/test_runner_config_v56.py`
   - `tests/unit/test_v4_scaffolding_gate.py`
   - `tests/unit/test_v4_versioning_reservations.py`
   - `tests/unit/test_v4_migration_plan.py`
   - `tests/unit/test_v4_scale_contracts.py`
   - `tests/architecture/test_v4_architecture_invariants.py`
   - `tests/architecture/test_v4_context_registry.py`
   - the new organization suites.
3. Run integration lanes with a disposable `palimpsest_test` database:
   `PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m integration`.
   The database gate fails closed when the URL is missing; record the blocker if
   no disposable instance is available.
4. Run Compose checks and the browser/acceptance lanes:
   - `docker compose config --quiet`
   - `uv run --frozen --python 3.12.14 pytest -m compose`
   - the Research UI wiring/smoke tests and the Playwright browser lane when
     Docker and a real browser driver are available;
   - if the browser lane exercises organization routes, pass a test-owned
     `PALIMPSEST_ORGANIZATION_ROOT` and `PALIMPSEST_ORGANIZATION_CURSOR_KEY`
     (with a published fixture) and assert summary/candidates/lineage; if it
     does not, assert `organization_disabled` explicitly and record that the
     enabled path was covered only by the Python/API lane.
5. Run the pinned Godot protocol suite:
   `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`.
   If `GODOT_BIN` is unavailable, record `unexecuted` with
   `prerequisite="godot-4.7.2"`.
6. Run the Research UI gates:
   `cd clients/research-ui && pnpm test && pnpm check && pnpm build`.
7. Run the benchmark regression lane required by the plan settings, including
   the V4 scale contract and the organization-specific end-to-end fixture. Do
   not claim capacity or prevalence.
8. Run static gates:
   - `uv run --frozen --python 3.12.14 ruff check src tests`
   - `uv run --frozen --python 3.12.14 mypy src tests`
   - import-linter via the project's configured command.
9. Produce a certification receipt in the run log with one line per lane:
   `lane=<name> state=executed_passed|executed_failed|unexecuted
   prerequisite=<...> command=<...>`.
   A failed or unexecuted required lane blocks certification.
10. Do not fix unrelated failures silently. If an unrelated baseline failure
    exists, record it separately and keep the V4-03 lanes scoped.

### Required Interfaces and Contracts

- Required lanes from the plan settings: unit, architecture, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, static.
- A skipped database/Godot/browser lane is `unexecuted`, never `executed_passed`.
- Coverage stays enabled for Python lanes.
- No lane changes production code.

### Requirement Evidence

- Plan Settings: "Testing: yes; full strategy".
- `.ai-factory/ARCHITECTURE.md` "Code Organization Note": coverage enabled;
  integration tests use disposable `palimpsest_test` databases.
- `docs/development.md`: exact commands and pinned toolchains.

### Error Handling and Logging

- Capture redacted command output; never include DSNs, tokens, prompts, or
  payloads.
- Report failure codes and the first failing test id, not full logs.

### Tests

- All commands in the steps above.
- Expected: every required lane is `executed_passed`, or the plan is not
  certifiable and the blocker is recorded.

### Acceptance Criteria

- The full V1-V4 regression and qualification lanes execute and pass.
- Every required lane has a three-state receipt.
- No pin is weakened; no unrelated baseline is hidden.

### Verification

- `uv run --frozen --python 3.12.14 pytest -q`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- Expected: pass; the certification receipt lists every required lane.

## Phase Risks and Mitigations

- Risk: a required lane is skipped and reported as green.
  Mitigation: three-state receipt; unexecuted blocks certification.
- Risk: the Godot lane is unavailable.
  Mitigation: record `unexecuted` with `prerequisite="godot-4.7.2"`; do not claim
  a Godot pass.
- Risk: an unrelated baseline failure obscures V4-03.
  Mitigation: record it separately; keep the feature lanes scoped.
- Risk: determinism tests depend on process hash randomization.
  Mitigation: explicit `PYTHONHASHSEED` subprocesses and canonical JSON.

## Phase Completion Checklist

- Every Task 19-20 acceptance criterion is met.
- The boundary/determinism suite passes.
- Every required lane has a receipt; no skip-pass exists.
- `index.md` checkboxes are updated immediately after verified completion.
