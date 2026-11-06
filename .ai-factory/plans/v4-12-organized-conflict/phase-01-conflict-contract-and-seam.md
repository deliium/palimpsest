# Phase 1: Conflict Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Freeze the organized-conflict vocabulary, identifier grammar, operation-to-command
matrix, locked cognition policy, locked analysis policy, and capability ownership
before any ledger or analysis code is written. After this phase,
`organized_conflict` is an owned V4 flag on `runner-config-v56`, requires
`diplomacy`, and fails closed on every invalid combination.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `V4ContextId.ORGANIZED_CONFLICT`, spec 170-183 | Declares the context as `objective_world`, `uses_existing_events=True`, prerequisite `DIPLOMACY`, non-goals no war state/registry and no army actor/hierarchy |
| `src/simulation/runner_models.py` | `_V4_CAPABILITY_FLAG_NAMES` 305-318; `_V4_OWNED_CAPABILITY_FLAGS` 320-326; `V4CapabilityFlags` 1115-1165; v56 gate 7996-8008 | Closed flag tuple, ownership set, and v56 requirement |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 155-157; matrix entry 761-781 | Mirror ownership set and compatibility prose |
| `src/simulation/runner.py` | `RunnerConstructionErrorCode` 276-288; `from_config` 2273-2345; `_cognition_config_for` 1023-1033; call sites 2751-2760, 6465-6476 | Fail-closed construction and run-level cognition mode wiring |
| `src/agents/cognition/configuration.py` | `CognitionDiplomacyMode` 474-483; config fields 685-698; validation 1286-1302; fingerprint 1652-1656; construction 1933-1934 | Pattern for a run-level mode and locked policy |
| `src/world/actions.py` | commands 52-246, `OpposePublicGood` 847-858 | Existing commands available to the operation matrix |
| `src/world/_rules.py` | attack 1572-1618, 3384-3464; flee 1621-1694, 3467-3538; help 1469-1484, 4019-4039; take 1285-1335; give 1375-1407 | Physical semantics the matrix may reference |
| `src/world/events.py` | `Attacked` 821-842; `Fled` 845-867; `Died` 968-983; `Helped` 744-763; `Taken`/`Given` 580-634; `PublicGoodOpposed` 2728-2752 | Events that later analysis consumes; no new event is added |
| `src/analysis/specifications.py` | count 53; diplomacy/treaty enum tail 238-245; builders 7384-7814; `_BUILDERS` 7978-7986 | Catalog append point and current 168 pin |
| `tests/architecture/test_v4_architecture_invariants.py` | ownership pins 156-178, 346-362 | Existing assertions that must change from "organized_conflict unowned" to owned |
| `tests/unit/test_runner_config_v56.py` | v56 accepted/owned/fail-closed 127-299 | Activation tests to extend |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/organized_conflict.py` | create | Closed vocabulary, identifiers, operation matrix, policy dataclass, validators |
| `src/analysis/organized_conflict_contract.py` | create | Analysis prefixes, closed episode/event/alignment vocabulary, forbidden result fields |
| `src/analysis/organized_conflict_policy.py` | create | Locked deterministic detection thresholds |
| `src/simulation/runner_models.py` | modify | Add `organized_conflict` to owned set; update docstrings |
| `src/simulation/compatibility.py` | modify | Add `organized_conflict` to owned set; update matrix prose |
| `src/simulation/runner.py` | modify | Add `v4_prerequisite_missing`; pass `organized_conflict_enabled` to cognition config; enforce diplomacy prerequisite |
| `src/agents/cognition/configuration.py` | modify | Add `CognitionOrganizedConflictMode`, config fields, validation, fingerprint, construction pass-through |
| `tests/unit/test_organized_conflict_contract.py` | create | Vocabulary, ID, matrix, forbidden-field tests |
| `tests/unit/test_organized_conflict_policy.py` | create | Exact policy values and immutability |
| `tests/unit/test_runner_config_v4_flags.py` | modify | Five-flag ownership and prerequisite combinations |
| `tests/unit/test_runner_config_v56.py` | modify | v56 ownership and fail-closed cases |
| `tests/unit/test_v4_scaffolding_gate.py` | modify | Owned/unowned split |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Five owned flags; organized_conflict owned |
| `tests/architecture/test_diplomacy_boundaries.py` | modify | Organized conflict no longer fails closed; replace with prerequisite test |
| `tests/architecture/test_organized_conflict_boundaries.py` | create (skeleton) | Phase 7 expands; Phase 1 adds ownership assertions |

## Task 1: Freeze the conflict vocabulary identifier grammar and command matrix

### Intent

Make every later row, frame, metric, and snapshot use one closed vocabulary. The
operation matrix is the contract that keeps the eight requested primitives inside
existing low-level mechanics.

### Implementation Steps

1. Create `src/agents/cognition/organized_conflict.py` with module docstring
   stating: coordination is one owner's belief; no war state, army actor,
   registry, obligation, or command path; all physical effects are ordinary
   `WorldEngine` admission.
2. Define constants:
   - `ORGANIZED_CONFLICT_POLICY_VERSION = "organized-conflict.v1"`
   - `ORGANIZED_CONFLICT_CONTRACT_VERSION = "organized-conflict-v1"`
   - `ORGANIZED_CONFLICT_ID_HEX_LEN = 16`
   - `ORGANIZED_CONFLICT_ID_SEPARATOR = "|"`
   - `ORGANIZED_CONFLICT_FRAME_VERSION = "ocf_v1"`
   - `ORGANIZED_CONFLICT_FRAME_MAX_CHARS = 256`
   - `ORGANIZED_CONFLICT_FRAME_FIELD_COUNT = 12`
3. Define closed `StrEnum` vocabularies:
   - `ConflictOperation`: `coordinated_attack`, `defense`, `movement_group`,
     `resource_capture`, `structure_attack`, `route_blocking`, `retreat`,
     `assistance`.
   - `ConflictRole`: `attacker`, `defender`, `scout`, `blocker`, `capturer`,
     `assistant`, `retreater`, `messenger`, `unknown`.
   - `ConflictTargetKind`: `agent`, `group`, `location`, `route`, `resource`,
     `structure`, `unknown`.
   - `ConflictPlanStatus`: `proposed`, `joined`, `active`, `completed`,
     `abandoned`, `expired`.
   - `ConflictParticipationStance`: `join`, `decline`, `withdraw`, `unknown`.
   - `ConflictInterpretationKind`: `individual_violence`,
     `coordinated_conflict`, `defense`, `retreat`, `assistance`,
     `resource_capture`, `route_blocking`, `structure_attack`,
     `persistent_inter_group_conflict`, `unclear`.
   - `ConflictProvenance`: `self_declared`, `communicated`, `observed`,
     `remembered`, `inferred`.
   - `ConflictOutcomeKind`: `hit`, `miss`, `damage`, `death`, `flee_success`,
     `flee_failure`, `custody_capture`, `structure_opposition`, `assistance`,
     `co_movement`.
   - `ConflictContradictionKind`: `duplicate_plan`, `contradictory_plan`,
     `contradictory_interpretation`, `conflicting_side`.
   - `ConflictTerminationKind`: `completed`, `abandoned`, `expired`,
     `withdrawn`.
4. Define `CONFLICT_OPERATION_COMMANDS: Mapping[ConflictOperation, frozenset[str]]`
   with exactly:
   - `coordinated_attack`: `{"attack"}`
   - `defense`: `{"attack", "help", "move"}`
   - `movement_group`: `{"move", "transport"}`
   - `resource_capture`: `{"take", "give"}`
   - `structure_attack`: `{"oppose_public_good", "attack"}`
   - `route_blocking`: `{"move", "attack", "flee", "help"}`
   - `retreat`: `{"flee"}`
   - `assistance`: `{"help", "feed", "transport"}`
5. Define `CONFLICT_ID_PREFIXES` for cognition rows:
   `oce-` episode, `ocp-` plan, `ocm-` participation, `oco-` observation,
   `oci-` interpretation, `ocx-` outcome, `occ-` contradiction, `oct-`
   termination.
6. Add validators:
   - `assert_conflict_no_forbidden_fields(value)` rejects `at_war`,
     `war_state`, `army_id`, `conflict_registry`, `winner`, `loser`,
     `legitimacy`, `score`, `composite`, `truth`, `enforced`.
   - `require_conflict_id(name, value, prefixes=...)` enforces prefix, separator,
     and 16 lowercase hex characters.
   - `require_conflict_token(name, value)` enforces a bounded opaque token.
   - `conflict_target_token(value: str) -> str` hashes one target/side value
     under `palimpsest.organized_conflict.target.v1` and returns 16 lowercase
     hex; `conflict_group_token(tokens)` hashes sorted member tokens under
     `palimpsest.organized_conflict.group.v1`.
   - `conflict_record_id(prefix, *parts)` returns a content-addressed
     `prefix + 16 hex` from canonical JSON parts.
7. Create `src/analysis/organized_conflict_contract.py` with:
   - `ORGANIZED_CONFLICT_CANDIDATE_PREFIX = "oc-"`
   - `ORGANIZED_CONFLICT_EDGE_PREFIX = "oc-edge-"`
   - `ORGANIZED_CONFLICT_PUBLICATION_PREFIX = "oc-pub-"`
   - `ConflictEpisodeClass`: `individual_violence`, `coordinated_conflict`,
     `persistent_inter_group_conflict`.
   - `ConflictAlignment`: `consistent`, `unresolved`, `inconsistent`,
     `not_applicable`.
   - `ConflictEventClass`: `attack`, `defense`, `retreat`, `assistance`,
     `custody_capture`, `structure_opposition`, `co_movement`, `route_denial`.
   - `CONFLICT_FORBIDDEN_RESULT_FIELDS`: `war_score`, `violence_score`,
     `escalation_index`, `legitimacy`, `winner`, `loser`, `truth`, `verified`,
     `enforced`, `enforcement`, `composite`, `overall_conflict`.
8. Add tests for every enum value, exact matrix contents, valid/invalid IDs,
   forbidden fields, and the absence of any `world.at_war`-style field.

### Required Interfaces and Contracts

```python
class ConflictOperation(StrEnum): ...
CONFLICT_OPERATION_COMMANDS: Final[Mapping[ConflictOperation, frozenset[str]]]
CONFLICT_ID_PREFIXES: Final[Mapping[str, str]]
def conflict_record_id(prefix: str, *parts: object) -> str: ...
def require_conflict_id(name: str, value: object, *, prefixes: frozenset[str]) -> str: ...
def conflict_target_token(value: str) -> str: ...
def conflict_group_token(tokens: Sequence[str]) -> str: ...
def assert_conflict_no_forbidden_fields(value: object) -> None: ...
```

Compatibility: the module may import `world` action classes only in later tasks;
Task 1 stores command names, not constructed commands. No `AgentCommand` value is
created here.

### Requirement Evidence

- Source: Original Request — eight requested primitives.
- Source: `src/simulation/v4_architecture.py` 170-183 — context id, authority,
  existing events, prerequisite, non-goals.
- Source: `src/world/actions.py` 52-246 and 830-858 — the only available commands.
- Supported combinations: every operation maps to at least one existing command;
  `structure_attack` has exactly two legal physical routes; no operation maps to
  a non-existent command.

### Error Handling and Logging

- Raise `ValueError` with stable messages for invalid IDs, tokens, or forbidden
  fields; no payload values in messages.
- DEBUG log only counts: `organized_conflict_vocabulary_loaded
  operations=8 roles=9 targets=7`.
- Never log actor ids, target ids, or frame content.

### Tests

- `tests/unit/test_organized_conflict_contract.py`
  - `test_operation_vocabulary_is_exactly_eight`
  - `test_operation_command_matrix_uses_only_existing_commands`
  - `test_conflict_ids_are_content_addressed_and_bounded`
  - `test_forbidden_war_state_fields_are_rejected`
  - `test_analysis_prefixes_do_not_overlap_diplomacy`
- Command: `uv run pytest tests/unit/test_organized_conflict_contract.py -q`

### Acceptance Criteria

- Eight operations, nine roles, seven target kinds, six plan statuses, four
  participation stances, ten interpretation kinds, five provenances, ten outcome
  kinds, four contradiction kinds, and four termination kinds exist exactly.
- Every mapped command name exists in `src/world/actions.py`.
- `oce-`, `ocp-`, `ocm-`, `oco-`, `oci-`, `ocx-`, `occ-`, `oct-`, `oc-`,
  `oc-edge-`, and `oc-pub-` are distinct and validated.
- No war-state, army, registry, score, winner, or legitimacy field exists.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_contract.py -q`
- Expected: all tests pass.

