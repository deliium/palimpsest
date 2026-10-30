# Macro-society analytical identity

V4-02 detects and represents large society-like clusters as **analytical
candidates**. A candidate is a research label over detached evidence with an
`msoc-` identifier. It is not a nation, state, polity, civilization, government,
or organization, and no global society registry exists anywhere.

The bounded context is `macro_society_identity`, declared in
`simulation.v4_architecture` as `detached_analysis` with `analysis` as its only
owning package, no capability flag, and no write-pair reservation.

## What a macro-society is not

- Not an entity with authority, membership rights, or a treasury.
- Not a command target, event actor, or observation field.
- Not an exclusive partition: a person may belong to several candidates.
- Not a census: candidate counts are analytical counts under stated coverage.
- Not agent knowledge: nothing here feeds cognition, memory, prompts, admission,
  or stop selectors.

## Three separated layers

| Layer | Type | May contain | Must not contain |
| --- | --- | --- | --- |
| Objective population structure | `MacroSocietyObjectiveRow` | region, tick, population count, cohort/stage ids | person ids, candidate ids, statuses |
| Owner-scoped identity claims | `MacroSocietySubjectiveRow` | owner id, lane, owner-local token | candidate ids, other owners' claims, `msoc-` values |
| Analytical candidates | `MacroSocietyCandidate` | `msoc-` ids, member ids, lane support, status | objective authority, permissions, world ids |

`analysis.macro_society_layers.assert_layer_separation` fails closed on any leak.

## Evidence lanes

| Lane | Kind | Detached source |
| --- | --- | --- |
| `interaction` | edge | applied actions between an actor and a target person |
| `communication` | edge | verified `talk`/`ask`/`tell` delivery |
| `migration` | edge | journeys sharing origin and destination in one tick |
| `exchange` | edge | completed item moves between two owners |
| `institution` | token | owner-local institution/office pattern ids |
| `culture` | token | cultural trait carriers |
| `territory` | token | claims, locations, and residence regions |
| `self_identification` | token | owner-scoped group membership |
| `collective_decision` | token | owner-scoped proposal/case references |

Adapters read identifiers, weights, and opaque tokens only. They never copy
utterances, narratives, memories, embeddings, or labels. A missing lane is
reported through `lane_presence` and `PARTIAL`/`ABSENT` availability; it is never
coerced to "no society".

## Detection policy

Policy version: `macro-society-identity.v1`.

1. Token lanes form one lane cluster per shared token with at least
   `MIN_LANE_CLUSTER_MEMBERS = 4` persons.
2. Edge lanes are clustered with the pinned community algorithm
   (`greedy_modularity_communities`) over the summed per-lane graph.
3. Lane clusters from **different** lanes are unioned when their member Jaccard
   is at least `LANE_AGREEMENT_JACCARD = 0.5`. Two clusters from the same lane
   never merge.
4. Each union component with at least four members is one candidate. Persons in
   no candidate are explicit fragments.
5. A candidate with fewer than two contributing lanes, or coverage below
   `FRAGMENT_COVERAGE_MIN = 0.4`, is `fragmented`.
6. A candidate with at least `CONTESTED_MIN_MEMBERS = 2` members whose own
   self-identification cluster belongs to another candidate is `contested`.
7. Otherwise the candidate is `supported`.

Membership per person is `supported`, `partial` (present in fewer than half of
the candidate's contributing lanes), or `contested`.

## Stable analytical identity

`derive_macro_society_id` hashes canonical JSON over the creation tick, the
founding member set, and the contributing lane signature. The result is
`msoc-` plus 16 lowercase hex characters.

- An identity is minted once, at first observation, and then inherited.
- An identity survives membership churn while adjacent-window Jaccard stays at
  or above `LINEAGE_JACCARD = 0.5`.
- Absorption (containment at or above `ABSORPTION_CONTAINMENT = 0.5`) keeps the
  parent identity and is recorded as `transformed`.
- Split children and merge results always mint **new** identities.
- No mutable counter, UUID, wall-clock value, or `hash()` participates.

## Lineage

Lineage is forward-only and acyclic:

| Kind | Meaning |
| --- | --- |
| `continued` | same identity, Jaccard at or above 0.75 |
| `transformed` | same identity, lower overlap or absorption |
| `split` | one identity becomes two or more new identities |
| `merge` | two or more identities become one new identity |
| `dissolved` | an identity has no successor in the next window |
| `emerged` | a new identity has no predecessor |

`dissolved` is not death and `emerged` is not birth: they describe analytical
visibility. Continuation edges keep one identity and are not graph transitions.

## Metric families

Four detached families raise the catalog from 136 to 140:

- `macro_society_structure@1` — candidate counts, coverage, overlap, fragments.
- `macro_society_identity_alignment@1` — self-identification and territory
  support, contested candidates.
- `macro_society_lineage@1` — continuation/split/merge/dissolution/emergence.
- `macro_society_membership_dispute@1` — disputed memberships and overlap.

All four report denominators and censoring explicitly. They never present a
candidate as an objective society.

## Publication

`macro-society-snapshot-v1` is a bounded, canonical JSON snapshot with a
content-addressed `msoc-edge-` publication id. It contains windows, candidates,
lineage edges, objective population counts, coverage, and a provenance code.

Publication is opt-in and completed-run only:

- `experiments.macro_society_publication` maps analysis to the artifact.
- `persistence.macro_society_filesystem` stores it atomically under
  `<root>/<run_id>/` with one `state.json` commit point and quotas.
- `research_runner` exposes `--macro-society-root`,
  `--macro-society-max-publications`, and `--macro-society-max-bytes`. After a
  successful generational run it projects the committed events into bounded
  windows, derives communication, interaction, exchange, and migration edges,
  and leaves the other five lanes explicitly absent. A storage failure changes
  only the receipt `status`, never the scientific result. When the run has no
  usable evidence the receipt reports `status=unavailable` with a safe reason
  code rather than a false success. The receipt is written to
  `macro-society-publication-<run_id>.json` under the artifact root.

Caps: 512 members per candidate record, 4096 candidates, 16384 edges, 512
windows, 4096 objective rows, 4 MiB per snapshot.

## Read-only access

Four `GET` routes under `/v1/simulations/{run_id}/macro-societies` require the
`SUBJECTIVE_DEBUG` capability because candidates join owner-scoped evidence:

- `GET /v1/simulations/{run_id}/macro-societies`
- `GET /v1/simulations/{run_id}/macro-societies/candidates`
- `GET /v1/simulations/{run_id}/macro-societies/candidates/{macro_society_id}`
- `GET /v1/simulations/{run_id}/macro-societies/lineage`

Cursors are HMAC-signed and bound to purpose, run, publication, snapshot digest,
and filter. Responses are `no-store`. When `PALIMPSEST_MACRO_SOCIETY_ROOT` is
unset the routes return `503 macro_society_disabled`.

The Research UI adds a **Macro-societies** tab that renders published data only
and performs no client-side clustering or identity derivation.

## Non-goals

- No objective country, nation, state, polity, tribe, empire, or civilization.
- No global organization/society registry or `WorldEngine` identity.
- No exclusive membership or forced self-identification.
- No capability flag, runner schema, command, event, observer semantic type,
  `/v2` route, observer protocol change, or SQL migration.
- No capacity, prevalence, emergence-probability, or predictive claim.

## See also

- [Organizations](organizations.md): a macro-society candidate is a large society-like cluster; an organization concept is a narrower recurring collective structure held as an owner-scoped belief.
