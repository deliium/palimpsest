# Borders and Claims

[← Architecture](architecture.md) · [Experiments](experiments.md) · [Back to README](../README.md)

## What it is

A border belief is one owner's opinion that a sorted set of logical `EntityId`
locations belongs to it. A boundary is the set of observed adjacency pairs with
exactly one endpoint inside that set. There is no grid, coordinate, polygon,
area, country, objective border object, territory registry, or `CountryOwner`
field anywhere in the system.

`WorldEngine` knows only locations and occupancy. `WorldEngine`, perception,
admission, stop selectors, memory, prompts, observer semantics, and the
presentation client never read a border ledger.

## Activation

Border cognition is available only when all of the following hold:

- the runner writes `runner-config-v56`;
- the owned `v4_capability_flags.organizations` context is enabled;
- the agent's `territorial_claim_mode` is `DETERMINISTIC`.

Legacy v15/v44/v55 runs without `organizations` produce no border ledger. V4-13
adds no capability flag, context, `runner-config-v57`, runner root field, or
per-agent runner key. The `organizations` context is deepened, not replaced.

## What it controls

- owner-scoped domain claims over 1-8 logical locations;
- boundary recognitions over observed adjacency edges;
- access expectations in the closed modes `open`, `restricted`,
  `permission_expected`, and `unknown`;
- border agreements with closed acts, provisions, and statuses;
- retained border disputes over contested locations;
- metadata notices and content-addressed row ids.

## What it never controls

A border belief never changes world state, admission, perception, memory,
prompts, stop selectors, observer semantics, physics, or commands. It grants no
access, blocks no command, creates no obligation, proves no truth, and confers
no sovereignty, legitimacy, ownership, enforcement, winner, border score, or composite.
Overlapping claims are legal and retained. A dispute records contested
locations without a verdict or forced boundary.

## Location sets and boundaries

Locations are logical ids, not grid cells. A domain holds 1-8 sorted unique
locations. Boundary edges are canonical observed adjacency pairs; a location
with no observed edge is explicitly `unresolved` and is never invented. Region
membership is never converted into a border.

## The five row families

| Family | Retains |
| --- | --- |
| Domain claim | locations, observed edges, optional anchor, status, strength, evidence |
| Boundary recognition | domain, edge subset, basis (`own_claim`, `direct_observation`, `testimony`, `agreement`, `unresolved`), status |
| Access expectation | domain, subject kind/ref, closed mode, status |
| Border agreement | domain, counterparty, provisions, status, recognition belief, effective/expiry ticks |
| Border dispute | domain, counterparty, contested locations, status |

Caps are locked in `borders-claims.v1`; active domains and active agreements are
never silently dropped. Overflow with nothing droppable fails closed.

## `bdr_v1`

`bdr_v1` is a bounded relation group carried inside existing `Talk`, `Ask`, or
`Tell` speech. Each relation is at most 256 characters; a group has at most eight
relations and one to eight locations. The wire shape is the `bdr_v1` subject
marker followed by ten relation fields (eleven colon-separated components in
total): act, domain id, party kind, party ref, index, count, location ref,
expiry tick, access mode, and provision. The speaker is verified by delivery, the
declared party is untrusted, and malformed, oversize, speaker-mismatched,
duplicate-index, or non-contiguous groups are dropped. No new event, command,
observer semantic type, write pair, or wire genre exists.

## Four analysis layers

1. **Physical control** — derived counts and closed classes from committed
   presence, use, hostile, and assistance events. Not ownership.
2. **Subjective claim** — owner claims, recognitions, access expectations, and
   disputes from exported ledgers.
3. **Agreement** — owner agreement beliefs. Binding on nobody.
4. **Analytical control pattern** — closed labels such as `claim_aligned`,
   `claim_overlap`, `agreement_aligned`, `agreement_contested`, `contested`,
   `physical_unclaimed`, and `unknown`, with counts and denominators.

A hard leakage guard keeps these layers in separate types; a leak is a build
failure.

## Snapshot, store, API, UI, and overlays

- `borders-snapshot-v1` is canonical, bounded at 4 MiB, immutable after
  finalization, and carries a required summary plus candidate, claim,
  recognition, access, agreement, dispute, physical, pattern, overlap, lineage,
  alignment, and metric-provenance rows.
- `borders-store-v1` is atomic, locked, quota-bounded, and idempotent.
- Six GET-only routes under `/v1/simulations/{run_id}/borders` require
  `SUBJECTIVE_DEBUG`, return `borders_disabled` when unconfigured, and serve only
  published hashed tokens and closed labels.
- The Research UI exposes four read-only sections with epistemic badges.
- The presentation client keeps its three-class evidence model and maps four
  border overlay kinds onto objective, subjective, and analytical classes.
  Agreement is a distinct subjective overlay, not a fourth evidence class.

## Non-goals

No objective `CountryOwner`, `world.at_war`, border enforcement, access control,
grid, polygon, territory registry, `Border` class, new event/command/write
pair/migration, `/v2` route, or `observer-protocol-v2` exists. Analysis never
mints, renames, splits, merges, or dissolves `org-` or `msoc-` identities.

Current catalog: 212 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
