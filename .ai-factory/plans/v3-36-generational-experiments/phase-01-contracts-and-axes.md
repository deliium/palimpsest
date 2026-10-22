# Phase 1: Comparison contracts and axis engine

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Introduce a closed, validated experiment-comparison contract and a single axis-application engine that both the catalog scenario builder and the matrix layer can reuse. The phase must make every supported variable explicit and deterministic before any experiment or metric code consumes it.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/models.py` | `ExperimentDefinition.__post_init__`, `_scenario_layout` | Paired conditions already require identical seed, stochastic identity, and scenario layout (resources stripped). |
| `src/simulation/runner_models.py` | `MemoryMode` (327), `SkillLearningMode` (422), `TeachingInteractionMode` (435), `InstitutionConceptMode` (597), `PopulationLifecycleSpec` (1337), `AgentCognitionSpec` (6701) | Existing closed modes and the lifecycle fields the axes must modify. |
| `src/simulation/runner_models.py` | `default_lifespan_distribution_spec` (1332), `example_durable_records_spec` (3728) | Passthrough lifespan and reference durable-records spec. |
| `src/simulation/runner_models.py` | `example_cultural_feature_provenance_spec` (3015) | Required sibling when durable records are enabled. |
| `src/simulation/runner_models.py` | `V3CapabilityFlags` (1057), `regions_migration` validation (9055-9130) | Migration and cultural-memory flags must stay consistent. |
| `src/world/models.py` | `Resource` (142) | Scarcity scaling must preserve ids/locations/kinds and keep quantity within maximum. |
| `src/experiments/matrix_factors.py` | `clone_runner_config` (52), `_map_agents` (72), `apply_factor_level` (324) | Applicator conventions; factors must not mutate `schema_version`. |
| `src/experiments/architectures.py` | `expand_architecture` (118) | Existing architecture expansion sets `schema_version` and rebuilds a limited config, so it cannot be reused directly on v55. |
| `src/simulation/cognition_contracts.py` | `get_architecture`, `validate_architecture_compatibility`, `ArchitectureDefinition` | Registry source for mode-only architecture composition. |
| `src/experiments/generational_runner_scenario.py` | `_lifecycle`, `_config` (46-107) | Reference v55 generational lifecycle and agent setup. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/generational_comparison_models.py` | create | Closed axis enum, level table, comparison/spec dataclasses, stable validation errors. |
| `src/experiments/__init__.py` | modify | Export the new comparison model names from the public facade. |
| `src/experiments/generational_axes.py` | create | One dispatcher and exact level applicators for all supported variables. |
| `src/experiments/architectures.py` | modify | Add `apply_architecture_modes` that preserves the entire v55 config and does not change `schema_version`. |
| `tests/unit/test_generational_comparison_models.py` | create | Contract validation tests. |
| `tests/unit/test_generational_axes_population.py` | create | Lifecycle/population/records/migration/scarcity tests. |
| `tests/unit/test_generational_axes_cognition.py` | create | Learning/teaching/innovation/memory/institution/architecture tests. |

## Task 1: Add closed comparison axis and level contracts

### Intent

Provide the typed vocabulary and validation used by every later task. The registry is deliberately closed: a later matrix factor or scenario builder may not invent a level or numeric payload that this contract does not know.

### Implementation Steps

1. Create `src/experiments/generational_comparison_models.py` with `from __future__ import annotations`, `dataclasses.dataclass`, `enum.StrEnum`, `collections.abc.Mapping`/`Sequence`, and `typing.Final`.
2. Define `GenerationalComparisonAxis(StrEnum)` with exactly these members and values:
   - `LIFESPAN = "lifespan"`
   - `LEARNING_MODEL = "learning_model"`
   - `TEACHING_FREQUENCY = "teaching_frequency"`
   - `RECORD_AVAILABILITY = "record_availability"`
   - `MEMORY_ARCHITECTURE = "memory_architecture"`
   - `INNOVATION_RATE = "innovation_rate"`
   - `MIGRATION = "migration"`
   - `RESOURCE_SCARCITY = "resource_scarcity"`
   - `POPULATION_SIZE = "population_size"`
   - `INSTITUTION_SUPPORT = "institution_support"`
   - `COGNITIVE_ARCHITECTURE = "cognitive_architecture"`
