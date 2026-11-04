# Phase 1: Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Freeze the delegation-representation vocabulary, identity grammar, and locked
policy; prove that V4-09 deepens the already-owned `organizations` flag on
`runner-config-v56` without adding a flag, context, runner schema, root field, or
per-agent runner key; and install the disabled-by-default cognition mode seam.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/v4_architecture.py` | `V4_CONTEXT_MAP_VERSION` 38; `_REQUIRED_CONTEXT_COUNT` 56; `V4_CONTEXTS` 103-314; `organizations` 104-121; `diplomacy` 150-163; `V4_CAPABILITY_FLAGS` 324-326 | The 14/12 registry is closed; `diplomacy` already declares `organizations` as a prerequisite |
| `src/simulation/runner_models.py` | `_V4_OWNED_CAPABILITY_FLAGS` 320-325; `V4CapabilityFlags` 1114-1163; v56 gate 7964-7976 | `organizations` is owned; no new ownership or schema key may appear |
| `src/simulation/runner.py` | `_cognition_config_for` 1029-1031; organizations branch 1366-1397; legal-disputes branch 1416-1437 | Representation mode attaches inside the existing `organizations_enabled` branch |
| `src/agents/cognition/configuration.py` | `CognitionOrganizationMode`; `CognitionEvidenceMode` 440; loop config 647-658; reconciliation 1139-1227 | Mode/policy seam to extend |
| `src/agents/cognition/evidence_testimony.py` | policy 289-358; `EVIDENCE_FRAME_MAX_CHARS`; ids 38-58 | Locked-policy and id-grammar precedent |
| `src/agents/cognition/organization_concepts.py` | `ORGANIZATION_CONCEPT_ID_PREFIX` 31; `organization_concept_id` 373 | Owner-local collective anchor grammar |
| `tests/architecture/test_v4_architecture_invariants.py` | 160-200 | Existing 14/12/3 pin the new suite must extend, not weaken |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/delegation_representation.py` | create | Closed vocabulary, id grammar, locked policy, limits |
| `src/agents/cognition/configuration.py` | modify | `CognitionRepresentationMode`; loop-config fields and reconciliation |
| `src/simulation/runner.py` | modify | Derive mode/policy from `organizations_enabled` |
| `src/agents/cognition/loop.py` | modify | Install mode/policy and prepared slot (no behavior yet) |
| `src/agents/cognition/__init__.py` | modify | Export the frozen vocabulary |
| `tests/unit/test_delegation_representation_contracts.py` | create | Vocabulary/id/policy tests |
| `tests/unit/test_delegation_representation_config.py` | create | Mode and seam tests |
| `tests/architecture/test_delegation_representation_boundaries.py` | create | Ownership pin (extended in Task 20) |

## Task 1: Freeze the delegation-representation vocabulary and identity grammar

### Intent

One owner's belief about standing to act or speak for a principal must have a
closed, deterministic vocabulary before any record, frame, analysis row, or
route is written. Every later phase imports these names; changing them later
would ripple through the bundle.

### Implementation Steps

1. Create `src/agents/cognition/delegation_representation.py` with a module
   docstring stating that representation is an owner belief, never authority,
   permission, legitimacy, or truth.
2. Define `REPRESENTATION_POLICY_VERSION = "delegation-representation.v1"`,
   `REPRESENTATION_ID_HEX_LEN = 16`, the separator `"\x1f"`, and the id
   namespaces.
3. Define the closed str-enums exactly as listed under Required Interfaces.
4. Define id prefixes: owner-local `rmd-` (mandate), `rmp-` (position), `rmv-`
   (revocation), `rmx-` (conflict). Analytical `rep-`/`rep-edge-` prefixes are
   defined only in `analysis/delegation_representation_contract.py` (Task 10);
   `analysis` must not import `agents`, so this module exports no analytical
   grammar.
