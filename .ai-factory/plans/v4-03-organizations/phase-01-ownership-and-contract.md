# Phase 1: Ownership and Closed Contract

Plan: [index.md](index.md)
Tasks: 1-2
Depends on: none

## Objective

Own the already-declared `organizations` V4 context on the existing
`runner-config-v56` seam, and freeze the closed owner-scoped organization
vocabulary, identity grammar, policy, and error codes that every later phase
consumes. No behavior, event, command, migration, or runner schema is added in
this phase.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `V4_CONTEXTS` 103-310; `ORGANIZATIONS` 104-117; `V4Authority.OWNER_SCOPED` 79-85; `validate_v4_contexts` 357-407 | The context is already declared `owner_scoped`, owners `("agents.cognition", "social", "simulation")`, seam `v4_capability_flags.organizations`, `uses_existing_events=True`, prerequisites `()`, non-goals "no global organization actor or registry" and "no automatic resource pool or treasury". |
| `src/simulation/runner_models.py` | `_V4_CAPABILITY_FLAG_NAMES` 305-318; `_V4_OWNED_CAPABILITY_FLAGS` 320-322; `V4CapabilityFlags` 1111-1159; `SimulationRunnerConfig` 7526; schema gate 7882-7894 | Ownership is currently empty; every flag is unimplemented. Any enabled V4 flag requires `runner-config-v56`. |
| `src/simulation/runner.py` | `from_config` 2025+; V4 fail-closed 2141-2154 | `v4_unimplemented` is derived from `unimplemented_enabled_names()`; owning `organizations` removes it from that tuple without touching the gate. |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 155; runner-config bump 525-530; `v4_capability_flags` entry 757-773 | Public compatibility declaration and human-readable bump text must agree with ownership. |
| `src/simulation/versioning.py` | `V4_EVENT_REUSING_CONTEXTS` 77-90; reservations 39-75 | `organizations` is a reuse context. It must never claim event 23-26 or codec `v21`-`v24`. |
| `src/observer/capabilities.py` | `ObserverCapability` 17-29; advertised 32-37; reserved 39-46 | `organization_rows` is a reserved observer capability; V4-03 must not advertise it or change `/version`. |
| `tests/architecture/test_v4_context_registry.py` | 99-177 | Pins 14 contexts, 12 flags, `v4-context-map-v2`, analysis-only set, owner union, and doc headings. |
| `tests/architecture/test_v4_architecture_invariants.py` | 120-234 | Pins runner/wire/metric values, flag ownership, flag-reference allowlist, magic-actor tokens, and V4 authority. |
| `tests/unit/test_runner_config_v4_flags.py` | 72-108 | Pins digest, field order, and "all flags unimplemented". |
| `tests/unit/test_runner_config_v56.py` | 127-283 | Pins acceptance, exact 12 keys, and fail-closed construction for every flag. |
| `tests/unit/test_v4_scaffolding_gate.py` | 80-131 | Pins scaffolding-profile rejection and construction failure for every enabled V4 flag. |
| `docs/v4-architecture.md` | `### organizations` section | Must keep exactly 14 `### ` context headings; edit only the body. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/runner_models.py` | modify | Add `"organizations"` to `_V4_OWNED_CAPABILITY_FLAGS`; update the comment. |
| `src/simulation/v4_architecture.py` | modify | Expand only the `organizations` `existing_mechanism` description to name the V3 institutional primitives; keep authority, owners, prerequisites, count, order, and non-goals unchanged. |
| `src/simulation/compatibility.py` | modify | Set `V4_OWNED_CAPABILITY_FLAGS = frozenset({"organizations"})`; update the `runner-config-v56` and `v4_capability_flags` bump text so exactly one flag is owned and eleven remain unowned. |
| `src/agents/cognition/organization_concepts.py` | create | Closed enums, ID grammar, policy, caps, error type, and validation primitives. No formation logic yet. |
| `src/agents/cognition/__init__.py` | modify | Export the new public contract symbols through the package facade. |
| `docs/v4-architecture.md` | modify | State that `organizations` is owned by V4-03 on v56, remains owner-scoped, and adds no actor/registry/treasury. Do not add a `###` heading. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Split the ownership assertion: `organizations` owned; the other eleven unimplemented. |
| `tests/unit/test_runner_config_v4_flags.py` | modify | Split the per-flag ownership expectation and keep the exact digest/field-order pins. |
| `tests/unit/test_runner_config_v56.py` | modify | Keep `v57` unsupported; split owned/unowned construction expectations; keep the matrix finalize rejection of enabled V4 flags. |
| `tests/unit/test_v4_scaffolding_gate.py` | modify | Keep the scaffolding profile rejecting every enabled V4 flag; split the construction test. |
| `tests/unit/test_organization_contract.py` | create | Contract tests for Task 2. |

