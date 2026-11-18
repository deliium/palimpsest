# Phase 1: Contracts and configuration

Plan: [index.md](index.md)
Tasks: 1–4
Depends on: none

## Objective

Establish a closed, default-absent physical instrument channel without changing legacy item, experiment, or runner wire meanings. The decisions in the index's contract sections are normative for every phase.

## Current-Code Evidence

| Path | Symbols / evidence | Why it matters |
|---|---|---|
| `src/world/models.py` | `Item`, `Resource`, `PhysicalRules` | Item has no instrument properties; preserve its exact legacy keys. |
| `src/world/production.py` | `ToolMark`, `ToolRole`, `ItemProduct` | Sidecars keyed by portable TOOL item IDs are an existing structural pattern. |
| `src/world/actions.py` | `Experiment`, `AgentCommand`, `_COMMAND_TYPES` | Existing experiment operators are categorical, not measurement operations. |
| `src/simulation/runner_models.py` | `WorldScenarioSpec`, `SimulationRunnerConfig`, science validation near 8271 | Science currently requires v56 exactly; a new version needs explicit accepted-family handling. |
| `src/simulation/runner_serialization.py` | `_v56_family_root_keys`, `encode_runner_config`, `decode_runner_config` | Preserve exact active-family root sets, including optional generational siblings. |
| `src/simulation/versioning.py` | `V4_DEEPENING_WRITE_PAIRS`, `V4_EVENT_REUSING_CONTEXTS` | Do not consume reserved epidemic/ecology/disaster pairs. |
| `src/simulation/v4_architecture.py` | SCIENCE spec; authority validator near 470 | Science remains owner-scoped; physical substrate does not authorize beliefs as world state. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/world/measurement.py` | create | Public frozen quantities, instrument/reference state, reading, instrument/reference appearances, policy and validation contracts. |
| `src/world/actions.py`, `src/world/__init__.py` | modify | Two closed commands and explicit public exports. |
| `src/simulation/measurement_config.py` | create | Strict instrument spec and canonical config helpers; import only allowed inner contracts. |
| `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/__init__.py` | modify | Optional spec and distinct runner-v57 encoding/decoding. |
| `src/simulation/compatibility.py`, `src/simulation/versioning.py`, `src/simulation/v4_architecture.py` | modify | Version taxonomy and narrow physical-deepening metadata. |
| `pyproject.toml`, `tests/architecture/boundary_checker.py` | modify | Register the new private modules and their narrow allowed importers without broadening domain access. |
| `tests/unit/test_measurement_contracts.py`, `tests/unit/test_measurement_commands.py`, `tests/unit/test_runner_config_v57.py`, `tests/unit/test_measurement_versioning.py` | create | Focused contract/config tests. |

## Task 1: Define instrument and reading contracts

### Intent

Separate what an instrument physically is, what its display says, and what an agent may believe.

### Implementation Steps

1. Add `src/world/measurement.py`, using exact-type, finite, range, tuple-copy and stable-ID validation consistent with world contracts. Introduce `MeasurementQuantity`, `MeasurementUnit`, `CalibrationState`, `InstrumentState`, `MeasurementReference`, `MeasurementReading`, `InstrumentAppearance`, and `ReferenceAppearance`. Reference appearance contains only its eligible visible nominal mark and unit, never its physical value.
2. Implement the five quantity/target/unit combinations, fixed-point arithmetic inputs and policy constants specified in the index. An instrument supports exactly one quantity and one `MeasurementUnit`; references support one unit, not a globally authoritative truth label. `MeasurementUnit` has a closed kind plus an optional exact resource-unit label, not a finite enumeration that discards existing `Resource.unit` strings.
3. Keep instrument/reference records separate from `Item`; both anchor existing `ItemKind.TOOL` items. Initial precision, bias, error, damage, correction, calibration revision and timer epoch are objective. Public appearance contains only supported quantity, nominal scale division, coarse wear, and a visible adjustment marker.
4. Give `MeasurementReading` a stable reading ID, instrument ID, target ID, quantity, unit, displayed scalar OR category, sampling tick, and nominal display division. It must not contain sampled value, actual error, true bias or objectively guaranteed uncertainty.
5. Export public agent-safe contracts from `world`; do not export private resolution functions.

### Required Interfaces and Contracts

`InstrumentState` and `MeasurementReference` are physical contracts, not cognition inputs. The reading's exclusive scalar/category invariant must reject both-present and both-absent cases. Scalar fields use bounded int64 milli-units; bool is never an integer. A coarse category reading cannot be treated as an exact scalar.

### Requirement Evidence

Original Request: physical tools, precision, bias/error, damage, calibration, readings not truth. Architecture: frozen/detached contracts and owner-safe perception.

### Error Handling and Logging

Use stable `measurement_invalid_*` codes and field paths. Constructors/codecs do not log property values or payloads. DEBUG may log safe IDs, enum quantity, counts and reason code only.

### Tests

Cover all five dimensions; negative temperature; zero amounts; invalid units, scalar/category XOR, bool/NaN/inf, int64 overflow, duplicate IDs, defensive detachment and repr leakage. Confirm legacy `Item` keys and TOOL category are unchanged.

### Acceptance Criteria

Every requested property has an objective representation; the agent-facing reading/appearance types expose none of the hidden calibration/error fields.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_contracts.py --cov=world --cov-report=term-missing -q`

