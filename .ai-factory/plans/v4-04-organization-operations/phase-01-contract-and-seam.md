# Phase 1: Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-2
Depends on: none

## Objective

Freeze the V4-04 operational vocabulary, identity grammar, policy limits, and
config seam before any behavior is written. The phase must establish that
operational state is a second owner-scoped ledger keyed by existing `orgc-`
concepts, that it adds no V4 flag, runner schema, command, event, observer
semantic type, write pair, API version, or migration, and that it can be enabled
by the already-owned `organizations` flag without a `runner-config-v57`.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/organization_concepts.py` | `ORGANIZATION_CONCEPT_POLICY_VERSION` 30; `OrganizationConcept` 1203-1480; `OrganizationConceptLedger` 1482-1550; `apply_organization_concept_update` 2880-3175 | The concept contract stays unchanged; operations reference `orgc-` ids and reuse its owner/ledger validation style. |
| `src/agents/cognition/configuration.py` | `CognitionOrganizationMode` 382-390; `organization_concept_mode/policy` 588-591; validation 1064-1085; material digest 1392-1398 | Operations share the existing mode; only a policy field is added. |
| `src/simulation/runner.py` | `_build_cognition_config` organization block 1316-1332; `organizations_enabled` parameter 1011; result assembly 4949; export 5315-5328 | The runner already derives the concept mode from the flag; operations derive from the same boolean. |
| `src/simulation/runner_models.py` | `organization_concept_ledgers` 6374, 6644-6653; `RunnerResult` | The result carries detached ledgers; a sibling tuple is additive and not serialized into runner/result docs. |
| `src/simulation/v4_architecture.py` | `organizations` registry entry 103-121; non-goals 113-116 | The context is already owned, owner-scoped, and explicitly forbids a resource pool or treasury. |
| `src/simulation/versioning.py` | `V4_EVENT_REUSING_CONTEXTS` 99-120; reservations 124-139 | Operations must reuse existing events and allocate no write pair. |
| `src/simulation/organization_models.py` | constants 48-60; `OrganizationSnapshot` 453-530 | V4-03 owns `organization-snapshot-v1`; V4-04 will extend it additively in a later phase. |
| `tests/architecture/test_organization_boundaries.py` | 232-272 | Existing pins and ownership split are executable. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/organization_operations.py` | create | Closed enums, policy, ID/ref grammar, error codes, and public contract for operational state. |
| `src/agents/cognition/configuration.py` | modify | Add `organization_operation_policy`, validation, and material-digest participation. |
| `src/simulation/runner.py` | modify | Construct the default operation policy from `organizations_enabled`; log the mode/policy; keep v56. |
| `src/agents/cognition/loop.py` | modify | Accept and validate the operation policy; keep the concept mode as the only mode. |
| `src/agents/cognition/__init__.py` | modify | Re-export the new contract and policy symbols. |
| `tests/unit/test_organization_operations_contract.py` | create | Vocabulary, policy, ID, ref, and forbidden-name tests. |
| `tests/unit/test_organization_operations_config.py` | create | Config/runner seam tests proving no v57 and no new flag. |

## Task 1: Freeze the operational vocabulary and identity grammar

### Intent

Give later tasks one closed vocabulary. Every operational record must use these
enums and IDs; no later task may invent a synonym, a free-form status, or a
different identity shape.

### Implementation Steps

1. Create `src/agents/cognition/organization_operations.py` with a module
   docstring that states: operations are owner-scoped beliefs, never objective
   organization state, never a resource pool, and never a command source.
2. Add `ORGANIZATION_OPERATION_POLICY_VERSION = "organization-operations.v1"` and
   `ORGANIZATION_OPERATION_ANALYSIS_POLICY_VERSION = "organization-operations-analysis.v1"`.
3. Add ID prefixes and hex length:
   - `ORGANIZATION_DECISION_ID_PREFIX = "orgd-"`
   - `ORGANIZATION_ACTION_ID_PREFIX = "orga-"`
   - `ORGANIZATION_PUBLICATION_OPERATION_ID_PREFIX = "orgop-"`
   - `ORGANIZATION_OPERATION_EVIDENCE_ID_PREFIX = "orgev-"`
   - `ORGANIZATION_ID_HEX_LEN = 16`
   Reuse the concept module's 16-hex convention; do not create a second length.
