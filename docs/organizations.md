# Organizations

V4-03 adds a general, emergent organization concept built from existing V3
institutional primitives; V4-04 extends the same owner-scoped context with
socially recognized operational state; V4-05 adds owner-scoped collective
agency: proposals, positions, amendments, recognized procedures, collective
decision records, and per-actor implementation tracking. An organization is never a hard-coded class
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

## Operational state

V4-04 adds an owner-scoped **operation sidecar** keyed by the existing
`orgc-` concept id under locked policy `organization-operations.v1`. It records
what one owner believes the structure legitimately controls or does across eight
domains:

| Domain | Belief |
| --- | --- |
| `resource_control` | who may use a referenced resource |
| `storage` | where a resource is believed to be kept |
| `record_keeping` | who is believed to keep a record |
| `membership_admission` | who was believed admitted |
| `membership_departure` | who was believed to leave |
| `role_assignment` | who is believed assigned to a role |
| `procedure_action` | which recognized procedure act occurred |
| `internal_commitment` | which internal commitment exists |

**Objective possession is separate.** Custody and storage remain the existing
world fields — `holder_id`, `location_id`, `custodian_repository_id`, and
`stored_quantity`. A control belief cites those anchors; it never changes them,
and no objective `owner_id` or `ownership` field exists.

**No teleport, no executor.** No organization object returns, constructs,
submits, or resolves an `AgentCommand`, moves a resource, or performs a physical
action. Every physical effect is an ordinary command (`Give`, `Take`, `Store`,
`Inscribe`, `DepositRecord`, and the rest of the closed command set) selected and
submitted by an agent and admitted by `WorldEngine`.

**Claims, not permissions.** Admission, departure, and role assignment are
bounded claims with provenance. They never grant world permission and never
change admission rules.

**Disagreement is legal and retained.** Owners may disagree about membership,
authority, resource legitimacy, or procedures. Contradictory records keep
`stance=disputed` and a non-zero `contest_count`; both sides stay visible, and
the organization still operates. There is no consensus gate, exclusive
membership, forced self-identification, or census requirement.

**Provenance.** Owner-local decisions use `orgd-` ids and actions use `orga-`
ids, each carrying an authority basis, evidence refs, and a closed provenance
code. Publication exposes deterministic `orgop-` records without owner-local ids
or office ids.

Operations travel as bounded `org_op_v1` relations inside existing `Talk`/`Tell`
speech. No command, event, observer semantic type, write pair, or migration is
added.

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
- Owner-local operation ids: `orgd-` decisions and `orga-` actions.
- Published operation ids: `orgop-` plus 16 hex characters.

Identities are content-addressed; no `hash()`, UUID, wall clock, or mutable
counter is used.

## Collective agency

V4-05 adds a third owner-scoped sidecar keyed by the existing `orgc-` concept id
under locked policy `organization-agency.v1`. The pipeline is proposal →
discussion → support/opposition/abstention → amendment → recognized procedure →
collective decision record → individual implementation/compliance.

A collective decision is an **owner belief** about a recognized process. It is
never an organization will, a super-agent, a quorum, a majority, a binding
resolution, or a permission, and there is no global OrganizationLLM. Proposals,
positions, refusals, and implementation reports travel as bounded `org_ca_v1`
claims inside existing `Talk`/`Tell`; no command, event, observer semantic type,
or free-text payload is added.

Implementation is observed, not dispatched. Each expected actor's status comes
from real observed effects or explicit testimony:

- `implemented` / `partial` from matching real effects or explicit reports;
- `refused` only from a refusal claim or report;
- `sabotaged` only with a contrary effect plus intent evidence; otherwise
  `contrary`. Sabotage remains an owner attribution, never an objective fact;
- `unimplemented` after a closed window when the actor was observed but inactive;
- `unknown` when the actor was never observed. Silence is never refusal or
  sabotage.

A decision can be `recognized`, `contested`, `unrecognized`, or `expired`;
disagreement is retained and never blocks a decision. Detached analysis adds
`organization_collective_agency@1` and
`organization_collective_implementation@1` (metric families 146 → 148) and
joins agency rows to existing `org-` candidates without creating or changing
identity.

## Lineage

Detached lineage records `continued`, `transformed`, `split`, `merge`,
`dissolved`, and `emerged`. Edges are forward-only, monotone in ticks, and
validated acyclic. Continuation inherits an id; split children and merge results
mint new ids.

## Configuration

Enable `v4_capability_flags.organizations` on `runner-config-v56`. The flag
enables concept, operation, and collective-agency state. There is no
`runner-config-v57`, no agency mode, and no per-agent runner key. Existing V3 modes (institution
concepts, offices, institutional memory, collective decisions, structured
commitments, group formation, conventions) supply evidence; absent evidence is
valid and yields an empty typed ledger. The channel is off by default and leaves
flags-off trajectories unchanged.

## Publication and inspection

Publication is opt-in and post-completion:

- CLI (`generational`): `--organization-root`,
  `--organization-max-publications`, `--organization-max-bytes`; a storage or
  composition failure changes only the publication receipt.
- Artifact: canonical `organization-snapshot-v3` JSON, at most 4 MiB.
  `organization-snapshot-v1` and `organization-snapshot-v2` remain decodable and
  byte-verifiable; new publications are v3.
- API: six GET-only `/v1` routes under
  `/v1/simulations/{run_id}/organizations`, all requiring `SUBJECTIVE_DEBUG`:
  summary, candidate page, candidate detail, lineage page, operation page, and
  collective-agency page. The operation page filters by `domain` and
  `organization_id`; the collective-agency page filters by `recognition` and
  `organization_id`. Every paged route uses purpose-bound cursors bound to the
  publication digest.
  `PALIMPSEST_ORGANIZATION_ROOT` enables reads; when unset the routes return
  `503 organization_disabled`. `PALIMPSEST_ORGANIZATION_CURSOR_KEY` keeps cursors
  restart-stable.
- Research UI: a read-only Organizations panel renders summary, candidates,
  detail, lineage, and an operations table with a domain filter and contested
  badges without client-side derivation.

## Limits

| Limit | Value |
| --- | --- |
| Snapshot bytes | 4 MiB |
| Snapshot candidates | 2048 |
| Candidate members | 512 |
| Snapshot windows | 512 |
| Lineage edges | 16384 |
| Operations per candidate | 64 |
| Operations per snapshot | 4096 |
| Collective decisions per candidate | 64 |
| Implementations per decision | 32 |
| Collective decisions per snapshot | 4096 |
| Collective implementations per snapshot | 8192 |
| Operation records per owner ledger | 256 |
| Rows per page | 500 |

Member truncation is explicit (`provenance_code="member_list_truncated"`), never
silent. Operation truncation, unresolved anchors, and expiry are equally
explicit: `operations_truncated`, `operation_anchor_unresolved`, and
`operation_expired`.

## Non-claims

Counts describe detached candidates under stated coverage. The feature claims no
capacity, prevalence, emergence probability, predictive power, throughput, or
composite civilization score.

## See also

- [V4 architecture](v4-architecture.md)
- [Formal social rules](formal-rules.md)
- [Macro-societies](macro-societies.md)
- [Configuration](configuration.md)
- [Research API](research-api.md)
- [Research UI](research-ui.md)

## See also

- [Delegation and representation](delegation-representation.md)
- [Formal social rules](formal-rules.md)
- [Disputes](disputes.md)
- [Research API](research-api.md)
