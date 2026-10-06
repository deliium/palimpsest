"""Effective developmental rate composition (lifecycle + dependency zeros)."""

from __future__ import annotations

from agents.cognition.developmental_learning import (
    DevelopmentalDomainId,
    DevelopmentalStageCompose,
    compose_developmental_effective_rate,
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
