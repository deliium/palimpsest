# Phase 2: Scenario, base, and matrix composition

Plan: [index.md](index.md)
Tasks: 4-7
Depends on: Phase 1 / Tasks 1-3

## Objective

Turn the closed axis engine into usable experiment configuration: one canonical rich v55 base, one generic pair builder, one off-gate BM experiment with the five requested examples, and matrix factors that reuse the same axis implementation with fail-closed compatibility checks.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/generational_runner_scenario.py` | `_lifecycle` (46), `_config` (78), `generational_runner_scenario` (109) | Existing v55 generational scenario; BL is the closest real-world reference. |
| `src/experiments/regional_migration_scenario.py` | `regional_migration_scenario` (305), AY condition configs | Real AY world, four founders, regions/routes, and a regional diagnostic arbiter. |
| `src/experiments/models.py` | `ExperimentDefinition` (71), `__post_init__` (94-126), `_scenario_layout` (46) | Comparability and resource-stripped layout contract. |
| `src/experiments/catalog.py` | `OFF_GATE_MATRIX_EXPERIMENT_IDS` (2754), `experiment_bl_generational_runner` (5520) | Registration and off-gate pattern. |
| `src/experiments/__init__.py` | catalog imports/`__all__` | Public facade; new BM builder must be exported. |
| `src/experiments/matrix_models.py` | `MatrixFactorId` (49), `LOCKED_FACTOR_LEVEL_IDS` (37), `MatrixFactorLevel` (189) | Closed matrix axes and discrete levels. |
| `src/experiments/matrix_factors.py` | `_APPLICATORS` (302), `apply_factor_level` (324), `apply_factor_levels` (359) | Factor dispatch and schema-preservation rule. |
| `src/experiments/matrix_expand.py` | `expand_matrix` (95), `_resolve_base` (31) | Expansion/finalize order and embedded-base requirement. |
| `src/experiments/matrix_schema.py` | v55 first branch (152) | Existing highest-wins select; no new schema branch is needed. |
| `src/experiments/matrix_serialization.py` | `encode_matrix_spec`, `decode_matrix_spec` (432) | Strict factor-id/level decoding. |
| `src/simulation/new_agent_initialization.py` | `default_new_agent_initialization_spec` (833) | Default fixed/`none` initialization used for comparability. |
| `src/simulation/generational_models.py` | `GenerationalRunSpec` (573), generation stop semantics | Keep the same run contract across axes. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/generational_comparison_base.py` | create | Canonical v55 base builder and comparability invariant. |
| `src/experiments/generational_comparison.py` | create | Generic pair builder from `GenerationalComparisonSpec`. |
| `src/experiments/generational_comparison_scenario.py` | create | BM experiment with five paired examples. |
| `src/experiments/catalog.py` | modify | Add `experiment_bm_generational_comparison` and off-gate id. |
| `src/experiments/__init__.py` | modify | Export the BM builder. |
| `src/experiments/matrix_models.py` | modify | Add ten generational matrix factor ids and locked level tables. |
| `src/experiments/matrix_factors.py` | modify | Delegate factor levels to `apply_generational_level` and add compatibility validation. |
| `src/experiments/matrix_expand.py` | modify | Validate factor combinations and generational comparability before returning. |
| `tests/unit/test_generational_comparison_base.py` | create | Base and comparability tests. |
| `tests/unit/test_experiment_bm.py` | create | BM construction/registration tests. |
| `tests/unit/test_generational_matrix_factors.py` | create | Factor application, compatibility, and serialization tests. |

## Task 4: Add the canonical generational comparison base and comparability gate

### Intent

Create one reusable v55 base that is rich enough for all requested comparisons, and one invariant that prevents a pair from claiming comparable initial conditions when seed, world, founder roster, schedule, or initialization differ.

### Implementation Steps

