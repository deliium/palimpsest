# Phase 2: Capability and Runner Evolution

Plan: [index.md](index.md)
Tasks: 4-6
Depends on: Phase 1 (Tasks 1-3)

## Objective

Land the closed V4 capability vocabulary and a new accepted runner schema that
can carry it, without enabling any behavior. After this phase every V4 flag is
declared, serializable, and rejected at runtime construction.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/runner_models.py` | `_V2_CAPABILITY_FLAG_NAMES` (266), `_V3_CAPABILITY_FLAG_NAMES` (284), `_V3_OWNED_CAPABILITY_FLAGS` (293) | Exact pattern to mirror for V4. |
| `src/simulation/runner_models.py` | `V3CapabilityFlags` (1044-1085) | Frozen slots dataclass, `any_enabled`, `enabled_names`, `unimplemented_enabled_names`, `owned_enabled_names`. |
| `src/simulation/runner_models.py` | `RUNNER_SCHEMA_VERSION_V55` (149), `SUPPORTED_RUNNER_SCHEMA_VERSIONS` (151-209) | Accepted-set registration point. |
| `src/simulation/runner_models.py` | `SimulationRunnerConfig` fields (7440-7474), `__post_init__` v3 gate (9406-9458) | Where the V4 flags field and the `v4_capability_requires_v56` gate belong. |
| `src/simulation/runner_models.py` | `v3_capability_flags_digest` (11831) | Digest helper pattern. |
| `src/simulation/runner_serialization.py` | `_CAPABILITY_FLAG_KEYS` (5222), `_encode_v3_capability_flags` (5286), `_decode_v3_capability_flags` (5296) | Exact-key encoder/decoder pattern. |
| `src/simulation/runner_serialization.py` | `_encode_runner_document` (7417), `_v55_family_root_keys` (4751), `decode_runner_config` (9129) | Version-specific root-key and strict decode points. |
| `src/simulation/compatibility.py` | `V3_CAPABILITY_FLAGS_WIRE_KEY` (134), `V3_CAPABILITY_FLAG_NAMES` (143), matrix row `v3_capability_flags` (712), `_LOG.debug` extras (800) | Where the V4 wire key, public flag tuple, matrix row, and diagnostics are added. |
| `src/simulation/runner.py` | `from_config` rejection block (2085-2138), `CAPABILITY_UNIMPLEMENTED` (285) | Fail-closed gate to extend with `stage="v4_capability_flags"`. |
| `src/experiments/matrix_schema.py` | `finalize_matrix_cell_config` (70), highest-wins chain (152-320) | Explicit v56 identity must survive finalization; nothing auto-emits it. |
| `src/experiments/catalog.py` | `v3_scaffolding_profile` (1664), `v2_regression_profile` (1691) | Profile composition pattern. |
| `tests/unit/test_v3_scaffolding_gate.py` | fail-closed proof (55-89) | Exact gate-test shape to mirror. |
| `tests/architecture/test_path_dependence_boundaries.py` | line 90 asserts `"runner-config-v56" not in` source | Must be updated deliberately in Task 5. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/runner_models.py` | modify | V4 flag names/ownership/dataclass/digest/field/v56 constant/gates. |
| `src/simulation/runner_serialization.py` | modify | V4 flag encode/decode, v56 exact keyset, legacy synthesis. |
| `src/simulation/runner.py` | modify | V4 fail-closed construction gate. |
| `src/simulation/compatibility.py` | modify | Wire key, public flags, matrix row, runner bump prose, debug extras. |
| `src/simulation/__init__.py` | modify | Export new public names. |
| `src/experiments/matrix_schema.py` | modify | Preserve explicit v56; never auto-emit. |
| `src/experiments/catalog.py` | modify | `v4_scaffolding_profile`, `v3_regression_profile`. |
| `src/experiments/__init__.py` | modify | Profile exports and `__all__`. |
| `tests/unit/test_runner_config_v4_flags.py` | create | Flag contract, ownership, digest, registry parity. |
| `tests/unit/test_runner_config_v56.py` | create | Accepted set, round-trip, exact keys, legacy synthesis. |
| `tests/unit/test_v4_scaffolding_gate.py` | create | Profiles and fail-closed runtime gate. |
| `tests/unit/test_compatibility_matrix.py` | modify | Add `v4_capability_flags` to the required matrix taxonomy id set. |
| `tests/architecture/test_path_dependence_boundaries.py` | modify | Replace the v56-forbidden pin with the v57 guard. |
| `tests/architecture/test_v3_baseline_inventory.py` | modify | Record v56 as newly accepted while keeping default v4 / latest v55 baseline assertions. |