## Task 2: Add the locked cognition and analysis policies

### Intent

Freeze every cap and detection threshold so later code cannot choose them ad hoc.
The analysis thresholds define the difference between individual violence and
persistent coordinated inter-group conflict.

### Implementation Steps

1. In `src/agents/cognition/organized_conflict.py`, add
   `OrganizedConflictPolicy` frozen dataclass with:
   - `max_plans=8`
   - `max_participants_per_plan=16`
   - `max_observations=64`
   - `max_interpretations=16`
   - `max_outcomes=32`
   - `max_contradictions=8`
   - `max_terminations=16`
   - `max_total_records=128`
   - `max_frame_chars=256`
   - `plan_ttl_ticks=24`
   - `max_target_refs=8`
2. Add `_ORGANIZED_CONFLICT_POLICY_VALUES`, `default_organized_conflict_policy()`,
   and `__post_init__` checks for exact types, positive integers, and the frame
   bound.
3. Create `src/analysis/organized_conflict_policy.py` with
   `ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION = "organized-conflict-analysis.v1"`
   and `OrganizedConflictAnalysisPolicy` frozen dataclass:
   - `window_ticks=6`
   - `min_side_actors=2`
   - `min_hostile_events=2`
   - `min_coordinated_windows=2`
   - `min_windows=3`
   - `sustained_span_ticks=24`
   - `sustained_min_hostile_events=6`
   - `sustained_min_active_ticks=3`
   - `inter_group_min_sides=2`
   - `inter_group_min_actors_per_side=2`
   - `reciprocal_min_windows=2`
   - `max_episodes=2048`
   - `max_windows=4096`
   - `max_participants_per_episode=64`
   - `confidence_bands=(0.25, 0.5, 0.75)`
