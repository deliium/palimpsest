# Experiments Framework

[← Architecture](architecture.md) · [Simulation runner](simulation-runner.md) · [Back to README](../README.md)

## Trust boundary

The `experiments` package is trusted outer orchestration. It may coordinate public `simulation` and read-only `analysis` contracts. Domain packages (`world`, `agents`, `agents.cognition`, `memory`, `social`) and `simulation` must never import `experiments` or receive collectors, truth specifications, objective snapshots, or analysis results.

Objective instrumentation is post-commit observation only. Collectors never flow back into cognition, memory formation, prompts, or action selection.

## Catalog (A–K)

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

Builders share scenario, seed, and stochastic identity across paired arms; only declared treatment dimensions differ. Condition/config fingerprints change when treatments change.

**Experiment A** has three arms (`a-reference`, `a-reconstructive`, `a-reconstructive-v2`). The V1 regression gate uses `experiment_a_memory_v1_arms()` / `EXPERIMENT_A_V1_CONDITION_IDS` so only the two V1 arms run — a broken V2 path cannot fail V1 `exact_trajectory_hash` baselines. V2 audits are harvested in-run, composed via `map_recall_audits_to_dynamics_report`, and never agent-visible.

Catalog builders emit current write schema (`runner-config-v4`) with all `V2CapabilityFlags` default-off and `CognitionTraceSpec` disabled. Use `experiments.catalog.v1_regression_profile(config)` to assert the V1-equivalent profile (raises `v1_regression_flags_enabled` if any flag is on, or `v1_regression_trace_enabled` if tracing is enabled). Capability flags and tracing are configuration identifiers only; they do not change experiment-definition schema (`experiment-definition-v1`).

Network-free regression gate: `tests/unit/test_v1_regression_gate.py` (short ticks, catalog A–E + reference scenario). Experiments F, G, H, I, J, and K are additive and are not part of that gate. The default config write stays `runner-config-v4`. `runner-config-v5` is emitted only when some agent's consolidation mode is not `DISABLED`. `runner-config-v6` is emitted only when some agent's reflection mode is not `DISABLED`, and that document may also carry consolidation. `runner-config-v8` is emitted only when some agent's counterfactual mode is not `DISABLED`, and that document may also carry consolidation, reflection, and prospective imagination. Experiment G checks a shared objective hash through the reflection tick and an audit on the deterministic arm only. It does not preload the decision-divergence memories, and it does not require a later command to change.

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
