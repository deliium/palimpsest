# Disasters

[← Commons governance](commons-governance.md) · [Back to README](../README.md) · [Societal resilience →](societal-resilience.md)

Optional rare objective shocks owned by V4-39 under `disasters`. Exact
`runner-config-v63` plus `disasters.v1` schedule bounded one-tick pulses against
managed ecological stocks, operational infrastructure, or the active fictional
disease channel. Shocks are configured physical mechanics with integer
parts-per-million chances — not narrative hazard labels, cognition authority,
or arbitrary mutation hooks.

## Scope

| Kind | Target | Pulse effect |
| --- | --- | --- |
| `flood_like` | Managed FOOD stock | Quantity loss (tenths) |
| `fire` | Managed FOOD or MATERIAL stock | Quantity loss; clear weather only |
| `drought` | Managed WATER stock | Quantity loss |
| `resource_collapse` | Managed FOOD/WATER/MATERIAL stock | Capacity damage (tenths) |
| `infrastructure_destruction` | Live infra asset by kind/topology | Existing condition/durability path |
| `epidemic_surge` | Location under active disease | Extra private exposure opportunity (milli) |

Not modeled: long-lived hazard fronts, automatic geographic spread, secondary
disasters, new death mechanisms, real-world hazard calibration, or population-
scale causal claims from the fixture.

Disabled (`disasters=false` / no v63 sibling): no scheduling, disaster state,
draws, or new writes; prior channel write selections stay unchanged.

## Configuration

Requires `runner-config-v63`, `disasters=true`, owned `ecological_feedback` and
`supply_chains`, active `environmental_dynamics`, and `ecological_resources`.
Infrastructure destruction additionally requires `infrastructure_networks`.
Epidemic surge additionally requires active `epidemics` / `disease_mechanics`.
Sibling ecology modes (overexploitation, commons governance) may compose only
through their existing prerequisites.

```json
{
  "policy_id": "disasters.v1",
  "rules": [
    {
      "rule_id": "drought-a",
      "kind": "drought",
      "chance_ppm": 0,
      "target": {"resource_id": "res-water"},
      "effect": {"loss_tenths": 10}
    }
  ],
  "schedule": []
}
```

| Field | Contract |
| --- | --- |
| `chance_ppm` | Integer parts-per-million in `[0, 10000]`; scheduled rules must be `0` |
| `schedule` | Zero or more `{tick, rule_id}` entries; each rule applies at most once |
| Stock effects | `loss_tenths` / `capacity_damage_tenths` in `[1, 10000]` |
| Surge effect | `extra_opportunity_milli` in `[1, 1000]` |
| Infra effect | Empty object; uses existing infrastructure mutation |

Zero chance plus empty schedule is the inert control. A policy may mix
scheduled and spontaneous rules; sources stay disjoint per rule. Due scheduled
candidates resolve before spontaneous candidates in the same tranche.

### Kind examples (programmatic)