5. Define `RepresentationPolicy` as a frozen slots dataclass whose
   `__post_init__` compares every field to `_REPRESENTATION_POLICY_VALUES` (a
   `MappingProxyType`) and raises `RepresentationError(
   "representation_policy_not_locked")` on any mismatch.
6. Define `default_representation_policy()` returning the locked value.
7. Define token validators: `require_representation_id(value, prefix)`,
   `require_representation_token(value, *, max_chars)`, and
   `require_representation_scope_subject(value)` (lowercase `[a-z0-9_.:-]`, 1-32
   chars, `none` reserved).
8. Add `RepresentationError(Exception)` with a safe `.code` attribute; never put
   a token, actor id, or frame body into the message.
9. Export the enums, prefixes, policy, defaults, and validators from
   `src/agents/cognition/__init__.py` following the existing
   `evidence_testimony` export block.

### Required Interfaces and Contracts

```python
REPRESENTATION_POLICY_VERSION: Final[str] = "delegation-representation.v1"

class RepresentationPrincipalKind(StrEnum):
    AGENT = "agent"
    ORGANIZATION = "organization"
    SETTLEMENT = "settlement"
    COALITION = "coalition"
    UNKNOWN = "unknown"

class RepresentationScopeKind(StrEnum):
    SPEAK_FOR = "speak_for"
    NEGOTIATE = "negotiate"
    CARRY_MESSAGE = "carry_message"
    COORDINATE_PROJECT = "coordinate_project"
    TRANSACT = "transact"
    DECIDE = "decide"
    UNKNOWN = "unknown"

class RepresentationDurationKind(StrEnum):
    SINGLE_ACT = "single_act"
    OCCASION = "occasion"
    UNTIL_TICK = "until_tick"
    UNTIL_REVOKED = "until_revoked"
    UNKNOWN = "unknown"

class RepresentationStatus(StrEnum):
    CLAIMED = "claimed"
    RECOGNIZED = "recognized"
    CONTESTED = "contested"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"

class RepresentationProvenance(StrEnum):
    SELF_DECLARED = "self_declared"
    PRINCIPAL_DECLARED = "principal_declared"
    COMMUNICATED = "communicated"
    WITNESSED_ACT = "witnessed_act"
    WRITTEN_RECORD = "written_record"
    OFFICE_BELIEF = "office_belief"
    COLLECTIVE_DECISION = "collective_decision"
    PROCEDURE_BELIEF = "procedure_belief"
    UNKNOWN = "unknown"

class RepresentationPositionStance(StrEnum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    ABSTAIN = "abstain"
    UNKNOWN = "unknown"

class RepresentationRevocationKind(StrEnum):
    PRINCIPAL_REVOKED = "principal_revoked"
    REPRESENTATIVE_RESIGNED = "representative_resigned"
    COLLECTIVE_DECISION_REVOKED = "collective_decision_revoked"
    SCOPE_EXPIRED = "scope_expired"
    OFFICE_LOST = "office_lost"
    CONTESTED = "contested"
    UNKNOWN = "unknown"

class RepresentationRecognitionBasis(StrEnum):
    PRINCIPAL_DECLARATION = "principal_declaration"
    INDEPENDENT_SUPPORT = "independent_support"
    OFFICE_AUTHORITY = "office_authority"
    COLLECTIVE_DECISION = "collective_decision"
    WRITTEN_AUTHORIZATION = "written_authorization"
    NONE = "none"
    UNKNOWN = "unknown"

class RepresentationConflictKind(StrEnum):
    DUPLICATE_MANDATE = "duplicate_mandate"
    CONTRADICTORY_SCOPE = "contradictory_scope"
    CONFLICTING_PRINCIPAL = "conflicting_principal"
    REVOCATION_DISPUTE = "revocation_dispute"
    UNKNOWN = "unknown"
```

