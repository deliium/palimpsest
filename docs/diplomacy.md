# Diplomacy

[← Organizations](organizations.md) · [Back to README](../README.md) · [Delegation and representation →](delegation-representation.md)

Diplomacy is one owner's belief about recurring contact, envoys, negotiations,
and agreements with another party. It is never a polity, nation, civilization,
border, citizenship, treaty store, treaty authority, envoy registry, army, war
state, or bilateral relationship score.

## Status and ownership

V4-10 owns the declared `diplomacy` V4 context on the accepted
`runner-config-v56` seam. It is the fourth owned V4 flag alongside
`organizations`, `formal_rules`, and `legal_disputes`; the other eight V4 flags
remain unowned and fail closed. Activation is exactly
`v4_capability_flags.diplomacy = true` on `runner-config-v56`; there is no
`runner-config-v57`, runner root field, or per-agent runner key.

The registry declares `organizations` as a prerequisite for planning order, not
as a runtime gate. Diplomacy runs with `organizations` disabled; organization and
coalition anchors then stay unresolved instead of inventing a collective.

## Authority

Everything in this contract is an owner-scoped belief. `WorldEngine`,
perception, admission, stop selectors, memory, prompts, observer semantics, and
the Godot client never read a diplomacy ledger. No diplomacy helper constructs,
submits, resolves, or executes an `AgentCommand`; every physical effect remains
an ordinary admitted command. A contested agreement grants no access, moves no
item, and blocks no physically possible action.

Current envoy standing is derived from the owner's own representation ledger and
is recomputed at detection, export, composition, and read time. The status stored
on an envoy accreditation row is only the accreditation-time snapshot.

## Vocabulary

- Party kinds: `agent`, `organization`, `settlement`, `coalition`, `unknown`.
  No polity, nation, civilization, tribe, or state kind exists.
- Contact kinds: `direct_co_presence`, `mediated_message`, `written_record`,
  `third_party_report`, `journey_presence`, `unknown`.
- Envoy statuses: `claimed`, `recognized`, `contested`, `rejected`, `revoked`,
  `expired`, `superseded`, `unknown`.
- Negotiation statuses: `opened`, `ongoing`, `stalled`, `closed`, `abandoned`,
  `unknown`.
- Instrument kinds: `proposal`, `promise`, `agreement`, `dispute`,
  `shared_project`, `unknown`. No row is created with kind `agreement`; an
  agreement view is an accepted proposal.
- Instrument statuses: `proposed`, `open`, `apparently_accepted`, `rejected`,
  `withdrawn`, `unresolved`, `active`, `completed_claimed`, `superseded`,
  `expired`, `unknown`.
- Term kinds: `material_exchange`, `shared_work`, `passage`, `recognition`,
  `procedure`, `unknown`.
- Provenance: `self_declared`, `principal_declared`, `communicated`,
  `witnessed_contact`, `written_record`, `representation_belief`,
  `collective_decision`, `unknown`.
- Terminations: `party_withdrew`, `envoy_recalled`, `envoy_resigned`,
  `agreement_disputed`, `superseded`, `expired`, `unknown`.
- Misrepresentation: `mandate_unrecognized`, `scope_exceeded`,
  `contradicted_by_principal`, `contested_by_member`, `unknown`.
- Conflicts: `duplicate_envoy`, `contradictory_terms`, `conflicting_party`,
  `agreement_dispute`, `unknown`.
- Acceptance basis: `all_parties_declared`, `opener_only`, `rejected`,
  `withdrawn`, `disputed`, `expired`, `superseded`, `none`, `unknown`.

## Long-running relations

A `DiplomaticRelation` is a retained anchor with an ordered `party_ids` tuple.
The owner's self-party is always first. Relations group retained contacts,
accreditations, negotiations, instruments, declarations, misrepresentation
observations, terminations, and conflicts across ticks. The ledger stores no
valence, rank, trust value, index, or composite.

The locked `diplomacy.v1` policy bounds relations, parties, per-relation
contacts/envoys/negotiations/instruments, per-instrument declarations, anchor
references, total records, and frame characters. Deterministic truncation drops
only documented low-priority rows and never a self-party, a relation party set,
or an active accepted agreement. When nothing droppable remains, the update fails
with `diplomacy_capacity_reached`.

Expiry is exclusive: a row with `end_tick` is expired when `tick >= end_tick`.
Expiry, withdrawal, recall, resignation, dispute, and supersession append a
retained `DiplomaticTermination` row. No row is deleted, and two recognized
agreements for one pair may coexist.

## Envoys and partial authority

An envoy is an accreditation belief, not authority. Standing is derived from the
owner's representation ledger:

- no mandate reference: `claimed`;
- missing or foreign mandate: `unknown`;
- a current mandate status maps directly to `recognized`, `contested`,
  `rejected`, `revoked`, `expired`, or `superseded`;
- a revoked, expired, or superseded mandate after accreditation is visible at the
  next read; the stored accreditation status is never treated as current.

A self-claim alone stays `claimed`. An authority-bearing declaration by an envoy
without recognized standing retains a `mandate_unrecognized` observation.

Scope coverage is one closed matrix over the mandate's `scope_kind` and
`duration_kind`. `single_act` and `occasion` never cover a long-running
agreement, promise, or shared project; `until_tick` and `until_revoked` may. A
named scope subject must equal the instrument subject. A mismatch retains a
`scope_exceeded` observation and never completes party acceptance.

