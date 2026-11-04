# Phase 2: Owner-Scoped Representation Beliefs

Plan: [index.md](index.md)
Tasks: 4-9
Depends on: Phase 1 / Tasks 1-3

## Objective

Implement one owner's representation ledger: bounded mandates with principal,
representative, scope, duration, provenance, support, opposition, revocation, and
conflict rows; verified-speaker speech frames; principal resolution against the
owner's own collective concepts and observed regions; derived recognition that
never grants legitimacy; deterministic carry through cognition, perspective,
checkpoints, and the runner result.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/agents/cognition/evidence_testimony.py` | records 778-1137; ledger 1145-1167; limits 1425-1504; digest; `require_owner_evidence` 1370-1390 | Closest record/ledger template including truncation |
| `src/agents/cognition/evidence_testimony_communication.py` | `_FRAME_KEYS` 101-119; encode 374-390; parse 393-461; party check 491-507 | Frame shape, cap, verified-speaker rule |
| `src/agents/cognition/legal_disputes.py` | `_reject_forbidden_input` 2517-2544; `apply_dispute_update` 3542-3559 | Recursive foreign-owner guard and update entry point |
| `src/agents/cognition/offices.py` | occupant support/opposition 579-667; `_record_support` 1934-1983; recognition 1143-1195 | Support/opposition/independence pattern; no auto-recognition |
| `src/agents/cognition/collective_decisions.py` | acts 152-160; `CollectiveDelegation` 705-719 | Decision-scoped delegation that representation must compose with, not duplicate |
| `src/agents/cognition/organization_concepts.py` | `orgc-` ids 31/373; label filters 458-476 | Collective anchor identity |
| `src/world/observations.py` | `ObservedRegionalContext` 333-349; `ObservedJourney` 352-374; `VisibleExit.destination_region_id` 291 | Owner-visible settlement anchors |
| `src/agents/cognition/configuration.py` | loop config 647-658; reconciliation 1139-1227 | Mode install from Task 3 |
| `src/agents/cognition/loop.py` | org/evidence install 925-1028; `_prepare_evidence` 2651-2864; utterance recorder 5650-5658 | Prepare and late-utterance pattern |
| `src/simulation/perception.py` | `build_perspective` 113/140-162/353-375 | Perspective carry |
| `src/simulation/runner_models.py` | result ledgers 6377-6382; ordered validation 6698-6723 | Result carry validation |
| `src/simulation/agent_runtime.py` | commit 2843-2865; `_commit_evidence` 1432-1460 | Runtime commit and owner check |
| `src/simulation/run_control.py` | checkpoint fields 614-619; validation 793-813 | Checkpoint validation |
| `src/simulation/runner.py` | exporters 5508-5551; `finish_run` 5051-5097 | Result export |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/delegation_representation.py` | modify | Records, ledger, apply, recognition, conflicts, revocation, limits, digest |
| `src/agents/cognition/delegation_representation_communication.py` | create | `rep_v1` encode/parse/party verification |
| `src/agents/cognition/loop.py` | modify | `_prepare_representation`, late utterance recording |
| `src/agents/cognition/contracts.py` | modify | `Perspective.representation` |
| `src/simulation/perception.py` | modify | `build_perspective` kwarg/forward |
| `src/simulation/agent_runtime.py` | modify | `_representation` slot, `_commit_representation`, dispatch |
| `src/simulation/run_control.py` | modify | Checkpoint field and validation |
| `src/simulation/runner_models.py` | modify | `representation_ledgers` ordered/type validation |
| `src/simulation/runner.py` | modify | `export_representation_ledgers`, result population |
| `src/agents/cognition/__init__.py` | modify | Public exports |
| `tests/unit/test_delegation_representation_records.py` | create | Record/ledger invariants |
| `tests/unit/test_delegation_representation_communication.py` | create | Frame codec and speaker checks |
| `tests/unit/test_delegation_representation_collection.py` | create | Apply/update behavior |
| `tests/unit/test_delegation_representation_recognition.py` | create | Principal resolution and recognition |
| `tests/unit/test_delegation_representation_revocation.py` | create | Revocation, expiry, conflicts |
| `tests/unit/test_delegation_representation_runtime.py` | create | Carry chain |
| `tests/unit/test_delegation_representation_determinism.py` | create | Ordering/digest/no global RNG |

## Task 4: Define representation records and ledger invariants

### Intent

Fix the data contract for one owner's beliefs before any collection logic runs.
Later phases (analysis, snapshot, API) mirror these fields, so their names and
bounds must be final here.

