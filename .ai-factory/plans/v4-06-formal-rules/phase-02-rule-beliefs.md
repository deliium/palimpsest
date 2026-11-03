# Phase 2: Owner-Scoped Formal-Rule Beliefs

Plan: [index.md](index.md)
Tasks: 4-8
Depends on: Phase 1 / Task 3

## Objective

Implement the owner-scoped `FormalRuleLedger`: bounded records, systems, versions,
positions, responses, exceptions, sanctions, evidence, and `fr_v1` speech. The
ledger must derive the progression from existing norms, conventions, durable
records, offices, institution concepts, organization concepts, and collective
decisions without reading world authority or creating commands.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/social_norms.py` | `NormResponse` 115-125; `NormSanction`; `NormLedger` 608; `apply_norm_update` 1303; `_record_sanction`/`_enforce` | Norm stage, response, and sanction precedent. |
| `src/agents/cognition/social_conventions.py` | `ConventionBelief` 401; `ConventionLedger` 553; `apply_convention_update` 1680 | Habit/situation evidence and competing variants. |
| `src/agents/cognition/institution_concepts.py` | six channels 148-167; recognition freeze 1327-1351; update 1388 | Recognition thresholds and channel evidence. |
| `src/agents/cognition/offices.py` | duty/authority/occupant records 455-778; recognition 1143-1195; update 2477 | Recognized authority and revision/succession pattern. |
| `src/agents/cognition/organization_concepts.py` | procedures 847; records 889; commitments 925; ledger 1483; update 2880 | Organization procedure/authority input and sidecar-safe reading. |
| `src/agents/cognition/organization_agency_communication.py` | frame 54-57; acts 60-88; encode/parse 278-398; injection 487 | Exact bounded-speech pattern to mirror. |
| `src/world/artifacts.py` | `ArtifactKind` 78; `DurableRecordGenre` 97; `RecordIntegrity` 110; `InformationArtifact` 315 | Written representation anchors and integrity. |
| `src/world/repositories.py` | `KnowledgeRepository` 149 | Optional repository anchor. |
| `src/world/observations.py` | `ObservedArtifact` 673; `ObservedRepository` 775 | Owner-visible written evidence only. |
| `src/agents/cognition/artifacts.py` | ledger 193; update 330 | Existing owner-scoped reading of artifact revisions. |
| `src/agents/cognition/loop.py` | prepare order 4412-4520; organization prepare 2316-2500 | Where the new prepare stage belongs. |
| `src/agents/cognition/deliberation.py` | penalties 444-480; organization speech 1262-1297 | Where penalties and speech injection belong. |
| `src/simulation/perception.py` | `build_perspective` fields 120-155, 330-375 | Perspective carry. |
| `src/simulation/runner_models.py` | result 6374-6376; ordered validation 6646-6677 | Result and ledger ordering contract. |
| `src/simulation/runner.py` | export methods 5363-5405; result wiring 4993-4997 | Export pattern. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/formal_rules.py` | modify | Records, ledger, update, stage/version pipeline, positions/responses. |
| `src/agents/cognition/formal_rule_communication.py` | create | `fr_v1` frame codec and injection. |
| `src/agents/cognition/__init__.py` | modify | Export the ledger, update, policy, response, and speech helpers. |
| `src/agents/cognition/models.py` | modify | Snapshot/proposal/result carry and owner validation. |
| `src/agents/cognition/loop.py` | modify | Prepare stage, ordering, and result carry. |
| `src/agents/cognition/deliberation.py` | modify | Response penalties, direction preference, and `fr_v1` speech. |
| `src/agents/cognition/fork_state.py` | modify | Fork/copy the ledger. |
| `src/simulation/perception.py` | modify | `build_perspective` parameter and `Perspective` field. |
| `src/simulation/agent_runtime.py` | modify | `__slots__`, commit, deferred finalization, checkpoint export/restore, owner validation. |
| `src/simulation/run_control.py` | modify | `AgentRuntimeCheckpoint.formal_rules` field and owner validation. |
| `src/simulation/runner_models.py` | modify | Result field and ordered validation; checkpoint fields. |
| `src/simulation/runner.py` | modify | Export method, result wiring, and checkpoint owner validation. |
| `tests/unit/test_formal_rule_records.py` | create | Record/ledger invariants. |
| `tests/unit/test_formal_rule_communication.py` | create | Frame codec and receiver independence. |
| `tests/unit/test_formal_rule_stages.py` | create | Progression, versions, recognition. |
| `tests/unit/test_formal_rule_responses.py` | create | Responses, sanctions, exceptions, competing systems. |
| `tests/unit/test_formal_rule_runtime.py` | create | Carry, checkpoint, disabled mode. |
| `tests/unit/test_formal_rule_deliberation.py` | create | Penalties and speech injection. |

