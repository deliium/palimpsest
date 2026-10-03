# Experiments Framework

[← Architecture](architecture.md) · [Simulation runner](simulation-runner.md) · [Back to README](../README.md)

## Trust boundary

The `experiments` package is trusted outer orchestration. It may coordinate public `simulation` and read-only `analysis` contracts. Domain packages (`world`, `agents`, `agents.cognition`, `memory`, `social`) and `simulation` must never import `experiments` or receive collectors, truth specifications, objective snapshots, or analysis results.

Objective instrumentation is post-commit observation only. Collectors never flow back into cognition, memory formation, prompts, or action selection.

## Catalog (A–Q)

| ID | Treatment |
| --- | --- |
| A | Exact/reference memory vs V1 reconstructive vs opt-in `RECONSTRUCTIVE_V2` |
| B | Imagination (future simulation) disabled vs enabled |
| C | Mortality disabled vs enabled (non-lethal physical rules overlay) |
| D | Controlled curiosity / safety / belonging / status drive profiles |
| E | Inject one controlled false `Tell` through ordinary communication; measure propagation without exposing the objective truth label to agents |
| F | Sleep consolidation `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v5`), shared seed and scenario. Not on the V1 regression gate |
| G | Reflection `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v6`), shared seed and scenario, default interval. Not on the V1 regression gate |
| H | Identity `extended_self_model` off vs on, both arms `runner-config-v4`, scenario `identity-divergence-v1`. One agent gets repeated search success and the other a failed flee. Not on the V1 regression gate |
| I | Causal world model `predictive_world_model` off vs on, both arms `runner-config-v4`, shared seed and scenario. Comparison metric `causal_world_model@1` runs after the run. Not on the V1 regression gate |
| J | Prospective imagination `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v7`), shared seed and scenario. Comparison metric `prospective_imagination@1` runs after the run. Not on the V1 regression gate |
| K | Counterfactual reasoning `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v8`), shared seed and scenario. Comparison metric `counterfactual_reasoning@1` runs after the run. Not on the V1 regression gate |
| N | Communication strategy `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v9`), shared seed and scenario. Trust comparison. Not on the V1 regression gate |
| O | Same arm shape as N, for deception labels. Not on the V1 regression gate |
| P | Same arm shape as N, for information cascades. Not on the V1 regression gate |
| Q | Reputation `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v10`), shared seed and scenario. Comparison metric `distributed_reputation@1` is analysis-only and is not run by the catalog. Not on the V1 regression gate |
| R | Skill learning `DISABLED` (`runner-config-v4`) vs `DETERMINISTIC` (`runner-config-v11`), shared seed and scenario. Comparison metric `skill_learning@1` is analysis-only and is not run by the catalog. Not on the V1 regression gate |
| S | Teaching `DISABLED` on `runner-config-v11` with skill learning `DETERMINISTIC`, vs both modes `DETERMINISTIC` on `runner-config-v12`. Shared seed, scenario, and stochastic identity. Comparison metric `cultural_transmission@1` is analysis-only and is not run by the catalog. Not on the V1 regression gate |
| T | Same mode pair and shared identity as S, for skill specialization. `cultural_transmission@1` stays off the V1 regression gate |

Builders share scenario, seed, and stochastic identity across paired arms; only declared treatment dimensions differ. Condition/config fingerprints change when treatments change.

**Experiment A** has three arms (`a-reference`, `a-reconstructive`, `a-reconstructive-v2`). The V1 regression gate uses `experiment_a_memory_v1_arms()` / `EXPERIMENT_A_V1_CONDITION_IDS` so only the two V1 arms run — a broken V2 path cannot fail V1 `exact_trajectory_hash` baselines. V2 audits are harvested in-run, composed via `map_recall_audits_to_dynamics_report`, and never agent-visible.

Catalog builders emit current write schema (`runner-config-v4`) with all `V2CapabilityFlags` default-off and `CognitionTraceSpec` disabled. Use `experiments.catalog.v1_regression_profile(config)` to assert the V1-equivalent profile (raises `v1_regression_flags_enabled` if any flag is on, or `v1_regression_trace_enabled` if tracing is enabled). Capability flags and tracing are configuration identifiers only; they do not change experiment-definition schema (`experiment-definition-v1`).

Network-free regression gate: `tests/unit/test_v1_regression_gate.py` (short ticks, catalog A–E + reference scenario). Experiments F, G, H, I, J, K, N, O, P, Q, and R are additive and are not part of that gate. The default config write stays `runner-config-v4`. `runner-config-v5` is emitted only when some agent's consolidation mode is not `DISABLED`. `runner-config-v6` is emitted only when some agent's reflection mode is not `DISABLED`, and that document may also carry consolidation. `runner-config-v8` is emitted only when some agent's counterfactual mode is not `DISABLED`, and that document may also carry consolidation, reflection, and prospective imagination. `runner-config-v9` is emitted only when some agent's communication strategy mode is `DETERMINISTIC` and every reputation mode is `DISABLED`. That document carries the v8 cognition keys plus `communication_strategy_mode`. A non-disabled strategy is also accepted on `runner-config-v10`. `runner-config-v10` is emitted only when some agent's reputation mode is `DETERMINISTIC`, and that document carries every v9 cognition key plus `reputation_mode`. Reputation and the earlier cognition modes are also accepted on `runner-config-v11`. `runner-config-v11` is emitted only when some agent's skill-learning mode is `DETERMINISTIC`. That document carries every v10 cognition key plus `skill_learning_mode` and the locked rate keys. No capability flag was added for skill learning. `v1_regression_profile` is unchanged. Experiment G checks a shared objective hash through the reflection tick and an audit on the deterministic arm only. It does not preload the decision-divergence memories, and it does not require a later command to change.

