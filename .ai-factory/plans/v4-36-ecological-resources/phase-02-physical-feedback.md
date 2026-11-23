# Phase 2: Physical feedback

Plan: [index.md](index.md)  
Tasks: 3–4  
Depends on: Phase 1

## Objective

Ordinary admitted withdrawals lower future stock capacity on selected renewable nodes; the existing season schedule governs regrowth, and resting a node restores capacity gradually. Existing unmanaged nodes and the current tick's already resolved admissions are untouched.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/world/models.py` | `Resource` | Already has actual quantity, baseline maximum and base regeneration. No parallel stock model is needed. |
| `src/world/_rules.py`, `src/world/_production.py`, `src/world/_experiment_apply.py` | Resource extraction and `_mutate_drink`, `_apply_harvest`, `_consume` | Multiple command paths debit nodes; counting `Harvest` commands would miss real withdrawals. |
| `src/simulation/engine.py` | `WorldEngine` autonomous physical resolution around `apply_autonomous_physical_step` | Receives the tick-start snapshot and the post-command / post-completion candidate. |
| `src/world/_physical.py` | `apply_autonomous_physical_step`, `node_quantity_witness` use | One sorted regeneration pass already applies seasonal multipliers, shortage windows and infrastructure. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/world/_ecological_resources.py` | create | Pure damage transition, fixed-point capacity and invariants; no new RNG. |
| `src/world/_physical.py`, `src/simulation/engine.py` | modify | Pass tick-start quantities for managed nodes; apply damage and existing regeneration in the same resource pass. |
| `src/world/events.py`, `src/world/__init__.py` | modify | Add the frozen typed effect and export the public event detail, without exposing the private state. |
| `tests/unit/test_ecological_resources_engine.py`, `tests/unit/test_ecological_resources_transition.py` | create | Property tests and real ordered-action/next-observation checks. |

## Task 3: Implement the bounded stock transition

### Intent

Encode one auditable local mechanism, not a separate ecology simulation.

### Implementation Steps

1. Implement an internal pure `advance_stock_damage` in `world._ecological_resources`. Its inputs are a trusted row, baseline `maximum_quantity`, tick-start quantity and post-command quantity, converted from canonical world tenths. Return updated damage; do not mutate inputs.
2. Use exact integer arithmetic, where `base` is the configured node's `Resource.maximum_quantity` in tenths, `floor` its explicit positive minimum capacity, and `damage` the capacity lost in tenths:

   ```text
   withdrawn = max(0, start_quantity - post_command_quantity)
   if withdrawn == 0:
       next_damage = max(0, damage - recovery_tenths)
   else:
       next_damage = min(base - floor, damage + max(0, withdrawn - allowance_tenths))
   capacity = base - next_damage
   ```

3. Withdrawals up to the allowance preserve existing damage; only a zero-withdrawal tick heals. Capacity loss is no greater than actual withdrawal, so stock that was valid at tick start cannot be above the new capacity after the withdrawal. Assert this invariant rather than adding a clipping effect. A capacity increase does not itself add stock.
4. Define `EcologicalResourceChanged(resource_id, before_damage_tenths, after_damage_tenths)` for the resulting capacity transition only. Reject a no-op damage change or non-integer or negative units. The actual stock changes are recorded by the existing extraction and regeneration events. Do not embed policy knobs or project future yields into the event. Task 5 implements wire admission and projection.

### Required Interfaces and Contracts

- Existing `Resource.maximum_quantity` remains the immutable baseline. Effective capacity is local, never a population threshold or admission quota.
- `0 <= quantity <= capacity <= base`, `floor <= capacity`, `0 <= damage <= base - floor`; no extra draws, growth clock, age structure, spatial diffusion or RNG.
- Source: Original Request and `docs/v4-architecture.md` → `ecological_feedback`; the latter's no automatic carrying-capacity policy is preserved by explicit per-node stock limits, not a policy acting on populations.

### Error Handling and Logging

Reject invalid bounds or off-grid managed quantities instead of rounding unknown state into validity. Use stable reason codes. Pure math does not log.

### Tests

`tests/unit/test_ecological_resources_transition.py`: table cases for exact allowance, zero withdrawal, saturation at floor, repeated pressure, recovery saturation, recovery without growth, and subunit inputs. Use Hypothesis with valid integral-tenth bounds and command quantities to assert stock/cap invariants (including that clipping is never needed), deterministic equality, monotonic damage with increasing withdrawal at fixed prior damage, and no stock creation in the pure step.

### Acceptance Criteria

With base `4.0`, floor `1.0`, allowance `0.0`, and recovery `0.5`, a `2.0` withdrawal at full stock makes damage `2.0`, retains `2.0` standing stock and caps later renewal at `2.0`; a following rest tick raises capacity to `2.5` without creating stock by itself.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_transition.py -q` passes.

