# Phase 2: Owner-Scoped Diplomacy Beliefs

Plan: [index.md](index.md)
Tasks: 4-11
Depends on: Phase 1 / Task 3

## Objective

Implement one owner's long-running diplomacy belief ledger: retained relation
records, parties, contact episodes, accredited envoys, negotiations, proposals, promises,
agreements, disputes, shared projects, declarations, retained misrepresentation
beliefs, conflicts, termination, expiry, and supersession. Everything is an
owner belief carried in existing speech; nothing grants authority or moves a
resource.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/agents/cognition/delegation_representation.py` | `RepresentationLedger` invariants; `RepresentationMandate` 250-420; `apply_representation_update`; `require_owner_representation`; `representation_ledger_digest` | Owner-scoped ledger, ordering, derived status, and digest precedent |
| `src/agents/cognition/offices.py` | `OfficeConceptLedger` 998; support/opposition independence 579-667, 1934-1983 | Same-root retellings are not independent support |
| `src/agents/cognition/collective_decisions.py` | proposal windows 705-719; one-hop delegation 152-160 | Decisions remain proposal-scoped; diplomacy composes read-only |
| `src/agents/cognition/structured_commitments.py` | `StructuredCommitmentLedger` 206 | Promise anchors are read-only references, never enforcement |
| `src/agents/cognition/legal_disputes.py` | `DisputeLedger` 1751; resolution states; `apparently_accepted` rule | Agreements use the same "every named party declares" discipline |
| `src/agents/cognition/evidence_testimony.py` | `EvidenceLedger` 1146 | Owner-local evidence anchors |
| `src/agents/cognition/evidence_testimony_communication.py` | frame verification 491-507 | Speaker/party verification precedent |
| `src/agents/cognition/legal_dispute_communication.py` | `DisputeFrame` 315; `encode_dispute_frame` 457; `parse_dispute_frame` 501; `dispute_frame_party_matches` 622 | `dip_v1` frame shape to mirror |
| `src/agents/cognition/delegation_representation_communication.py` | `REPRESENTATION_FRAME_*` 57-62; `representation_frame_party_matches`; `representation_frames_from_observation` | Bounded frame and speaker verification precedent |
| `src/world/observations.py` | `ObservedOccurrence` 973-1019; `ObservedCommunication` 1020 | Contact and speech inputs available to cognition |
| `src/world/_perception.py` | `ContactRecorded` public facts 1119-1126 (`contact_location_id`, `contact_participant_ids`, `contact_present_ids`) | Objective co-presence anchor for the contact lane |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot.representation` 765; `CognitiveLoopProposal` 3989; `CognitiveLoopResult` 4317 | Carry-slot pattern |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint.representation` 620; validation 815 | Checkpoint pattern |
| `src/simulation/agent_runtime.py` | `_representation`/`_commit_representation` 1464; restore 3502 | Runtime carry pattern |
| `src/simulation/perception.py` | `representation` 163, 377 | Perspective plumbing pattern |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/diplomacy.py` | modify | Records, ledger, relations, terminations, ids, validators, recognition, conflicts, limits, digest |
| `src/agents/cognition/diplomacy_communication.py` | create | `dip_v1` frame encode/parse/verify and observation extraction |
| `src/agents/cognition/loop.py` | modify | Prepare, record, and carry the ledger |
| `src/agents/cognition/contracts.py` | modify | `Perspective.diplomacy` |
| `src/agents/cognition/models.py` | modify | Snapshot/proposal/result carry |
| `src/simulation/perception.py` | modify | Perspective plumbing |
| `src/simulation/agent_runtime.py` | modify | Runtime carry/restore |
| `src/simulation/run_control.py` | modify | Checkpoint carry |
| `src/simulation/runner.py` | modify | `export_diplomacy_ledgers` and result population |
| `src/simulation/runner_models.py` | modify | `SimulationRunnerResult.diplomacy_ledgers` and ordered validation |
| `src/agents/cognition/__init__.py` | modify | Export new public contracts |
| `tests/unit/test_diplomacy_records.py` | create | Record and ledger invariants |
| `tests/unit/test_diplomacy_communication.py` | create | Frame tests |
| `tests/unit/test_diplomacy_collection.py` | create | Contact/envoy/negotiation tests |
| `tests/unit/test_diplomacy_instruments.py` | create | Instrument collection tests |
| `tests/unit/test_diplomacy_acceptance.py` | create | Envoy standing and agreement tests |
| `tests/unit/test_diplomacy_termination.py` | create | Termination/supersession tests |
| `tests/unit/test_diplomacy_runtime.py` | create | Carry and checkpoint tests |
| `tests/unit/test_diplomacy_determinism.py` | create | Determinism tests |

## Task 4: Define relation, party, contact, envoy, and negotiation records

### Intent

A long-running relation is an identity anchor plus episodes, not a score. Parties
are owner-local anchors with a closed kind; contacts and negotiations are
immutable rows; envoys are accreditations whose standing is derived, never
asserted.

### Implementation Steps

1. Add `DiplomaticRelation` with `relation_id`, ordered `party_ids` (the owner
   self-party first, then the counterparty), `opened_tick`, `last_tick`,
   `provenance`. This is the missing anchor every other row references.
2. Add `DiplomaticParty` with `party_id`, `kind`, `anchor_ref`, `resolution`,
   `first_seen_tick`, `provenance`. Every relation includes one owner self-party
   (`anchor_ref=owner_id`, `kind=agent`, `provenance=SELF_DECLARED`) so the
   owner's own declarations have a valid `declarer_party_id`.
3. Add `DiplomaticContact` with `contact_id`, `relation_id`, `tick`,
   `contact_kind`, `location_anchor`, `participant_count`, `provenance`,
   `source_ref`.
4. Add `DiplomaticEnvoy` with `envoy_id`, `relation_id`, `party_id`, `envoy_ref`,
   `mandate_ref`, `status`, `accredited_tick`, `end_tick`, `revision`,
   `provenance`. `party_id` names the party the envoy is believed to represent;
   `status` is the accreditation-time snapshot, never the current standing.
