# Phase 2: Exact opt-in configuration

Plan: [index.md](index.md)
Tasks: 3–4
Depends on: Tasks 1–2

## Objective
Introduce one default-off per-agent mode without claiming a capability flag or widening historical wire schemas.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/simulation/runner_models.py` | `MediationMode`, `AgentCognitionSpec`, `SimulationRunnerConfig.__post_init__` (10412+) | Latest mode-on validation is currently v52-specific. |
| `src/simulation/runner_serialization.py` | `_COGNITION_KEYS_V52` (517), `_v52_family_root_keys` (4528), `_encode_runner_document`, `decode_runner_config` | Mode-only root families, exact cognition keys and many explicit accepted-version sets. |
| `src/agents/cognition/configuration.py` | `CognitionLoopConfig`, mode translation/factory patterns | Cognition does not import runner-owned enums. |
| `tests/unit/test_runner_config_v52.py` | strict round trip, mixed owners, malformed-key tests | Preserve legacy behavior and extend accepted combinations explicitly. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/runner_models.py` | modify | v53 constant, supported set, mode, per-owner validation. |
| `src/simulation/new_agent_initialization.py` | modify in Task 9 | Explicit empty learner profile; Task 3 reserves its version-gate contract without importing a not-yet-created symbol. |
| `src/simulation/runner_serialization.py` | modify | v53 exact keys, family selection, codecs and fingerprinting. |
| `src/simulation/compatibility.py` | modify | Describe accepted runner v53 and unchanged other surfaces. |
| `src/simulation/__init__.py` | modify | Public version/mode exports consistent with existing facade. |
| `src/agents/cognition/configuration.py` | modify | Cognition-local mode, locked policy, factory and fingerprint. |
| `src/agents/cognition/loop.py` | modify | Constructor field/default only in this phase. |
| `src/simulation/runner.py` | modify | Runner-to-cognition mode mapping in `_cognition_config_for`. |
| `tests/unit/test_runner_config_v53.py` | create | All allowed and rejected schema/mode combinations. |

## Task 3: Add runner-config-v53 without changing old keysets

### Intent
Institutional memory is a cognition mode, not ownership of `institutional_economy`.

### Implementation Steps
1. Add `InstitutionalMemoryMode(DISABLED, DETERMINISTIC)`, `AgentCognitionSpec.institutional_memory_mode=DISABLED`, and `RUNNER_SCHEMA_VERSION_V53`. Extend the supported runner set and deliberate public exports.
2. Deterministic institutional memory is accepted only in v53, and v53 requires at least one deterministic institutional-memory owner. For each enabled owner require its own deterministic `office_succession_mode` or `institution_concept_mode`; another agent's mode does not satisfy the dependency. No recognized content is required at configuration time.
3. v53 cognition keys equal exactly `_COGNITION_KEYS_V52 ∪ {institutional_memory_mode}`. All agents in a v53 document include that key, including disabled owners. Historical schemas omit/reject it. `_v53_family_root_keys(data)` delegates to the existing v52 family without adding a root sibling.
4. Extend every relevant explicit accepted-version set, encode branch, decode wire-version preservation branch, lower-family normalization and nested cognition schema selection to v53. Audit occurrences of `RUNNER_SCHEMA_VERSION_V52` in these two named files; do not blindly replace every equality.
5. Earlier mode enablement gates must accept v53 as an additive higher version; specifically mediation-on accepts v52 or v53, but v52 still requires mediation. Preserve v49/v50/v51/v52 historical requirements, roots and exact keys. Keep dependencies of records/repositories/lifecycle/contact exactly as before.
6. Encoding retains the supplied validated config schema; do not auto-promote legacy all-off configs or introduce a global highest-version default. Default remains v4. Keep fingerprints deterministic and include mode only in its correct versioned surface.
7. Record compatibility taxonomy: no new event, codec, command, observer semantic, protocol or SQL migration. Existing enabled objective channels still choose their existing write pairs; never force replay-v22/v20 universally.
8. Audit both initialization-profile gates in `runner_models.py` (current office-profile guards near 7160 and 9126), not only initial-agent mode checks. Accept the existing office profile on v53 without changing its content. Task 9 adds the new explicit `species_default_institutional_memory_v1` profile and its v53-only validation in the same commit as its registry definition; until then no production import of that future constant is added. The new profile will require lifecycle/admission prerequisites already enforced by its chosen lower-family root and at least one enabled initial institutional-memory owner, just like other v53 runs. Preserve old profile behavior and reject the new identifier on v52 and older with `institutional_memory_profile_requires_v53`.

