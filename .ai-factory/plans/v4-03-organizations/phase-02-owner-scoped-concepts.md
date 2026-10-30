# Phase 2: Owner-Scoped Organization Concepts

Plan: [index.md](index.md)
Tasks: 3-6
Depends on: Phase 1 / Task 2

## Objective

Implement the owner-scoped belief ledger that represents what one agent believes
about a recurring collective structure: perceived members, roles, shared goals,
referenced resources, procedures, records, internal commitments, identity
concepts, bounded history, and owner-local lineage. The ledger is enabled by the
owned `organizations` flag, reads only the owner's own observation and ledgers,
and never creates an objective organization, command, or peer-state lookup.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/institution_concepts.py` | `InstitutionConcept` 394-554; `InstitutionConceptLedger` 557-607; `apply_institution_concept_update` 1388-1470 | Closest owner-scoped concept ledger: bounded evidence, locked policy, identity minted at inception, owner-only inputs. |
| `src/agents/cognition/offices.py` | `OfficeConcept` 777-995; `OfficeConceptLedger` 997-1059; `apply_office_concept_update` 2477-2619 | Roles, duties, authority beliefs, occupants, revisions, succession, and predecessor ids. |
| `src/agents/cognition/institutional_memory.py` | `InstitutionalMemoryEntry` 654-793; `InstitutionalChannel` 453-547 | Procedure/role references and bounded provenance; role channels reference stable office ids. |
| `src/agents/cognition/institutional_decay.py` | `InstitutionDecayRecord` 443-545; `InstitutionDecaySample` 706-799 | Bounded per-concept history with absolute activity witnesses and raw samples. |
| `src/agents/cognition/collective_decisions.py` | `CollectiveProposal` 512-643; `CollectiveTopic` 163-171 | Shared-goal anchors and claimed courses; no binding resolution. |
| `src/agents/cognition/structured_commitments.py` | `CommitmentInterpretation` 88-202; `StructuredCommitmentLedger` 205-235 | Internal commitment references, parties, status, due semantics. |
| `src/agents/cognition/group_formation.py` | `GroupMembershipBelief` 315-372; `GroupConcept` 375-414 | Perceived membership and `WE`/`OUR_GROUP` self-identification; overlapping beliefs are legal. |
| `src/agents/cognition/institution_concepts.py` | `InstitutionPatternChannel` 148-156 | `role_recognition` and `procedure_recurrence` anchors. |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot` 714-750 | Snapshot field block that carries every owner ledger. |
| `src/agents/cognition/contracts.py` | `Perspective` 142-180; `to_snapshot` 537-570 | Cognition input contract and snapshot conversion. |
| `src/agents/cognition/loop.py` | `prepare` 4001+; stage order 4221-4252; `complete` 4702+; result 4906-4959 | Exact update/commit ordering. Organization concepts run after offices and before institutional memory. |
| `src/agents/cognition/configuration.py` | `CognitionLoopConfig` ledger fields 550-571; `build_cognitive_loop` 1358-1630; fingerprint 1330-1349 | Configuration and deterministic fingerprint wiring. |
| `src/agents/cognition/fork_state.py` | `CognitiveLoopForkState` 42-60 | Prepare-stage state that must survive a fork. |
| `src/simulation/agent_runtime.py` | slots 454-468; init 614-619; commit 1143-1329; finalization 2636-2654; restore 3144-3215; export 3274-3319 | Owner runtime commit/restore path. |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint` 589-617; validation 744-793 | Process-local checkpoint continuation. |
| `src/simulation/runner.py` | `from_config` 2025+; build loops 2589/6126/6495; result assembly 4900-4905; ledger exports 5238-5318 | Flag-to-cognition wiring and `RunnerResult` export. |
| `src/simulation/runner_models.py` | `RunnerResult` 6361-6373 | Tuple-of-ledger result surface consumed by analysis. |
| `src/simulation/perception.py` | `build_perspective` 113-350 | Owner-safe perspective construction. |
| `tests/unit/test_institution_concepts_*.py`, `test_offices_*.py`, `test_institutional_decay_*.py` | n/a | Test patterns for contracts, formation, runtime, checkpoints, and isolation. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/organization_concepts.py` | modify | Belief records, concept, ledger, revision/lineage records, update algorithm, identity minting. |
| `src/agents/cognition/organization_communication.py` | create | `org_v1` speech claim frames and utterance decoration in existing `Talk`/`Tell`. |
| `src/agents/cognition/__init__.py` | modify | Export the new ledger and frame symbols. |
| `src/agents/cognition/configuration.py` | modify | `CognitionOrganizationMode`, two ledger fields, validation, fingerprint, `build_cognitive_loop` forwarding. |
| `src/agents/cognition/loop.py` | modify | Slots, constructor, prepare hook, result field, fork-state integration. |
| `src/agents/cognition/models.py` | modify | `SubjectiveSnapshot.organization_concepts`, proposal/result fields and validation. |
| `src/agents/cognition/contracts.py` | modify | `Perspective.organization_concepts`, validation, `to_snapshot` forwarding. |
| `src/agents/cognition/fork_state.py` | modify | `prepared_organization_concepts` field. |
| `src/simulation/perception.py` | modify | `build_perspective` parameter and forwarding. |
| `src/simulation/agent_runtime.py` | modify | Slot, init, commit, preflight, finalization, restore, export. |
| `src/simulation/run_control.py` | modify | `AgentRuntimeCheckpoint.organization_concepts` and owner/type validation. |
| `src/simulation/runner.py` | modify | Enable the policy when the flag is on; export ledgers; assemble `RunnerResult`. |
| `src/simulation/runner_models.py` | modify | `RunnerResult.organization_concept_ledgers`. |
| `tests/unit/test_organization_contracts.py` | create | Record/concept/ledger invariants. |
| `tests/unit/test_organization_formation.py` | create | Deterministic formation/update, recognition, temporary expiry, overlap. |
| `tests/unit/test_organization_owner_lineage.py` | create | Continuation/split/merge/dissolution and acyclicity. |
| `tests/unit/test_organization_communication.py` | create | `org_v1` frames and explicit/disputed claims. |
| `tests/unit/test_organization_runtime.py` | create | Loop prepare/complete, checkpoint, fork, admission, runner flag wiring. |
| `tests/unit/test_organization_isolation.py` | create | No peer ledger, world state, command, or analysis reads. |

