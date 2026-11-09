# Phase 4: Lifecycle

Plan: [index.md](index.md)
Tasks: 8-9
Depends on: Phase 3 / Task 7

## Objective

Support damage, repair, decay, and destruction using Maintain/Oppose/Repair plus
engine tick decay — never automatic maintenance.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/world/_collective_projects.py` | maintain/oppose/decay helpers | Sync points |
| `src/world/actions.py` | `MaintainPublicGood`, `OpposePublicGood`, `Repair` | Command reuse |
| `src/world/production.py` | `Structure.integrity` | Repair linkage |
| `src/simulation/engine.py` | end-of-tick public-good decay | Schedule infra decay |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/world/_infrastructure.py` | modify | damage/repair/decay/destroy helpers |
| `src/world/_collective_projects.py` | modify | Sync linked infra after maintain/oppose/public decay |
| `src/world/_rules.py` | modify | Sync after `Repair` |
| `src/simulation/engine.py` | modify | Call `decay_infrastructure` each tick |
| `tests/unit/test_infrastructure_lifecycle.py` | create | Lifecycle matrix |

## Task 8: Damage and repair command wiring

### Intent
Explicit agent commands change integrity; destroyed assets reject repair.

### Implementation Steps
1. Successful `MaintainPublicGood` on a linked project raises infra integrity by
   `REPAIR_INTEGRITY_DELTA = 0.15`, sets `last_maintained_tick`, and restores
   `operational` when ≥ catalog min (unless destroyed).
2. `OpposePublicGood` lowers integrity; below min ⇒ `damaged`; `0.0` ⇒ `destroyed`.
3. Successful production `Repair` on `linked_structure_id` (including ROAD)
   mirrors the maintain upward path even when public_goods is off.
4. Never bypass material/labor shortage paths of those commands.
5. Repair/maintain on `destroyed` ⇒ reject `infrastructure_destroyed`.
6. Emit repaired/damaged event hooks for Task 14.

### Required Interfaces and Contracts
- No new AgentCommand types.
- Destroyed is terminal for modifiers and repair.

### Error Handling and Logging
- DEBUG integrity before/after (quantized millis); WARN destroyed repair attempts.

### Tests
- Maintain/Oppose/Repair paths; road Repair without public_goods; destroyed
  reject; shortage unchanged.
- `uv run pytest tests/unit/test_infrastructure_lifecycle.py -q`

### Acceptance Criteria
- Damage/repair require resources/labor via existing commands; roads Repairable.

### Verification
- Lifecycle tests green.

## Task 9: Tick decay and destruction

### Intent
Unmaintained assets lose integrity each tick without auto-repair.

### Implementation Steps
1. `decay_infrastructure(state, tick)` runs end-of-tick when channel active.
2. Subtract catalog `decay_per_tick`; clamp; update status; `0.0` ⇒ `destroyed`
   tombstone retained.
3. After public-good structure decay and infra decay, linked assets take
   `min(structure.integrity, asset.integrity)` (fail closed on worse condition).
4. Emit decayed/destroyed events (Task 14).
5. Architecture/unit guard: no scheduler calls repair without an agent command.

### Required Interfaces and Contracts
- Tombstones retained; modifiers ignore non-operational assets.

### Error Handling and Logging
- DEBUG decayed_count; INFO destroyed_count; WARN threshold crossings.

### Tests
- Deterministic multi-tick decay; threshold flips; destroy once; no auto-repair.
- `uv run pytest tests/unit/test_infrastructure_lifecycle.py -q`

### Acceptance Criteria
- Decay/destruction deterministic; no automatic maintenance.

### Verification
- Decay tests green.

## Phase Risks and Mitigations
- Risk: double-decay divergence.
  Mitigation: min() coupling rule above.

## Phase Completion Checklist
- Tasks 8-9 done.