5. Add `DiplomaticNegotiation` with `negotiation_id`, `relation_id`,
   `topic_subject`, `status`, `opened_tick`, `last_tick`, `envoy_refs`,
   `term_kind`, `provenance`, `revision`.
6. Add `DiplomaticLedger` with ordered tuples `relations`, `parties`, `contacts`,
   `envoys`, `negotiations` (Task 5 extends it with instruments, declarations,
   misrepresentations, terminations, conflicts) and `owner_id`, `tick`,
   `policy_version`, `revision`.
7. `DiplomaticLedger.__post_init__` must enforce: type and owner equality across
   rows; tuple ordering by `(tick, id)`; unique ids; unique
   `(relation_id, party_id)`; every `relation_id`/`party_id`/`envoy_ref`/
   `mandate_ref` resolves inside the ledger or the owner sidecars; every
   relation's `party_ids` resolve and include the self-party; policy version
   exact; no forbidden field names; no value that is a score, valence, rank, or
   aggregate.
8. Add content-addressed id minters for relation, party, contact, envoy, and
   negotiation using `DIPLOMACY_SEPARATOR`, SHA-256, and the 16-hex suffix;
   ids must be stable for identical inputs and differ across owner/tick inputs.
9. Add `empty_diplomacy_ledger(owner_id, *, tick)` and
   `require_owner_diplomacy(value, owner_id)`.
10. Add `diplomacy_ledger_digest(ledger)` over canonical JSON with sorted keys.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class DiplomaticRelation:
    relation_id: str
    party_ids: tuple[str, ...]          # self-party first, then counterparty
    opened_tick: int
    last_tick: int
    provenance: DiplomaticProvenance

@dataclass(frozen=True, slots=True)
class DiplomaticParty:
    party_id: str
    kind: DiplomaticPartyKind
    anchor_ref: str | None
    resolution: DiplomaticPartyResolution
    first_seen_tick: int
    provenance: DiplomaticProvenance

@dataclass(frozen=True, slots=True)
class DiplomaticContact:
    contact_id: str
    relation_id: str
    tick: int
    contact_kind: DiplomaticContactKind
    location_anchor: str | None
    participant_count: int
    provenance: DiplomaticProvenance
    source_ref: str | None

@dataclass(frozen=True, slots=True)
class DiplomaticEnvoy:
    envoy_id: str
    relation_id: str
    party_id: str
    envoy_ref: str
    mandate_ref: str | None
    status: DiplomaticEnvoyStatus     # accreditation-time snapshot only
    accredited_tick: int
    end_tick: int | None
    revision: int
    provenance: DiplomaticProvenance

@dataclass(frozen=True, slots=True)
class DiplomaticNegotiation:
    negotiation_id: str
    relation_id: str
    topic_subject: str
    status: DiplomaticNegotiationStatus
    opened_tick: int
    last_tick: int
    envoy_refs: tuple[str, ...]
    term_kind: DiplomaticTermKind
    provenance: DiplomaticProvenance
    revision: int
```

- `relation_id` is derived from `(owner_id, sorted party anchor keys)`; two
  owners never share an id, and an unresolved counterparty still produces a
  stable id.
- `party_id` is derived from `(owner_id, kind, anchor_ref or "none")`; the owner
  self-party uses the owner id and `kind=agent`.
- `participant_count` is bounded by the observed contact fact and is never
  inferred from silence.
- `DiplomaticEnvoy.status` is never read as current standing after
  `accredited_tick`; Task 9 recomputes it.
- No row stores a relationship score, trust value, severity, or rank.

### Requirement Evidence (when reconciliation applies)

- Original Request: "diplomatic contact", "envoys", "negotiations"; "Do not
  create magical bilateral relationship scores".
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts":
  owner-scoped beliefs, no shared mutable store.

### Error Handling and Logging

- Codes: `diplomacy_owner_mismatch`, `diplomacy_foreign_reference`,
  `diplomacy_duplicate_id`, `diplomacy_unordered_rows`,
  `diplomacy_invalid_participant_count`, `diplomacy_self_party_missing`,
  `diplomacy_party_set_invalid`.
- `DEBUG diplomacy_relation_recorded relations=%s parties=%s contacts=%s
  envoys=%s negotiations=%s`; never log ids, anchors, refs, or subjects.

### Tests

- `tests/unit/test_diplomacy_records.py`: relation rows carry ordered party sets
  with a self-party; every `relation_id`/`party_id`/`envoy_ref` resolves;
  ordering, duplicate rejection, foreign reference rejection, owner mismatch,
  policy mismatch, determinism of every id minter, anchor-less party stability,
  forbidden field/score scan, digest stability under row permutation, envoy
  `party_id` validation, and negotiation `revision` monotonicity.

### Acceptance Criteria

- A ledger can be constructed from valid rows only; every invariant fails with a
  safe code.
- No score-like field exists.

### Verification

- `uv run pytest tests/unit/test_diplomacy_records.py -q`
- Expected: pass.

## Task 5: Define instrument, declaration, misrepresentation, termination, and conflict records

### Intent

Proposals, promises, agreements, disputes, and shared projects share one
instrument shape with a closed kind, plus immutable party declarations. This is
what lets "apparently accepted" require every party's own declaration without
creating a treaty or a court.

### Implementation Steps

1. Add `DiplomaticInstrument` with `instrument_id`, `relation_id`, ordered
   `party_ids` (inherited from the relation), `kind`, `term_kind`,
   `topic_subject`, `opener_envoy_ref`, `opened_tick`, `end_tick`, `anchor_refs`,
   `revision`, `provenance`.
2. Add `DiplomaticDeclaration` with `declaration_id`, `instrument_id`,
   `declarer_party_id`, `envoy_ref`, `act` (`DiplomaticDeclarationAct`:
   `propose`, `accept`, `reject`, `withdraw`, `promise`, `dispute`,
   `shared_project`, `report`), `declared_tick`, `provenance`,
   `independence_ref`, `revision`.
3. Add `DiplomaticMisrepresentation` with `misrepresentation_id`,
   `instrument_id`, `kind`, `observed_tick`, `envoy_ref`, `declarer_party_id`,
   `provenance`.
4. Add `DiplomaticTermination` with `termination_id`, `target_kind`
   (`instrument`, `envoy`, `relation`), `target_ref`, `kind`, `tick`,
   `provenance`.
5. Add `DiplomaticConflict` with `conflict_id`, `relation_id`, `kind`,
   `observed_tick`, `instrument_refs`, `party_refs`, `provenance`.
6. Extend `DiplomaticLedger` with `instruments`, `declarations`,
   `misrepresentations`, `terminations`, `conflicts` and extend validation:
   declaration references resolve; instrument `party_ids` equal the relation
   `party_ids`; one active declaration per `(instrument, party, act, revision)`;
   `anchor_refs` and `independence_ref` are opaque tokens only; termination
   targets resolve; conflict parties resolve.
7. Add content-addressed minters for instrument, declaration, misrepresentation,
   termination, and conflict.
8. Define `DiplomaticAcceptanceBasis`: `all_parties_declared`, `opener_only`,
   `rejected`, `withdrawn`, `disputed`, `expired`, `superseded`, `none`,
   `unknown` — a diagnostic basis only, never a legitimacy verdict.
9. Define `DiplomaticStandingSummary` (read-only projection for later plans):
   relation count, party/resolution counts, envoy status counts, instrument
   status counts, termination counts, and last activity tick. It carries no
   score and does not duplicate V4-09's `representation_standing_summary`; for
   principal standing, consume that function read-only.

### Required Interfaces and Contracts

```python
class DiplomaticDeclarationAct(StrEnum):
    PROPOSE = "propose"
    ACCEPT = "accept"
    REJECT = "reject"
    WITHDRAW = "withdraw"
    PROMISE = "promise"
    DISPUTE = "dispute"
    SHARED_PROJECT = "shared_project"
    REPORT = "report"

