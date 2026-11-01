# Phase 2: Owner-Scoped Operational Beliefs

Plan: [index.md](index.md)
Tasks: 3-8
Depends on: Phase 1 / Tasks 1-2

## Objective

Implement the operational sidecar ledger: immutable records for control,
storage, record keeping, admission, departure, role assignment, procedure
actions, internal commitments, decisions, and actions; a bounded `org_op_v1`
speech frame; a deterministic owner-local update that records provenance; the
existing-speech/command wiring; and the full cognition/runtime/checkpoint/runner
carry path. The concept ledger from V4-03 is not modified.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/organization_concepts.py` | member/role/goal/resource/procedure/record/commitment beliefs 668-971; `OrganizationConcept` 1203-1480; `_collect_observation` 1991-2075; `apply_organization_concept_update` 2880-3175 | Operations reference these anchors and follow the same owner-only, deterministic update style. |
| `src/agents/cognition/organization_communication.py` | policy 44-57; `OrganizationClaim` 95-118; encode/parse 120-199; utterance decorator 241-288 | The new frame follows the same bounded-relation pattern and the existing `org_v1` frame stays unchanged. |
| `src/agents/cognition/possession_legitimacy.py` | `POSSESSION_DOCTRINES` import 19; ledger 78-137; `apply_possession_legitimacy_update` 252-288 | Provides the subjective legitimacy vocabulary (`group_owns`, `first_claimant_owns`, etc.); never moves items. |
| `src/agents/cognition/offices.py` | `OfficeAuthorityKind` 213-220; `OfficeConcept` 777-995; `preferred_occupant` 951-982 | Role authority is a revisable belief; it never becomes a permission. |
| `src/agents/cognition/collective_decisions.py` | proposals 512-644; positions 646-703; outcomes 813-862; ledger 1029-1180 | Decision authority and support/oppose counts come from the owner's decision ledger. |
| `src/agents/cognition/structured_commitments.py` | `CommitmentInterpretation` 88-202; ledger 205-234 | Internal commitments reference owner interpretations; no enforcement. |
| `src/agents/cognition/deliberation.py` | `_reputation_testimony_command` 767-1540; decoration block 1170-1353 | The existing speech decoration chain is the exact integration point; V4-03 claims were never wired here. |
| `src/agents/cognition/loop.py` | state slots 345-370; constructor 470-500; organization validation 890-915; `_prepare_organization_concepts` 2279-2336; prepare sequence 4309-4349; proposal 4680-4717; result 5020-5058 | The operation ledger must be prepared after concepts and carried through proposal/result. |
| `src/agents/cognition/fork_state.py` | `prepared_organization_concepts` 60; `state_format_version` 61 | Add one optional process-local field; keep `cognitive-loop-fork-state-v1`. |
| `src/agents/cognition/contracts.py` | `Perspective` 142-191; validation 401-408; `to_snapshot()` 577 | Add the owner-scoped operation ledger to the perspective and snapshot parity. |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot` 715-759; `CognitiveLoopProposal` 3895-3934; `CognitiveLoopResult` 4220-4256 | Three additive optional fields. |
| `src/simulation/agent_runtime.py` | slots 460-490; `_commit_organization_concepts` 1273-1300; perspective build 2164-2208; commit sequence 2678-2683; restore 3230-3239; export 3338-3345 | Mirror the concept ledger carry path for operations. |
| `src/simulation/perception.py` | `build_perspective` 113-160; `Perspective(...)` 322-348 | The trusted perspective assembly must accept the operation ledger explicitly. |
| `src/simulation/runner.py` | checkpoint validation 4697-4718; result assembly 4949; export 5315-5328 | Validate owner/mode and export the new ledger tuple. |
| `src/simulation/runner_models.py` | `organization_concept_ledgers` 6374, 6644-6653 | Add `organization_operation_ledgers` as a sibling detached tuple. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/organization_operations.py` | modify | Record dataclasses, ledger, evidence collection, deterministic update. |
| `src/agents/cognition/organization_operations_communication.py` | create | `org_op_v1` frame encode/parse/relation/utterance. |
| `src/agents/cognition/organization_operations_actions.py` | create | Domain-to-command allowlist, support classification, commitment follow-through recognition. |
| `src/agents/cognition/deliberation.py` | modify | Wire `org_v1` and `org_op_v1` decoration into the existing speech chain. |
| `src/agents/cognition/models.py` | modify | Add `organization_operations` to snapshot/proposal/result. |
| `src/agents/cognition/contracts.py` | modify | Add and validate `Perspective.organization_operations`; copy in `to_snapshot()`. |
| `src/agents/cognition/loop.py` | modify | Prepare the ledger after concepts; carry it in proposal/result; fork-state fields. |
| `src/agents/cognition/fork_state.py` | modify | Add `prepared_organization_operations`. |
| `src/simulation/agent_runtime.py` | modify | Commit, restore, export, and expose the ledger. |
| `src/simulation/perception.py` | modify | Accept/pass `organization_operations` in `build_perspective`. |
| `src/simulation/runner.py` | modify | Validate and export the ledger tuple. |
| `src/simulation/runner_models.py` | modify | Add `organization_operation_ledgers`. |
| `src/simulation/run_control.py` | modify | Add and validate `AgentRuntimeCheckpoint.organization_operations`. |
| `src/agents/cognition/__init__.py` | modify | Re-export records, ledger, update, communication, and action helpers. |
| `tests/unit/test_organization_operations_ledger.py` | create | Record/ledger validation and caps. |
| `tests/unit/test_organization_operations_communication.py` | create | Frame grammar and deliberation decoration. |
| `tests/unit/test_organization_operations_update.py` | create | Evidence mapping, disagreement, provenance, orphaning. |
| `tests/unit/test_organization_operations_actions.py` | create | Command allowlist and commitment follow-through. |
| `tests/unit/test_organization_operations_runtime.py` | create | Perspective/loop/runtime/checkpoint/runner carry path. |

## Task 3: Define operational records and ledger invariants

### Intent

Provide the immutable record types that every later layer reads. The ledger is a
sidecar keyed by `orgc-` ids so the V4-03 concept digest, identity, and lineage
semantics do not change.

### Implementation Steps

1. In `organization_operations.py`, add `OrganizationOperationEvidence`:
   - `evidence_id: str` (`orgev-`), `ordinal: int`, `source: str` (one of
     `observation`, `communication`, `owner_ledger`, `memory`), `ref: str`,
     `tick: int`, `actor_id: str | None`, `anchor_digest: str` (64 hex).
   Every record below must call `_reject_forbidden_fields(type(self))` from the
   concept module and reuse its validators (`require_organization_tick`,
   `_require_enum`, `_require_bool`, `_require_unit`, `_require_count`,
   `_require_hex64`, `_require_reason_token`, `_require_label_token`) where the
   type matches; do not duplicate looser validators.
2. Add `OrganizationControlBelief`:
   - `domain: OrganizationOperationDomain` (only `resource_control`, `storage`,
     `record_keeping`);
   - `anchor_kind: str` (one of `item`, `resource`, `artifact`, `structure`,
     `repository`, `unknown`);
   - `anchor_id: str`;
   - `stance: OrganizationControlStance`;
   - `authority_basis: OrganizationAuthorityBasis`;
   - `legitimacy_doctrine: str` (an `ORGANIZATION_LEGITIMACY_DOCTRINES` token);
   - `decision_ref: str | None` (`orgd-` or `None`);
   - `role_ref: str | None` (owner-local `office_id` or `None`);
   - `first_tick`, `last_tick`;
   - `owner_support_count: int` (1..32), `contest_count: int` (0..32);
   - `evidence_refs: tuple[str, ...]` (≤8, sorted unique).
3. Add `OrganizationAdmissionBelief` with `member_id`, `stance`
   (`OrganizationAdmissionStance`), `authority_basis`, `role_ref`, `decision_ref`,
   `temporal_scope` (`OrganizationTemporalScope`), `expires_tick`, `first_tick`,
   `last_tick`, support/contest, evidence refs. Temporary admission requires
   `expires_tick`; non-temporary forbids it.
4. Add `OrganizationDepartureBelief` with `member_id`, `stance`
   (`OrganizationDepartureStance`), `authority_basis`, `decision_ref`, span,
   support/contest, evidence refs.
5. Add `OrganizationAssignmentBelief` with `office_id`, `occupant_id`, `stance`
   (`OrganizationAssignmentStance`), `authority_basis`, `decision_ref`, span,
   support/contest, evidence refs.
6. Add `OrganizationProcedureActionBelief` with `procedure_ref`, `command_kind`
   (closed token from the existing command tag vocabulary), `actor_id`,
   `outcome` (`OrganizationOperationOutcome`), `authority_basis`, `decision_ref`,
   span, support/contest, evidence refs.
7. Add `OrganizationCommitmentOperationBelief` with `commitment_id`, `role`
   (`OrganizationCommitmentRole`), `counterpart_id`, `stance`
   (`OrganizationCommitmentStance`), `authority_basis`, `decision_ref`,
   `due_tick`, span, support/contest, evidence refs.
8. Add `OrganizationDecisionRecord` with `decision_id`, `domain`, `act`,
   `actor_id`, `target_id: str | None`, `anchor_kind`, `anchor_id`,
   `authority_basis`, `stance` (`supported`, `contested`, `unknown`),
   `support_count`, `oppose_count`, `provenance_code`, `tick`, evidence refs.
9. Add `OrganizationActionRecord` with `action_id`, `decision_id: str | None`,
   `domain`, `act` (`OrganizationOperationAct`), `actor_id`, `command_kind`,
   `anchor_kind`, `anchor_id`, `outcome`, `provenance_code`, `tick`, evidence
   refs.
10. Add `OrganizationOperationalConcept`:
    - `organization_id: str` (`orgc-`), `owner_id: AgentId`,
      `status: str` (`active`, `dissolved`, `orphaned`), `first_tick`, `last_tick`;
    - tuples: `controls`, `admissions`, `departures`, `assignments`, `procedures`,
      `commitments`, `decisions`, `actions`, `notices`.
11. Add `OrganizationOperationLedger` with `owner_id`, `concepts`, `notices`,
    and `policy_version` (default `ORGANIZATION_OPERATION_POLICY_VERSION`).
    Validate:
    - `policy_version` equals the module constant;
    - concepts sorted by `organization_id`, unique, owner-matched;
    - every concept id is a valid `orgc-` id;
    - each tuple is capped by `OrganizationOperationPolicy`; controls are capped
      at 16 per domain and 32 total; the sum of all record tuples across all
      concepts is ≤ `max_total_records`;
    - decision/action ids are unique; every `decision_ref` points to a decision in
      the same concept; every `action.decision_id` is either `None` or exists;
    - every record span is ordered; decisions/actions are tick-monotone in append
      order; evidence refs are sorted unique and within the per-record cap;
    - `notices` come from a closed set:
      `operations_truncated`, `operations_orphaned`, `authority_unresolved`,
      `contest_unresolved`, `operation_expired`, `operation_anchor_unresolved`.
12. Add `empty_organization_operation_ledger(owner_id, policy=None)` and
    `require_owner_organization_operations(value, owner_id, *, field_name)`.
13. Re-export all public record types.

### Required Interfaces and Contracts

- The ledger is keyed by `orgc-`; it never mints a second owner-local organization
  id.
- `decision_ref`/`action_id` are owner-local provenance ids; they are never
  published unchanged.
- `owner_support_count` counts this owner's evidence only. It is not a peer count
  and must not be described as popularity or consensus.
- `contest_count` counts contradictory owner evidence; it is not a vote.
- No record has a `truth`, `verified`, `owner`, `property`, `title`, `deed`, or
  `permission` field.
- The module must not import `WorldState`, `WorldEngine`, `ActionSubmission`,
  `AgentCommand`, event stores, analysis, persistence, API, or infrastructure.

### Requirement Evidence

- Original Request: "Keep objective physical possession separate from
  subjective/legal ownership"; records store beliefs, not custody.
- Original Request: "Record provenance of decisions and actions"; decision/action
  records carry authority and evidence.
- V4-03 `OrganizationResourceBelief` docstring: "never an owned pool".

### Error Handling and Logging

- Validation raises `OrganizationOperationError` with a stable code; rejected
  values are never echoed.
- DEBUG only: `organization_operation_ledger_constructed owner_id=%s concepts=%s`
  plus one count per record family. No anchor values, labels, or payloads.

### Tests

- `tests/unit/test_organization_operations_ledger.py`:
  - each record family validates its closed status/authority vocabularies;
  - every record rejects forbidden fields (`truth`, `owner`, `property`, `title`,
    `deed`, `permission`) through `_reject_forbidden_fields`;
  - temporary admission requires expiry; non-temporary forbids it;
  - decision/action ids are unique and references resolve;
  - caps reject the 33rd control, 17th assignment, 65th action, and 9th evidence
    ref;
  - the ledger rejects more than 256 total records across concepts;
  - tick regression and unsorted tuples fail;
  - notices are closed (including `operation_expired`);
  - `require_owner_organization_operations` rejects a foreign owner;
  - no class name ends with `Command` or `Event`.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_ledger.py -q`

