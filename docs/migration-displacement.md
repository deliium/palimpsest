# Migration and Displacement

[← Borders and claims](borders-and-claims.md) · [Back to README](../README.md) · [Regions and migration →](regions-migration.md)

## What it is

A migration belief is one owner's opinion about a possible population movement
from a logical origin through an ordered logical route to a logical destination.
It is not a world object, a refugee category, a legal or social status, a
command, or an objective cause. Locations are exact `EntityId` values; there is
no grid, coordinate, polygon, area, or region-to-border conversion.

`WorldEngine` knows only locations, occupancy, and ordinary movement admission.
`WorldEngine`, perception, admission, stop selectors, memory, prompts, observer
semantics, and the presentation client never read a migration-displacement
ledger. "Migration" here means population movement and has no relation to SQL
schema migration.

## Activation

Migration-displacement cognition is available only when all of the following
hold:

- the runner writes or accepts `runner-config-v56`;
- the owned `v4_capability_flags.organizations` context is enabled;
- the owned `v3_capability_flags.multi_polity_migration` flag is enabled;
- `regions_migration.cognition_mode` is `deterministic`.

Legacy v15/v44/v55 runs, v56 without `organizations`, v56 without
`multi_polity_migration`, or regional cognition that is absent or `disabled`
produce no migration-displacement ledger. V4-14 adds no capability flag,
context, `runner-config-v57`, runner root field, or per-agent runner key. The
`organizations` context and the V3 regional-migration seam are deepened, not
replaced.

## What it controls

- owner-scoped migration intents over ordered routes of two to four logical
  locations;
- route beliefs with closed basis and status;
- cause evidence with closed cause kinds and sources;
- social-cluster beliefs with closed bases and statuses;
- integration beliefs over closed domains and statuses;
- wave observations without a shared peer ledger;
- metadata notices and content-addressed row ids.

## What it never controls

A migration belief never changes world state, admission, perception, memory,
prompts, stop selectors, observer semantics, physics, or commands. It grants no
permission, blocks no movement, proves no truth, and confers no refugee status,
asylum status, enforcement, legitimacy, wellbeing score, assimilation score,
composite score, winner, or sovereignty. Peer testimony is delivery-bound and
untrusted as truth. Analytical `displacement_like` labels are researcher-only
classifications, never a legal or social status.

## Vocabulary

| Family | Retains |
| --- | --- |
| Intent | origin, ordered route, destination, status, confidence, optional cluster |
| Route belief | locations, basis, status, observed edges |
| Cause evidence | closed cause kind, source, status, optional anchors |
| Social cluster | members, closed bases, status |
| Integration belief | destination, closed domain, closed status, evidence counts |
| Wave observation | participants, route tokens, status, same-root suppression |

Cause kinds are closed:
`resource_scarcity`, `environmental_hazard`, `conflict`, `opportunity`,
`social_network`, `institution`, `unknown`. Cause sources, cluster bases,
integration domains (`residence`, `needs`, `resource_access`,
`organization_participation`, `institution_participation`, `relationships`,
`conflict_status`, `unknown`), integration statuses (`settled`, `transient`,
`returned`, `onward`, `unknown`), and wave observation statuses are likewise
closed. Caps are locked in `migration-displacement.v1`; overflow with nothing
droppable fails closed.

## Physical movement

Physical travel remains ordinary world admission through existing `Move`,
`Transport`, and `Flee` (and related journey lifecycle events). V4-14 adds no
teleport, no new command, no new event, and no new write pair. Beliefs may bias
an owner's later command selection only through the existing cognition path;
helpers never return, construct, submit, resolve, or block an `AgentCommand`.

## `mdp_v1`

`mdp_v1` is a bounded relation group carried inside existing `Talk`, `Ask`, or
`Tell` speech. Each relation is at most 256 characters; a group has at most four
relations. The wire shape is the `mdp_v1` subject marker followed by thirteen
semantic fields (fourteen colon-separated parts in total): act, speaker ref,
subject ref, origin ref, route refs, destination ref, cause kind, source kind,
cluster ref, confidence quanta, as-of tick, evidence ref, and declared
provenance ref. Delivery proves the speaker; declared provenance is replaced by
delivery provenance and is never trusted as truth. Malformed, oversize,
speaker-mismatched, or illegal route groups are dropped. No new event, command,
observer semantic type, write pair, or wire genre exists.

## Update order

Owner-scoped ledger updates run in exactly eleven steps:
`intents`, `routes`, `causes`, `clusters`, `frames`, `anchors`,
`integrations`, `waves`, `expire`, `caps`, `digest`.

## Four analysis layers

1. **Objective movement** — committed presence and journey events; not a cause.
2. **Subjective cause** — owner cause, route, cluster, and intent beliefs.
3. **Analytical wave** — detached wave and cluster candidates, including closed
   `displacement_like` / `mixed` / `not_displacement_like` / `unknown` labels.
4. **Integration outcome** — detached destination outcome counts and coverage.

A hard leakage guard keeps these layers in separate types; a leak is a build
failure.

## Waves and no telepathy

Each owner derives its own ledger. Independent movements may form an analytical
wave only from detached evidence. Same-root testimony is suppressed once and is
never independent corroboration. There is no shared migration ledger, no peer
ledger read, and no collective telepathy.

## Displacement-like classification

Closed analytical labels (`displacement_like`, `not_displacement_like`,
`mixed`, `unknown`) rest on independent cause bases for researchers only. They
are not a refugee, asylum, forced, displaced-person, legal, or social status,
and they never feed cognition, prompts, memory, world state, or admission.

## Integration outcomes

Closed labels (`settled`, `transient`, `returned`, `onward`, `unknown`) report
counts, residence-tick buckets, domain evidence counts, and coverage only.
There is no wellbeing, assimilation, integration score, or composite.

## Caps and notices

Ledger and snapshot caps fail closed. Notices are closed metadata codes such as
`same_root_suppressed`, `truncated`, `malformed_frame`, and family capacity
codes. Notices carry no payload and grant no authority.

## Snapshot, store, API, UI, and overlays

- `migration-displacement-snapshot-v1` is canonical, bounded at 4 MiB, immutable
  after finalization, and carries a required summary plus candidate, movement,
  cause, cluster, wave, outcome, lineage, alignment, and metric-provenance rows.
- `migration-displacement-store-v1` is atomic, locked, quota-bounded, and
  idempotent.
- Six GET-only routes under `/v1/simulations/{run_id}/migration` require
  `SUBJECTIVE_DEBUG`, return `migration_displacement_disabled` when
  unconfigured, and serve only published hashed tokens and closed labels.
- The Research UI exposes four read-only sections with epistemic badges and an
  analytical caveat; it never renders refugee/asylum status labels.
- The presentation client keeps its three-class evidence model and maps four
  migration overlay kinds onto objective, subjective, and analytical classes.

## Non-goals

No objective refugee registry, asylum process, forced-migration oracle, new
event/command/write pair/migration, `/v2` route, or `observer-protocol-v2`
exists. Analysis never mints, renames, splits, merges, or dissolves `org-` or
`msoc-` identities. Docs and metrics claim no prevalence, prediction,
wellbeing, or composite score.

## See also

- [Regions and migration](regions-migration.md)
- [Borders and claims](borders-and-claims.md)
- [Organizations](organizations.md)
- [Analysis metrics](analysis-metrics.md)
