# Phase 1: Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Freeze the dispute vocabulary, kinds, statuses, identity grammar, and limits;
make `legal_disputes` the third owned V4 capability flag on the existing
`runner-config-v56` seam; and add a default-disabled cognition mode and policy
without changing runner config, commands, events, or the mediation/organization
stacks.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `V4ContextId.LEGAL_DISPUTES` 64; spec 136-149; `validate_v4_contexts` 361-411 | The context is already declared as owner-scoped, prerequisite `formal_rules`, event-reusing, with non-goals "no court, verdict, or binding settlement" and "no global dispute registry or forced transfer". |
| `src/simulation/runner_models.py` | `_V4_CAPABILITY_FLAG_NAMES` 305-318; `_V4_OWNED_CAPABILITY_FLAGS` 320-325; `V4CapabilityFlags` 1114-1163; v56 gate 7936-7948 | Ownership is a runtime pin; the flag name and v56 requirement already exist. |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 155-157; v4 capability matrix row 761-780 | Duplicate ownership pin and human-readable compatibility notes. |
| `src/simulation/runner.py` | `_cognition_config_for` 1006-1019; unowned-v4 validation 2169-2238; call sites 2644-2651, 6292-6299, 6665-6672 | The runner derives cognition modes from V4 flags and rejects unowned flags before construction. |
| `src/agents/cognition/configuration.py` | `CognitionFormalRuleMode` 408-420; fields 620-621; normalization 1152-1169; fingerprint 1493-1497 | Pattern for a default-disabled cognition mode and optional locked policy. |
| `src/agents/cognition/formal_rules.py` | policy 356-404; ledger 1289-1395; update 1811-1885 | Vocabulary, policy, id, and owner-scoped update conventions to mirror. |
| `src/agents/cognition/mediation.py` | policy 74; forbidden fields 133; `MediationAct` 158-168; `MediationResponseKind` 169-180; `MediationCaseStatus` 197-220; ledger 1373-1398; authority 3068 | Existing dispute-adjacent vocabulary and resolution semantics. |
| `src/agents/cognition/structured_commitments.py` | statuses, `CommitmentInterpretation`, `apply_structured_commitment_update` | Contested-debt and broken-promise evidence source. |
| `src/agents/cognition/offices.py` | `OfficeFunction.CONFLICT_MEDIATION`, `OfficeAuthorityKind` | Institutional-role authority references; no judge/court. |
| `src/agents/cognition/institution_concepts.py` | `InstitutionPatternChannel`, `InstitutionConceptStatus` | Institutional-role evidence for authority references. |
| `src/world/observations.py` | `ObservationProvenance` 232-281; `ObservedOccurrence` 973-1017; `ObservedCommunication` 1020-1035; `ObservedArtifact` 673-691; `ObservedRepository` 775-792 | Evidence-reference sources; opaque `EventId` correlation is already allowed. |
| `tests/architecture/test_v4_architecture_invariants.py` | ownership test 155-177; allowed flag references 80-89 | Must be updated because three flags are now owned. |
| `tests/unit/test_v4_scaffolding_gate.py` | unowned gate 112-129; owned organizations 132-145 | Mirrors the fail-closed and owned-construction contract. |
| `tests/unit/test_runner_config_v56.py` | exact keys 181-207; unowned parameterization 249-282; owned 285-299 | Must keep the 12-key sibling exact while changing ownership. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/legal_disputes.py` | create | Policy version, enums, id grammar, limits, error class, default policy, subject/party digests. |
| `src/simulation/runner_models.py` | modify | Add `legal_disputes` to `_V4_OWNED_CAPABILITY_FLAGS`. |
| `src/simulation/compatibility.py` | modify | Add `legal_disputes` to `V4_OWNED_CAPABILITY_FLAGS`; update the v4 capability matrix row. |
| `src/agents/cognition/configuration.py` | modify | Add `CognitionDisputeMode`, fields, normalization, fingerprint. |
| `src/simulation/runner.py` | modify | Accept and forward `legal_disputes_enabled`; pass the flag at all three cognition construction sites. |
| `tests/unit/test_dispute_contracts.py` | create | Vocabulary, id, policy, limit, and forbidden-field tests. |
| `tests/unit/test_dispute_config.py` | create | Mode/policy seam and disabled-default tests. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Three owned flags; keep 14 contexts / 12 flags / `v4-context-map-v2`. |
| `tests/unit/test_v4_scaffolding_gate.py` | modify | Remove `legal_disputes` from the unowned parameterization; add owned construction. |
| `tests/unit/test_runner_config_v56.py` | modify | Move `legal_disputes` from the unowned parameterization to the owned construction test. |
| `tests/unit/test_runner_config_v4_flags.py` | modify | Keep the 12-name closed set; assert the three-flag owned split. |
| `tests/unit/test_organization_gate.py` | modify | Ownership split assertion only; no organization behavior change. |
| `tests/unit/test_formal_rule_regression.py` | modify | Ownership split assertion only; Task 13 updates its catalog assertions. |
| `tests/architecture/test_organization_boundaries.py` | modify | Ownership split assertion only; no organization behavior change. |
| `tests/architecture/test_formal_rule_boundaries.py` | modify | Ownership split assertion only; no formal-rule behavior change. |

## Task 1: Freeze the dispute vocabulary and identity grammar

### Intent

Create the single domain module that later phases extend. A smaller implementer
must not invent case kinds, claim roles, id prefixes, or limits while writing the
ledger.

### Implementation Steps

1. Create `src/agents/cognition/legal_disputes.py` with a module docstring:
   a dispute is one owner's belief about attributed claims, testimony, evidence,
   rule interpretations, mediation links, and proposed or declared resolutions;
   it is not a court, verdict, justice engine, or global case registry.
2. Define `DISPUTE_POLICY_VERSION: Final[str] = "dispute-resolution.v1"`.
3. Define `DISPUTE_ID_HEX_LEN: Final[int] = 16` and these prefixes:
   `dsc-` dispute case, `dcl-` claim, `dts-` testimony, `dev-` evidence,
   `drf-` rule reference, `dmr-` mediation reference, `dar-` authority
   reference, `drs-` resolution, `drp-` resolution response.
4. Define digest namespaces exactly: `dispute-case`, `dispute-claim`,
   `dispute-testimony`, `dispute-evidence`, `dispute-rule-reference`,
   `dispute-mediation-reference`, `dispute-authority-reference`,
   `dispute-resolution`, `dispute-resolution-response`, `dispute-subject`,
   `dispute-party-set`.
5. Define anchored regexes and `require_*` validators for every prefix. Reject
   uppercase, non-hex, wrong length, and foreign prefixes with
   `DisputeError("dispute_invalid_id")`.
6. Define the closed enums exactly:
   - `DisputeKind`: `contested_debt`, `ownership_claim`,
     `contract_interpretation`, `injury`, `broken_promise`,
     `resource_appropriation`, `other`.
   - `DisputeClaimRole`: `claim`, `counterclaim`, `supplementary`.
   - `DisputeClaimPolarity`: `affirm`, `deny`, `uncertain`.
   - `DisputeClaimKind`: `debt_owed`, `item_owned`, `term_meaning`,
     `harm_caused`, `promise_broken`, `resource_taken`, `other`.
   - `DisputeSubjectKind`: `commitment`, `item`, `resource`, `action`, `record`,
     `relationship`, `unspecified`.
   - `DisputeStatus`: `open`, `evidence_gathering`, `rule_cited`,
     `mediation_referenced`, `resolution_proposed`, `contested`,
     `apparently_resolved`, `withdrawn`, `abandoned`, `reopened`, `expired`.
   - `DisputeEvidenceChannel`: `observed`, `communicated`, `remembered`,
     `recorded`, `derived`, `unknown`.
   - `DisputeEvidenceReferenceKind`: `observed_occurrence`,
     `observed_communication`, `memory_trace`, `reconstructed_memory`,
     `artifact`, `durable_record`, `repository_entry`, `commitment`,
     `valuation`, `mediation_record`, `rule_record`, `office_record`,
     `institution_record`, `organization_record`, `unknown`.
   - `DisputeTestimonyChannel`: `direct`, `communicated`.
   - `DisputeRuleApplicability`: `applies`, `does_not_apply`, `uncertain`.
   - `DisputeRuleInterpretation`: `literal`, `narrow`, `broad`, `custom`,
     `unknown`.
   - `DisputeRuleReferenceStatus`: `resolved`, `orphaned`, `version_mismatch`,
     `contested`, `retired`.
   - `DisputeAuthorityKind`: `self`, `office`, `institution`, `organization`,
     `collective_decision`, `procedure`, `written_record`, `custom`, `unknown`.
   - `DisputeMediationLinkStatus`: `linked`, `stale`, `orphaned`, `disputed`.
   - `DisputeResolutionSource`: `negotiated`, `mediator`, `unilateral`,
     `custom`, `unknown`.
   - `DisputeResolutionStatus`: `proposed`, `partially_accepted`,
     `apparently_accepted`, `contested`, `withdrawn`, `expired`, `superseded`.
   - `DisputeResolutionTermKind`: `return_item`, `transfer_item`,
     `perform_service`, `stop_action`, `acknowledge`, `no_action`.
   - `DisputeResolutionResponseKind`: `accept`, `reject`, `counterpropose`,
     `defer`, `withdraw`.
   - `DisputeProvenance`: `self_asserted`, `communicated`,
     `derived_from_memory`, `derived_from_record`, `derived_from_rule`,
     `derived_from_mediation`, `derived_from_observation`, `contested`,
     `orphaned`, `unknown`.
   - `DisputeReportKind`: `claim_reported`, `testimony_reported`,
     `resolution_reported`, `acceptance_reported`, `rejection_reported`.
7. Define `DISPUTE_ERROR_CODES` and `DisputeError` with a safe `.code`.
8. Define frozen `DisputePolicy` with locked values:
   `max_cases=16`, `max_claims_per_case=16`, `max_testimony_per_case=32`,
   `max_evidence_per_claim=16`, `max_rule_references_per_case=8`,
   `max_authority_references_per_case=8`, `max_mediation_references_per_case=4`,
   `max_resolutions_per_case=4`, `max_responses_per_resolution=8`,
   `max_parties=8`, `max_terms_per_resolution=4`, `max_total_records=640`,
   `min_testimony_for_corroboration=2`, `resolution_window_ticks=64`,
   `max_frame_chars=768`, `max_relations=32`.
9. Add `DISPUTE_FORBIDDEN_FIELD_NAMES` covering at least: `verdict`,
   `judgment`, `court`, `judge`, `jury`, `jurisdiction`, `binding`, `enforce`,
   `guilt`, `liable`, `liability`, `damages`, `sentence`, `decree`, `winner`,
   `loser`, `true_owner`, `objective_claim`, `justice`, `arbiter_authority`,
   `case_registry`, `global_dispute_registry`, `authoritative_resolution`,
   `enforced_by_world`, `settlement_registry`, `punishment`, `police`,
   `government`, `sovereign`, `legal_code`, `statute`.
10. Add content-addressed minters using canonical JSON + SHA-256 and the
    namespaces above:
    - `dispute_case_id(owner_id, case_ref)`.
    - `dispute_claim_ref(case_ref, claimant_id, role, claim_kind, polarity,
      subject_digest)` — the portable claim token carried in speech.
    - `dispute_claim_id(owner_id, claim_ref)` — the owner-local `dcl-` id.
    - `dispute_testimony_id(owner_id, case_ref, claim_ref, speaker_id, channel,
      root_ref, tick)`.
    - `dispute_evidence_id(owner_id, case_ref, claim_ref, channel,
      reference_kind, reference_id, ordinal)`.
    - `dispute_rule_reference_id(owner_id, case_ref, system_ref, rule_id,
      version_number, interpretation)`.
    - `dispute_authority_reference_id(owner_id, case_ref, authority_kind,
      reference_id)`.
    - `dispute_mediation_reference_id(owner_id, case_ref, mediation_case_ref,
      recommendation_ref)`.
    - `dispute_resolution_ref(case_ref, proposer_id, terms_digest)` — the
      portable resolution token carried in speech.
    - `dispute_resolution_id(owner_id, resolution_ref)` — the owner-local
      `drs-` id.
    - `dispute_response_id(owner_id, resolution_ref, party_id, kind, tick)`.
11. Add `dispute_subject_digest(kind, subject_token)` and
    `dispute_party_set_digest(party_ids)`: sort, deduplicate, reject empty party
    sets beyond the owner, and return 64 hex chars. The case ref is the portable
    thread token `dispute_case_ref(subject_token, party_ids)`; the `party_ids`
    used for the ref are the initiating party set (claimant and respondent, or
    the mediation case parties). Later additional parties do not change the ref.
    The case `kind` may be refined from `other` to a specific kind without
    changing the ref. The owner-local case id is
    `dispute_case_id(owner_id, case_ref)`. The portable ref lets two owners
    discuss one thread without sharing a ledger.
12. The ids must not hash labels, evidence ordinals where an id would repeat, or
    any wall-clock value. Repeating the same claim updates ticks rather than
    minting a second identity.

### Required Interfaces and Contracts

```python
DISPUTE_POLICY_VERSION: Final[str] = "dispute-resolution.v1"

