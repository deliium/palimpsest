# Phase 1: Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-2
Depends on: none

## Objective

Freeze the V4-05 collective-agency vocabulary, identity grammar, locked policy, and
cognition configuration seam. The result is a stable contract that later phases
consume without adding a V4 flag, a runner schema, a per-agent runner key, a
command, an event, or a migration.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/organization_operations.py` | `ORGANIZATION_OPERATION_POLICY_VERSION` 45; ID prefixes 50-53; `OrganizationOperationDomain` 89-99; `OrganizationAuthorityBasis` 173-187; `OrganizationOperationPolicy` 256-323; ID helpers 356-539; error codes 225-237; `FORBIDDEN_OPERATION_FIELD_NAMES` 603-611 | Exact pattern to mirror for a third organization sidecar |
| `src/agents/cognition/organization_concepts.py` | `ORGANIZATION_CONCEPT_ID_PREFIX = "orgc-"` 30-46; `OrganizationStatus` 50-58; `OrganizationProcedureBelief` 846-886; `OrganizationConceptLedger` 1482-1549; `FORBIDDEN_ORGANIZATION_FIELD_NAMES` 483-512 | Existing concept identity, status, procedure belief, and forbidden-field conventions |
| `src/agents/cognition/configuration.py` | `CognitionOrganizationMode` 387-395; `CognitionLoopConfig.organization_concept_mode` 593-597; validation/null allocation 1070-1111; fingerprint 1418-1429; `build_cognitive_loop` 1694-1696 | The only seam V4-05 may extend; no new runner field |
| `src/simulation/runner.py` | `_cognition_config_for(..., organizations_enabled=...)` 1005-1012; organizations wiring 1316-1346; `CognitionLoopConfig` assembly 1471-1473 | Proves the `organizations` flag already carries both V4-03 and V4-04 policies |
| `src/simulation/runner_models.py` | `RUNNER_SCHEMA_VERSION_V56` 150; `_V4_OWNED_CAPABILITY_FLAGS = {"organizations"}` 320-323; `V4CapabilityFlags.organizations` 1112-1140; `v4_capability_requires_v56` 7907-7919 | Must remain unchanged; no `runner-config-v57` |
| `src/simulation/v4_architecture.py` | `V4ContextId.ORGANIZATIONS` 60-76; context spec 103-121 | The context is owner-scoped and already declared; V4-05 deepens it |
| `src/agents/cognition/__init__.py` | organization import blocks 692-831; `__all__` 1230-1256, 1646-1704, 1857-1858, 1944-1945, 1983-1984, 2000-2001, 2079-2094, 2107-2110, 2134-2144, 2160-2161 | Public facade that must export the new symbols |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/organization_agency.py` | create | Module docstring, policy version constants, ID prefixes/namespaces, closed enums, error codes, notices, forbidden field names, locked policy, ID/ref minting and validation |
| `src/agents/cognition/configuration.py` | modify | Add `organization_agency_policy` to `CognitionLoopConfig`; import the default policy; validate it only when `organization_concept_mode` is `DETERMINISTIC`; include the policy version in the fingerprint; forward it in `build_cognitive_loop` |
| `src/agents/cognition/loop.py` | modify | Add `_organization_agency_policy` and `_prepared_organization_agency` to `__slots__` (356) and the constructor signature (487); validate/store the policy beside the V4-04 policy |
| `src/simulation/runner.py` | modify | Allocate `default_organization_agency_policy()` when `organizations_enabled`; pass it into `CognitionLoopConfig`; no runner schema change |
| `src/agents/cognition/__init__.py` | modify | Export the public vocabulary from phase 1 |
| `src/agents/cognition/models.py` | modify | No data field yet; only import surface if needed for type aliases in phase 2 |
| `tests/unit/test_organization_agency_config.py` | create | Dedicated config/fingerprint/loop-construction tests mirroring `test_organization_operations_config.py` |

## Task 1: Freeze the collective-agency vocabulary and identity grammar

### Intent