1. Create `src/experiments/generational_comparison_base.py`.
2. Implement `generational_comparison_base(*, seed: int = 23, max_ticks: int = 12, base: SimulationRunnerConfig | None = None) -> SimulationRunnerConfig`:
   - If `base is None`, call `regional_migration_scenario(seed=seed, max_ticks=max_ticks)` and select the `ay-accurate-evidence` condition.
   - If `base` is supplied, require `type(base) is SimulationRunnerConfig` and `base.regions_migration is not None`; otherwise raise `ValueError("generational_base_scenario_required")`.
   - Require `max_ticks >= 8`; otherwise raise `ValueError("generational_base_horizon_too_short")`.
   - Start from `seed_config = selected_or_supplied_config`.
   - Replace the run-level contract:
     - `schema_version = RUNNER_SCHEMA_VERSION_V55`;
     - `mortality_mode = MortalityMode.ENABLED`;
     - `stop_policy = RunnerStopPolicy(max_ticks=max_ticks, stop_on_all_agents_terminal=False)`;
     - `v3_capability_flags = V3CapabilityFlags(generational_population=True, multi_polity_migration=True, cultural_historical_memory=True)` (all other V3 flags false);
     - `population_lifecycle = _base_lifecycle(_spawn_locations(seed_config.scenario))`;
     - `new_agent_initialization = default_new_agent_initialization_spec()`;
     - `cultural_feature_provenance = example_cultural_feature_provenance_spec()`;
     - `durable_records = None`;
     - `generational_run = GenerationalRunSpec(max_generation_index=6, stop_on_extinction=False, criterion_cadence_ticks=1)`.
   - Replace each agent cognition with `dataclasses.replace` preserving every field, then set `skill_learning_mode=DETERMINISTIC`, `teaching_interaction_mode=DETERMINISTIC`, and `communication_strategy_mode=DETERMINISTIC`. This makes the oral-transmission control meaningful while leaving memory/imagination/reflection at the AY defaults.
   - Preserve the AY `regions_migration` template, scenario, seed, and stochastic identity.
   - Emit `INFO generational_comparison_base_built seed_status=provided|ay max_ticks=... agent_count=... resource_count=...` without logging ids or payloads.
3. Implement `_spawn_locations(scenario: WorldScenarioSpec) -> tuple[str, ...]`:
   - preserve the canonical AY order when every one of `loc-origin`, `loc-spring`, `loc-grain`, `loc-remote` exists;
   - otherwise return the first up-to-four scenario location ids in declared order;
   - require at least one location and raise `ValueError("generational_base_spawn_locations_required")` otherwise.
4. Implement `_base_lifecycle(spawn_location_ids: tuple[str, ...]) -> PopulationLifecycleSpec` with:
   - `lifespan_ticks=12`;
   - stages `(infant, 2)`, `(juvenile, 4)`, `(adult, 11)`;
   - `dependent_until_stage=juvenile`;
   - `demographic_policy_id="generational_interval_entry"`;
   - params exactly `{"interval_ticks": 2, "entries_per_interval": 1, "generation_length_ticks": 4, "name_prefix": "entrant", "cohort_id_prefix": "cohort", "spawn_location_ids": list(spawn_location_ids)}`;
   - `max_population=9`;
   - `natural_death_on_lifespan=True`;
   - `lifespan_distribution=default_lifespan_distribution_spec()`.
5. Implement `assert_comparable_generational_conditions(conditions: Sequence[SimulationRunnerConfig], *, allow_population_size: bool = False) -> None`:
   - Require at least two configs, all `SimulationRunnerConfig`, all v55, and all with `generational_run is not None`.
   - Compare seed, stochastic identity, and derivation version; raise `comparison_seed_mismatch`/`comparison_identity_mismatch`.
   - Compare world id/revision/physical rules/locations/bodies/weather; raise `comparison_scenario_mismatch`.
   - Compare resource node identity and order (`entity_id`, `name`, `kind`, `location_id`, `unit`); allow only quantity/maximum/regeneration differences; raise `comparison_resource_identity_mismatch`.
   - Compare agent ids, body ids, names, and initial goals in order; raise `comparison_roster_mismatch`.
   - Compare `stop_policy`; raise `comparison_stop_policy_mismatch`.
   - Compare lifecycle `demographic_policy_id` and the schedule keys `interval_ticks`, `generation_length_ticks`, `name_prefix`, `cohort_id_prefix`, and `spawn_location_ids`; raise `comparison_schedule_mismatch`.
   - Compare `population_lifecycle.max_population` and `demographic_policy_params["entries_per_interval"]`; when they differ, require `allow_population_size=True`, otherwise raise `comparison_population_capacity_mismatch`. Provide the keyword `allow_population_size: bool = False`; the generic pair builder passes `True` only for a `population_size` comparison.
   - Compare lifecycle `dependent_until_stage`, `natural_death_on_lifespan`, `stage_capability_effects`, `gradual_aging`, and all remaining `demographic_policy_params` keys; raise `comparison_lifecycle_mismatch`. `lifespan_ticks`/`stage_thresholds` and population capacity/entry rate are the only lifecycle fields allowed to differ, and only for their declared axes.
   - Compare `generational_run`; raise `comparison_generational_run_mismatch`.
   - Compare `new_agent_initialization`; raise `comparison_initialization_mismatch`.
   - Require `population_lifecycle.lifespan_distribution.is_passthrough_default()`; raise `comparison_lifespan_distribution_not_passthrough`.
   - Require `new_agent_initialization.parameter_distributions.distribution_id == "none"` and empty params; raise `comparison_initialization_not_deterministic`.
   - Emit `INFO generational_comparison_comparable condition_count=...` only after every check passes.