## Task 4: Define formal-rule records, systems, versions, and ledger invariants

### Intent

Give every later stage one frozen set of types and one ledger with strict
invariants. If a record is ambiguous here, the update and analysis layers will
invent incompatible shapes.

### Implementation Steps

1. Add to `src/agents/cognition/formal_rules.py` the frozen dataclasses:
   - `FormalRuleScope(kind, anchor_ids, digest)`
   - `FormalRuleWrittenRepresentation(artifact_id, artifact_revision, genre,
     repository_id, status, tick)`
   - `FormalRuleSanctionExpectation(kind, severity, source, enforcement_ref)`
   - `FormalRuleException(exception_id, rule_id, condition_digest, reason,
     scope, evidence_ref, tick)`
   - `FormalRuleEvidence(evidence_id, rule_id, channel, provenance, tick,
     source_actor, artifact_id, artifact_revision, claim_ref, lineage_ref)`
   - `FormalRuleProponent(position_id, rule_id, actor_id, stance, provenance,
     tick, ordinal)`
   - `FormalRuleVersion(version_id, rule_id, version_number, stage, constraint,
     authority, recognition, scope, written, sanction_kinds, exception_ids,
     tick, revision_kind, supersedes_version_id, provenance)`
   - `FormalRule(rule_id, system_id, owner_id, stage, constraint, action_token,
     scope, authority, recognition, status, strength, proponents, versions,
     evidence, sanctions, exceptions, responses, first_tick, last_tick,
     notices)`
   - `FormalRuleSystem(system_id, owner_id, scope, authority, proponent_ids,
     rule_ids, status, competing_system_ids, first_tick, last_tick)`
   - `FormalRuleResponse(response_id, rule_id, actor_id, kind, tick, provenance,
     claim_ref)`
   - `FormalRuleLedger(owner_id, systems, rules, notices, policy_version)`
2. Add `FormalRuleRevisionKind`: `initial`, `stage_promotion`, `scope_change`,
   `authority_change`, `written_change`, `sanction_change`,
   `exception_change`, `recognition_change`, `retirement`.
3. Add `FormalRuleExceptionReason`: `exempt_actor`, `exempt_place`,
   `emergency`, `role_duty`, `prior_obligation`, `unknown`.
4. Quantize `FormalRuleSanctionExpectation.severity` to six decimals and require
   `0.0 <= severity <= 1.0`.
5. Implement `empty_formal_rule_ledger(owner_id, policy=None)` and
   `require_owner_formal_rules(value, owner_id, *, field_name)`.
6. Enforce ledger invariants in `FormalRuleLedger.__post_init__`:
   - policy version is exactly `formal-rules.v1`;
   - owner ids match across systems/rules;
   - systems and rules are sorted by id and unique;
   - every `rule.system_id` exists; every `system.rule_ids` exists and matches;
   - competing system ids are symmetric, sorted, and exist;
   - version numbers are contiguous `1..N`, sorted, and `supersedes` points to
     the previous version or `None`;
   - evidence/position/response/exception caps hold per rule;
   - total records are `<= policy.max_total_records`;
   - no rule has a physical constraint (the enum cannot express one);
   - no forbidden field name appears in any mapping or `__dataclass_fields__`.
7. Add `formal_rule_ledger_digest(ledger)` using canonical JSON with sorted keys
   and six-decimal floats.
8. Add a bounded `FormalRuleNotice` code set:
   `cap_exceeded`, `ignored_kind`, `unresolved_scope`, `no_candidate`,
   `orphaned_rule_system`, `formal_rule_version_out_of_order`,
   `formal_rule_truncated`, `representation_damaged`, `representation_missing`,
   `unrecognized_authority`, `contested_system`, `expired`.
9. Do not add a `truth`, `valid`, `binding`, `enforced`, or `objective` field.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class FormalRuleLedger:
    owner_id: AgentId
    systems: tuple[FormalRuleSystem, ...]
    rules: tuple[FormalRule, ...]
    notices: tuple[str, ...]
    policy_version: str