### Acceptance Criteria

- The ledger is immutable, bounded, owner-scoped, and keyed by `orgc-`.
- Objective possession is absent from every record.
- Provenance ids are deterministic and owner-local.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_ledger.py -q`
- Expected: pass.

## Task 4: Add bounded `org_op_v1` operational speech frames

### Intent

Let owners express admission, departure, role assignment, control, procedure, and
commitment claims inside ordinary `Talk`/`Tell` without a new command or free
text. Receivers treat the frame as testimony, never as authority.

### Implementation Steps

1. Create `organization_operations_communication.py` with:
   - `ORGANIZATION_OPERATION_COMMUNICATION_POLICY_VERSION =
     "organization-operations-communication.v1"`;
   - `ORGANIZATION_OPERATION_FRAME_SUBJECT = "org_op_v1"`;
   - predicate map keyed by `OrganizationOperationAct`:
     `admit → org_admit`, `depart → org_depart`, `assign → org_assign`,
     `remove → org_remove`, `authorize_control → org_authorize`,
     `revoke_control → org_revoke`, `invoke_procedure → org_invoke`,
     `declare_commitment → org_commit`, `fulfill_commitment → org_fulfill`,
     `record_decision → org_record`.
2. Define `OrganizationOperationClaim` with `act`, optional `label_token`
   (≤32, same grammar as `org_v1` and rejected when
   `organization_label_is_forbidden` returns true), optional `target_ref`
   (16 hex), `anchor_kind` (closed token: `item`, `resource`, `artifact`,
   `structure`, `repository`, `collective_project`, `member`, `unknown`), optional
   `anchor_ref` (16 hex; `none` for `unknown`), optional `authority_ref` (16 hex
   over a public role signature or decision content), `stance`, and optional
   `expires_tick`. Owner-local office/commitment anchors are not carried as
   cross-owner refs; a role-assignment claim carries the public role signature in
   `authority_ref` and `anchor_kind="unknown"`. The
   allowed stance family is fixed by the act:
   - `admit` → `OrganizationAdmissionStance`;
   - `depart` → `OrganizationDepartureStance`;
   - `assign`/`remove` → `OrganizationAssignmentStance`;
   - `authorize_control`/`revoke_control`/`invoke_procedure` → `OrganizationControlStance`;
   - `declare_commitment`/`fulfill_commitment` → `OrganizationCommitmentStance`;
   - `record_decision` → `claimed`/`disputed`/`unknown` from
     `OrganizationControlStance`.
   A stance outside its act family fails closed.
3. Encode as:
   `org_op_v1:<predicate>:<label|none>:<target_ref|none>:<anchor_kind>:<anchor_ref|none>:<authority_ref|none>:<stance>:<expiry|none>`
   - exactly nine colon-separated parts;
   - maximum 256 characters;
   - no whitespace, newline, tab, or control characters;
   - every `none` sentinel is literal;
   - unknown predicate/stance/act fails closed.
4. Add `organization_operation_claim_relation(claim)` returning one
   `CommunicationRelation(subject="org_op_v1", predicate=<org_*>, object=<7-part frame>)`.
5. Add `parse_organization_operation_claim_relation(relation)` that returns `None`
   for a different subject, an unknown predicate, or malformed content. It must
   never raise for unrelated communication.
6. Add `organization_operation_communicate_utterance(command, ledger)`:
   - no-op for non-`Talk`/`Tell`, `None`/wrong ledger, empty ledger, missing
     utterance/content, or an existing `org_op_v1` subject;
   - attach at most one relation and preserve command class, recipient, utterance,
     and every existing relation;
   - refuse when the relation count is already 32.
7. Add `organization_operation_ref(value, namespace)` re-export from the contract
   module; receivers compute the same refs for observed ids, anchors, office role
   signatures, and decision content. Raw ids are never carried in the frame.
8. Add a deterministic selector `_select_operation_claim(ledger)` that prefers, in
   order: a disputed admission/departure/assignment/control record, then an
   unresolved admission, then a recognized control/procedure, then `None`. It
   must be stable by `(organization_id, tick, record id)`.

### Required Interfaces and Contracts

- `org_v1` is untouched; `parse_organization_claim_relation` must continue to
  ignore `org_op_v1`.
- The frame carries no raw entity ids, labels beyond the bounded token, object
  contents, or free text. References are 16-hex digests so peers can match their
  own observations without receiving an id table.
- The predicate is the transport atom; the stance/act vocabulary is the meaning.
- Delivery proves speech only. It never proves membership, authority, control, or
  that a decision occurred.
- One utterance may carry one `org_v1` and one `org_op_v1` relation; total
  relations remain ≤32.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts":
  speech proves eligible delivery only.
- V4-03 `organization_communication.py` bounded-relation precedent.
- Original Request: "Allow organizations to operate even when members disagree";
  claims must travel without requiring agreement.

### Error Handling and Logging

- Malformed frames raise `OrganizationOperationError` only from the strict parser;
  the relation parser returns `None`.
- DEBUG: `organization_operation_claim act=%s stance=%s` (no ids or labels).
- WARN only when a claim is refused because the relation cap is reached:
  `organization_operation_claim_skipped reason=relation_cap`.

### Tests

- `tests/unit/test_organization_operations_communication.py`:
  - round-trip every act/stance pair;
  - reject wrong subject, predicate, part count, length, whitespace, bad refs,
    bad expiry, and non-hex refs;
  - allow `expires_tick` only for `admit`; reject it for every other act;
  - unrelated relations return `None`;
  - the decorator preserves the original command class, recipient, and relations;
  - an existing `org_op_v1` relation prevents a second one;
  - 32 relations prevents attachment;
  - `org_v1` parsing still ignores `org_op_v1` and vice versa.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_communication.py -q`

