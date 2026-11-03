# Phase 2: Owner-Scoped Dispute Beliefs

Plan: [index.md](index.md)
Tasks: 4-9
Depends on: Phase 1 / Tasks 1-3

## Objective

Implement the owner-scoped dispute ledger: typed cases, attributed claims and
counterclaims, testimony, evidence references, rule references, authority
references, mediation links, proposed resolutions, and per-party
accepted/rejected declarations. The ledger must support sincere memory-dependent
disagreement and must never become an objective justice oracle.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/formal_rules.py` | `FormalRuleLedger` 1289-1395; `apply_formal_rule_update` 1811-1885; forbidden-input scan | Owner-scoped ledger, evidence collection, and update shape to mirror. |
| `src/agents/cognition/formal_rule_communication.py` | frame subject 54; `FormalRuleClaim` 120-260; encode/parse 300-470; utterance decorator 520-620 | Bounded speech-frame pattern. |
| `src/agents/cognition/mediation.py` | policy 74; forbidden fields 133; `MediationAct` 158-168; `MediationResponseKind` 169-180; `MediationCaseStatus` 197-220; `MediationLedger` 1373-1398; `appraise_mediation_authority` 3068 | Existing case/account/recommendation/response/outcome semantics to integrate with, not duplicate. |
| `src/agents/cognition/mediation_communication.py` | policy 49; encode 167; parse 306; `mediation_communicate_utterance` 695 | Speech relation and utterance-decorating pattern. |
| `src/agents/cognition/mediation_actions.py` | `_SUPPORTED_ACTIONS` 34; `compile_mediation_undertaking` 75-125; `record_mediation_attempt` 126 | The only supported undertaking path; reuse it. |
| `src/agents/cognition/structured_commitments.py` | `COMMITMENT_STATUSES`, `CommitmentInterpretation`, `CommitmentRevision`, `apply_structured_commitment_update` | Contested-debt and broken-promise evidence, including revision-on-dispute. |
| `src/agents/cognition/subjective_value.py` | `ValuationRow`, `SubjectiveValuationLedger`, `ExchangeView` | Valuation/exchange evidence references for ownership and appropriation claims. |
| `src/agents/cognition/offices.py` | `OfficeFunction.CONFLICT_MEDIATION`, `OfficeAuthorityKind`, `OfficeOccupantClaim` | Mediator/authority beliefs; no judge role. |
| `src/agents/cognition/institution_concepts.py` | `InstitutionPatternChannel`, `InstitutionConceptStatus`, `InstitutionConcept` | Legitimacy/social-expectation evidence. |
| `src/agents/cognition/organization_concepts.py` | `orgc-` ids, procedures, records, commitments, roles | Organization authority/procedure references. |
| `src/agents/cognition/organization_agency.py` | collective decisions, implementation/compliance/refusal | Collective-decision references without an organization will. |
| `src/world/observations.py` | `ObservationProvenance` 232-281; `ObservedOccurrence` 973-1017; `ObservedCommunication` 1020-1035 | Evidence refs and opaque event correlation. |
| `src/world/communications.py` | `CommunicationRelation`, `origin_utterance`, `retell_utterance`, relation limits | `dsp_v1` frame carrier and origin/retell semantics. |
| `src/simulation/perception.py` | `build_perspective` 143, 354 | Where the carried ledger enters cognition. |
| `src/simulation/agent_runtime.py` | `_commit_formal_rules` 1368-1389; result application 2788; checkpoint 3364-3373, 3485 | Runtime carry/checkpoint pattern. |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint.formal_rules` 617; owner validation 791-796 | Checkpoint field and owner check pattern. |
| `src/simulation/runner_models.py` | `SimulationRunnerResult.formal_rule_ledgers` 6380, 6683-6695 | Ordered ledger result field and validation. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/legal_disputes.py` | modify | Records, ledger, validation, update, references, resolutions, deliberation hooks. |
| `src/agents/cognition/legal_dispute_communication.py` | create | `dsp_v1` acts, frame codec, relation conversion, utterance decorator. |
| `src/agents/cognition/__init__.py` | modify | Export the public dispute contracts and helpers. |
| `src/agents/cognition/models.py` | modify | Carry `disputes` on snapshot/proposal/result. |
| `src/agents/cognition/contracts.py` | modify | Carry `disputes` on `Perspective`. |
| `src/agents/cognition/loop.py` | modify | Prepare/record/return disputes; fork state. |
| `src/simulation/perception.py` | modify | Accept and forward `disputes`. |
| `src/simulation/agent_runtime.py` | modify | Commit/checkpoint/export disputes. |
| `src/simulation/run_control.py` | modify | `AgentRuntimeCheckpoint.disputes` and owner validation. |
| `src/simulation/runner.py` | modify | `export_dispute_ledgers()` and result assembly. |
| `src/simulation/runner_models.py` | modify | `SimulationRunnerResult.dispute_ledgers` ordered validation. |
| `src/simulation/__init__.py` | modify | Export the dispute snapshot/port/ledger contracts. |
| `tests/unit/test_dispute_records.py` | create | Record/ledger invariants. |
| `tests/unit/test_dispute_communication.py` | create | Frame encode/decode/delivery. |
| `tests/unit/test_dispute_stages.py` | create | Claim/testimony/evidence collection. |
| `tests/unit/test_dispute_reasoning.py` | create | Rule/authority/mediation references. |
| `tests/unit/test_dispute_resolutions.py` | create | Proposal/accept/reject/expiry. |
| `tests/unit/test_dispute_runtime.py` | create | Carry/checkpoint/export. |
| `tests/unit/test_dispute_deliberation.py` | create | Preference/penalty hooks. |

## Task 4: Define dispute records and ledger invariants

### Intent

Freeze the exact record shapes and referential invariants before any collection
or analysis code exists. Later tasks must not invent fields such as `verdict`,
`liable`, or `true_owner`.

### Implementation Steps

1. In `src/agents/cognition/legal_disputes.py`, define frozen, slotted
   dataclasses with `__post_init__` validation:
   - `DisputeCase`: `case_id`, `owner_id`, `case_ref`, `kind`, `subject_kind`,
     `subject_token`, `subject_digest`, `context_key`, `party_ids`,
     `claimant_ids`, `respondent_ids`, `status`, `first_tick`, `last_tick`,
     `window_first_tick`, `window_last_tick`, `origin_ref`, `uncertainty`,
     `notices`.
   - `DisputeClaim`: `claim_id`, `claim_ref`, `case_ref`, `owner_id`,
     `claimant_id`, `respondent_id`, `role`, `claim_kind`, `polarity`,
     `subject_kind`, `subject_token`, `subject_digest`, `action_token`,
     `item_token`, `quantity`, `terms_digest`, `counters_claim_ref`,
     `rule_reference_token`, `evidence_ids`, `provenance`, `confidence`,
     `first_tick`, `last_tick`, `active`, `notices`.
   - `DisputeTestimony`: `testimony_id`, `case_ref`, `claim_ref`, `owner_id`,
     `speaker_id`, `channel`, `root_ref`, `independently_evidenced`,
     `evidence_id`, `tick`, `provenance`, `active`.
   - `DisputeEvidence`: `evidence_id`, `case_ref`, `claim_ref`, `owner_id`,
     `channel`, `reference_kind`, `reference_id`, `tick`, `actor_id`,
     `independently_evidenced`, `provenance`, `active`.
   - `DisputeRuleReference`: `rule_reference_id`, `case_ref`, `claim_ref`,
     `owner_id`, `system_ref`, `rule_id`, `version_number`, `constraint_kind`,
     `scope_digest`, `applicability`, `interpretation`, `status`, `provenance`,
     `first_tick`, `last_tick`.
   - `DisputeAuthorityReference`: `authority_reference_id`, `case_ref`,
     `owner_id`, `authority_kind`, `reference_id`, `strength`, `uncertainty`,
     `provenance`, `dissenting`, `first_tick`, `last_tick`.
   - `DisputeMediationReference`: `mediation_reference_id`, `case_ref`,
     `owner_id`, `mediation_case_ref`, `recommendation_ref`, `response_ref`,
     `outcome_ref`, `link_status`, `provenance`, `first_tick`, `last_tick`.
   - `DisputeResolutionTerm`: `term_kind`, `party_id`, `counterparty_id`,
     `item_token`, `service_token`, `action_token`, `quantity`, `due_tick`.
   - `DisputeResolution`: `resolution_id`, `resolution_ref`, `case_ref`,
     `owner_id`, `proposer_id`, `source`, `terms`, `terms_digest`, `status`,
     `first_tick`, `last_tick`, `expires_tick`, `provenance`, `notices`.
   - `DisputeResolutionResponse`: `response_id`, `resolution_id`,
     `resolution_ref`, `case_ref`, `owner_id`, `party_id`, `kind`, `tick`,
     `terms_digest`, `active`, `provenance`, `counter_resolution_ref`.
2. Define `DisputeLedger` with `owner_id`, `cases`, `claims`, `testimony`,
   `evidence`, `rule_references`, `authority_references`,
   `mediation_references`, `resolutions`, `resolution_responses`, `notices`,
   `policy_version`, `first_observed_tick`, `last_observed_tick`,
   `observation_count`, `pruned_case_count`, `pruned_claim_count`,
   `pruned_testimony_count`, `pruned_evidence_count`,
   `pruned_resolution_count`, `pruned_reference_count`.
3. Add `empty_dispute_ledger(owner_id, policy=None)` and
   `require_owner_disputes(value, owner_id, *, field_name)`.
4. Validate:
   - every row `owner_id` equals the ledger owner;
   - every id matches its prefix and is unique;
   - every `case_ref` resolves to a case in the same ledger;
   - every `claim_ref` resolves to a claim in the same ledger;
   - every `evidence_id` in a claim resolves to an evidence row in the same
     ledger;
   - every rule reference `claim_ref` resolves to a claim in the same ledger;
   - every `resolution_ref` resolves to a resolution in the same ledger;
   - every response `resolution_ref` resolves to a resolution and its
     `terms_digest` matches that resolution;
   - every testimony `evidence_id` resolves to an evidence row in the same
     ledger;
   - `party_ids` contains the owner exactly once, is sorted, and is bounded by
     `max_parties`;
   - `claimant_id` and `respondent_id` are in `party_ids`;
   - every resolution term `party_id` and `counterparty_id` is in `party_ids`;
   - every response `party_id` is in `party_ids`;
   - `role=counterclaim` requires `counters_claim_ref` and a different claimant;
   - every `counters_claim_ref` resolves to a claim in the same ledger;
   - `polarity=uncertain` is legal and is not treated as denial;
   - `quantity` is `0..3`; `confidence`, `strength`, and `uncertainty` are
     quantized to six decimals in `[0, 1]`;
   - each resolution has at most `max_terms_per_resolution` terms;
   - each resolution has at most one active response per party;
   - record counts respect every policy limit;
   - `policy_version` equals `DISPUTE_POLICY_VERSION`.
5. Reject any field name in `DISPUTE_FORBIDDEN_FIELD_NAMES` recursively. Reject
   any `WorldEvent`, `WorldState`, event store, command, or peer ledger object
   anywhere in the ledger.
6. Add properties `enabled`, `has_content`, `coverage` (`complete` or `partial`),
   `open_cases`, and `counterclaims`. `coverage` is `partial` whenever any
   `pruned_*` count is non-zero or any row reports reduced evidence; otherwise
   `complete`. An enabled ledger with zero rows is `complete` and `has_content`
   is `False`; that is different from an absent or disabled ledger.
7. Add `dispute_ledger_digest(ledger)` using canonical JSON over sorted records
   for determinism tests.
8. Every truncation appends a bounded notice and increments the matching pruned
   count; never silently drop. Cover case, claim, testimony, evidence,
   resolution, and reference caps.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class DisputeLedger:
    owner_id: str
    cases: tuple[DisputeCase, ...] = ()
    claims: tuple[DisputeClaim, ...] = ()
    testimony: tuple[DisputeTestimony, ...] = ()
    evidence: tuple[DisputeEvidence, ...] = ()
    rule_references: tuple[DisputeRuleReference, ...] = ()
    authority_references: tuple[DisputeAuthorityReference, ...] = ()
    mediation_references: tuple[DisputeMediationReference, ...] = ()
    resolutions: tuple[DisputeResolution, ...] = ()
    resolution_responses: tuple[DisputeResolutionResponse, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = DISPUTE_POLICY_VERSION
    ...

def empty_dispute_ledger(owner_id: str, policy: DisputePolicy | None = None) -> DisputeLedger: ...
def require_owner_disputes(value: object, owner_id: str, *, field_name: str) -> DisputeLedger: ...
```

