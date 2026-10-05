"""Unit tests for seed-derived lifespan assignment."""

from __future__ import annotations

import logging

import pytest

from simulation.lifespan_distribution import assign_lifespan_ticks
from simulation.models import (
    DERIVATION_VERSION_V3,
    SimulationRunConfig,
    StochasticIdentity,
)
from simulation.runner_models import (
    LifespanDistributionSpec,
    example_population_lifecycle_spec,
)
from world.models import default_physical_rules

_LOG = logging.getLogger("tests.lifespan_distribution")


def _run_config(seed: int = 7) -> SimulationRunConfig:
    return SimulationRunConfig(
        seed=seed,
        derivation_version=DERIVATION_VERSION_V3,
        physical_rules=default_physical_rules(),
        stochastic_identity=StochasticIdentity("cmp-lifespan"),
    )


def test_fixed_distribution_copies_lifespan_ticks() -> None:
    _LOG.debug("case_id=fixed_copy")
    spec = example_population_lifecycle_spec(lifespan_ticks=20)
    assigned = assign_lifespan_ticks(spec=spec, agent_id="agent-1")
    assert assigned == 20


def test_uniform_int_draw_is_deterministic() -> None:
    _LOG.debug("case_id=uniform_deterministic")
    from dataclasses import replace

    base = example_population_lifecycle_spec(lifespan_ticks=20)
    spec = replace(
        base,
        lifespan_distribution=LifespanDistributionSpec(
            distribution_id="uniform_int",
            params={"min_ticks": 10, "max_ticks": 20},
        ),
    )
    kwargs = {
        "spec": spec,
        "run_config": _run_config(11),
        "run_id": "run-1",
        "world_id": "world-1",
        "agent_id": "agent-a",
        "entry_tick": 0,
    }
    first = assign_lifespan_ticks(**kwargs)
    second = assign_lifespan_ticks(**kwargs)
    assert first == second
    assert 10 <= first <= 20
    other = assign_lifespan_ticks(
        **{**kwargs, "run_config": _run_config(99)}
    )
    # Different seed may diverge; allow equal by chance but prefer divergence proof
    # via stream identity when seeds differ enough.
    _LOG.debug("assigned_seed11=%s assigned_seed99=%s", first, other)


def test_uniform_requires_stream_context() -> None:
    _LOG.debug("case_id=uniform_missing_context")
    from dataclasses import replace

    spec = replace(
        example_population_lifecycle_spec(lifespan_ticks=20),
        lifespan_distribution=LifespanDistributionSpec(
            distribution_id="uniform_int",
            params={"min_ticks": 10, "max_ticks": 20},
        ),
    )
    with pytest.raises(ValueError, match="lifespan_draw_context"):
        assign_lifespan_ticks(spec=spec, agent_id="agent-1")


def test_discrete_table_draw() -> None:
    _LOG.debug("case_id=discrete_table")
    from dataclasses import replace

    spec = replace(
        example_population_lifecycle_spec(lifespan_ticks=20),
        lifespan_distribution=LifespanDistributionSpec(
            distribution_id="discrete_table",
            params={"weights": {"12": 1.0, "18": 1.0}},
        ),
    )
    assigned = assign_lifespan_ticks(
        spec=spec,
        run_config=_run_config(3),
        run_id="run-1",
        world_id="world-1",
        agent_id="agent-b",
        entry_tick=0,
    )
    assert assigned in {12, 18}