```python
from simulation.disasters_config import DISASTERS_POLICY_ID, DisastersSpec
from world.disasters import (
    DisasterCollapseEffect,
    DisasterInfrastructureEffect,
    DisasterInfrastructureTarget,
    DisasterKind,
    DisasterLocationTarget,
    DisasterLossEffect,
    DisasterResourceTarget,
    DisasterRule,
    DisasterScheduleEntry,
    DisasterSurgeEffect,
)
from world.identifiers import EntityId
from world.infrastructure import InfrastructureKind

flood = DisasterRule(
    rule_id="flood-a",
    kind=DisasterKind.FLOOD_LIKE,
    chance_ppm=0,
    target=DisasterResourceTarget(resource_id=EntityId("res-food")),
    effect=DisasterLossEffect(loss_tenths=10),
)
fire = DisasterRule(
    rule_id="fire-a",
    kind=DisasterKind.FIRE,
    chance_ppm=0,
    target=DisasterResourceTarget(resource_id=EntityId("res-material")),
    effect=DisasterLossEffect(loss_tenths=10),
)
drought = DisasterRule(
    rule_id="drought-a",
    kind=DisasterKind.DROUGHT,
    chance_ppm=0,
    target=DisasterResourceTarget(resource_id=EntityId("res-water")),
    effect=DisasterLossEffect(loss_tenths=10),
)
collapse = DisasterRule(
    rule_id="collapse-a",
    kind=DisasterKind.RESOURCE_COLLAPSE,
    chance_ppm=0,
    target=DisasterResourceTarget(resource_id=EntityId("res-water")),
    effect=DisasterCollapseEffect(capacity_damage_tenths=25),
)
infra = DisasterRule(
    rule_id="infra-a",
    kind=DisasterKind.INFRASTRUCTURE_DESTRUCTION,
    chance_ppm=0,
    target=DisasterInfrastructureTarget(
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        infrastructure_kind=InfrastructureKind.WELL,
    ),
    effect=DisasterInfrastructureEffect(),
)
surge = DisasterRule(
    rule_id="surge-a",
    kind=DisasterKind.EPIDEMIC_SURGE,
    chance_ppm=0,
    target=DisasterLocationTarget(location_id=EntityId("loc-settled")),
    effect=DisasterSurgeEffect(extra_opportunity_milli=1000),
)

# Zero-probability scheduled pair (control keeps schedule=()).
control = DisastersSpec(
    policy_id=DISASTERS_POLICY_ID, rules=(drought,), schedule=()
)
treatment = DisastersSpec(
    policy_id=DISASTERS_POLICY_ID,
    rules=(drought,),
    schedule=(DisasterScheduleEntry(tick=2, rule_id="drought-a"),),
)

# Nonzero spontaneous example (empty schedule; seeded stream).
spontaneous = DisastersSpec(
    policy_id=DISASTERS_POLICY_ID,
    rules=(
        DisasterRule(
            rule_id="drought-a",
            kind=DisasterKind.DROUGHT,
            chance_ppm=2500,
            target=DisasterResourceTarget(resource_id=EntityId("res-water")),
            effect=DisasterLossEffect(loss_tenths=10),
        ),
    ),
    schedule=(),
)
```

Default runner write remains `runner-config-v4`. Active disaster runs select
reserved write pair event **26** / codec **`v24`**. Ecology remains event
**29** / codec **`v27`** when that channel is active. Alembic head stays
`0017`. Commands stay 45; observer semantics stay 73; metric catalog stays
275. No new `/v1` route or client protocol.

## Trigger order and receipts

1. Evaluate due scheduled rules for the current tick (consumed once).
2. Evaluate spontaneous rules with disjoint keyed draws.
3. Journal typed `DisasterResolved` effects (or skip outcomes), never a
   seed-only trigger.

| Outcome | Meaning |
| --- | --- |
| `applied` | Pulse mutated eligible physical or private disease state |
| `no_effect` | Eligible attempt produced no material change |
| `weather_ineligible` | Fire under rain (or similar closed weather gate) |
| `no_live_asset` / `asset_ambiguous` | Infrastructure target missing or not unique |
| Absent | Feature off, rule not due, or probability miss |

Historical fold applies recorded effects without the live policy. Live
continuation from restored state requires a matching disasters policy digest.
Private disease and hazard evidence stay out of ordinary observers and
cognition; receipts can still participate in journal verification after public
page selection excludes them.

Existing stock recovery, infrastructure repair/decay, and disease progression
continue on their ordinary schedules after a one-tick pulse.

## Controlled experiments

Off-gate `disasters@1` builds paired `control` / `scheduled-shock` arms by
replacing only the immutable schedule on a validated v63 base (one rule, zero
`chance_ppm`, empty schedule, finite horizon beyond the inject tick):

```python
from experiments import experiment_disasters
from world.disasters import DisasterScheduleEntry

definition = experiment_disasters(
    base,  # validated runner-config-v63 disasters document
    treatment_entry=DisasterScheduleEntry(tick=2, rule_id="drought-a"),
)
```

`ExperimentCoordinator.run_all` assigns distinct durable run IDs while
preserving seed and stochastic identity. Qualification compares pre-treatment
physical prefixes and measured deltas from committed events — not whole
snapshot bytes or narrative outcomes. Same-identity spontaneous twins must
match canonical objective event output; a contrasting seed may diverge.

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_disaster_*.py tests/unit/test_v1_regression_gate.py -q
```

## See Also

- [Ecological resources](ecological-resources.md) — managed stock prerequisite
- [Disease mechanics](disease-mechanics.md) — private surge privacy contract
- [Commons governance](commons-governance.md) — composed two-pool fixture lane
- [Configuration](configuration.md) — runner schema gates
- [Development](development.md) — verification commands
