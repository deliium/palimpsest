# Phase 1: Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Freeze the formal-rule vocabulary, identity grammar, and limits; make
`formal_rules` the second owned V4 capability flag on the existing
`runner-config-v56` seam; and add a default-disabled cognition mode and policy
without changing runner config, commands, events, or the organization stack.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `V4ContextId.FORMAL_RULES` 64; spec 122-135; `validate_v4_contexts` 361-411 | The context is already declared as owner-scoped, event-reusing, no prerequisite, with non-goals "no world-law object" and "no automatic sanction or policy engine". |
| `src/simulation/runner_models.py` | `_V4_CAPABILITY_FLAG_NAMES` 305-318; `_V4_OWNED_CAPABILITY_FLAGS` 320-323; `V4CapabilityFlags` 1112-1160; v56 gate 7919-7931 | Ownership is a single runtime pin; the flag name and v56 requirement already exist. |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 155; bump text 525-529, 762-769 | Duplicate ownership pin and human-readable compatibility notes. |
| `src/simulation/runner.py` | `_cognition_config_for` 1005-1012; validation 2130-2204; config call sites 2610-2616, 6606-6612 | The runner derives cognition modes from V4 flags and rejects unowned flags before construction. |
| `src/agents/cognition/configuration.py` | `CognitionOrganizationMode` 392-400; fields 590-603; normalization 1070-1132; fingerprint 1440-1455 | Pattern for a default-disabled cognition mode and optional policy. |
| `src/agents/cognition/social_norms.py` | policy 29; enums 87-146; ledger 608; policy 677-751 | Vocabulary and policy conventions to mirror. |
| `src/agents/cognition/organization_concepts.py` | id grammar 30-47; policy 256-324; error codes 192-252 | Exact id/error/policy pattern to mirror. |
| `tests/architecture/test_v4_architecture_invariants.py` | ownership test 155-177; allowed flag references 80-89 | Must be updated because two flags are now owned. |
| `tests/unit/test_v4_scaffolding_gate.py` | unowned gate 112-129; owned organizations 132-145 | Mirrors the fail-closed and owned-construction contract. |
| `tests/unit/test_runner_config_v56.py` | exact keys 181; unowned param 249-282; owned 285-299 | Must keep the 12-key sibling exact while changing ownership. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/formal_rules.py` | create | Policy version, enums, id grammar, limits, error class, default policy. |
| `src/simulation/runner_models.py` | modify | Add `formal_rules` to `_V4_OWNED_CAPABILITY_FLAGS`. |
| `src/simulation/compatibility.py` | modify | Add `formal_rules` to `V4_OWNED_CAPABILITY_FLAGS`; update bump text. |
| `src/agents/cognition/configuration.py` | modify | Add `CognitionFormalRuleMode`, fields, normalization, fingerprint. |
| `src/simulation/runner.py` | modify | Accept and forward `formal_rules_enabled`; pass the flag at both call sites. |
| `tests/unit/test_formal_rule_contracts.py` | create | Vocabulary, id, policy, and limit tests. |
| `tests/unit/test_formal_rule_config.py` | create | Mode/policy seam and disabled-default tests. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Two owned flags; keep 14 contexts / 12 flags / `v4-context-map-v2`. |
| `tests/unit/test_v4_scaffolding_gate.py` | modify | Remove `formal_rules` from the unowned parameterization; add owned construction. |
| `tests/unit/test_runner_config_v56.py` | modify | Move `formal_rules` from the unowned parameterization to the owned construction test. |
| `tests/unit/test_runner_config_v4_flags.py` | modify | Keep the 12-name closed set; assert the two-flag owned split. |
| `tests/architecture/test_organization_boundaries.py` | modify | Ownership split assertion only; no organization behavior change. |

## Task 1: Freeze the formal-rule vocabulary, stages, and identity grammar

### Intent

Create the single domain module that later phases extend. A smaller implementer
must not invent stage names, id prefixes, or limits while writing the ledger.

### Implementation Steps

1. Create `src/agents/cognition/formal_rules.py` with a module docstring stating:
   a rule is one owner's belief about a socially recognized constraint; it is
   not a world law, admission rule, permission, or enforcement engine.
2. Define `FORMAL_RULE_POLICY_VERSION: Final[str] = "formal-rules.v1"`.
3. Define `FORMAL_RULE_ID_HEX_LEN: Final[int] = 16` and these prefixes:
   `frs-` system, `frl-` rule, `frv-` version, `fre-` evidence, `frp-`
   position, `frr-` response, `frx-` exception.
4. Define digest namespaces exactly:
   `formal-rule-system`, `formal-rule`, `formal-rule-version`,
   `formal-rule-evidence`, `formal-rule-position`, `formal-rule-response`,
   `formal-rule-exception`.
5. Define anchored regexes and `require_*` validators for every prefix. Reject
   uppercase, non-hex, wrong length, and foreign prefixes with
   `FormalRuleError("formal_rule_invalid_id")`.
6. Define closed enums exactly:
   - `FormalRuleStage`: `habit`, `expectation`, `norm`, `documented`,
     `recognized_enforcement`.
   - `FormalRuleConstraintKind`: `prohibition`, `obligation`, `permission`.
   - `FormalRuleScopeKind`: `person`, `place`, `resource`, `action`,
     `collective`, `unspecified`.
   - `FormalRuleAuthorityKind`: `self`, `office`, `organization`,
     `collective_decision`, `procedure`, `written_record`, `custom`, `unknown`.
   - `FormalRuleRecognition`: `unrecognized`, `claimed`, `recognized`,
     `contested`.
   - `FormalRuleStatus`: `candidate`, `active`, `contested`, `superseded`,
     `retired`.
   - `FormalRulePositionStance`: `proponent`, `supporter`, `opponent`,
     `challenger`, `reinterpreter`, `amender`, `withdrawer`.
   - `FormalRuleResponseKind`: `follow`, `violate`, `challenge`, `reinterpret`,
     `ignore`.
   - `FormalRuleEvidenceChannel`: `observed`, `communicated`, `remembered`,
     `recorded`, `derived`.
   - `FormalRuleSanctionKind`: `criticism`, `refusal`, `reduced_trust`,
     `retaliation`, `exclusion`, `restitution`.
   - `FormalRuleReportKind`: `compliance`, `violation`, `exemption`,
     `enforcement`.
   - `FormalRuleRepresentationStatus`: `intact`, `damaged`, `missing`,
     `unknown`.
   - `FormalRuleProvenance`: `self_authored`, `communicated`,
     `derived_from_norm`, `derived_from_convention`, `derived_from_record`,
     `authority_recognized`, `observed_effect`, `contested`, `unrecognized`,
     `expired`, `orphaned`, `unknown`.
7. Define `FORMAL_RULE_ERROR_CODES` and `FormalRuleError` with a safe `.code`.
8. Define frozen `FormalRulePolicy` with locked values:
   `max_systems=8`, `max_rules=32`, `max_versions_per_rule=16`,
   `max_evidence_per_rule=64`, `max_positions_per_rule=64`,
   `max_responses_per_rule=64`, `max_exceptions_per_rule=8`,
   `max_sanctions_per_rule=8`, `max_scope_anchors=8`,
   `max_total_records=512`, `min_supporters_for_recognition=2`,
   `min_enforcement_recurrence=2`, `version_window_ticks=64`,
   `max_frame_chars=384`, `max_relations=32`.
9. Add `FORMAL_RULE_FORBIDDEN_FIELD_NAMES` covering at least: `law`,
   `statute`, `legal_code`, `court`, `judge`, `police`, `government`,
   `jurisdiction`, `sovereign`, `rule_engine`, `sanction_engine`,
   `policy_engine`, `enforced_by_world`, `physical_law`, `objective_rule`,
   `global_rule_registry`, `current_law`, `binding_rule`.
10. Add content-addressed minters using canonical JSON + SHA-256 and the
    namespaces above. `formal_rule_id` hashes owner id, system id, constraint
    kind, action token, and scope digest; it must not hash a label or evidence
    ordinal.
11. Add `formal_rule_scope_digest(kind, anchor_ids)` that sorts and deduplicates
    anchors, rejects more than `max_scope_anchors`, and returns 64 hex chars.

### Required Interfaces and Contracts

```python
FORMAL_RULE_POLICY_VERSION: Final[str] = "formal-rules.v1"