## Task 3: Define organization belief records and ledger invariants

### Intent

Provide the immutable, bounded data model that later formation and analysis code
consume. The model is deliberately explicit about the nine requested aspects and
about what each aspect is allowed to reference.

### Implementation Steps

1. In `organization_concepts.py`, add frozen slots dataclasses:
   - `OrganizationEvidence`: `evidence_id`, `ordinal`, `channel`, `ref`, `tick`,
     `anchor_digest`, `actor_id`.
   - `OrganizationMemberBelief`: `member_id`, `status`, `basis`,
     `temporal_scope`, `first_tick`, `last_tick`, `expires_tick`, `strength`,
     `channels`, `independently_evidenced`, `evidence_refs`.
   - `OrganizationRoleBelief`: `office_id`, `function`, `context_key`,
     `occupant_ids`, `status`, `first_tick`, `last_tick`, `evidence_refs`.
   - `OrganizationGoalBelief`: `anchor_kind`, `anchor_id`, `status`,
     `first_tick`, `last_tick`, `evidence_refs`.
   - `OrganizationResourceBelief`: `resource_kind`, `anchor_id`, `access_belief`,
     `first_tick`, `last_tick`, `evidence_refs`.
   - `OrganizationProcedureBelief`: `procedure_kind`, `anchor_id`, `recurrence`,
     `status`, `first_tick`, `last_tick`, `evidence_refs`.
   - `OrganizationRecordBelief`: `record_kind`, `anchor_id`, `integrity`,
     `custody_belief`, `first_tick`, `last_tick`, `evidence_refs`.
   - `OrganizationCommitmentBelief`: `commitment_id`, `role`, `counterpart_id`,
     `commitment_kind`, `status`, `due_tick`, `first_tick`, `last_tick`,
     `evidence_refs`.
   - `OrganizationIdentityBelief`: `label_token`, `conceptualization`, `stance`,
     `first_tick`, `last_tick`, `evidence_refs`.
   - `OrganizationWindowRecord`: `window_index`, `tick`, `status`,
     `temporal_scope`, `member_ids`, `role_anchor_ids`, `goal_anchor_ids`,
     `resource_anchor_ids`, `procedure_anchor_ids`, `record_anchor_ids`,
     `commitment_ids`, `identity_token`, `structural_signature`,
     `evidence_count`.
   - `OrganizationRevisionRecord`: `revision_id`, `kind`, `tick`,
     `before_digest`, `after_digest`, `reason_code`.
   - `OrganizationLineageRecord`: `lineage_id`, `kind`, `tick`, `from_ids`,
     `to_ids`, `evidence_digest`.
   - `OrganizationConcept`: `organization_id`, `owner_id`, `creation_tick`,
     `inception_digest`, `status`, `temporal_scope`, `strength`,
     `member_evidence_count`, `structural_channel_count`, `first_tick`,
     `last_tick`, `members`, `roles`, `goals`, `resources`, `procedures`,
     `records`, `commitments`, `identities`, `snapshots`, `revisions`,
     `lineage`, `predecessor_ids`, `notices`.
   - `OrganizationConceptLedger`: `owner_id`, `concepts`, `lineage`, `notices`,
     `policy_version`.