def dispute_case_ref(subject_token: str, party_ids: Sequence[str]) -> str: ...
def dispute_case_id(owner_id: str, case_ref: str) -> str: ...
def dispute_claim_ref(case_ref: str, claimant_id: str, role: str, kind: str, polarity: str, subject_digest: str) -> str: ...
def dispute_claim_id(owner_id: str, claim_ref: str) -> str: ...
def dispute_testimony_id(owner_id: str, case_ref: str, claim_ref: str, speaker_id: str, channel: str, root_ref: str, tick: int) -> str: ...
def dispute_evidence_id(owner_id: str, case_ref: str, claim_ref: str, channel: str, reference_kind: str, reference_id: str, ordinal: int) -> str: ...
def dispute_rule_reference_id(owner_id: str, case_ref: str, system_ref: str, rule_id: str, version_number: int, interpretation: str) -> str: ...
def dispute_authority_reference_id(owner_id: str, case_ref: str, authority_kind: str, reference_id: str) -> str: ...
def dispute_mediation_reference_id(owner_id: str, case_ref: str, mediation_case_ref: str, recommendation_ref: str) -> str: ...
def dispute_resolution_ref(case_ref: str, proposer_id: str, terms_digest: str) -> str: ...
def dispute_resolution_id(owner_id: str, resolution_ref: str) -> str: ...
def dispute_response_id(owner_id: str, resolution_ref: str, party_id: str, kind: str, tick: int) -> str: ...
def require_dispute_policy(policy: object | None) -> DisputePolicy: ...
def default_dispute_policy() -> DisputePolicy: ...
```

Compatibility invariants:

- Enum values are stable API identifiers; never rename them in a later phase.
- There is no `verdict`, `guilt`, `liable`, `court`, `judge`, or `jurisdiction`
  member in any enum.
- All minters are deterministic and owner-scoped. No `hash()`, UUID, wall clock,
  or global random source.
- The policy object is frozen and `__post_init__` refuses non-locked values with
  `dispute_policy_not_locked`.

### Requirement Evidence

- Original Request: structured disputes, six example kinds, separate claims,
  sincere memory disagreement, claim/counterclaim/testimony/evidence/rule/
  mediation/resolution support, no objective justice oracle, research-only
  objective history, mediation and institutional-role integration.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-6 and "Important V3 seams"
  V3-29 through V3-32.
- `src/simulation/v4_architecture.py` 136-149: owner-scoped authority and the two
  non-goals.
- `src/agents/cognition/formal_rules.py` 356-404, 1289-1395: id, error, policy,
  and owner-scoped ledger pattern.
- `src/agents/cognition/mediation.py` 74, 133, 158-220, 1373-1398: existing
  dispute-adjacent policy, forbidden fields, and response vocabulary.

### Error Handling and Logging

- Invalid ids raise `DisputeError("dispute_invalid_id")`.
- Invalid enum values raise `DisputeError("dispute_invalid_mode")`.
- Locked-policy violations raise `DisputeError("dispute_policy_not_locked")`.
- Party/subject overflows raise `DisputeError("dispute_party_limit")` or
  `DisputeError("dispute_subject_limit")`.
- DEBUG: `dispute_contract_validated name=%s count=%s` (enum name and count).
- Never log subject tokens, party ids, claim text, evidence ids, rule ids,
  mediation ids, resolution terms, or record bodies. INFO only on module-level
  policy construction (once per process).

### Tests

`tests/unit/test_dispute_contracts.py`:

- `test_policy_version_and_limits_are_locked`
- `test_every_id_prefix_round_trips_and_rejects_foreign_ids`
- `test_case_and_claim_ids_are_content_addressed_and_owner_scoped`
- `test_party_and_subject_digests_are_sorted_deduplicated_and_bounded`
- `test_kind_vocabulary_contains_the_six_requested_examples`
- `test_forbidden_justice_vocabulary_is_closed`
- `test_no_global_nondeterminism_imports`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_contracts.py -q`.

