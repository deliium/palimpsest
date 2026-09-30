"""Competence beliefs may bias command choice without changing world math."""

from __future__ import annotations

import logging
from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition.competence import (
    CompetenceBelief,
    CompetenceDomain,
    CompetenceSelfModel,
    competence_direction_term,
    default_competence_belief_policy,
    empty_competence_model,
)
from agents.cognition.competence_selection import (
    CompetenceSelectionOutput,
    select_competence_domains,
)
from agents.cognition.deliberation import _compile_command, _pairwise_compare
from agents.cognition.models import (
    ActionDirection,
    FutureAppraisal,
    ImaginedFuture,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    PossibleFutures,
    SituationClaimCode,
)
from agents.models import AgentId
from simulation.lifecycle import ActionSubmission
from tests.physical_helpers import make_engine, two_location_fixture
from tests.unit.test_skill_resolution import _engine, _search_bit
from world._skills import (
    ObjectiveSkillLedger,
    adjusted_move_fatigue,
    adjusted_search_probability,
    default_objective_skill_policy,
)
from world.actions import Move, Search
from world.events import Moved
from world.identifiers import EntityId
from world.models import default_physical_rules
from world.values import clamp_unit_interval

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")


def _model(levels: dict[CompetenceDomain, float]) -> CompetenceSelfModel:
    blank = empty_competence_model(_OWNER)
    beliefs = tuple(
        CompetenceBelief(
            domain=belief.domain,
            believed_level=levels.get(belief.domain, 0.0),
            support_mass=0.0,
            counter_mass=0.0,
        )
        for belief in blank.beliefs
    )
    return CompetenceSelfModel(
        owner_id=blank.owner_id,
        beliefs=beliefs,
        cursors=blank.cursors,
    )


def _future(
    future_id: str, direction: ActionDirection, target: str | None
) -> ImaginedFuture:
    return ImaginedFuture(
        future_id=future_id,
        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
        confidence=0.5,
        direction=direction,
        target_entity_id=target,
    )


def _appraisal(future: ImaginedFuture, *, goals: int = 0) -> FutureAppraisal:
    return FutureAppraisal(future_id=future.future_id, support_goal_count=goals)


def _motivation(*appraisals: FutureAppraisal) -> MotivationEvaluation:
    return MotivationEvaluation(
        owner_id=_OWNER,
        scores=(MotivationScore(motive=MotivationCode.WAIT, score=0.5),),
        confidence=0.5,
        appraisals=appraisals,
        active_drive_kinds=(),
    )


def test_belief_breaks_a_tie_and_an_integer_vote_still_wins() -> None:
    search = _future("search", ActionDirection.SEARCH, None)
    wait = _future("wait", ActionDirection.WAIT, None)
    futures = {search.future_id: search, wait.future_id: wait}
    model = _model({CompetenceDomain.FORAGING: 1.0})
    policy = default_competence_belief_policy()
    tied = _pairwise_compare(
        _appraisal(search),
        _appraisal(wait),
        futures,
        _motivation(),
        competence_model=model,
        competence_weight=policy.belief_action_weight,
        owner_id=_OWNER,
    )
    assert tied == 1
    unchanged = _pairwise_compare(
        _appraisal(search),
        _appraisal(wait),
        futures,
        _motivation(),
    )
    assert unchanged == 0
    integer = _pairwise_compare(
        _appraisal(wait, goals=1),
        _appraisal(search),
        futures,
        _motivation(),
        competence_model=model,
        competence_weight=policy.belief_action_weight,
        owner_id=_OWNER,
    )
    assert integer == 1