## Task 1: Own the organizations context on runner-config-v56

### Intent

`V4-01` declared `organizations` but owned no V4 flag. V4-03 must make
`organizations` the one owned flag while every other V4 flag continues to fail
closed. This task is the ownership gate; it adds no organization behavior.

### Implementation Steps

1. In `src/simulation/runner_models.py`, replace
   `_V4_OWNED_CAPABILITY_FLAGS: Final[frozenset[str]] = frozenset()` with
   `frozenset({"organizations"})` and replace the comment with one that names
   V4-03 as the owner and states that the remaining eleven flags stay unowned.
2. In `src/simulation/compatibility.py`, set
   `V4_OWNED_CAPABILITY_FLAGS = frozenset({"organizations"})`. Update the
   `runner-config-v56` bump text and the `v4_capability_flags` entry text so they
   say `organizations` is owned on v56 and the other eleven flags fail closed at
   `stage="v4_capability_flags"`.
3. Expand only the `organizations` `existing_mechanism` string in
   `src/simulation/v4_architecture.py` to
   `"collective_projects, public_goods, mentorship, institution_concepts, offices, institutional_memory, collective_decisions, structured_commitments, group_formation"`.
   Do **not** change its authority, owner packages, prerequisites, non-goals,
   position, or the 14-context/12-flag counts. Do **not** change
   `src/simulation/versioning.py`, `src/simulation/migration_plan.py`, or
   `src/simulation/runner.py`.
4. Confirm `SimulationRunner.from_config` now passes the V4 gate when
   `organizations` is enabled, while `v4_unimplemented` still contains the other
   eleven flags. The ownership check is data-driven; do not add a special case.
5. In `docs/v4-architecture.md`, replace the `organizations` body with the owned
   statement. Preserve every `### ` heading and the 11 required sections.
6. Update the four test files listed above:
   - `test_v4_architecture_invariants.py`: for each flag, expect
     `owned_enabled_names() == ("organizations",)` and
     `unimplemented_enabled_names() == ()` for `organizations`; for every other
     flag expect the inverse.
   - `test_runner_config_v4_flags.py`: same split.
   - `test_runner_config_v56.py`: `organizations` constructs; every other flag
     raises `RunnerConstructionError(code="capability_unimplemented",
     stage="v4_capability_flags")`. Keep `runner-config-v57` absent from
     `SUPPORTED_RUNNER_SCHEMA_VERSIONS` and keep the matrix finalize rejection.
   - `test_v4_scaffolding_gate.py`: the `v4_scaffolding_profile` still rejects
     any enabled V4 flag, including `organizations`; the construction split
     matches the runner test.
7. Add `tests/unit/test_organization_gate.py` with:
   - `V4CapabilityFlags(organizations=True).owned_enabled_names() == ("organizations",)`;
   - `unimplemented_enabled_names() == ()`;
   - `V4CapabilityFlags(organizations=True).any_enabled() is True`;
   - enabling `organizations` on `runner-config-v4` or `runner-config-v55`
     raises `v4_capability_requires_v56`;
   - no `"v4_capability_flags"` literal appears in `organization_*` modules,
     except in the existing allowlisted files.

