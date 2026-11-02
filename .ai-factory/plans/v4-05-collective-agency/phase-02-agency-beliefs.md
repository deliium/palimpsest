# Phase 2: Owner-Scoped Collective-Agency Beliefs

Plan: [index.md](index.md)
Tasks: 3-8
Depends on: Phase 1 / Tasks 1-2

## Objective

Add the owner-scoped collective-agency ledger: proposals, discussion claims,
support/opposition/abstention, amendments, recognized procedure, collective
decision records, and per-actor implementation/compliance/refusal/sabotage
tracking. The ledger remains a belief sidecar keyed by existing `orgc-` ids. It
never becomes an organization actor, a super-agent, a command source, or a
global OrganizationLLM.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/organization_operations.py` | `OrganizationDecisionRecord` 1157-1244; `OrganizationActionRecord` 1247-1320; `OrganizationOperationalConcept` 1333-1423; `OrganizationOperationLedger` 1426-1522; `apply_organization_operation_update` 2708-2971 | Exact record/ledger/update pattern to mirror |
| `src/agents/cognition/organization_operations_communication.py` | `OrganizationOperationClaim` 161-204; encode 207-221; parse 224-285; relation 288-300; utterance decoration 486-537 | Bounded frame pattern; `org_ca_v1` must be equally strict |
| `src/agents/cognition/collective_decisions.py` | `CollectiveAct` 152-160; `CollectivePositionStance` 193-199; `CollectiveCompliance` 864-923; `CollectiveDecisionLedger` 1029-1180; `apply_collective_decision_update` 2295-2378; `appraise_collective_compliance` 2469-2579 | Existing V3-31 mechanism; V4-05 must not change it, and must add the missing organization-keyed stages |
| `src/agents/cognition/offices.py` | `OfficeAuthorityBelief` 541-575; `OfficeConceptStatus` 182-190; `office_role_signature` 421-435 | Authority evidence for procedure/role claims remains a belief |
| `src/agents/cognition/organization_concepts.py` | `OrganizationProcedureBelief` 846-886; `OrganizationConcept` 1203-1429; `OrganizationConceptLedger` 1482-1549; `_collect_claims` 2078-2175 | Procedure reference resolution and owner-only claim parsing |
| `src/agents/cognition/deliberation.py` | organization decoration 1246-1285 | Where `org_v1` and `org_op_v1` are added; `org_ca_v1` follows the same place |
| `src/world/_perception.py` | `ObservedOccurrence` construction 939-1011; `ObservedCommunication` 1015-1044 | The only observed fields implementation tracking may use |
| `src/agents/cognition/configuration.py` | `CognitionLoopConfig` 593-597; validation 1070-1111 | Policy seam from Task 2 |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/organization_agency.py` | modify | Add proposal/position/amendment/decision/implementation records, concept/ledger, update entrypoint, decision recognition |
| `src/agents/cognition/organization_agency_communication.py` | create | Bounded `org_ca_v1` frame, claim, parser, relation builder, utterance decoration |
| `src/agents/cognition/organization_agency_actions.py` | create | Effect catalog helpers, physical/testimonial classification, occurrence matching predicates; never constructs a command |
| `src/agents/cognition/models.py` | modify | Carry `organization_agency` on proposal/result |
| `src/agents/cognition/contracts.py` | modify | Carry `organization_agency` on `SubjectiveSnapshot`/`Perspective` and validate owner |
| `src/agents/cognition/loop.py` | modify | Prepare the agency ledger after concepts/operations; fork/restore; policy field |
| `src/agents/cognition/fork_state.py` | modify | Export/restore the agency ledger |
| `src/agents/cognition/deliberation.py` | modify | Decorate `Talk`/`Tell` with at most one `org_ca_v1` relation |
| `src/agents/cognition/__init__.py` | modify | Export new records, update functions, communication symbols |
| `src/simulation/agent_runtime.py` | modify | Private field, commit, finalization, checkpoint validation, and the `build_perspective` call at 3392 |
| `src/simulation/perception.py` | modify | Add `organization_agency` to `build_perspective` at 141 and pass it into `Perspective` at 350 |
| `src/simulation/run_control.py` | modify | Checkpoint field and owner validator |
| `src/simulation/runner.py` | modify | Export owner agency ledgers into the result |
| `src/simulation/runner_models.py` | modify | Result field plus ordered-sequence validation; no schema version bump |
| `tests/unit/organization_agency_helpers.py` | create | Deterministic owner/observation/proposal builders for agency tests |

## Task 3: Define agency records and ledger invariants

### Intent

Turn the vocabulary from Task 1 into immutable, validated records. The ledger is
a third sidecar keyed by `orgc-`; it does not alter `OrganizationConcept`,
`OrganizationOperationalConcept`, or their digests.

### Implementation Steps

1. Add `OrganizationProposal` to `organization_agency.py` with fields:
   `proposal_id`, `organization_id`, `proposal_ref`, `topic`, `domain`, `effect`,
   `implementation_mode`, `target_kind`, `target_ref`, `procedure_ref`,
   `expected_actors: tuple[AgentId, ...]`, `quantity: int`, `revision: int`,
   `terms_ref`, `status`, `opened_tick`, `deadline_tick`, `first_tick`,
   `last_tick`, `support_count`, `oppose_count`, `abstain_count`,
   `contest_count`, `evidence_refs`, `notices`.
2. Add `OrganizationPosition` with `proposal_id`, `revision`, `actor_id`,
   `stance`, `authority_basis`, `evidence_refs`, `disputed`, `tick`.
3. Add `OrganizationAmendment` with `amendment_id`, `proposal_id`,
   `from_revision`, `to_revision`, `terms_ref`, `domain`, `effect`,
   `target_kind`, `target_ref`, `procedure_ref`, `amended_tick`,
   `evidence_refs`.