4. Add `default_organized_conflict_analysis_policy()` and validation. The policy
   is import-safe and Pydantic-free.
5. Define classification rules in docstrings:
   - `individual_violence`: one attacker and one target, no shared
     co-participation, no recurrence.
   - `coordinated_conflict`: at least `min_side_actors` on one side and at least
     `min_hostile_events` in a `window_ticks` window, recurring in at least
     `min_windows` windows.
   - `persistent_inter_group_conflict`: at least `inter_group_min_sides` sides,
     each with at least `inter_group_min_actors_per_side`, reciprocal hostile
     windows at least `reciprocal_min_windows` times, and sustained span/event
     thresholds.
6. Add tests for exact values, frozen behavior, and invalid mutations.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class OrganizedConflictPolicy: ...
def default_organized_conflict_policy() -> OrganizedConflictPolicy: ...

@dataclass(frozen=True, slots=True)
class OrganizedConflictAnalysisPolicy: ...
def default_organized_conflict_analysis_policy() -> OrganizedConflictAnalysisPolicy: ...
```

Compatibility: these policies are domain constants, not runner JSON. They are
not added to `runner-config-v56` and do not change the runner fingerprint. The
cognition policy version enters the cognition config fingerprint; the analysis
policy version enters metric/snapshot provenance.

### Requirement Evidence

- Source: Original Request — "detect sustained organized conflict from event
  patterns" and "distinguish individual violence from persistent coordinated
  inter-group conflict".
- Source: `src/agents/cognition/diplomacy.py` 501-606 — locked policy precedent.
- Supported combinations: a one-attacker/one-target sequence is individual; a
  two-actor repeated sequence is coordinated; a two-side reciprocal sequence is
  persistent inter-group. Thresholds are fixed, not learned.

### Error Handling and Logging

- Invalid policy mutation raises `TypeError`/`ValueError` with field name only.
- INFO once at construction: `organized_conflict_policy_loaded
  policy_version=organized-conflict.v1 plan_cap=8`.
- INFO once: `organized_conflict_analysis_policy_loaded
  policy_version=organized-conflict-analysis.v1 window_ticks=6`.
- Never log episode contents or participant tokens.

### Tests

- `tests/unit/test_organized_conflict_policy.py`
  - `test_cognition_policy_values_are_exact`
  - `test_analysis_thresholds_are_exact_and_frozen`
  - `test_policy_rejects_bool_as_int`
  - `test_default_policies_are_deterministic`
- Command: `uv run pytest tests/unit/test_organized_conflict_policy.py -q`

### Acceptance Criteria

- Both policies exist with exact values and are frozen.
- The analysis policy defines all three episode classes unambiguously.
- No policy reads environment variables, wall clock, random state, or runner
  configuration.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_policy.py -q`