Create the closed vocabulary every later phase uses. This task deliberately adds
no ledger or update logic; it prevents later phases from inventing names, ID
prefixes, policy bounds, or provenance codes ad hoc.

### Implementation Steps

1. Create `src/agents/cognition/organization_agency.py` with a module docstring
   that states: a collective decision is an owner-scoped belief about a
   recognized collective process, never an organization will, never an
   objective actor, and never a command source. Every physical effect remains an
   ordinary agent command admitted by `WorldEngine`.
2. Add these policy constants:
   - `ORGANIZATION_AGENCY_POLICY_VERSION = "organization-agency.v1"`
   - `ORGANIZATION_AGENCY_ANALYSIS_POLICY_VERSION = "organization-agency-analysis.v1"`
   - `ORGANIZATION_AGENCY_COMMUNICATION_POLICY_VERSION = "organization-agency-communication.v1"` in the communication module (Task 4), re-exported through `agents.cognition`.
3. Add exact owner-local ID prefixes and validators:
   - `orgp-` proposal
   - `orgpm-` amendment
   - `orgcd-` collective decision
   - `orgci-` implementation record
   - `orgcev-` agency evidence
   - `orgcpd-` published collective decision
   - `orgcpi-` published implementation record
   Every prefix is followed by exactly 16 lowercase hex characters
   (`ORGANIZATION_ID_HEX_LEN`). Add `organization_proposal_id`,
   `organization_amendment_id`, `organization_collective_decision_id`,
   `organization_implementation_id`, `organization_agency_evidence_id`,
   `organization_publication_decision_id`,
   `organization_publication_implementation_id`, and their `require_*`
   validators. Use SHA-256 over a versioned namespace plus sorted material, then
   take the first 16 hex characters; never use `hash()`, UUID, wall clock, or a
   mutable counter.
4. Add content-reference helpers:
   - `organization_agency_ref(namespace, material)` with namespaces
     `proposal`, `terms`, `procedure`, `target`, `actor`, `decision`.
   - `require_organization_agency_ref` for exactly 16 lowercase hex characters.
   `proposal_ref` is derived from public proposal content (action domain,
   effect, procedure ref, target kind/ref, revision), not from `orgp-` or
   `orgc-`; the frame does not carry a topic token.
5. Add closed enums:
   - `OrganizationAgencyTopic`: `resource_use`, `storage`, `record_keeping`,
     `membership`, `role`, `procedure`, `commitment`, `other`.
   - `OrganizationAgencyProposalStatus`: `draft`, `active`, `amended`,
     `withdrawn`, `decided`, `expired`, `unknown`.
   - `OrganizationAgencyPositionStance`: `support`, `oppose`, `abstain`, `amend`,
     `withdraw`, `unknown`.
   - `OrganizationAgencyRecognition`: `recognized`, `contested`, `unrecognized`,
     `expired`, `unknown`.
   - `OrganizationAgencyImplementationStatus`: `pending`, `implemented`,
     `partial`, `unimplemented`, `obstructed`, `refused`, `sabotaged`,
     `contrary`, `unknown`, `expired`.
   - `OrganizationAgencyImplementationMode`: `physical`, `testimonial`.
   - `OrganizationAgencyEffect`: the real observed event kinds listed in the
     interface contract below, plus `none`.
   - `OrganizationAgencyReportKind`: `implemented`, `partial`, `unimplemented`,
     `refusal`, `sabotage`.
   - `OrganizationAgencyProvenance`: `self_authored`, `communicated`,
     `procedure_recognized`, `observed_effect`, `declared_refusal`,
     `contrary_effect`, `declared_sabotage`, `contested`, `unrecognized`,
     `expired`, `orphaned`, `unknown`.
   - `ORGANIZATION_AGENCY_NOTICE_CODES` as a closed string set:
     `proposal_expired`, `amendment_out_of_order`, `procedure_unresolved`,
     `target_unresolved`, `agency_truncated`, `implementation_truncated`,
     `refusal_unverified`, `sabotage_unverified`, `orphaned_concept`,
     `foreign_owner`, `malformed_claim`.
   Reuse `OrganizationAuthorityBasis` and `OrganizationOperationDomain` from
   `organization_operations`; do not duplicate them.