## Task 4: Add closed V4 capability flags

### Intent

Declare the complete V4 capability vocabulary exactly once, as a closed
default-off set. Every flag is unowned in V4-01, so enabling any of them must
fail at runtime construction instead of silently doing nothing.

### Implementation Steps

1. In `src/simulation/runner_models.py`, immediately after the V3 flag block,
   add `_V4_CAPABILITY_FLAG_NAMES: Final[tuple[str, ...]]` with these twelve
   names in this exact order:
   `organizations`, `formal_rules`, `legal_disputes`, `diplomacy`,
   `organized_conflict`, `infrastructure_networks`, `supply_chains`,
   `markets_credit`, `science`, `epidemics`, `ecological_feedback`, `disasters`.
   `societal_resilience` is a detached-analysis context and deliberately has no
   runner capability flag.
2. Add `_V4_OWNED_CAPABILITY_FLAGS: Final[frozenset[str]] = frozenset()` with a
   comment stating that V4-01 owns none and every flag fails closed until its
   behavior plan lands.
3. Add `@dataclass(frozen=True, slots=True) class V4CapabilityFlags` with the
   twelve boolean fields defaulting to `False`, a `__post_init__` that rejects
   non-bool values with `TypeError("V4CapabilityFlags.<name> must be bool")`, and
   methods `any_enabled()`, `enabled_names()`, `unimplemented_enabled_names()`,
   `owned_enabled_names()` mirroring `V3CapabilityFlags` exactly.
4. Add `V4_CAPABILITY_FLAG_NAMES` and `V4_CAPABILITY_FLAGS_WIRE_KEY =
   "v4_capability_flags"` in `src/simulation/compatibility.py`, plus a
   `"v4_capability_flags"` matrix entry:
   - `write_version=V4_CAPABILITY_FLAGS_WIRE_KEY`
   - `accepted_restore=_versions(*V4_CAPABILITY_FLAG_NAMES)`
   - `bump_trigger` states: closed reserved set, sibling of `capability_flags`
     and `v3_capability_flags`, all flags unowned in V4-01, any enabled flag
     fails closed at `SimulationRunner.from_config`.
   - `owner_package="simulation.runner_models / simulation.runner"`
   - `v1_fixture_impact` states: defaults off; legacy configs synthesize
     defaults; V1/V2/V3 identity unchanged when off.
5. Add `v4_capability_flags_digest(flags: V4CapabilityFlags) -> str` next to the
   V3 digest helper, using the same canonical encoding approach and a stable
   `"v4-capability-flags"` namespace.
6. Export `V4CapabilityFlags`, `V4_CAPABILITY_FLAG_NAMES`,
   `V4_CAPABILITY_FLAGS_WIRE_KEY`, and `v4_capability_flags_digest` through
   `src/simulation/__init__.py`, `src/simulation/compatibility.py::__all__`, and
   the facade style already used for V3.
7. Add `tests/unit/test_runner_config_v4_flags.py`:
   - `V4CapabilityFlags()` has `any_enabled() is False` and twelve names.
   - `tuple(spec.capability_flag for spec in V4_CONTEXTS if
     spec.capability_flag is not None) == V4_CAPABILITY_FLAG_NAMES` (registry
     parity: twelve flagged contexts, one analysis-only).
   - Each name is rejected by `V3CapabilityFlags`/`V2CapabilityFlags` and vice
     versa (no vocabulary overlap).
   - Non-bool input raises `TypeError`.
   - Digest is 64 lowercase hex characters, deterministic across calls, and
     changes when exactly one flag flips; it equals
     `hashlib.sha256(json.dumps({name: getattr(flags, name) for name in
     V4_CAPABILITY_FLAG_NAMES}, separators=(",", ":"),
     sort_keys=True).encode("utf-8")).hexdigest()`.
   - `unimplemented_enabled_names()` equals `enabled_names()` for every
     single-flag combination.
   - `tests/unit/test_compatibility_matrix.py::test_matrix_covers_required_taxonomy_ids`
     includes `"v4_capability_flags"` in its required set, and
     `list_compatibility_ids()` remains sorted.