### Acceptance Criteria

- The frame is bounded, strict, and additive.
- No command, event, observer semantic, or free-text payload is added.
- Malformed or unrelated frames never break communication.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_communication.py -q`
- Expected: pass.

## Task 5: Collect operational evidence and derive decision/action provenance

### Intent

Build the owner-only evidence bundle and derive the deterministic decision/action
records that prove *why* an operational act is believed. This task stops at an
internal bundle; it does not materialize the public ledger (Task 6 does).

### Implementation Steps

1. Add a private `_OperationEvidence` dataclass in
   `organization_operations.py` with `owner_id`, `tick`, `by_concept` (an ordered
   mapping of `orgc-` id to an internal bundle), and `notices`. Add
   `_collect_operation_evidence(*, owner_id, tick, observation, prior,
   organization_concepts, offices, collective_decisions, structured_commitments,
   possession_legitimacy, policy) -> _OperationEvidence`.
2. Validate owner, tick, policy type, prior type/owner, and every input ledger
   type. A `None` concept ledger returns an empty evidence bundle (organizations
   disabled or no concepts).
3. Evidence sources are limited to:
   - the owner's concept ledger: members, roles/occupants, resources, procedures,
     records, commitments, identities;
   - the owner's office concepts: recognized roles and preferred occupants;
   - the owner's collective decisions: proposals, positions, outcomes;
   - the owner's structured commitments: interpretations;
   - the owner's possession doctrine support;
   - `observation.occurrences` where the owner is actor or target;
   - `observation.communications` where the owner is speaker or listener; a
     self-authored claim is evidence of the owner's own act, a received claim is
     testimony only.
   Concept resources/procedures/records are **match keys**, not automatic control
   claims: they do not create `OrganizationControlBelief` or
   `OrganizationProcedureActionBelief` by themselves. Commitment-operation beliefs
   may be seeded from concept commitments with `authority_basis=unknown` unless
   stronger evidence exists. Perceived membership and role occupancy alone do not
   create admission/departure/assignment beliefs; those require an explicit claim
   or an observed act.
   When several legitimacy bases exist, choose deterministically:
   `decision_grant` (supported decision) → `role_trusteeship` (preferred occupant)
   → `group_owns` (owner supports that possession doctrine) →
   `first_claimant_owns` (self-authored control) → `shared_use` → `unknown`.
   No base grants objective ownership.
4. Map occurrences to operations using `occurrence.kind`, `actor_id`,
   `target_id`, `other_entity_id`, `success`, and bounded `public_facts`. Only
   record an occurrence when it matches an active concept by actor membership
   **or** by an anchor already referenced by that concept; unrelated ordinary
   actions produce no operation record. This prevents every `Give`/`Store` from
   inventing an organization.

   | Occurrence kind | Domain | Act | `command_kind` | `outcome` | Anchor |
   | --- | --- | --- | --- | --- | --- |
   | `taken`, `taken_from_corpse` | `resource_control` | `authorize_control` | `take` | `completed` if success else `blocked` | `item` from `item_ids` |
   | `dropped` | `resource_control` | `revoke_control` | `drop` | `completed` if success else `blocked` | `item` from `item_ids` |
   | `given` | `resource_control` | `authorize_control` | `give` | `completed` if success else `blocked` | `item` from `item_id` |
   | `item_stored` | `storage` | `authorize_control` | `store` | `completed` if success else `blocked` | `structure` from `target_id` or `unknown` |
   | `artifact_created` | `record_keeping` | `record_decision` | `inscribe` | `completed` if success else `blocked` | `artifact` from `artifact_id` |
   | `artifact_modified`, `artifact_annotated` | `record_keeping` | `record_decision` | `amend`/`annotate_record` | `completed` if success else `blocked` | `artifact` from `artifact_id` |
   | `artifact_copied` | `record_keeping` | `record_decision` | `copy_record` | `completed` if success else `blocked` | `artifact` from `artifact_id` |
   | `artifact_moved` | `record_keeping` | `authorize_control` | `transfer_artifact` | `completed` if success else `blocked` | `artifact` from `artifact_id` |
   | `repository_established`, `repository_maintained`, `repository_indexed` | `procedure_action` | `invoke_procedure` | `establish_repository`/`maintain_repository`/`index_repository` | `completed` if success else `blocked` | `repository` from `target_id` or `unknown` |
   | `repository_member_deposited`, `repository_member_retrieved` | `storage` | `authorize_control` | `deposit_record`/`retrieve_record` | `completed` if success else `blocked` | `repository` from `target_id` or `unknown` |
   | `project_contributed` | `procedure_action` | `invoke_procedure` | `contribute_collective_project` | `completed` if success else `blocked` | `collective_project` from `target_id` or `unknown` |
   | `public_good_maintained`, `public_good_benefit`, `public_good_opposed` | `procedure_action` | `invoke_procedure` | `maintain_public_good`/`use_public_good`/`oppose_public_good` | `completed` if success else `blocked` | `structure` from `target_id` or `unknown` |

   When `occurrence.success` is `None`, use `outcome="observed"`; when the fact is
   absent, use `outcome="unknown"`. Never infer a command that was not observed.
5. Map `org_op_v1` claims:
   - `admit` → admission evidence; `depart` → departure evidence; `assign`/
     `remove` → assignment evidence; `authorize_control`/`revoke_control` →
     control evidence; `invoke_procedure` → procedure-action evidence;
     `declare_commitment`/`fulfill_commitment` → commitment evidence;
     `record_decision` → decision evidence.
   - Resolve the frame against the owner's concept identities (label token), and
     against refs computed from the owner's observed entity/anchor ids. A claim
     that matches no concept is not fabricated into one: record a ledger-level
     `operation_anchor_unresolved` notice and drop the unbound claim.
   - `expires_tick` is legal only for `admit`; any other act with an expiry is
     rejected by the frame parser.
   - Authorship: `speaker == owner` → `authority_basis=self_authored`; otherwise
     use `role_belief` only when `authority_ref` matches the digest of one of the
     owner's recognized office **role signatures** and the speaker is a preferred
     occupant; use `decision_belief` only when `authority_ref` matches the digest
     of a supported decision's **public content** (topic/action/target); else
     `unknown`. The owner must never read the speaker's ledger or compare
     owner-local office/decision ids across owners.
6. Derive decision records with
   `organization_decision_id(owner_id, organization_id, domain, act, tick,
   actor_id, target_id, anchor_kind, anchor_id, stance)` and action records with
   `organization_action_id(owner_id, organization_id, decision_id, tick, actor_id,
   command_kind, anchor_kind, anchor_id)`.
   - Decision `support_count`/`oppose_count` come from active positions on the
     owner's matching collective proposal; ties/absent positions are 0.
   - Link each action to the most recent decision in the same concept/domain by the
     same actor whose anchor matches the action anchor; tie-break by
     `(tick, decision_id)`; if none matches, set `decision_id=None`. Never invent a
     decision to justify an action.
7. Derive decision provenance from `self_authored`, `role_authorized`,
   `decision_supported`, `procedure_recognized`, `unknown_authority`,
   `contested`, or `expired`; derive action provenance from `observed_effect`,
   `contested`, or `unknown_authority`.
8. Return the frozen `_OperationEvidence` bundle. Log DEBUG counts only:
   `organization_operation_evidence owner_id=%s concepts=%s decisions=%s actions=%s tick=%s`.

### Required Interfaces and Contracts

- `_collect_operation_evidence` is private and returns an internal bundle; it does
  not build `OrganizationOperationLedger` and performs no cap truncation.
- It has no peer/all-owner/world/runtime parameter and reads only the owner
  observation and prepared owner ledgers.
- Decision/action ids are content-addressed; re-observing the same evidence at the
  same tick does not duplicate it.
- `action_id` is derived from the decision (or `none`) plus the command/anchor
  material; the action-decision link is deterministic.
- No objective outcome is asserted. `outcome=observed` means the owner saw an
  effect; it does not mean the organization "succeeded".

### Requirement Evidence

- Original Request: "organization-owned/controlled resources", "storage",
  "records", "membership admission", "membership departure", "role assignment",
  "procedural actions", "internal commitments".
- Original Request: "Record provenance of decisions and actions."
- Original Request: "Agent-mediated actions must produce all physical effects."

### Error Handling and Logging

- Invalid inputs fail closed with `OrganizationOperationError`.
- Missing anchors are retained as `unknown` with
  `operation_anchor_unresolved`, never zero-filled.
- Logs contain counts only; no ids, labels, anchors, utterance content, or
  payloads.

### Tests

- `tests/unit/test_organization_operations_update.py`:
  - owner-only evidence: a peer ledger/world state is not accepted;
  - self-authored admission creates a decision with `self_authored`;
  - a peer claim without recognized role/decision creates `unknown_authority`;
  - a recognized-office speaker yields `role_belief`; a supported decision yields
    `decision_belief`;
  - observed `given`/`item_stored`/`artifact_created` create action records with
    the right domain/anchor, `command_kind`, and `outcome`;
  - an action links to the matching decision, and a non-matching action has
    `decision_id=None`;
  - missing anchor facts yield `unknown` and a notice, not a zero;
  - same inputs at the same tick produce identical decisions/actions/ids;
  - different ticks/actors/anchors change the content-addressed ids.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_update.py -q`