class DiplomaticAcceptanceBasis(StrEnum):
    ALL_PARTIES_DECLARED = "all_parties_declared"
    OPENER_ONLY = "opener_only"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    DISPUTED = "disputed"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    NONE = "none"
    UNKNOWN = "unknown"

@dataclass(frozen=True, slots=True)
class DiplomaticTermination:
    termination_id: str
    target_kind: str          # instrument | envoy | relation
    target_ref: str
    kind: DiplomaticTerminationKind
    tick: int
    provenance: DiplomaticProvenance
```

- `DiplomaticInstrument.kind` determines the permitted declaration acts:
  proposal/agreement use `propose`/`accept`/`reject`/`withdraw`/`report`;
  promise uses `promise`/`withdraw`/`report`; dispute uses
  `dispute`/`withdraw`/`report`; shared project uses
  `shared_project`/`accept`/`withdraw`/`report`. Invalid pairs fail with
  `diplomacy_declaration_kind_mismatch`.
- `anchor_refs` may cite commitments, collective projects, organization-agency
  decisions, disputes, or evidence as opaque tokens. They are references, not
  lookups that grant authority.
- A single actor cannot satisfy two parties: declarations deduplicate by
  `declarer_party_id`.

### Requirement Evidence (when reconciliation applies)

- Original Request: "proposals", "promises", "agreements", "disputes", "shared
  projects".
- `src/agents/cognition/legal_disputes.py`: `apparently_accepted` requires every
  named party and still binds nobody.
- `.ai-factory/ARCHITECTURE.md` V3 seams: commitments are speech, not enforced
  debt; collective projects are not leadership or automatic access.

### Error Handling and Logging

- Codes: `diplomacy_declaration_kind_mismatch`,
  `diplomacy_duplicate_declaration`, `diplomacy_unknown_anchor`,
  `diplomacy_foreign_reference`, `diplomacy_instrument_party_mismatch`,
  `diplomacy_unknown_termination_target`.
- `DEBUG diplomacy_instruments instruments=%s declarations=%s terminations=%s`;
  never log anchors, subjects, or declarer identities.

### Tests

- `tests/unit/test_diplomacy_records.py` (extended): kind/act matrix accepted and
  rejected pairs; duplicate declaration rejection; anchor token bounds; single
  actor cannot appear as two parties; instrument `party_ids` match the relation;
  termination targets resolve and cannot be invented; standing summary counts
  equal row counts and contain no score key; `DiplomaticStandingSummary` does
  not duplicate a V4-09 principal summary.

### Acceptance Criteria

- All five instrument kinds, eight declaration acts, and six termination kinds
  are representable and retained.
- Invalid kind/act combinations fail closed.

### Verification

- `uv run pytest tests/unit/test_diplomacy_records.py -q`
- Expected: pass.

## Task 6: Add bounded dip_v1 diplomacy speech frames

### Intent

Diplomacy claims must travel through existing `Talk`/`Ask`/`Tell` as one bounded
relation, with the verified speaker checked against the claimed envoy. Forged or
mismatched frames are dropped with a notice, never recorded as another party's
claim.

### Implementation Steps

1. Create `src/agents/cognition/diplomacy_communication.py` importing
   `CommunicationRelation`, `CommunicationSourceBasis`, and `origin_utterance`
   from `world.communications`.
2. Define `DIPLOMACY_FRAME_VERSION = "dip_v1"`,
   `DIPLOMACY_FRAME_SUBJECT = "dip_v1"`, `DIPLOMACY_FRAME_MAX_CHARS = 320`,
   `DIPLOMACY_FRAME_FIELD_COUNT = 15`.
3. Define `DiplomaticAct` with twelve members: `dip_contact`, `dip_accredit`,
   `dip_recall`, `dip_open_negotiation`, `dip_propose`, `dip_promise`,
   `dip_accept`, `dip_reject`, `dip_withdraw`, `dip_dispute`,
   `dip_shared_project`, `dip_report`, plus the predicate mapping.
4. Define the 15 frame keys: `act`, `relation_ref`, `party_kind`, `party_ref`,
   `envoy_ref`, `mandate_ref`, `negotiation_ref`, `instrument_ref`,
   `instrument_kind`, `term_kind`, `topic_subject`, `declaration_ref`,
   `end_tick`, `provenance`, `revision`. `topic_subject` is required for
   `dip_open_negotiation`, `dip_propose`, `dip_promise`, `dip_dispute`, and
   `dip_shared_project`; it is rejected for acts that do not open or describe a
   subject.
5. Implement `encode_diplomacy_frame`, `parse_diplomacy_frame`,
   `diplomacy_frame_relation`, `parse_diplomacy_frame_relation`,
   `diplomacy_frame_party_matches(frame, verified_speaker)`,
   `diplomacy_frames_from_observation(observation, *, owner_id)`, and
   `diplomacy_communicate_utterance(command, frame, *, max_chars=320)`.
6. `diplomacy_frame_party_matches` returns true only when `envoy_ref` equals the
   verified speaker. A frame may name a different `party_ref`; that is a claim to
   represent, not proof, and never a principal acceptance.
7. `provenance` is assigned by the receiver from the verified delivery context
   (`COMMUNICATED` for a peer frame, `SELF_DECLARED` for the owner's own
   utterance); a peer-supplied `provenance` of `PRINCIPAL_DECLARED`,
   `WITNESSED_CONTACT`, or `WRITTEN_RECORD` is ignored. A peer-supplied
   `mandate_ref` is only a claim and must resolve in the owner's own
   representation ledger before it can affect standing.
8. Parsing is fail-closed: unknown keys, wrong field count, over-length text,
   invalid tokens, an invalid `topic_subject`, or unknown enum values return
   `None` after a `DEBUG diplomacy_frame_dropped reason=invalid` line. Never log
   the body.
9. `diplomacy_frames_from_observation` reads only `ObservedCommunication`
   relations whose subject is `dip_v1`; it never reads another owner's ledger.
10. Add `diplomacy_contact_anchors_from_observation` that maps
    `ObservedOccurrence.kind == "contact_recorded"` public facts to bounded
    contact anchors (`location_anchor`, `participant_count`), ignoring malformed
    facts with `diplomacy_contact_dropped`.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class DiplomacyFrame:
    act: DiplomaticAct
    relation_ref: str | None = None
    party_kind: DiplomaticPartyKind | None = None
    party_ref: str | None = None
    envoy_ref: str | None = None
    mandate_ref: str | None = None
    negotiation_ref: str | None = None
    instrument_ref: str | None = None
    instrument_kind: DiplomaticInstrumentKind | None = None
    term_kind: DiplomaticTermKind | None = None
    topic_subject: str | None = None
    declaration_ref: str | None = None
    end_tick: int | None = None
    provenance: DiplomaticProvenance | None = None
    revision: int = 0
    actor_ref: str | None = None
```