### Required Interfaces and Contracts
Error codes: `institutional_memory_requires_v53`, `v53_requires_institutional_memory`, `institutional_memory_requires_local_role_or_procedure`. Exact type checking rejects runner/cognition enum confusion. `institutional_economy` and `multi_hop_testimony_tracking` remain fail-closed.

### Requirement Evidence
Index reconciliation combinations C1–C4, C11. `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract and capability ownership.

### Error Handling and Logging
Use existing `RunnerSerializationError` path/code reporting without values. Mode validation logs field path, schema and safe reason code. No payload dump or fingerprint logging.

### Tests
Test v53 role-only, procedure-only, both modes, mixed owners, optional artifact/teaching channels, composition with mediation/decisions/narratives/regions, the existing office initialization profile on v53, exact keys, enum failures, enabled-on-old-schema rejection, all-off-v53 rejection, missing local dependency, unowned flag rejection. Task 9 adds the new profile's round-trip/rejection cases when its definition exists. Re-encode representative existing BF/BI configs and legacy golden fixtures unchanged.

### Acceptance Criteria
v53 round-trips/fingerprints; v4 default and all previously accepted schemas preserve their wire contract; v52 mediation still runs.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v53.py tests/unit/test_runner_config_v52.py tests/unit/test_compatibility_matrix.py --cov=simulation --cov-report=term -q`

## Task 4: Add cognition-local configuration and composition

### Intent
Keep dependency direction correct and mode-off execution identical.

### Implementation Steps
1. Add `CognitionInstitutionalMemoryMode` to `configuration.py`; extend `CognitionLoopConfig` with mode and policy. Disabled resolves policy to `None`; deterministic resolves exactly `default_institutional_memory_policy()`. Reject custom policy versions/weights rather than adding user-tunable behavior in this plan.
2. Extend `condition_fingerprint_material()` and factory constructor forwarding using the same mode/policy-version pattern as mediation, with one explicit compatibility rule: add the new mode/policy keys only when institutional memory is enabled. Disabled always returns exactly the pre-feature material; add a test pinning that old default material.
3. Add constructor slot and default to `CognitiveLoop`, with no update call when disabled. `_cognition_config_for` translates runner enum by value into the cognition enum and emits a safe configuration metadata event.
4. Do not auto-enable artifact interpretation, teaching, offices, institutions, skill learning or cultural flags. The caller supplies permitted combinations. Missing optional channels reduce opportunities rather than creating hidden dependencies.

### Required Interfaces and Contracts
`CognitionLoopConfig.institutional_memory_mode`, `institutional_memory_policy`; `CognitiveLoop(..., institutional_memory_mode=DISABLED, institutional_memory_policy=None)`. Imports flow runner → cognition; cognition never imports `simulation`.

### Requirement Evidence
Index C1–C4 and C7; architecture default-off invariance and inward dependencies.

### Error Handling and Logging
Wrong enum and policy versions fail before runner construction. `cognition_config_institutional_memory` logs mode/policy version only. Disabled calls no policy or frame parser.

### Tests
Extend v53 tests for direct cognition config, cross-enum rejection, locked policy, constructor forwarding, default fingerprint parity, and spies proving disabled parsing/preparation never runs.

### Acceptance Criteria
Direct and runner-composed loops agree on mode and locked policy; disabled behavior has no new ledger, audit or command bias.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v53.py tests/unit/test_v1_regression_gate.py --cov=simulation --cov=agents.cognition --cov-report=term -q`

## Phase Risks and Mitigations
- Explicit version allowlists are numerous. Mitigation: targeted symbol audit plus round trips of lower-family compositions; no mass search/replace.
- Mode enablement is not recognition. Mitigation: enabled-but-empty ledgers are valid and expected.

## Phase Completion Checklist
- Verify Tasks 3–4, then update only index checkboxes.
- Commit checkpoint 1 is after Tasks 1–4, not before strict configuration checks pass.