6. Add `ORGANIZATION_AGENCY_ERROR_CODES` and `OrganizationAgencyError`:
   `organization_agency_invalid`, `organization_agency_policy_mismatch`,
   `organization_agency_foreign_ledger`, `organization_agency_cap_exceeded`,
   `organization_agency_unknown_concept`, `organization_agency_unknown_proposal`,
   `organization_agency_unknown_decision`, `organization_agency_tick_regression`,
   `organization_agency_invalid_ref`, `organization_agency_duplicate_record`,
   `organization_agency_invalid_transition`,
   `organization_agency_unresolved_procedure`.
7. Add `FORBIDDEN_AGENCY_FIELD_NAMES` by extending
   `FORBIDDEN_OPERATION_FIELD_NAMES` with: `will`, `volition`, `intent`,
   `consensus`, `quorum`, `majority`, `binding`, `enforce`, `permission`,
   `command`, `organization_llm`, `global_prompt`, `collective_prompt`,
   `sabotage_intent` (the last is forbidden as an objective field; the belief
   code `sabotage` is allowed only under the provenance enum).
8. Add `OrganizationAgencyPolicy` with locked values:
   `max_concepts=16`, `max_proposals=32`, `max_positions=64`, `max_amendments=32`,
   `max_decisions=32`, `max_implementations=64`, `max_expected_actors=16`,
   `max_evidence_per_record=8`, `max_total_records=256`,
   `max_total_evidence=256`, `max_owner_support=32`, `max_contest=32`,
   `max_revision=9999`, `proposal_window_ticks=16`,
   `implementation_window_ticks=32`, `recognition_min_supporters=1`,
   `procedure_min_recurrence=2`, `max_decision_implementations=32`.
   Validate every value by type and exact equality in `__post_init__`; expose
   `default_organization_agency_policy()`.
9. Add `ORGANIZATION_AGENCY_TARGET_KINDS` as a closed set:
   `item`, `resource`, `artifact`, `structure`, `repository`,
   `collective_project`, `commitment`, `location`, `agent`, `none`, `unknown`.
10. Add `ORGANIZATION_AGENCY_EFFECTS` as a frozen set of the real observation
   kinds, `ORGANIZATION_AGENCY_CONTRARY_EFFECTS` as a closed set of destructive
   or obstructive observation kinds (`attack`, `artifact_destroyed`,
   `artifact_damaged`, `artifact_partially_lost`, `public_good_opposed`,
   `repository_maintained`, `take`, `drop`), and
   `ORGANIZATION_AGENCY_DOMAIN_EFFECTS` mapping `OrganizationOperationDomain` to
   allowed expected effects. The mapping is the only place domain-to-effect
   policy lives; contrary effects are never valid expected effects.
11. Export the new names from `src/agents/cognition/__init__.py` in the existing
    organization blocks; do not reorder or remove existing exports.

### Required Interfaces and Contracts

- `ORGANIZATION_AGENCY_EFFECTS` values must be exact observed event kinds:
  `give`, `item_stored`, `artifact_created`, `artifact_modified`,
  `artifact_destroyed`, `repository_member_deposited`,
  `repository_member_retrieved`, `repository_established`,
  `repository_maintained`, `structure_built`, `structure_repaired`,
  `resource_harvested`, `item_crafted`, `project_contributed`,
  `public_good_maintained`, `public_good_opposed`, `public_good_benefit`,
  `help`, `feed`, `transport`, `move`, `attack`, `commitment_declared`,
  `exchange_completed`, `none`.
- `ORGANIZATION_AGENCY_DOMAIN_EFFECTS`:
  - `resource_control` -> `give`, `item_stored`, `resource_harvested`, `none`
  - `storage` -> `item_stored`, `repository_member_deposited`,
    `repository_established`, `repository_maintained`, `none`
  - `record_keeping` -> `artifact_created`, `artifact_modified`,
    `repository_member_deposited`, `repository_member_retrieved`, `none`
  - `membership_admission` -> `none`
  - `membership_departure` -> `none`
  - `role_assignment` -> `none`
  - `procedure_action` -> every non-destructive effect plus `none`
  - `internal_commitment` -> `commitment_declared`, `give`, `help`, `feed`,
    `transport`, `none`
