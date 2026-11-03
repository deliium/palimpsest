# Phase 7: Invariants, End-to-End Evidence, and Regression

Plan: [index.md](index.md)
Tasks: 19-21
Depends on: Phase 6 / Task 18

## Objective

Prove the formal-rule authority claims with executable architecture, isolation,
determinism, physical-vs-social, competing-system, publication, and end-to-end
tests; then execute the full V1-V4 regression and qualification lanes and record
an honest three-state receipt.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_organization_agency_boundaries.py` | 100-134 | Magic-actor, command, route, and pin assertion pattern. |
| `tests/architecture/test_organization_operations_boundaries.py` | 262-307 | V4 ownership, reservations, route-count pattern. |
| `tests/architecture/test_v4_architecture_invariants.py` | 80-177, 207-297 | Flag allowlist, registry, reservation, validator mutation patterns. |
| `tests/unit/test_organization_agency_determinism.py` | 75-106 | Repeated/shuffled determinism pattern. |
| `tests/unit/test_organization_agency_end_to_end.py` | real command/perception/publication flow | E2E precedent. |
| `tests/unit/test_organization_agency_isolation.py` | owner-only isolation | Isolation precedent. |
| `src/world/actions.py` | `Give` 93; `Attack` 230; `Inscribe` 348 | Real commands for the E2E. |
| `src/world/artifacts.py` | `ArtifactKind.RECORD` 78; `DurableRecordGenre.AGREEMENT` 97 | Written representation anchor. |
| `src/simulation/engine.py` | `WorldEngine` admission | Physical impossibility test. |
| `docs/development.md` | verification commands | Lane commands and prerequisites. |
| `tests/compose/acceptance.py` | Compose/browser acceptance | Required-lane receipt. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_formal_rule_boundaries.py` | create | Authority, magic-actor, command, pin, route, cursor, snapshot checks. |
| `tests/unit/test_formal_rule_determinism.py` | create | Repeated/shuffled/permutation determinism. |
| `tests/unit/test_formal_rule_isolation.py` | create | Owner-only and forbidden-input isolation. |
| `tests/unit/test_formal_rule_physical_distinction.py` | create | Physical impossibility vs social prohibition. |
| `tests/unit/test_formal_rule_end_to_end.py` | create | Real run, artifact, command, publication, API, metrics. |
| `tests/unit/test_formal_rule_regression.py` | create | Exact pins and no-v57/no-new-write-pair. |
| Existing architecture/unit pin files | modify | 151 families, two owned flags, twelve aggregate routes, six formal-rule routes. |

## Task 19: Add the formal-rule boundary and determinism suite

### Intent

Make every forbidden shortcut a failing test: objective law, world enforcement,
global registry, command construction, peer-ledger reads, cross-context identity,
and nondeterminism.

### Implementation Steps