### Required Interfaces and Contracts

- `_V4_OWNED_CAPABILITY_FLAGS == frozenset({"organizations"})`.
- `V4_OWNED_CAPABILITY_FLAGS == frozenset({"organizations"})`.
- `V4CapabilityFlags` keeps exactly twelve boolean fields in the declared order.
- `RUNNER_SCHEMA_VERSION_V56 == "runner-config-v56"` remains accepted-only.
- `RUNNER_SCHEMA_VERSION_V57` must not exist and `"runner-config-v57"` must not be
  in `SUPPORTED_RUNNER_SCHEMA_VERSIONS`.
- `V4_EVENT_REUSING_CONTEXTS` still contains `ORGANIZATIONS`; no reservation is
  added.
- `observer_capability_payload()` still advertises the same four capabilities and
  reserves `organization_rows`; `/version` is unchanged.

### Requirement Evidence

- Original request: "An Organization must not receive an independent omniscient
  cognition engine"; this task owns only a flag and a registry entry.
- `.ai-factory/ARCHITECTURE.md` "Capability ownership": owned flags may enable;
  unowned flags fail closed.
- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract": accepted-set and
  exact-key-set evolution; no silent widening.
- `src/simulation/v4_architecture.py` `ORGANIZATIONS`: owner-scoped,
  existing-events, no global actor/registry, no automatic pool/treasury.

### Error Handling and Logging

- No new logging in this task.
- Existing `runner_construction_v4_capability_unimplemented` remains the ERROR
  path for the eleven unowned flags and must not log flag values.
- Invalid schema/flag combinations keep the existing safe `ValueError` codes.

### Tests