6. Add `assert_comparable_generational_pair(control, treatment, *, allow_population_size=False)` that delegates to the sequence function.
7. Keep this module free of analysis imports and runtime execution.

### Required Interfaces and Contracts

```python
def generational_comparison_base(
    *, seed: int = 23, max_ticks: int = 12,
    base: SimulationRunnerConfig | None = None,
) -> SimulationRunnerConfig: ...

def assert_comparable_generational_conditions(
    conditions: Sequence[SimulationRunnerConfig],
    *,
    allow_population_size: bool = False,
) -> None: ...

def assert_comparable_generational_pair(
    control: SimulationRunnerConfig,
    treatment: SimulationRunnerConfig,
    *,
    allow_population_size: bool = False,
) -> None: ...
```

Invariants:

- The canonical base uses a real AY-derived scenario, four founders, up to four scenario spawn locations, and an enabled regional template.
- The base has no durable records, institution-support modes, or institutional-economy flag.
- The base has teaching, skill learning, and communication enabled in every arm; record availability is the only difference in the oral-vs-records pair.
- The base's lifespan and initialization distributions are passthrough/fixed.

### Error Handling and Logging

- Stable `ValueError` codes listed above; never use bare assertions for user-visible validation.
- `INFO` logs bounded counts only. `DEBUG` may report `seed_status`, `lifespan_ticks`, `max_population`, and presence booleans.
- Do not log agent ids, resource values, or the encoded config.

### Tests

Create `tests/unit/test_generational_comparison_base.py`:

- Base is v55, generational, AY-derived, mortality enabled, finite ticks, stop-on-terminal false, flag set exact, provenance present, durable absent.
- Base agents have skill learning, teaching, and communication deterministic; all agent ids/body ids are the AY four.
- Lifecycle schedule is exact; max population 9; fixed lifespan distribution; default `none` initialization.
- A non-AY base with different location ids uses up to four declared locations for spawns; a base with no locations fails `generational_base_spawn_locations_required`.
- Encode/decode roundtrip equals the base.
- Comparability passes for two identical configs.
- Seed, stochastic identity, scenario location, body, agent id, stop policy, schedule, lifecycle non-treatment fields, `generational_run`, initialization, and non-passthrough lifespan each fail with the expected code.
- Resource quantity differences pass; resource id/location differences fail.
- `allow_population_size=True` permits the entries/max-population difference; `allow_population_size=False` rejects a capacity-only difference with `comparison_population_capacity_mismatch`; a changed interval/generation length still fails.

Command:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_comparison_base.py -q
```

### Acceptance Criteria

- A single canonical base supports all five BM comparisons and the matrix factors.
- Comparable pairs are enforced by code, not documentation.
- The base roundtrips as v55 and does not require a new schema.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_comparison_base.py -q`
- Expected: all base, negative, and roundtrip tests pass.

## Task 5: Add the generic pair builder and BM experiment

### Intent

Provide the reusable composition API and the concrete off-gate BM experiment requested by the user. The builder must build independent pairs, not a Cartesian product, so each treatment differs from its control by exactly one declared axis.

### Implementation Steps