3. Define `AXIS_LEVEL_IDS: Final[Mapping[GenerationalComparisonAxis, frozenset[str]]]` with exactly:
   - lifespan: `short`, `long`
   - learning_model: `practice_only`, `teaching_supported`
   - teaching_frequency: `low`, `high`
   - record_availability: `absent`, `present`
   - memory_architecture: `reference`, `reconstructive`
   - innovation_rate: `low`, `high`
   - migration: `isolated`, `connected`
   - resource_scarcity: `scarce`, `abundant`
   - population_size: `small`, `large`
   - institution_support: `off`, `on`
   - cognitive_architecture: `v1_memory`, `full_v2`
4. Define `GenerationalComparisonError(ValueError)` with `code: str` and a stable `message`; log `WARNING generational_comparison_invalid` with only `reason_code` and the comparison id when available.
5. Define frozen slotted dataclasses:
   - `GenerationalAxisLevel(axis: GenerationalComparisonAxis, level_id: str, label_code: str)`. Validate the axis is the enum, `level_id` belongs to `AXIS_LEVEL_IDS[axis]`, and `label_code` is a non-empty stable id matching `[a-z0-9][a-z0-9._-]*`.
   - `GenerationalComparison(comparison_id: str, axis: GenerationalComparisonAxis, control_level_id: str, treatment_level_id: str, label_code: str)`. Validate `comparison_id`/`label_code` as stable ids, both levels belong to the axis table, and control and treatment differ.
   - `GenerationalComparisonSpec(experiment_id: str, base: SimulationRunnerConfig, comparisons: tuple[GenerationalComparison, ...], seed_matrix: ExperimentSeedMatrix, max_ticks: int)`. Validate type of `base` and `seed_matrix`, positive exact `max_ticks`, non-empty comparisons, unique `comparison_id`, and at most one comparison per axis.
6. Keep construction side-effect free. Emit `INFO generational_comparison_spec_built` with `experiment_id`, `comparison_count`, `axis_count`, and `max_ticks`; never log agent ids or config payloads.
7. Add a module `__all__` and export `GenerationalComparisonAxis`, `GenerationalAxisLevel`, `GenerationalComparison`, `GenerationalComparisonSpec`, `GenerationalComparisonError`, and `AXIS_LEVEL_IDS` from `src/experiments/__init__.py`. Keep the facade import limited to this model module; do not import `experiments.catalog`, `experiments.matrix_*`, or any simulation runtime module here. Imports are limited to `experiments.models` for `ExperimentSeedMatrix` and `simulation.runner_models` for the config type.

### Required Interfaces and Contracts

```python
class GenerationalComparisonAxis(StrEnum):
    LIFESPAN = "lifespan"
    ...

AXIS_LEVEL_IDS: Final[Mapping[GenerationalComparisonAxis, frozenset[str]]]

@dataclass(frozen=True, slots=True)
class GenerationalComparison:
    comparison_id: str
    axis: GenerationalComparisonAxis
    control_level_id: str
    treatment_level_id: str
    label_code: str

@dataclass(frozen=True, slots=True)
class GenerationalComparisonSpec:
    experiment_id: str
    base: SimulationRunnerConfig
    comparisons: tuple[GenerationalComparison, ...]
    seed_matrix: ExperimentSeedMatrix
    max_ticks: int
```

Invariant: a spec never carries free-form numeric parameters. Every level's numeric meaning is owned by `generational_axes.py` in Tasks 2-3.

### Error Handling and Logging