- A proposal with a `none` effect is `testimonial`; every other effect is
  `physical`.
- `organization_agency_ref` never includes an owner id, `orgc-`, or a member set.
- Policy values are exact; a mismatch raises
  `organization_agency_policy_mismatch` before any state is built.

### Requirement Evidence

- Original Request: "Implement collective decisions without turning
  organizations into super-agents"; "Do not add a global OrganizationLLM";
  "Agent cognition remains the source of intentional actions."
- `.ai-factory/ARCHITECTURE.md` "V4-04 organizations operations seam" and "Key
  Principles 1-2": owner beliefs, detached analysis, deterministic identity.
- `.ai-factory/ARCHITECTURE.md` "Important V3 seams": offices, collective
  decisions, and mediation remain beliefs, never permissions.
- V4-04 `organization_operations.py` identity/policy pattern (cited above).

### Error Handling and Logging

- Every validation failure raises `OrganizationAgencyError` with a code from the
  closed set; no payload detail is included in the exception text.
- `default_organization_agency_policy()` logs once at DEBUG:
  `organization_agency_policy mode=contract domains=%s caps=%s`.
- Do not log proposal text, utterance bodies, member sets, labels, or
  `orgc-`/`orgp-` values at INFO or above.

### Tests

Create `tests/unit/test_organization_agency_contract.py`:
- ID grammar accepts exactly 16 lowercase hex; rejects uppercase, wrong length,
  `orgc-`, `orgd-`, `orga-`, `orgp-x`, and non-hex.
- Each ID minter is deterministic across repeated calls and differs when one
  material field changes.
- `organization_agency_ref` never contains `orgc-`, `orgp-`, or an owner id.
- Policy accepts the default; each mutated field raises
  `organization_agency_policy_mismatch`.
- Every effect in `ORGANIZATION_AGENCY_EFFECTS` is a string token; every domain
  maps to a non-empty subset; `none` appears exactly in the testimonial domains.
- `ORGANIZATION_AGENCY_CONTRARY_EFFECTS` is disjoint from every domain's allowed
  expected effects.
- Forbidden field names include `will`, `consensus`, `binding`, `permission`,
  `organization_llm`, and `command`.
- Public facade exports every new symbol.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_contract.py -q`

### Acceptance Criteria

- The module imports without importing `WorldState`, `WorldEngine`, event stores,
  commands, `llm`, API, persistence, or analysis.
- All prefixes and policy values are exact and test-pinned.
- No existing organization, runner, command, event, or metric symbol changes.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_contract.py -q`
- Expected: all tests pass; `ruff check src/agents/cognition/organization_agency.py`
  clean.

## Task 2: Add the policy seam without a runner schema change

### Intent

