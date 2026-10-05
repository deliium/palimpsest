"""Unit tests for seeded new-agent parameter draws."""

from __future__ import annotations

import logging

from agents.models import DriveKind
from simulation.models import SimulationRunConfig
from simulation.new_agent_initialization import (
    ParameterDistributionSpec,
    draw_parameter_distribution,
    new_agent_init_stream,
)
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.new_agent_init_rng")


def _run_config(seed: int) -> SimulationRunConfig:
    return SimulationRunConfig(seed=seed, physical_rules=non_lethal_physical_rules())


def test_same_seed_draws_identical() -> None:
    _LOG.debug("case_id=same_seed_draws_identical")
    dist = ParameterDistributionSpec(
        distribution_id="uniform_drive_delta",
        params={
            "drive_kind": DriveKind.CURIOSITY.value,
            "min_delta": 0.0,
            "max_delta": 0.5,
        },
    )
    cfg = _run_config(42)
    a = draw_parameter_distribution(
        cfg, run_id="run-1", agent_id="entrant-1", distribution=dist
    )
    b = draw_parameter_distribution(
        cfg, run_id="run-1", agent_id="entrant-1", distribution=dist
    )
    assert a.distribution_id == "uniform_drive_delta"
    assert a.drive_kind is DriveKind.CURIOSITY
    assert a.delta == b.delta


def test_cross_agent_stream_isolation() -> None:
    _LOG.debug("case_id=cross_agent_stream_isolation")
    cfg = _run_config(99)
    stream_a = new_agent_init_stream(
        cfg, run_id="run-1", agent_id="agent-a", draw_name="parameter_distribution"
    )
    stream_b = new_agent_init_stream(
        cfg, run_id="run-1", agent_id="agent-b", draw_name="parameter_distribution"
    )
    samples_a = [stream_a.random() for _ in range(8)]
    samples_b = [stream_b.random() for _ in range(8)]
    assert samples_a != samples_b


def test_none_distribution_skips_draw() -> None:
    _LOG.debug("case_id=none_distribution_skips_draw")
    result = draw_parameter_distribution(
        _run_config(1),
        run_id="run-1",
        agent_id="agent-1",
        distribution=ParameterDistributionSpec(distribution_id="none", params={}),
    )
    assert result.distribution_id == "none"
    assert result.delta is None