- Unknown axis, unknown level, duplicate comparison id, duplicate axis, equal control/treatment, non-positive ticks, or wrong type raise `GenerationalComparisonError` with codes `unknown_axis`, `unknown_level`, `duplicate_comparison_id`, `duplicate_axis`, `identical_levels`, `invalid_max_ticks`, or `invalid_type`.
- `WARNING` entries contain only stable reason codes and ids. `DEBUG` may record the resolved axis/level counts.
- Sensitive fields: none in this task; still never log a full runner config.

### Tests

Create `tests/unit/test_generational_comparison_models.py`:

- Valid spec with five distinct axes and a single seed.
- Unknown level and unknown axis each raise the expected code.
- Duplicate comparison id and duplicate axis each fail.
- Control equal to treatment fails.
- `max_ticks` of zero/negative/bool fails.
- `AXIS_LEVEL_IDS` covers exactly `frozenset(GenerationalComparisonAxis)` and every level set is non-empty.
- A spec built twice from equal values compares equal (frozen dataclass).
- `from experiments import GenerationalComparisonAxis, GenerationalComparisonSpec` succeeds.

Command:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_comparison_models.py -q
```

### Acceptance Criteria

- The axis/level tables are closed and importable without touching the matrix registry.
- Invalid specs fail before any config is cloned or run.
- No new schema identifier, flag, command, or event is introduced.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_comparison_models.py -q`
- Expected: all tests pass; no warnings-as-errors failures.

## Task 2: Implement population, lifespan, records, migration, and scarcity axes

### Intent

Implement the run-level axes that change objective configuration while preserving world identity and founder comparability. These applicators are the only place that knows the exact preset values.

### Implementation Steps

1. Create `src/experiments/generational_axes.py` with `apply_generational_level(config, axis, level_id) -> SimulationRunnerConfig`.
2. Implement `_require_generational_base(config)`:
   - require `type(config) is SimulationRunnerConfig`;
   - require `config.schema_version == RUNNER_SCHEMA_VERSION_V55`;
   - require `config.generational_run is not None`, `config.population_lifecycle is not None`, `config.new_agent_initialization is not None`;
   - otherwise raise `GenerationalComparisonError("generational_base_required")`.
   This helper is called by every applicator, including matrix reuse.
3. Implement `_replace_lifecycle(config, *, lifespan_ticks=None, max_population=None, entries_per_interval=None)`:
   - use `dataclasses.replace` on `PopulationLifecycleSpec`;
   - when lifespan changes, rebuild `stage_thresholds` exactly as `(infant, 2)`, `(juvenile, 4 for short / 6 for long)`, `(adult, lifespan_ticks - 1)` and keep `dependent_until_stage=juvenile`;
   - preserve `demographic_policy_id`, `interval_ticks`, `generation_length_ticks`, `name_prefix`, `cohort_id_prefix`, and `spawn_location_ids`;
   - copy `demographic_policy_params` into a mutable dict, change only `entries_per_interval` when requested, and pass a new mapping;
   - never change `lifespan_distribution` or gradual-aging settings.
4. Implement lifespan presets:
   - `short`: `lifespan_ticks=8`, stage thresholds `(2, 4, 7)`.
   - `long`: `lifespan_ticks=24`, stage thresholds `(2, 6, 23)`.
5. Implement population-size presets on top of the existing schedule:
   - `small`: `max_population=6`, `entries_per_interval=1`.
   - `large`: `max_population=10`, `entries_per_interval=2`.
   - Keep `interval_ticks=2`, `generation_length_ticks=4`, and the four canonical AY spawn locations from the base.
6. Implement record availability:
   - `absent`: `replace(config, durable_records=None)`; keep `cultural_historical_memory` and any existing `cultural_feature_provenance` unchanged.
   - `present`: set `cultural_historical_memory=True`; if `cultural_feature_provenance is None`, set `example_cultural_feature_provenance_spec()`; set `durable_records=example_durable_records_spec(default_fidelity="perfect", perception_mode="marks_and_meta")`.
   - Keep all other flags/siblings unchanged.