- Attach at most one relation per utterance; `Talk`/`Ask`/`Tell` only.
- The frame is self-authored: `actor_ref` is set from the verified speaker and
  must equal `envoy_ref` when that field is present.
- No frame field may carry free text beyond 32-character subjects.

### Requirement Evidence (when reconciliation applies)

- Original Request: "Representatives may misrepresent their society or lack full
  authority".
- `src/agents/cognition/delegation_representation_communication.py` 57-62,
  `representation_frame_party_matches`: verified-speaker discipline.
- `.ai-factory/ARCHITECTURE.md`: `Talk`/`Ask`/`Tell` prove delivery only.

### Error Handling and Logging

- `WARN diplomacy_party_mismatch` (count only) when a frame's `envoy_ref` is not
  the verified speaker; the frame is dropped.
- `DEBUG diplomacy_frame_dropped reason=invalid|oversize|unknown_subject`; never
  log the frame text.
- `DEBUG diplomacy_contact_dropped reason=malformed`.

### Tests

- `tests/unit/test_diplomacy_communication.py`: round-trip for all twelve acts;
  field-count and length caps; `topic_subject` required for negotiation/
  instrument-opening acts and rejected elsewhere; unknown key rejected;
  predicate/act bijection; speaker mismatch dropped; an envoy frame claiming
  another party is retained only as a claim; a peer-supplied
  `PRINCIPAL_DECLARED`/`WITNESSED_CONTACT` provenance is overwritten with
  `COMMUNICATED`; a peer-supplied `mandate_ref` never affects standing; contact
  anchors parsed from public facts; malformed contacts dropped; no log call
  receives the frame body (assert via captured records that no foreign token
  appears).

### Acceptance Criteria

- All diplomacy claims are expressible in one bounded relation.
- A speaker cannot pass off a mandate or declaration as another party's.

### Verification

- `uv run pytest tests/unit/test_diplomacy_communication.py -q`
- Expected: pass.

## Task 7: Collect contacts, envoys, and negotiations

### Intent

This task turns owner-visible evidence into retained relation, contact, envoy,
and negotiation rows. It is the first behavior step: still no agreement, no
authority, and no command.

### Implementation Steps

1. Implement `apply_diplomacy_update(*, owner_id, tick, observation, prior,
   frames=(), representation=None, organization_concepts=None,
   collective_decisions=None, structured_commitments=None, disputes=None,
   evidence=None, policy=None) -> DiplomacyLedger`.
2. Validate `prior` ownership and policy; derive `contact anchors` from the
   observation (Task 6), then merge frames.
3. Party resolution reuses the V4-09 helpers instead of re-implementing them:
   `resolve_representation_principal` (1506-1525) for `agent`/organization/
   coalition/settlement anchors and `_observation_region_anchors` (1528-1548)
   for settlement regions. An `agent` party is the other observed participant or
   declared counterparty token; `organization` and `coalition` resolve only
   against the owner's own `orgc-` concepts passed in `organization_concepts`;
   `settlement` resolves only against an owner-visible region anchor; `unknown`
   has no anchor. A missing concept or region keeps `resolution=UNRESOLVED` and
   logs `WARN diplomacy_party_unresolved kind=%s` (kind only, never the id). If
   the private region helper is imported from `agents.cognition`, add a public
   `observation_region_anchors` alias rather than exporting the underscore name.
4. Attributing an agent or concept to a macro-society candidate is analysis-only
   (Task 13) and never happens here.
5. For each contact anchor or `dip_contact` frame, upsert a `DiplomaticRelation`
   keyed by `(owner, sorted party anchors)` with the owner self-party first and
   append an immutable contact row. Contact kind is `direct_co_presence` for
   `contact_recorded`, `mediated_message` for a `dip_contact` frame,
   `third_party_report` when the speaker is neither party, and
   `journey_presence` for a journey occurrence.