Compatibility invariants:

- All tuples are ordered deterministically by stable keys.
- No record stores a `winner`, `verdict`, `liable`, `guilt`, `true_owner`,
  `binding`, `enforced_by_world`, or `global_dispute_registry` field.
- The ledger is defensively detached; callers cannot mutate nested tuples.

### Requirement Evidence

- Original Request "Represent claims made by parties separately" and the support
  list.
- `.ai-factory/ARCHITECTURE.md` Key Principle 1 and "Memory, testimony, and
  subjective concepts".
- `src/agents/cognition/formal_rules.py` 1289-1395: record/ledger validation
  pattern.
- `src/agents/cognition/mediation.py` 133, 1373-1398: forbidden-field and
  owner-scoped ledger pattern.

### Error Handling and Logging

- Invalid owner: `DisputeError("dispute_owner_mismatch")`.
- Unknown reference: `DisputeError("dispute_unknown_reference")`.
- Duplicate id: `DisputeError("dispute_duplicate_id")`.
- Capacity overflow: deterministic truncation plus `dispute_truncated`.
- Forbidden field: `DisputeError("dispute_forbidden_field")`.
- Log only counts and codes at DEBUG; never record content.

### Tests

`tests/unit/test_dispute_records.py`:

- `test_empty_ledger_is_owner_scoped_and_disabled_without_content`
- `test_claim_and_counterclaim_are_separate_and_attributed`
- `test_unknown_case_claim_or_resolution_reference_fails_closed`
- `test_party_and_quantity_bounds`
- `test_forbidden_justice_fields_are_rejected_recursively`
- `test_truncation_is_explicit_and_deterministic`
- `test_each_ledger_cap_increments_its_pruned_count`
- `test_partial_coverage_when_any_pruned_count_is_nonzero`
- `test_enabled_empty_ledger_is_complete_not_partial`
- `test_ledger_digest_is_order_independent`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_records.py -q`.

### Acceptance Criteria

- Every record validates its owner, references, bounds, and enum values.
- Opposing claims can coexist in one ledger.
- No forbidden justice field can be constructed.
- Truncation is explicit, never silent.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_records.py -q`
- Expected result: all tests pass.