1. Create `src/experiments/generational_comparison.py`.
2. Implement `build_generational_comparison(spec: GenerationalComparisonSpec) -> ExperimentDefinition`:
   - Validate spec type.
   - Require `spec.base.stop_policy.max_ticks == spec.max_ticks`; otherwise raise `GenerationalComparisonError("comparison_horizon_mismatch")`. This keeps the immutable spec horizon and the runner stop policy from drifting.
   - For each comparison in order:
     - `control_config = apply_generational_level(spec.base, comparison.axis, comparison.control_level_id)`;
     - `treatment_config = apply_generational_level(spec.base, comparison.axis, comparison.treatment_level_id)`;
     - condition ids `f"{comparison.comparison_id}-control"` and `f"{comparison.comparison_id}-treatment"`;
     - label codes `f"{comparison.label_code}_control"` and `f"{comparison.label_code}_treatment"`.
   - Build `ExperimentCondition` objects in comparison order.
   - For each pair, call `assert_comparable_generational_pair(control_config, treatment_config, allow_population_size=(comparison.axis is GenerationalComparisonAxis.POPULATION_SIZE))`. This lets a population-size pair change capacity/entry rate while every other pair must keep the schedule identical.
   - After all conditions are built, call `assert_comparable_generational_conditions(all_configs, allow_population_size=True)` to enforce the cross-pair invariants (seed, identity, scenario, roster, stop policy, generation run, initialization, and schedule except the explicitly allowed population-size entries). This supports a generic spec that mixes population size with other axes without weakening per-pair checks.
   - Build `ExperimentDefinition(experiment_id=spec.experiment_id, schema_version=EXPERIMENT_SCHEMA_VERSION, seed_matrix=spec.seed_matrix, conditions=..., paired_world_group=f"{spec.experiment_id}-paired-world")`.
   - Log `INFO generational_comparison_built experiment_id=... comparison_count=... condition_count=...`.
3. Create `src/experiments/generational_comparison_scenario.py`:
   - `EXPERIMENT_ID: Final[str] = "generational_comparison@1"`.
   - `generational_comparison_scenario(*, seed: int = 23, max_ticks: int = 12, seed_matrix: ExperimentSeedMatrix | None = None, base: SimulationRunnerConfig | None = None) -> ExperimentDefinition`.
   - Build the canonical base via `generational_comparison_base(seed=seed, max_ticks=max_ticks, base=base)`.
   - `matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base_config.seed,))`.
   - Define exactly five comparisons:
     - `bm-oral-vs-records`: `RECORD_AVAILABILITY`, control `absent`, treatment `present`, label `oral_transmission_vs_durable_records`.
     - `bm-short-vs-long-lifespan`: `LIFESPAN`, control `short`, treatment `long`, label `short_vs_long_lifespan`.
     - `bm-isolated-vs-connected`: `MIGRATION`, control `isolated`, treatment `connected`, label `isolated_vs_connected_groups`.
     - `bm-low-vs-high-teaching`: `TEACHING_FREQUENCY`, control `low`, treatment `high`, label `low_vs_high_teaching`.
     - `bm-reference-vs-reconstructive-memory`: `MEMORY_ARCHITECTURE`, control `reference`, treatment `reconstructive`, label `reference_vs_reconstructive_memory`.
   - Call `build_generational_comparison`.
   - Log `INFO generational_scenario_built experiment_id=... arms=10 max_ticks=...`.
4. Modify `src/experiments/catalog.py`:
   - Add `experiment_bm_generational_comparison(base, *, seed_matrix=None, max_ticks=12)` using the lazy import pattern from BL; ignore `seed_matrix` only if the scenario supports its own. Prefer passing `seed_matrix` through to the scenario.
   - Add `"generational_comparison@1"` to `OFF_GATE_MATRIX_EXPERIMENT_IDS`.
   - Log `experiment_registered experiment_id=generational_comparison@1 arms=10`.
5. Modify `src/experiments/__init__.py` to import and export `experiment_bm_generational_comparison`, `generational_comparison_scenario`, `build_generational_comparison`, `generational_comparison_base`, `assert_comparable_generational_conditions`, and `assert_comparable_generational_pair`; add every name to `__all__`.
6. No coordinator or matrix-runner dispatch change is required: BM uses ordinary `SimulationRunner.from_config`, and v55 matrix execution still uses the existing generational context path.

### Required Interfaces and Contracts

```python
def build_generational_comparison(
    spec: GenerationalComparisonSpec,
) -> ExperimentDefinition: ...

EXPERIMENT_ID: Final[str] = "generational_comparison@1"

def generational_comparison_scenario(
    *, seed: int = 23, max_ticks: int = 12,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition: ...
```

Condition ids are exactly:

```text
bm-oral-vs-records-control
bm-oral-vs-records-treatment
bm-short-vs-long-lifespan-control
bm-short-vs-long-lifespan-treatment
bm-isolated-vs-connected-control
bm-isolated-vs-connected-treatment
bm-low-vs-high-teaching-control
bm-low-vs-high-teaching-treatment
bm-reference-vs-reconstructive-memory-control
bm-reference-vs-reconstructive-memory-treatment
```

### Error Handling and Logging

- Duplicate condition ids or duplicate comparison ids are rejected before `ExperimentDefinition` creation.
- A comparability failure propagates the stable code from Task 4.
- `INFO` logs the experiment id, arm count, and max ticks. Never log configs or agent ids.
- BM stays off the V1 A–E gate; it must not be added to `v1_regression_profile` or V1 condition ids.

### Tests

Create `tests/unit/test_experiment_bm.py`:

- Scenario builds exactly ten conditions in the ordered five-pair set.
- Every condition is v55, generational, finite ticks, stop-on-terminal false, same seed/stochastic identity, and comparability passes.
- Each pair has exactly one axis difference:
  - record control has no durable records, treatment has durable records;
  - lifespan short/long have the exact ticks/stages;
  - isolated has no regions/flag, connected has both;
  - teaching low/high have the exact rates;
  - memory reference/reconstructive have the expected `MemoryMode`.
- All non-treatment fields (agents ids/bodies, scenario, stop policy, lifecycle schedule, generational run, initialization) are equal within each pair.
- `condition_fingerprint` is deterministic across two builds; control/treatment fingerprints differ.
- A generic spec mixing `POPULATION_SIZE` with `LIFESPAN` passes per-pair comparability, while a non-population pair with a changed `interval_ticks` still fails.
- `"generational_comparison@1"` is in `OFF_GATE_MATRIX_EXPERIMENT_IDS`.
- `experiment_bm_generational_comparison`, `generational_comparison_scenario`, and `build_generational_comparison` are importable from `experiments`.
- Invalid `max_ticks < 8` fails, and a spec whose `max_ticks` disagrees with `base.stop_policy.max_ticks` fails with `comparison_horizon_mismatch`.

Command:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bm.py -q
```

### Acceptance Criteria

- BM exposes all five requested example comparisons as ten real v55 arms.
- Each pair differs by exactly one declared axis and passes the comparability gate.
- Registration is off-gate and deterministic.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bm.py -q`
- `uv run --frozen --python 3.12.14 python -c "from experiments import experiment_bm_generational_comparison"`
- Expected: tests pass and the builder is publicly importable.

## Task 6: Add generational matrix factors and compatibility validation

### Intent

Expose the same axes as locked `experiment-matrix-v1` factors, while preventing a factor from changing schema or silently overriding another factor. Existing factors and legacy matrix behavior must stay unchanged.

### Implementation Steps

1. Modify `src/experiments/matrix_models.py`:
   - Add `MatrixFactorId` members:
     - `LIFESPAN = "lifespan"`
     - `LEARNING_MODEL = "learning_model"`
     - `TEACHING_FREQUENCY = "teaching_frequency"`
     - `RECORD_AVAILABILITY = "record_availability"`
     - `INNOVATION_RATE = "innovation_rate"`
     - `MIGRATION = "migration"`
     - `POPULATION_SIZE = "population_size"`
     - `INSTITUTION_SUPPORT = "institution_support"`
     - `COGNITIVE_ARCHITECTURE = "cognitive_architecture"`
     - `GENERATIONAL_RESOURCE_SCARCITY = "generational_resource_scarcity"`
   - Add matching `LOCKED_FACTOR_LEVEL_IDS` entries using exactly the Task 1 level ids. `GENERATIONAL_RESOURCE_SCARCITY` uses `scarce`/`abundant`; it delegates to the `RESOURCE_SCARCITY` axis rather than the legacy fixed-layout applicator.
2. Modify `src/experiments/matrix_factors.py`:
   - Import `apply_generational_level` and the axis enum.
   - Add `_apply_generational_axis(axis)` returning a level table that calls `apply_generational_level(config, axis, level_id)`.
   - Register the ten new factors in `_APPLICATORS`.
   - Keep `apply_factor_level`'s `factor_mutated_schema_version` check unchanged.