4. Add `OrganizationOperationDomain` with exactly eight values:
   `resource_control`, `storage`, `record_keeping`, `membership_admission`,
   `membership_departure`, `role_assignment`, `procedure_action`,
   `internal_commitment`.
5. Add `OrganizationOperationAct` with exactly ten values:
   `admit`, `depart`, `assign`, `remove`, `authorize_control`, `revoke_control`,
   `invoke_procedure`, `declare_commitment`, `fulfill_commitment`, `record_decision`.
6. Add these status vocabularies:
   - `OrganizationControlStance`: `claimed`, `recognized`, `shared`, `disputed`,
     `former`, `unknown`.
   - `OrganizationAdmissionStance`: `admitted`, `claimed`, `self_joined`,
     `denied`, `disputed`, `former`, `unknown`.
   - `OrganizationDepartureStance`: `resigned`, `expelled`, `departed`,
     `disputed`, `unknown`.
   - `OrganizationAssignmentStance`: `assigned`, `claimed`, `disputed`,
     `removed`, `vacant`, `unknown`.
   - `OrganizationCommitmentStance`: `declared`, `accepted`, `fulfilled`,
     `violated`, `disputed`, `forgotten`, `unknown`.
7. Add `OrganizationAuthorityBasis` with exactly seven values: `self_authored`,
   `role_belief`, `decision_belief`, `procedure_belief`, `record_reference`,
   `observation`, `unknown`.
8. Add `OrganizationOperationOutcome` with exactly five values: `observed`,
   `attempted`, `completed`, `blocked`, `unknown`.
9. Add `OrganizationOperationProvenance` with exactly nine values:
   `self_authored`, `role_authorized`, `decision_supported`,
   `procedure_recognized`, `observed_effect`, `unknown_authority`, `contested`,
   `expired`, `orphaned`.
10. Add `ORGANIZATION_LEGITIMACY_DOCTRINES` as a closed frozenset:
    `none`, `group_owns`, `role_trusteeship`, `decision_grant`,
    `first_claimant_owns`, `shared_use`, `unknown`. `group_owns` and
    `first_claimant_owns` reuse the possession doctrine tokens; the others are
    operational beliefs. No token grants legal or objective ownership.
11. Add `OrganizationOperationError(ValueError)` with a stable `code` and a
    closed `ORGANIZATION_OPERATION_ERROR_CODES` frozenset. Codes must cover:
    `organization_operation_invalid`, `organization_operation_policy_mismatch`,
    `organization_operation_foreign_ledger`, `organization_operation_cap_exceeded`,
    `organization_operation_unknown_concept`, `organization_operation_unknown_decision`,
    `organization_operation_tick_regression`, `organization_operation_invalid_ref`,
    `organization_duplicate_operation`.
12. Add `OrganizationOperationPolicy` as a frozen slots dataclass with locked
    defaults, mirroring `OrganizationConceptPolicy` rather than inventing a
    `version` field:
    - `max_concepts = 16`
    - `max_controls = 32` (at most 16 per domain)
    - `max_admissions = 32`
    - `max_departures = 32`
    - `max_assignments = 16`
    - `max_procedures = 16`
    - `max_commitments = 16`
    - `max_decisions = 32`
    - `max_actions = 64`
    - `max_evidence_per_record = 8`
    - `max_total_evidence = 256`
    - `max_total_records = 256`
    - `max_owner_support = 32`
    - `max_contest = 32`
    Add `_LOCKED_OPERATION_POLICY_VALUES` as a `MappingProxyType` of the exact
    values and validate every field against it in `__post_init__`, failing with
    `organization_operation_policy_mismatch`. Add
    `default_organization_operation_policy()` returning a module-level singleton.
    The policy version is the module constant
    `ORGANIZATION_OPERATION_POLICY_VERSION`, not a dataclass field.