### Acceptance Criteria

- Every id prefix round-trips and rejects a foreign prefix.
- The six requested dispute kinds and six claim kinds exist exactly once.
- No forbidden justice/court/verdict vocabulary appears in enum members.
- Policy limits are exact and immutable.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_contracts.py -q`
- Expected result: all tests pass.

## Task 2: Own the legal_disputes capability flag

### Intent

Move `legal_disputes` from the unowned V4 set to the owned set without adding a
runner schema, root field, per-agent mode, or prerequisite flag requirement.

### Implementation Steps

1. In `src/simulation/runner_models.py`, add `"legal_disputes"` to
   `_V4_OWNED_CAPABILITY_FLAGS` (the frozenset currently containing
   `"organizations"` and `"formal_rules"`). Do not change
   `_V4_CAPABILITY_FLAG_NAMES` or the `V4CapabilityFlags` field list.
2. In `src/simulation/compatibility.py`, add `"legal_disputes"` to
   `V4_OWNED_CAPABILITY_FLAGS` and update the `v4_capability_flags` matrix row
   text to say three flags are owned and nine remain unowned.
3. Keep the accepted `runner-config-v56` keyset exactly the 12-name
   `v4_capability_flags` sibling. Do not add a root key or per-agent key.
4. Do not change `SimulationRunner.from_config`'s ownership logic. It already
   computes `unimplemented_enabled_names()` from the ownership pin; after the pin
   change, `legal_disputes` constructs and the other nine flags still fail with
   `capability_unimplemented` at `stage="v4_capability_flags"`.
5. Assert the declared context remains unchanged:
   `V4ContextId.LEGAL_DISPUTES`, `authority=OWNER_SCOPED`,
   `owner_packages=("agents.cognition", "simulation")`,
   `prerequisite_contexts=(V4ContextId.FORMAL_RULES,)`,
   `uses_existing_events=True`, and
   `required_config_seam="v4_capability_flags.legal_disputes"`.
6. Support both combinations: `legal_disputes` alone (rule references orphaned)
   and `legal_disputes` plus `formal_rules` (rule references resolve). Do not add
   a runtime prerequisite check between flags.
7. Update the ownership assertions in the architecture/unit tests without
   weakening the 14-context, 12-flag, four-reservation, or v56 exact-key pins.

### Required Interfaces and Contracts

```python
_V4_OWNED_CAPABILITY_FLAGS = frozenset(
    {"organizations", "formal_rules", "legal_disputes"}
)
V4_OWNED_CAPABILITY_FLAGS = frozenset(
    {"organizations", "formal_rules", "legal_disputes"}
)
```

Compatibility invariants:

- `runner-config-v56` remains accepted-only; the default write remains
  `runner-config-v4`.
- No `runner-config-v57` constant, no `SUPPORTED_RUNNER_SCHEMA_VERSIONS` entry,
  and no serializer branch is added.
- Enabling `legal_disputes` on v4 or v55 raises `v4_capability_requires_v56`.
- Enabling an unowned V4 flag still raises `capability_unimplemented` with
  `stage="v4_capability_flags"`.

### Requirement Evidence

- Original Request "structured social disputes" and "disputes and legal
  reasoning".
- `.ai-factory/ARCHITECTURE.md` "Capability ownership": owned V4 flags are
  `organizations` and `formal_rules`; this plan adds `legal_disputes`.
- `src/simulation/v4_architecture.py` 136-149: exact context declaration.
- `src/simulation/runner_models.py` 305-325, 1114-1163, 7936-7948.
- `src/simulation/compatibility.py` 155-157, 761-780.
- `src/simulation/runner.py` 2169-2238.

### Error Handling and Logging

- Unowned flags: safe log `runner_construction_v4_capability_unimplemented` and
  raise `RunnerConstructionError(CAPABILITY_UNIMPLEMENTED,
  stage="v4_capability_flags")`.
- Non-v56 enablement: `ValueError("V4 capability flags require
  runner-config-v56 (code=v4_capability_requires_v56)")`.
- INFO: `v4_capability_owned flag=legal_disputes owner_count=3` once at
  construction; never log flag combinations beyond safe names and counts.

### Tests

`tests/unit/test_v4_scaffolding_gate.py`:

- Remove `legal_disputes` from the unowned parameterization.
- Add `test_legal_disputes_constructs_on_v56`.
- Keep `test_unowned_v4_flag_still_fails_closed` covering `diplomacy`.

`tests/unit/test_runner_config_v56.py`:

- Exact 12-key sibling remains.
- `legal_disputes` constructs on v56.
- All-flags-off v56 round-trips byte-identically.
- v55 rejects the sibling.

`tests/unit/test_runner_config_v4_flags.py`:

- Closed 12-name set is unchanged.
- Owned split is exactly three flags; unowned split is exactly nine.

`tests/unit/test_organization_gate.py`:

- The ownership predicate treats `legal_disputes` as owned.
- The unowned parameterization excludes all three owned flags.
- No organization behavior changes.

`tests/unit/test_formal_rule_regression.py`:

- Change `test_formal_rules_flag_is_owned_and_ten_flags_remain_unowned` to
  assert exactly nine unowned flags and that `legal_disputes` is owned.
- Do not change formal-rule behavior or catalog assertions in this task; Task 13
  updates the catalog count and last-family ordering.

`tests/architecture/test_v4_architecture_invariants.py`:

- 14 contexts, 12 flags, `v4-context-map-v2`.
- Three owned flags; `legal_disputes` prerequisite is `formal_rules`.
- Four write-pair reservations and event-reusing contexts are unchanged.
- No `runner-config-v57` and no Alembic `0018`.

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_scaffolding_gate.py tests/unit/test_runner_config_v56.py tests/unit/test_runner_config_v4_flags.py tests/architecture/test_v4_architecture_invariants.py -q`.

### Acceptance Criteria

- `legal_disputes` is owned; enabling it on v56 constructs.
- The other nine flags still fail closed.
- No runner schema, root field, per-agent key, event, or migration is added.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_scaffolding_gate.py tests/unit/test_runner_config_v56.py tests/unit/test_runner_config_v4_flags.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected result: all tests pass; no `v57` or `0018` reference exists outside a
  negative assertion.

## Task 3: Add the cognition mode and policy seam

### Intent

Give the runner a deterministic on/off switch that is derived only from the
owned V4 flag, with a locked policy and a disabled passthrough that allocates no
ledger and changes no legacy condition identity.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`, define
   `CognitionDisputeMode(StrEnum)` with `DISABLED = "disabled"` and
   `DETERMINISTIC = "deterministic"`. Its docstring states it is lockstep with
   `simulation.V4CapabilityFlags.legal_disputes` and is not a per-agent runner
   mode.
2. Add `dispute_mode: CognitionDisputeMode = DISABLED` and
   `dispute_policy: DisputePolicy | None = None` to `CognitionLoopConfig`.
3. In normalization, when the mode is `DISABLED`, clear `dispute_policy` to
   `None`; when `DETERMINISTIC`, install `default_dispute_policy()` if no policy
   is supplied; reject a non-`DisputePolicy` value with
   `invalid_enum path=dispute_policy reason_code=invalid_type`.
4. Include `dispute_mode` and `dispute_policy_version` in the condition
   fingerprint only when the mode is `DETERMINISTIC`, matching the formal-rule
   pattern. Disabled runs must keep the legacy fingerprint.
5. In `src/simulation/runner.py`, add
   `legal_disputes_enabled: bool = False` to `_cognition_config_for(...)`.
   Derive `dispute_mode = DETERMINISTIC if legal_disputes_enabled else DISABLED`
   and `dispute_policy = default_dispute_policy() if enabled else None`.
6. Pass `legal_disputes_enabled=config.v4_capability_flags.legal_disputes` at
   all three cognition construction sites (initial, mid-run admission, bundle
   factory).
7. Add a deterministic INFO log on mode resolution:
   `cognition_dispute_mode mode=%s policy_version=%s`.
8. Do not add `AgentCognitionSpec.dispute_mode` or any per-agent runner key.

### Required Interfaces and Contracts

```python
class CognitionDisputeMode(StrEnum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"

@dataclass(frozen=True, slots=True)
class CognitionLoopConfig:
    ...
    dispute_mode: CognitionDisputeMode = CognitionDisputeMode.DISABLED
    dispute_policy: DisputePolicy | None = None
```

Compatibility invariants:

- Disabled mode allocates no ledger, emits no metrics, publishes nothing, and
  leaves every V1-V4-06 trajectory identical.
- Deterministic mode installs exactly `default_dispute_policy()`.
- The mode is run-level, not per-agent; all agents receive the same mode for a
  given run.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Optional channels default off and must leave
  off-path behavior unchanged."
- `src/agents/cognition/configuration.py` 408-420, 620-621, 1152-1169,
  1493-1497.
- `src/simulation/runner.py` 1006-1019, 1370-1389, 1518-1519, 2644-2651,
  6292-6299, 6665-6672.
- `tests/unit/test_formal_rule_config.py` 75-94: exact mode/policy seam
  precedent.

### Error Handling and Logging

- A non-`CognitionDisputeMode` value raises `TypeError`.
- A supplied policy under `DISABLED` is cleared with DEBUG
  `cognition_dispute_policy_cleared`.
- INFO mode resolution; no policy body, party data, or claim data is logged.

### Tests

`tests/unit/test_dispute_config.py`:

- `test_default_dispute_mode_is_disabled_and_policy_is_none`
- `test_deterministic_dispute_mode_installs_locked_policy`
- `test_disabled_mode_clears_supplied_policy`
- `test_condition_fingerprint_omits_disabled_dispute_fields`
- `test_legal_disputes_flag_derives_deterministic_mode`
- `test_no_per_agent_dispute_runner_key`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_config.py -q`.

### Acceptance Criteria

- Default configs remain `runner-config-v4` with dispute mode disabled.
- Enabling `legal_disputes` on v56 produces deterministic mode and the locked
  policy for every agent.
- Disabled mode leaves the condition fingerprint unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_config.py -q`
- Expected result: all tests pass.

## Phase Risks and Mitigations

- Risk: The ownership pin is duplicated in two modules and one is missed.
  Mitigation: Task 2 tests assert both pins and the 3/9 split.
- Risk: A new root field or per-agent key is introduced to carry the mode.
  Mitigation: Task 2/3 tests assert the exact v56 keyset and the absence of
  `AgentCognitionSpec.dispute_mode`.
- Risk: Disabled mode changes legacy condition identity.
  Mitigation: Task 3 fingerprint test and the V1 regression gate in Task 22.
- Risk: The media/legal vocabulary leaks an objective justice concept.
  Mitigation: Task 1 forbidden-field test and Task 20 boundary scan.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