## Task 4: Integrate at the post-command regeneration boundary

### Intent

Close the loop with the world agents actually observe and act on, without changing cognition or admission rules.

### Implementation Steps

1. In the engine's autonomous resolution, take managed node quantities from the same tick-start state used for observations. Pass this read-only bounded mapping and the typed physical parameters from Task 2 into `apply_autonomous_physical_step`. Use the candidate after ordered action resolution and due completions as `post_command_quantity`; a failed, denied, or rolled-back effect has no artificial pressure. Do not add per-command extraction hooks.
2. At the start of each managed row's existing sorted regeneration iteration apply Task 3, keeping both mutations in the same candidate rebuild. Stage its change event with the existing regeneration system family and a distinct ordinal before that node's regeneration event; retain existing `origin_location_id` and deterministic ordering. Emit the ecology event only when damage changes, including when no stock changes. Failed ticks publish neither state nor these events.
3. Preserve rate calculation order: base rate × existing season multiplier, then existing shortage suppression and infrastructure delta for unmanaged nodes exactly as today. For managed nodes, shortage is a hard zero of total regrowth for that tick (including bonus); otherwise take the existing rounded seasonal rate plus infrastructure delta, floored at zero. Regrow from the post-command quantity by at most the gap to effective capacity. Emit ordinary `ResourceRegenerated` for strictly positive growth only using its actual delta and resulting quantity. Preserve the existing zero-to-positive node witness on regrowth and all command-side depletion witnesses.
4. Let the next tick observe the ordinary folded `Resource.quantity` via existing perception. No new observation fields; no capacity/damage exposed to cognition, prompts, stop policies or agent-facing prior-event hints. No change to inventory outputs, tool bonuses, access checks or extraction costs. If ecology is off, do not build a pressure map or change ordering, events, or calculations.

### Required Interfaces and Contracts

- Concurrent pressure means multiple valid ordered actions on the same node in one tick; use aggregate actual debit, not the sum of requests. Dynamics-on/unmanaged and all ecology-off behavior retain legacy rules.
- One row pass and constant work per row beyond existing season/infrastructure lookup; bounded staging, no history scan or extra awaits. Do not heal a node twice on retries or replay.
- Sources: `.ai-factory/ARCHITECTURE.md` → Objective authority and runtime, Versioned Extension Contract; existing `EnvironmentalDynamicsSpec.season_at` and `multiplier_for` are the seasonal source of truth.

### Error Handling and Logging

Missing managed baseline/candidate, missing bound policy, or cap/state mismatch aborts the tick; no silent fallback to legacy regeneration. One metadata-only DEBUG summary when there are changes (tick, managed count, damaged/restored count); no raw policy, rows, stock amounts or agent command payloads.

### Tests

`tests/unit/test_ecological_resources_engine.py`: before the replay pair is registered, exercise `apply_autonomous_physical_step` with valid post-command state and tick-start quantities, and assert its `PendingSystemStep.working_state` and ordered `pending_details` without publishing events. Include an unmanaged same-kind node, season transition and zero-yield season, depleted-node recovery and existing node witnesses, and managed shortage with infrastructure delta versus legacy unmanaged treatment. Mechanical expected values use the rate at the committed tick, not the next observation's season. Task 5 adds the real resolution/commit assertions to this file.

### Acceptance Criteria

The physical candidate contains the expected changed stock and ordered typed pending effects, without publishing anything. An unselected node and the off path preserve established behavior. Task 5 proves the installed engine publishes the same result.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_engine.py tests/unit/test_environmental_dynamics_resolution.py tests/unit/test_environmental_dynamics_perception.py -q` passes without requiring the new persistence codec.

## Phase Risks and Mitigations

- Accidentally regenerating twice or ignoring direct drinking: use one stock pass with before/after quantities, not a second pass or action-kind accounting.
- Silent drift in action ordering or witness IDs: keep unmanaged order unchanged and assert same-node ecology-before-regeneration order at commit/replay.

## Phase Completion Checklist

- Formula and physical candidate verified; committed engine tests are owned by Task 5.
- Update only the verified task checkboxes in `index.md`.