### Acceptance Criteria

- The evidence bundle covers all eight domains.
- Decisions and actions carry deterministic ids and provenance.
- No ledger is materialized in this task.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_update.py -q`
- Expected: pass.

## Task 6: Materialize the operation ledger and enforce caps

### Intent

Consume the evidence bundle, materialize the eight operational record families,
merge contradictory evidence without resolving it, expire temporary admissions,
carry prior concepts, and enforce the policy caps. This is the public
`apply_organization_operation_update` task.

### Implementation Steps

1. Add `apply_organization_operation_update(*, owner_id, tick, observation, prior,
   organization_concepts, offices, collective_decisions, structured_commitments,
   possession_legitimacy, policy) -> OrganizationOperationLedger`. It calls
   `_collect_operation_evidence` from Task 5; an empty bundle returns an empty
   ledger with the policy version.
2. Materialize control, admission, departure, assignment, procedure-action, and
   commitment-operation records with these merge keys:
   - control `(domain, anchor_kind, anchor_id)`;
   - admission/departure `member_id`;
   - assignment `(office_id, occupant_id)`;
   - procedure `(procedure_ref, command_kind, actor_id)`;
   - commitment `(commitment_id, role, counterpart_id)`.
   Decisions/actions append with content-addressed ids and dedupe by id.
3. Apply admission expiry: when an admission has
   `temporal_scope=TEMPORARY` and `expires_tick <= tick`, set `stance=former`
   and add `operation_expired` to the concept notices. Do not invent a new
   decision record for expiry; the original admission decision keeps its
   provenance. Do not expire departures, assignments, controls, procedures, or
   commitments.
4. Apply stance precedence:
   `disputed > recognized > admitted/assigned/claimed > shared > unknown > former`.
   Contradictory stances increment `contest_count` and set `disputed`; never drop
   either side. `owner_support_count = min(policy.max_owner_support, evidence count)`.
5. Carry prior concepts forward; update matching records; mark concepts absent
   from the concept ledger as `orphaned`; mark concepts whose concept status is
   `dissolved`/`retired` as `dissolved`; never mint a concept. Drop operation
   concepts that end with no records (they simply have no operational state).
   Operations stay with the predecessor on split/merge; children start empty.
6. Trim caps with a stable `(tick, id)` order, add `operations_truncated`;
   enforce `max_total_records` across all concepts after per-family caps; when a
   decision is trimmed, rewrite any referencing action's `decision_id` to `None`
   before validation; add `operations_orphaned` for orphaned concepts,
   `authority_unresolved` for unknown authority, `contest_unresolved` when
   disputes remain, `operation_expired` when admissions expired, and
   `operation_anchor_unresolved` when an anchor kind is `unknown`.
7. Build `OrganizationOperationLedger(owner_id=owner, concepts=..., notices=...,
   policy_version=ORGANIZATION_OPERATION_POLICY_VERSION)` and validate it.
8. Log DEBUG counts only:
   `organization_operations_update owner_id=%s concepts=%s controls=%s decisions=%s actions=%s tick=%s`.

### Required Interfaces and Contracts

- The public update has no peer/all-owner/world/runtime parameter.
- The concept ledger is an input, not an output; operations never create, split,
  merge, or dissolve concepts. An admission/departure decision records an **act**;
  perceived membership remains the V4-03 concept ledger's responsibility, fed by
  `org_v1` claims and observation. A sender that wants both should emit both
  frames (Task 8 wires both decorators).
- Disagreement is data, not an error. A single owner's claim is enough to record
  an operation; contradictory evidence sets `disputed` and increments contest.
- Temporary admission expiry is explicit; it never silently persists.
- The ledger is sorted, capped, and owner-matched; no objective ownership or
  resource pool is created.

### Requirement Evidence

- Original Request: "Allow organizations to operate even when members disagree
  about membership, authority, resource legitimacy, procedures."
- Original Request: "Keep objective physical possession separate from
  subjective/legal ownership."
- V4-03 `OrganizationConceptLedger` owner/sort/notice invariants 1483-1550.

### Error Handling and Logging

- Invalid ledger state fails closed with `OrganizationOperationError`.
- Truncation, orphaning, and expiry emit WARN with counts only; no ids or
  payloads.
- A dangling action-decision reference is rewritten before validation, never
  silently accepted.

### Tests

- `tests/unit/test_organization_operations_update.py`:
  - all eight domains materialize into the ledger;
  - two contradictory admission claims yield `disputed` and `contest_count > 0`,
    with both sides retained;
  - a temporary admission expires to `former` with `operation_expired`;
  - a dissolved concept yields `dissolved` operations and no new decisions;
  - split/merge leaves predecessor operations and empty children;
  - caps truncate deterministically, add `operations_truncated`, and enforce
    `max_total_records`;
  - a trimmed decision nulls referencing action `decision_id`s;
  - ledger owner/sort/notice validation passes; a foreign owner fails;
  - same inputs produce identical ledgers and ids.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_update.py tests/unit/test_organization_operations_ledger.py -q`