7. Implement migration:
   - `isolated`: `replace(config, v3_capability_flags=replace(flags, multi_polity_migration=False), regions_migration=None)`. This level is idempotent and needs no template.
   - `connected`: require the current config to carry a `regions_migration` template; otherwise raise `GenerationalComparisonError("migration_template_required")`. Return `replace(config, v3_capability_flags=replace(flags, multi_polity_migration=True), regions_migration=template)`. This level is idempotent when a template is present.
   - Do not edit the scenario, routes, or agent ids.
8. Implement resource scarcity by proportional scaling:
   - `scarce`: factor `0.5`; `abundant`: factor `1.5`.
   - For every `Resource`, replace `quantity`, `maximum_quantity`, and `regeneration_per_tick` with `value * factor`, using finite non-negative floats. Preserve `entity_id`, `name`, `kind`, `location_id`, and `unit`.
   - Because `quantity` is scaled with `maximum_quantity`, the existing `quantity <= maximum_quantity` invariant remains true. Do not introduce a new `Resource` model.
   - Raise `GenerationalComparisonError("resource_scarcity_layout_empty")` if there are no resources.
9. Log `DEBUG generational_axis_applied` with `axis`, `level_id`, and a bounded field name/count (for example `resource_count`, `lifespan_ticks`, `max_population`). Do not log resource values or full configs.
10. Every branch returns a new immutable config and must leave `seed`, `stochastic_identity`, `scenario` (except resource values), `agents`, `stop_policy`, `generational_run`, and `schema_version` unchanged.

### Required Interfaces and Contracts

```python
def apply_generational_level(
    config: SimulationRunnerConfig,
    axis: GenerationalComparisonAxis | str,
    level_id: str,
) -> SimulationRunnerConfig: ...
```

- Accept a `str` axis and convert through `GenerationalComparisonAxis`; unknown axes raise `unknown_axis`.
- Accept levels only from `AXIS_LEVEL_IDS`.
- The returned config must still satisfy `SimulationRunnerConfig.__post_init__` for v55.
- No applicator may set `schema_version`.

### Error Handling and Logging

- Wrong base type/schema/missing generational fields: `generational_base_required`.
- Missing migration template on `connected`: `migration_template_required`; `isolated` does not require one.
- Empty resources: `resource_scarcity_layout_empty`.
- Invalid population/lifespan consistency is surfaced by `PopulationLifecycleSpec`; do not catch or rewrite it.
- Logging is metadata-only and bounded; no payload dumps.

### Tests

Create `tests/unit/test_generational_axes_population.py` using a helper that builds a minimal valid v55 base from `regional_migration_scenario` or a tiny synthetic v55 config:

- Lifespan short/long change only lifecycle lifespan/stages; seed, scenario, agents, stop policy, generational run, and schema are unchanged.
- Population size small/large change `max_population` and `entries_per_interval`; interval, generation length, and spawn locations are unchanged.
- Record absent removes `durable_records`; present sets the flag, provenance, and durable spec; both roundtrip through `encode_runner_config`/`decode_runner_config`.
- Migration isolated disables the flag and removes regions; connected restores the template; both preserve the scenario; connected on a config without a template raises `migration_template_required`.
- Scarcity scarce/abundant scale every resource quantity/max/regeneration and preserve ids/locations/kinds; `quantity <= maximum_quantity` holds.
- Applying an axis to a v4 config raises `generational_base_required`.
- Applying each level twice is idempotent for lifespan, population size, record availability, and migration; scarcity is multiplicative by design and is applied once per level.

Command:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_axes_population.py -q
```

### Acceptance Criteria

- Task 2 axes produce exact, documented presets without changing the v55 schema or founder world.
- Resource scarcity is quantifiable and layout-preserving.
- Every applicator fails closed outside a v55 generational base.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_axes_population.py -q`
- Expected: all tests pass and every encoded config decodes to an equal value.

## Task 3: Implement cognition, teaching, innovation, institution, and architecture axes

### Intent