### Implementation Steps

1. Add frozen slots dataclasses to
   `src/agents/cognition/delegation_representation.py`:
   `RepresentationMandate`, `RepresentationPosition`,
   `RepresentationRevocation`, `RepresentationConflict`, and
   `RepresentationLedger`.
2. Give every record a `__post_init__` that validates owner-independent fields:
   id grammar, tick range, enum membership, quantized confidence, bounded token
   lengths, tuple normalization, and forbidden field names.
3. Validate owner consistency in `RepresentationLedger.__post_init__`: every row
   id must start with the owner-local prefix and every record must carry the
   minting owner implicitly through its id namespace; reject duplicates and
   unknown cross-references (`mandate_id` in position/revocation/conflict must
   exist).
4. Normalize ordering: mandates by `(start_tick, mandate_id)`; positions by
   `(tick, position_id)`; revocations by `(tick, revocation_id)`; conflicts by
   `(tick, conflict_id)`; `region_anchors` sorted and unique.
5. Reject tick regression: every record tick and the observation span must be
   non-decreasing relative to `prior` when merged.
6. Define `coverage` as `complete` when no `pruned_*` counter is non-zero and no
   truncation notice exists, else `partial`.
7. Implement `enforce_representation_limits(ledger) -> RepresentationLedger`
   with a deterministic, recognition-preserving drop order:
   superseded/expired terminal mandates oldest first (their positions,
   revocations, and conflicts follow), then oldest unresolved conflicts, then the
   oldest `claimed`/`contested`/`rejected` mandate with no recognized position.
   Never drop a `recognized`, unrevoked, unexpired mandate. Increment the matching
   `pruned_*` counter, append `representation_truncated`, and set coverage to
   `partial`. If nothing is droppable at the hard cap, leave the ledger intact,
   append `representation_capacity_reached`, and reject the newest claim instead
   of deleting a live belief.
8. Implement `empty_representation_ledger(owner_id)`,
   `require_owner_representation(ledger, owner_id)`, and
   `representation_ledger_digest(ledger)` using canonical sorted JSON fields and
   SHA-256.
9. Quantize `confidence` with `Decimal("0.000001")` and `ROUND_HALF_UP`; reject
   bools, NaN, and values outside `[0, 1]`.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class RepresentationMandate:
    mandate_id: str                 # rmd-<16 hex>
    principal_kind: RepresentationPrincipalKind
    principal_ref: str | None       # agent id | orgc- id | region id | None
    representative_id: str          # owner-observed agent id; never the owner for self-claims
    scope_kind: RepresentationScopeKind
    scope_subject: str | None       # bounded token or None
    duration_kind: RepresentationDurationKind
    start_tick: int
    end_tick: int | None
    provenance: RepresentationProvenance
    attributed_actor_id: str | None # verified speaker who conveyed the claim
    evidence_refs: tuple[str, ...]  # evs-/evw-/evi-/evc- ids
    decision_refs: tuple[str, ...]  # 64-hex collective decision ids
    office_refs: tuple[str, ...]    # 64-hex office concept ids
    rule_refs: tuple[str, ...]      # frl-<16 hex> written-rule ids
    confidence: float
    principal_resolved: bool
    principal_declared: bool       # verified agent principal accepted the mandate
    office_basis: bool             # owner office ledger supports the representative
    decision_basis: bool           # owner collective decision supports it
    written_basis: bool            # owner written-rule/record basis exists
    revoked: bool
    expired: bool
    superseded: bool
    status: RepresentationStatus
    recognition_basis: RepresentationRecognitionBasis
    revision: int

@dataclass(frozen=True, slots=True)
class RepresentationPosition:
    position_id: str                # rmp-<16 hex>
    mandate_id: str
    actor_id: str
    stance: RepresentationPositionStance
    root_ref: str | None            # shared-root independence key
    provenance: RepresentationProvenance
    tick: int
    active: bool

@dataclass(frozen=True, slots=True)
class RepresentationRevocation:
    revocation_id: str              # rmv-<16 hex>
    mandate_id: str
    actor_id: str
    kind: RepresentationRevocationKind
    provenance: RepresentationProvenance
    tick: int
    contested: bool

@dataclass(frozen=True, slots=True)
class RepresentationConflict:
    conflict_id: str                # rmx-<16 hex>
    mandate_ids: tuple[str, ...]    # two or more, sorted
    kind: RepresentationConflictKind
    status: str                     # "unresolved" only
    tick: int