2. Enforce in each `__post_init__`:
   - exact enum types, not strings;
   - non-negative exact `int` ticks (reject `bool` and float);
   - `first_tick <= last_tick`; `expires_tick` only on `temporary` membership;
   - member ids, anchor ids, and evidence refs unique, non-empty, sorted;
   - `label_token` is `None` or a bounded token of at most 32 chars from
     `[a-z0-9][a-z0-9_-]*`; it is never free text and never a forbidden label;
   - strengths are finite floats in `[0, 1]`;
   - arrays respect every `OrganizationConceptPolicy` cap;
   - `OrganizationConcept.owner_id` matches the ledger owner;
   - `predecessor_ids` reference concepts in the same ledger;
   - a `temporary` member must have `expires_tick`; an `ongoing` member must not;
   - status/membership consistency: `recognized` requires at least
     `recognition_min_members` and `recognition_min_channels`; `disputed`
     requires at least one disputed member or identity conflict; `dissolved`
     requires no active goals and no successor; `retired` requires no active
     goals unless a `split`/`merge` lineage record transfers them to a
     successor.
3. Add `empty_organization_concept_ledger(owner_id, policy)` and
   `require_owner_organization_concepts(ledger, owner_id)`. A ledger of `None`
   means the channel is disabled; an empty typed ledger means enabled with no
   beliefs.
4. Add `organization_concept_digest(concept)` as canonical JSON over sorted
   fields for revision/lineage evidence. Do not store payload bodies.
5. Add `FORBIDDEN_ORGANIZATION_FIELD_NAMES` and reject any keyword argument or
   dynamic attribute named `government`, `church`, `corporation`, `army`,
   `university`, `guild`, `state`, `nation`, `polity`, `empire`, `tribe`,
   `treasury`, `bank`, `court`, `police`, `party`, `religion`, `ministry`,
   `department`, `firm`, `company`, `organization_type`, `authoritative_leader`,
   `current_decision`, `membership_roster`, or `global_registry`.
6. Tests in `tests/unit/test_organization_contracts.py`:
   - every aspect accepts a representative record and rejects a wrong enum;
   - duplicate/unsorted members and anchors are rejected;
   - tick regression and bool ticks are rejected;
   - temporary membership requires `expires_tick`; expiry before `first_tick` is
     rejected;
   - cap overflow is rejected with `organization_cap_exceeded`;
   - foreign-owner ledger is rejected with `organization_foreign_ledger`;
   - forbidden labels/fields are rejected;
   - `None` versus empty-ledger semantics are distinct.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class OrganizationConceptLedger:
    owner_id: str
    concepts: tuple[OrganizationConcept, ...]
    lineage: tuple[OrganizationLineageRecord, ...]
    notices: tuple[str, ...]
    policy_version: str
