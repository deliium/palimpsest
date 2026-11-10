# Phase 6: Experiment and End-to-End

Plan: [index.md](index.md)
Tasks: 19-21
Depends on: Phase 1 Task 4, Phase 3 Task 11, Phase 4 Task 13, Phase 5 Task 17

## Objective

Register a reproducible off-gate experiment comparing chain-off and chain-on
lanes, prove the pipeline with real engine admission, commands, events, a real
snapshot, and a real API read, and lock determinism, cap bounds, and leakage.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/experiments/catalog.py` | off-gate ids 2800-2833; infra builder 5611-5630; trade builder 5651-5667; V1 gate 244-246 | Registration and gate separation |
| `src/experiments/trade_network_scenario.py` | id 31; scenario 49-87; labels 59-72 | Scenario shape |
| `src/experiments/infrastructure_networks_scenario.py` | `_with_production` 52-62; v56 replace 65-95; flags 86-88; conditions 118-128 | Exact v56/catalog scenario pattern |
| `src/experiments/models.py` | `ExperimentDefinition` 82-107 | Available definition fields |
| `src/experiments/collectors.py` | `collect_for_experiment` 1401-1425 | Dispatch |
| `src/simulation/runner_models.py` | `AgentCognitionSpec.production_knowledge_mode` 7050; catalog 7053 | Scenario inputs |
| `src/world/_production.py` | `_apply_craft` 500-564; `complete_due_jobs` 157-235 (`due_tick = tick + 1`) | Completion timing |
| `src/world/actions.py` | `Harvest` 254-269; `Craft` 272-284; `Store` 320-335 | Commands the E2E submits |
| `tests/unit/test_trade_networks_end_to_end.py` | full file | In-process E2E pattern |
| `tests/unit/test_trade_networks_determinism.py` | full file | Determinism pattern |
| `tests/unit/test_trade_networks_bounds.py` | full file | Cap/truncation pattern |
| `tests/unit/test_trade_networks_leakage.py` | full file | Leakage pattern |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/supply_chain_scenario.py` | create | `supply_chains@1` control/treatment |
| `src/experiments/catalog.py` | modify | Builder + off-gate entry |
| `tests/unit/test_supply_chain_experiment.py` | create | Scenario/gate tests |
| `tests/unit/test_supply_chain_end_to_end.py` | create | Real-engine chain → snapshot → API |
| `tests/unit/test_supply_chain_determinism.py` | create | Repeatability/restore parity |
| `tests/unit/test_supply_chain_bounds.py` | create | Caps/truncation |
| `tests/unit/test_supply_chain_leakage.py` | create | No authority/payload leakage |

## Task 19: Register off-gate `supply_chains@1` experiment

### Intent

Make the capability testable as a paired, reproducible comparison without
touching the V1 A–E gate.

### Implementation Steps

1. `src/experiments/supply_chain_scenario.py`:
   - `SUPPLY_CHAINS_EXPERIMENT_ID = "supply_chains@1"`;
   - `_with_catalog(config, catalog)` replaces each agent's
     `cognition.production_catalog` (mirroring
     `infrastructure_networks_scenario._with_production` 52-62);
   - `_with_production_knowledge(config)` sets
     `cognition.production_knowledge_mode=ProductionKnowledgeMode.DETERMINISTIC`
     for every agent;
   - `supply_chain_scenario(base, *, seed_matrix=None, max_ticks=48)` builds
     both conditions with `replace(base, schema_version=RUNNER_SCHEMA_VERSION_V56,
     mortality_mode=MortalityMode.DISABLED, stop_policy=RunnerStopPolicy(
     max_ticks=max_ticks), v3_capability_flags=V3CapabilityFlags(),
     v4_capability_flags=V4CapabilityFlags(supply_chains=<bool>))`, then applies
     the catalog and knowledge helpers;
   - control `supply-chain-off`: flag off, `example_production_catalog()`;
   - treatment `supply-chain-on`: flag on,
     `supply_chain_production_catalog(example_production_catalog())`;
   - both share seed, stochastic identity, world layout, founder roster, stop
     horizon, and initialization;
   - `ExperimentDefinition(experiment_id=..., schema_version=..., seed_matrix=...,
     conditions=(control, treatment), paired_world_group="supply-chains")`.
2. `src/experiments/catalog.py`: add
   `experiment_supply_chains(base, *, seed_matrix=None, max_ticks=48)` next to
   the trade builder, log `experiment_registered experiment_id=supply_chains@1`,
   and add `"supply_chains@1"` to `OFF_GATE_MATRIX_EXPERIMENT_IDS`. Do not add
   it to `EXPERIMENT_A_V1_CONDITION_IDS`.