6. Implement `diplomacy_envoy_status(envoy, representation, *, tick, policy)` as a
   pure mapping from the owner's current representation mandate status to
   `CLAIMED`, `RECOGNIZED`, `CONTESTED`, `REJECTED`, `REVOKED`, `EXPIRED`,
   `SUPERSEDED`, or `UNKNOWN`. For `dip_accredit`, append an envoy row with
   `party_id`, `mandate_ref`, and the accreditation-time status; recompute
   current standing on every read. A missing or foreign mandate is legal and
   yields `CLAIMED` or `UNKNOWN`, never `RECOGNIZED`.
7. For `dip_recall`, append a `DiplomaticTermination` (`target_kind="envoy"`,
   `kind=ENVOY_RECALLED`) and retain every envoy row (Task 10).
8. For `dip_open_negotiation`, append a negotiation row with `status=OPENED`,
   `topic_subject`, `opened_tick`, `revision=0`, and bounded `envoy_refs`.
   Repeated openings with the same subject append a new revision and update
   `last_tick`/status; do not mutate history.
9. Do **not** enforce caps here. Task 7 may return a ledger above a cap in a
   focused test; `enforce_diplomacy_limits` runs in Task 10 so Task 7 never
   forward-references a task that depends on it.
10. Never infer a contact, envoy, or negotiation from silence or another owner's
    ledger.

### Required Interfaces and Contracts

- `apply_diplomacy_update` is pure: same inputs → identical ledger and digest.
- It accepts no `WorldState`, `WorldEvent` store, or engine token.
- `organization_concepts`, `representation`, `collective_decisions`,
  `structured_commitments`, `disputes`, and `evidence` are read-only owner
  sidecars; the function must not mutate them.
- A `dip_contact` frame from a third party records `third_party_report` and
  resolves no counterparty party acceptance.
- Every appended row is ordered by `(tick, id)`.

### Requirement Evidence (when reconciliation applies)

- Original Request: "diplomatic contact", "envoys", "negotiations"; "using
  agent-mediated interaction".
- `src/simulation/v4_architecture.py` 150-163: objective facts are contact
  co-presence, journeys, and ordinary command effects.
- `.ai-factory/ARCHITECTURE.md`: direct and communicated testimony are distinct.

### Error Handling and Logging

- Codes: `diplomacy_owner_mismatch`, `diplomacy_policy_mismatch`,
  `diplomacy_invalid_tick`, `diplomacy_unknown_party`.
- `DEBUG diplomacy_prepare relations=%s contacts=%s envoys=%s negotiations=%s`.
- `WARN diplomacy_party_unresolved kind=%s`; never log anchors or agent ids.
- Cap enforcement and `WARN diplomacy_truncated` belong to Task 10, not here.

### Tests

- `tests/unit/test_diplomacy_collection.py`: contact from `contact_recorded`;
  mediated contact; third-party report never resolves a party; organization
  anchor resolves with an owned `orgc-` concept and stays unresolved without
  one; settlement resolves only with a visible region; agent party resolution;
  relation rows carry the owner self-party; repeated identical observation is
  idempotent; ordering and digest; no peer-ledger input is accepted (signature
  check); no cap is enforced in this task.
- Hypothesis: appending the same observation never changes the digest.

### Acceptance Criteria

- Contacts, envoys, and negotiations accumulate deterministically across ticks.
- Missing anchors stay unresolved; nothing is invented.

### Verification

- `uv run pytest tests/unit/test_diplomacy_collection.py -q`
- Expected: pass.

## Task 8: Collect proposals, promises, agreements, disputes, and shared projects

### Intent

All five instrument kinds must be created and declared through speech, with
bounded anchors into the owner's other ledgers. Nothing here binds, enforces, or
executes.

### Implementation Steps

1. Map frames to instrument kinds: `dip_propose` → `PROPOSAL` with
   `term_kind` and `topic_subject`; `dip_promise` → `PROMISE`;
   `dip_shared_project` → `SHARED_PROJECT`; `dip_dispute` → `DISPUTE`; an
   `dip_accept` on a proposal that then has every party's declaration produces
   an `AGREEMENT` **view** over the same instrument id (do not create a second
   instrument). Define `is_agreement_view(instrument, declarations, *, tick,
   policy)` and use it for `agreement_count` in Task 15, because
   `DiplomaticInstrument.kind` stays `PROPOSAL` and no row ever has kind
   `AGREEMENT` otherwise.
2. Append a `DiplomaticDeclaration` for every `propose`/`accept`/`reject`/
   `withdraw`/`promise`/`dispute`/`shared_project`/`report` frame. The new
   instrument inherits the relation's ordered `party_ids`; a declaration whose
   `declarer_party_id` is not in that set is rejected with
   `diplomacy_party_set_invalid`.
3. Validate anchors: `anchor_refs` may cite
   `structured_commitments`, `collective_decisions` (project proposals),
   `disputes`, or `evidence` tokens that the owner already holds. Unknown
   anchors are retained as opaque tokens with
   `WARN diplomacy_anchor_unresolved kind=%s`; they are never looked up in a
   peer ledger.
4. A `dip_promise` creates a promise instrument; if the frame cites a commitment
   anchor, store it, but never claim the commitment was fulfilled or broken.
5. A `dip_dispute` creates a dispute instrument referencing the owner's dispute
   or evidence rows when supplied; it is not a court case.
6. A `dip_shared_project` creates a shared-project instrument referencing a
   collective project or organization-agency decision anchor; it is not objective
   work and does not allocate resources.
7. `dip_report` appends a `REPORT` declaration with provenance `COMMUNICATED`;
   it changes no status.
8. A `dip_accept` from a principal counts directly for its party; a `dip_accept`
   from an envoy requires recognized standing. An envoy whose standing is not
   `RECOGNIZED` is retained as a communicated declaration and does not complete
   party acceptance (Task 9).