Carry the locked policy through the existing `organizations` capability without
adding `runner-config-v57`, a new V4 flag, a root field, or a per-agent mode.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`, import
   `OrganizationAgencyPolicy` and `default_organization_agency_policy` beside the
   V4-04 imports at line 82, then add
   `organization_agency_policy: OrganizationAgencyPolicy | None = None` to
   `CognitionLoopConfig` beside `organization_operation_policy`.
2. In `CognitionLoopConfig.__post_init__` (or the existing validation block at
   1070-1111), require a non-`None` `OrganizationAgencyPolicy` only when
   `organization_concept_mode is CognitionOrganizationMode.DETERMINISTIC`; set
   it to `None` when the mode is `DISABLED`. Reject a wrong type with the
   existing configuration error convention.
3. Include `organization_agency_policy_version` in the configuration
   fingerprint only when the mode is `DETERMINISTIC`, exactly as the V4-04 policy
   is included at 1418-1429.
4. Forward the field in `build_cognitive_loop` at 1694-1696.
5. In `src/agents/cognition/loop.py`, add `_organization_agency_policy` and
   `_prepared_organization_agency` to `__slots__` (356), add
   `organization_agency_policy: object | None = None` to the constructor
   signature beside `organization_operation_policy` (487), and validate/store it
   in the organization policy block at 893-938. Initialize
   `_prepared_organization_agency` to `None`. Do not add a new mode enum.
6. In `src/simulation/runner.py`, import
   `default_organization_agency_policy` beside the V4-04 import at 1320, allocate
   it in `_cognition_config_for` when `organizations_enabled is True`, and pass
   it into `CognitionLoopConfig` at the 1471-1473 assembly point. Do not add a
   runner config field, wire key, or supported version.
7. Add no `v4_capability_flags` key, no `runner-config-v57`, and no
   `runner_serialization.py` change.

### Required Interfaces and Contracts

- `CognitionLoopConfig.organization_agency_policy` is internal cognition
  configuration; it never appears in runner JSON.
- The `organizations` flag remains the only V4 gate.
- `CognitionOrganizationMode.DETERMINISTIC` is the only enabling value; off-path
  behavior is byte-identical to V4-04.
- The fingerprint changes only for organizations-enabled runs, and only by the
  policy version string.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Capability ownership": `organizations` is the
  one owned V4 flag; new behavior must use its owned, versioned configuration
  seam.
- V4-04 `architecture decision 1` and Task 2: policy seam without a runner schema
  change.
- `src/simulation/runner_models.py` 305-322, 1112-1140, 7907-7919.

### Error Handling and Logging

- A missing policy with mode `DETERMINISTIC` fails closed at loop construction
  with the existing configuration error code; log
  `organization_agency_config_rejected reason=missing_policy` at WARN with no
  owner or payload fields.
- Log `organization_agency_policy_bound mode=deterministic` once at INFO when
  the loop is constructed; counts only.

### Tests

Create `tests/unit/test_organization_agency_config.py` (mirroring
`tests/unit/test_organization_operations_config.py`) and extend
`tests/unit/test_organization_agency_contract.py` and
`tests/unit/test_organization_agency_runtime.py`:
- `CognitionLoopConfig(organization_concept_mode=DETERMINISTIC, organization_agency_policy=None, ...)`
  fails closed.
- `DISABLED` with a policy is normalized to `None`.
- Fingerprint contains `organization_agency_policy_version` only when mode is
  enabled, and differs between policy versions.
- `build_cognitive_loop` forwards the policy; `CognitiveLoop._organization_agency_policy`
  is the exact policy and `_prepared_organization_agency` starts `None`.
- `SimulationRunner.from_config` with `organizations=True` on
  `runner-config-v56` constructs a loop with the agency policy.
- `organizations=True` on v4/v55 fails with `v4_capability_requires_v56`.
- `runner-config-v57` is absent from the supported set and decoding rejects it.
- A default flags-off run has `organization_agency_policy is None` and no agency
  ledger.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_config.py tests/unit/test_organization_agency_contract.py tests/unit/test_organization_agency_runtime.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py -q`

### Acceptance Criteria

- No new runner schema, flag, root field, or per-agent mode exists.
- The policy is present exactly when the `organizations` flag is enabled on v56.
- V4-04 and V4-03 behavior is unchanged when the new policy is default.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_config.py tests/unit/test_organization_agency_contract.py tests/unit/test_organization_agency_runtime.py tests/unit/test_runner_config_v56.py -q`
- Expected: all tests pass; `git diff` shows no runner schema version change.

## Phase Risks and Mitigations

- Risk: a new ID prefix collides with `orgc-` or `orgd-`.
  Mitigation: exact `^prefix-<16 hex>$` patterns and a table-driven collision test
  covering every existing organization prefix.
- Risk: policy allocation accidentally appears in runner JSON.
  Mitigation: runner serialization tests assert the v56 wire key set is
  unchanged and `organization_agency_policy` never appears in encoded config.
- Risk: a later phase adds a mode to avoid the policy seam.
  Mitigation: Task 19 boundary scan rejects any `CognitionOrganizationAgencyMode`
  or `organization_agency_mode` runner key.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