### Required Interfaces and Contracts

- `V4CapabilityFlags` is frozen, slotted, and constructible with no arguments.
- Field order equals `_V4_CAPABILITY_FLAG_NAMES`; the dataclass has exactly
  twelve fields and no extra attributes.
- `V4_CAPABILITY_FLAG_NAMES` is the only public ordered tuple; `v4_architecture`
  remains the owner of context identity, not flag names.
- No behavior, spec, or runner field reads the flags in this task.

### Requirement Evidence

- Original Request: "feature flags" and "Do not implement V4 social mechanics
  yet".
- Existing V3 pattern in `runner_models.py` and `compatibility.py`.

### Error Handling and Logging

- Construction rejects non-bool values with `TypeError`; no logging.
- No logging at import. `compatibility` may include `v4_flag_count` in its
  existing DEBUG extras.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v4_flags.py -q`

### Acceptance Criteria

- Twelve closed flags exist, default off, and are exported.
- Registry/flag parity passes.
- No flag is owned.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v4_flags.py -q`
- Expected result: all tests pass, 0 failures.

## Task 5: Accept runner-config-v56 with an exact keyset

### Intent

Give V4 a versioned wire identity without changing the default write or the
latest feature runner. `runner-config-v56` is the active v55 family keyset plus
one sibling `v4_capability_flags` object; generational siblings follow the
selected family, and no other field is added.

### Implementation Steps

1. In `src/simulation/runner_models.py`:
   - Add `RUNNER_SCHEMA_VERSION_V56: Final[str] = "runner-config-v56"` after v55.
   - Add it to `SUPPORTED_RUNNER_SCHEMA_VERSIONS` and to
     `EXPLICIT_NEW_AGENT_INITIALIZATION_SCHEMAS` (v55 is already a member, and
     v56 preserves v55 initialization semantics).
   - Add `v4_capability_flags: V4CapabilityFlags = V4CapabilityFlags()` to
     `SimulationRunnerConfig` immediately after `v3_capability_flags`.
   - In `__post_init__`, before the V3 gate, add: if any V4 flag is enabled and
     `schema_version != RUNNER_SCHEMA_VERSION_V56`, log
     `v4_capability_requires_v56` at ERROR with `schema_version` and
     `flag_count`, then raise
     `ValueError("V4 capability flags require runner-config-v56 (code=v4_capability_requires_v56)")`.
   - If `schema_version == RUNNER_SCHEMA_VERSION_V56`, preserve every v55
     prerequisite validator that applies to the selected family; do not relax
     any of them. A v56 scaffolding config without a generational run does not
     acquire the generational siblings, and v56 never invents a generational
     run.
2. In `src/simulation/runner_serialization.py`:
   - Add `_V4_CAPABILITY_FLAG_KEYS` mirroring `_V3_CAPABILITY_FLAG_KEYS`.
   - Add `_encode_v4_capability_flags` / `_decode_v4_capability_flags` using
     `_require_keys` and `_bool_field`, raising `RunnerSerializationError` with
     the same codes as the V3 pair.
   - In `_encode_runner_document`, emit `"v4_capability_flags"` only when
     `schema_version == RUNNER_SCHEMA_VERSION_V56`. Never emit it for v55 or
     lower.
   - In `decode_runner_config`, add v56 to the accepted branch. For v56 the root
     keyset is the active v55 family selection plus mandatory
     `v4_capability_flags`; generational siblings are required exactly when a
     generational run is present. The V4 key is mandatory and decoded exactly.
     For v1-v55, `v4_capability_flags` is an unknown field and must be rejected.
     For v1-v55 payloads synthesize `V4CapabilityFlags()`.
3. In `src/simulation/compatibility.py`:
   - Extend the `runner_config` `bump_trigger` with a v56 sentence: accepted v56
     carries the closed `v4_capability_flags` sibling; all flags unowned; no
     behavior; default write remains v4 and latest feature runner remains v55.
   - Add `v4_flag_count` to the existing DEBUG extras.
