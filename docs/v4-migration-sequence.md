# V4 Migration Sequence

V4-01 adds **no migration**. Alembic head stays `0017`, and
`alembic/versions/0018_*.py` must not exist.

`simulation.migration_plan` publishes the order in which V4 may add persistence.
A stage is intent plus an evidence trigger, not an approval. A stage may be
implemented only when its trigger is proven and its prerequisite flags are owned.
V4-01 owns none of them.

## Current state

| Item | Value |
| --- | --- |
| Alembic head | `0017` |
| Applied V4 stages | none |
| Next revision | `0018` (from `next_revision()`) |
| Future migration files | none (`future_migration_files(...) == ()`) |

## Ordered stages

| # | Stage | Migration | Trigger | Prerequisite flags | Owner | Authority impact |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `v4-m01-capability-scaffolding` | no | V4-01 flags and version acceptance only | — | `simulation` | none |
| 2 | `v4-m02-objective-network-state` | yes | proven indexed inspection need for network topology, capacity, or condition across runs | `infrastructure_networks`, `supply_chains` | `persistence` | additive objective tables/indexes only |
| 3 | `v4-m03-epidemic-host-state` | yes | proven indexed need for host/transmission history | `epidemics` | `persistence` | additive objective tables/indexes only |
| 4 | `v4-m04-ecological-state` | yes | proven indexed need for regeneration/depletion history | `ecological_feedback` | `persistence` | additive objective tables/indexes only |
| 5 | `v4-m05-disaster-state` | yes | proven indexed need for multi-location hazard history | `disasters` | `persistence` | additive objective tables/indexes only |
| 6 | `v4-m06-resilience-read-model` | yes | detached resilience queries exceed bounded in-memory aggregation | — | `persistence` | read-model indexes only; no cognition or world authority |

`societal_resilience` is analysis-only and has no runner capability flag, so
stage 6 is gated by a proven read-model need rather than a flag.

## Invariants

- Order is contiguous from 1; stage ids are unique and start with `v4-m`.
- Once a stage requires a migration, no later stage may say otherwise.
- Every prerequisite flag exists in `V4_CAPABILITY_FLAG_NAMES`.
- `current_head` must equal `ALEMBIC_HEAD_REVISION`; otherwise
  `validate_migration_sequence` raises `v4_migration_head_mismatch`. Advancing
  the head therefore requires updating the constant and this plan deliberately.
- Capability flags remain runner JSON. A migration is added only for a proven
  persistence or indexed-inspection need, never automatically per feature.

See [Persistence](persistence.md) for the event store, codecs, and checkpoints.

Current catalog: 220 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
