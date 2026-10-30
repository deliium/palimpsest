# Organizations

V4-03 adds a general, emergent organization concept built from existing V3
institutional primitives. An organization is never a hard-coded class
(Government, Church, Corporation, Army, University, Guild, State, Nation,
Polity, Empire, Tribe, Ministry, Department, Treasury, Bank, Court, Police,
Party) and never an independent cognition engine.

## What an organization is

An organization is an **owner-scoped belief** one agent holds about a recurring
collective structure: who seems to belong, which roles recur, which goals are
shared, which resources and records are referenced, which procedures are
recognized, which internal commitments exist, what identity label (if any) the
structure carries, and a bounded history of how those beliefs changed. Objective
facts remain the ordinary physical effects of ordinary agent commands.

## What it is not

- Not a `WorldEngine` entity, actor, roster, treasury, resource pool, record
  store, or command source.
- Not a global organization registry and not objective role assignment.
- Not an omniscient cognition engine: a ledger reads only its owner's observation
  and prepared owner ledgers, never peer ledgers, world state, or event stores.
- Not an exclusive membership partition: overlapping and temporary membership is
  legal, and self-identification is optional.
- Not a source of permissions: duties and expected authority remain beliefs.

## The nine aspects

| Aspect | Belief type | Allowed anchor |
| --- | --- | --- |
| Perceived members | `OrganizationMemberBelief` | agent or entity ids observed by the owner |
| Roles | `OrganizationRoleBelief` | owner-local `OfficeConcept` id |
| Shared goals | `OrganizationGoalBelief` | collective project / public good / owner proposal id |
| Shared resources | `OrganizationResourceBelief` | observed repository, artifact, stored resource, shelter, territory |
| Procedures | `OrganizationProcedureBelief` | owner-local institution concept or social convention id |
| Records | `OrganizationRecordBelief` | observed artifact or repository id |
| Internal commitments | `OrganizationCommitmentBelief` | owner-local commitment interpretation id |
| Identity concepts | `OrganizationIdentityBelief` | bounded opaque label token plus stance |
| History | `OrganizationWindowRecord` / `OrganizationRevisionRecord` / `OrganizationLineageRecord` | owner-local ticks and creation evidence |

Resources and records are references, never ownership. Commitments are the
owner's interpretations, never enforced debt.

## Membership

Closed statuses: `explicit` (self-authored claim), `perceived` (participation,
role, or collective evidence), `disputed` (contradictory evidence), `unknown`
(anchor-only reference), and `former` (leave claim or expiry). Temporal scope is
`ongoing`, `temporary`, or `unknown`; a temporary claim carries an explicit
`expires_tick`. Membership may overlap across concepts; no partition exists and
no census is implied.

Explicit and disputed claims travel as bounded `org_v1` relations inside existing
`Talk`/`Tell` speech; the feature adds no command, event, observer semantic type,
or free-text payload.

## Identity

- Owner-local concept ids: `orgc-` plus 16 hex characters, minted once from the
  owner, creation tick, founding members, and first structural anchors.
- Analytical ids: `org-` plus 16 hex characters, minted from creation evidence in
  detached analysis.
- Publication lineage ids: `org-edge-` plus 16 hex characters.

Identities are content-addressed; no `hash()`, UUID, wall clock, or mutable
counter is used.

## Lineage

Detached lineage records `continued`, `transformed`, `split`, `merge`,
`dissolved`, and `emerged`. Edges are forward-only, monotone in ticks, and
validated acyclic. Continuation inherits an id; split children and merge results
mint new ids.

## Configuration

Enable `v4_capability_flags.organizations` on `runner-config-v56`. There is no
`runner-config-v57` and no per-agent runner key. Existing V3 modes (institution
concepts, offices, institutional memory, collective decisions, structured
commitments, group formation, conventions) supply evidence; absent evidence is
valid and yields an empty typed ledger. The channel is off by default and leaves
flags-off trajectories unchanged.

## Publication and inspection

Publication is opt-in and post-completion:

- CLI (`generational`): `--organization-root`,
  `--organization-max-publications`, `--organization-max-bytes`; a storage or
  composition failure changes only the publication receipt.
- Artifact: canonical `organization-snapshot-v1` JSON, at most 4 MiB.
- API: four GET-only `/v1` routes under
  `/v1/simulations/{run_id}/organizations`, all requiring `SUBJECTIVE_DEBUG`:
  summary, candidate page, candidate detail, and lineage page.
  `PALIMPSEST_ORGANIZATION_ROOT` enables reads; when unset the routes return
  `503 organization_disabled`. `PALIMPSEST_ORGANIZATION_CURSOR_KEY` keeps cursors
  restart-stable.
- Research UI: a read-only Organizations panel renders summary, candidates,
  detail, and lineage without client-side derivation.

## Limits

| Limit | Value |
| --- | --- |
| Snapshot bytes | 4 MiB |
| Snapshot candidates | 2048 |
| Candidate members | 512 |
| Snapshot windows | 512 |
| Lineage edges | 16384 |
| Rows per page | 500 |

Member truncation is explicit (`provenance_code="member_list_truncated"`), never
silent.

## Non-claims

Counts describe detached candidates under stated coverage. The feature claims no
capacity, prevalence, emergence probability, predictive power, throughput, or
composite civilization score.

## See also

- [V4 architecture](v4-architecture.md)
- [Macro-societies](macro-societies.md)
- [Configuration](configuration.md)
- [Research API](research-api.md)
- [Research UI](research-ui.md)
