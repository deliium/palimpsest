"""Experiment H diverges ability and weakness with the intervention, not the id."""

from __future__ import annotations

import pytest

from agents.cognition.identity import IdentityAspect
from agents.cognition.models import project_identity_state
from experiments.catalog import experiment_h_identity
from experiments.reference_scenario import identity_divergence_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS


def _aspect_rate(state: object, aspect: IdentityAspect) -> float:
    rates = [
        view.derived_rate
        for view in state.views  # type: ignore[attr-defined]
        if view.aspect is aspect
    ]
    return max(rates) if rates else 0.0


def _states_from_runtimes(runtimes: object) -> dict[str, object]:
    states: dict[str, object] = {}
    for runtime in runtimes:  # type: ignore[attr-defined]
        reader = runtime._semantic_belief_reader
        heads = reader.snapshot()
        histories = tuple(
            history
            for belief in heads
            if (history := reader.history(belief.belief_id)) is not None
        )
        states[runtime.agent_id.value] = project_identity_state(
            owner_id=runtime.agent_id,
            histories=histories,
        )
    return states


async def _run(success_agent: str, *, enabled: bool, run_id: str):
    bundle = identity_divergence_scenario(success_agent_id=success_agent)
    definition = experiment_h_identity(bundle.config)
    condition_id = "h-enabled" if enabled else "h-disabled"
    config = next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == condition_id
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId(run_id)
    ) as runner:
        runner.set_intervention_arbiter(bundle.arbiter)
        result = await runner.run()
        states = _states_from_runtimes(runner.runtimes) if enabled else None
        predicates = []
        if not enabled:
            for runtime in runner.runtimes:
                reader = runtime._semantic_belief_reader
                predicates.extend(
                    belief.claim.predicate for belief in reader.snapshot()
                )
    return result, states, predicates, bundle


def test_identity_experiment_stays_off_the_v1_gate() -> None:
    ids = {experiment_id for experiment_id, _builder in _CATALOG_BUILDERS}
    assert "experiment-h-identity" not in ids


def test_swap_assigns_search_and_failed_flee() -> None:
    first = identity_divergence_scenario(success_agent_id="agent-a")
    second = identity_divergence_scenario(success_agent_id="agent-b")
    assert first.config.scenario.world_id.value == "identity-divergence-v1"
    assert first.config.seed == second.config.seed
    assert first.config.stochastic_identity == second.config.stochastic_identity
    assert first.config.scenario.bodies == second.config.scenario.bodies

    def kinds(bundle: object) -> dict[str, str]:
        assigned: dict[str, str] = {}
        for item in bundle.arbiter.milestones:  # type: ignore[attr-defined]
            assigned[item.agent_id.value] = item.build_command().kind
        return assigned

    assert kinds(first)[first.success_agent_id.value] == "search"
    assert kinds(first)[first.stalled_agent_id.value] == "flee"
    assert kinds(second)["agent-a"] == "flee"
    assert kinds(second)["agent-b"] == "search"


@pytest.mark.asyncio
async def test_flags_off_trajectory_is_stable_and_stores_no_identity() -> None:
    first, _states, predicates, _bundle = await _run(
        "agent-a", enabled=False, run_id="run-h-off-1"
    )
    second, _again, again_predicates, _ignored = await _run(
        "agent-a", enabled=False, run_id="run-h-off-2"
    )
    assert first.objective_state_hash == second.objective_state_hash
    assert all(not predicate.startswith("identity.") for predicate in predicates)
    assert all(not predicate.startswith("identity.") for predicate in again_predicates)


@pytest.mark.asyncio
async def test_ability_rate_follows_the_success_intervention() -> None:
    _result, states, _predicates, bundle = await _run(
        "agent-a", enabled=True, run_id="run-h-on-a"
    )
    assert states is not None
    success = bundle.success_agent_id.value
    stalled = bundle.stalled_agent_id.value
    assert _aspect_rate(states[success], IdentityAspect.ABILITY) > _aspect_rate(
        states[stalled], IdentityAspect.ABILITY
    )
    assert _aspect_rate(states[stalled], IdentityAspect.WEAKNESS) > _aspect_rate(
        states[success], IdentityAspect.WEAKNESS
    )
    _swapped, swapped_states, _ignored, swapped_bundle = await _run(
        "agent-b", enabled=True, run_id="run-h-on-b"
    )
    assert swapped_states is not None
    higher = max(
        swapped_states,
        key=lambda owner: _aspect_rate(
            swapped_states[owner], IdentityAspect.ABILITY
        ),
    )
    assert higher == swapped_bundle.success_agent_id.value
    assert higher == "agent-b"
    views = swapped_states[higher].views  # type: ignore[attr-defined]
    assert views
    assert {view.activation.value for view in views} <= {
        "candidate",
        "active",
    }
