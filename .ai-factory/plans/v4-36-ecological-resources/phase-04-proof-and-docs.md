# Phase 4: Proof and docs

Plan: [index.md](index.md)  
Tasks: 8–10  
Depends on: Phase 3

## Objective

Demonstrate the entire feedback loop with ordinary actions and matched controls, then qualify and document the supported surface without claiming autonomous emergence.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `tests/simulation_helpers.py`, `tests/unit/test_supply_chain_mechanics.py` | `make_resource`, `alive_body`, `connected_locations`; real ordered stock commands | Reusable foundations for physical tests without monkeypatching the world. |
| `src/world/_rules.py`, `src/simulation/runner.py` | `_evaluate_drink`, `_mutate_drink`, `set_intervention_arbiter` | Resource `Drink` is deterministic, debits ordinary stock, and is refused at stock `<1.0`. The existing trusted runner seam can apply the same timed probe in both arms. |
| `tests/unit/test_environmental_dynamics_replay.py`, `tests/unit/test_experiment_bg.py` | environmental prefix parity; `bf_baseline_v4.json` golden fixture | Established evidence and compatibility controls. |
| `docs/development.md`, `docs/v4-versioning.md` | verification commands, active version pins | Project verification is coverage-on and environment-gated lanes have separate status. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `tests/unit/test_ecological_resources_feedback.py` | create | Real matched runner trace, a legacy fixture smoke test and replay parity. |
| `tests/unit/test_v4_scaffolding_gate.py`, `tests/unit/test_runner_config_v4_flags.py`, `tests/unit/test_compatibility_matrix.py`, `tests/architecture/test_v4_architecture_invariants.py` | modify as specified in Task 9 | Update only stale active acceptance/ownership expectations, leaving historical invariants intact. |
| `README.md`, `docs/ecological-resources.md`, `docs/configuration.md`, `docs/v4-versioning.md`, `docs/v4-architecture.md`, `docs/research-api.md`, `docs/development.md` | create new topic page; update existing pages | Publish the exact scope, composed semantics, replay and verification. |
| `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` | modify at implementation checkpoint | Record landed compatibility/ownership where approved by corresponding workflow; don't close M8. |

## Task 8: Demonstrate the feedback loop in matched runs

### Intent

Prove that earlier admitted social activity changes future available stock and that stock changes a later ordinary action. Do not count an event name or final statistic as proof on its own.

### Implementation Steps

1. Build a single v60 `SimulationRunnerConfig` fixture with two co-located living founders, one selected water node (`quantity=maximum_quantity=2.0`, regen `1.5`, floor `.5`, allowance `0`, recovery `.1` per idle tick), and a second unselected water node with identical physical inputs. Use default extraction `1.0`, seed `34`, shared stochastic identity, no terminal early stop, no unrelated enabled channels, and an existing environmental dynamics spec with no shortages and `1.0` water yield on ticks 0–2. Use the real `SimulationRunner.from_config` and deterministic fake cognitive dependencies; seed/identity, config and policy must be identical for both arms.
2. Use a test-only implementation of the trusted intervention arbiter's `maybe_replace` contract. At tick 0, pressure arm gives each founder `Drink` targeting the selected node; rest arm gives both `Wait`. At tick 1, both arms wait. At tick 2, both issue the identical ordinary `Drink` probe for one founder; the other waits. Override only via ordinary admission, never edit world state or force outcomes.
3. Add a depletion-only control: reuse the pressure schedule, but change just the selected node's `withdrawal_allowance_tenths` from `0` to `20`, avoiding damage from that exact `2.0` withdrawal. Both pressure arms must first have two committed resource-backed `Drunk` effects and reach stock `0.0` before regrowth at tick 0. At the ends of ticks 0 and 1, assert quantities `0.5` and `0.6` in the degradation arm (damage `1.5`, then `1.4`); `1.5` and `2.0` in the depletion-only arm (damage `0`); and `2.0` in the rest arm. Assert the identical tick-2 probe fails with `resource_depleted` only in the degradation arm and produces an admitted `Drunk` effect in both controls. Verify the unmanaged node stays unchanged and use Task 4's separate season/shortage case.
4. Repeat same-arm twins with fixed identities (compare normalized event bytes/digests if run identity differs), round-trip actual checkpoint plus tail, and compare observed stock and later decisions before and after restoration. Add a real legacy artifact smoke lane: decode the checked-in `tests/fixtures/runner_configs/bf_baseline_v4.json` using the same approach as `test_experiment_bg.py`, assert canonical bytes and run one real tick without adding ecology to state or events.

### Required Interfaces and Contracts

- Test and contributor reproduction only. No new experiment registry entry, production schedule, metric family, generic matrix factor or dashboard needed.
- Evidence chain: admitted withdrawals → committed damage and capped renewal → next observation → identical probe, different actual result. This is a controlled mechanism demonstration, not a society-level prediction.

### Error Handling and Logging