### Acceptance Criteria

- The public update materializes all eight domains.
- Disagreement and expiry are preserved explicitly.
- Caps and notices are deterministic; no concept identity or lineage changes.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_update.py tests/unit/test_organization_operations_ledger.py -q`
- Expected: pass.

## Task 7: Carry the operation ledger through cognition, runtime, checkpoints, and the runner

### Intent

Make the sidecar a first-class owner-scoped artifact alongside the concept ledger,
with the same disabled behavior, ownership checks, checkpoint continuity, and
detached export.

### Implementation Steps

1. `src/agents/cognition/models.py`:
   - add `organization_operations: object | None = None` after
     `organization_concepts` in `SubjectiveSnapshot`, `CognitiveLoopProposal`, and
     `CognitiveLoopResult`;
   - extend `SubjectiveSnapshot.__post_init__` (the existing
     `require_owner_organization_concepts` block at 1018-1025) with
     `require_owner_organization_operations` for the new field.
2. `src/agents/cognition/contracts.py`:
   - add `organization_operations: object | None = None` after
     `organization_concepts`;
   - validate with `require_owner_organization_operations` when not `None`;
   - copy it in `to_snapshot()`.
3. `src/agents/cognition/loop.py`:
   - add `_organization_operation_policy` and
     `_prepared_organization_operations` to the slots list;
   - add `_prepare_organization_operations(loop_input, organization_concepts,
     offices, collective_decisions, structured_commitments,
     possession_legitimacy)` after `_prepare_organization_concepts`;
   - return `None` when the mode is disabled; otherwise read the prior ledger from
     `snapshot.organization_operations`, call
     `apply_organization_operation_update`, store it, and log the concept/record
     counts;
   - call it in the prepare sequence at ~4334 and pass `organization_operations`
     to `CognitiveLoopProposal` at ~4700 and to `CognitiveLoopResult` at ~5041.
4. `src/agents/cognition/fork_state.py`:
   - add `prepared_organization_operations: object | None = None`;
   - keep `COGNITIVE_LOOP_FORK_STATE_VERSION` at `cognitive-loop-fork-state-v1`;
   - capture it in `CognitiveLoopForkState(...)` next to
     `prepared_organization_concepts` at ~1391 and restore it in `loop.py` next
     to `prepared_organization_concepts`.
5. `src/simulation/agent_runtime.py`:
   - add `_organization_operations` to the slots and initialize it to `None` in
     `__init__` next to `_organization_concepts`;
   - add `_commit_organization_operations(ledger, tick)` mirroring
     `_commit_organization_concepts`, with owner/type checks and a DEBUG count;
   - include `organization_operations=self._organization_operations` in
     `build_perspective` at ~2196;
   - call `_commit_organization_operations(getattr(pending.loop_result,
     "organization_operations", None), pending.tick)` immediately after the
     concept commit at ~2678;
   - restore it from the checkpoint at ~3230 and reject a foreign owner;
   - include it in `export_runtime_checkpoint()` at ~3339.
6. `src/simulation/perception.py`:
   - add `organization_operations: object | None = None` to `build_perspective`
     after `organization_concepts`;
   - pass it into `Perspective(...)` at ~348;
   - include an operation concept count in the existing DEBUG
     `perspective_built` metadata only if the existing pattern includes the
     concept count; do not log records/anchors.
7. `src/simulation/runner.py`:
   - extend the checkpoint validation loop at ~4697 to validate the operation
     ledger type/owner and disabled-owner rule;
   - add `organization_operation_ledgers=self.export_organization_operation_ledgers()`
     to the `RunnerResult` at ~4949;
   - add `export_organization_operation_ledgers()` next to the concept exporter;
   - log `runner_organization_operation_ledger_export ledger_count=%s`.
8. `src/simulation/runner_models.py`:
   - add `organization_operation_ledgers: tuple[object, ...] = ()` after
     `organization_concept_ledgers`;
   - apply the same ordered-sequence validation.
9. `src/simulation/run_control.py`:
   - add `organization_operations: object | None = None` to
     `AgentRuntimeCheckpoint` after `organization_concepts`;
   - extend its `__post_init__` with
     `require_owner_organization_operations` and the same field name.
10. Re-export the new symbols from `agents.cognition.__init__`.

### Required Interfaces and Contracts

- Disabled mode allocates nothing and carries `None`; flags-off trajectories are
  unchanged.
- The operation ledger is owner-matched; a foreign ledger is an ownership error.
- The loop prepares concepts first, then operations; operations may reference a
  concept created in the same tick.
- The fork-state version stays v1 because the new field is optional and
  process-local. No durable subjective restart is claimed.
- No SQL migration, new checkpoint codec, or new event is added.
- `RunnerResult` gains a detached tuple only; runner/result document schemas are
  unchanged.

### Requirement Evidence

- V4-03 plan decision 18: checkpoint continuity is tested through the real
  `export_runtime_checkpoint()` → `apply_runtime_checkpoint()` path.
- `.ai-factory/ARCHITECTURE.md` "Requirements for later changes" 4: subjective
  checkpoints stay outside the objective event fold.
- Original Request: operations must remain owner-scoped and agent-mediated.

### Error Handling and Logging

- Wrong type/owner raises `TypeError`/`AgentRuntimeError(OWNERSHIP)`; disabled
  owners never retain a ledger.
- DEBUG per-owner counts; INFO export count. No record content or anchor values.
- Checkpoint restore rejects an operation ledger for a disabled owner.

### Tests

- `tests/unit/test_organization_operations_runtime.py`:
  - disabled loop returns `None` and the runtime carries `None`;
  - enabled loop prepares the ledger after concepts and exposes it on the
    proposal/result;
  - `Perspective.to_snapshot()` preserves the same ledger object/owner;
  - runtime commit rejects a foreign owner;
  - checkpoint export/restore round-trips the ledger through the real methods;
  - a checkpoint with an operation ledger for a disabled owner fails;
  - runner result exports owner-ordered ledgers and no duplicate owners.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_runtime.py -q`