4. In `src/experiments/matrix_schema.py::finalize_matrix_cell_config`, add an
   early branch before the `generational_run` branch:
   `if config.schema_version == RUNNER_SCHEMA_VERSION_V56: return (RUNNER_SCHEMA_VERSION_V56, "explicit_v56")`.
   This preserves an explicitly constructed scaffolding config and never emits
   v56 from feature selection on its own. Assert no V4 flag is enabled in this
   branch (all are unowned in V4-01).
5. Update the deliberate baseline pins:
   - In `tests/architecture/test_path_dependence_boundaries.py`, replace the
     `"runner-config-v56" not in source` assertion with
     `"runner-config-v57" not in source` and rename the test to
     `test_no_unplanned_runner_or_replay_schema_files`. Keep the existing pin
     assertions unchanged.
   - In `tests/architecture/test_v3_baseline_inventory.py`, change the accepted
     set assertion to include v56 and to exclude v57, while keeping
     `RUNNER_SCHEMA_VERSION == "runner-config-v4"` and
     `RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"`. Add a comment that v56
     is accepted-only scaffolding.
6. Before running tests, grep `src/simulation` for `RUNNER_SCHEMA_VERSION_V55`
   and add `RUNNER_SCHEMA_VERSION_V56` to every version set that admits a v55
   feature (agent encoding, family roots, feature gates, initialization
   schemas). Do not add v56 to the default-write or automatic feature-selection
   decision. Record the touched symbols in the task receipt so the set is
   auditable.
7. Add `tests/unit/test_runner_config_v56.py`:
   - `RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS`.
   - `RUNNER_SCHEMA_VERSION == RUNNER_SCHEMA_VERSION_V4`.
   - A v56 config with all flags off round-trips byte-identically and includes
     the `v4_capability_flags` key with twelve false booleans.
   - A v55 config does not include the key; adding it to a v55 payload raises
     `unexpected_field` or `unknown_field` (assert the exact code produced by
     `decode_runner_config`).
   - A v56 payload missing the key raises the exact missing-field code.
   - A v56 payload with an extra key inside `v4_capability_flags` raises.
   - Legacy v4/v23/v55 payloads decode with all V4 flags false.
   - `finalize_matrix_cell_config` on an explicit v56 returns v56; on a plain v4
     config returns v4; no input without v56 returns v56.
   - V4 flags enabled on v56 encode/decode successfully but
     `SimulationRunner.from_config` raises `CAPABILITY_UNIMPLEMENTED` with
     `stage == "v4_capability_flags"` (assert for all twelve flags
     parametrically).

### Required Interfaces and Contracts

- `runner-config-v56` is **accepted**, never the default, and never auto-emitted.
- Wire shape: active v55 family keyset plus mandatory sibling
  `v4_capability_flags` with exactly the twelve keys, all booleans. Generational
  siblings remain mandatory only when a generational run is present.
- Legacy synthesis: v1-v55 decode with `V4CapabilityFlags()`.
- Strictness: unknown, missing, duplicate, or non-bool fields fail closed with
  the existing `RunnerSerializationError` codes.
- `runner-result-v3` is unchanged; v56 generational runs still write v3.
- No new command, event, observer semantic type, metric family, or migration.

### Requirement Evidence

- Original Request: "schema/version evolution", "event versioning",
  "compatibility strategy", "feature flags".
- `src/simulation/runner_models.py` accepted-set contract.
- `docs/configuration.md` currently states there is no v56; this task
  deliberately supersedes that sentence. Task 16 updates the document.

### Error Handling and Logging

- Config-construction failure: `v4_capability_requires_v56` at ERROR with
  `schema_version`, `flag_count`, `reason_code`.
- Runtime construction failure: existing `runner_construction_v4_capability_unimplemented`
  log at ERROR with `stage="v4_capability_flags"` and the enabled flag names
  (names are safe metadata; never log config payloads).