def empty_formal_rule_ledger(owner_id: AgentId, policy: FormalRulePolicy | None = None) -> FormalRuleLedger: ...
def require_owner_formal_rules(value: object | None, owner_id: AgentId, *, field_name: str) -> FormalRuleLedger | None: ...
```

Compatibility invariants:

- `None` means the mode is disabled; an empty ledger means enabled with no
  evidence.
- A foreign-owner ledger raises `formal_rule_owner_mismatch`.
- A malformed ledger raises `formal_rule_invalid_ledger`.
- `FormalRuleResponse` exists per rule and is bounded; it is not an objective
  compliance table.

### Requirement Evidence

- Original Request fields: scope, proponents, authority, written representation,
  expected sanction, exceptions, historical versions.
- `organization_concepts.py` 1483-1600 and `organization_agency.py` 1523-1600:
  frozen ledger/cap/digest pattern.
- `offices.py` 455-778: provenance-aware evidence and revision records.
- `world/artifacts.py` 78-110, 315: written anchors and integrity.

### Error Handling and Logging

- Invalid record types raise `TypeError` with the field name.
- Invariant violations raise `FormalRuleError("formal_rule_invalid_ledger")`.
- Owner mismatch raises `FormalRuleError("formal_rule_owner_mismatch")`.
- Cap overflow is resolved by the update, not by silently dropping here.
- DEBUG: `formal_rule_ledger_validated systems=%s rules=%s` (counts only).
- Never log rule ids, scope digests, action tokens, or actor ids.

### Tests

`tests/unit/test_formal_rule_records.py`:

- `test_ledger_requires_one_owner_and_rejects_foreign_ledgers`
- `test_system_rule_and_version_references_are_closed`
- `test_competing_system_links_are_symmetric`
- `test_version_numbers_are_contiguous_and_supersede_the_previous_version`
- `test_caps_and_total_record_limit_are_enforced`
- `test_no_physical_truth_binding_or_enforced_fields_exist`
- `test_ledger_digest_is_stable_and_float_quantized`

Run: `uv run pytest tests/unit/test_formal_rule_records.py -q`.

### Acceptance Criteria

- The ledger can represent every requested dimension without an objective-law
  field.
- Two ledgers with the same content produce the same digest.
- A foreign-owner ledger is rejected on construction and on snapshot carry.

### Verification

- `uv run pytest tests/unit/test_formal_rule_records.py -q`
- `uv run mypy src/agents/cognition/formal_rules.py`

## Task 5: Add bounded `fr_v1` formal-rule speech frames

### Intent

Let owners assert, support, oppose, challenge, reinterpret, amend, withdraw,
recognize, and report rules through existing `Talk`/`Tell` without a new command
or free-text payload.

### Implementation Steps

1. Create `src/agents/cognition/formal_rule_communication.py`.
2. Define:
   - `FORMAL_RULE_COMMUNICATION_POLICY_VERSION = "formal-rule-communication.v1"`
   - `FORMAL_RULE_FRAME_SUBJECT = "fr_v1"`
   - predicate map:
     `fr_assert`, `fr_support`, `fr_oppose`, `fr_challenge`, `fr_reinterpret`,
     `fr_amend`, `fr_withdraw`, `fr_recognize`, `fr_report`.
3. Define `FormalRuleClaim` with bounded fields:
   `system_ref`, `rule_ref`, `version_number`, `stage`, `constraint_kind`,
   `action_token`, `scope_digest`, `authority_kind`, `written_artifact_ref`,
   `sanction_kind`, `stance`, `report_kind`, `revision`, `ordinal`.
   Use `none` sentinels for absent refs/enums.
4. Encode as a strict colon-delimited frame with exact arity per act. Reject
   whitespace, newlines, unknown acts, bad ids, out-of-range version/revision,
   and frames longer than `FormalRulePolicy.max_frame_chars` with
   `formal_rule_frame_invalid`.
5. `parse_formal_rule_claim_relation(subject, predicate, object)` returns
   `FormalRuleClaim | None`; unrelated subjects/predicates return `None`, and a
   malformed `fr_v1` relation raises the safe code.
6. `formal_rule_communicate_utterance(talk_or_tell, claim)` stamps at most one
   `fr_v1` relation, preserves command type/recipient/other relations, skips if
   already present or the relation cap is reached, and accepts only `Talk`/`Tell`.
7. Do not accept free-form text, labels, artifact content, or peer ids beyond the
   bounded refs.
8. Receiver behavior: a delivered claim becomes owner-local evidence or a
   position in Task 6; it never copies the sender's rule, ledger, status, or
   recognition.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class FormalRuleClaim:
    act: str
    system_ref: str
    rule_ref: str
    version_number: int
    stage: str
    constraint_kind: str
    action_token: str
    scope_digest: str
    authority_kind: str
    written_artifact_ref: str
    sanction_kind: str
    stance: str
    report_kind: str
    revision: int
    ordinal: int

def encode_formal_rule_claim(claim: FormalRuleClaim) -> str: ...
def parse_formal_rule_claim(frame: str) -> FormalRuleClaim: ...
def formal_rule_claim_relation(claim: FormalRuleClaim) -> tuple[str, str, str]: ...
def parse_formal_rule_claim_relation(subject: str, predicate: str, object: str) -> FormalRuleClaim | None: ...
def formal_rule_communicate_utterance(command: object, claim: FormalRuleClaim) -> object: ...
```

Compatibility invariants:

- `org_v1`, `org_op_v1`, `org_ca_v1`, and `collective_decision` frames are
  unchanged.
- At most one `fr_v1` relation per command.
- Frame length and relation count stay within policy.
- No command is created, replaced, or re-targeted.

### Requirement Evidence

- Original Request "Agents may: follow / violate / challenge / reinterpret /
  ignore" and "Allow competing rule systems".
- `organization_agency_communication.py` 54-57, 60-128, 278-398, 487.
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts".

### Error Handling and Logging

- Malformed frames raise `FormalRuleError("formal_rule_frame_invalid")`.
- Unsupported command type raises `formal_rule_frame_unsupported_command`.
- Relation cap reached is a silent skip plus DEBUG `formal_rule_frame_skipped
  reason=relation_cap`.
- DEBUG: `formal_rule_frame_encoded act=%s` (act only).
- Never log frame bodies, refs, or actor ids.

### Tests

`tests/unit/test_formal_rule_communication.py`:

- `test_every_act_round_trips_with_exact_arity`
- `test_malformed_and_overlong_frames_are_rejected`
- `test_relational_parser_ignores_unrelated_frames`
- `test_only_talk_and_tell_accept_a_claim`
- `test_existing_relations_and_command_type_are_preserved`
- `test_receiver_forms_independent_evidence_without_copying`
- `test_organization_agency_and_collective_decision_frames_are_unchanged`

Run: `uv run pytest tests/unit/test_formal_rule_communication.py -q`.

### Acceptance Criteria

- Every requested act is expressible.
- No new command/event/observer semantic is introduced.
- A malformed or overlong claim never reaches the ledger.

### Verification

- `uv run pytest tests/unit/test_formal_rule_communication.py -q`
- `uv run ruff check src/agents/cognition/formal_rule_communication.py`

## Task 6: Collect evidence and materialize stages, systems, and versions

### Intent

Turn owner-visible norms, conventions, durable records, authorities, and
delivered claims into monotone rule stages and bounded historical versions.

### Implementation Steps

1. Add `FORMAL_RULE_ACTION_TOKENS` as a closed frozenset of existing action
   tokens: `give`, `take`, `attack`, `move`, `sleep`, `inscribe`, `amend`,
   `erase`, `maintain`, `produce`, `exchange`, `teach`, `heal`, `feed`,
   `transport`, `wait`, `communicate`, `tell`, `ask`, `share`, `withhold`,
   `enter`, `leave`, `unspecified`.
2. Add a total mapping from `NormExpectation` and `NormPattern` to those tokens,
   and from convention content/action strings where a closed match exists. No
   free-text inference.
3. Implement:

```python
def apply_formal_rule_update(
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    prior: FormalRuleLedger | None,
    *,
    social_norms: object | None = None,
    social_conventions: object | None = None,
    institution_concepts: object | None = None,
    office_concepts: object | None = None,
    organization_concepts: object | None = None,
    collective_decisions: object | None = None,
    artifact_interpretations: object | None = None,
    policy: FormalRulePolicy | None = None,
) -> FormalRuleLedger: ...
```

4. Reject `WorldState`, `WorldEvent`, `PhysicalRules`, `MetricDocument`, a
   foreign-owner prior ledger, and any prior ledger whose `policy_version`
   differs.
5. `_collect_observation`: read only `observation.artifacts` and
   `observation.repositories`. Accept durable-capable artifacts with a
   `record_genre`; record `artifact_id`, `artifact_revision`, genre, optional
   `custodian_repository_id`, and integrity. Derive `representation_status`:
   `intact`, `damaged`, `missing` (referenced but not observed), or `unknown`.
   Do not parse or store artifact content.
6. `_collect_norms`: for each active norm belief, derive an expectation candidate:
   action token, scope anchors from the norm context, sanction kinds from
   `NormSanction`, and provenance `derived_from_norm`.
7. `_collect_conventions`: for each active convention, derive a habit candidate:
   situation-derived scope digest, usual action token, provenance
   `derived_from_convention`.
8. `_collect_authority`: for matching scope/action, read:
   - office beliefs with recognized status and duty/authority kinds;
   - institution concepts with recognized status;
   - organization procedure beliefs with recurrence;
   - collective decisions with recognized outcome.
   Emit authority evidence only; never copy the source record.
9. `_collect_claims`: parse delivered `fr_v1` claims addressed to this owner.
   Claims with a matching `system_ref` become raw `FormalRuleEvidence` and, when
   they carry a proponent/supporter/opponent stance, an initial
   `FormalRuleProponent` **before** stage promotion so the supporter threshold can
   see them. Claims with no matching system append `orphaned_rule_system` and
   mint no rule. Do not append a version or re-appraise a position here; that is
   Task 7's single responsibility.