4. Add `OrganizationCollectiveDecision` with `decision_id`, `organization_id`,
   `proposal_id`, `revision`, `procedure_ref`, `recognition`,
   `authority_basis`, `support_count`, `oppose_count`, `abstain_count`,
   `contest_count`, `implementation_mode`, `effect`, `target_kind`,
   `target_ref`, `expected_actors`, `quantity`, `decided_tick`,
   `window_end_tick`, `implementation_status`, `provenance_code`,
   `evidence_refs`, `resolved`, `notices`.
5. Add `OrganizationImplementation` with `implementation_id`, `decision_id`,
   `actor_id`, `status`, `effect`, `observed_tick`, `provenance_code`,
   `evidence_refs`, `resolved`.
6. Add `OrganizationAgencyConcept` and `OrganizationAgencyLedger`:
   - Concept fields: `organization_id`, `owner_id`,
     `status: OrganizationStatus`, `first_tick`, `last_tick`, `proposals`,
     `positions`, `amendments`, `decisions`, `implementations`, `notices`.
   - Ledger fields: `owner_id`, `concepts`, `notices`, `policy_version`.
   - Reuse `OrganizationStatus` from `organization_concepts`; do not create a
     second lifecycle enum.
7. Enforce invariants in `__post_init__`:
   - Every id passes its exact validator.
   - `organization_id` starts `orgc-`; `owner_id` is `AgentId`.
   - Every position/amendment references an existing proposal in the same
     concept; every decision references an existing proposal revision; every
     implementation references an existing decision.
   - No duplicate proposal/amendment/decision/implementation ids within a
     concept or across the ledger.
   - Proposal/decision/implementation ticks are nondecreasing within each family.
   - `first_tick <= last_tick <= current` is not knowable here; require only
     `first_tick <= last_tick` and nonnegative.
   - `revision` is `1..max_revision`; `to_revision == from_revision + 1` for an
     amendment; a proposal's `revision` equals the highest amendment
     `to_revision` or 1.
   - `quantity` is `1..8`; `max_expected_actors` bounds the tuple; actors are
     sorted and unique.
   - `target_kind` is in `ORGANIZATION_AGENCY_TARGET_KINDS`; `target_ref` is a
     16-hex content ref or `None` exactly when `target_kind` is `none`/`unknown`.
   - `proposal_ref`/`terms_ref`/`procedure_ref` are 16-hex content refs or
     `None` where the contract allows it.
   - `support_count`, `oppose_count`, `abstain_count`, `contest_count` are
     bounded by `max_owner_support`/`max_contest`.
   - `implementation_mode is PHYSICAL` iff `effect is not NONE`; reject
     `testimonial` with a physical effect or vice versa.
   - A decision's `window_end_tick >= decided_tick`.
   - `resolved` is true exactly when `target_kind != "unknown"`; reject
     contradictions.
   - `forbidden` field names are rejected at the dataclass class level.
8. Enforce ledger caps: concepts, proposals, positions, amendments, decisions,
   implementations, total records, evidence per record, total evidence. Raise
   `organization_agency_cap_exceeded`; never silently drop.
9. Add `empty_organization_agency_ledger(owner_id, policy=None)` and
   `require_owner_organization_agency(ledger, owner_id, field_name=...)`.
10. Ensure all ordering is deterministic: proposals by `(opened_tick,
    proposal_id)`, positions by `(tick, proposal_id, revision, actor_id,
    stance)`, amendments by `(amended_tick, amendment_id)`, decisions by
    `(decided_tick, decision_id)`, implementations by `(observed_tick,
    decision_id, actor_id)`.

### Required Interfaces and Contracts

- `OrganizationAgencyLedger.policy_version` must equal
  `ORGANIZATION_AGENCY_POLICY_VERSION`; a mismatch fails closed.
- `None` ledger means the mode is off; an empty ledger means the mode is on with
  no evidence. These are different states.
- No field may hold a `WorldState`, `WorldEvent`, `AgentCommand`, event store,
  peer ledger, or prompt.
- `OrganizationProposal.proposal_ref` is a 16-hex content ref, not `orgp-`.
- `OrganizationCollectiveDecision.decision_id` is `orgcd-`; publication later
  mints a separate `orgcpd-` id.

### Requirement Evidence

- Original Request: proposals, supporters, opponents, abstention, amendments,
  recognized outcomes, compliance, refusal, sabotage.
- `.ai-factory/ARCHITECTURE.md` "Key Principles 1-3": separate authorities,
  deterministic identity, frozen contracts.
- V4-04 record/ledger invariants (cited above).

### Error Handling and Logging

- Validation failures raise `OrganizationAgencyError` with a closed code.
- On ledger construction, log DEBUG counts only:
  `organization_agency_ledger_constructed owner_id=%s concepts=%s proposals=%s decisions=%s implementations=%s`.
- Never log actor sets, proposal refs, labels, or evidence bodies.

### Tests

Create `tests/unit/test_organization_agency_ledger.py`:
- Round-trip construction of a valid ledger with one concept, one proposal, one
  position, one amendment, one decision, and one implementation.
- Each invariant violation raises the expected code: duplicate record, unknown
  proposal, unknown decision, tick regression, bad revision, bad quantity,
  physical/testimonial mismatch, unresolved contradiction, foreign owner,
  cap exceeded.
- Ordering is canonical regardless of input order.
- `None` and empty ledgers carry distinct meaning.
- A `WorldState`/`AgentCommand` field is rejected by the forbidden-field guard.
- A concept with an existing V4-03/V4-04 ledger can be extended without changing
  either digest.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_ledger.py -q`

### Acceptance Criteria

- All records are immutable and validated.
- The ledger is keyed only by existing `orgc-` ids.
- No V4-03/V4-04 record or digest changes.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_ledger.py -q`
- Expected: all tests pass.

## Task 4: Add bounded `org_ca_v1` collective-agency speech frames

### Intent

Carry proposals, positions, amendments, recognition claims, refusals, and
implementation reports inside existing `Talk`/`Tell` speech. No new command,
event, observer semantic type, or free-text payload is added.