### Acceptance Criteria

- The ledger is prepared, committed, checkpointed, and exported through the real
  paths.
- Flags-off behavior is unchanged.
- No new persistent schema or event exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_runtime.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: the sidecar duplicates the concept aspects and drifts.
  Mitigation: concepts remain structural beliefs; the sidecar only records
  control/acts/provenance, and tests assert concept digests/identity are untouched.
- Risk: an organization is accidentally given execution authority.
  Mitigation: the allowlist only classifies existing commands; no helper returns a
  command and no module imports `AgentCommand`/`WorldState`.
- Risk: peer evidence leaks into the update.
  Mitigation: the update signature and inspection test forbid peer/world inputs.
- Risk: disagreement is collapsed to one status.
  Mitigation: stance precedence keeps `disputed` and `contest_count`, and tests
  assert both sides survive.
- Risk: checkpoint compatibility breaks.
  Mitigation: optional field, v1 fork-state version, real round-trip test.

## Phase Completion Checklist

- Every Task 3-8 acceptance criterion is met.
- All eight operational domains are representable.
- Speech frames are bounded and reachable from deliberation.
- The ledger is carried through perspective, loop, runtime, checkpoint, and
  runner export.
- `index.md` task checkboxes are updated immediately after verified completion.
## Task 8: Wire claims and operational classification into existing deliberation