Expected: all contracts and negative/leakage cases pass.

## Task 2: Add explicit measurement and calibration commands

### Intent

Make measurement a normal, non-authoritative physical action, never an analysis call or permission bypass.

### Implementation Steps

1. Add frozen `Measure(instrument_id, target_id, quantity)` with tag `measure`, and `CalibrateInstrument(instrument_id, reference_id)` with tag `calibrate_instrument` to `src/world/actions.py`.
2. Extend `AgentCommand`, `_COMMAND_TYPES`, tag validation and public facade exports. Constructors validate shapes only, not ownership/reachability or hidden reliability.
3. Keep `Experiment`, its three operators, process tokens, and all `hyp_v1`/`rep_v1` fields unchanged. Commands contain no predicted value, submitted reading, confidence, requested precision or user-supplied calibration correction.
4. Add the command count delta to new measurement pins: 43 → 45. Co-update current-count assertions exercised by the phase's focused/architecture checks as this closed vocabulary changes; preserve historical-order and legacy-wire assertions. Phase 6 audits all remaining current global pins after the complete pipeline lands.

### Required Interfaces and Contracts

Exactly one command per selected action. Calibration is not repair, certification, or a global clock service. Channel-off rejection belongs to admission, not dataclass construction. No new item category or free-form operator.

### Requirement Evidence

Architecture extension contract requires command/admission/event/replay co-delivery. Original Request supplies the physical action need.

### Error Handling and Logging

Constructor errors are stable type/value errors. DEBUG command construction logs tags and safe IDs only; never readings or hidden parameters.

### Tests

Closed membership, immutable commands, unknown quantity, cross-type IDs, tag roundtrip fixtures prepared for Phase 3, absent predictions/corrections, and existing experiment constructors unchanged.

### Acceptance Criteria

Two new commands are expressible through the public facade but have no authority before engine admission.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_commands.py tests/unit/test_experiment_command.py --cov=world --cov-report=term-missing -q`

Expected: new constructors and unchanged experiment command cases pass.

## Task 3: Add the exact runner-config-v57 instrument seam

### Intent

Make activation explicit and reproduce physical initialization without widening v56.

### Implementation Steps

1. Introduce `MeasurementInstrumentsSpec` in `src/simulation/measurement_config.py`, re-export through `runner_models` and the documented simulation facade. Exact keys: `policy_version`, `instruments`, `references`. Locked policy: `measurement-instruments.v1`. Both record sequences are ordered by item ID, bounded to 64 each, and validated against scenario TOOL items; at least one instrument is required. References may be empty.
2. Add `measurement_instruments: MeasurementInstrumentsSpec | None = None` to `SimulationRunnerConfig`. Introduce `RUNNER_SCHEMA_VERSION_V57` and supported-set membership.
3. A v57 root is the selected v56 family root union the one mandatory, non-null `measurement_instruments` sibling. Nested scenario, cognition and V4 flag objects keep their old keys. v1–v56 must reject that sibling and decode the Python field as absent.
4. Require `science=True`, its existing `predictive_world_model` and `bounded_experimentation` prerequisites, and valid initial anchors. Route-time instruments additionally require configured `regions_migration`/owned migration seam. No new capability flag or per-agent config key. Generalize exact-v56 validations to the explicit `{v56,v57}` family where semantically necessary; never replace them with an unbounded numeric comparison.
5. Writer chooses v57 only for a present spec; reject explicit v57 without a spec and old schemas with a spec. Preserve automatic selection and canonical bytes for every absent-spec input, including science v56 and default v4.
6. Add strict helpers for spec encode/decode in the new module; the runner serializer delegates to them rather than copying another thousand-line family.

### Required Interfaces and Contracts

No implicit tools, references or starter instruments. IDs must resolve exactly once; instrument and reference IDs cannot overlap or carry STRIKE tool marks. Instrument bias and calibration settings are config-private and never passed to cognition construction.

### Error Handling and Logging

Codes: `measurement_schema_required`, `measurement_spec_required`, `measurement_science_required`, `measurement_anchor_invalid`, `measurement_route_context_required`. Report paths but not rejected payloads. INFO activation logs instrument/reference counts and policy version only.

### Tests

v57 exact-key roundtrip for ordinary and generational active families; v56 extra-root rejection; v57 null/missing spec; each prerequisite independently missing; duplicate/dangling/non-TOOL/cross-role anchors; absent references accepted; 65-record caps; representative existing v56 fixture byte-stable; every old mode still accepts its previously supported schema.

### Acceptance Criteria

No legacy root or nested schema changes meaning. Valid v57 is deterministic and selects instruments only when explicitly present.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v57.py tests/unit/test_runner_config_v56.py tests/unit/test_bounded_experimentation_spec.py --cov=simulation --cov-report=term-missing -q`