- `RepresentationPolicy` fields and locked values:
  `recognition_min_independent_roots=2`, `max_mandates=32`,
  `max_positions_per_mandate=32`, `max_revocations_per_mandate=8`,
  `max_conflicts_per_mandate=8`, `max_evidence_refs=8`, `max_decision_refs=8`,
  `max_office_refs=8`, `max_rule_refs=8`, `max_region_anchors=16`,
  `max_total_records=320`, `max_frame_chars=384`.
- No field may be named `truth`, `verified`, `legitimate`, `authority`,
  `permission`, `allowed`, `winner`, `proxy`, or `mandate_valid`.

### Error Handling and Logging

- Policy mismatch: raise `RepresentationError("representation_policy_not_locked")`.
- Unknown enum value construction raises `ValueError` from `StrEnum`; do not
  catch it in domain code.
- `_LOG.debug("representation_policy_loaded version=%s", ...)` with the version
  only; never log field values or ids.

### Tests

- `tests/unit/test_delegation_representation_contracts.py`:
  exact enum member sets; prefix regex acceptance/rejection (`rmd-` + 16 hex);
  `none` rejected as a scope subject; locked-policy mutation raises; default
  policy equals the mapping; id minter is deterministic for the same inputs and
  differs across ticks/owners; no forbidden field names on any dataclass
  (`truth`, `verified`, `legitimate`, `permission`, `winner`).

### Acceptance Criteria

- Every enum and prefix above exists exactly once and is exported.
- The policy is immutable and fails closed on any field change.
- No truth/authority/permission/verdict name exists in the module.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_contracts.py -q`
- Expected: all tests pass; `rg -n "truth|verified|legitimate|permission|winner" src/agents/cognition/delegation_representation.py` returns only docstring non-claim prose.

## Task 2: Pin the organizations deepening seam

### Intent

V4-09 must invest in the existing `organizations` capability without inventing
ownership. This task locks that decision in tests before any behavior exists so a
later task cannot quietly add a flag, context, schema, or per-agent key.

### Implementation Steps

1. Create `tests/architecture/test_delegation_representation_boundaries.py`
   with a `test_v4_09_deepens_organizations_without_new_schema` case.
2. Assert `V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"`, `len(V4_CONTEXTS)
   == 14`, `len(V4_CAPABILITY_FLAGS) == 12`, and
   `V4_OWNED_CAPABILITY_FLAGS == {"organizations", "formal_rules",
   "legal_disputes"}`.
3. Assert `V4_CONTEXT_BY_ID[V4ContextId.ORGANIZATIONS].authority is
   V4Authority.OWNER_SCOPED` and that `diplomacy` still declares
   `organizations` as a prerequisite and remains unowned.
4. Scan every first-party Python file under `src/` and assert the literal
   `runner-config-v57` does not occur.
5. Assert no `representation_mode` field exists on `AgentCognitionSpec`,
   `SimulationRunnerSpec`, or `SimulationRunnerConfig` (use
   `__dataclass_fields__`), mirroring
   `tests/unit/test_dispute_config.py:110-112`.
6. Assert `organizations` alone enables the representation seam and that
   enabling `diplomacy` still raises `capability_unimplemented` at
   `SimulationRunner.from_config` (reuse the existing fail-closed assertion
   pattern rather than constructing a new runner).
7. Create `tests/unit/test_delegation_representation_config.py` with the
   runner-side assertions for Task 3.

### Required Interfaces and Contracts

- The deepening is expressed only through `runner-config-v56` +
   `v4_capability_flags.organizations = true`.
- No new `V4ContextId`, `V4CapabilityFlags` field, `RUNNER_SCHEMA_VERSION_*`,
  support entry, codec key, or compatibility matrix row.
- `diplomacy` stays unowned and fail-closed; V4-09 does not claim it.

### Error Handling and Logging

- No runtime behavior. Test failures must name the offending symbol and path.
- Do not weaken `tests/architecture/test_v4_architecture_invariants.py`; add a
  new test instead.

### Tests

- `tests/architecture/test_delegation_representation_boundaries.py::test_v4_09_deepens_organizations_without_new_schema`
- `tests/unit/test_delegation_representation_config.py::test_no_representation_runner_key`

### Acceptance Criteria

- The suite proves 14 contexts, 12 flags, 3 owned flags, no v57, no new runner
  field, and fail-closed `diplomacy`.

### Verification

- `uv run pytest tests/architecture/test_delegation_representation_boundaries.py tests/unit/test_delegation_representation_config.py -q`
- Expected: pass; `git diff --stat src/simulation/v4_architecture.py src/simulation/runner_models.py` shows no change.

## Task 3: Add the cognition representation mode and policy seam

### Intent

The ledger must be constructed only when the owner-scoped `organizations`
capability is active, with the same run-wide, flag-derived activation used by
organization concepts, operations, and agency. No per-agent mode is introduced.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`, add
   `CognitionRepresentationMode` with `DISABLED = "disabled"` and
   `DETERMINISTIC = "deterministic"`, placed beside
   `CognitionOrganizationMode`.