- Expected: all tests pass.

## Task 3: Claim organized_conflict and enforce the diplomacy prerequisite

### Intent

Turn the declared context into an owned capability without adding a schema. The
only new runtime behavior in this task is activation plus a prerequisite gate.

### Implementation Steps

1. In `src/simulation/runner_models.py`:
   - Add `organized_conflict` to `_V4_OWNED_CAPABILITY_FLAGS`.
   - Update the comment and `V4CapabilityFlags` docstring to name V4-12.
   - Keep `_V4_CAPABILITY_FLAG_NAMES` unchanged (12 names).
2. In `src/simulation/compatibility.py`:
   - Add `organized_conflict` to `V4_OWNED_CAPABILITY_FLAGS`.
   - Update the `v4_capability_flags` matrix prose: five owned, seven unowned;
     `organized_conflict` owned by V4-12; still fail closed for the rest.
3. In `src/simulation/runner.py`:
   - Add `V4_PREREQUISITE_MISSING = "v4_prerequisite_missing"` to
     `RunnerConstructionErrorCode`.
   - After the `v4_unimplemented` guard and before `stage = "physical_rules"`,
     check: if `config.v4_capability_flags.organized_conflict` is true and
     `config.v4_capability_flags.diplomacy` is false, log an ERROR with
     `reason_code=v4_prerequisite_missing`, `stage=v4_capability_flags`, and
     `context=organized_conflict`, then raise
     `RunnerConstructionError(V4_PREREQUISITE_MISSING, stage="v4_capability_flags")`.
   - Add `organized_conflict_enabled` parameter to `_cognition_config_for` and
     pass it at both call sites (`2751-2760`, `6465-6476`).
