# Phase 7: Invariants and Pins

Plan: [index.md](index.md)
Tasks: 19
Depends on: Phases 1-6 / Tasks 1-18

## Objective

Prove V4-18 is a deepening, not a new capability: no new flag/context/write
pair, no new command/event/semantic type, no migration, exact metric append, and
no authority leakage into analysis or clients.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_v4_architecture_invariants.py` | wire pins 124-137; observer pins 140-144; Alembic 147-151; commands 154-159; contexts 162-191; no-v57 194-220; reservations 223-230; flag allowlist 253-259 | Primary invariant gate. |
| `tests/architecture/test_v4_context_registry.py` | exact context order/count 99-120; prerequisites 48-65 | Registry invariants. |
| `tests/architecture/boundary_checker.py` | imports 54-81; allowlists 325-329/650-684 | Import boundary checker. |
| `pyproject.toml` | import-linter contracts 212-393 | Package dependency contracts. |
| `tests/architecture/test_infrastructure_boundaries.py` | pins 74-75; route/auth shape | Prior deepening boundary pattern. |
| `tests/architecture/test_travel_network_boundaries.py` | private module allowlist 39-46 | Prior deepening private-module pattern. |
| `tests/unit/test_inter_society_relations_catalog.py` | count/append pins 59-90 | Catalog assertion pattern. |
| `tests/unit/test_migration_displacement_catalog.py` | count/append pins 51-81 | Catalog assertion pattern. |
| `tests/architecture/test_v3_baseline_inventory.py` | baseline 63; test 96-102 | Baseline count inventory. |
| `tests/unit/test_alembic_head_pin.py` | head 0017 | Migration pin. |
| `tests/unit/test_observer_contracts.py` | semantic count 47-55 | Observer pin. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_trade_networks_boundaries.py` | create | V4-18 deepening invariants and surface checks. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Metric pin 192 -> 198; keep all other pins. |
| `tests/unit/test_inter_society_relations_catalog.py` | modify | Expected count 198; prior-slot digest remains. |
| `tests/unit/test_migration_displacement_catalog.py` | modify | Expected count 198; prior-slot digest remains. |
| `tests/unit/test_travel_network_metrics.py` | modify | Count 198 and last-six ordering. |
| `tests/unit/test_infrastructure_metrics.py` | modify | Count 198. |
| `tests/architecture/test_v3_baseline_inventory.py` | modify | Baseline/count assertions 198. |
| `tests/architecture/test_infrastructure_boundaries.py` | modify | Metric pin 198; no new write pair. |
| `tests/unit/test_alembic_head_pin.py` | verify unchanged | Head stays 0017. |

## Task 19: Enforce architecture invariants and pin sweeps

### Intent

Catch the most likely regressions: an accidental new flag, a stolen write pair,
a new command/event/semantic type, a reordered metric catalog, or an analysis
module importing world authority.

### Implementation Steps