- `uv run pytest tests/unit/test_organization_gate.py -q`
- `uv run pytest tests/unit/test_runner_config_v4_flags.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py -q`
- `uv run pytest tests/architecture/test_v4_context_registry.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected: all pass; no `runner-config-v57` reference; `/version` tests unchanged.

### Acceptance Criteria

- `organizations` is owned; all other V4 flags remain unowned and fail closed.
- No new runner schema, event, codec, command, observer capability, migration, or
  API route exists.
- Registry validation still passes at 14 contexts and 12 flags.

### Verification

- `uv run python -c "from simulation.runner_models import V4CapabilityFlags; f=V4CapabilityFlags(organizations=True); print(f.owned_enabled_names(), f.unimplemented_enabled_names())"`
- Expected: `('organizations',) ()`
- `uv run python -c "from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS as v; print('runner-config-v56' in v, 'runner-config-v57' in v)"`
- Expected: `True False`

## Task 2: Freeze the closed organization contract

### Intent

Every later phase must use one vocabulary. This task fixes the owner-scoped
enums, ID grammar, locked policy, caps, and error codes before any ledger or
analysis code exists. It deliberately contains no formation logic and no world
imports.

### Implementation Steps

1. Create `src/agents/cognition/organization_concepts.py` with a module docstring
   that states: owner-scoped belief only; no objective organization entity,
   roster, treasury, registry, command, or permission; all activity remains
   agents, records, roles, and recognized procedures.
2. Define `ORGANIZATION_CONCEPT_POLICY_VERSION = "organization-concepts.v1"`,
   `ORGANIZATION_CONCEPT_ID_PREFIX = "orgc-"`, and `_ID_HEX_LEN = 16`.
3. Define the closed enums:
   - `OrganizationStatus`: `candidate`, `recognized`, `disputed`, `dissolved`,
     `retired`.
   - `OrganizationMembershipStatus`: `explicit`, `perceived`, `disputed`,
     `unknown`, `former`.
   - `OrganizationTemporalScope`: `ongoing`, `temporary`, `unknown`.
   - `OrganizationEvidenceChannel`: `observed`, `communicated`, `remembered`,
     `recorded`.
   - `OrganizationMembershipBasis`: `self_identification`, `participation`,
     `role_occupancy`, `collective_participation`, `communicated_claim`,
     `record_reference`, `inference`.
   - `OrganizationIdentityStance`: `member`, `affiliated`, `outside`, `unknown`.
   - `OrganizationConceptualization`: `none`, `named_usual`, `named_custom`.
   - `OrganizationGoalKind`: `collective_project`, `public_good`,
     `resource_allocation`, `migration`, `shared_defense`, `storage`,
     `norm_enforcement`, `unknown`.
   - `OrganizationResourceKind`: `repository`, `artifact`, `stored_resource`,
     `shelter`, `territory`, `unknown`.
   - `OrganizationProcedureKind`: `institution_concept`,
     `social_convention`, `unknown`.
   - `OrganizationRecordKind`: `artifact`, `repository`, `unknown`.
   - `OrganizationCommitmentRole`: `debtor`, `creditor`.
   - `OrganizationRevisionKind`: `membership_revised`, `role_revised`,
     `goal_revised`, `resource_revised`, `procedure_revised`, `record_revised`,
     `commitment_revised`, `identity_revised`, `continued`, `split`, `merged`,
     `dissolved`, `revived`.
   - `OrganizationLineageKind`: `continued`, `transformed`, `split`, `merge`,
     `dissolved`, `emerged`.
4. Define `OrganizationConceptError(ValueError)` whose messages are stable codes
   only. Reserve these codes:
   `organization_invalid_owner`, `organization_invalid_id`,
   `organization_invalid_status`, `organization_invalid_member`,
   `organization_duplicate_member`, `organization_unknown_anchor`,
   `organization_tick_regression`, `organization_cap_exceeded`,
   `organization_foreign_ledger`, `organization_forbidden_label`,
   `organization_invalid_temporal_scope`, `organization_invalid_lineage`,
   `organization_lineage_cycle`, `organization_policy_mismatch`.
5. Define `FORBIDDEN_ORGANIZATION_LABEL_TOKENS` as a frozen set containing at
   least: `government`, `church`, `corporation`, `army`, `university`, `guild`,
   `state`, `nation`, `polity`, `empire`, `tribe`, `treasury`, `bank`, `court`,
   `police`, `party`, `religion`, `ministry`, `department`, `firm`, `company`.
   These are forbidden as stored organization type/label tokens. Agents may use
   ordinary private words in speech; the ledger stores only opaque bounded label
   tokens, never these hard-coded classes.
6. Define `OrganizationConceptPolicy` (frozen, slots) with locked values:
   `max_concepts=16`, `max_members=32`, `max_roles=16`, `max_goals=16`,
   `max_resources=16`, `max_procedures=16`, `max_records=16`,
   `max_commitments=16`, `max_identities=8`, `max_evidence=64`,
   `max_snapshots=64`, `max_revisions=32`, `max_lineage=32`,
   `recognition_min_members=2`, `recognition_min_channels=2`,
   `recognition_min_evidence=3`, `recognition_floor=0.45`,
   `retire_floor=0.12`, `window_ticks=100`, `temporary_default_ticks=16`,
   `merge_jaccard=0.5`, `split_containment=0.4`.
   `__post_init__` rejects any deviation with `organization_policy_mismatch`.
   Provide `default_organization_concept_policy()`.
7. Define helpers `organization_concept_id(owner_id, creation_tick,
   founding_member_ids, structural_anchors)` and
   `organization_lineage_id(...)`. Both use SHA-256 over a UTF-8 namespace and
   sorted, delimiter-joined material; the concept id is `orgc-` plus the first
   16 hex characters. No `hash()`, UUID, wall-clock, or mutable counter.
8. Export the contract through `src/agents/cognition/__init__.py`.
9. Add `tests/unit/test_organization_contract.py` with:
   - every enum's exact member set and order-independent lookup;
   - ID stability for permuted members/anchors and sensitivity to creation tick;
   - policy exact values and rejection of a mutated policy;
   - forbidden-label rejection;
   - error tokens are stable and contain no payload text;
   - the module imports only stdlib and `agents.cognition` contract modules; it
     does not import `world`, `simulation`, `analysis`, or `experiments`.

### Required Interfaces and Contracts

```python
ORGANIZATION_CONCEPT_POLICY_VERSION: Final[str] = "organization-concepts.v1"
ORGANIZATION_CONCEPT_ID_PREFIX: Final[str] = "orgc-"
ORGANIZATION_ANALYTICAL_ID_PREFIX: Final[str] = "org-"
ORGANIZATION_PUBLICATION_ID_PREFIX: Final[str] = "org-edge-"

