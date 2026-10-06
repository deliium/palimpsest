"""Effective developmental rate composition (lifecycle + dependency zeros)."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.developmental_learning import (
    DevelopmentalDomainId,
    DevelopmentalStageCompose,
    compose_developmental_effective_rate,
    resolve_developmental_applicability,
    resolve_developmental_rate_hints,
)
from agents.models import AgentId


def test_learning_rate_zero_blocks() -> None:
    rate = compose_developmental_effective_rate(
        owner_id=AgentId("a"),
        domain=DevelopmentalDomainId.SKILLS,
        base_rate=1.0,
        source_weight=1.0,
        stage_compose=DevelopmentalStageCompose.MULTIPLY_LIFECYCLE_LEARNING_RATE,
        lifecycle_factor=1.0,
        learning_rate_zero=True,
    )
    assert rate == 0.0


def test_lifecycle_multiply_and_ignore() -> None:
    multiply = compose_developmental_effective_rate(
        owner_id=AgentId("a"),
        domain="locations",
        base_rate=0.5,
        source_weight=0.5,
        stage_compose=DevelopmentalStageCompose.MULTIPLY_LIFECYCLE_LEARNING_RATE,
        lifecycle_factor=0.5,
        learning_rate_zero=False,
    )
    assert multiply == 0.125
    ignore = compose_developmental_effective_rate(
        owner_id=AgentId("a"),
        domain="locations",
        base_rate=0.5,
        source_weight=0.5,
        stage_compose=DevelopmentalStageCompose.IGNORE_LIFECYCLE,
        lifecycle_factor=0.5,
        learning_rate_zero=False,
    )
    assert ignore == 0.25


def test_min_exposures_gate() -> None:
    rate = compose_developmental_effective_rate(
        owner_id=AgentId("a"),
        domain=DevelopmentalDomainId.RESOURCES,
        base_rate=1.0,
        source_weight=1.0,
        stage_compose=DevelopmentalStageCompose.IGNORE_LIFECYCLE,
        exposure_count=1,
        min_exposures=3,
    )
    assert rate == 0.0
    rate2 = compose_developmental_effective_rate(
        owner_id=AgentId("a"),
        domain=DevelopmentalDomainId.RESOURCES,
        base_rate=1.0,
        source_weight=1.0,
        stage_compose=DevelopmentalStageCompose.IGNORE_LIFECYCLE,
        exposure_count=3,
        min_exposures=3,
    )
    assert rate2 == 1.0


def test_resolve_rate_hints_from_observation_and_stage_table() -> None:
    observation = SimpleNamespace(
        self_body=SimpleNamespace(
            lifecycle=SimpleNamespace(stage="juvenile"),
            dependency_needs=SimpleNamespace(
                needs=(
                    SimpleNamespace(need_id="learning", critical=True),
                )
            ),
        )
    )
    factor, zero = resolve_developmental_rate_hints(
        observation,
        stage_learning_rates={"juvenile": 0.8, "adult": 1.0},
    )
    assert factor == 0.8
    assert zero is True


def test_entity_learning_rate_prefers_objective_continuous_map() -> None:
    observation = SimpleNamespace(
        self_body=SimpleNamespace(
            lifecycle=SimpleNamespace(stage="juvenile"),
            dependency_needs=None,
        )
    )
    factor, zero = resolve_developmental_rate_hints(
        observation,
        stage_learning_rates={"juvenile": 0.8, "adult": 1.0},
        entity_learning_rate=1.15,
    )
    assert factor == 1.15
    assert zero is False


def test_resolve_applicability_modes() -> None:
    learning = SimpleNamespace(
        self_body=SimpleNamespace(lifecycle=SimpleNamespace(stage="learning"))
    )
    adult = SimpleNamespace(
        self_body=SimpleNamespace(lifecycle=SimpleNamespace(stage="adult"))
    )
    assert resolve_developmental_applicability(
        applicability="all_live_agents",
        observation=adult,
        mid_run_admit=False,
    )
    assert not resolve_developmental_applicability(
        applicability="mid_run_new_agents",
        observation=adult,
        mid_run_admit=False,
    )
    assert resolve_developmental_applicability(
        applicability="mid_run_new_agents",
        observation=adult,
        mid_run_admit=True,
    )
    assert resolve_developmental_applicability(
        applicability="lifecycle_learning_stage",
        observation=learning,
        mid_run_admit=False,
    )
    assert not resolve_developmental_applicability(
        applicability="lifecycle_learning_stage",
        observation=adult,
        mid_run_admit=True,
    )
