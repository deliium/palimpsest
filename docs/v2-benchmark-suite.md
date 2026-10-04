# V2 benchmark suite

[← Experiments](experiments.md) · [Godot observer](godot-observer.md) · [Research UI](research-ui.md) · [Development](development.md) · [Back to README](../README.md)

Composition and validation surface for remaining M6 research integration. It reuses catalog builders, matrix factors, observer protocol, and zero-install startup — it does **not** own `multi_hop_testimony_tracking`, add `V2CapabilityFlags` slots, or script emergence outcomes.

Package entry: `experiments.benchmark_suite` / `experiments.benchmark_scenarios`. Smoke helper: `experiments.benchmark_smoke`. Observer world: `experiments.observer_graphical_scenario`.

## Non-assertions

Scenarios prove that **mechanisms required for emergence work** and that **metrics can detect the phenomenon when it occurs**. Absence, weak support, and strong support are all valid.

Forbidden (test deny-list over registry strings): “must emerge”, “must form”, “must invent myth”, “society forms”. Boolean fields such as `myth_must_emerge` / `group_must_form` are out of scope.

## Scenario catalog

| # | scenario_id | Locked condition ids | Focus |
| --- | --- | --- | --- |
| 1 | `bench-01-seasonal-planning` | `u-learned`, `u-naive` | Long-term planning under seasonal scarcity |
| 2 | `bench-02-memory-interference` | `a-reconstructive-v2`, `a-reconstructive` | Memory interference changing behavior |
| 3 | `bench-03-reflection-revision` | `g-deterministic`, `g-disabled` | Reflection revising a false belief |
| 4 | `bench-04-tom-social-failure` | `l-enabled`, `l-disabled` | Incorrect ToM → measurable social failure **when** mismatch occurs |
| 5 | `bench-05-tom-cooperation` | `l-enabled`, `l-disabled` | Successful cooperation using ToM **when** hypotheses help |
| 6 | `bench-06-deception-reputation` | `o-strategy-reputation`, `q-disabled`, `o-strategy-only` | Strategy + reputation on `runner-config-v10` |
| 7 | `bench-07-skill-specialization` | `r-enabled`, `t-enabled`, `r-disabled`, `t-disabled` | Skill learning and specialization |
| 8 | `bench-08-territorial` | `v-scarce`, `v-abundant` | Emergent territorial behavior |
| 9 | `bench-09-social-clusters` | `w-enabled`, `w-disabled` | Social cluster churn (no scripted shock) |
| 10 | `bench-10-norms` | `x-enabled`, `x-disabled` | Norm formation and violation |
| 11 | `bench-11-conventions` | `y-enabled`, `y-disabled` | Persistent convention/tradition |
| 12 | `bench-12-artifacts` | `artifact_channel`, `memory_only` | External artifacts preserving information |
| 13 | `bench-13-naming-drift` | `aa-enabled`, `aa-disabled` | Vocabulary/naming drift |
| 14 | `bench-14-rumor-narrative` | `ab-enabled`, `ab-disabled` | Rumor → persistent inaccurate narrative |
| 15 | `bench-15-architecture-matrix` | `ac-<architecture_id>` | Identical world, different architectures |
| 16 | `bench-16-forked-intervention` | `fork-parent`, `fork-child-comm-remove` | `COMMUNICATION_REMOVE` fork compare |

Every spec declares `scenario_id`, configuration refs, seed strategy, expected invariants, measurable outputs, non-goals, statistical comparison (or `n/a:`), `max_ticks`, and `off_v1_gate=true`. Default smoke budget is ≤ 4 ticks; full scenario budgets prefer ≤ 64.

## Matrix batch

Example manifest: `tests/fixtures/matrices/v2-benchmark-suite.json` (`experiment-matrix-v1`). Factors: `memory_type`, `tom`, `seasonality`, `resource_scarcity`; seeds `(11, 13, 17)`. Filesystem expand / metric sidecars / `matrix-metric-summary-v1` only — no HTTP batch start. Scenario 16 stays on branch-compare APIs, not this culture matrix.

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_benchmark_matrix_manifest.py -q
uv run palimpsest-matrix run --matrix tests/fixtures/matrices/v2-benchmark-suite.json --manifest-root ./matrix-out
```

## Observer graphical scenario

`observer-graphical-v2`: multi-agent world with locations, movement, resources, Talk/Ask/Tell, item exchange, environmental dynamics, production/structures, a terminal event, external artifact, and social transmission. Godot fixture: `clients/godot-observer/fixtures/observer_graphical_v2.json`.

Control checklist (protocol / compose gap-fill): start, live events, pause, event-step, tick-step, seek back/forward, large jump, return-to-live, filters, follow agent, causal debugger, fork switch. Presentation coordinates and seek/pause must not change `exact_trajectory_hash`.

## Zero-install acceptance

Normal startup: `./run.sh` (aliases `./scripts/up.sh`, `docker compose up -d` on `compose.yaml`). Acceptance environment is Docker/container runtime + browser only — not Godot editor, export templates, or manual asset compile.

Opt-in compose: `pytest -m compose tests/compose/test_observer_browser.py tests/compose/test_stack.py`. Static published-path checks live in `tests/unit/test_published_startup.py`.

## Scientific invariants gate

Network-free pin: `tests/unit/test_v2_scientific_invariants.py` (plus architecture isolation under `tests/architecture/`). Stays **off** `tests/unit/test_v1_regression_gate.py`. Scale limits reuse the `@pytest.mark.scale` harness from long-experiment scalability docs — no new BLAS-sensitive thresholds here. LLM record/replay remains proven by `tests/integration/test_llm_recording_replay.py`.

## Research UI acceptance

When `PALIMPSEST_RESEARCH_WEB_ROOT` points at a built `clients/research-ui/dist`, `/research/` serves the SPA. Matrix analytics resolve allowlisted documents under `PALIMPSEST_RESEARCH_MATRIX_ROOT` (manifest, aggregate, `metric-summary.json`, cell sidecars). Unit coverage: `tests/unit/test_benchmark_research_ui_artifacts.py`. Compose wiring: `tests/compose/test_research_ui_wiring.py` (skip-clean when smoke URL / dist / matrix mount unset).

## M6 status

This suite closes the V2 research/integration composition surface for M6. **Still open:** `multi_hop_testimony_tracking` (fails closed with `capability_unimplemented`).

## Tests

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_v1_regression_gate.py \
  tests/unit/test_v2_scientific_invariants.py \
  tests/unit/test_benchmark_suite_registry.py \
  tests/unit/test_benchmark_matrix_manifest.py \
  tests/unit/test_benchmark_research_ui_artifacts.py \
  tests/architecture/test_benchmark_suite_isolation.py \
  -q
```