3. Add `validate_generational_factor_combination(config, levels: tuple[tuple[str, str], ...]) -> None`:
   - Return immediately when `config.generational_run is None`.
   - Build `selected = dict(levels)`.
   - If `teaching_frequency` is selected and the effective config has any agent with `teaching_interaction_mode != DETERMINISTIC` or `skill_learning_mode != DETERMINISTIC`, raise `MatrixValidationError("incompatible_factor_combination")`.
   - If `innovation_rate` is selected and any agent has `skill_learning_mode != DETERMINISTIC`, raise the same code.
   - If `record_availability == "present"` and either `cultural_historical_memory` is false or `cultural_feature_provenance is None`, raise `incompatible_factor_combination`.
   - If `record_availability == "absent"` and `knowledge_repositories is not None`, raise `incompatible_factor_combination` because repositories require durable records.
   - If `migration == "connected"` and `regions_migration is None`, raise `incompatible_factor_combination`.
   - If `migration == "isolated"` and `cultural_contact is not None`, raise `incompatible_factor_combination` because contact requires regional physics.
   - If `learning_model == "practice_only"` and either teaching/innovation is selected or `mentorship is not None`, raise `incompatible_factor_combination`.
   - If `institution_support == "off"` and any agent has deterministic `institutional_memory_mode` or `institutional_decay_mode`, raise `incompatible_factor_combination` because those channels require institution/office concepts.
   - Log `DEBUG generational_factor_combination_validated factor_count=...` only on success.
4. Modify `src/experiments/matrix_expand.py`:
   - Import `validate_generational_factor_combination` and `assert_comparable_generational_conditions`.
   - After `apply_factor_levels(base, levels)`, call the compatibility validator before `finalize_matrix_cell_config`.
   - After `ExperimentDefinition` construction, if any condition has `generational_run is not None`, call `assert_comparable_generational_conditions` with `allow_population_size=True` (matrix conditions may include a population-size factor). The comparability function still rejects schedule/seed/scenario/initialization mismatches.
5. Do not change `matrix_schema.finalize_matrix_cell_config`: `generational_run` already selects v55 first. Add tests only.
6. Ensure legacy factors (`memory_type`, `mortality`, `imagination`, `reflection`, `tom`, `resource_scarcity`, `seasonality`, `cognitive_budget`) and non-v55 bases keep their existing behavior. New factors on a non-v55 base raise `generational_base_required` from the axis engine.

### Required Interfaces and Contracts

```python
def validate_generational_factor_combination(
    config: SimulationRunnerConfig,
    levels: tuple[tuple[str, str], ...],
) -> None: ...
```

- New factors are valid only on a v55 generational base.
- A factor level never changes `schema_version`, seed, stochastic identity, scenario, agent roster, or generation schedule.
- Existing `resource_scarcity` remains layout-bound and unchanged; the new scarcity factor is explicitly generational.

### Error Handling and Logging

- Missing v55 base: `MatrixValidationError("generational_base_required")`.
- Contradictory modes: `MatrixValidationError("incompatible_factor_combination")`.
- Schema mutation: existing `factor_mutated_schema_version`.
- Logging uses factor ids/levels and reason codes only; no config payloads.

### Tests

Create `tests/unit/test_generational_matrix_factors.py`:

- Every new factor and every level applies to a canonical v55 base and keeps `schema_version` v55.
- Expected config deltas match Task 2-3 presets; seed/scenario/agents/schedule are unchanged.
- Existing legacy factor tests still pass unchanged.
- `learning_model=practice_only` + `teaching_frequency=high` raises `incompatible_factor_combination`.
- `practice_only` + `innovation_rate=high` raises the same code.
- Teaching/innovation on a base with skill learning disabled but without the learning factor raises the same code.
- Record present on a v55 base without provenance adds both the flag and provenance, sets durable records, and roundtrips; a base with an unrelated contradictory cultural sibling still fails through normal config validation.
- The compatibility validator rejects a hand-constructed inconsistent config where record availability is selected but the effective flag/provenance is absent.
- Dependent-sibling conflicts fail closed: record absent + knowledge repositories, migration isolated + cultural contact, institution support off + institutional memory/decay, and practice-only + mentorship.
- New factor on a v4 base raises `generational_base_required`.
- Matrix with factors `lifespan`, `record_availability`, and `population_size` expands to v55 cells, preserves group roles, and passes comparability.
- Non-generational matrix expansion is byte-identical to the pre-change behavior for the existing fixture.