Expected: new family passes; update only the obsolete v57-unsupported assertion to test an actually unsupported version while preserving v56 exact-key rejection.

## Task 4: Register the physical deepening version contract

### Intent

Document why physical measurement needs new replay data without changing the authority of scientific beliefs.

### Implementation Steps

1. Register event 28 / persistence codec `v26` as the next `DeepeningWritePair` for SCIENCE in `src/simulation/versioning.py`. Keep reserved events 24–26/codecs v22–v24 untouched and unaccepted.
2. Mark the SCIENCE context as no longer exclusively event-reusing. Retain `authority=OWNER_SCOPED`, existing owner packages and all no-truth/no-encyclopedia non-goals. Its referenced world substrate remains engine-owned, just as ordinary experimentation already is.
3. Extend reservation coverage validation narrowly: coverage is reserved ∪ exclusively-reusing ∪ deepening-context IDs. Exclusively-reusing IDs cannot also require a deepening pair; reserved/deepening overlap remains legal for infrastructure. Validate deepening contexts are known, flagged and owned. Retain all existing authority checks; do not add `world` as an owner of an owner-scoped context.
4. Increment context-map metadata revision to `v4-context-map-v6` because the SCIENCE event-use metadata changed; context count remains 17, flag count 12, owned/unowned counts 9/3.
5. Update `simulation.compatibility` with the new accepted runner/replay/codec contracts and their bump triggers. Default writes remain v4/result v2; result schema, Alembic, API, observer protocol and metric catalog stay unchanged.
6. Record the paired import-boundary updates for Phase 2: add `world._measurement` and `world._ambient` to `pyproject.toml`'s `private_world_authority.protected_modules` and corresponding allowed private importers, and to `PRIVATE_WORLD_MODULES` / `PRIVATE_WORLD_IMPORTERS` in `tests/architecture/boundary_checker.py`. Add only the private leaf importers that actually need access. Keep simulation access restricted to existing engine/bootstrap roots, and do not allow cognition, public facades, codecs, API or analysis to import private measurement state. Co-land registration with first module imports in Tasks 5–6.

### Required Interfaces and Contracts

This is a deliberate V4-29 extension of historical reuse-only science, not permission for cognition to read instruments' physical internals. Runtime selection is implemented in Phase 3, not inferred from reservation metadata.

### Error Handling and Logging

Retain existing taxonomy reason codes; add a precise coverage conflict code if needed. Registration logs counts/version labels only.

### Tests

Contiguous deepening pairs 27/28 and v25/v26; reserved slots unchanged; missing science coverage, reuse/deepening conflict, unknown or unowned context rejected; authority invariants still reject world-owned subjective ledgers. Add AST fixtures that admit engine/private-physics imports but reject cognition/API/analysis imports of both new private modules.

### Acceptance Criteria

Taxonomy describes both owner-scoped science and its explicit physical write seam without weakening any package/authority invariant.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_versioning.py tests/unit/test_v4_versioning_reservations.py tests/architecture/test_v4_context_registry.py tests/architecture/test_v4_architecture_invariants.py --cov=simulation --cov-report=term-missing -q`

Expected: all taxonomy and authority checks pass with 17 contexts.

## Phase Risks and Mitigations

- Risk: adding fields to `Item` silently changes every legacy item encoding. Mitigation: item-keyed sidecars only.
- Risk: new schema accepted in one gate but rejected in another. Mitigation: explicit v56-family audit and both ordinary/generational fixture coverage.
- Risk: treating science as objective truth to satisfy metadata. Mitigation: retain owner-scoped authority and separately document engine substrate.

## Phase Completion Checklist

- Every task meets its acceptance criteria and focused checks.
- Only `index.md` task checkboxes are updated after verified completion.