## Task 5: Add bounded dsp_v1 dispute speech frames

### Intent

Let agents assert claims, counterclaims, testimony, evidence, rule references,
mediation links, proposed resolutions, and accepted/rejected resolutions inside
existing `Talk`/`Tell` speech without adding commands, events, or free-text
payloads.

### Implementation Steps

1. Create `src/agents/cognition/legal_dispute_communication.py` with policy
   `dispute-communication.v1`, frame subject `dsp_v1`, and a closed
   `DisputeAct`: `claim`, `counterclaim`, `testify`, `cite_evidence`,
   `cite_rule`, `reference_mediation`, `propose_resolution`,
   `accept_resolution`, `reject_resolution`, `withdraw_claim`.
2. Map predicates exactly: `dsp_claim`, `dsp_counterclaim`, `dsp_testify`,
   `dsp_evidence`, `dsp_rule`, `dsp_mediation`, `dsp_propose`, `dsp_accept`,
   `dsp_reject`, `dsp_withdraw`.
3. Define the fixed 17-field payload in this order: `case_ref`, `claim_ref`,
   `role`, `kind`, `polarity`, `party_ref`, `subject_kind`, `subject_token`,
   `action_token`, `evidence_ref`, `rule_ref`, `mediation_ref`,
   `resolution_ref`, `terms_digest`, `terms`, `direct`, `root_ref`.
4. Encode as `dsp_v1:<predicate>:<17 colon-separated fields>`; absent fields use
   the literal `none`. Require exactly 19 colon-separated parts, no whitespace or
   control characters, and at most `max_frame_chars=768`.
   `terms` is a bounded compact payload: up to four terms separated by `|`, each
   term colon-free with eight `,`-separated fields
   `term_kind,party,counterparty,item_token,quantity,service_token,action_token,due_tick`.
   Every token is `none` or a bounded stable reference token matching
   `[A-Za-z0-9][A-Za-z0-9._@-]*` with at most 128 characters; the whole payload
   is at most 256 characters. `terms_digest` is the canonical digest of the
   decoded terms.
5. Define `DisputeFrame` as a frozen slotted dataclass with per-act required and
   allowed fields:
   - `claim`: `case_ref`, `role`, `kind`, `polarity`, `party_ref`,
     `subject_kind`, `subject_token`.
   - `counterclaim`: `case_ref`, `claim_ref`, `role`, `kind`, `polarity`,
     `party_ref`, `subject_kind`, `subject_token`.
   - `testify`: `case_ref`, `claim_ref`, `party_ref`, `direct`, `root_ref`.
   - `cite_evidence`: `case_ref`, `claim_ref`, `evidence_ref`.
   - `cite_rule`: `case_ref`, `claim_ref`, `rule_ref`; `rule_ref` is encoded as
     `<frl-id>@<version_number>` so the receiver can detect version mismatch
     without a free-text field.
   - `reference_mediation`: `case_ref`, `mediation_ref`.
   - `propose_resolution`: `case_ref`, `resolution_ref`, `terms_digest`,
     `terms`.
   - `accept_resolution`: `case_ref`, `resolution_ref`, `party_ref`,
     `terms_digest`.
   - `reject_resolution`: `case_ref`, `resolution_ref`, `party_ref`,
     `terms_digest`.
   - `withdraw_claim`: `case_ref`, `claim_ref`, `party_ref`.
6. `party_ref` is informational and must equal the verified speaker. The parser
   takes the actor from `ObservedCommunication.provenance` /
   `speaker_id`; if the frame party differs, return `None` and record a
   `dispute_party_mismatch` notice. A speaker can never assert another party's
   claim or acceptance.
7. `direct` is `true` or `false` only for `testify`; `root_ref` is required for
   `testify` and must be a stable reference token. For all other acts both fields
   are `none`. `terms` is required only for `propose_resolution`; for
   `accept_resolution` and `reject_resolution` it must be `none` and the
   `terms_digest` is authoritative for matching. For every other act both
   `terms` and `terms_digest` are `none`.
8. Add `encode_dispute_frame(frame) -> str`,
   `parse_dispute_frame(text) -> DisputeFrame | None`,
   `dispute_frame_relation(frame) -> CommunicationRelation`, and
   `parse_dispute_frame_relation(relation) -> DisputeFrame | None`.
9. Add `dispute_communicate_utterance(command, frame)`:
   - accepts only existing `Talk` and `Tell`;
   - appends at most one `dsp_v1` relation and preserves all other relations;
   - returns the original command unchanged when the relation budget is full;
   - rebuilds an `origin_utterance` with `text="dispute"`, hop reset to 0, and
     `source_basis=UNREFERENCED`;
   - never creates, replaces, or rewrites a command.