10. `_promote_stage`: rank stages as
    `habit=0, expectation=1, norm=2, documented=3, recognized_enforcement=4`.
    Promote only upward. Promotion rules:
    - habit: active convention or an observed repeated own action;
    - expectation: a norm candidate or repeated claim;
    - norm: an active norm belief;
    - documented: norm or expectation plus an intact/damaged observed durable
      record whose action token/scope matches;
    - recognized_enforcement: documented plus at least
      `min_enforcement_recurrence` observations and at least
      `min_supporters_for_recognition` distinct proponents, where recognition
      comes from either one recognized authority source (office, institution,
      organization procedure, or collective decision) or that many explicit
      `recognize` claims. A written record alone is `documented`; it becomes
      recognized enforcement only with the additional recognition evidence.
11. `_append_version`: on any change to stage, constraint, scope, authority,
    recognition, written representation, sanction kinds, or exception ids,
    append `FormalRuleVersion` number `N+1`. If a claim carries a version number
    that is not `current+1`, keep the prior version and append
    `formal_rule_version_out_of_order`.
12. `_derive_competing`: after materialization, pair rules with the same
    `scope.digest` and `action_token` but different `constraint` or `authority`.
    Set symmetric `competing_system_ids`; mark both systems `contested` when both
    are active. Do not choose a winner.
13. Age and retire only by explicit evidence: a rule with no supporting evidence
    for `version_window_ticks` becomes `retired` with provenance `expired`; a
    recognized rule never silently demotes.
14. Sort systems/rules/versions/evidence/positions by id; trim to policy caps;
    append `formal_rule_truncated` when trimming.
15. Return a frozen ledger; never mutate the prior ledger.

### Required Interfaces and Contracts

- Stage rank is a total order; no update can lower it.
- A rule id is stable across promotions and versions; a version id changes.
- A system id is stable across its rules; a new authority or scope creates a new
  system.
- The ledger contains no objective artifact content, no world event, and no
  command.
- A missing written record is `missing`, not a false claim of writing.
- A claim cannot create a system unless the owner already has matching evidence
  or a recognized anchor.

### Requirement Evidence

- Original Request progression and fields.
- `social_norms.py` `NormLedger`/`apply_norm_update` 608-751, 1303.
- `social_conventions.py` `ConventionLedger`/`apply_convention_update`
  553-680, 1680.
- `institution_concepts.py` 1327-1470; `offices.py` 1143-1195, 2477.
- `organization_concepts.py` procedure/record/commitment beliefs 847-974.
- `world/artifacts.py` 78-110, 315; `world/_perception.py` observed artifacts.

### Error Handling and Logging

- Wrong owner/prior: `formal_rule_owner_mismatch`.
- Wrong prior version: `formal_rule_policy_mismatch`.
- Forbidden input type: `formal_rule_forbidden_input`.
- Missing scope anchor: notice `unresolved_scope`, no rule.
- Cap overflow: trim and notice `formal_rule_truncated`.
- INFO once per update: `formal_rule_update owner=%s rules=%s systems=%s`
  (owner id is a safe domain id; no content).
- DEBUG: `formal_rule_stage stage=%s count=%s`, `formal_rule_version_appended
  number=%s`.
- WARN on `representation_missing` / `orphaned_rule_system` with counts only.
- Never log scope anchors, action tokens, artifact ids, claim frames, or
  proponent ids.

### Tests

`tests/unit/test_formal_rule_stages.py`:

- `test_convention_only_stays_habit`
- `test_active_norm_reaches_norm_stage`
- `test_intact_durable_record_promotes_to_documented`
- `test_recognized_office_or_decision_promotes_to_recognized_enforcement`
- `test_two_explicit_recognize_claims_promote_a_documented_rule`
- `test_stage_never_regresses_when_evidence_fades`
- `test_missing_or_damaged_record_degrades_representation_not_stage`
- `test_versions_append_only_on_material_change`
- `test_out_of_order_version_keeps_prior_and_notices`
- `test_two_owners_opposite_constraints_form_competing_systems`
- `test_claim_without_matching_system_is_orphaned`
- `test_update_rejects_world_state_events_rules_and_metrics`
- `test_repeated_updates_are_identical`

Run: `uv run pytest tests/unit/test_formal_rule_stages.py -q`.

### Acceptance Criteria

- Every requested stage is reachable from a real owner-visible input.
- Promotion is monotone and versioned.
- Competing systems remain separate and mutually linked.
- No world authority is read and no command is produced.

### Verification

- `uv run pytest tests/unit/test_formal_rule_stages.py -q`
- `uv run mypy src/agents/cognition/formal_rules.py`

## Task 7: Generate positions, responses, sanctions, exceptions, and competing systems

### Intent

Let an owner hold a position on a rule, respond to it this tick, expect a
sanction, record an exception, and keep competing systems without any automatic
enforcement.