Implement the per-agent and mode-only axes, including a v55-preserving architecture helper. This task must not reuse `_with_agent_modes`, because that helper rebuilds a v4-era config and drops newer fields and V3 siblings.

### Implementation Steps

1. In `src/experiments/generational_axes.py`, add `_replace_cognition(config, **changes)` that maps every `AgentRunnerSpec` through `dataclasses.replace(agent, cognition=replace(agent.cognition, **changes))`. It must preserve agent id, body id, name, and initial goals.
2. Implement memory architecture:
   - `reference` -> `MemoryMode.REFERENCE`.
   - `reconstructive` -> `MemoryMode.RECONSTRUCTIVE_V2`.
   - Change only `memory_mode` on every agent.
3. Implement learning model:
   - `practice_only`: set `skill_learning_mode=SkillLearningMode.DETERMINISTIC` and `teaching_interaction_mode=TeachingInteractionMode.DISABLED`.
   - `teaching_supported`: set both to `DETERMINISTIC` and restore the default teaching rates `offer_window=8`, `demonstration_rate=0.02`, `practice_together_rate=0.02`, `teaching_response_weight=0.25`.
   - Do not change communication strategy, reputation, or memory mode.
4. Implement teaching frequency:
   - Both levels set `skill_learning_mode=DETERMINISTIC` and `teaching_interaction_mode=DETERMINISTIC`.
   - `low`: `offer_window=4`, `demonstration_rate=0.01`, `practice_together_rate=0.01`, `teaching_response_weight=0.10`.
   - `high`: `offer_window=12`, `demonstration_rate=0.06`, `practice_together_rate=0.06`, `teaching_response_weight=0.40`.
5. Implement innovation rate:
   - Both levels set `skill_learning_mode=DETERMINISTIC`.
   - `low`: `practice_rate=0.01`, `success_rate=0.03`, `failure_rate=0.02`, `instruction_rate=0.02`, `observation_rate=0.005`, `probability_gain=0.35`, `efficiency_gain=0.35`.
   - `high`: `practice_rate=0.08`, `success_rate=0.12`, `failure_rate=0.005`, `instruction_rate=0.08`, `observation_rate=0.03`, `probability_gain=0.65`, `efficiency_gain=0.65`.
   - Leave belief rates, goal behavior, and prompts untouched. This is an acquisition-rate proxy, not a new innovation authority.
6. Implement institution support:
   - `off`: every agent `institution_concept_mode=DISABLED`, `office_succession_mode=DISABLED`.
   - `on`: every agent `institution_concept_mode=DETERMINISTIC`, `office_succession_mode=DETERMINISTIC`.
   - Leave institutional memory, decay, collective decisions, and mediation exactly as the base has them.
7. Add `apply_architecture_modes(base, architecture_id)` to `src/experiments/architectures.py`:
   - call `get_architecture(architecture_id)` and read `definition.capabilities.required_modes`;
   - map each agent through `dataclasses.replace` for `memory_mode`, `imagination_mode`, `reflection_mode`, and `prospective_mode` only;
   - set `capability_flags=_flags_for_definition(definition)` and `mortality_mode=MortalityMode(modes["mortality_appraisal"])`;
   - preserve `seed`, `stochastic_identity`, `scenario`, `agents` identities, `stop_policy`, `v3_capability_flags`, `population_lifecycle`, `new_agent_initialization`, `generational_run`, persistence, provider, and every other sibling;
   - do **not** set `schema_version`;
   - validate with `mode_snapshot_from_runner_config` and `validate_architecture_compatibility`;
   - log `INFO architecture_modes_applied architecture_id=... schema_version=<unchanged> mode_count=4`.
8. In `generational_axes.py`, map `v1_memory` -> `v1_memory_agent` and `full_v2` -> `full_v2_agent`, call `apply_architecture_modes`, then assert the returned config still has the original `schema_version`, seed, scenario, agents ids/body ids, lifecycle, initialization, and generational run. Raise `GenerationalComparisonError("architecture_mutation")` if any invariant fails.
9. Do not import `experiments.catalog` from `architectures.py` or `generational_axes.py`. The new helper uses only `simulation.cognition_contracts` and local architecture helpers already present in `architectures.py`.