### Implementation Steps

1. Create `src/agents/cognition/organization_agency_communication.py` with:
   - `ORGANIZATION_AGENCY_COMMUNICATION_POLICY_VERSION =
     "organization-agency-communication.v1"`
   - `ORGANIZATION_AGENCY_FRAME_SUBJECT = "org_ca_v1"`
   - `ORGANIZATION_AGENCY_PREDICATES` mapping nine acts to predicates:
     `org_ca_propose`, `org_ca_support`, `org_ca_oppose`, `org_ca_abstain`,
     `org_ca_amend`, `org_ca_withdraw`, `org_ca_recognize`, `org_ca_refuse`,
     `org_ca_report`.
2. Define the exact frame shape with 11 colon fields:
   `org_ca_v1:<predicate>:<proposal_ref>:<procedure_ref>:<domain>:<effect>:<target_ref>:<revision>:<terms_ref>:<stance>:<report_kind>`
   - `none` for an absent optional token.
   - `proposal_ref`, `procedure_ref`, `target_ref`, `terms_ref` are 16-hex refs
     or `none`.
   - `domain` is one of the eight `OrganizationOperationDomain` values or
     `none`.
   - `effect` is an `OrganizationAgencyEffect` value or `none`; when both
     `domain` and `effect` are present, the effect must be allowed by the
     domain.
   - `revision` is a decimal `1..9999` or `none` when the predicate does not
     need it.
   - `stance` is a closed `OrganizationAgencyPositionStance` value or `none`.
   - `report_kind` is a closed `OrganizationAgencyReportKind` value or `none`.
   - Maximum 384 characters; reject whitespace, control characters, empty
     fields, and more than one `org_ca_v1` relation per utterance.
3. Add `OrganizationAgencyClaim` with fields matching the frame. Validate
   predicate-specific requirements:
   - `propose`: proposal_ref, domain, effect, revision, terms_ref required;
     stance and report_kind are `none`.
   - `support`/`oppose`/`abstain`/`withdraw`: proposal_ref and revision required;
     stance must match the predicate; effect/domain may be `none`; report_kind
     is `none`.
   - `amend`: proposal_ref, revision, terms_ref, domain, effect required; stance
     and report_kind are `none`; revision >= 2.
   - `recognize`: proposal_ref, revision, procedure_ref required; stance is
     `recognized` or `unrecognized`; effect/domain may be `none`; report_kind is
     `none`.
   - `refuse`: proposal_ref and revision required; stance is `refuse`;
     effect/domain may be `none`; report_kind is `none`.
   - `report`: proposal_ref and revision required; report_kind is required;
     effect/domain may be `none`; stance is `none`.
4. Add `encode_organization_agency_claim`, `parse_organization_agency_claim`,
   `organization_agency_claim_relation`, and
   `parse_organization_agency_claim_relation`.
5. Add `organization_agency_communicate_utterance(command, claims)` following the
   V4-04 pattern at 486-537:
   - Accept only `Talk` or `Tell`.
   - Preserve class, recipient, and utterance.
   - Append at most one `org_ca_v1` relation.
   - Refuse if an `org_ca_v1` relation already exists or the 32-relation cap is
     reached.
   - No free text, no label payload, no owner id.
6. Export the module's public names from `agents.cognition`.
7. Do not modify `organization_communication.py` (`org_v1`) or
   `organization_operations_communication.py` (`org_op_v1`).

### Required Interfaces and Contracts

- Frame subject is exactly `org_ca_v1`; predicates are exactly the nine listed.
- `parse_*` returns `None` for unrelated or malformed relations, never raises
  into the caller.
- `encode_*` raises `OrganizationAgencyError` only for invalid claims.
- The frame carries no raw agent ids, no `orgc-`/`orgp-` ids, and no free text.
- Existing `org_v1` and `org_op_v1` frames and relation counts are unchanged.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts":
  bounded speech, no free-text payload, no new command/event.
- V4-04 `org_op_v1` frame contract (cited above).
- Original Request pipeline: proposal, discussion, support/opposition,
  abstention, amendments, recognized procedure, decision, implementation,
  refusal, sabotage.

### Error Handling and Logging

- Invalid frames fail closed with `organization_agency_invalid`; callers record
  a `malformed_claim` notice rather than crashing the tick.
- Log only `organization_agency_claim_parse_failed reason=invalid_frame` at WARN
  with no frame body.
- No utterance text, relation object, or actor id in logs.

### Tests

Create `tests/unit/test_organization_agency_communication.py`:
- Encode/decode round trip for each of the nine predicates.
- Exactly 11 fields; rejects 10 or 12, whitespace, control characters, >384
  chars, bad refs, bad revision, bad stance, bad report kind, and an effect not
  allowed by the supplied domain.
- Predicate-specific requirement failures.
- `parse_organization_agency_claim_relation` returns `None` for `org_v1`,
  `org_op_v1`, unrelated relations, and malformed `org_ca_v1`.
- `organization_agency_communicate_utterance` preserves `Talk`/`Tell` and adds
  exactly one relation; rejects other commands and an existing `org_ca_v1`.
- 32-relation cap fails closed.
- No owner id or `orgc-`/`orgp-` token appears in an encoded frame.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_communication.py -q`

### Acceptance Criteria

- All nine predicates are usable and strictly bounded.
- `org_v1` and `org_op_v1` remain byte-identical for the same inputs.
- No command, event, observer semantic type, or free-text payload is added.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_communication.py tests/unit/test_organization_operations_communication.py tests/unit/test_organization_communication.py -q`
- Expected: all tests pass.

## Task 5: Collect claims and materialize proposals, positions, amendments, and decisions

### Intent

Apply owner-visible claims to the agency ledger, update support/opposition/
abstention counts, apply amendments, and mint collective decision records with
recognition status and provenance. This is the core of
proposal → discussion → support/opposition → recognized procedure → collective
decision record.