10. No command, event, observer semantic type, free-text body, or new relation
    subject other than `dsp_v1` is added.

### Required Interfaces and Contracts

```python
DISPUTE_COMMUNICATION_POLICY_VERSION: Final[str] = "dispute-communication.v1"
DISPUTE_FRAME_SUBJECT: Final[str] = "dsp_v1"

class DisputeAct(StrEnum):
    CLAIM = "claim"
    COUNTERCLAIM = "counterclaim"
    TESTIFY = "testify"
    CITE_EVIDENCE = "cite_evidence"
    CITE_RULE = "cite_rule"
    REFERENCE_MEDIATION = "reference_mediation"
    PROPOSE_RESOLUTION = "propose_resolution"
    ACCEPT_RESOLUTION = "accept_resolution"
    REJECT_RESOLUTION = "reject_resolution"
    WITHDRAW_CLAIM = "withdraw_claim"

def encode_dispute_frame(frame: DisputeFrame) -> str: ...
def parse_dispute_frame(text: str) -> DisputeFrame | None: ...
def dispute_communicate_utterance(command: object, frame: DisputeFrame) -> object: ...
```

Compatibility invariants:

- `fr_v1`, `org_v1`, `org_op_v1`, `org_ca_v1`, `im_v1`, and mediation frames are
  unchanged.
- A frame carries no free-form text, no narrative, no evidence payload, and no
  resolution body beyond a digest.
- A delivered frame proves delivery only; it is not truth.

### Requirement Evidence

- Original Request support list: claim, counterclaim, testimony, evidence
  references, rule references, mediation, proposed resolution, accepted/rejected
  resolution.
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts" and
  "Structured `Talk`/`Ask`/`Tell` proves delivery only".
- `src/agents/cognition/formal_rule_communication.py` 54-470: bounded frame and
  delivery pattern.
- `src/agents/cognition/mediation_communication.py` 49, 167-350, 695: relation
  and utterance-decorating pattern.

### Error Handling and Logging

- Invalid frame shape returns `None` from the parser; callers record
  `dispute_invalid_frame` and do not mint a claim.
- Party mismatch returns `None`; DEBUG `dispute_frame_rejected reason=party_mismatch`.
- Capacity overflow returns the original command unchanged; DEBUG
  `dispute_frame_skipped reason=relation_limit`.
- Never log frame content, subject tokens, parties, or resolution digests.

### Tests

`tests/unit/test_dispute_communication.py`:

- `test_each_act_round_trips_and_rejects_missing_fields`
- `test_party_must_equal_verified_speaker`
- `test_direct_and_root_are_testimony_only`
- `test_frame_rejects_free_text_and_control_characters`
- `test_decorator_preserves_command_type_and_other_relations`
- `test_decorator_returns_original_on_relation_limit`
- `test_no_new_command_or_event_is_created`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_communication.py -q`.

### Acceptance Criteria

- All ten acts encode/decode exactly.
- A speaker cannot assert another party's claim or acceptance.
- The decorator only decorates an existing `Talk`/`Tell`.
- No free-text or payload field exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_communication.py -q`
- Expected result: all tests pass.

## Task 6: Collect claims, testimony, and evidence

### Intent

Build one owner's dispute view from that owner's observation and prepared
same-owner ledgers. Mere observation supplies evidence, not a case; a case
requires a claim, a disputed commitment, or a mediation case involving the
owner.

### Implementation Steps

1. Add:
   ```python
   def apply_dispute_update(
       owner_id: AgentId,
       tick: int,
       observation: object,
       prior: DisputeLedger | None,
       *,
       retrieved_memory_context: object | None = None,
       structured_commitments: object | None = None,
       subjective_valuations: object | None = None,
       mediation: object | None = None,
       formal_rules: object | None = None,
       offices: object | None = None,
       institution_concepts: object | None = None,
       organization_concepts: object | None = None,
       collective_decisions: object | None = None,
       policy: DisputePolicy | None = None,
   ) -> DisputeLedger: ...
   ```
2. Validate the owner, tick, policy, and prior. Reject forbidden inputs
   recursively as in Task 4. If `prior` exists, require owner and policy version
   match.
3. Parse incoming `dsp_v1` claims from `observation.communications` where the
   listener is the owner. For each `claim`/`counterclaim` frame:
   - set `claimant_id = verified speaker` and `respondent_id = frame.party_ref`;
   - create or update a case keyed by the portable
     `dispute_case_ref(subject_token, party_ids)` only when the owner is the
     claimant, the respondent, or an explicitly addressed named party; otherwise
     record testimony/evidence only if a matching case already exists and never
     create a new case from third-party gossip;
   - create a `DisputeClaim` with the verified attribution; mint
     `claim_ref = dispute_claim_ref(case_ref, claimant_id, role, claim_kind,
     polarity, subject_digest)` and `claim_id = dispute_claim_id(owner_id,
     claim_ref)`; a counterclaim sets `counters_claim_ref` to the referenced
     portable claim ref; the owner's own outgoing claim is recorded by
     `record_dispute_utterance`, not by this incoming path;
   - create a `DisputeTestimony` only for `testify` frames, keyed by the
     portable `claim_ref`, with `channel` derived from `direct` and proof roots;
   - create `DisputeEvidence` for `cite_evidence` frames only if the reference
     token is well formed and keyed by the portable `claim_ref`; otherwise
     record `dispute_unknown_reference`;
   - create a `DisputeResolution` for a `propose_resolution` frame only when
     `terms` decodes to at most four valid terms and `terms_digest` matches;
     the proposer is the verified speaker and the source is `unilateral` unless
     a linked mediation recommendation exists;
   - record an `accept_resolution` or `reject_resolution` only when the
     referenced resolution already exists in the owner's ledger and the digest
     matches; otherwise record `dispute_unknown_reference` and no response;
   - for `cite_rule`, set `rule_reference_token` on the referenced claim and
     leave resolution to Task 7; for `reference_mediation`, record a typed
     mediation evidence reference for Task 7 to upgrade; for `withdraw_claim`,
     deactivate the referenced claim with `provenance=self_asserted`.
4. Collect own commitment evidence from `structured_commitments.interpretations`:
   - `status in {"disputed", "violated", "partial"}` creates a case kind
     `contested_debt` when `kind in {"debt", "future_exchange"}` and
     `broken_promise` when `kind in {"promise", "conditional_agreement",
     "service_obligation"}`;
   - the owner is `claimant_id`; the debtor/creditor counterpart is
     `respondent_id`;
   - evidence ref `commitment:<local_id>` with channel `derived` and
     `provenance=derived_from_memory`.