```

- No field stores a free-text description, speech body, memory content, or
  peer ledger.
- Every anchor is an opaque id: owner-local office/institution/convention/
  commitment id, or objective project/repository/artifact/region id.
- Resource and record anchors are references, not ownership. The ledger never
  contains a resource pool, treasury balance, or organization-owned item list.
- `policy_version` must equal `ORGANIZATION_CONCEPT_POLICY_VERSION`.

### Requirement Evidence

- Original request: "perceived membership", "roles", "shared goals", "shared
  resources", "procedures", "records", "internal commitments", "identity
  concepts", "historical lineage".
- Original request: "An Organization must not receive an independent omniscient
  cognition engine."
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-3: authorities stay separate;
  deterministic identity; frozen/defensive contracts.
- `.ai-factory/ARCHITECTURE.md` "Important V3 seams": offices and institution
  concepts are owner-scoped beliefs; duties are not permissions; repositories are
  objective containers and artifact membership is not agent membership.

### Error Handling and Logging

- Raise `OrganizationConceptError` with a stable code only.
- No DEBUG log in constructors; later update code logs `owner_id`, counts, and
  codes at DEBUG, never member ids or labels.

### Tests

- `uv run pytest tests/unit/test_organization_contracts.py -q`
- `uv run mypy src/agents/cognition/organization_concepts.py`
- Expected: pass/clean.

### Acceptance Criteria

- All nine organization aspects have a bounded belief type.
- Membership supports `explicit`, `perceived`, `disputed`, `unknown`, and
  `former`, plus `ongoing`/`temporary` scope.
- The ledger cannot represent an objective roster, treasury, organization-owned
  resource, or hard-coded organization class.

### Verification

- `uv run python -c "from agents.cognition.organization_concepts import OrganizationMembershipStatus as S; print([m.value for m in S])"`
- Expected: `['explicit', 'perceived', 'disputed', 'unknown', 'former']`

## Task 4: Add bounded organization claims in existing speech

### Intent

Explicit membership and identity claims must be self-authored, not inferred from
silence. Agents express them through existing `Talk`/`Tell` commands. This task
adds a bounded speech relation and utterance decoration; it adds no command,
event, observer semantic type, or free-text path. It lands before Task 5 so the
formation update can parse claims without depending on a later task.

### Implementation Steps

1. Create `src/agents/cognition/organization_communication.py`.
2. Define:
   - `ORGANIZATION_FRAME_SUBJECT = "org_v1"`;
   - `ORGANIZATION_PREDICATES = ("organization_claim",
     "organization_affirm", "organization_dispute", "organization_leave")`;
   - `ORGANIZATION_COMMUNICATION_POLICY_VERSION =
     "organization-communication.v1"`.
3. Define the frame grammar
   `org_v1:<predicate>:<label_token>:<stance>:<expires_tick>` where:
   - `label_token` is `none` or a 1-32 char `[a-z0-9][a-z0-9_-]*` token;
   - `stance` is one of `member`, `affiliated`, `outside`, `unknown`;
   - `expires_tick` is `none` or a non-negative decimal integer.
   Reject any other field count, free text, newline, colon, or overlong token
   with `organization_invalid_claim`.
4. Implement `encode_organization_claim(...)`,
   `parse_organization_claim(...)`, and
   `organization_claim_relation(...)`. Parsing is strict and returns a frozen
   `OrganizationClaim` dataclass.
5. Implement `organization_communicate_utterance(command, ledger)`:
   - only decorates an already-selected `Talk` or `Tell`;
   - never creates a command, changes its target, or changes delivery;
   - attaches at most one `org_v1` relation and preserves all existing
     relations;
   - returns the command unchanged when the ledger is `None`, empty, or has no
     active identity claim to express.
6. In `apply_organization_concept_update`, parse only `org_v1` relations from
   the owner's own observed communications and inbox. A claim authored by the
   owner is `explicit`; a claim authored by another agent about itself is
   `communicated_claim`; a claim about a third party is `perceived` only when
   corroborated by independent participation or a record.
7. Reject self-contradictory frames and non-addressed claims that would promote a
   member to `explicit`.
8. Tests in `tests/unit/test_organization_communication.py`:
   - encode/parse round trip for all four predicates and all stances;
   - malformed/overlong/free-text frames fail closed;
   - `organization_communicate_utterance` leaves `Wait`, `Give`, and other
     commands untouched;
   - a self claim yields `explicit`; a contrary self claim yields `disputed`;
   - `organization_leave` yields `former`, not deletion;
   - no new command class or event type exists.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class OrganizationClaim:
    predicate: str
    label_token: str | None
    stance: OrganizationIdentityStance
    expires_tick: int | None

def encode_organization_claim(claim: OrganizationClaim) -> str: ...
def parse_organization_claim(text: str) -> OrganizationClaim: ...
def organization_communicate_utterance(command: object, ledger: object | None) -> object: ...
```

- The relation is carried inside existing `Talk`/`Tell` relations, following the
  collective-decision and institutional-memory precedent.
- No person id, member set, evidence list, or resource id is encoded in the
  frame.
- Claims are testimony, never world facts or membership authority.

### Requirement Evidence

- Original request: membership may be "explicit" and "disputed"; identity
  concepts are required.
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts":
  `Talk`/`Ask`/`Tell` prove delivery only; declared lineage is testimony.
- `.ai-factory/ARCHITECTURE.md` "Important V3 seams": collective decisions and
  institutional memory travel as bounded relations inside existing speech.

### Error Handling and Logging

- `OrganizationClaimError` (subclass of `OrganizationConceptError`) with code
  `organization_invalid_claim`; never echo the rejected text.
- DEBUG `organization_claim predicate=%s stance=%s` at most; never the label
  token or recipient id.

### Tests

- `uv run pytest tests/unit/test_organization_communication.py -q`
- `uv run pytest tests/architecture/test_v4_architecture_invariants.py -q -k command`
- Expected: pass; command count remains 43.

### Acceptance Criteria

- Explicit membership has a self-authored, bounded speech path.
- The feature adds no command, event, observer semantic type, or free-text
  payload.
- Malformed claims fail closed without leaking content.

