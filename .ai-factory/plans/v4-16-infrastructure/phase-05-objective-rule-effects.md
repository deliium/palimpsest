# Phase 5: Objective rule effects

Plan: [index.md](index.md)
Tasks: 10-13
Depends on: Phase 2 / Tasks 3-4; Phase 4 / Task 9

## Objective

Make operational infrastructure objectively alter travel, capacity, production/
storage, and risk inside WorldEngine rules while remaining location-based.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/world/_rules.py` | `_travel_duration` 1162-1164; move apply ~3203 | Travel hooks |
| `src/world/regions.py` | `RegionRoute.duration_ticks`, `fatigue_cost` | Regional journeys |
| `src/world/models.py` | location capacities | Capacity checks |
| `src/world/_collective_projects.py` | bridge fatigue / warning exposure relief | Risk precedents |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/world/_infrastructure.py` | modify | Operational query helpers |
| `src/world/_rules.py` | modify | Effective travel/capacity/exposure |
| Resource/production tick paths | modify | Regen + store caps |
| `tests/unit/test_infrastructure_effects.py` | create | Effect matrix |

## Task 10: Travel time and fatigue modifiers

### Intent
Roads shorten hop duration/fatigue; bridges relieve fatigue from their location.

### Implementation Steps
1. `effective_travel_duration` / `effective_travel_fatigue` start from base route
   values then apply sorted operational assets:
   - edge assets matching normalized `{origin,destination}` use catalog travel
     deltas
   - operational `bridge` nodes at origin apply fatigue delta
2. Clamp duration ≥ 1 and fatigue ≥ 0.
3. Replace move/transport call sites when channel active.
4. Non-operational assets contribute nothing.

### Required Interfaces and Contracts
- Sort by `asset_id` before folding; no global speed multiplier.

### Error Handling and Logging
- DEBUG base vs effective ints only.

### Tests
- Road shortens duration; destroyed ignored; min 1; bridge fatigue; channel off
  legacy.
- `uv run pytest tests/unit/test_infrastructure_effects.py -k travel -q`

### Acceptance Criteria
- Travel modifiers match locked catalog.

### Verification
- Travel tests green.

## Task 11: Location capacity modifiers

### Intent
Large shelters / trade posts raise body/item capacity at their location.

### Implementation Steps
1. `effective_body_capacity` / `effective_item_capacity` = base + sorted deltas.
2. Clamp bonuses with `MAX_INFRA_BODY_BONUS = 8` and `MAX_INFRA_ITEM_BONUS = 8`.
3. Patch admission checks when channel active.

### Required Interfaces and Contracts
- Catalog deltas ≥ 0; bonuses never reduce below base before clamp.

### Error Handling and Logging
- WARN `infrastructure_capacity_bonus_clamped`.

### Tests
- Shelter body bonus; destroyed inert; clamp.
- `uv run pytest tests/unit/test_infrastructure_effects.py -k capacity -q`

### Acceptance Criteria
- Location-scoped clamped capacity bonuses.

### Verification
- Capacity tests green.

## Task 12: Resource production and storage modifiers

### Intent
Irrigation boosts regen; storage/trade_post raise store ceilings.

### Implementation Steps
1. Operational `irrigation` adds `resource_regen_delta` to all regenerating
   resources at its location.
2. Operational `storage` / `trade_post` add `store_capacity_delta` to linked
   store max `stored_quantity`.
3. No auto-create/teleport of items; no supply-chain planner.

### Required Interfaces and Contracts
- Missing linked store ⇒ skip with WARN unresolved; do not invent stores.

### Error Handling and Logging
- DEBUG regen base/delta; WARN unresolved store link.

### Tests
- Irrigation vs control twin; storage max; destroyed inert.
- `uv run pytest tests/unit/test_infrastructure_effects.py -k production -q`

### Acceptance Criteria
- Production/storage modifiers proven without allocation planner.

### Verification
- Production tests green.

## Task 13: Risk and exposure modifiers

### Intent
Communication markers and large shelters reduce exposure magnitude only.

### Implementation Steps
1. Multiply exposure by `∏ (1 - exposure_relief_coefficient)` for operational
   assets at the location with nonzero coefficient.
2. Clamp product to `[0,1]`.
3. Never publish a safety/infrastructure score field.

### Required Interfaces and Contracts
- Physical effect only; forbid-list applies to DTOs.

### Error Handling and Logging
- DEBUG relief product.

### Tests
- Marker reduces exposure; stacking multiplies; destroyed inert.
- `uv run pytest tests/unit/test_infrastructure_effects.py -k exposure -q`

### Acceptance Criteria
- Exposure relief works without score fields.

### Verification
- Exposure tests green.

## Phase Risks and Mitigations
- Risk: global multipliers.
  Mitigation: helpers require location or edge endpoints.

## Phase Completion Checklist
- Tasks 10-13 focused tests green; channel-off legacy preserved.