### Required Interfaces and Contracts

```python
# src/experiments/architectures.py
def apply_architecture_modes(
    base: SimulationRunnerConfig, architecture_id: str
) -> SimulationRunnerConfig: ...

# src/experiments/generational_axes.py
def apply_generational_level(
    config: SimulationRunnerConfig,
    axis: GenerationalComparisonAxis | str,
    level_id: str,
) -> SimulationRunnerConfig: ...
```

Invariants:

- `schema_version` is unchanged for every Task 3 axis.
- Agent ids, body ids, names, and initial goals are unchanged.
- `population_lifecycle`, `new_agent_initialization`, `generational_run`, `regions_migration`, and all V3 flags are preserved.
- Architecture application is mode-only and never invents a runner `architecture_id` schema key.

### Error Handling and Logging

- Unknown architecture id is surfaced by `get_architecture` and wrapped as `GenerationalComparisonError("unknown_architecture")`.
- Any invariant mutation raises `architecture_mutation` after logging the field names that changed, never values.
- Teaching/innovation levels set skill learning deterministically; the matrix layer later rejects contradictory combinations instead of silently overriding another factor.
- Logging is metadata-only: axis, level, architecture id, and changed field names.

### Tests

Create `tests/unit/test_generational_axes_cognition.py`:

- Memory reference/reconstructive change only `memory_mode`.
- Learning practice-only/teaching-supported set the exact modes; teaching rates restore defaults for teaching-supported.
- Teaching low/high set the exact four rate fields and keep skill learning deterministic.
- Innovation low/high set the exact seven rate fields.
- Institution off/on set exactly the two modes and preserve institutional memory/decay.
- Architecture v1_memory/full_v2 preserve `schema_version`, seed, scenario, agents ids/body ids, lifecycle, init, regions, flags, and generational run; mode fields match the registered definition.
- Applying each level twice is idempotent.
- A v4 base raises `generational_base_required` for all axes.

Command:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_axes_cognition.py -q
```

### Acceptance Criteria

- All requested cognitive variables have exact, closed presets.
- Architecture comparison works on v55 without dropping newer config fields.
- No schema version, world, founder roster, or generational schedule changes.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_axes_cognition.py -q`
- `uv run --frozen --python 3.12.14 mypy src/experiments/generational_comparison_models.py src/experiments/generational_axes.py src/experiments/architectures.py`
- Expected: tests pass, typing is clean, and encoded v55 configs decode unchanged.

## Phase Risks and Mitigations

- Risk: a new axis accidentally changes `schema_version` or drops a V3 sibling.
  Mitigation: every applicator goes through `dataclasses.replace` and the Task 3 architecture helper has explicit preservation assertions.
- Risk: lifespan preset thresholds do not cover the assigned lifespan.
  Mitigation: rebuild `stage_thresholds` with the final adult threshold at `lifespan_ticks - 1` and test `PopulationLifecycleSpec` construction.
- Risk: record availability leaves flag/provenance inconsistent.
  Mitigation: `present` sets the flag and provenance before `durable_records`; `absent` removes only the durable sibling.
- Risk: resource scaling rounds in a way that violates `quantity <= maximum`.
  Mitigation: scale both fields with the same float factor and assert the invariant in tests.
- Risk: architecture modes conflict with a required flag not owned by the experiment layer.
  Mitigation: use only registered architecture definitions and `validate_architecture_compatibility`.

## Phase Completion Checklist

- Every Task 1-3 section satisfies its acceptance criteria.
- `tests/unit/test_generational_comparison_models.py`, `test_generational_axes_population.py`, and `test_generational_axes_cognition.py` pass.
- No adapter imports cross package boundaries; `experiments` does not import `analysis`, `api`, or persistence.
- `index.md` task checkboxes are updated immediately after verified completion.