2. Add `representation_mode: CognitionRepresentationMode = DISABLED` and
   `representation_policy: RepresentationPolicy | None = None` to
   `CognitionLoopConfig` after the organization-agency policy fields.
3. Extend `CognitionLoopConfig.__post_init__` reconciliation: DETERMINISTIC
   requires a policy; DISABLED requires `None`; reject any other combination
   with `representation_mode_policy_mismatch`. Follow the evidence block at
   `configuration.py:1211-1227`.
4. In `src/simulation/runner.py` inside the `organizations_enabled` branch,
   derive `representation_mode` and `representation_policy =
   default_representation_policy()` exactly as `organization_agency_policy` is
   derived at 1390-1392.
5. Pass both into `CognitionLoopConfig(...)` beside the organization-agency
   fields (the call site assembled at 1560-1575).
6. In `src/agents/cognition/loop.py`, add the install block beside the
   organization block at 925-963: store `_representation_mode`,
   `_representation_policy`, and allocate `_prepared_representation = None`.
   Do not call any ledger function yet.
7. Log `INFO cognition_representation_mode mode=... policy_version=...` when
   DETERMINISTIC and `DEBUG` when DISABLED.
8. Import `default_representation_policy` lazily inside
   `_cognition_config_for`, matching the existing local-import style.

### Required Interfaces and Contracts

- `CognitionRepresentationMode.DETERMINISTIC` is reachable only through
  `organizations_enabled`; `legal_disputes`, `formal_rules`, and all other V4
  flags must not enable it.
- Disabled mode is a passthrough: no ledger, no notices, no metrics, no
  publication.
- No new `SimulationRunnerSpec` or `SimulationRunnerConfig` field, no wire key,
  no codec change.

### Error Handling and Logging

- Reject DETERMINISTIC without a policy and DISABLED with a policy using
  `representation_mode_policy_mismatch`.
- Log mode and policy version only; never log policy field values.

### Tests

- `tests/unit/test_delegation_representation_config.py`:
  default config has DISABLED/None; `organizations=True` yields DETERMINISTIC
  with the locked policy; `formal_rules`/`legal_disputes` alone yield DISABLED;
  missing/mismatched policy raises; runner schema stays `runner-config-v56`.

### Acceptance Criteria

- Mode activation is derived solely from the owned `organizations` flag.
- Off-path configuration is byte-identical to V4-08.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_config.py -q`
- Expected: pass; `uv run pytest tests/unit/test_organization_agency_runtime.py tests/unit/test_dispute_config.py -q` stays green.

## Phase Risks and Mitigations

- Risk: adding a mode to `CognitionLoopConfig` accidentally changes the runner
  wire schema.
  Mitigation: Task 2 asserts no new spec/config field; Task 3 adds fields only
  to the loop config.
- Risk: representation gets enabled by the wrong V4 flag.
  Mitigation: parameterized tests over all 12 flags with only `organizations`
  expected to activate it.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