### Implementation Steps

1. Add deterministic position generation:
   `generate_formal_rule_position(ledger, *, tick, rule_id, policy)` returns a
   `FormalRuleProponent` for the owner. The owner is `proponent` for a rule it
   derived, and `supporter` for a rule it adopted from a recognized anchor.
2. Add:
   `appraise_formal_rule_position(ledger, *, tick, claim, policy)` which is the
   single appraiser for **newly delivered** claims. It accepts
   support/oppose/challenge/reinterpret/amend/withdraw claims from delivered
   `fr_v1` frames, appends the corresponding position/evidence exactly once, and
   is never called for a claim already materialized by Task 6. Recognition
   thresholds:
   - `oppose`/`challenge` increments contest;
   - `reinterpret` appends a version with `reinterpretation` provenance;
   - `amend` appends a version only when the claim revision is exactly current+1;
   - `withdraw` removes support but never deletes history.
3. Add `select_formal_rule_response(ledger, *, tick, action_token, policy) ->
   FormalRuleResponse | None`. It chooses one of `follow`, `violate`,
   `challenge`, `reinterpret`, `ignore` for the owner's own active rule using a
   deterministic policy:
   - `follow` when the rule is recognized and the action matches;
   - `ignore` when the rule is candidate/unrecognized;
   - `challenge` when the rule is contested and the owner is an opponent;
   - `reinterpret` when a written representation is damaged/missing;
   - `violate` only when the owner is an opponent and the current owner plan
     already contains a matching action token.
   The function returns a response record only, never a command, and never
   decides physical possibility.
4. Add `formal_rule_direction_preference(ledger, *, action_token) -> float` in
   `[-0.25, 0.0]` or `[0.0, 0.25]` for existing plan candidates. It is a weak
   bias, never an obligation.
5. Add `formal_rule_response_penalties(ledger, *, tick)` returning bounded
   penalties keyed by rule id for existing futures; no command construction.
6. Sanctions:
   - derive expected sanction kinds from active norms and claims;
   - store `FormalRuleSanctionExpectation` with severity quantized;
   - never dispatch a sanction, alter a relationship, or reduce trust in this
     module.
7. Exceptions:
   - accept `exempt_actor`, `exempt_place`, `emergency`, `role_duty`,
     `prior_obligation`, `unknown` reasons from claims or observed records;
   - store bounded `frx-` records;
   - an exception never changes the rule constraint or grants world permission.
8. Competing systems:
   - when a rule is contested, keep both systems active and set
     `status=contested` on both;
   - no precedence scan, majority count, or automatic winner.
9. Add `formal_rule_ledger_digest` stability under reordered equal evidence.
10. Update `deliberation.py` to apply the direction preference and penalties to
    existing candidates only, and to stamp an `fr_v1` claim on an existing
    `Talk`/`Tell` when the owner communicates a rule. Do not add a command.

### Required Interfaces and Contracts

```python
def generate_formal_rule_position(ledger: FormalRuleLedger, *, tick: int, rule_id: str, policy: FormalRulePolicy) -> FormalRuleLedger: ...
def appraise_formal_rule_position(ledger: FormalRuleLedger, *, tick: int, claim: FormalRuleClaim, policy: FormalRulePolicy) -> FormalRuleLedger: ...
def select_formal_rule_response(ledger: FormalRuleLedger, *, tick: int, action_token: str, policy: FormalRulePolicy) -> tuple[FormalRuleLedger, FormalRuleResponse | None]: ...
def formal_rule_direction_preference(ledger: FormalRuleLedger, *, action_token: str) -> float: ...
def formal_rule_response_penalties(ledger: FormalRuleLedger, *, tick: int) -> Mapping[str, float]: ...
```

Compatibility invariants:

- Responses are capped per rule and never imply objective compliance.
- A missing observation yields no `violate` response.
- `ignore` is not a sanction, violation, or refusal.
- The response selector accepts only closed action tokens.
- No function returns `AgentCommand`, `ActionRequest`, or `ActionSubmission`.

### Requirement Evidence

- Original Request "Agents may: follow / violate / challenge / reinterpret /
  ignore" and "expected sanction" and "exceptions".
- `social_norms.py` 115-125, `_record_sanction`/`_enforce`.
- `organization_agency.py` implementation-status censoring precedent.
- `.ai-factory/ARCHITECTURE.md` anti-pattern "Treating ... collective outcome ...
  as world-verified authority".

### Error Handling and Logging

- Unknown action token: `formal_rule_action_invalid`.
- Unknown response: `formal_rule_response_invalid`.
- Cap overflow: trim oldest response and notice `cap_exceeded`.
- INFO on response selection: `formal_rule_response kind=%s` (kind only).
- DEBUG on sanction/exception counts.
- WARN when a response is censored because the action was not observed; never
  log the action or owner.