5. Collect own mediation cases from `mediation.cases` where
   `owner_id == owner` and the owner is in `party_ids`. Create a case kind
   `other` until an explicit claim supplies a more specific kind; refining the
   kind does not change the portable `case_ref`. Link a
   `DisputeMediationReference` in Task 7.
6. Collect evidence references from:
   - `observation.occurrences` → `observed_occurrence` using the opaque
     `provenance.source_event_id`;
   - `observation.communications` → `observed_communication`;
   - visible artifacts/repositories → `artifact` / `repository_entry`;
   - `retrieved_memory_context` → `memory_trace` / `reconstructed_memory` by
     stable id through `_memory_evidence_refs`; when absent, no remembered
     evidence is created and no trace id is invented;
   - `subjective_valuations` → `valuation`;
   - `structured_commitments` → `commitment`.
   Evidence is attached to a claim only when the claim already references it or
   when the evidence is the direct source of a derived claim. Do not invent a
   claim from observation alone.
7. Add `record_dispute_utterance(ledger, *, owner_id, tick, command, identity,
   policy=None) -> DisputeLedger`:
   - parse the selected command's `dsp_v1` relation;
   - record the owner's own claim/counterclaim/accept/reject/withdraw;
   - require `party_ref == owner`;
   - never create a command.
8. Rebuild the ledger deterministically: sort cases by `(first_tick, case_id)`,
   claims by `(first_tick, claim_id)`, testimony by `(tick, testimony_id)`,
   evidence by `(tick, evidence_id)`, and all reference/resolution rows by their
   ids. Deduplicate by id. Apply caps with explicit notices.
9. Preserve prior rows that are still supported; do not delete a claim because a
   later observation is missing. Expire only through explicit status rules.
10. The update must never read a peer ledger, `WorldState`, event store, command,
    analysis row, or published snapshot.

### Required Interfaces and Contracts

```python
def record_dispute_utterance(
    ledger: DisputeLedger,
    *,
    owner_id: str,
    tick: int,
    command: object,
    identity: object | None = None,
    policy: DisputePolicy | None = None,
) -> DisputeLedger: ...
```

Compatibility invariants:

- Two owners receiving the same event can derive different cases and evidence
  sets; neither is corrected.
- A case can exist with a claim but no resolution; a resolution cannot exist
  without a case.
- Observation alone never creates a claim or a case.
- A claim can be `active=False` only through an explicit withdraw or expiry.

### Requirement Evidence

- Original Request "Represent claims made by parties separately" and "Agents may
  sincerely disagree because memories differ".
- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" and "Memory,
  testimony, and subjective concepts".
- `src/agents/cognition/loop.py` 2716-2760: `retrieved_memory_context=memory`
  seam used by mediation and adopted by disputes.
- `src/agents/cognition/structured_commitments.py` statuses and revisions.
- `src/agents/cognition/mediation.py` case/account/evidence structures.
- `src/world/observations.py` 232-281, 973-1035.

### Error Handling and Logging

- Peer ledger or forbidden object: `DisputeError("dispute_forbidden_input")`.
- Malformed frame: notice `dispute_invalid_frame`; no claim.
- Unknown evidence kind: notice `dispute_unknown_reference`; no evidence.
- Capacity: notice `dispute_truncated` plus pruned count.
- DEBUG counts only: `dispute_update owner=%s cases=%s claims=%s evidence=%s`.

### Tests

`tests/unit/test_dispute_stages.py`:

- `test_observation_alone_does_not_create_a_claim`
- `test_own_claim_creates_case_and_claim`
- `test_counterclaim_is_attributed_to_the_speaker`
- `test_two_owners_with_different_memories_retain_both_claims`
- `test_commitment_dispute_creates_contested_debt_or_broken_promise`
- `test_mediation_case_creates_case_without_binding_outcome`
- `test_evidence_references_are_typed_and_opaque`
- `test_missing_memory_context_creates_no_remembered_evidence`
- `test_prior_claims_are_not_deleted_by_missing_later_evidence`
- `test_shuffled_delivery_produces_identical_ledger`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_stages.py -q`.

### Acceptance Criteria

- Claims and counterclaims are attributed and separate.
- Conflicting memories are retained without reconciliation.
- Evidence references are typed and never carry `WorldEvent` bodies.
- Observation alone does not fabricate a dispute.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_stages.py -q`
- Expected result: all tests pass.

## Task 7: Derive rule, authority, and mediation references

### Intent

Add legal-reasoning structure: rule references, authority references, and
mediation links. These are beliefs about applicable constraints and roles, not
permissions, verdicts, or enforcement.

### Implementation Steps

1. Add `derive_rule_references(ledger, *, formal_rules, owner_id, policy=None)`:
   - for each active claim with `rule_reference_token`, parse the token as
     `<frl-id>@<version_number>` and look up the rule in the owner's
     `FormalRuleLedger`; resolve the version as
     `rule.versions[version_number - 1]` and verify
     `version.version_number == version_number` before accepting it; an
     out-of-range or non-contiguous version becomes `version_mismatch`;
   - if found, create `DisputeRuleReference` with `claim_ref`, `status=resolved`,
     `constraint_kind`, `scope_digest`, `applicability`, and `interpretation`;
   - if not found, create `status=orphaned` and keep the claim unchanged;
   - if the rule id exists but the version does not, create
     `status=version_mismatch`;
   - if the owner rule is `contested`, create `status=contested`;
   - if retired, create `status=retired`.
2. Derive `applicability` deterministically from the claim kind and rule
   constraint kind:
   - a claim about `resource_taken` with a `prohibition` rule is `applies`;
   - a claim about `debt_owed` with an `obligation` rule is `applies`;
   - a claim about `term_meaning` with any rule is `uncertain` unless the rule's
     scope digest matches the claim subject digest;
   - otherwise `uncertain`.
   This is a belief heuristic, not a legal conclusion.
3. Derive `interpretation` from the frame/claim `terms_digest` and evidence:
   `literal` when the claim cites a written record with an intact representation;
   `narrow`/`broad` when the owner has competing interpretations; `custom` when a
   norm/convention exists; `unknown` otherwise.