Misrepresentation is observation, not adjudication. The four kinds above are
retained; there is no lie detector, truth field, guilt, bad faith, liability, or
punishment.

## Instruments

Proposals, promises, disputes, and shared projects share one immutable
instrument shape. A later acceptance of a proposal by every party produces an
**agreement view** over the same instrument id; no second row is created.
`is_agreement_view` is the only agreement predicate.

`apparently_accepted` requires every party in the instrument's ordered party set
to have its own active acceptance declaration, with at least two distinct
parties. A principal declaration counts directly. An envoy declaration counts
only with recognized standing and covering scope. An envoy's say-so never binds
a party, and `apparently_accepted` still binds nobody.

Promises reference commitments as opaque anchors and are never enforced or
objectively verified. Disputes link the owner's dispute and evidence rows;
shared projects link collective-project or organization-agency anchors. These
are read-only references. A completion claim is a retained `completed_claimed`
observation, never an objective check.

## Speech

Diplomacy claims travel as one bounded `dip_v1` relation inside existing
`Talk`/`Ask`/`Tell` speech. The 15 fields are `act`, `relation_ref`,
`party_kind`, `party_ref`, `envoy_ref`, `mandate_ref`, `negotiation_ref`,
`instrument_ref`, `instrument_kind`, `term_kind`, `topic_subject`,
`declaration_ref`, `end_tick`, `provenance`, and `revision`. Frames are bounded
at 320 characters.

A verified speaker must equal the claimed `envoy_ref`; mismatched frames are
dropped with a warning and never attributed to another party. The receiver
assigns provenance from the delivery context: `communicated` for peer speech,
`self_declared` for the owner's own utterance. A peer-supplied
`principal_declared`, `witnessed_contact`, or `written_record` provenance is
ignored, and a peer-supplied `mandate_ref` is only a claim that must resolve in
the owner's own representation ledger.

Repetition is idempotent. Derived misrepresentation, termination, and conflict
rows are content-addressed and deduplicated.

## Detached analysis

Detached `analysis.diplomacy_*` harvests exported ledgers into token-only rows and
derives exactly six independent lanes: agent relationships, trade, conflict,
agreements, narratives, and institutional interaction. The trade lane counts
`ExchangeCompleted` only; one-way `Given` transfers are never trade.

Candidates use stable `dip-` identities and join read-only to existing `org-` and
`msoc-` identities through owner-safe `orgc-` and region anchors. Analysis never
mints, renames, splits, merges, or dissolves an organization or macro-society
identity. Objective counts, owner-token rows, and analytical candidates stay in
three separated layers with a hard leakage guard.

Envoy alignment (`consistent`, `unresolved`, `inconsistent`,
`not_applicable`) is researcher-only. It never reaches cognition, prompts,
memory, world state, stop selectors, or observer semantics.

## Metrics

Four appended families raise the catalog from 160 to 164:

- `diplomatic_contact_structure@1` — retained relations, parties, contacts,
  envoys, and negotiations with closed-kind histograms and explicit coverage.
- `diplomatic_instrument_outcomes@1` — instrument and declaration counts,
  agreement views, rejection, withdrawal, dispute, supersession,
  misrepresentation, and a quantized acceptance ratio.
- `diplomatic_envoy_alignment@1` — researcher-only consistent/unresolved/
  inconsistent/not-applicable counts and explicit ratios.
- `inter_society_relation_lanes@1` — per-lane pair counts with an explicit lane
  histogram and coverage ratio. It has no aggregate or composite key.

No family exposes `score`, `relation_score`, `trust`, `rank`, `valence`, `index`,
`composite`, `mean_score`, or `overall_relation`.

## Publication and API

`diplomacy-snapshot-v1` is canonical, bounded, content-addressed, and immutable
after publication. `diplomacy-store-v1` publishes it atomically with cumulative
per-run publication and byte quotas; publication is opt-in, post-completion, and
isolated from scientific status.

Six GET-only routes under `/v1/simulations/{run_id}/diplomacy` require the
`SUBJECTIVE_DEBUG` capability:

| Route | Result |
| --- | --- |
| `GET /diplomacy` | summary |
| `GET /diplomacy/relations` | paged relations |
| `GET /diplomacy/relations/{relation_id}` | relation detail including retained terminations |
| `GET /diplomacy/instruments` | paged instruments |
| `GET /diplomacy/instruments/{instrument_id}` | instrument detail |
| `GET /diplomacy/lineage` | paged lineage |

An unconfigured root returns 503 `diplomacy_disabled`. Unknown published ids
return 404, cursor mismatch 400, and cursor expiry 410. Cursors bind run,
publication, digest, purpose, and filters. Response rows expose only
content-addressed ids, hashed tokens, and owner-safe `orgc-`/region anchors.

## Research UI

The Research UI adds a read-only Diplomacy panel. It renders server-provided
counts, relation rows, parties, envoys, instruments, declarations,
misrepresentation observations, terminations, conflicts, and lineage. It
displays envoy standing as a status label, never as authority or legitimacy. It
never aggregates lanes, ranks parties, invents a score, or decides which
agreement is real.

## Composition and non-goals

Representation, collective decisions, structured commitments, offices, formal
rules, disputes, and evidence are consulted read-only. V4-10 adds no command,
event, observer semantic type, write pair, `/v2` route, or SQL migration. It does
not implement organized conflict, infrastructure, supply chains, markets,
credit, science, epidemics, ecological feedback, disasters, resilience, or
macro-society behavior. Diplomacy is a belief; a later plan that lets it bias
behavior must be separately owned.