- Never log sanction severity, exception condition, or claim refs.

### Tests

`tests/unit/test_formal_rule_responses.py`:

- `test_each_response_kind_is_reachable_and_bounded`
- `test_unobserved_action_never_yields_violate`
- `test_ignore_is_not_treated_as_violation_or_refusal`
- `test_expected_sanction_is_recorded_without_side_effects`
- `test_exception_never_grants_permission_or_removes_prohibition`
- `test_competing_systems_stay_contested_and_symmetric`
- `test_response_selector_returns_no_command`
- `test_position_thresholds_and_reinterpretation_versions`
- `test_out_of_order_amendment_is_rejected`
- `test_direction_preference_is_bounded`

Run: `uv run pytest tests/unit/test_formal_rule_responses.py -q`.

### Acceptance Criteria

- All five responses exist and are deterministic.
- No response creates, suppresses, or rewrites a command.
- Sanctions and exceptions remain beliefs.
- Competing systems remain separate.

### Verification

- `uv run pytest tests/unit/test_formal_rule_responses.py -q`
- `uv run ruff check src/agents/cognition/formal_rules.py src/agents/cognition/deliberation.py`

## Task 8: Carry the ledger through cognition, runtime, checkpoints, and deliberation

### Intent

Make the owner-scoped ledger survive the cognitive loop, perspective, deferred
finalization, runtime checkpoints, and runner results, exactly like the existing
organization ledgers, and gate everything on the new mode.

### Implementation Steps

1. `src/agents/cognition/models.py`:
   - add `formal_rules: object | None = None` to `SubjectiveSnapshot`,
     `CognitiveLoopProposal`, and `CognitiveLoopResult`;
   - call `require_owner_formal_rules` in `SubjectiveSnapshot.__post_init__`;
   - keep the field absent/`None` when disabled.
2. `src/agents/cognition/loop.py`:
   - import the update, generation, appraisal, response, and policy helpers;
   - add `_prepare_formal_rules(loop_input)` after
     `_prepare_organization_agency` (around 4510) so it can consume the prepared
     organization ledgers;
   - when `formal_rule_mode` is `DISABLED`, return `None` without allocating;
   - call `apply_formal_rule_update` with the owner's prepared norms,
     conventions, institution concepts, offices, organization concepts,
     collective decisions, and artifact interpretations;
   - call `generate_formal_rule_position`, `appraise_formal_rule_position`, and
     `select_formal_rule_response` in deterministic order;
   - carry the ledger into the loop result and proposal.
3. `src/agents/cognition/deliberation.py`:
   - read `formal_rules` from the snapshot;
   - apply `formal_rule_direction_preference` and
     `formal_rule_response_penalties` to existing candidates;
   - inject `fr_v1` claims through `formal_rule_communicate_utterance` on
     existing `Talk`/`Tell`;
   - never add or remove a command kind.
4. `src/agents/cognition/fork_state.py`:
   - add `prepared_formal_rules: object | None = None` to the prepared-state
     record next to `prepared_organization_agency` (line 62);
   - copy the ledger by type/owner, not by mutable reference.
5. `src/simulation/perception.py`: add `formal_rules: object | None = None` to
   `build_perspective` parameters and to `Perspective`; pass it through.
6. `src/simulation/run_control.py`:
   - add `formal_rules: object | None = None` to
     `AgentRuntimeCheckpoint` next to `organization_agency` (line 616);
   - in `__post_init__`, call `require_owner_formal_rules` with the checkpoint
     `agent_id` and `field_name="formal_rules"` (mirror the organization branch
     at 781-788).
7. `src/simulation/agent_runtime.py`:
   - add `_formal_rules` to `AgentRuntime.__slots__` next to
     `_organization_agency` (line 470) and initialize it to `None` (line 622);
   - add `_commit_formal_rules(ledger, tick)` mirroring
     `_commit_organization_agency` (1337-1360), with type and owner checks;
   - commit it from the pending result path (2751-2752) and include it in
     `export_runtime_checkpoint` (3437);
   - restore it in the checkpoint restore block (3317-3320), rejecting a
     foreign-owner ledger.
8. `src/simulation/runner_models.py`:
   - add `formal_rule_ledgers: tuple[object, ...] = ()` to
     `SimulationRunnerResult`;
   - validate ordered sequences and `FormalRuleLedger` items exactly like
     `organization_agency_ledgers`.
9. `src/simulation/runner.py`:
   - add `export_formal_rule_ledgers()` mirroring
     `export_organization_agency_ledgers` (5363-5405);
   - wire it into the result at 4993-4997;
   - extend the checkpoint owner validation block (4727-4762) to read
     `state.formal_rules` and reject a foreign owner.