@dataclass(frozen=True, slots=True)
class RepresentationLedger:
    owner_id: str
    mandates: tuple[RepresentationMandate, ...] = ()
    positions: tuple[RepresentationPosition, ...] = ()
    revocations: tuple[RepresentationRevocation, ...] = ()
    conflicts: tuple[RepresentationConflict, ...] = ()
    region_anchors: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = REPRESENTATION_POLICY_VERSION
    first_tick: int = 0
    last_tick: int = 0
    pruned_mandates: int = 0
    pruned_positions: int = 0
    pruned_revocations: int = 0
    pruned_conflicts: int = 0
    coverage: str = "complete"
```

- `duration_kind=UNTIL_TICK` requires `end_tick`; `SINGLE_ACT` requires
  `end_tick == start_tick`; `OCCASION` requires `end_tick >= start_tick`;
  `UNTIL_REVOKED` and `UNKNOWN` require `end_tick is None`.
- `principal_kind=AGENT` requires a stable agent token and
  `principal_ref != representative_id`; `ORGANIZATION`/`COALITION` require the
  `orgc-` grammar; `SETTLEMENT` requires a region token; `UNKNOWN` requires
  `principal_ref is None` and `principal_resolved=False`.
- The recognition-input booleans (`principal_declared`, `office_basis`,
  `decision_basis`, `written_basis`, `revoked`, `expired`, `superseded`) default
  to `False`; Task 6/7/8 populate them and derive `status`/`recognition_basis`
  from them. Task 4 only validates that they are exact `bool`s, that at most one
  of `revoked`/`expired`/`superseded` is true, and that the sole true terminal
  boolean matches the terminal status.
- `scope_kind=UNKNOWN` requires `scope_subject is None`; other kinds may carry a
  bounded subject.
- `rule_refs` match `^frl-[0-9a-f]{16}$`; `decision_refs` and `office_refs` are
  64 lowercase hex; `evidence_refs` match `evs-`/`evw-`/`evi-`/`evc-`. Each ref
  tuple is sorted, unique, and capped by the policy.
- Every conflict `status` is exactly `"unresolved"`.

### Error Handling and Logging

- Codes: `representation_invalid_owner`, `representation_invalid_id`,
  `representation_duplicate_id`, `representation_unknown_reference`,
  `representation_tick_regression`, `representation_invalid_duration`,
  `representation_invalid_principal`, `representation_invalid_confidence`,
  `representation_policy_version_mismatch`.
- `_LOG.warning("representation_truncated mandates=%d positions=%d", ...)` on
  truncation; counts only, never ids or principals.
- `_LOG.debug("representation_ledger_digest prefix=%s", digest[:12])` is allowed;
  never log the full digest with domain values.

### Tests

- `tests/unit/test_delegation_representation_records.py`:
  each duration/principal/scope validation matrix; duplicate/unknown reference;
  ordering normalization (reversed input yields identical ledger); tick
  regression; truncation order and counters; capacity-reached rejection without
  deleting a recognized mandate; digest stability; owner guard accepts same owner
  and rejects foreign.

### Acceptance Criteria

- Invalid records fail closed with a safe code.
- Ordering and digests are identical for any input permutation.
- Truncation is explicit and never silent.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_records.py -q`
- Expected: pass.

## Task 5: Add bounded rep_v1 delegation speech frames

### Intent

Delegations are claimed, accepted, rejected, supported, opposed, revoked, and
resigned through existing speech. The frame must be bounded, closed, and
speaker-verified so no agent can forge another party's mandate.

### Implementation Steps

1. Create
   `src/agents/cognition/delegation_representation_communication.py`.
2. Define `REPRESENTATION_FRAME_VERSION = "rep_v1"`,
   `REPRESENTATION_FRAME_MAX_CHARS = 256` (the attachable ceiling imposed by
   `CommunicationRelation.object`), and the ordered `_FRAME_KEYS`:
   `mandate_ref`, `principal_kind`, `principal_ref`, `representative_ref`,
   `scope_kind`, `scope_subject`, `duration_kind`, `end_tick`, `provenance`,
   `revision`.
3. Define `RepresentationAct` values and their predicate strings:
   `rep_claim`, `rep_delegate`, `rep_accept`, `rep_reject`, `rep_support`,
   `rep_oppose`, `rep_abstain`, `rep_revoke`, `rep_resign`, `rep_report`.
4. Define a frozen `RepresentationFrame` dataclass over those fields; optional
   values are `None` and serialize as `none`; enums serialize as `.value`.
5. Implement `encode_representation_frame(frame) -> str` and
   `parse_representation_frame(text) -> RepresentationFrame | None`; return
   `None` for wrong version, wrong arity, unknown enum value, over-cap text, or
   non-integer revision/end tick.