### Implementation Steps

1. Add `apply_organization_agency_update(owner_id, tick, observation, prior,
   organization_concepts, policy=None) -> OrganizationAgencyLedger | None` to
   `organization_agency.py`.
2. Validate:
   - `owner_id` is `AgentId`; `tick` is nonnegative; `policy` is the locked type.
   - `prior` is `None` or an `OrganizationAgencyLedger` of the same owner.
   - `organization_concepts` is `None` or an `OrganizationConceptLedger` of the
     same owner; a foreign ledger fails closed.
   - `observation` is owner-safe: reject objects whose class module starts with
     `world._`, `simulation.engine`, `persistence`, or `api`; duck-type
     `observer_id`, `occurrences`, `communications`.
   - `observation.observer_id == owner_id` when present.
3. If `organization_concepts is None`, return an empty ledger for the owner.
   Do not retain a prior agency ledger when the concept ledger is absent.
4. Collect claims:
   - Iterate `observation.communications` in deterministic order.
   - Parse only `org_ca_v1` relations; ignore unrelated relations.
   - Ignore claims not addressed to the owner (`listener_id != owner_id`), and
     claims with `declared.source_basis` that cannot be verified? Existing
     V4-03/V4-04 accept delivered communications; follow their rule: only
     delivered `Talk`/`Tell` addressed to the owner, one hop.
5. Resolve a claim to a proposal:
   - Match `proposal_ref` and `revision` within concepts owned by the owner.
   - If exactly one match, apply.
   - If multiple, choose the concept with the largest membership overlap with
     the speaker; tie-break by `organization_id`.
   - If none and the predicate is `propose`, try to create an owner-local peer
     proposal under the concept where the speaker is a perceived member. Use
     the frame's `domain`, `effect`, `procedure_ref`, `target_ref`, and
     `terms_ref`; validate the effect against the domain. Derive `topic` from
     the domain (`resource_control`→`resource_use`, `storage`→`storage`,
     `record_keeping`→`record_keeping`, `membership_*`→`membership`,
     `role_assignment`→`role`, `procedure_action`→`procedure`,
     `internal_commitment`→`commitment`). Choose the concept with the largest
     membership overlap; tie-break by `organization_id`. If no concept matches,
     append `orphaned_concept`.
   - If none and the predicate is not `propose`, append `orphaned_concept` and
     do not create a proposal.
6. Apply:
   - `propose`: if a matching proposal exists, attach the communication as
     evidence only; a proposal claim is not an implicit support position. If a
     peer proposal was created, store it with
     `authority_basis=OBSERVATION`, `provenance_code=COMMUNICATED`,
     `status=ACTIVE`, and the normal deadline.
   - `support`/`oppose`/`abstain`: append or replace one position per
     `(proposal_id, revision, actor_id)`; recompute counts.
   - `withdraw`: if the speaker is the proposal originator and no decision
     exists, set the proposal status to `WITHDRAWN`; otherwise retract the
     speaker's prior position by recording a `withdraw` position (retain the
     row for provenance). Do not delete prior evidence.
   - `amend`: if `tick <= proposal.deadline_tick`,
     `revision == proposal.revision + 1`, and `terms_ref` validates, append an
     `OrganizationAmendment`; set proposal `revision`, `terms_ref`, `domain`,
     `effect`, `target_ref`, `procedure_ref`, `status=AMENDED`; reset counts to
     zero for the new revision; record an `amend` position for the speaker on
     the new revision. If out of order, add `amendment_out_of_order` and keep
     the prior revision. An amendment after the deadline adds
     `proposal_expired` and is retained as evidence only.
   - `recognize`: compute recognition (below); if `stance=recognized`, record the
     claim as a `support` position for the speaker and mint a decision when
     recognition is possible; if `unrecognized`, record an `oppose` position for
     the speaker and keep the claim as evidence against recognition.
   - `refuse`: append a `refuse` position for the speaker; do not change support
     counts; it is implementation evidence for Task 6.
   - `report`: store the report as evidence for Task 6; do not change positions.
   - Position authority basis: self-authored positions use `SELF_AUTHORED`,
     delivered peer claims use `OBSERVATION`, procedure-matched positions use
     `PROCEDURE_BELIEF`, recognition claims use `DECISION_BELIEF`, and
     unresolved targets use `UNKNOWN`.
7. Recognition:
   - Apply all claims for the tick in deterministic order, then evaluate
     recognition/expiry exactly once per tick. An amendment delivered on the
     deadline is applied before recognition, so the decision uses the amended
     revision.
   - A procedure is recognized when the concept has an
     `OrganizationProcedureBelief` whose
     `organization_agency_ref("procedure", anchor_id)` equals the proposal's
     `procedure_ref`, `status is OrganizationStatus.RECOGNIZED`, and
     `recurrence >= policy.procedure_min_recurrence`.
   - `support_count` is the number of distinct actors with an active `support`
     position on the current revision.
   - `oppose_count` is the number of distinct actors with an active `oppose`
     position; `abstain_count` is the number with `abstain`.
   - `contest_count = oppose_count + number of disputed support claims`.
   - A `WITHDRAWN` or `EXPIRED` proposal mints no decision.
   - `recognized` when procedure recognized,
     support_count >= policy.recognition_min_supporters, and contest_count == 0.
   - `contested` when
     support_count >= policy.recognition_min_supporters and (procedure
     recognized or contest_count > 0).
   - `unrecognized` when support_count == 0, or the procedure is not recognized
     and contest_count == 0.
   - An explicit `recognize` claim may mint a decision before the deadline. At
     `tick >= deadline_tick`, mint one decision for the current revision if
     support_count >= 1; otherwise set proposal `status=EXPIRED` and add
     `proposal_expired`.
8. Mint `OrganizationCollectiveDecision` once per `(proposal_id, revision)`.
   Set the proposal status to `DECIDED` when a decision is minted. Reuse the
   existing id on later ticks; update `implementation_status` only in Task 6.
   `decided_tick` is the first tick recognition was evaluated; do not rewrite
   it. `window_end_tick = decided_tick + policy.implementation_window_ticks`.