13. Add deterministic helpers:
    - `organization_decision_id(owner_id, organization_id, domain, act, tick, actor_id, target_id, anchor_kind, anchor_id, stance)` → `orgd-` + 16 hex.
    - `organization_action_id(owner_id, organization_id, decision_id, tick, actor_id, command_kind, anchor_kind, anchor_id)` → `orga-` + 16 hex.
    - `organization_publication_operation_id(organization_id, domain, tick, ordinal, content_digest)` → `orgop-` + 16 hex.
    - `organization_operation_evidence_id(owner_id, organization_id, source, tick, ordinal, ref)` → `orgev-` + 16 hex.
    All use `hashlib.sha256` over a `\x1f`-joined UTF-8 namespace. No `hash()`,
    `uuid`, wall clock, or mutable counter.
14. Add `organization_operation_ref(value: str, *, namespace: str) -> str` returning
    16 lowercase hex for the bounded speech frames. Namespaces are exactly
    `target`, `anchor`, `role_signature`, and `decision_content`. The
    `role_signature` ref is computed from an office's public
    function/context/duty signature, never from an owner-local office id; the
    `decision_content` ref is computed from a decision's topic/action/target
    material, never from an owner-local decision id.
15. Add `require_organization_decision_id`, `require_organization_action_id`,
    `require_organization_publication_operation_id`, and
    `require_organization_operation_evidence_id` validators.
16. Re-export the public symbols from `src/agents/cognition/__init__.py` in the
    same change, following the V4-03 facade convention.

### Required Interfaces and Contracts

- `OrganizationOperationDomain` values map one-to-one to the eight requested
  primitives. Do not add a ninth domain for "government", "treasury", or any
  hard-coded organization type.
- `OrganizationAuthorityBasis` describes *why the owner believes* an act is
  authorized; it is not a permission and is never checked by the world.
- `OrganizationOperationProvenance` describes how the owner learned or produced a
  decision/action record; it never asserts objective truth.
- The module may import `agents.models`, stdlib, and `agents.cognition` types, but
  it must not import `WorldState`, `WorldEngine`, `ActionSubmission`, `AgentCommand`,
  an event store, or any analysis/persistence/API module.
- No class name may end in `Command` or `Event` (the existing boundary test scans
  `organization_*.py`).
- Identity helpers accept only exact strings/ints; malformed values raise
  `OrganizationOperationError` with a stable code.

### Requirement Evidence

- Original Request: "Record provenance of decisions and actions"; the identity
  grammar is the provenance anchor.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 2: deterministic seeds,
  namespaced IDs, no global RNG/`hash()`/UUID/wall clock.
- V4-03 plan decision 6: `orgc-`, `org-`, and `org-edge-` are content-addressed
  from creation evidence.

### Error Handling and Logging

- Validation failures raise `OrganizationOperationError`; the rejected text is
  never echoed.
- Emit at most one DEBUG milestone in this task:
  `organization_operation_policy mode=contract domains=%s cap_concepts=%s`.
  Do not log raw ids, labels, anchors, or payloads.

### Tests

- `tests/unit/test_organization_operations_contract.py`:
  - every enum has exactly the documented members and order;
  - the eight domains equal the eight requested primitives by value;
  - the policy is frozen, uses the locked-values mapping, rejects any deviation,
    and `default_organization_operation_policy()` returns the same singleton;
  - there is no `version` dataclass field; the module constant is
    `organization-operations.v1`;
  - IDs are stable, prefix-correct, 16-hex, and differ when any material field
    changes;
  - refs are stable for the same `(namespace, value)` and differ across
    namespaces;
  - malformed ids/refs fail closed with a stable code;
  - no class in the module ends with `Command` or `Event`;
  - `inspect.signature` contains no peer/world parameter.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_contract.py -q`

### Acceptance Criteria

- The closed vocabulary and policy exist and are exported.
- Identity helpers are deterministic and content-addressed.
- No new command/event/world symbol is introduced.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_contract.py -q`
- Expected: pass.

## Task 2: Add the policy seam without a runner schema change

### Intent