## Reference scenario (V1 gate)

`experiments.reference_scenario.build_reference_scenario()` builds the canonical five-agent / 48-tick fixture used by end-to-end proofs:

- Connected camp/spring/grove/ridge map with regenerating food and water
- Reconstructive memory + imagination enabled; deterministic-fake provider
- Sparse milestone arbiter (extract/drink/eat/tell/colocate/lethal attack) with a bounded override budget
- Early scheduled death proving N+1 terminal status and no later applied actions
- Public receipts/projections only in Task 20 tests (no `runner.engine` / `WorldState`)

Wire the arbiter with `SimulationRunner.set_intervention_arbiter(...)` before `run()`.

## Experiment E

The story enters as a normal structured `Tell` at a configured tick/source/recipient. The utterance has no `is_false` marker. A separate analysis-only `StoryTruthSpec` and intervention fingerprint identify the controlled treatment. Multi-hop lineage uses parent/root communication IDs on declared transmission metadata.

## Persistence

Append-only experiment records (Alembic `0010`, reconciled with run-control membership in `0011`):

- `experiment_definitions` — schema version, payload hash, definition fingerprint
- `experiment_assignments` — condition × seed ordinal × replicate → run ID
- `experiment_results` — one immutable final result per assigned run

Identical re-writes are idempotent; divergent reuse conflicts. SQLAlchemy adapter: `persistence.create_experiment_record_repository(...)`. In-memory port: `InMemoryExperimentRecordRepository`. The `experiments` package never imports SQLAlchemy.

## Coordinator

`ExperimentCoordinator` materializes assignments in condition × seed × replicate order and runs one fresh `SimulationRunner` per arm. Optional story intervention arbiter binds before pending subjective state is created.

## Experiment matrices (`experiment-matrix-v1`)

Additive research batch orchestration over catalog applicators. Matrix documents expand into existing `experiment-definition-v1` arms + `SimulationRunnerConfig`; they do **not** bump runner-config schema sets or own `multi_hop_testimony_tracking`. Matrix batch runs stay **off** the V1 regression gate.

### Locked axes and levels

| Factor id | Level ids | Effect |
| --- | --- | --- |
| `memory_type` | `reference`, `reconstructive`, `reconstructive_v2` | `MemoryMode` |
| `mortality` | `disabled`, `enabled` | `MortalityMode` |
| `imagination` | `disabled`, `enabled` | `ImaginationMode` only |
| `reflection` | `disabled`, `deterministic` | `ReflectionMode` |
| `tom` | `off`, `on` | `advanced_social_inference` only |
| `resource_scarcity` | `scarce`, `abundant` | scenario resource quantities (layout preserved) |
| `seasonality` | `off`, `on` | clear / set `EnvironmentalDynamicsSpec` |
| `cognitive_budget` | `disabled`, `low_cost`, `high_cost` | `CognitiveBudgetMode` + AD presets |

Constraints accept only `exclude_combos`. Expansion requires ≥2 conditions after filtering.

**Base config:** `expand_matrix` accepts an embedded `SimulationRunnerConfig` only. A `catalog` base id may appear in the matrix JSON schema, but expansion fail-closes with `catalog_base_unresolved` until a later plan wires catalog-builder resolution — embed the runner config instead.

### Schema finalize (highest-wins)

Factor applicators never set `schema_version`. After levels apply, `finalize_matrix_cell_config` picks the first match: budget → `v22`, cultural narratives → `v21`, semantic naming → `v20`, artifact interpretation → `v19`, environmental dynamics → `v14`, reflection → `v6`, else `v4`.

### `group_role` composition

1. Optional named `groups` overlay match → that role
2. Else `treatment` if any selected level is `treatment`
3. Else `control` if any is `control`
4. Else `neutral`

Labels are researcher metadata only — not world friend/enemy/leader roles.

### Resume and crash recovery

Filesystem store: `manifest.json` + `cells/<cell_id>.json` (+ completion sidecars). Validity requires matching matrix/cell/config fingerprints, schema versions, and `RunVersionIdentity`. On open, any cell `running` without a valid completion resets to `pending`. Divergent rewrite of the same matrix fingerprint fails closed. Process-local concurrency only (`max_concurrency`, default `1`); durable persistence requires serial execution.

### CLI (no HTTP)

Composition package `research_runner` (forbids `api`):

```bash
uv run palimpsest-matrix run --matrix matrix.json --manifest-root ./matrix-out
uv run palimpsest-matrix resume --matrix matrix.json --manifest-root ./matrix-out
uv run palimpsest-matrix status --manifest-root ./matrix-out
uv run palimpsest-matrix aggregate --matrix matrix.json --manifest-root ./matrix-out
# or: python -m research_runner …
```

Optional `--print-fingerprint` prints the matrix fingerprint only. Never dump full configs or seeds by default. Collectors for matrix experiment ids use summary + trajectory + catalog fallback. Aggregates are `matrix-aggregate-v1` analysis-only documents.

`RunVersionIdentity.code_revision` is optional metadata: pass `--code-revision` or set `PALIMPSEST_CODE_REVISION`. Empty is allowed; the CLI never invents a wall-clock surrogate.

## Logging

DEBUG/INFO may include experiment/condition/run IDs, ordinals, counts, versions, and hash prefixes. Never log seeds, story content, truth labels, drive values, prompts, credentials, or canonical JSON payloads.

## Tests

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_experiment_definitions.py \
  tests/unit/test_experiment_interventions.py \
  tests/unit/test_experiment_coordinator.py \
  tests/unit/test_experiment_persistence_contracts.py \
  tests/unit/test_v1_regression_gate.py \
  tests/unit/test_v2_flag_defaults.py \
  tests/architecture/test_experiment_instrumentation_isolation.py -q
```