9. Provenance:
   - `authority_basis` is `SELF_AUTHORED` for the owner's own proposal,
     `DECISION_BELIEF` for a peer proposal with support, `PROCEDURE_BELIEF` for
     a procedure-matched recognition, and `UNKNOWN` otherwise.
   - `provenance_code` is `PROCEDURE_RECOGNIZED` for recognized, `CONTESTED`
     for contested, `UNRECOGNIZED` for unrecognized, `EXPIRED` for expired, and
     `UNKNOWN` for unresolved.
10. Evidence refs: mint `orgcev-` from owner, concept, source kind, source tick,
    ordinal, and content ref; sort and deduplicate; cap at
    `max_evidence_per_record`.
11. Trim deterministically when caps are exceeded: drop the oldest
    proposals/decisions/implementations by `(tick, id)` and add
    `agency_truncated`/`implementation_truncated`; never drop a record without a
    notice.

### Required Interfaces and Contracts

- The function returns `None` only when `organization_concepts is None` or the
  mode is off; otherwise it returns a ledger.
- It never reads `WorldState`, event stores, commands, peer ledgers, analysis,
  persistence, API, or prompts.
- A peer `propose` claim may create only an owner-local proposal belief under
  an existing `orgc-` concept; it never creates an organization concept, an
  objective actor, or a decision by itself. Non-`propose` claims never create a
  proposal.
- Positions are claims, not permissions. A `support` position never authorizes a
  command.
- Recognition is an owner belief; it does not require consensus, a quorum, or a
  majority.
- A decision record is minted when support reaches the recognition threshold,
  even if the procedure is unrecognized or the decision is contested; the
  `recognition` field carries the status. A proposal that never reaches the
  threshold expires without a decision.
- Existing `OrganizationConcept` and `OrganizationOperationLedger` objects are
  read-only inputs.

### Requirement Evidence

- Original Request: proposal, discussion, support/opposition, recognized
  procedure, collective decision record, recognized outcomes.
- `.ai-factory/ARCHITECTURE.md` "Important V3 seams": collective decisions and
  offices are beliefs, never binding resolutions.
- V3-31 `CollectiveDecisionLedger` and `appraise_collective_compliance` remain
  unchanged; V4-05 adds organization-keyed records.
- V4-04 `_claim_authority`/`_decision_authority_match` pattern (1778-1922).

### Error Handling and Logging

- Malformed claims are skipped with a `malformed_claim` notice; they do not
  abort the tick.
- Foreign owner/ledger inputs raise `organization_agency_foreign_ledger`.
- Tick regression raises `organization_agency_tick_regression`.
- Log INFO on recognition:
  `organization_agency_decision_recorded owner_id=%s recognition=%s supporters=%s opponents=%s abstainers=%s`
  (counts only). Log DEBUG for claim counts by predicate, never actor sets.
- WARN on truncation, unresolved procedure, or orphaned claim with reason codes.

### Tests

Create `tests/unit/test_organization_agency_update.py`:
- Proposal with no support → no decision at deadline; proposal `expired`.
- Proposal with one support and a recognized procedure → `recognized` decision.
- Proposal with one support and no recognized procedure → `unrecognized`
  decision (still recorded).
- Support + oppose → `contested`, both counts retained, decision recorded.
- Abstention does not block recognition and increments `abstain_count`.
- Amendment increments revision, resets counts, and keeps the prior amendment
  row; out-of-order amendment adds `amendment_out_of_order` and does not change
  the revision.
- Peer support/oppose/abstain/refuse/report claims apply to an existing
  proposal; an unknown `proposal_ref` on a non-`propose` claim produces
  `orphaned_concept` and no new proposal.
- A peer `propose` claim under an existing concept creates one owner-local
  proposal belief with `authority_basis=OBSERVATION` and
  `provenance_code=COMMUNICATED`; the same claim with no matching concept
  produces `orphaned_concept` and no proposal.
- A `recognize` claim before the deadline mints one decision; later ticks reuse
  the same `orgcd-` id.
- Evidence refs are `orgcev-`, sorted, deduplicated, capped.
- A `WorldState` or `AgentCommand` input fails closed.
- A foreign owner ledger fails closed.
- Deterministic output for a shuffled communication list.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_update.py -q`

### Acceptance Criteria

- The full proposal → discussion → support/opposition → recognized procedure →
  decision pipeline is represented in owner-local records.
- Disagreement is retained; no consensus gate exists.
- No peer claim can create an organization concept or a decision without the
  owner's own recognition; a peer `propose` claim can create only an owner-local
  proposal belief under an existing concept.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_update.py -q`
- Expected: all tests pass.

## Task 6: Generate proposals, appraise positions, and track implementation

### Intent

Add deterministic per-agent proposal generation and per-actor implementation
tracking. This is where collective decisions can fail because members do not act,
and where compliance, refusal, and owner-attributed sabotage become explicit.

### Implementation Steps

1. Create `src/agents/cognition/organization_agency_actions.py`:
   - `organization_agency_effect_for_kind(kind: str) -> OrganizationAgencyEffect | None`.
   - `organization_agency_domain_allows(domain, effect) -> bool`.
   - `organization_agency_occurrence_matches(decision, occurrence) -> bool`:
     compare actor, effect kind, and target ref when the decision is
     target-bound; ignore occurrences outside the decision window.
   - `organization_agency_implementation_mode(effect)`.
   - `organization_agency_contrary_effect(kind, public_facts) -> bool` using the
     closed `ORGANIZATION_AGENCY_CONTRARY_EFFECTS` set; `repository_maintained`
     is contrary only when its mode is `destroy`.
   - `organization_agency_report_matches(decision, communication) -> ...`.
   - These helpers classify and compare only. They never return, construct, or
     submit an `AgentCommand`.
