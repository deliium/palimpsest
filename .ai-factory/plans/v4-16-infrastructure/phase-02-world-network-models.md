# Phase 2: World network models

Plan: [index.md](index.md)
Tasks: 3-4
Depends on: Phase 1 / Tasks 1-2

## Objective

Introduce immutable objective infrastructure asset records and attach them to
`WorldState`, including new structure kinds needed for anchors and completion.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/world/_state.py` | `WorldState`, `rebuild_world_state` | Attachment + rebuild kwargs |
| `src/world/production.py` | `StructureKind` 87-93 | Extend ROAD/IRRIGATION/TRADE_POST |
| `src/world/collective_projects.py` | `CollectiveProject` 284-301 | Shape precedent; later target_location_id |
| `src/world/identifiers.py` | `EntityId` | Minting |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/world/infrastructure.py` | modify | `InfrastructureAsset` dataclass |
| `src/world/_infrastructure.py` | create | insert/replace/cap helpers |
| `src/world/_state.py` | modify | `infrastructure` field + `rebuild_world_state` kwarg |
| `src/world/production.py` | modify | `StructureKind.ROAD`, `IRRIGATION`, `TRADE_POST` |
| `tests/unit/test_infrastructure_models.py` | create | Validation suite |

## Task 3: `InfrastructureAsset` / network WorldState types

### Intent
Define the only objective infrastructure record the engine mutates.

### Implementation Steps
1. Add frozen `InfrastructureAsset` fields:
   `asset_id`, `kind`, `topology`, `status` (`operational`|`damaged`|`destroyed`),
   `integrity` ∈ [0,1], `location_id`, `endpoint_location_id` (required iff edge),
   `linked_structure_id`, `linked_project_id`, `created_tick`,
   `last_maintained_tick`.
2. Validation: edge endpoints distinct + present; node forbids endpoint;
   `destroyed` ⇒ integrity `0.0`; reject forbidden field names.
3. Caps: `MAX_INFRASTRUCTURE_ASSETS = 64`.
4. `WorldState.infrastructure: Mapping[EntityId, InfrastructureAsset] | None`.
   Channel off ⇒ `None`; channel on at run start ⇒ empty mapping `{}`.
5. Thread `infrastructure=` through `rebuild_world_state`.
6. Add `StructureKind.ROAD`, `IRRIGATION`, `TRADE_POST`.

### Required Interfaces and Contracts
- No coordinates/polygons/grid cells.
- Assets are never created in `under_construction` status.

### Error Handling and Logging
- ERROR codes: `infrastructure_invalid_topology`, `infrastructure_edge_endpoints`,
  `infrastructure_integrity_range`, `infrastructure_destroyed_integrity`.

### Tests
- Node/edge/destroyed matrix; rebuild preserves mapping; new StructureKind values.
- `uv run pytest tests/unit/test_infrastructure_models.py -q`

### Acceptance Criteria
- Valid assets freeze; invalid topologies fail closed; rebuild supports field.

### Verification
- Model tests green.

## Task 4: Content-addressed `infra-` identity helpers

### Intent
Deterministic ids without UUID/`hash()`/wall-clock.

### Implementation Steps
1. `mint_infrastructure_id` from `(kind, sorted endpoint location values,
   created_tick, project_id)` using the repo’s content-address / namespaced
   digest pattern.
2. Normalize edge endpoints so `location_id < endpoint_location_id` by id string
   order at mint/insert time.
3. Insert collision → `infrastructure_id_collision`.
4. DEBUG digest prefix only (≤8 hex).

### Required Interfaces and Contracts
- Prefix always `infra-`; endpoint permutation ⇒ same id.

### Error Handling and Logging
- ERROR `infrastructure_id_collision`, `infrastructure_id_prefix`.

### Tests
- Permutation stability; kind/location divergence; prefix enforcement.
- `uv run pytest tests/unit/test_infrastructure_models.py -q`

### Acceptance Criteria
- Stable `infra-` ids; collisions fail closed.

### Verification
- Identity tests green.

## Phase Risks and Mitigations
- Risk: forgetting `rebuild_world_state` kwarg.
  Mitigation: explicit Task 3 step + rebuild test.

## Phase Completion Checklist
- Tasks 3-4 done.