### Required Interfaces and Contracts

- Conditions differ only in the flag and catalog; every other input is equal.
- No new runner schema, root field, or per-agent key.
- Off-gate and reproducible; never appears in V1 gate text.

### Requirement Evidence

- `catalog.py` 244-246/2800-2833/5611-5667; `trade_network_scenario.py` 31-87;
  `infrastructure_networks_scenario.py` 52-128; `models.py` 82-107;
  `runner_models.py` 7050/7053.
- Supported combinations: flag off/on, knowledge on/off, legacy/extended
  catalog, paired seeds.

### Error Handling and Logging

- `INFO experiment_registered experiment_id=supply_chains@1 conditions=2`.
- `WARN supply_chain_scenario_invalid reason=<code>` for a non-v56 base or an
  already-enabled flag.
- Never log catalogs or rosters.

### Tests

- `tests/unit/test_supply_chain_experiment.py`:
  `test_experiment_id`, `test_two_paired_conditions`,
  `test_conditions_share_seed_and_world`,
  `test_treatment_enables_flag_and_catalog`,
  `test_control_keeps_legacy_catalog`,
  `test_conditions_enable_production_knowledge`,
  `test_off_gate_registry_contains_id`, `test_absent_from_v1_gate`,
  `test_no_new_runner_schema`.
- `uv run pytest tests/unit/test_supply_chain_experiment.py tests/unit/test_v1_regression_gate.py -q`.

### Acceptance Criteria

- Both conditions pass `SimulationRunner.from_config` without
  `capability_unimplemented`.
- V1 gate tests stay green.
- No v57 constant exists.

### Verification

- `uv run pytest tests/unit/test_supply_chain_experiment.py tests/unit/test_v1_regression_gate.py -q` → all pass.

## Task 20: Add in-process supply-chain end-to-end coverage

### Intent

Prove the request end to end with real admission: harvest grain, craft flour and
bread, craft a tool, benefit from the tool bonus, publish a snapshot, and read it
through the API.

### Implementation Steps

1. `tests/unit/test_supply_chain_end_to_end.py` builds a deterministic world
   with one location holding `grain` (quantity 4), `wood` (2), and `stone` (2)
   resources, one agent with the extended catalog, deterministic production
   knowledge, and the flag on.
2. Submit ordinary commands:
   - `Harvest(RecipeId("harvest_grain"), grain_resource)` three times with
     enough ticks between attempts;
   - `Craft(RecipeId("mill_grain"))` twice and `Craft(RecipeId("bake_bread"))`
     once;
   - `Harvest(RecipeId("harvest_wood"))`, `Harvest(RecipeId("harvest_stone"))`,
     `Craft(RecipeId("craft_plank"))`, `Craft(RecipeId("craft_tool_head"))`,
     `Craft(RecipeId("assemble_tool"))`.
   Multi-tick crafts are `CraftStarted` in tick T and complete on tick **T+1**
   (`ProductionJob.due_tick = tick + 1`); advance one tick per pending job.
3. Assert committed events: `ResourceHarvested`, `CraftStarted`, `ItemCrafted`
   with the expected recipe ids; the harvest submitted while holding
   `fine_tool` has `success=True` under the clamped probability (0.90 + 0.10).
4. Build the analysis with `build_completed_run_supply_chain_analysis` from the
   events; assert the six chain edges, at least one depth-3 chain, and a
   `tool_dependency` or `upstream_shortfall` row where the fixture produces one.
5. Compose/publish via `compose_supply_chain_snapshot` and
   `publish_supply_chain_snapshot` into `tmp_path`, then read summary and one
   page through the FastAPI test client with both settings configured.
6. Negative variant: flag off + legacy catalog + same commands → no chain
   edges and no supply snapshot; API returns 503 when unconfigured.

### Required Interfaces and Contracts

- Real `WorldEngine` admission only; no monkeypatched production functions.
- Assertions use committed events, snapshot, and API responses only.
- The harvest probability bonus is asserted through the committed
  `success`/`duration_ticks`, not internal state.

### Requirement Evidence

- `test_trade_networks_end_to_end.py`; `actions.py` 254-335;
  `_production.py` 157-235/500-564; Original Request chain example.
- Supported combinations: full chain, flag off, disabled API, pending job
  completion timing.

### Error Handling and Logging