### Verification

- `uv run python -c "from agents.cognition.organization_communication import ORGANIZATION_PREDICATES; print(ORGANIZATION_PREDICATES)"`
- Expected: the four declared predicates.

## Task 5: Implement deterministic formation, recognition, revisions, and owner-local lineage

### Intent

Turn the owner's existing evidence into organization beliefs without reading peer
state or inventing an organization actor. Formation must be deterministic under
input permutation and must preserve overlap, dispute, temporary membership, and
bounded history. It consumes the bounded `org_v1` claims parsed by Task 4.

### Implementation Steps

1. Add `apply_organization_concept_update(...)` with this signature:

```python
def apply_organization_concept_update(
    *,
    owner_id: str,
    tick: int,
    observation: object,
    prior: OrganizationConceptLedger | None,
    institution_concepts: object | None,
    offices: object | None,
    group_formation: object | None,
    collective_decisions: object | None,
    structured_commitments: object | None,
    social_conventions: object | None,
    policy: OrganizationConceptPolicy,
) -> OrganizationConceptLedger: ...
```

2. Reject a foreign owner or a foreign ledger with
   `organization_foreign_ledger`. Read only the owner's own prepared ledgers and
   the owner's own `observation`; never look up another owner's runtime.
3. Extract membership evidence deterministically:
   - self-identification from the owner's own `GroupMembershipBelief` with
     `stance in {WE, OUR_GROUP}` and from the owner's identity claims;
   - observed participation from the owner's observation of collective project
     contributions, public-good acts, repository deposits/retrievals, and
     migration co-presence;
   - role occupancy from the owner's own `OfficeConcept` occupants;
   - collective participation from the owner's own `CollectiveProposal`
     positions;
   - communicated claims from the owner's own inbox/observed communications with
     `org_v1` relations;
   - record references from observed durable records and repositories;
   - inference from repeated co-presence and shared anchors.
   Each member belief records its basis and channels. `explicit` requires a
   self-authored claim; `perceived` requires participation/role/collective
   evidence; `unknown` is used when an anchor references a person without direct
   membership evidence; `disputed` requires contradictory evidence; `former` is
   used after explicit leave or expiry.
4. Extract structural anchors:
   - roles: owner-local office ids with function/context and occupant ids;
   - goals: objective collective-project/public-good ids and owner-local
     collective proposal ids;
   - resources: observed repository/artifact/stored-resource/shelter/territory
     ids with an access belief;
   - procedures: owner-local institution concept ids with
     `procedure_recurrence > 0`, plus owner-local social-convention ids;
   - records: observed artifact/repository ids with integrity and custody belief;
   - commitments: owner-local commitment ids where the owner or a perceived
     member is a party;
   - identity: the owner's bounded label token and stance.
5. Match evidence to an existing concept with this ordered rule:
   - same non-empty identity label token and member Jaccard >= `merge_jaccard`;
   - member Jaccard >= `merge_jaccard` and at least one shared structural anchor;
   - the same owner-local office anchor and at least one shared member.
   Otherwise create a new concept. If two existing concepts match each other,
   emit a `merge` lineage record and create one successor concept with a new
   `orgc-` id; transfer the predecessors' active goals and anchors to the
   successor, mark the predecessors `retired` with `reason_code="merged"`, and
   never mark a predecessor `dissolved`. If one concept's evidence partitions
   into two disjoint sets each with at least `recognition_min_members` and one
   structural anchor, create two successors, emit a `split` record, transfer the
   parent's anchors by containment, and mark the parent `retired` with
   `reason_code="split"`.
6. Mint the id only at creation:
   `organization_concept_id(owner_id, creation_tick, sorted_founding_members,
   sorted_structural_anchors)`. Continuation inherits the id. A merge result and
   each split child receive new ids.
7. Compute `structural_channel_count` as the number of non-empty aspect families
   among roles, goals, resources, procedures, records, commitments, identities.
   Compute `strength` as the quantized mean of member support and structural
   coverage, capped at `1.0`.
8. Status transition:
   - `candidate` until `member_evidence_count >= recognition_min_evidence`,
     `structural_channel_count >= recognition_min_channels`, and
     `strength >= recognition_floor`;
   - `recognized` when all three hold and no dispute;
   - `disputed` when any member is disputed or identity stance conflicts with
     membership;
   - `dissolved` when no member/anchor evidence for `window_ticks` and no active
     goal;
   - `retired` after `2 * window_ticks` without evidence or after an explicit
     owner `organization_leave` claim with no contrary evidence.