10. `src/agents/cognition/__init__.py`: export the public ledger, update, policy,
    response, and speech helpers with `__all__`.
11. Keep the mode-off path byte-identical to the pre-change trajectory: no
    ledger allocation, no notices, no extra log lines beyond the existing mode
    log.

### Required Interfaces and Contracts

- `Perspective.formal_rules` and `SubjectiveSnapshot.formal_rules` are
  `object | None`.
- `SimulationRunnerResult.formal_rule_ledgers` is owner-ordered, unique, and
  contains only `FormalRuleLedger`.
- Checkpoints preserve exactly one owner's ledger; admission transfers nothing.
- `build_perspective` never accepts a peer ledger or `WorldState`.
- `CognitionLoopResult` carries the same ledger object identity as the loop
  prepared for that owner.
- No analysis, persistence, API, or observer type enters cognition.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime".
- `src/simulation/perception.py` 120-155, 330-375.
- `src/simulation/runner_models.py` 6374-6376, 6646-6677.
- `src/simulation/run_control.py` 590-637, 781-788.
- `src/simulation/agent_runtime.py` 470, 622, 1337-1360, 2751-2752, 3317-3320,
  3437.
- `src/simulation/runner.py` 4727-4762, 4993-4997, 5363-5405.
- `src/agents/cognition/loop.py` 4412-4520.
- `src/agents/cognition/models.py` 742-744, 1020-1045, 3934-3935.
- `src/agents/cognition/fork_state.py` 62.

### Error Handling and Logging

- Foreign-owner ledger raises `formal_rule_owner_mismatch` at snapshot,
  checkpoint, and result validation.
- Wrong item type raises `TypeError("formal_rule_ledgers: invalid_item")`.
- Unordered input raises `TypeError("formal_rule_ledgers must be ordered")`.
- INFO once per export: `runner_formal_rule_ledger_export ledger_count=%s`.
- DEBUG per prepare: `formal_rule_prepare mode=%s rules=%s`.
- Never log ledger digests, rule ids, scope anchors, or claim refs.

### Tests

`tests/unit/test_formal_rule_runtime.py`:

- `test_disabled_mode_allocates_no_ledger`
- `test_deterministic_mode_prepares_and_carries_one_owner_ledger`
- `test_snapshot_and_checkpoint_reject_foreign_owner`
- `test_runtime_checkpoint_field_round_trips_the_ledger`
- `test_checkpoint_restore_rejects_foreign_owner`
- `test_runner_checkpoint_validation_rejects_foreign_owner`
- `test_perspective_carries_the_ledger`
- `test_runner_result_requires_ordered_unique_ledgers`
- `test_fork_state_copies_without_sharing`
- `test_agent_runtime_slots_include_formal_rules`

`tests/unit/test_formal_rule_deliberation.py`:

- `test_direction_preference_only_biases_existing_candidates`
- `test_response_penalties_do_not_create_commands`
- `test_rule_speech_stamps_existing_talk_and_preserves_other_relations`
- `test_no_formal_rule_command_kind_is_added`

Run: `uv run pytest tests/unit/test_formal_rule_runtime.py tests/unit/test_formal_rule_deliberation.py -q`.

### Acceptance Criteria

- A disabled run has no ledger anywhere.
- An enabled run carries exactly one ledger per owner through every boundary.
- No command/event/observer contract changes.
- Existing organization tests remain green.

### Verification

- `uv run pytest tests/unit/test_formal_rule_runtime.py tests/unit/test_formal_rule_deliberation.py -q`
- `uv run pytest tests/unit/test_organization_agency_runtime.py tests/unit/test_organization_operations_runtime.py -q`
  (adjust to the actual organization runtime test names; keep them green)
- `uv run mypy src/agents/cognition src/simulation`

## Phase Risks and Mitigations

- Risk: stage derivation reads peer ledgers or world authority.
  Mitigation: the update signature accepts only owner-scoped prepared ledgers and
  `Observation`; add a boundary test asserting `WorldState`/`WorldEvent` are
  rejected.
- Risk: a rule response is mistaken for an objective compliance finding.
  Mitigation: name the record `FormalRuleResponse`, document it as a declaration,
  and never derive `violate` from silence or an unobserved act.
- Risk: written representation becomes an objective law reader.
  Mitigation: store only artifact id/revision/genre/status; never store or parse
  artifact content.
- Risk: competing systems are accidentally unioned by detection.
  Mitigation: detection in Task 10 preserves overlapping candidates and Task 6
  links them symmetrically.
- Risk: runtime carry breaks existing organization ledger ordering.
  Mitigation: mirror the existing tuple validation and add the new field last.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
- The disabled path remains byte-identical to pre-change behavior.
- No command, event, write pair, migration, artifact kind, or organization
  contract changed.