- Assert no unexpected `WARN supply_chain_*` in `caplog`.
- Engine rejections asserted by code (`actor_busy`, `materials_unavailable`,
  `unknown_recipe`), not message text.

### Tests

- `uv run pytest tests/unit/test_supply_chain_end_to_end.py -q`.

### Acceptance Criteria

- The full chain commits; analysis reports depth ≥ 3.
- Tool-assisted harvest succeeds deterministically in the fixture.
- Snapshot publish + API read succeed; disabled variant returns 503.

### Verification

- `uv run pytest tests/unit/test_supply_chain_end_to_end.py -q` → all pass.

## Task 21: Add determinism property bounds and leakage coverage

### Intent

Guarantee the new analysis and mechanics are reproducible across hash seeds,
bounded by every cap, and unable to smuggle authority, payloads, or optimizer
semantics into analysis, clients, or metrics.

### Implementation Steps

1. `tests/unit/test_supply_chain_determinism.py`:
   - Hypothesis generates ordered event sequences from the closed production
     event set with ticks 0..128 and unique stable ids;
   - assert evidence → analysis → metrics are byte-identical across two runs,
     including one subprocess case with different `PYTHONHASHSEED`;
   - assert engine restore parity: run N ticks, serialize, restore, run M, and
     compare event kinds, ticks, recipe ids, and `duration_ticks`;
   - assert the plan sequence is identical across two indistinguishable loops;
   - shuffle input order in one property and assert output is unchanged.
2. `tests/unit/test_supply_chain_bounds.py`: one property per cap
   (`max_evidence_rows`, `max_stages`, `max_edges`, `max_chains`,
   `max_bottlenecks`, `max_locations`, `max_organizations`,
   `max_lineage_edges`) asserting exact retention, one truncation notice, and
   `partial` coverage.
3. `tests/unit/test_supply_chain_leakage.py`:
   - AST scan of `src/analysis/supply_chain_*.py` for forbidden imports
     (`simulation.engine`, `simulation.bootstrap`, `experiments`, `api`,
     `persistence`, `observer`, `agents.cognition`, `world._*`);
   - forbidden key scan across analysis/rows/models/codec/UI types;
   - pinned counts: 43 commands, 73 observer semantics, replay-v27/`v25`,
     Alembic `0017`;
   - Research UI client contains no mutating method.
4. `tests/architecture/test_supply_chain_boundaries.py`: extend the Task 1 file
   with the trade AST approach (`_trade_paths`/`_ast_names` 54-68, denylist
   124-143); assert simulation does not import analysis, analysis does not
   import the new world module, `METRIC_FAMILY_COUNT == 204`, and the last six
   ids.

### Required Interfaces and Contracts

- Determinism asserted over public functions only.
- Bounds tests use generated inputs plus one real catalog case.
- Leakage tests fail on any new forbidden import or key.
- Edge-kind pins cover all ten closed kinds.

### Requirement Evidence

- Trade determinism/bounds/leakage suites; trade boundary AST
  (`test_trade_networks_boundaries.py` 54-174); ARCHITECTURE Key Principles
  1-2/5.
- Supported combinations: identical inputs across seeds, each cap boundary,
  injected forbidden import (fails), injected forbidden key (fails).

### Error Handling and Logging

- No production logging change.
- Property failures shrink through pytest.

### Tests

- `uv run pytest tests/unit/test_supply_chain_determinism.py tests/unit/test_supply_chain_bounds.py tests/unit/test_supply_chain_leakage.py tests/architecture/test_supply_chain_boundaries.py -q`.

### Acceptance Criteria

- Identical inputs produce identical analysis, metrics, and snapshot digests
  across hash seeds.
- Every cap retains exactly the deterministic prefix plus one notice.
- A deliberately injected forbidden import/key fails the guard.

### Verification

- `uv run pytest tests/unit/test_supply_chain_determinism.py tests/unit/test_supply_chain_bounds.py tests/unit/test_supply_chain_leakage.py tests/architecture/test_supply_chain_boundaries.py -q` → all pass.

## Phase Risks and Mitigations

- Risk: E2E relies on internal state. Mitigation: events/snapshot/API only.
- Risk: Hypothesis only exercises duplicate rejection. Mitigation: unique id
  generator; duplicates covered in Task 6.
- Risk: determinism passes only because input order is fixed. Mitigation:
  shuffled-order property.
- Risk: leakage scan covers one module. Mitigation: glob every supply file.

## Phase Completion Checklist

- Every Task 19-21 satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