4. In `src/agents/cognition/configuration.py`:
   - Add `CognitionOrganizedConflictMode` with `DISABLED`/`DETERMINISTIC`.
   - Add `organized_conflict_mode` and `organized_conflict_policy` fields after
     diplomacy.
   - Validate: disabled clears policy; deterministic installs the locked default;
     a mismatched policy raises `organized_conflict_mode_policy_mismatch`.
   - Add mode/policy version to the config fingerprint only in deterministic
     mode.
   - Pass both fields through `build_cognitive_loop`.
5. Update tests:
   - `test_runner_config_v4_flags.py`: ownership is exactly five; organized
     conflict is owned.
   - `test_runner_config_v56.py`: `organized_conflict` alone fails with
     `v4_prerequisite_missing`; with diplomacy it constructs; v4/v55 still fail.
   - `test_v4_scaffolding_gate.py`: owned/unowned split.
   - `test_v4_architecture_invariants.py`: five owned flags; organized conflict
     owned.
   - `test_diplomacy_boundaries.py`: replace the "organized conflict still fails
     closed" assertion with a prerequisite assertion.
6. Do not add a per-agent runner key. The mode is run-level and derived from the
   flag.

### Required Interfaces and Contracts

```python
class RunnerConstructionErrorCode(StrEnum):
    ...
    V4_PREREQUISITE_MISSING = "v4_prerequisite_missing"

class CognitionOrganizedConflictMode(StrEnum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
```

Compatibility: `runner-config-v56` remains the only V4 schema; default runner
write remains `v4`; no v57 field or key is added.

### Requirement Evidence

- Source: `src/simulation/v4_architecture.py` 170-183 — prerequisite `DIPLOMACY`.
- Source: `src/simulation/runner_models.py` 320-326 and 7996-8008 — owned set and
  v56 gate.
- Source: `src/simulation/runner.py` 2278-2345 — fail-closed construction.
- Supported combinations: off/off; v4+v56 errors; v56+conflict-only errors;
  v56+conflict+diplomacy constructs; diplomacy-only constructs without conflict.

### Error Handling and Logging

- ERROR `runner_construction_v4_prerequisite_missing
  schema_version=runner-config-v56 stage=v4_capability_flags
  reason_code=v4_prerequisite_missing context=organized_conflict` — no flag
  values beyond names and no agent ids.
- INFO `runner_v4_owned_flags count=5`.
- INFO `cognition_organized_conflict_mode mode=deterministic
  policy_version=organized-conflict.v1`.

### Tests

- `tests/unit/test_runner_config_v4_flags.py`
- `tests/unit/test_runner_config_v56.py`
- `tests/unit/test_v4_scaffolding_gate.py`
- `tests/architecture/test_v4_architecture_invariants.py`
- `tests/architecture/test_diplomacy_boundaries.py`
- Command:
  `uv run pytest tests/unit/test_runner_config_v4_flags.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_diplomacy_boundaries.py -q`

### Acceptance Criteria

- `organized_conflict` is owned and constructible only on v56 with diplomacy.
- Missing diplomacy fails with `v4_prerequisite_missing`.
- No v57, no new flag, no new root field, no per-agent key.
- Existing owned flags still construct.
- The ownership sets in `runner_models` and `compatibility` agree.

### Verification

- Commands above.
- Expected: all pass; no `runner-config-v57` string exists in `src/`.

## Phase Risks and Mitigations

- Risk: the prerequisite gate rejects previously valid diplomacy-only runs.
  Mitigation: the gate fires only when `organized_conflict` is enabled.
- Risk: duplicated ownership sets drift.
  Mitigation: test asserts `_V4_OWNED_CAPABILITY_FLAGS` equals
  `compatibility.V4_OWNED_CAPABILITY_FLAGS`.
- Risk: adding a run-level mode accidentally changes runner JSON.
  Mitigation: mode lives only in `CognitionLoopConfig`; serializer tests pin the
  exact v56 keyset.
- Risk: an implementer adds a new command to satisfy an operation.
  Mitigation: the matrix test checks every name against `src/world/actions.py`
  and the command-count pin stays 43.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