1. Create `tests/architecture/test_formal_rule_boundaries.py` with:
   - `test_formal_rule_modules_import_no_world_engine_state_or_commands`:
     AST scan of `src/agents/cognition/formal_rule*.py`,
     `src/analysis/formal_rule*.py`, `src/simulation/formal_rule*.py`,
     `src/experiments/formal_rule*.py`, `src/persistence/formal_rule*.py`,
     `src/api/routes/formal_rule.py`, `src/api/formal_rule_*.py`,
     `src/api/app.py`, `src/api/dependencies.py`,
     `src/infrastructure/settings.py`, and
     `src/research_runner/formal_rule_composition.py` for imports of
     `world._state`, `WorldState`, `WorldEvent`, `PhysicalRules`,
     `AgentCommand`, `ActionSubmission`, `simulation.engine`, and
     `simulation.actions`.
   - `test_no_world_law_magic_actor_classes_exist`: scan source class names and
     module names for `Law`, `Statute`, `LegalCode`, `Court`, `Judge`, `Police`,
     `Government`, `Jurisdiction`, `RuleEngine`, `SanctionEngine`,
     `PolicyEngine`, `GlobalRuleRegistry`, `WorldRule`; allow only historical
     V3-31/V3-32 vocabulary in its existing files and the forbidden-field
     denylist in `formal_rules.py`.
   - `test_world_engine_perception_and_admission_do_not_reference_formal_rules`:
     scan `src/world/_rules.py`, `src/world/_operations.py`,
     `src/world/_perception.py`, `src/simulation/engine.py`,
     `src/simulation/actions.py`, `src/simulation/perception.py`, and stop
     selectors for `formal_rule` identifiers.
   - `test_no_command_construction_or_dispatch`: assert no formal-rule function
     returns or constructs a command class; AST scan for `Give(`, `Attack(`,
     `Inscribe(`, `AgentCommand(`, `ActionSubmission(` in formal-rule modules.
   - `test_no_objective_ownership_or_jurisdiction_fields`: scan models/records
     for `owner_id` on world artifacts, `jurisdiction`, `enforced_by_world`,
     `law_id`, `binding`, `objective_rule`, `law`.
   - `test_no_global_rule_registry_or_cross_owner_store`: assert analysis
     candidates are detached and no module exposes a process-global mutable
     registry.
   - `test_six_get_only_formal_rule_routes`: enumerate routes with the
     `/formal-rules` prefix, assert 6, all GET.
   - `test_six_organization_routes_are_unchanged`: enumerate the organization
     prefix, assert 6, all GET.
   - `test_six_formal_rule_cursor_purposes`: assert the closed tuple.
   - `test_snapshot_schema_and_store_schema_are_v1`.
   - `test_compatibility_pins_are_exact`: default v4/result v2; latest feature
     v55; v56 only; no v57; events 22; codec v20; commands 43; observer
     semantics 73; metric families 151; Alembic 0017; `/v1`;
     `observer-protocol-v1`; `observer-layout-v1`; `prepare_parallel=False`.
   - `test_v4_registry_has_fourteen_contexts_twelve_flags_two_owned`.
   - `test_reserved_write_pairs_are_unchanged`.
   - `test_formal_rules_reuses_existing_events_and_has_no_reservation`.
   - `test_organization_snapshots_remain_v1_v2_v3`.
   - `test_no_new_event_command_observer_semantic_or_migration`
   - `test_settings_never_imports_or_reads_a_formal_rule_ledger`
   - `test_app_wiring_imports_only_api_and_persistence`.
2. Create `tests/unit/test_formal_rule_determinism.py`:
   - `test_repeated_updates_are_byte_identical`
   - `test_shuffled_communications_produce_the_same_ledger`
   - `test_shuffled_evidence_produces_the_same_digest`
   - `test_candidate_identity_is_reproducible`
   - `test_no_hash_uuid_or_wall_clock_in_formal_rule_domain`
   - `test_metric_documents_are_permutation_invariant`
3. Create `tests/unit/test_formal_rule_isolation.py`:
   - `test_update_rejects_world_state_world_event_physical_rules_and_metrics`
   - `test_update_rejects_foreign_owner_prior_ledger`
   - `test_snapshot_checkpoint_and_result_reject_foreign_owner`
   - `test_owner_a_cannot_read_owner_b_ledger`
   - `test_analysis_never_reads_live_cognition`
   - `test_formal_rule_candidate_never_changes_organization_identity`
4. Create `tests/unit/test_formal_rule_physical_distinction.py`:
   - `test_socially_prohibited_but_physically_possible_command_is_admitted`:
     owner has a prohibition belief for `Give`; a real `Give` with a held item is
     admitted and works.
   - `test_physically_impossible_command_is_rejected_without_rule_attribution`:
     `Give` without the item or at an invalid target is rejected by existing
     rules; no formal-rule code appears in the error.
   - `test_rule_does_not_change_admission_or_action_rules`
   - `test_response_selection_never_suppresses_a_command`
   - `test_no_physical_constraint_member_exists`