def test_competence_bias_log_uses_domain_not_probability(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.competence")
    model = _model({CompetenceDomain.FORAGING: 1.0})
    competence_direction_term(
        model,
        direction=ActionDirection.SEARCH,
        targeted_search=False,
        owner_id=_OWNER,
        weight=0.25,
    )
    competence_direction_term(
        model,
        direction="not-a-direction",
        targeted_search=False,
        owner_id=_OWNER,
        weight=0.25,
    )
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "competence_bias" in messages
    assert "domain=foraging" in messages
    assert "reason_code=unknown_domain" in messages
    assert "probability" not in messages
    assert "utterance" not in messages


def test_search_preference_follows_believed_domain() -> None:
    fixture = two_location_fixture(item_on_ground=False)
    engine = make_engine(fixture, seed=3)
    engine.observe()
    observation = engine.observation_for(AgentId("agent-1"))
    targeted = _future("targeted", ActionDirection.SEARCH, "res-food")
    untargeted = _future("open", ActionDirection.SEARCH, None)
    futures = PossibleFutures(
        owner_id=_OWNER, futures=(targeted, untargeted), confidence=0.5
    )
    command = _compile_command(
        targeted,
        observation,
        owner_id=_OWNER,
        futures=futures,
        competence_model=_model({CompetenceDomain.FORAGING: 1.0}),
    )
    assert command == Search()
    reverse = _compile_command(
        untargeted,
        observation,
        owner_id=_OWNER,
        futures=futures,
        competence_model=_model({CompetenceDomain.RESOURCE_DETECTION: 1.0}),
    )
    assert reverse == Search(target_id=EntityId("res-food"))


def test_believed_skill_does_not_change_level_zero_world_math() -> None:
    model = _model(
        {CompetenceDomain.FORAGING: 1.0, CompetenceDomain.NAVIGATION: 1.0}
    )
    assert model.belief_for(CompetenceDomain.FORAGING).believed_level == 1.0
    policy = default_objective_skill_policy()
    rules = default_physical_rules()
    level_zero = adjusted_search_probability(
        search_base_probability=rules.search_base_probability,
        search_visibility_weight=rules.search_visibility_weight,
        visibility=0.5,
        foraging_level=0.0,
        resource_detection_level=0.0,
        policy=policy,
    )
    expected = clamp_unit_interval(
        rules.search_base_probability + rules.search_visibility_weight * 0.5
    )
    assert level_zero == expected
    assert adjusted_move_fatigue(rules.move_fatigue, 0.0, policy) == 5.0
    zeros = ObjectiveSkillLedger.bootstrap((EntityId("body-1"),))
    enabled = _engine(11, policy=policy, enabled=("body-1",), ledger=zeros)
    disabled = make_engine(two_location_fixture(item_on_ground=False), seed=11)
    assert _search_bit(enabled, "agent-1") is _search_bit(disabled, "agent-1")
    assert _move_delta(enabled_seed_engine()) == _move_delta(disabled_seed_engine())


def enabled_seed_engine():
    policy = default_objective_skill_policy()
    return _engine(
        11,
        policy=policy,
        enabled=("body-1",),
        ledger=ObjectiveSkillLedger.bootstrap((EntityId("body-1"),)),
    )


def disabled_seed_engine():
    return make_engine(two_location_fixture(item_on_ground=False), seed=11)


def _move_delta(engine) -> float:
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Move(EntityId("loc-2"))),)
    )
    moved = next(
        record.event.details
        for record in result.events
        if type(record.event.details) is Moved
    )
    assert type(moved) is Moved
    assert moved.fatigue_delta is not None
    return moved.fatigue_delta


@pytest.mark.asyncio
async def test_provider_off_never_calls_generate_and_bad_tokens_fall_back() -> None:
    model = empty_competence_model(_OWNER)

    class _Provider:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, _request: object) -> object:
            self.calls += 1
            return SimpleNamespace(
                output=CompetenceSelectionOutput(selected_domains=("wizardry",))
            )

    idle = _Provider()
    same = await select_competence_domains(
        model,
        default_competence_belief_policy(),
        provider=idle,
        tick=1,
    )
    assert idle.calls == 0
    assert same.selection_fallback_used is False
    policy = replace(default_competence_belief_policy(), allow_provider=True)
    failed = await select_competence_domains(
        model, policy, provider=_Provider(), tick=1
    )
    assert failed.selection_fallback_used is True
    assert failed.preferred_domains == ()

    class _Accepted(_Provider):
        async def generate(self, _request: object) -> object:
            return SimpleNamespace(
                output=CompetenceSelectionOutput(selected_domains=("foraging",))
            )

    ranked = await select_competence_domains(
        model, policy, provider=_Accepted(), tick=1
    )
    assert ranked.preferred_domains == ("foraging",)
    assert ranked.selection_fallback_used is False