2. Add `generate_organization_agency_proposal(ledger, observation, identity,
   organization_concepts, policy=None)`:
   - Return the unchanged ledger when the mode is off or no concept qualifies.
   - For each concept with status `CANDIDATE`, `RECOGNIZED`, or `DISPUTED` and no
     active proposal (`ACTIVE`/`AMENDED`), choose one domain by priority:
     1. `internal_commitment` when a commitment belief exists;
     2. `resource_control` when a resource belief is contested or shared;
     3. `storage` when a repository resource exists;
     4. `record_keeping` when a record belief exists;
     5. `procedure_action` when a recognized procedure exists.
   - Derive `procedure_ref` from the procedure belief anchor, `target_ref` from
     the resource/record/commitment anchor, and `expected_actors` from the
     concept's perceived members (sorted, deduplicated, capped at 4 or the
     policy cap).
   - Set `effect` to the domain's primary effect:
     `internal_commitment -> commitment_declared`,
     `resource_control -> give`, `storage -> item_stored`,
     `record_keeping -> artifact_created`, `procedure_action -> none`.
   - `quantity=1`, `revision=1`, `opened_tick=tick`,
     `deadline_tick=tick + proposal_window_ticks`, `status=ACTIVE`,
     `terms_ref=organization_agency_ref("terms", ...)`.
   - Create at most one proposal per concept per tick; stop at `max_proposals`.
   - Do not create a proposal for a `DISSOLVED`/`RETIRED` concept.
3. Add `appraise_organization_agency_position(ledger, observation, identity,
   organization_concepts, policy=None)`:
   - For each active proposal where the owner is in `expected_actors` or a
     perceived member and no position exists for the current revision:
     - `support` when the proposal's procedure is recognized and the target does
       not conflict with an owner control belief;
     - `oppose` when the target conflicts with an owner control belief or an
       active commitment;
     - `abstain` when the procedure is unresolved or the target is unknown.
   - Record `authority_basis` (`PROCEDURE_BELIEF`, `SELF_AUTHORED`, `UNKNOWN`).
   - Never decide for another owner; no global position.
4. Add `track_organization_agency_implementation(ledger, observation, identity,
   policy=None)`:
   - For each decision with `implementation_status` not terminal and
     `decided_tick <= tick <= window_end_tick`:
     - For each expected actor, find matching occurrences in
       `observation.occurrences` within the window.
     - Physical mode: count matching effects; `implemented` when
       `count >= quantity`, `partial` when `0 < count < quantity`.
     - Testimonial mode: `implemented` only on an explicit `report` with
       `report_kind=implemented` from that actor; `partial` for `partial`.
     - `refused` when a `refuse` claim or `report_kind=refusal` from the actor
       is observed.
     - `sabotaged` only when a contrary effect by the actor is observed and at
       least one of: a prior `oppose`/`refuse` position by that actor on the
       same revision, a `report_kind=sabotage` claim, or two or more contrary
       effects by that actor in the window. Otherwise `contrary`.
     - `unimplemented` when the actor was observed at least once in the window
       (occurrence or communication), the window has closed, and no matching
       effect/refusal/sabotage exists.
     - `unknown` when the actor was never observed, the window is still open, or
       the decision is unresolved.
     - `expired` when the concept is dissolved/retired before the window closes.
   - Persist one `OrganizationImplementation` per `(decision_id, actor_id)`;
     update its status/provenance deterministically. Do not delete prior
     evidence.
   - Compute decision aggregate:
     - `obstructed` if any `refused`/`sabotaged`/`contrary`;
     - `implemented` if all expected actors are `implemented`;
     - `partial` if any `implemented`/`partial`;
     - `unimplemented` if the window closed and all expected actors are
       `unimplemented`;
     - `expired` if the concept dissolved/retired;
     - `pending` if the window is open and there is no evidence;
     - `unknown` otherwise.
   - Never infer refusal or sabotage from silence. Silence is `unimplemented`
     only after a closed window with the actor observed; otherwise `unknown`.
5. Add `aggregate_organization_agency_decision(decision, implementations)` as a
   pure helper used by tests and update.
6. Enforce caps after generation/tracking; trim oldest with a notice.
7. Add `organization_agency_command_effect` only if needed for audit; it must
   accept an `AgentCommand` and return an `OrganizationAgencyEffect | None`,
   never a command. If unused, omit it.

### Required Interfaces and Contracts

- Proposal generation is deterministic and owner-local; it does not call an LLM,
  a provider, a prompt, or another owner's ledger.
- `expected_effect`/`effect` values are exact observed event kinds, never
  synthetic aliases such as `given`, `taken`, or `dropped`. Do not reuse V4-04
  `_SOURCE_KIND_DOMAINS`.
- Implementation matching uses `ObservedOccurrence` fields only:
  `kind`, `actor_id`, `other_entity_id`, `destination_id`, `success`,
  `public_facts`, `audience_role`, `provenance.source_tick`.
- Anchor extraction is effect-specific:
  - `give` -> `public_facts["give_item_ids"]` (tuple; match any target ref);
  - `take` -> `public_facts["take_item_ids"]` (tuple);
  - `item_stored`/`repository_*` -> `destination_id` or
    `public_facts["target_id"]`/`public_facts["repository_id"]`;
  - `artifact_*` -> `public_facts["artifact_id"]` when present, otherwise
    `target_id`;
  - `project_contributed` -> `public_facts["project_id"]`;
  - `move` -> `destination_id`;
  - `give`/`help`/`feed`/`transport`/`commitment_declared` often have
    `success=None`; require the occurrence and role-visible facts, not
    `success is True`.
- Only match an occurrence when `audience_role` is `actor` or `witness` and the
  required anchor facts are present; a bystander row is not implementation
  evidence.
- `sabotage` is an owner attribution, not an objective fact. The record carries
  `declared_sabotage`/`contrary_effect` provenance and evidence refs.