9. Append an `OrganizationWindowRecord` when
   `tick % policy.window_ticks == 0`, when the structural signature changes, or
   when the concept is created/dissolved. Keep at most `max_snapshots`, dropping
   the oldest record and recording a `history_truncated` notice.
10. Append `OrganizationRevisionRecord` for every changed aspect family with
    `before_digest`/`after_digest`; append `OrganizationLineageRecord` for
    `emerged` on creation, `continued` on unchanged continuation,
    `transformed` on a structural change, `split`, `merge`, `dissolved`, and
    `revived`. Validate that lineage is forward-only and acyclic within the
    ledger.
11. Apply temporary expiry: at `tick >= expires_tick`, a member without renewed
    evidence becomes `former`; the concept remains if other evidence exists and
    becomes `dissolved` if none does. A temporary claim without an explicit
    expiry uses `tick + policy.temporary_default_ticks`.
12. Emit notices only as stable codes: `foreign_owner`, `missing_institution`,
    `missing_office`, `unresolved_anchor`, `history_truncated`,
    `membership_conflict`, `temporary_expired`.
13. Tests in `tests/unit/test_organization_formation.py` and
    `tests/unit/test_organization_owner_lineage.py`:
    - same inputs in permuted order produce byte-identical canonical ledgers;
    - repeated ticks are idempotent when evidence is unchanged;
    - explicit claim + contrary observation yields `disputed`;
    - one person in two concepts remains in both (overlap is not collapsed);
    - temporary claim becomes `former` at expiry, then `dissolved` when alone;
    - split creates two new ids and a `split` record; merge creates one new id and
      a `merge` record; continuation keeps the id;
    - lineage is acyclic and monotone in ticks;
    - a ledger never references another owner's ledger;
    - every `OrganizationMembershipStatus` value is reachable through the public
      update path, not only through a direct constructor;
    - every structural aspect family (role, goal, resource, procedure, record,
      commitment, identity) is reachable through the public update path;
    - no enum branch is dead: membership `explicit`, `perceived`, `disputed`,
      `unknown`, `former`; concept `candidate`, `recognized`, `disputed`,
      `dissolved`, `retired`; and all six lineage kinds each have an end-to-end
      fixture.

### Required Interfaces and Contracts

- `apply_organization_concept_update` returns a new frozen ledger; it never
  mutates `prior`.
- The function accepts `None` for any absent V3 evidence source. Absence yields
  no invented members or anchors and a `missing_*` notice at most.
- No `WorldState`, `WorldEvent`, `PhysicalRules`, `AgentBody`, `WorldEngine`,
  `ActionSubmission`, `AgentCommand`, or `MetricDocument` input is accepted.
- No RNG, `hash()`, UUID, or wall-clock. All ordering is lexical over string ids
  and numeric ticks.
- Determinism digest is canonical JSON over the finalized ledger, using sorted
  keys, compact separators, UTF-8, and one trailing newline.

### Requirement Evidence

- Original request: "Membership may be: explicit, disputed, unknown, overlapping,
  temporary."
- Original request: "All organization activity ultimately occurs through agents,
  records, roles and recognized procedures."
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 2: deterministic seeds, IDs, and
  logical clocks.
- `.ai-factory/ARCHITECTURE.md` "Important V3 seams": institution recognition
  requires recurring function and independent roots; roles are beliefs, not
  permissions; no objective office registry.

### Error Handling and Logging

- Invalid owner/type/tick/cap input raises a stable `OrganizationConceptError`.
- WARN `organization_evidence_incomplete owner_id=%s code=%s` when a required
  source is absent; never include anchor ids or member ids.
- DEBUG `organization_update owner_id=%s concepts=%s created=%s merged=%s
  split=%s dissolved=%s tick=%s`.
- Do not log labels, member sets, evidence refs, or payloads.

### Tests

- `uv run pytest tests/unit/test_organization_formation.py tests/unit/test_organization_owner_lineage.py -q`
- `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1` runs must produce the same digest.
- Hypothesis property: permuting member/anchor input order does not change the
  canonical ledger or the concept id.

### Acceptance Criteria

- Formation is deterministic, bounded, owner-local, and free of hard-coded
  organization classes.
- Overlap, dispute, unknown, temporary, and former membership are representable
  and tested.
- Split/merge/continuation produce valid owner-local lineage with new ids where
  required.

### Verification

- `uv run python -c "import hashlib; from agents.cognition.organization_concepts import organization_concept_id as f; print(f('a1', 10, ['b','a'], ['role:x'])[:4])"`
- Expected: `orgc`
- `uv run pytest tests/unit/test_organization_formation.py -q -k determinism`
- Expected: pass.

## Task 6: Integrate the ledger through cognition, checkpoints, and the runner

