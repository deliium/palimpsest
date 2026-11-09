# Phase 1: Ownership and contract

Plan: [index.md](index.md)
Tasks: 1-2
Depends on: none

## Objective

Claim `infrastructure_networks` ownership on **both** owned-flag frozensets,
publish the locked policy id, freeze the eight-kind catalog with exact
constants, and convert public-good kind sets to explicit frozensets.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/runner_models.py` | `_V4_OWNED_CAPABILITY_FLAGS` 325-333 | Runtime ownership |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 156-163 | Compatibility export; must match |
| `tests/unit/test_runner_config_v4_flags.py` | equality assert ~126-135 | Dual-frozenset pin |
| `src/world/collective_projects.py` | `PUBLIC_GOOD_KINDS` 209-227 | Auto-includes every kind except record_site |
| `src/simulation/v4_architecture.py` | `INFRASTRUCTURE_NETWORKS` 185-197 | Declared context |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/runner_models.py` | modify | Add flag to `_V4_OWNED_CAPABILITY_FLAGS` |
| `src/simulation/compatibility.py` | modify | Add flag to `V4_OWNED_CAPABILITY_FLAGS` (identical set) |
| `src/world/infrastructure.py` | create | Policy, kinds, statuses, locked catalog, forbid-list |
| `src/world/collective_projects.py` | modify | Explicit `PUBLIC_GOOD_KINDS` / `DRAW_*` / `PRESENCE_*` |
| `src/world/__init__.py` | modify | Re-export public contracts |
| `tests/unit/test_infrastructure_contract.py` | create | Catalog + public-good membership tests |
| Architecture pin suites | modify | Owned count 5→6 / frozenset equality |

## Task 1: Own `infrastructure_networks` on both flag frozensets

### Intent
Enable the flag without leaving `compatibility.V4_OWNED_CAPABILITY_FLAGS` stale.

### Implementation Steps
1. Add `"infrastructure_networks"` to `_V4_OWNED_CAPABILITY_FLAGS` in
   `runner_models.py` and to `V4_OWNED_CAPABILITY_FLAGS` in `compatibility.py`
   with the **same** six-member frozenset.
2. Confirm `SimulationRunner.from_config` accepts the owned flag on v56 and still
   fail-closes other unowned flags.
3. Create `src/world/infrastructure.py` with
   `INFRASTRUCTURE_NETWORKS_POLICY_ID = "infrastructure-networks.v1"` and
   `INFRASTRUCTURE_ID_PREFIX = "infra-"`.
4. Bind gate: flag on ⇒ schema v56 and `collective_projects` present; else
   `infrastructure_requires_collective_projects` / `infrastructure_requires_v56`.
5. Log INFO `infrastructure_networks_enabled policy_id=…` (no agent ids).
6. Sweep every current architecture assertion of owned-flag length `5` / exact
   five-name frozenset to include infrastructure (Task 23 completes the full
   sweep; Task 1 covers the two source frozensets + runner unit test).

### Required Interfaces and Contracts
- Owned set exactly: `organizations`, `formal_rules`, `legal_disputes`,
  `diplomacy`, `organized_conflict`, `infrastructure_networks`.
- `_V4_OWNED_CAPABILITY_FLAGS == V4_OWNED_CAPABILITY_FLAGS`.
- No `runner-config-v57`.

### Error Handling and Logging
- ERROR: `infrastructure_requires_collective_projects`,
  `infrastructure_requires_v56`, `capability_unimplemented`.
- DEBUG: bind booleans only.

### Tests
- `tests/unit/test_infrastructure_contract.py` + update
  `tests/unit/test_runner_config_v4_flags.py`.
- Command:
  `uv run pytest tests/unit/test_infrastructure_contract.py tests/unit/test_runner_config_v4_flags.py -q`

### Acceptance Criteria
- Both frozensets equal and size 6; flag enables with collective_projects; other
  unowned flags still unimplemented.

### Verification
- Pytest commands above green.

## Task 2: Locked kinds catalog and explicit public-good sets

### Intent
Remove implementer choice on numbers and stop new kinds from auto-joining public
goods.

### Implementation Steps
1. Define `InfrastructureKind`, `InfrastructureTopology` (`node`|`edge`),
   `InfrastructureStatus` (`operational`|`damaged`|`destroyed`) — **no**
   `under_construction`.
2. Populate `INFRASTRUCTURE_CATALOG` with the exact table from `index.md`
   Architecture (labor/material/decay/op_min/effects).
3. Convert `PUBLIC_GOOD_KINDS` to an explicit frozenset of the pre-V4-16 public
   kinds: `shared_shelter`, `bridge`, `storage`, `winter_reserve`, `well`,
   `warning_post` (exclude `record_site` and all new infra-only kinds).
4. Keep `DRAW_PUBLIC_KINDS` and `PRESENCE_PUBLIC_KINDS` as explicit frozensets
   with their current membership only.
5. Unit-test that collective catalog labor/materials for shared kinds match the
   infrastructure catalog where kinds map 1:1 (`bridge`, `storage`, `well`,
   `warning_post`).
6. Define `INFRASTRUCTURE_FORBIDDEN_FIELDS` including `score`,
   `infrastructure_score`, `civilization_score`, `planner`, `auto_maintain`,
   `owner_id`, `crew`, `nation_id`, `grid`, `coordinate`.

### Required Interfaces and Contracts
- Unknown kind → `infrastructure_unknown_kind`.
- Effects apply only when `status == operational` and
  `integrity >= operational_integrity_min`.

### Error Handling and Logging
- ERROR on catalog validation; DEBUG `infrastructure_catalog_loaded kind_count=8`.

### Tests
- Exact constant table; public-good membership excludes road/irrigation/
  trade_post/large_shelter; forbid-list.
- `uv run pytest tests/unit/test_infrastructure_contract.py -q`

### Acceptance Criteria
- Locked catalog committed; public-good sets explicit; no under_construction.

### Verification
- Contract tests green.

## Phase Risks and Mitigations
- Risk: updating only one owned frozenset.
  Mitigation: equality test in Task 1.
- Risk: `PUBLIC_GOOD_KINDS = frozenset(CollectiveProjectKind)` regressions.
  Mitigation: explicit membership tests.

## Phase Completion Checklist
- Tasks 1-2 acceptance met.