9. Implement `record_diplomacy_utterance(ledger, command, *, owner_id, tick,
   representation=None, organization_concepts=None, collective_decisions=None,
   structured_commitments=None, disputes=None, evidence=None, policy=None)`
   for the owner's own post-selection speech: it parses the attached `dip_v1`
   frame from an admitted `Talk`/`Ask`/`Tell` command, records it with
   `provenance=SELF_DECLARED` and the verified owner as envoy, and applies the
   same kind/act validation. It never re-submits or rewrites the command and it
   does not run the Task 10 detection/limit pipeline itself.

### Required Interfaces and Contracts

- Instruments are immutable; status is derived.
- One instrument id per `(owner, relation, kind, topic_subject, opened_tick)`;
  repeated declarations attach to it.
- Terms are closed (`DiplomaticTermKind`); free-form terms are rejected.
- No instrument field stores a price, quota, obligation, or enforcement state.

### Requirement Evidence (when reconciliation applies)

- Original Request: "proposals", "promises", "agreements", "disputes", "shared
  projects".
- `src/agents/cognition/structured_commitments.py` 206: commitments are speech,
  not enforced debt.
- `src/agents/cognition/collective_decisions.py` 152-160, 705-719: proposals and
  windows stay owner-scoped.

### Error Handling and Logging

- Codes: `diplomacy_instrument_kind_mismatch`,
  `diplomacy_invalid_anchor_count`, `diplomacy_unsupported_term`.
- `DEBUG diplomacy_instruments_added instruments=%s declarations=%s`.
- `WARN diplomacy_anchor_unresolved kind=%s`; never log the anchor value.

### Tests

- `tests/unit/test_diplomacy_instruments.py`: each kind/act pair; promise with
  and without a commitment anchor; dispute linking a dispute row; shared project
  linking a collective project; report changes no status; unknown anchor retained
  with notice; free-form term rejected; no second instrument for agreement;
  `is_agreement_view` is true only for an every-party proposal; a declaration
  outside the relation party set is rejected; a principal accept counts without
  an envoy and an unrecognized envoy accept does not.

### Acceptance Criteria

- All five kinds are created, declared, and referenced deterministically.
- No instrument can bind, enforce, or allocate.

### Verification

- `uv run pytest tests/unit/test_diplomacy_instruments.py -q`
- Expected: pass.

## Task 9: Derive envoy standing, agreement acceptance, and misrepresentation

### Intent

This is the core trust boundary: envoys may lack authority, may exceed scope, or
may be contradicted by their principal, and every one of those cases is retained
as a belief rather than resolved into a truth.

### Implementation Steps

1. Use the Task 7 `diplomacy_envoy_status(envoy, representation, *, tick,
   policy)` mapping as the single source of envoy standing; do not duplicate the
   mapping in Task 9. Recompute it at the requested `tick` from the mandate's
   current `scope_kind`, `duration_kind`, `scope_subject`, `end_tick`, and
   status, so a revocation or supersession after accreditation is visible.
2. Implement `diplomacy_instrument_status(instrument, declarations, *, tick,
   policy) -> tuple[DiplomaticInstrumentStatus, DiplomaticAcceptanceBasis]`:
   `PROPOSED`/`OPEN` with only the opener; `APPARENTLY_ACCEPTED` only when every
   party in `instrument.party_ids` has an active `ACCEPT` at or after
   `opened_tick` and at least `agreement_min_party_declarations` distinct
   parties are present. A principal declaration (`envoy_ref is None`) counts
   directly; an envoy declaration requires `diplomacy_envoy_status(...) ==
   RECOGNIZED` **and** `diplomacy_scope_covers(...)` for the instrument kind,
   duration, and subject. `REJECTED` on any active `REJECT`; `WITHDRAWN` on an
   active opener withdraw; `UNRESOLVED` when any party has an active `DISPUTE`;
   `ACTIVE` for shared projects with every party accepted; `COMPLETED_CLAIMED`
   on an explicit completion claim; `EXPIRED` at the fixed exclusive boundary;
   `SUPERSEDED` when a later instrument supersedes it (Task 10).
3. An `ACCEPT` from an envoy without recognized standing or without scope
   coverage is retained with `provenance=COMMUNICATED` and never satisfies party
   acceptance.
4. Implement `detect_diplomatic_misrepresentation(ledger, representation, *,
   tick, policy)` producing content-addressed, deduplicated retained rows:
   `MANDATE_UNRECOGNIZED` when an envoy declared an authority-bearing act with
   standing `UNKNOWN`/`CLAIMED`/`REJECTED`/`REVOKED`/`EXPIRED`/`SUPERSEDED`;
   `SCOPE_EXCEEDED` when `diplomacy_scope_covers` is false;
   `CONTRADICTED_BY_PRINCIPAL` when the principal's own later declaration on the
   same instrument disagrees; `CONTESTED_BY_MEMBER` when a party member rejects
   the envoy. Running the detector twice on one ledger yields the same rows and
   ids.
5. Never derive a "lie", "truth", "guilt", or "bad faith" field. A
   misrepresentation row states only what the owner observed.
6. A principal's own declaration always outranks an envoy's for the same party;
   if both are present, the principal declaration governs acceptance and the
   envoy's conflicting declaration produces `CONTRADICTED_BY_PRINCIPAL`.

### Required Interfaces and Contracts

```python
def diplomacy_envoy_status(
    envoy: DiplomaticEnvoy,
    representation: object | None,
    *,
    tick: int,
    policy: DiplomacyPolicy,
) -> DiplomaticEnvoyStatus: ...

def diplomacy_instrument_status(
    instrument: DiplomaticInstrument,
    declarations: Sequence[DiplomaticDeclaration],
    *,
    tick: int,
    policy: DiplomacyPolicy,
) -> tuple[DiplomaticInstrumentStatus, DiplomaticAcceptanceBasis]: ...

def detect_diplomatic_misrepresentation(
    ledger: DiplomaticLedger,
    representation: object | None,
    *,
    tick: int,
    policy: DiplomacyPolicy,
) -> tuple[DiplomaticMisrepresentation, ...]: ...
```

- Party acceptance deduplicates by `declarer_party_id`; one actor cannot satisfy
  two parties, and every `declarer_party_id` must be in `instrument.party_ids`.
- A principal declaration has `envoy_ref=None` and counts directly; only an
  envoy declaration is subjected to `RECOGNIZED` + `diplomacy_scope_covers`.