Wire the operation policy through the existing `organizations` flag and the
existing cognition config. The flag already requires `runner-config-v56`; adding
operations must not create `runner-config-v57`, a new flag, or a per-agent runner
key.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`:
   - add `organization_operation_policy: OrganizationOperationPolicy | None = None`
     immediately after `organization_concept_policy`;
   - in `__post_init__`, when `organization_concept_mode` is `DISABLED`, set the
     operation policy to `None`; when it is `DETERMINISTIC` and the policy is
     `None`, set `default_organization_operation_policy()`; reject any other type;
   - extend `_material()` with `organization_operation_policy_version` set to
     `ORGANIZATION_OPERATION_POLICY_VERSION` only when the mode is
     `DETERMINISTIC` (there is no policy `.version` field).
2. In `src/agents/cognition/loop.py`:
   - add `organization_operation_policy: object | None = None` to the constructor
     after `organization_concept_policy`;
   - validate it with the same DISABLED/DETERMINISTIC pattern and store
     `_organization_operation_policy`;
   - add the field to the slots list and to `__init__` defaults.
3. In `src/simulation/runner.py` `_build_cognition_config`:
   - import `default_organization_operation_policy`;
   - compute `organization_operation_policy = default_organization_operation_policy()
     if organizations_enabled else None`;
   - pass it to `CognitiveLoopConfig`;
   - log `cognition_config_organization_operation mode=%s policy_version=%s` with
     the mode value and policy version only.
4. Do not touch `runner_models.py` schema constants, `V4CapabilityFlags`, the
   accepted v56 keyset, `simulation/versioning.py`, or `v4_architecture.py`.
5. Add a guard assertion in the config test that `RUNNER_SCHEMA_VERSION_V56` is
   still accepted and `runner-config-v57` is absent.

### Required Interfaces and Contracts

- `CognitionOrganizationMode` remains the only organization mode. There is no
  `CognitionOrganizationOperationMode`.
- `organization_operation_policy` is internal cognition configuration; it is not
  a runner JSON field and does not change the runner schema digest.
- The policy is allocated only when `organizations` is enabled; flags-off runs
  allocate nothing and remain byte-identical.
- The loop may accept the policy directly (unit tests) or receive it from
  `CognitionLoopConfig`; both paths must agree on version
  `organization-operations.v1`.

### Requirement Evidence

- Original Request: "Extend organizations with operational primitives" — extension,
  not a new capability.
- `.ai-factory/ARCHITECTURE.md` "Capability ownership": per-agent modes are not
  automatically capability flags.
- V4-03 plan decision 1: `organizations` requires the accepted `runner-config-v56`;
  no `v57`.

### Error Handling and Logging

- A mismatched policy type raises `TypeError` in the config/loop constructor.
- Disabled mode clears the policy; it never retains a stale policy.
- Logs are metadata-only: mode token, policy version, no owner sets or payloads.

### Tests

- `tests/unit/test_organization_operations_config.py`:
  - default config has `organization_concept_mode=DISABLED` and
    `organization_operation_policy is None`;
  - deterministic mode fills the default policy;
  - a custom policy is preserved; an invalid type fails;
  - material digest includes the operation policy version only when enabled;
  - `runner-config-v56` is accepted, `runner-config-v57` is absent, and
    `V4CapabilityFlags(organizations=True).owned_enabled_names() == ("organizations",)`;
  - constructing a runner config with `organizations=True` still produces v56 and
    an operation policy.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_config.py tests/unit/test_organization_gate.py -q`

### Acceptance Criteria

- The operation policy is derived from the existing flag.
- No runner schema, flag, or per-agent mode is added.
- Flags-off configs allocate no operation policy.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_config.py tests/unit/test_organization_gate.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: a second mode or v57 is introduced to "cleanly" gate operations.
  Mitigation: the contract names `CognitionOrganizationMode` as the only mode and
  the tests assert no v57.
- Risk: the operation policy changes the runner material digest and therefore
  runner compatibility.
  Mitigation: the policy lives in cognition config, not the runner JSON; only the
  internal cognition material digest changes when the flag is on.
- Risk: identity helpers diverge from V4-03's 16-hex convention.
  Mitigation: reuse the constant and test the prefix/length explicitly.

## Phase Completion Checklist

- Every Task 1-2 acceptance criterion is met.
- The closed vocabulary, policy, and ID grammar are exported.
- No v57, new flag, command, event, or migration exists.
- `index.md` task checkboxes are updated immediately after verified completion.