Command:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_matrix_factors.py tests/unit/test_experiment_matrix_factors.py tests/unit/test_experiment_matrix_expand.py -q
```

### Acceptance Criteria

- All requested variables are available as closed matrix axes or documented scenario-only equivalents.
- New factors cannot bypass v55 or contradict one another.
- Existing matrix behavior is unchanged for legacy bases.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_matrix_factors.py tests/unit/test_experiment_matrix_factors.py tests/unit/test_experiment_matrix_expand.py -q`
- Expected: all pass; no existing test requires modification except additive level tables if it enumerates factor ids.

## Task 7: Add matrix expansion, serialization, and schema integration tests

### Intent

Prove that the new factor ids survive the strict matrix codec, that expansion finalizes v55, and that the existing highest-wins selector still works when generational and non-generational cells coexist.

### Implementation Steps

1. Extend `tests/unit/test_generational_matrix_factors.py` or create `tests/unit/test_generational_matrix_serialization.py`.
2. Build an `ExperimentMatrixSpec` with:
   - `base = MatrixEmbeddedBase(generational_comparison_base(seed=23, max_ticks=8))`;
   - factors `lifespan` (`short`/`long`), `record_availability` (`absent`/`present`), and `population_size` (`small`/`large`);
   - explicit `MatrixFactorLevel` `group_role=CONTROL/TREATMENT`;
   - one seed and one replicate.
3. Call `encode_matrix_spec`/`decode_matrix_spec`; assert the decoded spec equals the original and the canonical JSON contains the new factor ids and level ids.
4. Call `expand_matrix`; assert:
   - every condition is `runner-config-v55`;
   - `generational_run` is preserved;
   - condition ids include the factor/level tokens;
   - control/treatment roles are composed as specified;
   - `assert_comparable_generational_conditions` passes;
   - `finalize_matrix_cell_config` did not add a new branch or schema.
5. Add negative cases:
   - unknown factor id string -> `unknown_factor_id`;
   - known new factor with unknown level -> `unknown_level_id`;
   - duplicate levels -> existing matrix validation error;
   - a non-v55 embedded base with a new factor -> `generational_base_required`.
6. Add a regression assertion that a legacy matrix built from `matrix_reference_fixture_base` still finalizes to its existing schema and does not gain generational fields.

### Required Interfaces and Contracts

- No new serialization schema; the strict codec uses the existing enum/level tables.
- `MatrixEmbeddedBase` is the only supported base for expansion; `MatrixCatalogBase` remains unresolved.
- `RunVersionIdentity` is unchanged; new factor ids participate in the existing matrix/cell fingerprints.

### Error Handling and Logging

- Serialization errors remain `MatrixSerializationError` with stable code/path.
- Expansion errors remain `MatrixValidationError` with stable codes.
- Logging is metadata-only and bounded to matrix/cell/factor counts.

### Tests

Commands:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_matrix_serialization.py tests/unit/test_generational_matrix_schema.py tests/unit/test_experiment_matrix_serialization.py tests/unit/test_experiment_matrix_schema.py -q
```

- Expected: all tests pass; encoding is deterministic; legacy schema assertions are unchanged.

### Acceptance Criteria

- New factors roundtrip through the strict matrix codec.
- Expansion preserves v55 and comparability.
- The existing highest-wins selector needs no new branch.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_matrix_serialization.py tests/unit/test_generational_matrix_schema.py tests/unit/test_experiment_matrix_serialization.py tests/unit/test_experiment_matrix_schema.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: the canonical base is too rich and accidentally changes a compared variable.
  Mitigation: the comparability gate and per-pair tests compare every non-treatment field.
- Risk: matrix factors are applied in an order that silently overrides a prior factor.
  Mitigation: validate the final effective mode combination, not just the selected tokens.
- Risk: population-size treatment changes the schedule instead of only capacity/entry rate.
  Mitigation: Task 2 changes only `max_population` and `entries_per_interval`; comparability rejects schedule changes.
- Risk: new matrix factors break strict serialization for old documents.
  Mitigation: additive enum/level entries plus explicit legacy roundtrip tests.
- Risk: BM arms need a long horizon to show effects.
  Mitigation: enforce `max_ticks >= 8`, use generation length 4, and assert structural effects and at least two generations in Task 10.

## Phase Completion Checklist

- Tasks 4-7 acceptance criteria are met.
- BM builds ten ordered, comparable v55 arms and is off-gate.
- New matrix factors roundtrip, finalize v55, and reject incompatible combinations.
- `index.md` checkboxes are updated immediately after verified completion.
