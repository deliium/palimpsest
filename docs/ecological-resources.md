# Ecological resources

[← Medical beliefs](medical-beliefs.md) · [Back to README](../README.md) · [Next Page →](economic-cascades.md)

Optional bounded renewable-stock feedback owned by V4-36 under
`ecological_feedback`. Society can deplete and degrade selected local stocks;
those stocks then constrain later ordinary extraction. This is not a full
ecology simulator: there are no species, food webs, spatial diffusion, climate
models, disaster coupling, conservation controllers, or population ceilings.

## Scope

| Mechanism | Behavior |
| --- | --- |
| Renewable stock | Ordinary `Resource.quantity` remains the only available stock |
| Local capacity | Effective ceiling is `maximum_quantity − damage` (tenths grid) |
| Withdrawal pressure | Net actual debits after commands, before autonomous renewal |
| Degradation | Withdrawal above the node allowance raises damage |
| Idle recovery | Zero-withdrawal ticks lower damage by `recovery_tenths_per_idle_tick` |
| Seasonal renewal | Existing `environmental_dynamics` multipliers/shortages govern regrowth under the effective ceiling |
| Disabled | No ecology section, no ecology events, legacy pair selection unchanged |

Not modeled: population carrying-capacity policy, inter-node transfer, species
agents, automated conservation, climate, or disasters (still a separate
unowned flag).

## Configuration

Requires `runner-config-v60`, `ecological_feedback=true`, owned
`supply_chains`, active `environmental_dynamics`, and the exact
`ecological_resources` sibling (1–128 managed renewable nodes, lexical order):

```json
{
  "policy_id": "ecological-resources.v1",
  "nodes": [
    {
      "resource_id": "res-water",
      "minimum_capacity_tenths": 5,
      "withdrawal_allowance_tenths": 0,
      "recovery_tenths_per_idle_tick": 1
    }
  ]
}
```

Floors, allowances and recovery are integers on the tenths grid. Each managed
node must already exist as a renewable scenario resource whose
`maximum_quantity` strictly exceeds the floor. Flag/spec/schema mismatches and
missing prerequisites fail closed before runtime objects are created.

## Transition (one managed node per tick)

```text
withdrawn = max(0, start_quantity − post_command_quantity)   # tenths
if withdrawn == 0:
    next_damage = max(0, damage − recovery_tenths)
else:
    next_damage = min(base − floor, damage + max(0, withdrawn − allowance))
capacity = base − next_damage
```

Regrowth uses the existing seasonal rate (and shortage hard-zero), then clips
to the new capacity. Capacity recovery alone never invents stock.

## Perception and reads

- Agents observe ordinary folded quantity and regeneration only.
- Private `ecological_resource_changed` capacity transitions are hidden from
  observer list, detail, tick, frame and WebSocket surfaces
  (`observer_event_not_found` on direct lookup).
- Authorized raw objective inspection still contains ecology events when present.
- No new observer semantic type; public count remains 73.

## Persistence and replay

Enabled runs select reserved write pair event schema **25** / codec **`v23`**.
Checkpoints store mandatory `ecological_resources` and `environmental_dynamics`
siblings. Historical replay folds recorded capacity and stock effects without
the live ecology policy. Continuation at the durable head requires a verified
matching `EcologicalResourcesSpec` on `ReplayRequest`; without it the result
stays read-only and `open_durable` rejects. Mismatched policy or season digests
fail closed. No Alembic migration; head remains `0017`.

## Controlled demonstration

Matched arms in `tests/unit/test_ecological_resources_feedback.py` (seed `34`):

| Arm | Tick-0 actions | Allowance | Tick-2 probe |
| --- | --- | --- | --- |
| Degradation | both founders `Drink` managed node | `0` | `resource_depleted` (structural rejection) |
| Depletion-only | same drinks | `20` | admitted `Drunk` |
| Rest | both `Wait` | `0` | admitted `Drunk` |

Expected end-of-tick managed quantities: degradation `0.5` then `0.6`;
depletion-only `1.5` then `2.0`; rest stays `2.0`. Unmanaged same-kind water
is unchanged.

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_*.py -q
```

Disposable-DB durability (skipped when `PALIMPSEST_TEST_DATABASE_URL` is unset):

```bash
uv run --frozen --python 3.12.14 pytest -m integration \
  tests/integration/test_ecological_resources_durable_replay.py -q
```

## See Also

- [Overexploitation](overexploitation.md) — v61 deepening (pressure receipts, 29/`v27`)
- [Configuration](configuration.md)
- [V4 versioning](v4-versioning.md)
- [Physical Simulation](physical-simulation.md)
- [Disease mechanics](disease-mechanics.md)
- [Persistence](persistence.md)