5. Create `tests/unit/test_formal_rule_regression.py`:
   - `test_exact_pins`
   - `test_no_v57_runner_schema_exists`
   - `test_no_new_write_pair_reservation`
   - `test_catalog_is_151_with_three_formal_rule_families_last`
   - `test_formal_rules_flag_is_owned_and_ten_flags_remain_unowned`
   - `test_six_formal_rule_routes_and_six_organization_routes`
   - `test_formal_rule_snapshot_v1_and_store_v1`
6. Update existing pins:
   - `tests/architecture/test_organization_boundaries.py` ownership split and
     151 metric count.
   - `tests/architecture/test_organization_operations_boundaries.py` ownership
     split and 151 count.
   - `tests/architecture/test_organization_agency_boundaries.py` 151 count and
     aggregate route assertions.
   - `tests/architecture/test_v4_architecture_invariants.py` two owned flags and
     151 count.
   - `tests/architecture/test_path_dependence_boundaries.py` 151 count.
   - `tests/unit/test_organization_docs.py` / `test_organization_operations_docs.py`
     count assertions.
   - Any other `148` metric-catalog assertion found by
     `grep -rn "148" tests/unit tests/architecture`.
7. Do not weaken any existing assertion or skip a test to make the new surface
   pass.

### Required Interfaces and Contracts

- Boundary failures are hard failures, never warnings.
- A test may allowlist an existing historical mention only with an exact path
  and symbol; blanket path allowlists are forbidden.
- Pin tests assert exact values, not `>=` or membership-only.
- The physical-distinction test uses a real `WorldEngine` path, not a fake
  admission.

### Requirement Evidence

- Original Request "WorldEngine must NOT enforce social rules as physical laws"
  and "Distinguish physical impossibility from social prohibition".
- `.ai-factory/ARCHITECTURE.md` "Anti-Patterns" and "Key Principles".
- `.ai-factory/RULES.md` axioms 1, 3, 4, 5.
- `tests/architecture/test_organization_agency_boundaries.py` 100-134.
- `tests/architecture/test_v4_architecture_invariants.py` 80-177, 207-297.

### Error Handling and Logging

- Tests fail with the offending path/symbol and the violated rule.
- No test writes repository files, starts a server, or requires Docker.
- Unit/architecture tests remain network-free and PostgreSQL-free.

### Tests

- `uv run pytest tests/architecture/test_formal_rule_boundaries.py tests/unit/test_formal_rule_determinism.py tests/unit/test_formal_rule_isolation.py tests/unit/test_formal_rule_physical_distinction.py tests/unit/test_formal_rule_regression.py -q`

### Acceptance Criteria

- Every authority claim has an executable test.
- Physical impossibility and social prohibition are demonstrably separate.
- No forbidden class, field, import, command, or registry exists.
- All pins are exact.

### Verification

- `uv run pytest tests/architecture/test_formal_rule_boundaries.py -q`
- `uv run pytest tests/unit/test_formal_rule_determinism.py tests/unit/test_formal_rule_isolation.py tests/unit/test_formal_rule_physical_distinction.py -q`

## Task 20: Add the formal-rule end-to-end scenario

### Intent

Exercise the real path: a completed run with the flag enabled, a norm-derived
rule promoted by a real durable record and real claims, a real command that the
rule prohibits, publication, API read, and metric assembly.

### Implementation Steps

1. Create `tests/unit/test_formal_rule_end_to_end.py`.
2. Build a deterministic world with at least four agents and enough items/locations
   for `Give` and `Inscribe`. Reuse existing scenario builders for a minimal
   world; do not hand-roll `WorldState`.
3. Configure `runner-config-v56` by constructing `SimulationRunnerConfig`
   directly. Do **not** use `experiments.catalog.v4_scaffolding_profile`, which
   rejects every enabled V4 flag (1693-1718). Set:
   - `v4_capability_flags.formal_rules=True` and `organizations=False` for the
     primary scenario;
   - a second configuration with both `formal_rules=True` and
     `organizations=True` to prove the two owned flags coexist;
   - `DurableRecordsSpec` enabled (for the written record);
   - deterministic social norm mode (for the norm evidence);
   - all other V4 flags off.