- A collective party never "accepts" through an unaccredited member frame; that
  is a communicated declaration only.
- When no representation ledger exists (for example `organizations` is off), no
  envoy can be `RECOGNIZED`; every authority-bearing envoy declaration yields
  `MANDATE_UNRECOGNIZED` and the instrument stays `PROPOSED`/`OPEN`.
- Same-root declarations are not independent corroboration; deduplicate by
  `independence_ref` before counting any support-like aggregate. Agreement
  acceptance itself deduplicates by party, not by root.

### Requirement Evidence (when reconciliation applies)

- Original Request: "Representatives may misrepresent their society or lack full
  authority"; "Some members may reject the representative" (V4-09 seam reused).
- `src/agents/cognition/offices.py` 579-667, 1934-1983: retained support,
  opposition, and independence.
- `src/agents/cognition/legal_disputes.py`: `apparently_accepted` requires every
  named party and still binds nobody.

### Error Handling and Logging

- Codes: `diplomacy_acceptance_requires_two_parties`,
  `diplomacy_declaration_after_end_tick`, `diplomacy_party_duplicate`.
- `DEBUG diplomacy_standing recognized=%s claimed=%s contested=%s rejected=%s`.
- `INFO diplomacy_misrepresentation_recorded kind=%s` (kind only).
- Never log party, envoy, mandate, or declaration ids.

### Tests

- `tests/unit/test_diplomacy_acceptance.py`: self-claim stays claimed; recognized
  mandate plus every-party accept yields `APPARENTLY_ACCEPTED`; one party's
  accept is insufficient; an unrecognized envoy's accept does not complete; a
  principal accept counts without any envoy; a `single_act`/`occasion` mandate
  cannot accept a long-running agreement; a mismatched `scope_subject` yields
  `scope_exceeded`; a mandate revoked after accreditation is no longer current;
  a `superseded` mandate maps to `SUPERSEDED`; principal declaration overrides
  an envoy; reject/withdraw/dispute transitions; same actor cannot satisfy two
  parties; same-root declarations deduplicate; running detection twice produces
  identical ids; all four misrepresentation kinds produced exactly once; no
  truth/lie field.

### Acceptance Criteria

- Recognition is derived and revisable; nothing is automatically legitimate.
- Misrepresentation is retained, not punished or "verified".

### Verification

- `uv run pytest tests/unit/test_diplomacy_acceptance.py -q`
- Expected: pass.

## Task 10: Retain termination, supersession, expiry, and conflicts

### Intent

Long-running relations require explicit endings. Withdrawal, envoy recall,
dispute, expiry, and supersession are retained states; conflicts coexist and are
never reconciled into one authoritative agreement.

### Implementation Steps

1. Implement `expire_diplomacy_records(ledger, *, tick, policy) -> DiplomacyLedger`:
   an instrument or envoy with `end_tick is not None and tick >= end_tick` gains
   an appended `DiplomaticTermination` (`kind=EXPIRED`) and derives `EXPIRED`;
   expiry is never a mutable status field and every row is retained.
2. Implement `apply_diplomacy_termination(ledger, *, target_kind, target_ref,
   kind, tick, provenance)`: append a `DiplomaticTermination` carrying
   `PARTY_WITHDREW`, `ENVOY_RECALLED`, `ENVOY_RESIGNED`, `AGREEMENT_DISPUTED`,
   `SUPERSEDED`, or `EXPIRED`. Validate that the target exists and that the
   termination kind is legal for the target kind.
3. Implement `supersede_diplomacy_instruments(ledger)`: a later instrument with
   the same `(relation_id, kind, topic_subject)` supersedes an earlier
   `PROPOSED`/`OPEN`/`APPARENTLY_ACCEPTED` one only when the later instrument has
   at least one recognized party declaration; the older keeps all rows and gains
   a `SUPERSEDED` termination. Two recognized agreements may coexist.
4. Implement `detect_diplomacy_conflicts(ledger)`: `DUPLICATE_ENVOY` when two
   active envoys for one `party_id` hold different recognized mandates;
   `CONTRADICTORY_TERMS` when two instruments over the same subject carry
   different `term_kind` values; `CONFLICTING_PARTY` when one relation's
   `party_ids` resolve to more than one kind for the same anchor; `AGREEMENT_DISPUTE`
   when a dispute references an agreement view. Conflicts are content-addressed,
   sorted, merged without duplicates, retained, and never resolved.
5. Implement `enforce_diplomacy_limits(ledger, *, policy)` with deterministic
   truncation: relations beyond `max_relations`, parties beyond `max_parties`,
   per-relation rows beyond their caps, declarations/terminations beyond
   `max_declarations_per_instrument`, total records beyond
   `max_total_records`. Truncate the oldest low-priority rows first, never a
   relation party set, a self-party, or an active recognized agreement; emit
   `WARN diplomacy_truncated table=<name>`; when nothing droppable remains emit
   `ERROR diplomacy_capacity_reached table=<name>` with a safe code.
6. Extend `apply_diplomacy_update` and `record_diplomacy_utterance` into the one
   ordered pipeline: append raw rows, derive current standings, detect
   misrepresentation, expire, supersede, detect conflicts, then enforce limits.
   Each derived row family is deduplicated by content-addressed id, so repeating
   one update never duplicates a misrepresentation, conflict, or termination.
7. Never delete a row: supersession, termination, and truncation of droppable
   low-priority rows append or drop only the documented candidates; the digest
   history of retained rows is preserved.

### Required Interfaces and Contracts

- Boundary tick semantics are **exclusive**: a row with `end_tick` is `EXPIRED`
  when `tick >= end_tick`; `end_tick` is the first inactive tick. Test the exact
  boundary and the tick after it.
- Truncation is deterministic and order-stable across processes; it never drops
  a self-party, a relation party set, or an active recognized agreement.
- Two recognized agreements for one pair may coexist; there is no winner.
- The pipeline is idempotent: applying the same update twice yields identical
  misrepresentation, termination, and conflict ids.

### Requirement Evidence (when reconciliation applies)

- Original Request: "long-running relationships"; "Representatives may
  misrepresent their society or lack full authority".