- A decision with no implementation is `unimplemented`, not `satisfied`; a
  decision with no visibility is `unknown`, not `unimplemented`.
- No helper returns, constructs, submits, or resolves an `AgentCommand`.

### Requirement Evidence

- Original Request: "Collective decisions may fail because members do not act";
  "Track whether organization-level actions were actually implemented";
  compliance, refusal, sabotage.
- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime": agents select
  and submit commands; organizations never execute.
- `src/world/_perception.py` observed occurrence fields 939-1011.
- V4-04 observed-effect mapping bug evidence: real kinds are `give`,
  `item_stored`, `artifact_created`, not `given`/`taken`/`dropped`.

### Error Handling and Logging

- Missing/unresolved procedure: keep the proposal `ACTIVE`/`UNRECOGNIZED` with
  `procedure_unresolved`; never fabricate a procedure.
- Missing target: `target_unresolved`, `resolved=False`; implementation tracking
  uses effect-only matching and marks coverage partial.
- Refusal/sabotage report without corroboration: `refusal_unverified`/
  `sabotage_unverified`; do not upgrade to `refused`/`sabotaged` without the
  required evidence.
- Log INFO milestones with counts only:
  `organization_agency_proposal_generated`, `organization_agency_implementation_status`.
- WARN on truncation/unresolved evidence with safe codes; never log actor sets,
  utterance text, or target payloads.

### Tests

Create `tests/unit/test_organization_agency_actions.py` and
`tests/unit/test_organization_agency_generation.py`:
- Every `OrganizationAgencyEffect` value equals the real observation kind from a
  table-driven engine scenario for `give`, `item_stored`, `artifact_created`,
  `project_contributed`, `attack`, `move`, and `commitment_declared`.
- A real `Give` occurrence exposes `public_facts["give_item_ids"]` (not
  `item_id`) and `success=None`; the matcher accepts it without requiring
  `success is True`.
- A bystander-only occurrence is not implementation evidence.
- A domain rejects an effect outside its allowed set.
- Proposal generation: one proposal per qualifying concept/tick; priority order;
  no proposal for dissolved/retired concepts; cap/truncation notice.
- Self position: support with recognized procedure, oppose on conflicting
  control belief, abstain on unresolved procedure.
- Implementation:
  - one matching `give` → `implemented`;
  - zero matching effects but actor observed → `unimplemented` after window;
  - actor never observed → `unknown`;
  - explicit refusal → `refused`;
  - contrary effect + prior oppose → `sabotaged`;
  - contrary effect alone → `contrary`;
  - testimonial decision with report → `implemented`, without report →
    `unimplemented` after window;
  - decision aggregate for each status.
- No helper returns an `AgentCommand`; AST scan.
- Deterministic output for shuffled occurrences.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_actions.py tests/unit/test_organization_agency_generation.py -q`

### Acceptance Criteria

- Proposals are generated deterministically from owner beliefs.
- Implementation is observed per actor and aggregated per decision.
- Collective failure due to inaction is explicit and distinguishable from
  censoring.
- Refusal/sabotage require evidence and remain beliefs.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_actions.py tests/unit/test_organization_agency_generation.py -q`
- Expected: all tests pass.

## Task 7: Carry the agency ledger through cognition, runtime, checkpoints, and the runner

### Intent

Persist one owner's agency ledger through the existing owner-safe carry path so
later ticks and detached analysis see it, without adding a schema or a peer read.

### Implementation Steps

1. Add `organization_agency: object | None = None` to
   `CognitiveLoopProposal` and `CognitiveLoopResult` in
   `src/agents/cognition/models.py` beside `organization_operations`
   (3925/4248), and add the field plus owner validation to
   `SubjectiveSnapshot.__post_init__` at 1028.
2. Add `organization_agency` to `Perspective` in
   `src/agents/cognition/contracts.py` (175); extend owner validation at 411 and
   pass it through `as_loop_input`/the snapshot projection at 588.
3. In `CognitiveLoop.prepare()`, after `_prepare_organization_operations`
   (4418-4425), add `_prepare_organization_agency(...)`:
   - Return `None` unless `organization_concept_mode` is `DETERMINISTIC`.
   - Read `snapshot.organization_agency` if exact `OrganizationAgencyLedger`.
   - Call `apply_organization_agency_update`, then
     `generate_organization_agency_proposal`, then
     `appraise_organization_agency_position`, then
     `track_organization_agency_implementation`.
   - Store `self._prepared_organization_agency`; include it in the proposal at
     4792 and carry it from the proposal at 5134.
4. Add fork/restore in `src/agents/cognition/fork_state.py` (61) and `loop.py`
   1394-1460.
5. In `src/simulation/agent_runtime.py`:
   - Add `_organization_agency` beside `_organization_operations` in the slots
     (471) and initialization (620).
   - Add `_commit_organization_agency` gated on
     `_loop._organization_concept_mode is DETERMINISTIC`; reject wrong type/owner.
   - Call it after `complete()` with the result field at 2717.
   - Add checkpoint restore validation at 3271 and pass the ledger into
     `build_perspective` at 3392.
6. In `src/simulation/perception.py`, add `organization_agency: object | None =
   None` at 141 and pass it into `Perspective` at 350.
7. In `src/simulation/run_control.py`, add the checkpoint field at 615 and the
   owner validator at 771.
8. In `src/simulation/runner.py`, add
   `export_organization_agency_ledgers()` following
   `export_organization_operation_ledgers()` at 5340-5368; populate
   `SimulationRunnerResult.organization_agency_ledgers` in
   `runner_models.py` at 6375 and validate ordered sequences at 6656-6666. No
   result schema bump.
9. In `src/agents/cognition/__init__.py`, export
   `require_owner_organization_agency`, `empty_organization_agency_ledger`, and
   the update/generation/appraisal/tracking functions.

### Required Interfaces and Contracts

- The carry path is owner-only: a snapshot or checkpoint with another owner's
  ledger fails closed with `organization_agency_foreign_ledger`.