def formal_rule_system_id(owner_id: str, scope_digest: str, authority: str) -> str: ...
def formal_rule_id(owner_id: str, system_id: str, constraint: str, action: str, scope_digest: str) -> str: ...
def formal_rule_version_id(rule_id: str, version_number: int, content_digest: str) -> str: ...
def formal_rule_evidence_id(rule_id: str, ordinal: int, channel: str, lineage_ref: str) -> str: ...
def formal_rule_position_id(rule_id: str, actor_id: str, stance: str, ordinal: int) -> str: ...
def formal_rule_response_id(rule_id: str, actor_id: str, kind: str, tick: int) -> str: ...
def formal_rule_exception_id(rule_id: str, ordinal: int, condition_digest: str) -> str: ...
def require_formal_rule_policy(policy: object | None) -> FormalRulePolicy: ...
def default_formal_rule_policy() -> FormalRulePolicy: ...
```

Compatibility invariants:

- Enum values are stable API identifiers; never rename them in a later phase.
- `FormalRuleConstraintKind` has no physical member. Physical impossibility is
  not representable as a rule constraint.
- All minters are deterministic and owner-scoped. No `hash()`, UUID, wall clock,
  or global random source.
- The policy object is frozen and `__post_init__` refuses non-locked values with
  `formal_rule_policy_not_locked`.

### Requirement Evidence

- Original Request: progression, scope, proponents, authority, written
  representation, sanction, exceptions, versions, responses, competing systems.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-6 and "Important V3 seams".
- `src/simulation/v4_architecture.py` 122-135: owner-scoped authority and the two
  non-goals.
- `src/agents/cognition/organization_concepts.py` 30-47, 192-324: id, error, and
  policy pattern.
- `src/agents/cognition/social_norms.py` 87-146: closed stage/response/sanction
  vocabulary precedent.

### Error Handling and Logging

- Invalid ids raise `FormalRuleError("formal_rule_invalid_id")`.
- Invalid enum values raise `FormalRuleError("formal_rule_invalid_mode")`.
- Locked-policy violations raise `FormalRuleError("formal_rule_policy_not_locked")`.
- Scope overflows raise `FormalRuleError("formal_rule_scope_limit")`.
- DEBUG: `formal_rule_contract_validated name=%s count=%s` (enum name and count).
- Never log anchor ids, action tokens, scope contents, actor ids, or record
  bodies. INFO only on module-level policy construction (once per process).

### Tests

`tests/unit/test_formal_rule_contracts.py`:

- `test_policy_version_and_limits_are_locked`
- `test_every_id_prefix_round_trips_and_rejects_foreign_ids`
- `test_system_and_rule_ids_are_content_addressed_and_owner_scoped`
- `test_scope_digest_is_sorted_deduplicated_and_bounded`
- `test_constraint_vocabulary_has_no_physical_member`
- `test_forbidden_law_vocabulary_is_closed`
- `test_no_global_nondeterminism_imports`

Run: `uv run pytest tests/unit/test_formal_rule_contracts.py -q`.

### Acceptance Criteria

- At Task 1 completion, the module imports without `world`, `simulation`,
  `infrastructure`, `api`, `analysis`, or `persistence` dependencies. Later
  tasks may add only public `world`/`agents` contracts required by the records.
- Same inputs produce identical ids in two separate processes.
- No enum member or field name implies objective law or world enforcement.

### Verification

- `uv run pytest tests/unit/test_formal_rule_contracts.py -q`
- Expected: all tests pass; `ruff check src/agents/cognition/formal_rules.py`
  reports no issues.

## Task 2: Own the `formal_rules` capability flag without a runner schema change

### Intent

Flip the existing declared context from unowned/fail-closed to owned, exactly as
V4-03 did for `organizations`, while keeping the closed 12-flag vocabulary and
the single `runner-config-v56` seam.

### Implementation Steps

1. In `src/simulation/runner_models.py`, change
   `_V4_OWNED_CAPABILITY_FLAGS` to `frozenset({"organizations", "formal_rules"})`.
   Do not add a field, default, validator, or runner key.
2. In `src/simulation/compatibility.py`, change
   `V4_OWNED_CAPABILITY_FLAGS` to the same two-name frozenset and update the
   bump notes from "only organizations is owned / eleven unowned" to "two owned
   / ten unowned".
3. Keep `_V4_CAPABILITY_FLAG_NAMES` and `_V4_CAPABILITY_FLAG_KEYS` exactly the
   same 12 names in the same order. Do not add `formal_rules` a second time.
4. Update the ownership assertions only:
   - `tests/architecture/test_v4_architecture_invariants.py`:
     `test_context_registry_and_capability_ownership` expects
     `{"organizations", "formal_rules"}` and still 14 contexts / 12 flags.
   - `tests/unit/test_v4_scaffolding_gate.py`: remove `formal_rules` from
     `test_each_unowned_enabled_flag_fails_closed_at_construction`; add a
     parameterized owned-construction assertion mirroring the organizations test.
   - `tests/unit/test_runner_config_v56.py`: remove `formal_rules` from the
     unowned parameterization; add it to
     `test_owned_organizations_flag_constructs_after_encode_decode` (rename the
     test to cover both owned flags).
   - `tests/unit/test_runner_config_v4_flags.py`: assert the two-name owned split
     and keep the 12-name closed set.
   - `tests/architecture/test_organization_boundaries.py`: ownership split only.
5. If a new source file introduced in Task 3 mentions the literal
   `v4_capability_flags`, add that path to `ALLOWED_FLAG_REFERENCES` in
   `tests/architecture/test_v4_architecture_invariants.py` 80-89. Prefer reusing
   existing symbol imports to avoid widening the allowlist.
6. Keep `experiments.catalog` scaffolding profiles rejecting every enabled V4
   flag, including owned ones. Do not change `v4_scaffolding_profile`.
7. Do not touch `simulation.versioning`; `FORMAL_RULES` is already listed in
   `V4_EVENT_REUSING_CONTEXTS` and no reservation is added.

### Required Interfaces and Contracts

- `V4CapabilityFlags.formal_rules: bool = False` is unchanged.
- `unimplemented_enabled_names()` now excludes both owned flags.
- `owned_enabled_names()` returns enabled owned flags in closed-name order.
- Enabling `formal_rules` on v4/v55 still raises
  `ValueError("V4 capability flags require runner-config-v56 (code=v4_capability_requires_v56)")`.
- Enabling any of the ten unowned flags on v56 still raises
  `RunnerConstructionError(CAPABILITY_UNIMPLEMENTED, stage="v4_capability_flags")`.
- No `runner-config-v57` file, literal, or compatibility entry is added.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Capability ownership" and "V4-01 open-ended
  civilizations architecture seam".
- `src/simulation/v4_architecture.py` 122-135.
- `src/simulation/runner_models.py` 305-323, 1112-1160, 7919-7931.
- `src/simulation/runner.py` 2130-2204.
- `tests/unit/test_v4_scaffolding_gate.py` 92-145.

### Error Handling and Logging

- Construction failure keeps the existing safe code `capability_unimplemented`
  and stage `v4_capability_flags`; no flag values are logged.
- INFO once per construction:
  `runner_v4_owned_flags count=2` (count only).
- WARN when an unowned flag is enabled: existing safe log path only; never log
  the rest of the config.

### Tests

- `uv run pytest tests/unit/test_v4_scaffolding_gate.py tests/unit/test_runner_config_v56.py tests/unit/test_runner_config_v4_flags.py -q`
- `uv run pytest tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_organization_boundaries.py -q`

Expected: both owned flags construct on v56; all ten other flags fail closed;
14 contexts / 12 flags / `v4-context-map-v2` unchanged; no v57.

### Acceptance Criteria

- `formal_rules` is accepted only on a v56 config and never emitted as a default.
- `organizations` behavior and all organization tests remain unchanged.
- The 12-key `v4_capability_flags` sibling is byte-exact before and after.

### Verification

- `grep -R "runner-config-v57" -n src tests` → no matches outside existing
  negative assertions that pin the schema version's absence.
- `uv run pytest tests/unit/test_runner_config_v56.py -q` → all pass.

## Task 3: Add the cognition mode and policy seam

### Intent

Give the runner one deterministic per-agent switch and one policy object, gated
by the owned flag. Disabled mode must allocate nothing and leave every existing
trajectory unchanged.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`, add:

```python
class CognitionFormalRuleMode(StrEnum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
```

   Docstring: lockstep with `simulation.V4CapabilityFlags.formal_rules`; this is a
   cognition mode, not a capability flag.
2. Import `FormalRulePolicy` and `default_formal_rule_policy` from
   `agents.cognition.formal_rules` at the module boundary used by the other
   cognition policies. Add fields to `CognitionLoopConfig` next to the
   organization fields:
   `formal_rule_mode: CognitionFormalRuleMode = DISABLED` and
   `formal_rule_policy: FormalRulePolicy | None = None`.
3. Normalize in `__post_init__`: disabled forces policy to `None`; deterministic
   with `None` installs `default_formal_rule_policy()`; any other policy type
   raises `TypeError`.
4. Add the mode/policy to the config fingerprint in the existing sorted payload.
   Include the policy version, not its limits.
5. In `src/simulation/runner.py::_cognition_config_for`, import
   `CognitionFormalRuleMode`, `default_formal_rule_policy`, and
   `FORMAL_RULE_POLICY_VERSION` alongside the organization imports; add
   `formal_rules_enabled: bool = False`; derive the mode and policy; forward both
   fields. Pass `config.v4_capability_flags.formal_rules` at both call sites
   (2610-2616 and 6606-6612).