- Serialization failures keep stable codes and paths; no payload logging.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v56.py tests/unit/test_runner_config_v4_flags.py tests/unit/test_v3_scaffolding_gate.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_path_dependence_boundaries.py -q`

### Acceptance Criteria

- v56 is accepted, round-trips, and is never selected automatically.
- Default write stays v4; latest feature runner stays v55.
- All twelve flags fail closed at runtime with the documented stage.
- No V3 pin other than the deliberate v57 guard changes.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v56.py -q`
- Expected result: all tests pass, 0 failures, 0 skips.
- `uv run --frozen --python 3.12.14 lint-imports` reports 25 contracts kept.

## Task 6: Add V4 regression profiles and fail-closed gates

### Intent

Provide the executable definition of "V4 scaffolding off": a profile that
rejects any enabled V4 flag, and a composed V3 regression profile that later
qualification lanes can apply without re-implementing the checks.

### Implementation Steps

1. In `src/experiments/catalog.py`, add `v4_scaffolding_profile(config)`:
   - Type-check `SimulationRunnerConfig` and `V4CapabilityFlags` exactly as
     `v3_scaffolding_profile` does.
   - Compute `enabled = config.v4_capability_flags.enabled_names()` and a
     twelve-character digest prefix.
   - Log `v4_scaffolding_profile_check` at DEBUG with `schema_version`,
     `enabled_v4_flag_count`, `v4_capability_flags_digest_prefix`.
   - If `enabled`, raise
     `ValueError("v4 scaffolding requires all V4 capability flags off (code=v4_scaffolding_flags_enabled flag_count=N)")`.
   - Return the same config object (no mutation).
2. Add `v3_regression_profile(config)`:
   - Type-check, call `v4_scaffolding_profile(config)`, then
     `v2_regression_profile(config)`.
   - Log `v3_regression_profile_ok` at DEBUG with `schema_version`.
   - Return the profiled config.
3. Add both to `src/experiments/__init__.py` imports and `__all__`.
4. Create `tests/unit/test_v4_scaffolding_gate.py`:
   - A base v4 config passes `v4_scaffolding_profile` and
     `v3_regression_profile` unchanged (`is config`).
   - A v56 config with all flags off passes both.
   - For each of the twelve flags, a v56 config with only that flag enabled:
     encodes/decodes successfully, then `v4_scaffolding_profile` raises the
     documented code, and `SimulationRunner.from_config` raises
     `CAPABILITY_UNIMPLEMENTED` with stage `v4_capability_flags`.
   - A v4 config with a V4 flag enabled fails at construction with
     `v4_capability_requires_v56` before reaching the profile.
   - `v3_regression_profile` still enforces V1 rules (tracing off, V1 agent
     shape) by reusing an existing invalid fixture; assert the original error
     code rather than duplicating the logic.
5. Do not alter `v2_regression_profile` or `v3_scaffolding_profile` semantics.

### Required Interfaces and Contracts

- `v4_scaffolding_profile` returns the identical object on success; it is a
  validator, not a constructor.
- `v3_regression_profile` composes validators in the order V4 then V2; it does
  not enable or disable any mode.
- Error codes are stable strings consumed by tests and operators.

### Requirement Evidence

- Original Request: "V3 regression suite" and "compatibility strategy".
- `src/experiments/catalog.py` profile contract.

### Error Handling and Logging

- Profile failures raise `ValueError` with the stable code; the caller logs or
  surfaces it.
- DEBUG logs contain only schema version, counts, and digest prefix.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_scaffolding_gate.py tests/unit/test_v3_scaffolding_gate.py -q`

### Acceptance Criteria

- Both profiles exist, are exported, and fail closed for every V4 flag.
- Existing V3 profiles behave exactly as before.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_scaffolding_gate.py -q`
- Expected result: all tests pass, 0 failures.

## Phase Risks and Mitigations

- Risk: v56 accidentally becomes the default or is auto-selected by matrix
  finalization.
  Mitigation: explicit default-write and no-auto-emit tests, plus the v57 guard.
- Risk: legacy decoding of v1-v55 starts accepting the V4 key.
  Mitigation: exact-key tests for v55 rejection and v56 requirement.
- Risk: adding a field to `SimulationRunnerConfig` changes equality or
  fingerprints for V3 configs.
  Mitigation: the field defaults to an all-false frozen value; baseline and
  fingerprint tests must pass unchanged.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