4. Drive the run:
   - owner A observes repeated reciprocal `Give` behavior to form an active norm
     (reuse the existing norm test helper pattern);
   - owner A executes a real `Inscribe(ArtifactKind.RECORD,
     ArtifactContent(...), record_genre=DurableRecordGenre.AGREEMENT)` through
     `WorldEngine`; A perceives the artifact and reaches stage `documented`;
   - A communicates an `fr_assert` claim to B and C; over at least two
     consecutive ticks B and C deliver `fr_support`/`fr_recognize` claims so the
     recurrence and supporter thresholds are met; A's update reaches
     `recognized_enforcement`;
   - B asserts an opposite `permission` on the same scope/action; A and B hold
     competing systems with symmetric links and `contested` status;
   - A selects `follow`; B selects `violate`; assert both are response records and
     no command was created by the selector.
5. Physical/social assertion:
   - with A's prohibition active, B executes a real `Give` to A using a held item;
     admission succeeds and the item custody changes;
   - B executes a `Give` without the item; the existing admission rejects it and
     no formal-rule code appears.
6. Complete the run and compose:
   - call `build_completed_run_formal_rule_harvest` and
     `build_formal_rule_harvest_result`;
   - assert one `formal-rule-snapshot-v1`, canonical round-trip, stable digest,
     and two competing candidates remain distinct;
   - publish to a temporary root via `FilesystemFormalRulePublisher`;
   - read through `FilesystemFormalRuleReader` and assert summary/candidates/
     rules/versions/lineage pages;
   - call the six API routes with `SUBJECTIVE_DEBUG` credentials and assert the
     published fields (or call the route functions with a test client matching
     existing API test patterns).
7. Metric assembly:
   - pass `runner_result` through `assemble_arm_metric_bundle` (or the existing
     completed-run collector helper);
   - assert the three new metric documents are present and the first 148 are
     unchanged.
8. Failure isolation:
   - inject a publisher that raises `FormalRuleArtifactError`;
   - assert the receipt is `failed` with the safe code and the runner result and
     scientific document are byte-identical to the pre-publication values.
9. Determinism:
   - run the scenario twice with the same seed and assert identical ledger
     digests, snapshot digest, publication id, metric documents, and API pages.
10. Test names:
    - `test_formal_rule_progression_reaches_recognized_enforcement`
    - `test_formal_rules_and_organizations_flags_coexist_on_v56`
    - `test_competing_systems_survive_publication_and_read`
    - `test_declared_responses_do_not_create_commands`
    - `test_prohibited_but_possible_command_is_admitted`
    - `test_physically_impossible_command_is_rejected_independently`
    - `test_snapshot_publication_and_six_route_read`
    - `test_metric_assembly_emits_all_three_documents`
    - `test_publication_failure_changes_only_the_receipt`
    - `test_repeated_scenario_is_byte_identical`

### Required Interfaces and Contracts

- The E2E uses the real `WorldEngine`, real perception, real `Give`/`Inscribe`,
  real update, real codec, real filesystem store, real API route functions, and
  real metric assembly.
- No monkeypatched admission, no synthetic command, no fake perception.
- The rule never appears in admission errors.
- Competing candidates remain separate across publication and read.
- Publication failure does not alter the scientific result.

### Requirement Evidence

- Original Request all dimensions.
- `tests/unit/test_organization_agency_end_to_end.py` (real command/perception
  flow).
- `src/world/actions.py` 93, 230, 348.
- `src/world/artifacts.py` 78-110.
- `docs/development.md` verification commands.

### Error Handling and Logging

- The test asserts safe error codes only; never asserts raw messages containing
  payloads.
- A publication failure is asserted through the receipt, not by catching a broad
  exception in production code.
- No test logs rule content, artifact content, or owner ids.

### Tests

- `uv run pytest tests/unit/test_formal_rule_end_to_end.py -q`

### Acceptance Criteria

- The full pipeline works end to end with real domain and storage components.
- Physical and social constraints remain distinct in behavior.
- Two competing systems survive publication and read.
- The three metric documents are emitted.
- Publication failure is isolated.

### Verification