4. Add `derive_authority_references(ledger, *, owner_id, offices,
   institution_concepts, organization_concepts, collective_decisions,
   mediation, tick, policy=None)`:
   - cite `office` when an office concept has `function=conflict_mediation` and a
     matching `context_key`; store `office_id`, occupant/support strength, and
     dissenting flag;
   - cite `institution` for a recognized/candidate institution concept with
     matching anchor digest or mediator evidence; store `concept_id` and
     `0.5*legitimacy_belief + 0.5*social_expectation` as strength;
   - cite `organization` for an `orgc-` concept whose procedure/role/record
     matches the case; store `organization_id`;
   - cite `collective_decision` for a decision record involving the dispute
     subject; store the decision id;
   - cite `procedure` or `written_record` for a matching repository/record
     anchor;
   - when a mediator is named, call the existing
     `appraise_mediation_authority(owner_id, mediator_id, context_key, ...)` and
     store each available component as an authority reference with its channel,
     strength, uncertainty, provenance, and `dissenting`. Skip the call when
     `mediator_id == owner_id` (the existing function rejects self-appraisal)
     and store a `self` authority reference instead.
   No authority reference grants permission or enforcement.
5. Add `link_mediation_references(ledger, *, mediation, owner_id, tick,
   policy=None)`:
   - match the owner's mediation cases by `case_ref` when already linked, else
     by `subject_token` and overlapping party ids;
   - create `DisputeMediationReference` with `mediation_case_ref`,
     `recommendation_ref`, `response_ref`, `outcome_ref`, and `link_status`
     (`linked`, `stale`, `orphaned`, `disputed`);
   - if a mediation recommendation exists, create a `DisputeResolution` with
     `source=mediator`, `proposer_id=recommendation.originator_id`,
     `resolution_ref=dispute_resolution_ref(case_ref, proposer_id,
     terms_digest)`, and terms copied as beliefs (not authoritative);
   - never overwrite the mediation ledger.
6. Add `derive_case_status(case, claims, resolutions, responses, tick)`:
   - no claims and no mediation link → `abandoned`;
   - no claims but a mediation link exists → `evidence_gathering`;
   - only active claims, no resolution → `open` or `contested` when an opposing
     counterclaim exists;
   - a proposed resolution → `resolution_proposed`;
   - any active reject/counter → `contested`;
   - all named parties active accept on the latest resolution →
     `apparently_resolved`;
   - a new active claim after `apparently_resolved` → `reopened`;
   - expired tick → `expired`;
   - explicit withdraw of all claims → `withdrawn`.
   No status is `resolved` without the `apparently_` hedge.
7. Add `dispute_direction_preference(ledger, *, owner_id, tick)` and
   `dispute_response_penalties(ledger, ...)` for deliberation: a bounded bonus
   for speaking to a counterparty about an open claim and a bounded penalty for
   accepting an unknown resolution. These bias existing planning candidates; they
   never construct or select a command by themselves.
8. Add `dispute_case_summary(case, claims, resolutions)` for deterministic
   analysis handoff, with counts only.

### Required Interfaces and Contracts

```python
def derive_rule_references(ledger: DisputeLedger, *, formal_rules: object | None, owner_id: str, policy: DisputePolicy | None = None) -> DisputeLedger: ...
def derive_authority_references(ledger: DisputeLedger, *, owner_id: str, offices: object | None, institution_concepts: object | None, organization_concepts: object | None, collective_decisions: object | None, mediation: object | None, tick: int, policy: DisputePolicy | None = None) -> DisputeLedger: ...
def link_mediation_references(ledger: DisputeLedger, *, mediation: object | None, owner_id: str, tick: int, policy: DisputePolicy | None = None) -> DisputeLedger: ...
def derive_case_status(case: DisputeCase, claims: Sequence[DisputeClaim], resolutions: Sequence[DisputeResolution], responses: Sequence[DisputeResolutionResponse], tick: int) -> DisputeStatus: ...
```

Compatibility invariants:

- Rule references are owner-local and versioned.
- Authority references are existing owner beliefs; no new role or office type.
- Mediation links never copy a mediation recommendation into a binding rule.
- A missing rule is `orphaned`, not an error that drops the claim.

### Requirement Evidence

- Original Request "rule references", "mediation", "Integrate with existing
  mediation and institutional roles".
- `src/agents/cognition/formal_rules.py` 356-404, 939-967, 1199-1204,
  1289-1395: exact version lookup.
- `src/agents/cognition/mediation.py` 247-260, 3068: authority channels and
  self-mediator rejection.
- `src/agents/cognition/offices.py` `OfficeFunction.CONFLICT_MEDIATION`.
- `src/agents/cognition/institution_concepts.py` `InstitutionPatternChannel`.
- `src/agents/cognition/organization_concepts.py` roles/procedures/records.

### Error Handling and Logging

- Missing formal-rule ledger: all rule references `orphaned`; no error.
- Unknown mediation case: `link_status=orphaned`; no error.
- Invalid authority reference: notice `dispute_unknown_reference`.
- DEBUG counts only: `dispute_reasoning rules=%s authorities=%s mediation=%s`.
- Never log rule ids, office ids, mediator ids, or claim content.

### Tests

`tests/unit/test_dispute_reasoning.py`:

- `test_rule_reference_resolves_against_owner_formal_rules`
- `test_rule_version_lookup_requires_exact_contiguous_version`
- `test_self_mediator_uses_self_authority_without_calling_appraisal`
- `test_missing_rule_is_orphaned_and_claim_survives`
- `test_version_mismatch_is_not_silently_upgraded`
- `test_office_institution_and_organization_authority_refs_are_beliefs`
- `test_mediation_recommendation_becomes_dispute_resolution_belief`
- `test_competing_claims_are_not_reconciled`
- `test_case_status_never_reports_unhedged_resolution`
- `test_deliberation_hooks_do_not_construct_commands`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_reasoning.py -q`.

### Acceptance Criteria

- Rule references resolve only against the owner's formal rules.
- Authority references cite existing institutional-role beliefs.
- Mediation links never become binding outcomes.
- Competing claims coexist with no precedence.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_reasoning.py -q`
- Expected result: all tests pass.

## Task 8: Propose and respond to resolutions

### Intent

Support proposed resolutions and per-party accepted/rejected declarations
without creating a binding settlement, forced transfer, or objective justice
oracle.

### Implementation Steps

1. Add `propose_dispute_resolution(ledger, *, owner_id, case_ref, proposer_id,
   source, terms, tick, expires_tick=None, policy=None) -> DisputeLedger`:
   - require an existing active case;
   - require `proposer_id` to be the owner or a party/mediator already present in
     the owner's case-visible evidence;
   - validate at most `max_terms_per_resolution` terms;
   - compute `terms_digest` from canonical JSON over sorted terms and
     `resolution_ref = dispute_resolution_ref(case_ref, proposer_id,
     terms_digest)`;
   - mint `drs-` with `status=proposed`;
   - supersede the previous active resolution only when the new one is proposed
     by the same proposer and the old one is still `proposed`.