6. Do not create a ledger in this task. The mode is prepared by `loop.py` in
   Task 8.
7. Add `tests/unit/test_formal_rule_config.py` covering:
   - default config is disabled and allocates no policy;
   - deterministic mode installs the locked policy;
   - disabled normalizes a supplied policy to `None`;
   - a foreign policy type raises;
   - `_cognition_config_for(formal_rules_enabled=False)` yields disabled;
   - `_cognition_config_for(formal_rules_enabled=True)` yields deterministic;
   - fingerprints differ between modes and are stable within a mode.

### Required Interfaces and Contracts

- `CognitionFormalRuleMode` is internal to cognition and is not serialized into
  runner config or results.
- `formal_rule_policy.version == "formal-rules.v1"` whenever deterministic.
- Disabled mode must not construct `FormalRulePolicy`, allocate ids, or touch the
  observation.
- The runner still rejects `formal_rules` on non-v56 before reaching this seam.

### Requirement Evidence

- `src/agents/cognition/configuration.py` 392-400, 590-603, 1070-1095, 1440-1455.
- `src/simulation/runner.py` 1005-1012, 1316-1342, 1485-1488, 2610-2616,
  6606-6612.
- `src/simulation/v4_architecture.py` 128 (`required_config_seam`).

### Error Handling and Logging