6. Implement `parse_representation_frame_relation(subject, predicate, object)`
   accepting only `subject == "rep_v1"` and a known predicate; return `None`
   otherwise.
7. Implement `representation_frame_party_matches(frame, verified_speaker)`:
   - `rep_claim`/`rep_resign`: `representative_ref == verified_speaker`.
   - `rep_delegate`: `principal_kind is AGENT` and
     `principal_ref == verified_speaker`; the named `representative_ref` must
     differ from the speaker.
   - `rep_accept`/`rep_reject`: `principal_kind is AGENT` and
     `principal_ref == verified_speaker`.
   - `rep_revoke`: `principal_ref == verified_speaker` or
     `representative_ref == verified_speaker`.
   - `rep_support`/`rep_oppose`/`rep_abstain`/`rep_report`: any verified
     speaker passes; the actor is recorded separately.
8. Bound the frame so its colon-joined object stays under the
   `CommunicationRelation.object` limit of 256 characters; if a legal frame
   cannot fit, reject it at encode time with
   `representation_frame_too_large`.

### Required Interfaces and Contracts

```python
def encode_representation_frame(frame: RepresentationFrame) -> str: ...
def parse_representation_frame(text: str) -> RepresentationFrame | None: ...
def parse_representation_frame_relation(
    subject: str, predicate: str, object_text: str
) -> RepresentationFrame | None: ...
def representation_frame_party_matches(
    frame: RepresentationFrame, verified_speaker: str
) -> bool: ...
def representation_frames_from_observation(
    observation: object, *, owner_id: str
) -> tuple[RepresentationFrame, ...]: ...
```

- `representation_frames_from_observation` walks communications addressed to
  `owner_id`, parses each `rep_v1` relation, and returns only frames whose
  claimed party matches the verified speaker. It reads no world state and
  mutates nothing.

- Serialized shape:
  `rep_v1:<predicate>:<mandate_ref>:<principal_kind>:<principal_ref>:<representative_ref>:<scope_kind>:<scope_subject>:<duration_kind>:<end_tick>:<provenance>:<revision>`
- `rep_claim` uses `mandate_ref=none`; `rep_delegate` uses `mandate_ref=none`
  and mints a new mandate; every other act requires an `rmd-` id.
- A `rep_accept` from a non-agent principal is not an acceptance; the caller
  downgrades it to a support position (Task 6).

### Error Handling and Logging

- Malformed/over-cap frames return `None`; the caller drops them and appends
  `representation_frame_dropped` (no body, no actor).
- `_LOG.debug("representation_frame act=%s accepted=%s", ...)` may log the act
  name only.
- Never log the serialized frame, principals, or representatives.

### Tests

- `tests/unit/test_delegation_representation_communication.py`: round-trip every
  act; optional `none` handling; over-cap rejected both ways; unknown version
  and predicate rejected; each party-match rule including forged witness,
  delegation by a non-principal, delegation to self, self-claim by another
  actor, collective accept downgrade, and principal revoke.

### Acceptance Criteria

- Only the verified speaker can claim/resign a mandate or accept/reject as an
  agent principal.