### Intent

Make the operational frames and claims reachable from ordinary speech, and let
the owner classify whether its selected ordinary command is consistent with an
operational belief. The organization still cannot execute anything; the agent
selects and submits the command exactly as before.

### Implementation Steps

1. Create `organization_operations_actions.py` with
   `ORGANIZATION_DOMAIN_COMMANDS: Mapping[OrganizationOperationDomain,
   tuple[type, ...]]`:
   - `resource_control`: `Give`, `Take`, `Drop`, `Store`
   - `storage`: `Store`, `Take`, `DepositRecord`, `RetrieveRecord`
   - `record_keeping`: `Inscribe`, `Amend`, `CopyRecord`, `AnnotateRecord`,
     `TransferArtifact`, `DepositRecord`
   - `membership_admission`: `Talk`, `Tell`
   - `membership_departure`: `Talk`, `Tell`
   - `role_assignment`: `Talk`, `Tell`
   - `procedure_action`: `Help`, `ContributeCollectiveProject`,
     `MaintainPublicGood`, `MaintainRepository`, `EstablishRepository`, `Build`,
     `Repair`
   - `internal_commitment`: `Give`, `ContributeCollectiveProject`,
     `DepositRecord`
   Do not import `AgentCommand`; use exact concrete classes and `type(command)`.