- Invalid mode type raises `TypeError("formal_rule_mode must be
  CognitionFormalRuleMode")`.
- Disabled with a non-`None` policy normalizes silently; log at DEBUG only
  `cognition_formal_rule_policy_cleared`.
- INFO on deterministic mode:
  `cognition_formal_rule_mode mode=deterministic policy_version=formal-rules.v1`.
- Never log scope anchors, action tokens, or owner ids.

### Tests

- `uv run pytest tests/unit/test_formal_rule_config.py -q`
- `uv run pytest tests/unit/test_cognition_config.py tests/unit/test_runner_config_v56.py -q`
  (adjust the exact cognition config test path if the repository uses a
  different filename; keep the existing suite green).

### Acceptance Criteria

- A default run allocates no formal-rule mode or policy.
- Enabling the flag produces deterministic mode for every runtime without
  changing runner serialization.
- Existing cognition configuration tests stay green.

### Verification

- `uv run pytest tests/unit/test_formal_rule_config.py -q`
- `uv run mypy src/agents/cognition/configuration.py src/simulation/runner.py`
- Expected: both commands exit 0.

## Phase Risks and Mitigations

- Risk: adding `formal_rules` to the owned set accidentally changes the closed
  12-flag keyset.
  Mitigation: assert the exact keyset in `test_runner_config_v56.py` and never
  edit `_V4_CAPABILITY_FLAG_NAMES` or `_V4_CAPABILITY_FLAG_KEYS`.
- Risk: the duplicate ownership pin in `compatibility.py` drifts from
  `runner_models.py`.
  Mitigation: update both in the same task and add an equality assertion.
- Risk: a new module referencing the flag literal breaks the allowed-reference
  architecture test.
  Mitigation: reference `V4CapabilityFlags.formal_rules` through existing
  configuration plumbing and only widen `ALLOWED_FLAG_REFERENCES` if a concrete
  new literal is unavoidable.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
- No runner schema, command, event, write pair, migration, or organization
  contract changed.
