"""Pure dependency-care resolver and register tests."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from world.dependency_care import (
    CareAssistKind,
    CareNeedId,
    CareNeedPolicy,
    DependencyNeedRegister,
    care_action_legal,
    is_need_critical,
    needs_requiring_assistance,
    require_care_need_id,
    require_care_need_policy,
    self_satisfy_denied_kinds,
)
from world.lifecycle import DependencyStatus


def _policy(
    *,
    self_satisfy: bool = False,
    accrual: float = 0.1,
    threshold: float = 0.5,
    consequence: str = "health_damage",
) -> CareNeedPolicy:
    return CareNeedPolicy(
        self_satisfy=self_satisfy,
        unmet_accrual_per_tick=accrual,
        critical_threshold=threshold,
        critical_consequence=consequence,
    )


def test_needs_requiring_assistance_dependent_only() -> None:
    policies = {
        CareNeedId.FOOD: _policy(self_satisfy=False, consequence="accelerate_hunger"),
        CareNeedId.WATER: _policy(self_satisfy=True, consequence="accelerate_thirst"),
        CareNeedId.SAFETY: _policy(self_satisfy=False),
    }
    assert needs_requiring_assistance(
        DependencyStatus.INDEPENDENT, policies
    ) == ()
    assert needs_requiring_assistance(
        DependencyStatus.DEPENDENT, policies
    ) == (CareNeedId.FOOD, CareNeedId.SAFETY)


def test_self_satisfy_denied_kinds_union() -> None:
    policies = {
        CareNeedId.FOOD: _policy(
            self_satisfy=False, consequence="accelerate_hunger"
        ),
        CareNeedId.MOVEMENT: _policy(
            self_satisfy=False, consequence="no_extra"
        ),
        CareNeedId.LEARNING: _policy(
            self_satisfy=False, consequence="learning_rate_zero"
        ),
    }
    denied = self_satisfy_denied_kinds(
        DependencyStatus.DEPENDENT,
        (CareNeedId.FOOD, CareNeedId.MOVEMENT, CareNeedId.LEARNING),
        policies,
    )
    assert denied == frozenset({"eat", "move", "flee"})
    assert (
        self_satisfy_denied_kinds(
            DependencyStatus.INDEPENDENT,
            (CareNeedId.FOOD,),
            policies,
        )
        == frozenset()
    )


def test_is_need_critical_and_care_action_legal() -> None:
    policy = _policy(threshold=0.4)
    assert not is_need_critical(deficit=0.3, policy=policy)
    assert is_need_critical(deficit=0.4, policy=policy)
    assert care_action_legal(
        assist_kind=CareAssistKind.FEED,
        allow_feed=True,
        allow_transport=False,
        allow_help_safety=False,
        allow_teach_learning=False,
        require_colocated=True,
        colocated=True,
        target_status=DependencyStatus.DEPENDENT,
    )
    assert not care_action_legal(
        assist_kind="transport",
        allow_feed=True,
        allow_transport=True,
        allow_help_safety=False,
        allow_teach_learning=False,
        require_colocated=True,
        colocated=False,
        target_status=DependencyStatus.DEPENDENT,
    )
    assert not care_action_legal(
        assist_kind=CareAssistKind.HELP_SAFETY,
        allow_feed=False,
        allow_transport=False,
        allow_help_safety=True,
        allow_teach_learning=False,
        require_colocated=False,
        colocated=False,
        target_status=DependencyStatus.INDEPENDENT,
    )


def test_register_rejects_physiology_and_forbidden() -> None:
    agent = AgentId("a1")
    register = DependencyNeedRegister(
        agent_id=agent,
        deficits={"learning": 0.2, "movement": 0.1},
    )
    assert register.deficit_of(CareNeedId.LEARNING) == pytest.approx(0.2)
    updated = register.with_deficit(CareNeedId.LEARNING, 0.0)
    assert "learning" not in updated.deficits
    with pytest.raises(ValueError, match="dependency_care_physiology_need_in_register"):
        DependencyNeedRegister(agent_id=agent, deficits={"food": 0.5})
    with pytest.raises(ValueError, match="dependency_care_forbidden_need"):
        DependencyNeedRegister(agent_id=agent, deficits={"love": 0.1})
    with pytest.raises(ValueError, match="dependency_care_forbidden_need"):
        require_care_need_id("parenting")


def test_require_care_need_policy_consequence() -> None:
    ok = require_care_need_policy(
        CareNeedId.SHELTER,
        _policy(consequence="fatigue_accrual"),
    )
    assert ok.critical_consequence == "fatigue_accrual"
    with pytest.raises(ValueError, match="dependency_care_consequence_invalid"):
        require_care_need_policy(
            CareNeedId.MOVEMENT,
            _policy(consequence="health_damage"),
        )
