# Regions and Migration

[← Migration and displacement](migration-displacement.md) · [Back to README](../README.md) · [Physical simulation →](physical-simulation.md)

## What it is

`multi_polity_migration` owns the optional location and region travel substrate
on `runner-config-v44` and later accepted runners that carry the exact
`regions_migration` sibling. It supplies immutable regions, routes, and discrete
journeys. It does not create polities, citizenship, border enforcement, dynamic
settlements, or objective migrant status.

## Authority boundary

`WorldEngine` admits ordinary movement only. Regional cognition may retain
owner-scoped destination memory and known-route beliefs rebuilt from persisted
owner evidence. Wrong, contradictory, and old testimony is subjective evidence,
never admission authority. Hidden-world changes alone cannot supply destination
knowledge. Read-only regional metrics reconstruct crossings and dwell-qualified
movements from detached events; they never add a world `is_migrant` field or
feed truth into agents.

## Activation

- Enable `v3_capability_flags.multi_polity_migration` together with the exact
  `regions_migration` object.
- Enabled writes select replay 21 / codec v19 when regional migration is the
  active channel selector; older active channels retain their prior pair.
- Observer journey semantics extend the closed set; the protocol stays
  `observer-protocol-v1`, `/v1` stays stable, and Alembic head stays `0017`.

See [Configuration](configuration.md#optional-regions-and-migration-runner-config-v44)
and [Physical simulation](physical-simulation.md#discrete-regional-journeys).

## V4-14 deepening

Owner-scoped migration-displacement beliefs deepen the `organizations` context
on `runner-config-v56` when `organizations`, `multi_polity_migration`, and
deterministic `regions_migration` cognition are all active. Physical movement
still uses existing `Move` / `Transport` / `Flee` admission only. Beliefs never
teleport, never mint refugee status, and never bind world rules. See
[Migration and displacement](migration-displacement.md).

## See also

- [Migration and displacement](migration-displacement.md)
- [Architecture](architecture.md)
- [Experiments](experiments.md)

Current catalog: 208 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