- `src/agents/cognition/delegation_representation.py`: revocation, expiry,
  supersession, and conflict retention.
- `.ai-factory/ARCHITECTURE.md`: append-only authoritative history.

### Error Handling and Logging

- Codes: `diplomacy_unknown_instrument`, `diplomacy_invalid_termination`,
  `diplomacy_capacity_reached`.
- `INFO diplomacy_instrument_terminated kind=%s` (no ids).
- `WARN diplomacy_truncated table=%s dropped=%s`.
- `ERROR diplomacy_capacity_reached table=%s`.

### Tests

- `tests/unit/test_diplomacy_termination.py`: withdrawal, recall, resignation,
  dispute, expiry at the exact exclusive boundary and the tick after it,
  supersession of an older proposal but not of a recognized agreement,
  coexistence of two recognized agreements, each conflict kind, deterministic
  truncation, capacity error, retained termination rows, the full ordered
  pipeline materializing every row family in one update, and idempotence under a
  repeated update. No row is removed from the digest history.

### Acceptance Criteria

- Termination, expiry, and supersession are explicit and retained.
- Conflicts never collapse into one authority.

### Verification

- `uv run pytest tests/unit/test_diplomacy_termination.py -q`
- Expected: pass.

## Task 11: Carry the diplomacy ledger through cognition and runtime

### Intent

The owner's ledger must survive the loop, perspective, runtime checkpoint, and
runner result so detached analysis and later diplomacy plans can read it without
touching live cognition.

### Implementation Steps

1. Add `diplomacy: object | None = None` to `Perspective` in
   `src/agents/cognition/contracts.py` beside `representation` (177, 195-197).
2. Add `diplomacy` to `SubjectiveSnapshot` (765), `CognitiveLoopProposal`
   (3989), and `CognitiveLoopResult` (4317), validated through
   `require_owner_diplomacy`.
3. Add `diplomacy` to `AgentRuntimeCheckpoint` (`run_control.py` 620) and its
   validation (815).
4. In `agent_runtime.py`, add `_diplomacy`/`_commit_diplomacy` beside the
   representation pair (1464) and restore it at 3502.
5. In `perception.py::build_perspective`, add the `diplomacy` parameter
   (143, 161-163) and wire it into construction (357, 375-377).
6. In `loop.py`, implement `_prepare_diplomacy(loop_input, *, representation,
   organization_concepts, collective_decisions, structured_commitments, disputes,
   evidence)` beside `_prepare_representation` (2895). It reads the carried
   `snapshot.diplomacy`, falls back to `empty_diplomacy_ledger(loop_input.agent_id,
   tick=tick)`, validates ownership, and passes the prepared representation
   ledger plus the owner sidecars into `apply_diplomacy_update`. Call it from the
   prepare stage after `_prepare_representation` (5034) and call
   `record_diplomacy_utterance` at the post-selection record site (5751-5771)
   with the same mode guard and the same sidecars.
7. In `runner.py`, add `export_diplomacy_ledgers()` beside
   `export_representation_ledgers()` (5566) returning one ledger per owner in
   agent order, and populate it at the result construction site (5122-5125).
8. In `runner_models.py`, add `diplomacy_ledgers: tuple[object, ...] = ()` beside
   `representation_ledgers` (6383) and extend ordered-sequence/type validation
   (6725) with `require_owner_diplomacy`, unique owner ids, and canonical order.
9. Do not add the ledger to `SimulationRunnerResultDocument`; the result document
   stays unchanged, matching V4-09.

### Required Interfaces and Contracts

- `_prepare_diplomacy(loop_input, *, representation, organization_concepts,
  collective_decisions, structured_commitments, disputes, evidence) -> object |
  None`.
- `build_perspective(..., diplomacy: object | None = None)`.
- `export_diplomacy_ledgers(self) -> tuple[DiplomacyLedger, ...]`.
- Disabled mode exports nothing and allocates nothing.
- Carried ledgers are owner-scoped and never shared between engines or agents.
- Export carries the raw rows; current envoy/instrument standings are derived by
  Task 9 at snapshot/compose time, not frozen into the result.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime": owner-safe
  perspective, deferred finalization, no token or peer state.
- `.ai-factory/ARCHITECTURE.md` requirement 4: subjective checkpoints stay
  outside the objective event fold.

### Error Handling and Logging

- Codes: `diplomacy_owner_mismatch`, `diplomacy_ledger_order_invalid` via
  `require_owner_diplomacy`.
- `DEBUG diplomacy_prepare mode=%s relations=%s instruments=%s`.
- Never log ledger contents, ids, or anchors.

### Tests

- `tests/unit/test_diplomacy_runtime.py`: perspective round-trip; checkpoint
  preserve/restore; disabled mode allocates nothing; `_prepare_diplomacy`
  consumes the carried ledger and every sidecar; export order and owner
  validation; export keeps current standing derived rather than frozen; result
  rejects foreign/duplicate/misordered ledgers; result document schema
  unchanged.
- `tests/unit/test_diplomacy_determinism.py`: two runs with the same seed and
  observations produce byte-identical ledger digests; no `hash()`/UUID/wall-clock
  use in the module (AST scan).

### Acceptance Criteria

- The ledger round-trips through every supported carry path.
- Disabled mode remains allocation-free.

### Verification

- `uv run pytest tests/unit/test_diplomacy_runtime.py tests/unit/test_diplomacy_determinism.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: diplomacy becomes a de facto authority store.
  Mitigation: Task 9 derives standing only from the owner's representation
  ledger, and Task 10 never deletes or reconciles conflicts.
- Risk: party resolution reads analysis identities or peer ledgers.
  Mitigation: Task 7 accepts only owner sidecars and observation anchors;
  Task 22 scans imports and call signatures.
- Risk: an envoy's statement silently binds a collective.
  Mitigation: Task 9 requires each party's own recognized declaration and
  deduplicates actors; Task 8 keeps `REPORT` status-neutral.
- Risk: long-running rows grow unbounded.
  Mitigation: locked per-table caps plus deterministic truncation and an explicit
  capacity-reached error.

## Phase Completion Checklist

- Every task in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