2. Add `record_dispute_resolution_response(ledger, *, owner_id, resolution_ref,
   party_id, kind, tick, terms_digest, policy=None) -> DisputeLedger`:
   - require `party_id` to be the owner for a direct declaration;
   - for a delivered frame, the verified speaker is the party; never trust a
     frame-supplied party;
   - require `terms_digest` to equal the resolution's digest; a mismatch creates
     `dispute_terms_mismatch` and no response;
   - require a resolution proposed by another party to have been observed in a
     **prior committed tick**; a same-tick cross-owner proposal is not visible to
     the receiver's prepared ledger, so record
     `dispute_resolution_requires_prior_tick` and no response. A party may still
     record its own acceptance of its own proposal in the same tick;
   - `accept`, `reject`, `counterpropose`, `defer`, and `withdraw` are the only
     kinds;
   - a later response from the same party deactivates the earlier one; a
     `withdraw` from a non-proposer deactivates that party's earlier response,
     while a `withdraw` from the proposer withdraws the resolution;
   - `counterpropose` requires a linked new resolution reference.
3. Compute `resolution_status`:
   - any active `withdraw` from the proposer → `withdrawn`;
   - expired tick → `expired`;
   - any active `reject` or `counterpropose` → `contested`;
   - active `accept` from every named party and no active reject → 
     `apparently_accepted`;
   - at least one accept but not all → `partially_accepted`;
   - otherwise `proposed`.
   `apparently_accepted` is an owner belief that every named party declared
   acceptance; it is not binding.
4. Add `expire_dispute_resolutions(ledger, tick, policy=None)` and
   `supersede_dispute_resolutions(ledger, ...)`.
5. Add `compile_dispute_undertaking(ledger, *, owner_id, tick, identity,
   inventory, mediation) -> tuple[DisputeResolution, AgentCommand] | None`:
   - select the first active `apparently_accepted` resolution whose terms contain
     exactly one `transfer_item` or `return_item` term with `party_id` equal to
     the owner and `counterparty_id` equal to the recipient;
   - require a linked mediation recommendation whose `action_token` is `give`
     and whose item/target match the term exactly;
   - delegate to `compile_mediation_undertaking(...)`;
   - return `None` for any unsupported, ambiguous, or non-exact term;
   - never construct a command directly and never substitute a different item,
     target, `Feed`, `Transport`, or other command.
6. `record_dispute_undertaking` may record that an exactly matching final `Give`
   was selected, but only as a belief; a wrong recipient/item is not an
   undertaking.
7. No resolution term can force a transfer, change health, move an item, alter a
   relationship, or enqueue a command.

### Required Interfaces and Contracts

```python
def propose_dispute_resolution(
    ledger: DisputeLedger,
    *,
    owner_id: str,
    case_ref: str,
    proposer_id: str,
    source: str,
    terms: Sequence[DisputeResolutionTerm],
    tick: int,
    expires_tick: int | None = None,
    policy: DisputePolicy | None = None,
) -> DisputeLedger: ...

def record_dispute_resolution_response(
    ledger: DisputeLedger,
    *,
    owner_id: str,
    resolution_ref: str,
    party_id: str,
    kind: str,
    tick: int,
    terms_digest: str,
    policy: DisputePolicy | None = None,
) -> DisputeLedger: ...

def compile_dispute_undertaking(
    ledger: DisputeLedger,
    *,
    owner_id: str,
    tick: int,
    identity: object,
    inventory: object,
    mediation: object,
) -> tuple[DisputeResolution, object] | None: ...
```

Compatibility invariants:

- `apparently_accepted` is the strongest positive status; no `resolved`,
  `decided`, `binding`, or `enforced` status exists.
- A party's response is attributed to that party; a speaker cannot accept for
  another party.
- `terms_digest` binds the response to the exact terms the party saw.
- The only undertaking path is `compile_mediation_undertaking`.

### Requirement Evidence

- Original Request "proposed resolution" and "accepted/rejected resolution".
- `src/agents/cognition/mediation.py` 158-220, 1373-1398.
- `src/agents/cognition/mediation_actions.py` 34, 75-125.
- `.ai-factory/ARCHITECTURE.md` "Important V3 seams" V3-32: "No court, verdict,
  binding settlement, forced transfer, or global dispute registry exists."

### Error Handling and Logging

- Unknown resolution/case: `DisputeError("dispute_unknown_reference")`.
- Terms mismatch: notice `dispute_terms_mismatch`; no response.
- Forged party: notice `dispute_party_mismatch`; no response.
- Unsupported undertaking: return `None`; DEBUG
  `dispute_undertaking_skipped reason=unsupported_terms`.
- Never log terms, item tokens, party ids, or command details.

### Tests

`tests/unit/test_dispute_resolutions.py`:

- `test_proposed_resolution_is_not_binding`
- `test_one_accept_is_partially_accepted`
- `test_all_party_accepts_is_apparently_accepted`
- `test_reject_or_counterpropose_makes_resolution_contested`
- `test_terms_digest_mismatch_is_rejected`
- `test_speaker_cannot_accept_for_another_party`
- `test_expiry_and_supersession`
- `test_same_tick_acceptance_requires_prior_tick`
- `test_undertaking_delegates_to_mediation_and_rejects_unsupported_terms`
- `test_no_command_is_constructed_without_mediation`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_resolutions.py -q`.

### Acceptance Criteria

- Resolutions remain proposals; acceptance/rejection is per party.
- `apparently_accepted` requires every named party and binds nobody.
- No command is constructed directly; the mediation delegation is exact.
- No forced transfer or sanction exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_resolutions.py -q`
- Expected result: all tests pass.

## Task 9: Carry the ledger through cognition and runtime

### Intent

Make the dispute ledger an owner-scoped subjective sidecar carried through
perspective, loop proposals/results, checkpoints, and the runner result, with a
disabled passthrough and no world authority.

### Implementation Steps

1. Add `disputes: object | None = None` to `SubjectiveSnapshot`,
   `CognitiveLoopProposal`, and `CognitiveLoopResult` in
   `src/agents/cognition/models.py`. Validate owner via
   `require_owner_disputes` in `SubjectiveSnapshot.__post_init__`.
2. Add `disputes: object | None = None` to `Perspective` in
   `src/agents/cognition/contracts.py` and to `build_perspective(...)` in
   `src/simulation/perception.py`; forward it unchanged.
