"""V4-06 formal-rule responses, positions, exceptions, and penalties."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from agents.cognition import (
    FormalRuleAct,
    FormalRuleAuthorityKind,
    FormalRuleClaim,
    FormalRuleConstraintKind,
    FormalRuleError,
    FormalRulePositionStance,
    FormalRuleProvenance,
    FormalRuleRecognition,
    FormalRuleReportKind,
    FormalRuleResponse,
    FormalRuleResponseKind,
    FormalRuleRevisionKind,
    FormalRuleScope,
    FormalRuleScopeKind,
    FormalRuleStatus,
    FormalRuleSystem,
    apply_formal_rule_update,
    appraise_formal_rule_position,
    default_formal_rule_policy,
    formal_rule_direction_preference,
    formal_rule_id,
    formal_rule_response_penalties,
    formal_rule_system_id,
    generate_formal_rule_position,
    select_formal_rule_response,
)
from agents.cognition.social_conventions import (
    ConventionBelief,
    ConventionContent,
    ConventionLedger,
    ConventionSituation,
    ConventionStatus,
    convention_belief_id,
)
from agents.cognition.social_norms import (
    NormBelief,
    NormContext,
    NormExpectation,
    NormLedger,
    NormPattern,
    NormStatus,
    norm_belief_id,
)
from agents.models import AgentId
from world.actions import AgentCommand
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservedArtifact,
    ObservedItemPlacement,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
SCOPE = FormalRuleScope(FormalRuleScopeKind.UNSPECIFIED, ())
ACTION = "maintain"
POLICY = default_formal_rule_policy()


def _system_id(authority: FormalRuleAuthorityKind) -> str:
    return formal_rule_system_id(OWNER.value, SCOPE.digest, authority)


def _rule_id(authority: FormalRuleAuthorityKind) -> str:
    return formal_rule_id(
        OWNER.value,
        _system_id(authority),
        FormalRuleConstraintKind.OBLIGATION,
        ACTION,
        SCOPE.digest,
    )


def _observation(
    *, tick: int = 1, integrity: RecordIntegrity | None = None
) -> Observation:
    artifacts: tuple[ObservedArtifact, ...] = ()
    if integrity is not None:
        artifacts = (
            ObservedArtifact(
                entity_id=EntityId("artifact-1"),
                kind=ArtifactKind.RECORD,
                author_id=EntityId("body-1"),
                created_tick=1,
                content=ArtifactContent(),
                content_revision=1,
                placement=ObservedItemPlacement.GROUND_HERE,
                record_genre=DurableRecordGenre.INSTRUCTION,
                integrity=integrity,
            ),
        )
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(tick),
        tick=tick,
        artifacts=artifacts,
        communications=(),
    )


def _interpretations() -> SimpleNamespace:
    return SimpleNamespace(
        interpretations=(
            SimpleNamespace(
                artifact_id=EntityId("artifact-1"),
                reading_marks=(ACTION,),
                reading_relations=(),
            ),
        )
    )


def _norm() -> NormLedger:
    pattern = NormPattern.SHARED_UPKEEP
    return NormLedger(
        owner_id=OWNER,
        beliefs=(
            NormBelief(
                belief_id=norm_belief_id(OWNER, pattern),
                owner_id=OWNER,
                pattern=pattern,
                expectation=NormExpectation.MAINTAIN_STRUCTURE,
                context=NormContext(pattern=pattern),
                status=NormStatus.ACTIVE,
                confidence=0.7,
            ),
        ),
    )


def _convention() -> ConventionLedger:
    content = ConventionContent(
        situation=ConventionSituation.COLOCATED_MEETING,
        usual_action="attack",
    )
    return ConventionLedger(
        owner_id=OWNER,
        beliefs=(
            ConventionBelief(
                belief_id=convention_belief_id(OWNER, content),
                owner_id=OWNER,
                content=content,
                status=ConventionStatus.ACTIVE,
                strength=0.6,
            ),
        ),
    )


def _office() -> SimpleNamespace:
    return SimpleNamespace(
        concepts=(
            SimpleNamespace(
                status="recognized",
                duties=(SimpleNamespace(duty_kind="maintain"),),
                supporters=(),
            ),
        )
    )


def _ledger(*, documented: bool = True, recognized: bool = True) -> Any:
    observation = _observation(integrity=RecordIntegrity.INTACT if documented else None)
    return apply_formal_rule_update(
        OWNER,
        1,
        observation,
        None,
        social_norms=_norm(),
        office_concepts=_office() if recognized else None,
        artifact_interpretations=_interpretations() if documented else None,
    )


def _oppose_claim(authority: FormalRuleAuthorityKind) -> FormalRuleClaim:
    return FormalRuleClaim(
        act=FormalRuleAct.OPPOSE,
        system_ref=_system_id(authority),
        rule_ref=_rule_id(authority),
    )


def _reinterpret_claim(authority: FormalRuleAuthorityKind) -> FormalRuleClaim:
    return FormalRuleClaim(
        act=FormalRuleAct.REINTERPRET,
        system_ref=_system_id(authority),
        rule_ref=_rule_id(authority),
    )


def _amend_claim(authority: FormalRuleAuthorityKind, revision: int) -> FormalRuleClaim:
    return FormalRuleClaim(
        act=FormalRuleAct.AMEND,
        system_ref=_system_id(authority),
        rule_ref=_rule_id(authority),
        revision=revision,
    )


def _appraise(ledger: Any, claim: Any) -> Any:
    return appraise_formal_rule_position(
        ledger, tick=2, claim=claim, policy=POLICY
    )


def test_each_response_kind_is_reachable_and_bounded() -> None:
    recognized = _ledger()
    assert recognized.rules[0].recognition is FormalRuleRecognition.RECOGNIZED
    follow_ledger, follow = select_formal_rule_response(
        recognized, tick=2, action_token=ACTION, policy=POLICY
    )
    assert follow is not None
    assert follow.kind is FormalRuleResponseKind.FOLLOW
    assert type(follow) is FormalRuleResponse

    ignored = apply_formal_rule_update(
        OWNER,
        1,
        _observation(),
        None,
        social_conventions=_convention(),
    )
    _, ignore = select_formal_rule_response(
        ignored, tick=2, action_token="attack", policy=POLICY
    )
    assert ignore is not None
    assert ignore.kind is FormalRuleResponseKind.IGNORE

    contested = _appraise(recognized, _oppose_claim(FormalRuleAuthorityKind.OFFICE))
    assert contested.rules[0].status is FormalRuleStatus.CONTESTED
    _, challenge = select_formal_rule_response(
        contested, tick=3, action_token=ACTION, policy=POLICY
    )
    assert challenge is not None
    assert challenge.kind is FormalRuleResponseKind.CHALLENGE

    damaged = apply_formal_rule_update(
        OWNER,
        1,
        _observation(integrity=RecordIntegrity.DAMAGED),
        None,
        social_norms=_norm(),
        artifact_interpretations=_interpretations(),
    )
    _, reinterpret = select_formal_rule_response(
        damaged, tick=3, action_token=ACTION, policy=POLICY
    )
    assert reinterpret is not None
    assert reinterpret.kind is FormalRuleResponseKind.REINTERPRET

    _, violate = select_formal_rule_response(
        contested,
        tick=3,
        action_token=ACTION,
        policy=POLICY,
        plan_action_tokens=(ACTION,),
    )
    assert violate is not None
    assert violate.kind is FormalRuleResponseKind.VIOLATE

    assert len(follow_ledger.rules[0].responses) == 1
    assert len(contested.rules[0].responses) == 0


def test_unobserved_action_never_yields_violate() -> None:
    contested = _appraise(
        _ledger(), _oppose_claim(FormalRuleAuthorityKind.OFFICE)
    )
    _, response = select_formal_rule_response(
        contested, tick=3, action_token=ACTION, policy=POLICY
    )
    assert response is not None
    assert response.kind is not FormalRuleResponseKind.VIOLATE


def test_ignore_is_not_treated_as_violation_or_refusal() -> None:
    ignored = apply_formal_rule_update(
        OWNER,
        1,
        _observation(),
        None,
        social_conventions=_convention(),
    )
    ledger, response = select_formal_rule_response(
        ignored, tick=2, action_token="attack", policy=POLICY
    )
    assert response is not None
    assert response.kind is FormalRuleResponseKind.IGNORE
    assert ledger.rules[0].sanctions == ignored.rules[0].sanctions
    assert ledger.rules[0].constraint is FormalRuleConstraintKind.PERMISSION


def test_expected_sanction_is_recorded_without_side_effects() -> None:
    ledger = _ledger()
    rule = ledger.rules[0]
    assert rule.sanctions
    assert all(item.severity <= 1.0 for item in rule.sanctions)
    updated, response = select_formal_rule_response(
        ledger, tick=2, action_token=ACTION, policy=POLICY
    )
    assert response is not None
    assert updated.rules[0].sanctions == rule.sanctions
    assert "relationship" not in repr(updated)


def test_exception_never_grants_permission_or_removes_prohibition() -> None:
    prohibition = apply_formal_rule_update(
        OWNER,
        1,
        _observation(),
        None,
        social_norms=NormLedger(
            owner_id=OWNER,
            beliefs=(
                NormBelief(
                    belief_id=norm_belief_id(OWNER, NormPattern.SPARE_AFTER_SLEEP),
                    owner_id=OWNER,
                    pattern=NormPattern.SPARE_AFTER_SLEEP,
                    expectation=NormExpectation.WITHHOLD_ATTACK,
                    context=NormContext(pattern=NormPattern.SPARE_AFTER_SLEEP),
                    status=NormStatus.ACTIVE,
                    confidence=0.7,
                ),
            ),
        ),
    )
    rule = prohibition.rules[0]
    assert rule.constraint is FormalRuleConstraintKind.PROHIBITION
    exemption = FormalRuleClaim(
        act=FormalRuleAct.REPORT,
        rule_ref=rule.rule_id,
        report_kind=FormalRuleReportKind.EXEMPTION,
    )
    updated = appraise_formal_rule_position(
        prohibition, tick=2, claim=exemption, policy=POLICY
    )
    new_rule = updated.rules[0]
    assert new_rule.constraint is FormalRuleConstraintKind.PROHIBITION
    assert new_rule.exceptions
    assert new_rule.versions[-1].exception_ids == tuple(
        item.exception_id for item in new_rule.exceptions
    )
    assert formal_rule_direction_preference(
        updated, action_token=rule.action_token
    ) < 0.0


def test_competing_systems_stay_contested_and_symmetric() -> None:
    first = _ledger(recognized=False)
    second = apply_formal_rule_update(
        OWNER,
        2,
        _observation(tick=2),
        first,
        social_norms=_norm(),
        office_concepts=_office(),
    )
    assert len(second.systems) == 2
    left, right = second.systems
    assert left.competing_system_ids == (right.system_id,)
    assert right.competing_system_ids == (left.system_id,)
    assert {system.status for system in second.systems} == {
        FormalRuleStatus.CONTESTED
    }


def test_response_selector_returns_no_command() -> None:
    ledger = _ledger()
    _, response = select_formal_rule_response(
        ledger, tick=2, action_token=ACTION, policy=POLICY
    )
    assert type(response) is FormalRuleResponse
    assert not isinstance(response, AgentCommand)
    assert not hasattr(response, "to_agent_command")
    for rule in ledger.rules:
        assert rule.responses == ()


def test_position_thresholds_and_reinterpretation_versions() -> None:
    ledger = _ledger()
    rule = ledger.rules[0]
    positioned = generate_formal_rule_position(
        ledger, tick=2, rule_id=rule.rule_id, policy=POLICY
    )
    assert any(
        proponent.stance is FormalRulePositionStance.SUPPORTER
        for proponent in positioned.rules[0].proponents
    )

    reinterpreted = _appraise(
        positioned, _reinterpret_claim(FormalRuleAuthorityKind.OFFICE)
    )
    new_rule = reinterpreted.rules[0]
    assert len(new_rule.versions) == 2
    assert (
        new_rule.versions[-1].revision_kind
        is FormalRuleRevisionKind.REINTERPRETATION
    )
    assert new_rule.versions[-1].provenance is FormalRuleProvenance.REINTERPRETATION
    assert any(
        proponent.stance is FormalRulePositionStance.REINTERPRETER
        for proponent in new_rule.proponents
    )


def test_out_of_order_amendment_is_rejected() -> None:
    ledger = _ledger()
    rule = ledger.rules[0]
    rejected = _appraise(
        ledger, _amend_claim(FormalRuleAuthorityKind.OFFICE, 5)
    )
    assert len(rejected.rules[0].versions) == len(rule.versions)
    assert "formal_rule_version_out_of_order" in rejected.rules[0].notices

    accepted = _appraise(
        ledger, _amend_claim(FormalRuleAuthorityKind.OFFICE, 2)
    )
    assert len(accepted.rules[0].versions) == len(rule.versions) + 1
    assert (
        accepted.rules[0].versions[-1].revision_kind
        is FormalRuleRevisionKind.AMENDMENT
    )


def test_direction_preference_is_bounded() -> None:
    recognized = _ledger()
    assert 0.0 < formal_rule_direction_preference(
        recognized, action_token=ACTION
    ) <= 0.25

    contested = _appraise(
        recognized, _oppose_claim(FormalRuleAuthorityKind.OFFICE)
    )
    value = formal_rule_direction_preference(contested, action_token=ACTION)
    assert -0.25 <= value < 0.0

    assert (
        formal_rule_direction_preference(recognized, action_token="wait") == 0.0
    )
    with pytest.raises(FormalRuleError) as excinfo:
        formal_rule_direction_preference(recognized, action_token="not_an_action")
    assert excinfo.value.code == "formal_rule_action_invalid"

    penalties = formal_rule_response_penalties(contested, tick=3)
    assert all(0.0 <= value <= 0.25 for value in penalties.values())
    assert not isinstance(penalties, dict)


def test_unknown_action_and_response_are_rejected() -> None:
    ledger = _ledger()
    with pytest.raises(FormalRuleError) as excinfo:
        select_formal_rule_response(
            ledger, tick=2, action_token="not_an_action", policy=POLICY
        )
    assert excinfo.value.code == "formal_rule_action_invalid"

    with pytest.raises(TypeError):
        select_formal_rule_response(
            object(),  # type: ignore[arg-type]
            tick=2,
            action_token=ACTION,
            policy=POLICY,
        )


def test_manual_system_listing_matches_rules() -> None:
    ledger = _ledger()
    assert len(ledger.systems) == 1
    system: FormalRuleSystem = ledger.systems[0]
    assert system.rule_ids == (ledger.rules[0].rule_id,)