### Intent

Make the organization ledger a first-class owner-scoped cognition value without
changing default behavior, wire formats, or world authority. The existing
`organizations` flag is the only enablement seam.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`:
   - add `CognitionOrganizationMode` with `DISABLED` and `DETERMINISTIC`;
   - add `organization_concept_mode` and `organization_concept_policy` to
     `CognitionLoopConfig`;
   - in `__post_init__`, enforce exact enum/type; `DISABLED` forces policy
     `None`; `DETERMINISTIC` with `None` installs
     `default_organization_concept_policy()`; no cross-mode prerequisite is
     required because absent evidence is a valid empty ledger;
   - include `organization_concept_mode` and `organization_concept_policy_version`
     in fingerprint material only when the mode is enabled;
   - forward both through `build_cognitive_loop`.
2. In `src/agents/cognition/loop.py`:
   - add slots `_organization_concept_mode`, `_organization_concept_policy`,
     `_prepared_organization_concepts`;
   - add constructor parameters and the same validation pattern as institutional
     memory/decay;
   - insert `_prepare_organization_concepts(...)` in `prepare()` after
     `_prepare_office_concepts` (4230-4236) and before
     `_prepare_institutional_memory` (4246-4252); it reads the prior ledger from
     the snapshot and the freshly prepared institution/office/collective/group
     ledgers;
   - when disabled, return `None` and clear the prepared sidecar;
   - set `organization_concepts=self._prepared_organization_concepts` in
     `CognitiveLoopResult`.
3. In `src/agents/cognition/models.py`:
   - add `organization_concepts: object | None = None` to
     `SubjectiveSnapshot`, `CognitiveLoopProposal`, and `CognitiveLoopResult`;
   - validate exact owner/type at each boundary using the same helper pattern as
     `office_concepts`.
4. In `src/agents/cognition/contracts.py`:
   - add `organization_concepts` to `Perspective`;
   - validate it;
   - forward it in `to_snapshot()`. Add a parity test that
     `Perspective.to_snapshot().organization_concepts` is the same object.
5. In `src/agents/cognition/fork_state.py`:
   - add `prepared_organization_concepts` to `CognitiveLoopForkState`;
   - keep `COGNITIVE_LOOP_FORK_STATE_VERSION = "cognitive-loop-fork-state-v1"`:
     the field is optional and process-local, so old v1 states with the field
     absent remain valid;
   - include it in `export_fork_state`/`restore_fork_state` in `loop.py`.
6. In `src/simulation/perception.py`:
   - add an `organization_concepts` parameter to `build_perspective` and forward
     it to `Perspective`.
7. In `src/simulation/agent_runtime.py`:
   - add `_organization_concepts` to slots and initialize to `None`;
   - add `_commit_organization_concepts(ledger, tick)` with owner/type
     validation; `None` clears the value only when the mode is disabled;
   - call `_commit_organization_concepts` after `_commit_office_concepts` and
     before `_commit_institutional_memory` in the finalization order;
   - include the value in perspective construction, checkpoint export, checkpoint
     restore, and `export_runtime_checkpoint`.
8. In `src/simulation/run_control.py`:
   - add `organization_concepts` to `AgentRuntimeCheckpoint`;
   - validate owner/type with `require_owner_organization_concepts`;
   - reject a checkpoint whose organization ledger is owned by another agent.
9. In `src/simulation/runner.py`:
   - at all three `build_cognitive_loop` sites (2589, 6126, 6495), set
     `organization_concept_mode=DETERMINISTIC` and the default policy when
     `runner_config.v4_capability_flags.organizations` is true; otherwise leave
     `DISABLED`;
   - in `SimulationRunner.apply_runtime_checkpoint`, before
     `restore_runtime_cursor`, add an organization preflight block beside the
     institutional-memory/decay blocks (4571-4685): require exact
     `OrganizationConceptLedger` type, require
     `ledger.owner_id == state.agent_id`, and reject a ledger when the target
     runtime's loop mode is `DISABLED`; never mutate the engine before this
     validation passes;
   - add `export_organization_concept_ledgers()` beside
     `export_institutional_decay_ledgers()` and include it in `RunnerResult`
     assembly (4900-4905).
10. In `src/simulation/runner_models.py`:
    - add `organization_concept_ledgers: tuple[object, ...] = ()` to
    `RunnerResult`.
11. Do not modify `AgentCognitionSpec`, `runner-config-v56` keys, or
    `runner-config-v57`. Do not add a `NewAgentInitialization` profile: a newly
    admitted agent starts with an empty ledger because the runtime initializes
    the field to `None` and the enabled loop creates an empty ledger on first
    prepare.
12. Tests in `tests/unit/test_organization_runtime.py` and
    `tests/unit/test_organization_isolation.py`:
    - flag off: no ledger, no policy, fingerprint unchanged versus the V4-01
      baseline;
    - flag on: every agent gets the deterministic policy; empty evidence yields
      an empty typed ledger, not `None`;
    - loop prepare reads prior owner ledger and never a peer ledger;
    - the real `SimulationRunner.export_runtime_checkpoint()` →
      `apply_runtime_checkpoint()` path round-trips the ledger with per-owner
      parity and rejects a foreign-owner ledger or a ledger supplied to a
      disabled-owner runtime;
    - `CognitiveLoopForkState` restores a v1 state with
      `prepared_organization_concepts=None` and a v1 state with a prepared
      ledger;
    - admission of a newborn yields an empty ledger and copies no content;
    - runner result exports one ledger per owner;
    - no `WorldState`, `WorldEngine`, `ActionSubmission`, or `AgentCommand`
      symbol appears in the organization modules.

### Required Interfaces and Contracts

```python
class CognitionOrganizationMode(StrEnum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"

@dataclass(frozen=True, slots=True)
class CognitionLoopConfig:
    ...
    organization_concept_mode: CognitionOrganizationMode = (
        CognitionOrganizationMode.DISABLED
    )
    organization_concept_policy: OrganizationConceptPolicy | None = None
```

- `organization_concepts=None` means disabled; an empty
  `OrganizationConceptLedger` means enabled with no beliefs.
- The new field is process-local. It is not serialized to `runner-config`,
  `runner-result`, `observed` wire schemas, or the event store.
- `RunnerResult.organization_concept_ledgers` is a tuple of owner ledgers, one
  per runtime, in agent-id order.
- No stop selector, permission check, admission rule, or `WorldEngine` operation
  reads the ledger.

### Requirement Evidence

- Original request: "An Organization must not receive an independent omniscient
  cognition engine. All organization activity ultimately occurs through agents,
  records, roles and recognized procedures."
- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime": cognition gets
  owner-safe perspectives only; no `WorldState`, token, or all-agent batch.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 4: optional channels default off
  and leave off-path behavior unchanged.
- `.ai-factory/ARCHITECTURE.md` "Requirements for later changes" 4: subjective
  checkpoints stay outside the objective fold.

### Error Handling and Logging

- Invalid mode/policy raises `ValueError` with a stable code and no payload.
- `organization_concepts_carried owner_id=%s concept_count=%s tick=%s` at DEBUG.
- `organization_concepts_restore_rejected reason_code=foreign_owner` at WARN.
- Never log member ids, labels, evidence refs, or resource ids.

### Tests

- `uv run pytest tests/unit/test_organization_runtime.py tests/unit/test_organization_isolation.py -q`
- `uv run pytest tests/unit/test_runner_config_v56.py -q`
- `uv run pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py -q`
- Expected: pass; flags-off trajectories unchanged.

### Acceptance Criteria

- The ledger is carried through perspective, loop, proposal/result, checkpoints,
  fork state, runtime, and `RunnerResult`.
- Default configurations and V1-V3 regression profiles are unchanged.
- No peer ledger, world authority, command, event, or migration is introduced.

### Verification

- `uv run python -c "from agents.cognition.configuration import CognitionOrganizationMode as M; print([m.value for m in M])"`
- Expected: `['disabled', 'deterministic']`
- `uv run pytest tests/unit/test_organization_runtime.py -q -k checkpoint`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: the organization ledger reads a peer ledger to infer membership.
  Mitigation: the update signature accepts only the owner's prepared ledgers and
  observation; isolation tests and Task 19 AST checks enforce this.
- Risk: adding a snapshot field silently breaks an existing checkpoint.
  Mitigation: follow the institutional-decay pattern, default the field to
  `None`, and test old-checkpoint restore behavior.
- Risk: the flag changes default trajectories when off.
  Mitigation: disabled mode installs no policy and adds no fingerprint key; run
  the V1/V2 regression gates.
- Risk: the ledger becomes a de facto objective roster or treasury.
  Mitigation: all fields are beliefs and references; no resource balances, no
  member authority, no organization-owned item list; Task 19 forbids actor and
  registry symbols.
- Risk: temporary membership silently becomes permanent.
  Mitigation: expiry is explicit and tested.

## Phase Completion Checklist

- Every Task 3-6 acceptance criterion is met.
- Contract, formation, communication, runtime, and isolation tests pass.
- No new command, event, observer semantic type, runner schema, or migration was
  added.
- `index.md` checkboxes are updated immediately after verified completion.