2. Add `organization_domain_allows(domain, command) -> bool` and
   `organization_operation_command_support(ledger, command) -> tuple[OrganizationOperationDomain, ...]`
   returning the domains whose allowlist contains the command and whose
   operational record is active for the acting owner (record `actor_id` equals
   the owner, or the command's recipient/target equals the record target).
   A record for another actor never authorizes or classifies this command.
3. Add `organization_commitment_follow_through(ledger, command) -> str | None`
   returning a matching `commitment_id` only when the command is an exact
   supported `Give` to the counterparty, `ContributeCollectiveProject` for the
   referenced project, or `DepositRecord` for the referenced repository.
   This is a recognition helper, not a command rewriter.
4. In `deliberation.py` `_reputation_testimony_command`, after the
   `collective_decision_communicate_utterance` call at ~1261 and before the
   mediation call at ~1269 (use lazy imports, matching the surrounding
   decorators):
   - fetch `snapshot.organization_concepts` and call
     `organization_communicate_utterance(command, ledger)` (this wires the V4-03
     claim path that was previously only exported);
   - fetch `snapshot.organization_operations` and call
     `organization_operation_communicate_utterance(command, ledger)`;
   - preserve command class, recipient, and existing relations.
5. Do not add a planner, direction bias, or command rewrite. If the selected
   command is unsupported for every operational claim, leave it unchanged and let
   the next observation record no matching action.
6. Keep the existing late re-gate for durable/repository commands unchanged; the
   organization decoration must not add a command type.
7. Log DEBUG only when a relation is attached:
   `organization_operation_utterance act=%s` and
   `organization_claim utterance predicate=%s` (no ids/labels).

### Required Interfaces and Contracts

- The allowlist is a closed classification of the existing 43 commands; it adds
  no command and changes no admission rule.
- `organization_operation_command_support` returns a tuple for auditability; it
  never mutates the command or the ledger.
- Commitment follow-through is only recognized after the command is selected; it
  never creates a `Give`/`ContributeCollectiveProject`/`DepositRecord`.
- The V4-03 `org_v1` decoration is now actually reachable from deliberation, and
  its existing tests must still pass.
- No direction bias is added; organizations "operate" through the agent's
  ordinary selection, not through a second planner.

### Requirement Evidence

- Original Request: "Do not allow an Organization object to teleport resources or
  execute physical actions. Agent-mediated actions must produce all physical
  effects."
- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime": one
  `AgentCommand` per owner, ordinary admission.
- `src/agents/cognition/collective_decision_actions.py` 39-95: the established
  belief-to-existing-command allowlist precedent.

### Error Handling and Logging

- A ledger of the wrong type is ignored (no-op) rather than raising inside
  deliberation.
- A command outside the allowlist is not an error; it is simply unsupported.
- Logs contain only act/domain tokens and counts; never utterance content, ids,
  labels, anchors, or payloads.

### Tests

- `tests/unit/test_organization_operations_actions.py`:
  - every domain maps only to existing command classes;
  - no domain maps to a command that does not exist in the 43-command matrix;
  - `organization_operation_command_support` returns the expected domains for
    `Give`, `Store`, `Inscribe`, `Talk`, and `Wait`;
  - commitment follow-through recognizes exactly one matching command and returns
    `None` for a wrong recipient/item/project;
  - no helper mutates the command.
- `tests/unit/test_organization_operations_communication.py`:
  - deliberation on a `Talk`/`Tell` attaches both `org_v1` and `org_op_v1`
    relations when both ledgers carry a claim;
  - a `Wait` command is unchanged;
  - existing institutional/office/decision relations are preserved.
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_actions.py tests/unit/test_organization_operations_communication.py tests/unit/test_organization_communication.py -q`

### Acceptance Criteria

- Operational speech is reachable from ordinary deliberation.
- The command allowlist adds no command and no planner.
- No physical effect is produced by an organization object.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_actions.py tests/unit/test_organization_operations_communication.py tests/unit/test_organization_communication.py -q`
- Expected: pass.