Reject unexpected schedule ticks or missing target fixture nodes in test setup; real runner refusals preserve native reason codes. No production logging in the fixture.

### Tests

`tests/unit/test_ecological_resources_feedback.py`: pressure, rest and depletion-only arms, same-arm twin, checkpoint/tail parity and existing artifact off lane; use public runner and objective event interfaces for evidence, not a metric stub. Confirm the two pressure arms reached zero by comparing their committed command detail values, not a post-renewal frame.

### Acceptance Criteria

The test would fail if the world only logged depletion but did not change committed future stock or admission.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_feedback.py -q` passes.

## Task 9: Run compatibility and qualification gates

### Intent

Prove isolated activation and preserve old runs, including disease, measurements, environmental dynamics and observer contracts.

### Implementation Steps

1. Update current ownership and accepted-version assertions to 11 owned V4 flags, only `disasters` unowned, accepted v60, and activated event 25/`v23`; keep `v4-context-map-v6` unchanged because no context, edge or declared authority changes. Preserve legacy off fixtures and reservations. Find other live assertions by targeted search for `ecological_feedback`, `RUNNER_SCHEMA_VERSION_V59` and active/write-pair pins; do not rewrite dated landing snapshots.
2. Assert unchanged 45 commands, 73 observer semantic types, 275 metric families, 17 contexts, 12 flags, Alembic `0017`, API `/v1`, `observer-protocol-v1`, default runner/result v4/v2, and pending-finalization v1/v6 selection. Run the layered acceptance and rejection cases in the index, including version-for-version legacy event/codec coverage.
3. Record exact completed lanes and any missing prerequisites in the implementation verification receipt. Do not label skipped database/Compose/browser/Godot lanes as passes or claim a new capacity envelope.

### Required Interfaces and Contracts

- Preserve `.ai-factory/ARCHITECTURE.md` regression gates; metadata for V4-01 reservations stays reserved for `disasters` and does not become runnable.

### Error Handling and Logging

Treat a mismatched compatibility pin or an unexpected change to a legacy fixture as a blocker; don't regenerate legacy goldens to hide drift. Maintain coverage defaults.

### Tests

Run focused gates and then the repository-wide default and static checks below. Phase 3 specifies the separate disposable PostgreSQL durable lane.

### Acceptance Criteria

Feature tests and flags-off gates pass; verification distinguishes durability proof from an unavailable lane.

### Verification

```sh
uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_*.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_v4_scaffolding_gate.py tests/unit/test_runner_config_v4_flags.py tests/unit/test_v4_versioning_reservations.py tests/unit/test_v4_migration_plan.py tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_v4_context_registry.py -q
uv run --frozen --python 3.12.14 pytest
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

## Task 10: Document the bounded mechanism and rollout

### Intent

Make the opt-in reproducible and prevent readers from interpreting stock caps as ecological or demographic forecasts.

### Implementation Steps

1. Use the mandatory `$aif-docs` checkpoint. Add `docs/ecological-resources.md` with exact example JSON section, seasonal prerequisites/composition, formula and timing, no-population-limit interpretation, controlled-run command and expected measurements for both controls, strict config/replay handling, and explicitly no species, agents for natural systems, inter-node transfer, automated conservation, climate, disasters, policy enforcement or population control.
2. Update the README index, configuration and versioning tables, V4 ecology section, research API accepted versions and verification commands. Distinguish observer views (ordinary resource facts only) from authorized raw objective event inspection (including capacity-change data), and document trusted-policy requirements for continuation versus policy-free ecological replay.
3. Update current AI context pins after verification using the relevant document and roadmap workflow; add the scoped V4-36 completion evidence under M8 without closing `disasters` or editing dated historical counts.

### Required Interfaces and Contracts

- Docs reflect exact keys and example policy values and do not promise new API routes, SQL schema, UI or full subjective/API restart support.

### Error Handling and Logging

If a documented input example does not validate or a qualification lane is unexecuted, repair the example or qualify the claim. Do not publish logs with payloads or credentials.

### Tests

Add `tests/unit/test_ecological_resources_docs.py` to check README link, headings, exact reserved pair, the stock-limit/non-population-control distinction and agreement with executable version/ownership pins; parse the example policy via the public strict decoder in the config test.

### Acceptance Criteria

A contributor can reproduce the intended loop, locate the existing image/API compatibility surface, and know what the model expressly does not claim.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_docs.py tests/unit/test_ecological_resources_config.py -q` passes; review links and publish the actual gate receipt.

## Phase Risks and Mitigations

- Confounding weather, pressure and degradation: the rest comparison changes only tick-0 commands; the depletion-only comparison holds the command schedule fixed and changes only the damage allowance.
- Mistaking passed local checks for operational certification: separate unit, integration and environment-gated results.

## Phase Completion Checklist

- Feedback chain and off-path golden verified; compatibility and documentation checkpoint complete; update only verified task checkboxes in `index.md`.
