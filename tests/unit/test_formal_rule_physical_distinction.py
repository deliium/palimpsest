"""V4-06 physical impossibility versus social prohibition."""

from __future__ import annotations

from typing import Any

import pytest

from agents.cognition import (
    FormalRuleConstraintKind,
    FormalRuleStage,
    default_formal_rule_policy,
    formal_rule_direction_preference,
    select_formal_rule_response,
)
from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import physical_config, two_location_fixture
from tests.unit.formal_rule_helpers import make_ledger
from world.actions import Give, Take
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _engine() -> WorldEngine:
    return WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
    )


def _take_item(engine: WorldEngine) -> None:
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED


def _give(engine: WorldEngine, *, target: str = "body-2") -> Any:
    batch = engine.observe()
    return engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Give(EntityId(target), EntityId("item-1")),
            ),
        )
    )


def test_socially_prohibited_but_physically_possible_command_is_admitted() -> None:
    ledger = make_ledger(
        action="give",
        constraint=FormalRuleConstraintKind.PROHIBITION,
        stage=FormalRuleStage.RECOGNIZED_ENFORCEMENT,
    )
    assert formal_rule_direction_preference(ledger, action_token="give") < 0.0
    engine = _engine()
    _take_item(engine)
    result = _give(engine)
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED


def test_physically_impossible_command_is_rejected_without_rule_attribution() -> None:
    engine = _engine()
    result = _give(engine)
    resolution = result.resolutions[0]
    assert resolution.status is ActionResolutionStatus.REJECTED
    assert "formal_rule" not in repr(resolution)


def test_rule_does_not_change_admission_or_action_rules() -> None:
    ledger = make_ledger(
        action="give",
        constraint=FormalRuleConstraintKind.PROHIBITION,
    )
    engine = _engine()
    _take_item(engine)
    without = _give(engine)
    engine = _engine()
    _take_item(engine)
    with_rule = _give(engine)
    assert with_rule.resolutions[0].status is without.resolutions[0].status
    assert ledger.rules


def test_response_selection_never_suppresses_a_command() -> None:
    ledger = make_ledger(
        action="give",
        constraint=FormalRuleConstraintKind.PROHIBITION,
    )
    _, response = select_formal_rule_response(
        ledger,
        tick=1,
        action_token="give",
        policy=default_formal_rule_policy(),
    )
    assert response is not None
    engine = _engine()
    _take_item(engine)
    result = _give(engine)
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED


def test_no_physical_constraint_member_exists() -> None:
    assert tuple(kind.value for kind in FormalRuleConstraintKind) == (
        "prohibition",
        "obligation",
        "permission",
    )