1. Create `tests/architecture/test_trade_networks_boundaries.py`:
   - `test_pins_are_unchanged`: default runner `v4`, latest feature runner
     `v55`, accepted `v56`, `max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27`,
     `v25` accepted, `v22` absent, commands 43, observer semantics 73, Alembic
     `0017`, `/v1`, `observer-protocol-v1`.
   - `test_v4_contexts_and_flags_are_unchanged`: 14 contexts, 12 flags, exact
     six owned (`organizations`, `formal_rules`, `legal_disputes`, `diplomacy`,
     `organized_conflict`, `infrastructure_networks`), `v4-context-map-v2`.
   - `test_deepening_pairs_are_unchanged`: reservations 23-26 / `v21`-`v24`,
     deepening pairs exactly `(27, "v25")`; no 28/`v26`.
   - `test_no_v57_or_new_flag_reference`: scan `src/**/*.py` for
     `runner-config-v57` and for new `V4CapabilityFlags` fields.
   - `test_metric_catalog_is_198`: `METRIC_FAMILY_COUNT == 198` and the last six
     ids are the declared trade families.
   - `test_trade_analysis_imports_are_read_only`: AST scan of
     `src/analysis/trade_networks_*.py` rejects imports of
     `simulation.engine`, `simulation.bootstrap`, `world._*`,
     `experiments`, `api`, `persistence`, `observer`, and `agents.cognition`.
   - `test_trade_simulation_does_not_import_analysis`: AST scan of
     `src/simulation/trade_networks_*.py` rejects `analysis`.
   - `test_trade_surfaces_contain_no_forbidden_authority_fields`: scan trade
     modules, snapshot codec, API schemas, UI client, and Godot fixture for
     `price`, `money`, `currency`, `central_planner`, `route_plan`, `quota`,
     `allocation`, `score`, `ranking`.
   - `test_snapshot_network_statuses_match_analysis_lineage`: the local
     `TRADE_SNAPSHOT_NETWORK_STATUSES`, flow classes, and coverage tuples match
     the analysis enums; every lineage relation maps to a snapshot status.
   - `test_snapshot_carries_per_family_coverage_and_venue_fields`: network
     status, anchors, trade-post, cross-location, and sustained fields survive
     the codec/API schema parity check.
   - `test_trade_modules_never_reference_commands_or_world_authority`: no
     `AgentCommand`, `WorldState`, `WorldEngine`, `ActionSubmission`, or
     `COMMAND_RULE_MATRIX`.
2. Update exact count pins from 192 to 198 in the files listed above. Do not
   relax equality to a range or `>=`.
3. Keep the first-192 structural digest assertions unchanged; add a
   `test_first_192_are_unchanged` digest assertion in
   `test_trade_networks_catalog.py` if not already present.
4. Verify no new private-world module was introduced: V4-18 has no
   `world/_trade_*`; all new modules are public analysis/simulation/api/
   experiments/persistence modules.
5. Verify `tests/architecture/test_import_boundaries.py` and
   `uv run lint-imports` pass without allowlist changes. If an allowlist change
   is truly required, document the exact module and reason; V4-18 should not
   need one.
6. Keep `prepare_parallel=False`, `/v1`, and `observer-protocol-v1` unchanged.

### Required Interfaces and Contracts

- No new V4 context, flag, capability field, runner schema, or write pair.
- No new command, event detail type, observer semantic type, or alias.
- No new SQL table, column, index, or Alembic revision.
- Analysis never receives mutable world authority.
- Snapshot/store/API modules are read-only and import only public contracts.

### Error Handling and Logging

- Tests assert exact values and fail with a short path/reason, never a payload.
- No runtime logging changes.

### Tests

- `uv run pytest tests/architecture/test_trade_networks_boundaries.py -q`
- `uv run pytest tests/architecture tests/unit/test_trade_networks_catalog.py tests/unit/test_inter_society_relations_catalog.py tests/unit/test_migration_displacement_catalog.py tests/unit/test_travel_network_metrics.py -q`
- `uv run lint-imports`
- Expected result: all pass; 25+ import contracts kept, 0 broken.

### Acceptance Criteria

- The deepening posture is machine-proven.
- Counts are exact: 14 contexts, 12 flags, six owned, 43 commands, 73 semantics,
  198 metrics, replay max 27, codec `v25`, Alembic 0017.
- No trade-network module imports world authority or outer adapters.

### Verification

- `uv run pytest tests/architecture/test_trade_networks_boundaries.py -q`
- `uv run lint-imports`
- Expected result: green.

## Phase Risks and Mitigations

- Risk: several tests duplicate the 192 pin.
  Mitigation: update every exact equality found by `rg "192"` under `tests/` and
  `docs/`; Task 20 covers docs.
- Risk: an import allowlist could be silently widened.
  Mitigation: assert no diff in `pyproject.toml` protected/allowed lists and run
  import-linter.
- Risk: metric append could reorder a prior family.
  Mitigation: first-192 digest pin plus last-six order test.

## Phase Completion Checklist

- Task 19 acceptance criteria are satisfied.
- Required verification commands pass.
- `index.md` task checkbox is updated immediately after verified completion.