- A checkpoint without the field loads as `None`; older checkpoints remain
  valid.
- The runner result field is additive and absent/empty for flags-off runs.
- No peer ledger, `WorldState`, event store, command, or analysis type enters the
  carry path.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" and "Memory,
  testimony, and subjective concepts".
- V4-04 Task 7 carry pattern (models/contracts/loop/runtime/checkpoints/runner).
- Original Request: agent cognition remains the source of intentional actions.

### Error Handling and Logging

- Reject a foreign ledger with ERROR `organization_agency_carry_rejected
  reason=owner_mismatch`, safe id only.
- Reject an invalid type with WARN `reason=invalid_type`.
- Log DEBUG counts on commit and restore; never actor sets or proposal content.

### Tests

Extend `tests/unit/test_organization_agency_runtime.py`:
- Prepare produces an empty ledger when enabled with no evidence.
- Prepare returns `None` when disabled.
- `build_perspective(..., organization_agency=ledger)` carries the exact ledger
  into `Perspective`; omitting it yields `None`.
- Live/restored perspective parity includes the agency ledger.
- A foreign owner ledger fails closed on perspective/checkpoint/commit.
- An older checkpoint without the field restores `None`.
- `SimulationRunnerResult.organization_agency_ledgers` rejects a set or an
  unordered sequence and preserves tuple order.
- Runner result exports one ledger per owner; flags-off exports none.
- No new runner schema/result version.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_runtime.py tests/unit/test_organization_runtime.py tests/unit/test_organization_operations_runtime.py -q`

### Acceptance Criteria

- The ledger survives prepare → finalize → checkpoint → restore → result.
- Owner isolation is enforced at every boundary.
- Flags-off behavior is unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_runtime.py -q`
- Expected: all tests pass.

## Task 8: Wire collective-agency claims into existing deliberation

### Intent

Let an agent express its proposal/position through ordinary `Talk`/`Tell` while
keeping command selection and submission entirely in existing deliberation.

### Implementation Steps

1. In `src/agents/cognition/deliberation.py` at 1246-1285, after the
   `org_v1`/`org_op_v1` decoration, add
   `organization_agency_communicate_utterance`:
   - Read `snapshot.organization_agency` if prepared arguments are absent.
   - Determine the claim using a deterministic priority and tie-break:
     - If the owner has a newly generated `ACTIVE` proposal for the current tick
       and it has not been communicated, emit `propose` for the lowest
       `proposal_id`.
     - Else if the owner has a position on the current revision, emit that
       stance (`support`/`oppose`/`abstain`/`amend`/`withdraw`) for the lowest
       `(proposal_id, revision)`.
     - Else if the owner has a refusal/report for a decision, emit `refuse` or
       `report` for the lowest `decision_id`.
   - At most one `org_ca_v1` relation per command.
2. Do not change the selected command class, recipient, or existing utterance
   relations. Do not add a new deliberation stage.
3. Do not construct, replace, or submit an `AgentCommand`; the helper only
   decorates an already-selected `Talk`/`Tell`.
4. Ensure the decoration is skipped when the owner has no claim or when the
   command is not `Talk`/`Tell`.
5. Add a boundary test that `organization_agency*` modules contain no
   `AgentCommand(` construction and no import of `world.actions` command classes
   except for `Talk`/`Tell` type checks.

### Required Interfaces and Contracts

- `organization_agency_communicate_utterance(command, claims)` is pure and
  returns a new command of the same class.
- Existing `org_v1` and `org_op_v1` decoration order is preserved.
- No free text, label payload, or separate proposal command is added.
- The selected command remains the agent's own intentional action.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime": one
  `AgentCommand` per agent, ordinary admission.
- V4-03/V4-04 deliberation decoration (1246-1285).
- Original Request: no organization super-agent; agent cognition remains the
  source of intentional actions.

### Error Handling and Logging

- If decoration fails validation, keep the original command and log WARN
  `organization_agency_decoration_skipped reason=invalid_claim`; never fail the
  tick.
- Log DEBUG `organization_agency_communicated owner_id=%s predicate=%s`
  (predicate only, no utterance text).

### Tests

Extend `tests/unit/test_organization_agency_communication.py` and
`tests/unit/test_organization_agency_runtime.py`:
- A selected `Talk`/`Tell` gets exactly one `org_ca_v1` relation when a claim
  exists.
- No relation when there is no claim, or when the command is `Wait`/`Move`.
- Existing `org_v1`/`org_op_v1` relations remain and the 32-relation cap holds.
- The command class, recipient, and original utterance are preserved.
- AST scan finds no `AgentCommand(` construction in agency modules.
- A full tick with agency claims produces the same physical command as the same
  run without communication decoration (only the utterance relation differs).

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_communication.py tests/unit/test_organization_agency_runtime.py tests/architecture/test_organization_agency_boundaries.py -q`

### Acceptance Criteria

- Agency claims travel only inside existing `Talk`/`Tell`.
- No new command, event, observer semantic type, or free-text payload.
- Command selection remains agent-authored.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_communication.py tests/unit/test_organization_agency_runtime.py -q`
- Expected: all tests pass.

## Phase Risks and Mitigations

- Risk: the new sidecar duplicates V3-31 instead of composing with it.
  Mitigation: V3-31 types are read-only optional evidence; V4-05 records are
  organization-keyed and use separate IDs/frames. Task 19 asserts V3-31 files
  are unchanged.
- Risk: implementation tracking repeats the V4-04 synthetic-kind bug.
  Mitigation: `ORGANIZATION_AGENCY_EFFECTS` uses real observation kinds and
  Task 6/19 table-driven engine tests prove the mapping.
- Risk: refusal/sabotage are inferred from silence.
  Mitigation: explicit evidence requirements and censoring tests.
- Risk: a global OrganizationLLM slips in.
  Mitigation: boundary scan for `llm`, prompts, providers, and shared context.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