- No frame can attribute a claim to a different representative.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_communication.py -q`
- Expected: pass.

## Task 6: Collect mandates, positions, and revocations

### Intent

Turn delivered and own-uttered `rep_v1` frames into one owner's mandates,
positions, and revocation requests without reading world state, a peer ledger, or
constructing a command.

### Implementation Steps

1. Add `apply_representation_update(*, owner_id, tick, observation, prior,
   frames=(), organization_concepts=None, collective_decisions=None,
   offices=None, formal_rules=None, policy=None) -> RepresentationLedger` to
   `delegation_representation.py`.
2. Validate `prior` with `require_owner_representation`; reject any prepared
   sidecar whose owner differs and any `WorldState`, `WorldEvent`,
   `PhysicalRules`, `MetricDocument`, or `AgentCommand` nested input using a
   recursive guard copied from `legal_disputes._reject_forbidden_input`
   (2517-2544), not the weaker evidence check.
3. Refresh `region_anchors` from the observation: the assigned regional context,
   journey origin/destination region ids, and visible-exit destination region
   ids; deduplicate, sort, cap at `max_region_anchors`, append
   `representation_region_anchor_truncated` when capped.
4. Call `representation_frames_from_observation(observation, owner_id=owner_id)`
   to collect verified `rep_v1` frames, then dispatch each by act.
5. `rep_claim` mints an `rmd-` id from `(owner, tick, principal kind/ref,
   representative, scope kind/subject, duration)` where the representative is the
   verified speaker; a repeated identical claim returns the existing mandate and
   increments its revision.
6. `rep_delegate` from an agent principal mints an `rmd-` id naming the
   frame's representative, with `principal_declared=True`; the representative must
   differ from the principal. A repeat with the same principal, representative,
   scope, and duration is idempotent. The stored status is provisional here;
   Task 7 derives the final status and basis.
7. `rep_accept` from an agent principal sets `principal_declared=True` and
   records a position with provenance `principal_declared`; a collective
   principal accept is recorded as a support position with `communicated`
   provenance.
8. `rep_support`/`rep_oppose`/`rep_abstain` upsert one active position per
   `(mandate_id, actor_id)`; a later stance replaces the earlier active row by
   appending a new row and deactivating the old one. `root_ref` is taken from an
   observed communication id when present, else `None`.
9. `rep_revoke`/`rep_resign` create a revocation request; authorization and
   contested handling are finalized in Task 8.
10. `rep_report` never creates support; it records a mandate claim with
    provenance `communicated` and `status=claimed` only when the mandate does not
    already exist.
11. Implement `record_representation_utterance(ledger, command, *, owner_id,
    tick)` for the owner's own `Talk`/`Ask`/`Tell` frames, requiring the
    utterance's immediate source to be the owner.
12. Never infer a mandate from silence, an unobserved act, or a peer's ledger.
13. Call `enforce_representation_limits` before returning so every ledger is
    bounded and coverage is explicit. Task 7 inserts
    `resolve_representation_bases` immediately before this call.

### Required Interfaces and Contracts

- The function is pure: same `(prior, tick, observation, frames, sidecars)`
  produces the same ledger.
- Prepared sidecars are read-only: `organization_concepts` resolves anchors,
  `collective_decisions`/`offices`/`formal_rules` supply recognition bases. No
  sidecar is mutated and no peer owner id is accepted.
- The update never returns, constructs, submits, or resolves an `AgentCommand`.

### Error Handling and Logging

- Appended notices: `representation_frame_dropped`,
  `representation_party_mismatch`, `representation_unknown_mandate`,
  `representation_duplicate_claim`, `representation_region_unavailable`.
- `_LOG.info("representation_update owner=%s mandates=%d positions=%d
  revocations=%d", ...)` uses counts only; owner is already a safe token, but do
  not log principals or scope subjects.
- WARN for dropped/mismatched frames; ERROR only for unrecoverable policy or
  owner errors.

### Tests

- `tests/unit/test_delegation_representation_collection.py`: claim/delegate/
  accept/support/oppose/abstain/revoke/resign/report paths; duplicate claim;
  stance replacement; malformed frame drop; forged speaker notice; collective
  accept downgrade; owner-uttered capture; region-anchor refresh; foreign-owner
  and world-input rejection; no command construction (assert the module imports
  no `AgentCommand`).

### Acceptance Criteria

- Only verified speakers and the owner's own utterances create rows.
- Same-root positions are retained but never counted as independent yet.
- No world or peer state is read.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_collection.py -q`
- Expected: pass.

## Task 7: Resolve principals and derive owner recognition

### Intent

Representation is recognized only when this owner has a principal act,
independent support, or an office/decision/record basis, and no blocking
rejection or revocation. Recognition is a belief; it grants nothing.

### Implementation Steps

1. Implement `resolve_representation_principal(*, mandate, organization_concepts,
   region_anchors) -> bool`:
   - `AGENT`: true when the token is a stable agent id.
   - `ORGANIZATION`/`COALITION`: true only when the `orgc-` id exists in the
     owner's `OrganizationConceptLedger`.
   - `SETTLEMENT`: true only when the region id is in the ledger's
     `region_anchors`.
   - `UNKNOWN`: always false.
2. Implement `appraise_representation_recognition(*, principal_kind,
   principal_resolved, principal_declared, support_roots, opposition_roots,
   office_basis, decision_basis, written_basis, revoked, expired,
   superseded) -> tuple[RepresentationStatus, RepresentationRecognitionBasis]`
   with this exact precedence:
   1. `superseded`/`revoked`/`expired` dominate.
   2. unresolved principal → `CLAIMED` (or `UNKNOWN` for `UNKNOWN` kind).
   3. `principal_declared` → `RECOGNIZED` / `PRINCIPAL_DECLARATION`.
   4. office basis with ≥1 independent root → `OFFICE_AUTHORITY`.
   5. decision basis with ≥1 independent root → `COLLECTIVE_DECISION`.
   6. written basis with ≥1 independent root → `WRITTEN_AUTHORIZATION`.
   7. `support_roots >= 2 and opposition_roots < support_roots` →
      `RECOGNIZED` / `INDEPENDENT_SUPPORT`.
   8. any opposition and zero support → `REJECTED`.
   9. `opposition_roots >= support_roots and opposition_roots >= 1` →
      `REJECTED`.
   10. any opposition with support → `CONTESTED`.
   11. otherwise `CLAIMED` / `NONE`.
3. Compute `support_roots` and `opposition_roots` from active positions by
   independence key `root_ref or f"actor:{actor_id}"`; the owner's own support
   of its own claim is excluded; each key counts once per side.
4. Implement `resolve_representation_bases(ledger, *, organization_concepts,
   offices=None, collective_decisions=None, formal_rules=None,
   tick) -> RepresentationLedger` that resolves every mandate and returns a
   valid, fully derived ledger:
   - resolve `principal_resolved` from `organization_concepts` and the ledger's
     `region_anchors`;
   - populate `office_refs`, `decision_refs`, and `rule_refs` by deterministic
     matching against the owner's own sidecars:
     - **office basis:** an office in `offices` has an occupant claim whose
       occupant is the mandate's `representative_id` with status `candidate`,
       `preferred`, or `recognized`; store that office id.
     - **decision basis:** a recognized decision in `collective_decisions` names
       the principal and the representative (a supporting position or an
       implementation by the representative); store that decision id.
     - **written basis:** a rule in `formal_rules` has a present written
       representation anchor, status `documented` or `recognized_enforcement`,
       and (when `scope_subject` is set) a matching subject token; store that
       `frl-` rule id.
     - A missing sidecar leaves the corresponding refs empty and basis `False`.
     - Refs are sorted, unique, and capped by the policy; a cap appends
       `representation_reference_truncated`.
   - recompute `status` and `recognition_basis` from the persisted booleans and
     active positions, then construct the ledger once so validation never sees
     an inconsistent intermediate.
5. Extend `RepresentationLedger.__post_init__` so it recomputes each mandate's
   status and basis from the persisted booleans and active positions only (no
   sidecar at validation time) and rejects any mismatch with
   `representation_status_mismatch`. `resolve_representation_bases` and
   `apply_representation_update` both use the same private derivation helper, so
   stored and validated values cannot diverge.
6. Implement `representation_standing_summary(ledger, *, principal_kind,
   principal_ref) -> RepresentationStandingSummary` with counts by status,
   active scopes, and whether an unrevoked recognized agent representative
   exists. It returns beliefs only; it never returns a permission or command.
7. Add the summary to `src/agents/cognition/__init__.py` exports for the later
   diplomacy plan to consume read-only.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class RepresentationStandingSummary:
    principal_kind: RepresentationPrincipalKind
    principal_ref: str | None
    recognized_representatives: tuple[str, ...]  # sorted agent ids
    contested_representatives: tuple[str, ...]
    revoked_count: int
    active_scope_kinds: tuple[RepresentationScopeKind, ...]
    coverage: str

def representation_standing_summary(
    ledger: RepresentationLedger,
    *,
    principal_kind: RepresentationPrincipalKind,
    principal_ref: str | None,
) -> RepresentationStandingSummary: ...

def resolve_representation_bases(
    ledger: RepresentationLedger,
    *,
    organization_concepts: object | None,
    offices: object | None = None,
    collective_decisions: object | None = None,
    formal_rules: object | None = None,
    tick: int,
) -> RepresentationLedger: ...
```

- Office/decision/written bases require at least one independent root so a
  representative cannot cite its own proposal or written claim as sole
  authorization.
- The summary never includes a boolean named `authorized`, `allowed`, or
  `valid`; callers must interpret recognized/contested/revoked themselves.
- `principal_declared` is set only when the verified speaker equals the agent
  principal.

### Error Handling and Logging

- `representation_unresolved_principal` WARN with the principal kind only (never
  the ref).
- `representation_recognition` DEBUG with counts and derived status.
- Never log representative ids, principal refs, or scope subjects.

### Tests

- `tests/unit/test_delegation_representation_recognition.py`: each precedence
  branch; unresolved org/settlement; unknown principal; self-claim alone stays
  claimed; two independent roots recognize; same-root duplicates do not;
  opposition majority rejects; mixed support/opposition contests; owner
  self-support excluded; summary excludes revoked mandates; summary has no
  authorization field; office/decision/written basis matching and the
  independent-root requirement; update any Task 6 collection assertion that
  expected a provisional status.

### Acceptance Criteria

- A self-claim is never `recognized` without a principal act, independent
  support, or an office/decision/record basis.
- Rejection and contestation are retained states, not truth findings.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_recognition.py -q`
- Expected: pass.

## Task 8: Retain conflicts, revocation, and supersession

### Intent

Members may reject a representative, principals may revoke, representatives may
resign, and two mandates may conflict. Every outcome is retained; none is
reconciled into a single legitimate authority.

### Implementation Steps

1. Task 4 already defines the recognition-input booleans
   (`principal_declared`, `office_basis`, `decision_basis`, `written_basis`,
   `revoked`, `expired`, `superseded`). This task sets them during revocation,
   expiry, and supersession and keeps the derived status consistent.
2. Implement `detect_representation_conflicts(ledger) ->
   tuple[RepresentationConflict, ...]`:
   - `duplicate_mandate`: two non-terminal mandates share principal kind/ref,
     scope kind/subject, and have different representatives.
   - `contradictory_scope`: the same principal and representative hold an
     unbounded scope (`scope_subject is None`) and a bounded one for the same
     `scope_kind`.
   - `conflicting_principal`: the same representative and scope subject are
     claimed for two different principals.
   - `revocation_dispute`: a revocation with `contested=True`.
   Mint one `rmx-` id per unordered mandate pair/kind; deduplicate; sort.
3. Implement `apply_representation_revocation(ledger, *, tick, mandate_id,
   actor_id, kind, provenance)`:
   - `PRINCIPAL_REVOKED` requires an agent principal equal to `actor_id`.
   - `REPRESENTATIVE_RESIGNED` requires `representative_id == actor_id`.
   - `COLLECTIVE_DECISION_REVOKED` requires a `decision_refs` entry that exists
     in the owner's `CollectiveDecisionLedger`.
   - `OFFICE_LOST` requires an `office_refs` entry absent from the owner's
     `OfficeConceptLedger`.
   - `SCOPE_EXPIRED` is produced only by the tick-expiry pass.
   - Any other actor/kind creates a `CONTESTED` revocation and a
     `revocation_dispute` conflict; the mandate stays active.
4. Implement `expire_representation_mandates(ledger, *, tick)`: mark
   `end_tick <= tick` as expired for `until_tick`/`occasion`/`single_act`;
   `until_revoked` never expires.
5. Implement `supersede_representation_mandates(ledger)` after recognition: when
   a newly recognized mandate covers the same principal and scope as an older
   `claimed`/`contested`/`rejected` mandate with a different representative, mark
   the older `superseded=True`; when both are recognized, keep both and emit
   `duplicate_mandate`.
6. Recompute statuses after revocation/expiry/supersession and append
   `representation_conflict` / `representation_revoked` /
   `representation_expired` notices with counts only.

### Required Interfaces and Contracts

- Terminal statuses are `revoked`, `expired`, `superseded`; they are retained
  rows, never deleted.
- A contested revocation does not change mandate status.
- Two recognized mandates for the same principal/scope coexist and are flagged,
  never merged.
- No objective legitimacy, majority vote, or quorum is computed.

### Error Handling and Logging

- `representation_revocation_unauthorized` WARN (no actor id) when a revocation
  becomes contested.
- `representation_conflict_detected kind=%s` DEBUG; no mandate ids.
- Never log revocation provenance or decision/office refs.

### Tests

- `tests/unit/test_delegation_representation_revocation.py`: principal revoke,
  resign, collective-decision revoke, office-loss revoke, unauthorized contested
  revoke, expiry at boundary tick, `until_revoked` persistence, supersession of a
  claimed mandate, coexistence of two recognized mandates, conflict detection
  for all four kinds, retention after every transition.

### Acceptance Criteria

- Revocation and expiry are explicit, authorized, and retained.
- Conflicts remain unresolved and visible.
- No single representative is declared legitimate.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_revocation.py -q`
- Expected: pass.

## Task 9: Carry the ledger through cognition and runtime

### Intent

The ledger is useless unless the owner's cognition passes it forward and the
runner exports it for detached analysis. This task installs the carry chain with
owner checks and disabled-mode passthrough.

### Implementation Steps

1. In `src/agents/cognition/loop.py`, add `_prepare_representation` mirroring
   `_prepare_evidence` (2651-2864): set `_prepared_representation = None` at the
   start of every prepare; gate on `_representation_mode` (DISABLED returns
   without preparing); read `loop_input.snapshot.representation`; collect frames
   with `representation_frames_from_observation(observation,
   owner_id=loop_input.agent_id)`; call `apply_representation_update(...)`, then
   `detect_representation_conflicts`, `expire_representation_mandates`,
   `supersede_representation_mandates`, `resolve_representation_bases(...)`,
   and `enforce_representation_limits`; store `_prepared_representation`.
2. Add the prepare call beside the evidence call at 4926-4949, after
   organization concepts, collective decisions, offices, and formal rules have
   been prepared, because recognition bases read those same-owner sidecars.
3. Add late utterance recording beside `record_evidence_utterance` at
   5650-5658, gated on `_representation_mode is DETERMINISTIC` and the proposal
   value being a `RepresentationLedger`.
4. Add `representation: object | None = None` to `Perspective` in
   `src/agents/cognition/contracts.py` beside `evidence` (196) and to the
   `SubjectiveSnapshot` dataclass beside its `evidence` field; include it in
   `Perspective.to_snapshot()` so the loop's `loop_input.snapshot.representation`
   read is valid. The default keeps every existing constructor call valid.
5. In `src/simulation/perception.py`, add the
   `representation: object | None = None` kwarg to `build_perspective` and
   forward it into `Perspective(...)`; add `require_owner_representation` to
   `Perspective.__post_init__` for this field.
6. In `src/simulation/agent_runtime.py`, add the `_representation` slot, pass
   `representation=self._representation` in the perspective build
   (2324-2373), add `_commit_representation` modeled on `_commit_evidence`
   (1432-1460), and dispatch it at 2843-2865.
7. In `src/simulation/run_control.py`, add `representation: object | None = None`
   to `AgentRuntimeCheckpoint` and validate it with
   `require_owner_representation`.
8. In `src/simulation/runner_models.py`, add
   `representation_ledgers: tuple[RepresentationLedger, ...] = ()` to
   `SimulationRunnerResult` and validate ordered sequences and exact item type.
9. In `src/simulation/runner.py`, add `export_representation_ledgers` beside
   `export_evidence_ledgers` (5523-5536) and populate the result field in
   `finish_run`.
10. Export `RepresentationLedger` and `require_owner_representation` from
    `src/agents/cognition/__init__.py`, `CognitionRepresentationMode` from the
    same facade, and re-export the ledger from `src/simulation/__init__.py`
    beside the evidence-ledger import at line 3.

### Required Interfaces and Contracts

- Disabled mode clears the carried field to `None` at commit.
- Wrong type raises `TypeError("representation must be RepresentationLedger")`;
  foreign owner raises `AgentRuntimeError(OWNERSHIP, ...)`.
- Checkpoint and result validation reject unordered sequences exactly like the
  evidence fields at `runner_models.py:6711-6723`.
- `Perspective.to_snapshot()` round-trips the same ledger object identity (no
  copy), matching the evidence test pattern.

### Error Handling and Logging

- `INFO cognition_representation_mode mode=...` once per run build.
- `DEBUG representation_carry prepared=%s` (bool) in the loop.
- Checkpoint errors use existing safe codes; never include owner or mandate ids.

### Tests

- `tests/unit/test_delegation_representation_runtime.py`: disabled → no field;
  enabled → perspective carries the ledger; foreign-owner perspective rejected;
  checkpoint round-trip; result rejects list/set and wrong type; export returns
  one ledger per owner.
- `tests/unit/test_delegation_representation_determinism.py`: two identical runs
  produce identical ledger digests; ordering stable; no `hash(`, `uuid`, or
  `datetime.now` in the new modules.

### Acceptance Criteria

- The ledger reaches analysis through the real runner result.
- Owner checks fail closed at perspective, runtime, and checkpoint boundaries.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_runtime.py tests/unit/test_delegation_representation_determinism.py -q`
- Expected: pass; `uv run pytest tests/unit/test_evidence_testimony_runtime.py tests/unit/test_organization_agency_runtime.py -q` stays green.

## Phase Risks and Mitigations

- Risk: recognition drifts into a legitimacy oracle.
  Mitigation: the precedence table has no "truth" branch; tests assert a
  self-claim stays claimed and two recognized mandates coexist.
- Risk: a new ledger changes organization-enabled trajectories beyond the
  intended belief record.
  Mitigation: representation never biases command selection, prompts, or speech
  generation in V4-09; only frames emitted by agents create rows.
- Risk: recursive foreign-owner validation is skipped, leaking peer beliefs.
  Mitigation: copy the dispute guard and test a nested peer ledger rejection.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