3. In `CognitiveLoop`:
   - add `_prepared_disputes` and its fork-state field;
   - add `_prepare_disputes(loop_input, memory)` that returns `None` when
     `dispute_mode` is not `DETERMINISTIC`, otherwise calls
     `apply_dispute_update` with the carried ledger, the same-owner prepared
     ledgers, and `retrieved_memory_context=memory`; `_memory_evidence_refs`
     extracts only stable trace/reconstruction ids and returns empty when memory
     is absent;
   - call it in the main loop next to `_prepare_formal_rules`;
   - return `disputes` on `CognitiveLoopResult` and copy it from the proposal;
   - after final command selection and before `CognitiveLoopResult(...)` is
     constructed (the same location as `record_mediation_attempt` around
     `src/agents/cognition/loop.py:5221-5274`), call
     `record_dispute_utterance` for an owner-selected `dsp_v1` command and store
     the updated ledger in the result;
   - capture/restore `prepared_disputes` in `CognitiveLoopForkState`.
4. In `AgentRuntime`:
   - add `_disputes`;
   - add `_commit_disputes(ledger, tick)` that accepts only deterministic mode
     and the correct owner, and clears the slot when disabled;
   - pass `disputes=self._disputes` into the resolved perspective/result path;
   - apply the result, restore/export it in checkpoints, and enforce owner
     identity.
5. In `AgentRuntimeCheckpoint`, add `disputes: object | None = None` and owner
   validation via `require_owner_disputes`.
6. In `SimulationRunner`, add `export_dispute_ledgers() -> tuple[object, ...]`
   returning owner-ordered ledgers, and add `dispute_ledgers` to
   `SimulationRunnerResult` with ordered-sequence validation.
7. Export the public contracts from package facades:
   - `agents.cognition.__init__`: ledger, policy, frame codec, update, reference,
     resolution, and deliberation helpers (mirror the formal-rule export block);
   - `simulation.__init__`: snapshot models/codec/paging/ports and the dispute
     ledger re-export needed by callers;
   - `experiments.__init__` and `persistence.__init__` are added in Tasks 16/17.
8. Keep `dispute_ledgers` as `tuple[object, ...]` only if the shared result
   contract requires it. Tests that read ledger fields must narrow with
   `isinstance(ledger, DisputeLedger)` or a typed `cast`; do not read
   `ledger.owner_id` from `object` (the 2026-11-01 patch records the resulting
   `mypy [attr-defined]` failures). Add a facade-export test.
9. Add deliberation integration:
   - `dispute_direction_preference` returns a bounded directional hint for an
     open claim;
   - `dispute_response_penalties` returns bounded penalties for accepting an
     unknown or expired resolution;
   - neither helper constructs, submits, or resolves a command.
10. Disabled mode must clear the ledger and leave every existing field and
    fingerprint unchanged.

### Required Interfaces and Contracts

```python
class CognitiveLoopResult:
    ...
    disputes: object | None = None

class AgentRuntimeCheckpoint:
    ...
    disputes: object | None = None

class SimulationRunnerResult:
    ...
    dispute_ledgers: tuple[object, ...] = ()

def export_dispute_ledgers(self) -> tuple[object, ...]: ...
```

Compatibility invariants:

- The dispute ledger never enters `Observation`, `WorldState`, an event, an
  observer frame, an LLM prompt, or a memory write.
- Checkpoint restoration rejects an owner mismatch.
- The runner result keeps ledgers in deterministic owner order.
- Disabled mode yields `None` everywhere.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" and
  "Subjective checkpoints ... stay outside the objective event fold."
- `src/agents/cognition/models.py` 745, 1048-1053, 3945, 4270.
- `src/agents/cognition/contracts.py` 177.
- `src/simulation/perception.py` 143, 354.
- `src/simulation/agent_runtime.py` 1368-1389, 2788, 3364-3373, 3485.
- `src/simulation/run_control.py` 617, 791-796.
- `src/agents/cognition/__init__.py` 347-420: public facade export block.
- `src/simulation/runner_models.py` 6377-6695: ordered `tuple[object, ...]`
  result fields and the narrowing requirement.
- `.ai-factory/patches/2026-11-01-23.13.md`: mypy `attr-defined` prevention for
  shared `object` result fields.

### Error Handling and Logging

- Deterministic mode with a non-`DisputeLedger` value raises `TypeError`.
- Owner mismatch on checkpoint raises `ValueError` with a safe code.
- Disabled mode clears the slot with DEBUG `cognition_dispute_mode disabled`.
- INFO: `dispute_ledger_exported owners=%s`; never log claim content or ids.

### Tests

`tests/unit/test_dispute_runtime.py`:

- `test_disabled_mode_never_allocates_a_ledger`
- `test_deterministic_mode_carries_owner_ledger`
- `test_checkpoint_round_trip_preserves_disputes`
- `test_checkpoint_rejects_wrong_owner`
- `test_runner_exports_owner_ordered_ledgers`
- `test_worker_cannot_write_another_owner_ledger`
- `test_public_facades_export_dispute_contracts`
- `test_runner_result_ledgers_are_narrowed_before_field_access`

`tests/unit/test_dispute_deliberation.py`:

- `test_open_claim_produces_bounded_direction_hint`
- `test_accepting_unknown_resolution_is_penalized`
- `test_hooks_do_not_construct_commands`
- `test_hooks_do_not_change_world_state`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_runtime.py tests/unit/test_dispute_deliberation.py -q`.

### Acceptance Criteria

- The ledger reaches `Perspective`, loop result, checkpoint, and runner result.
- Disabled mode changes nothing.
- No world, event, observer, prompt, or memory path reads the ledger.
- Checkpoint owner isolation is enforced.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_runtime.py tests/unit/test_dispute_deliberation.py -q`
- Expected result: all tests pass.

## Phase Risks and Mitigations

- Risk: The ledger becomes a shared case file.
  Mitigation: Task 4 owner/reference checks and Task 20 cross-owner scan.
- Risk: Observation silently creates disputes.
  Mitigation: Task 6 explicit test that observation alone creates no claim.
- Risk: Rule references become objective law.
  Mitigation: Task 7 orphan/version tests and Task 20 no-world-read scan.
- Risk: Resolution acceptance becomes binding.
  Mitigation: Task 8 `apparently_accepted` semantics and Task 20/21 physical-effect
  tests.
- Risk: A second command compiler appears.
  Mitigation: Task 8 delegation to `compile_mediation_undertaking` and Task 20
  command-construction scan.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
