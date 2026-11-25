# Commons governance

[← Overexploitation](overexploitation.md) · [Back to README](../README.md) · [Next Page →](disasters.md)

Optional voluntary owner-scoped commons evidence under V4-38. Exact
`runner-config-v62` plus `commons-governance.v1` let several agents share finite
renewable water stocks and negotiate restrictions, monitoring, sanctions,
access claims, rotation, cooperation, or overuse through existing norms, formal
rules, and institution concepts. Nothing is mandatory: claims never enter
physical admission, and zero autonomous emergence is a valid research outcome.

## Scope

| Mechanism | Behavior |
| --- | --- |
| Opt-in | Exact `commons_governance` sibling on `runner-config-v62`; v61 overexploitation + ecology prerequisites required |
| Social prerequisites | `formal_rules=true`; every founder uses deterministic `social_norm_mode` and `institution_concept_mode` |
| Stock selector | 1–8 unique sorted WATER entity IDs that are ecology-managed with positive renewal |
| Monitoring | Visible stock quantity change only; peer accounts are testimony, not witnessed draws |
| Speech | Bounded one-relation `cgo_v1` inside ordinary `Talk`/`Tell` |
| Voluntary deferral | Uncontested owner-accepted rest/out-of-turn may replace `Drink` with `Wait` when thirst is below 0.65 |
| Measurement | Programmatic detached `commons-governance-report-v1`; no metric-catalog append |
| Disabled | Legacy v61/v60 bytes, event 29/`v27`, and equal-command objective behavior unchanged |

Not claimed: policy authority, objective membership, turn scheduler, sanction
executor, group actor, `/v1` routes, UI panels, Alembic migrations, or new
commands/events. Research rosters and analytical cohorts never enter cognition.
Objective disasters are a separate owned channel (`docs/disasters.md`).

## Configuration

Requires `runner-config-v62`, owned `ecological_feedback` and `supply_chains`,
active `environmental_dynamics`, `ecological_resources`,
`overexploitation: {"policy_id": "overexploitation.v1"}`, `formal_rules=true`,
deterministic founder social-norm and institution-concept modes, and:

```json
{
  "policy_id": "commons-governance.v1",
  "stock_ids": ["res-water"]
}
```

`stock_ids` must be nonempty (≤8), lexically sorted, unique, typed WATER,
ecology-managed, and positively renewable. Missing modes/flags, unsorted IDs,
or adding the sibling to v61/v60 fails closed before run. Inherited medical,
measurement, and generational options already accepted on v61 remain accepted
on v62. No environment variable is added; capture is programmatic and default
off.

Default runner write remains `runner-config-v4`. Active ecology still uses
event **29** / codec **`v27`** / projector **`v2`**. Owner pending codec
`finalization-command-v7` carries `commons-governance-state-v1` (subjective
only; not a world replay codec). Alembic head stays `0017`. Commands stay 45;
observer semantics stay 73; metric catalog is unchanged by this feature.

## Owner evidence and voluntary response

- Consecutive visible stock ticks can record `decline` / `nondecline`; gaps
  reset the baseline. Net quantity never invents peer use, pressure, or renewal.
- Proposals (`rest`, then optional two-person `turn`), support/oppose, access
  claims, self-reports, and criticism travel as `cgo_v1` testimony.
- Support requires an exact prior proposal; proposers cannot support themselves.
  Contested or expired arrangements are not binding. Physical `Drink` against a
  claimed restriction remains admissible.
- Formal-rule feed prohibitions tagged `commons:<proposal-id>` are owner beliefs
  only; they are excluded from generic action-token penalties. Institution
  `PROCEDURE_RECURRENCE` needs matched self-reports of consecutive turn slots.
- Explicit deferrals and `wait_expected` considerations are recorded separately
  for research; silence is not a sanction.

## Scenarios

Off-gate paired definitions (same layout within each definition):

| Experiment ID | Layout | Arms |
| --- | --- | --- |
| `commons_governance@1` | one shared pool, four founders | `shared-pool-off` (v61), `shared-pool-on` (v62) |
| `commons_governance_two_pools@1` | two adjacent pools, two founders each | `two-pools-off` (v61), `two-pools-on` (v62) |

Builders: `experiment_commons_governance`,
`experiment_commons_governance_two_pools`. Default seeds `(34, 35, 36, 37, 38)`,
horizon 64 ticks. Managed WATER starts at baseline/max `4.0`, renewal `1.0`,
ecology floor `0.5`, recovery `0.1`, allowance `0`. Autonomous arms have no
action schedule, seeded policy, entitlement, or required social outcome.
Two-pools analytical cohorts are research labels only.

## Capture and comparison

```python
from experiments.commons_governance_capture import (
    run_with_commons_governance_capture,
)
from analysis.commons_governance_comparison import (
    compare_commons_governance_reports,
)

# Attach opt-in sink before run; seal after terminal result.
# Statuses: disabled | unavailable | partial | complete
# (v61 subjective lane is inapplicable.)
```

Report `commons-governance-report-v1` keeps separate lanes for objective
sustainability, objective joint use, subjective cooperation, and welfare
thirst, each with numerators, denominators, and coverage. Joint use is not
cooperation. Controlled mechanism proofs and autonomous nulls must not be
pooled. `compare_commons_governance_reports` pairs matched off/on replicates
within one layout only.

Research-only `SimulationRunner.export_commons_governance_ledgers()` exports
detached finalized owner evidence; it is not on API, observer, or stop paths.

## Controlled vs autonomous

Controlled tests exercise restrictions, monitoring, sanctions/criticism, access
claims, rotation, cooperation, and overuse — including contested arrangements
and physically admissible noncompliance. Autonomous zero emergence is valid and
must not fail a suite as a “missed” governance outcome.

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_*.py -q
```

## See Also

- [Overexploitation](overexploitation.md) — v61 pressure baseline
- [Ecological resources](ecological-resources.md) — v60 stock model
- [Configuration](configuration.md) — runner schema gates
- [Development](development.md) — verification commands
