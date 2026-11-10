# Phase 7: Invariants and Pins

Plan: [index.md](index.md)
Tasks: 22
Depends on: Tasks 1-21

## Objective

Make the capability's boundaries executable: owned-flag counts, context and flag
totals, command/semantic/replay/migration pins, catalog count, edge-kind and
route pins, and import boundaries. The suite-wide numeric sweep already ran in
Task 12; this task adds the V4-19-specific invariants and verifies the pins.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `tests/architecture/test_v4_architecture_invariants.py` | ownership 162-191; 14/12/six-owned 194-213; 369-395 | Invariant pattern and hard-coded owned set |
| `src/simulation/v4_architecture.py` | `_REQUIRED_CONTEXT_COUNT = 14` 56; registry 109+; flags 330-332 | Context/flag totals |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 155-164 | Owned set |
| `src/simulation/runner_models.py` | `_V4_OWNED_CAPABILITY_FLAGS` 327 | Private owned copy |
| `src/world/actions.py` | union 911-955; `_COMMAND_TYPES` 957-1003 | 43-command pin |
| `tests/architecture/test_v3_developmental_learning_invariants.py` | 85 | Command-count assertion precedent |
| `src/observer/version.py` | 11-167 | 73-semantic-type pin |
| `src/simulation/versioning.py` | 40-53; 90-100 | Replay/codec maxima and the infra pair's prerequisite flags |
| `src/analysis/specifications.py` | 52-53; 9414-9422 | Catalog count pin |
| `src/api/routes/supply_chains.py` | `SUPPLY_CHAIN_ROUTE_COUNT = 7` | Route pin |
| `src/world/production.py` | `example_production_catalog()` 471-528 | Legacy catalog pin |
| `pyproject.toml` | import-linter contracts 193-210/212+; ids 279-614 | Static boundary gate |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Owned set seven; add V4-19 invariant |
| `tests/architecture/test_supply_chain_invariants.py` | create | Pins for commands, semantics, replay, migration, catalog, routes, edge kinds |
| `tests/architecture/test_supply_chain_boundaries.py` | modify | Include all new modules in allowlists/denylists |
| `pyproject.toml` | modify only if a contract needs the new module | Prefer no change |

## Task 22: Enforce architecture invariants and pin sweeps

### Intent

Freeze the ownership and compatibility contract before documentation, so the
docs and verification phases describe a repository that is already guarded.

### Implementation Steps

1. `tests/architecture/test_v4_architecture_invariants.py`: extend the
   hard-coded owned set in 162-191, 194-213, and 369-395 with
   `"supply_chains"`; assert 14 contexts, 12 flags, and
   `V4_OWNED_CAPABILITY_FLAGS == {"organizations", "formal_rules",
   "legal_disputes", "diplomacy", "organized_conflict",
   "infrastructure_networks", "supply_chains"}`.
2. Create `tests/architecture/test_supply_chain_invariants.py`:
   - `test_v4_19_owns_supply_chains`: seven owned / five unowned, 14/12, present
     in both owned sets;
   - `test_supply_chains_refuses_new_write_pair`: the registry entry has
     `uses_existing_events is True`, `authority is OBJECTIVE_WORLD`, owners
     `("world","simulation")`, non-goals exactly
     `("no central planner or quota", "no automatic allocation of items")`; the
     infrastructure pair (23/`v21`) keeps
     `prerequisite_flags=("infrastructure_networks", "supply_chains")` and
     supply_chains activates no pair by itself;
   - `test_no_new_command`: `len(_COMMAND_TYPES) == 43`;
   - `test_no_new_observer_semantic`: count is 73 and no `supply` semantic
     exists;
   - `test_replay_and_codec_maxima_unchanged`:
     `EVENT_SCHEMA_REPLAY_V27`/`v25` remain maxima; no `V28`/`v26`;
   - `test_alembic_head_is_0017` and the newest file is `0017_*`;
   - `test_metric_catalog_is_204`;
   - `test_seven_routes`: count 7 and every path GET-only;
   - `test_ten_edge_kinds`: the closed `SupplyEdgeKind` set has exactly ten
     members;
   - `test_legacy_production_catalog_unchanged`: `recipe_count == 6` and the
     digest matches the six locked ids;
   - `test_no_forbidden_authority`: AST scan rejects `WorldState`,
     `WorldEngine`, `ActionSubmission`, `ProductionCatalog` in
     `src/analysis/supply_chain_*` and `src/simulation/supply_chain_*`, and
     rejects `price|cost|score|rank|severity|recommendation|quota|allocation|optimizer`
     keys in analysis/snapshot/client types.
3. `tests/architecture/test_supply_chain_boundaries.py`: add every new module
   (`world/supply_chain.py`, `analysis/supply_chain_*`,
   `simulation/supply_chain_*`, `persistence/supply_chain_filesystem.py`,
   `api/routes/supply_chains.py`, `experiments/supply_chain_*`,
   `research_runner/supply_chain_composition.py`) to the allowlists/denylists so
   the denylist still fails on injection.
4. If `uv run lint-imports` reports a module outside a contract, extend the
   narrowest existing contract; do not add a permissive contract.

### Required Interfaces and Contracts

- Owned V4 flags 7; contexts 14; flags 12; unowned 5.
- Commands 43; observer semantics 73; families 204; Alembic `0017`; replay max
  `EVENT_SCHEMA_REPLAY_V27`; codec max `v25`; `/v1`;
  `observer-protocol-v1`.
- Supply-chain runs may write 23/`v21` (infrastructure channel) or 27/`v25`
  (travel channel); no new pair.
- No `runner-config-v57`.

### Requirement Evidence

- ARCHITECTURE baseline table and requirement 7; `v4_architecture.py`
  198-211; `compatibility.py` 155-164; `versioning.py` 40-53;
  `test_v4_architecture_invariants.py` 162-395.
- Supported combinations: supply_chains owned (constructs), another unowned
  flag (fails closed), legacy pins unchanged, supply-chain pins unchanged.

### Error Handling and Logging

- Tests only; failures name the pin and observed value, never payloads.

### Tests

- `uv run pytest tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_supply_chain_invariants.py tests/architecture/test_supply_chain_boundaries.py tests/unit/test_supply_chain_pins.py -q`
- `uv run lint-imports` → 25 contracts kept, 0 broken.

### Acceptance Criteria

- All pins pass; the pre-existing invariant suite stays green.
- Import-linter keeps at least the existing 25 contracts, zero broken.
- No production module outside the planned list changed.

### Verification

- `uv run pytest tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_supply_chain_invariants.py tests/architecture/test_supply_chain_boundaries.py tests/unit/test_supply_chain_pins.py -q`
- `uv run lint-imports`
- `git status --porcelain` lists only planned files.

## Phase Risks and Mitigations

- Risk: a third owned-set definition is missed. Mitigation: search all owned
  frozensets; the invariant test catches drift.
- Risk: pins are updated to match a wrong implementation. Mitigation: pins come
  from the locked summary in `index.md`.
- Risk: import-linter needs a new contract. Mitigation: extend an existing
  narrow contract; no permissive additions.

## Phase Completion Checklist

- Task 22 satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkbox is updated immediately after verified completion.