- `uv run pytest tests/unit/test_formal_rule_end_to_end.py -q`
- `uv run pytest tests/unit/test_formal_rule_end_to_end.py -q -k "repeated or publication_failure"`
- Expected: identical digests across repeats; receipt-only failure.

## Task 21: Execute the full V1-V4 regression and qualification lanes

### Intent

Run every required lane and record an honest three-state receipt. A missing
prerequisite or exceeded wall clock is `unexecuted` with a prerequisite; it is
never a skip-pass.

### Implementation Steps

1. Run and record:
   - `uv run pytest tests/unit tests/architecture --cov` with coverage enabled;
   - the focused V4-06 suite:
     `uv run pytest tests/unit/test_formal_rule_*.py tests/architecture/test_formal_rule_boundaries.py -q`;
   - `uv run ruff check src tests`;
   - `uv run mypy src tests`;
   - `uv run lint-imports`;
   - `uv run pytest -m "integration and not scale"` against a disposable
     `palimpsest_test` pgvector database;
   - `uv run pytest -m integration` including scale selection if the wall clock
     permits;
   - `docker compose config --quiet`;
   - Compose/browser acceptance with a built `PALIMPSEST_API_IMAGE` and a real
     browser driver;
   - the pinned Godot 4.7.2 regression suite;
   - the benchmark/scale lane with a disposable pgvector instance;
   - Research UI `npm run test -- --run`, `npx svelte-check`, `npx tsc --noEmit`,
     and `npm run build`.
2. Record each lane as exactly one of:
   - `executed_passed` with counts/duration;
   - `executed_failed` with the failing test/command;
   - `unexecuted` with the missing prerequisite or wall-clock reason.
3. Do not convert an unexecuted lane to a pass. Do not mark the plan complete
   while a required lane is unexecuted; instead record the blocker in the
   receipt and in Task 23.
4. Save the receipt in `index.md` under `## Verification Receipt` with the
   command, state, evidence, and prerequisite for each row.
5. Include the known institutional-memory order-dependent flake note only if it
   reproduces; otherwise record the green result.

### Required Interfaces and Contracts

- Coverage is enabled for Python lanes.
- Integration targets only a disposable database named with `palimpsest_test`.
- Compose/browser, Godot, and benchmark lanes are `unexecuted` when their
  prerequisites are absent.
- The receipt is part of the plan artifact, not a separate report task.

### Requirement Evidence

- Plan Settings "Testing: yes; full strategy".
- `docs/development.md`.
- `tests/compose/acceptance.py`.

### Error Handling and Logging

- Summarize failures with the failing command and bounded output, not full logs.
- Never paste credentials, DSNs, prompts, or payloads into the receipt.
- Record environment prerequisites by name only.

### Tests

This task runs the suites; it does not add a new test file.

### Acceptance Criteria

- Every required lane has a state and evidence.
- No lane is reported as passed without execution.
- Failures are reported exactly, not hidden.

### Verification

- `uv run pytest tests/unit tests/architecture --cov`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run lint-imports`
- `uv run pytest -m "integration and not scale"`
- `docker compose config --quiet`
- `cd clients/research-ui && npm run test -- --run && npx svelte-check && npx tsc --noEmit && npm run build`

Expected: all executable lanes pass; unexecuted lanes carry a prerequisite.

## Phase Risks and Mitigations

- Risk: the E2E passes by monkeypatching admission.
  Mitigation: use real `WorldEngine`/perception/commands and assert custody
  changes and existing rejection codes.
- Risk: the boundary suite allowlists too much and stops catching regressions.
  Mitigation: exact path/symbol allowlists and mutation tests for each guard.
- Risk: a full-suite run is too slow or flaky.
  Mitigation: record the lane honestly with its duration/flake, rerun focused
  failures, and never report a skip as a pass.
- Risk: 148 → 151 updates leave one stale assertion.
  Mitigation: run the grep in Task 12 and the full unit lane here.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
- The verification receipt uses only `executed_passed`, `executed_failed`, or
  `unexecuted`.
- No required lane is silently omitted.