def organization_concept_id(
    owner_id: str,
    creation_tick: int,
    founding_member_ids: Sequence[str],
    structural_anchors: Sequence[str],
) -> str: ...

def organization_lineage_id(
    owner_id: str,
    kind: str,
    tick: int,
    from_ids: Sequence[str],
    to_ids: Sequence[str],
) -> str: ...
```

- Concept ids match `^orgc-[0-9a-f]{16}$`.
- Analytical ids match `^org-[0-9a-f]{16}$`.
- Publication ids match `^org-edge-[0-9a-f]{16}$`.
- `creation_tick` is a non-negative exact `int` (reject `bool`).
- Founding member ids and anchors are non-empty, unique, sorted before hashing.
- A concept id is never derived from current membership alone; it is minted once
  from creation evidence and inherited on continuation.

### Requirement Evidence

- Original request: "Do NOT create hard-coded classes such as Government, Church,
  Corporation, Army, University, Guild"; "Organizations must be general enough
  that different structures emerge from the same low-level mechanics."
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1 and 2: separate authorities;
  deterministic seeds/IDs, no `hash()`, UUID, or wall-clock.
- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract": frozen/defensive
  contracts and fail-closed validation.
- `.ai-factory/rules/base.md`: fail-closed validation; package facades.

### Error Handling and Logging

- Invalid input raises `OrganizationConceptError` with one stable code; never
  include owner ids, member ids, labels, or raw evidence in the message.
- No logging in the contract module. Later callers log counts and codes only.
- Policy violations are programming errors and fail closed at construction.

### Tests

- `uv run pytest tests/unit/test_organization_contract.py -q`
- `uv run python -c "from agents.cognition import OrganizationConceptPolicy; print(OrganizationConceptPolicy().window_ticks)"`
- Expected: `100`

### Acceptance Criteria

- The contract is closed, deterministic, and free of hard-coded organization
  classes.
- Three distinct ID grammars exist for owner-local, analytical, and publication
  identities.
- No world, simulation, analysis, or experiment import exists in the contract
  module.

### Verification

- `uv run ruff check src/agents/cognition/organization_concepts.py tests/unit/test_organization_contract.py`
- `uv run mypy src/agents/cognition/organization_concepts.py`
- Expected: clean.

## Phase Risks and Mitigations

- Risk: ownership changes accidentally make every V4 flag pass the gate.
  Mitigation: the ownership set contains exactly `{"organizations"}`; tests assert
  the other eleven still fail closed.
- Risk: a new runner version is introduced to carry organization config.
  Mitigation: Task 1 explicitly forbids `v57`; Task 6 threads the existing v56
  flag into cognition configuration without new runner keys.
- Risk: the closed vocabulary drifts between cognition and analysis.
  Mitigation: Task 2 fixes the strings; Task 10 duplicates the analytical enums
  and asserts parity.
- Risk: forbidden hard-coded classes leak in through label tokens.
  Mitigation: the forbidden-token set and test are part of the contract.

## Phase Completion Checklist

- Every Task 1-2 acceptance criterion is met.
- Ownership tests and contract tests pass.
- No `runner-config-v57`, event 23, codec `v21`, migration `0018`, command, or
  observer semantic type was added.
- `index.md` checkboxes are updated immediately after verified completion.
