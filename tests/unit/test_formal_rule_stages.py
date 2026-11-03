"""V4-06 formal-rule stage derivation, versions, and competing systems."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    FormalRuleAct,
    FormalRuleAuthorityKind,
    FormalRuleClaim,
    FormalRuleConstraintKind,
    FormalRuleError,
    FormalRuleEvidenceChannel,
    FormalRuleLedger,
    FormalRuleRecognition,
    FormalRuleScope,
    FormalRuleScopeKind,
    FormalRuleStage,
    FormalRuleStatus,
    apply_formal_rule_update,
    formal_rule_claim_relation,
    formal_rule_id,
    formal_rule_ledger_digest,
    formal_rule_system_id,
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
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.communications import CommunicationRelation
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservedArtifact,
    ObservedItemPlacement,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
THIRD = AgentId("agent-3")

SCOPE = FormalRuleScope(FormalRuleScopeKind.UNSPECIFIED, ())
ACTION = "maintain"


def _system_id(authority: FormalRuleAuthorityKind) -> str:
    return formal_rule_system_id(OWNER.value, SCOPE.digest, authority)


def _rule_id(
    authority: FormalRuleAuthorityKind,
    constraint: FormalRuleConstraintKind,
) -> str:
    return formal_rule_id(
        OWNER.value,
        _system_id(authority),
        constraint,
        ACTION,
        SCOPE.digest,
    )


def _observation(
    *,
    attack: int = 1,
    artifacts: tuple[ObservedArtifact, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(attack),
        tick=attack,
        artifacts=artifacts,
        communications=(),
    )


def _artifact(integrity: RecordIntegrity = RecordIntegrity.INTACT) -> ObservedArtifact:
    return ObservedArtifact(
        entity_id=EntityId("artifact-1"),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=1,
        content=ArtifactContent(),
        content_revision=1,
        placement=ObservedItemPlacement.GROUND_HERE,
        record_genre=DurableRecordGenre.INSTRUCTION,
        integrity=integrity,
    )


def _interpretations(*marks: str) -> SimpleNamespace:
    return SimpleNamespace(
        interpretations=(
            SimpleNamespace(
                artifact_id=EntityId("artifact-1"),
                reading_marks=marks,
                reading_relations=(),
            ),
        )
    )


def _norm(
    expectation: NormExpectation = NormExpectation.MAINTAIN_STRUCTURE,
    pattern: NormPattern = NormPattern.SHARED_UPKEEP,
    supporters: tuple[AgentId, ...] = (),
) -> NormLedger:
    return NormLedger(
        owner_id=OWNER,
        beliefs=(
            NormBelief(
                belief_id=norm_belief_id(OWNER, pattern),
                owner_id=OWNER,
                pattern=pattern,
                expectation=expectation,
                context=NormContext(pattern=pattern),
                status=NormStatus.ACTIVE,
                confidence=0.7,
                supporters=supporters,
            ),
        ),
    )


def _convention(action: str = "attack") -> ConventionLedger:
    content = ConventionContent(
        situation=ConventionSituation.COLOCATED_MEETING,
        usual_action=action,
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


def _claim_observation(
    *claims: FormalRuleClaim,
    attack: int = 1,
    artifacts: tuple[ObservedArtifact, ...] = (),
) -> SimpleNamespace:
    relations = tuple(
        CommunicationRelation(
            subject=subject, predicate=predicate, object=body
        )
        for claim in claims
        for subject, predicate, body in (formal_rule_claim_relation(claim),)
    )
    return SimpleNamespace(
        tick=attack,
        artifacts=artifacts,
        communications=(
            SimpleNamespace(
                speaker_id=EntityId("body-2"),
                utterance=SimpleNamespace(
                    content=SimpleNamespace(relations=relations)
                ),
            ),
        ),
    )


def _support_claim(authority: FormalRuleAuthorityKind) -> FormalRuleClaim:
    return FormalRuleClaim(
        act=FormalRuleAct.SUPPORT,
        system_ref=_system_id(authority),
        rule_ref=_rule_id(
            authority, FormalRuleConstraintKind.OBLIGATION
        ),
    )


def _recognize_claim(authority: FormalRuleAuthorityKind) -> FormalRuleClaim:
    return FormalRuleClaim(
        act=FormalRuleAct.RECOGNIZE,
        system_ref=_system_id(authority),
        rule_ref=_rule_id(
            authority, FormalRuleConstraintKind.OBLIGATION
        ),
        authority_kind=FormalRuleAuthorityKind.OFFICE,
    )


def _update(
    observation: object,
    *,
    tick: int,
    prior: FormalRuleLedger | None = None,
    social_norms: object | None = None,
    social_conventions: object | None = None,
    office_concepts: object | None = None,
    artifact_interpretations: object | None = None,
) -> FormalRuleLedger:
    return apply_formal_rule_update(
        OWNER,
        tick,
        observation,
        prior,
        social_norms=social_norms,
        social_conventions=social_conventions,
        office_concepts=office_concepts,
        artifact_interpretations=artifact_interpretations,
    )


def test_convention_only_stays_habit() -> None:
    ledger = _update(
        _observation(),
        tick=1,
        social_conventions=_convention(),
    )
    assert len(ledger.rules) == 1
    rule = ledger.rules[0]
    assert rule.stage is FormalRuleStage.HABIT
    assert rule.constraint is FormalRuleConstraintKind.PERMISSION
    assert rule.recognition is FormalRuleRecognition.UNRECOGNIZED
    assert rule.versions[0].written is None
    assert rule.versions[0].provenance.value == "derived_from_convention"


def test_active_norm_reaches_norm_stage() -> None:
    ledger = _update(
        _observation(),
        tick=1,
        social_norms=_norm(
            expectation=NormExpectation.WITHHOLD_ATTACK,
            pattern=NormPattern.SPARE_AFTER_SLEEP,
        ),
    )
    rule = ledger.rules[0]
    assert rule.stage is FormalRuleStage.NORM
    assert rule.action_token == "withhold"
    assert rule.constraint is FormalRuleConstraintKind.PROHIBITION
    assert rule.recognition is FormalRuleRecognition.CLAIMED
    assert rule.evidence[0].channel is FormalRuleEvidenceChannel.OBSERVED


def test_intact_durable_record_promotes_to_documented() -> None:
    ledger = _update(
        _observation(artifacts=(_artifact(),)),
        tick=1,
        social_norms=_norm(),
        artifact_interpretations=_interpretations(ACTION),
    )
    rule = ledger.rules[0]
    assert rule.stage is FormalRuleStage.DOCUMENTED
    written = rule.versions[-1].written
    assert written is not None
    assert written.artifact_id == "artifact-1"
    assert written.status.value == "intact"


def test_recognized_office_or_decision_promotes_to_recognized_enforcement() -> None:
    ledger = _update(
        _claim_observation(
            _support_claim(FormalRuleAuthorityKind.OFFICE),
            artifacts=(_artifact(),),
        ),
        tick=1,
        social_norms=_norm(),
        office_concepts=_office(),
        artifact_interpretations=_interpretations(ACTION),
    )
    rule = ledger.rules[0]
    assert rule.system_id == _system_id(FormalRuleAuthorityKind.OFFICE)
    assert rule.stage is FormalRuleStage.RECOGNIZED_ENFORCEMENT
    assert rule.recognition is FormalRuleRecognition.RECOGNIZED
    assert {proponent.actor_id for proponent in rule.proponents} >= {
        OWNER.value,
        "body-2",
    }


def test_two_explicit_recognize_claims_promote_a_documented_rule() -> None:
    observation = _claim_observation(
        _recognize_claim(FormalRuleAuthorityKind.CUSTOM),
        _recognize_claim(FormalRuleAuthorityKind.CUSTOM),
        attack=1,
        artifacts=(_artifact(),),
    )
    ledger = _update(
        observation,
        tick=1,
        social_norms=_norm(),
        artifact_interpretations=_interpretations(ACTION),
    )
    rule = ledger.rules[0]
    assert rule.stage is FormalRuleStage.RECOGNIZED_ENFORCEMENT
    assert rule.recognition is FormalRuleRecognition.RECOGNIZED


def test_stage_never_regresses_when_evidence_fades() -> None:
    first = _update(
        _claim_observation(
            _support_claim(FormalRuleAuthorityKind.OFFICE),
            artifacts=(_artifact(),),
        ),
        tick=1,
        social_norms=_norm(),
        office_concepts=_office(),
        artifact_interpretations=_interpretations(ACTION),
    )
    assert first.rules[0].stage is FormalRuleStage.RECOGNIZED_ENFORCEMENT

    second = _update(
        _observation(attack=2, artifacts=(_artifact(),)),
        tick=2,
        prior=first,
        social_norms=_norm(),
        office_concepts=_office(),
        artifact_interpretations=_interpretations(ACTION),
    )
    rule = second.rules[0]
    assert rule.stage is FormalRuleStage.RECOGNIZED_ENFORCEMENT
    assert rule.versions[-1].stage is FormalRuleStage.RECOGNIZED_ENFORCEMENT


def test_missing_or_damaged_record_degrades_representation_not_stage() -> None:
    damaged = _update(
        _observation(artifacts=(_artifact(RecordIntegrity.DAMAGED),)),
        tick=1,
        social_norms=_norm(),
        artifact_interpretations=_interpretations(ACTION),
    )
    damaged_rule = damaged.rules[0]
    assert damaged_rule.stage is FormalRuleStage.DOCUMENTED
    assert damaged_rule.versions[-1].written is not None
    assert damaged_rule.versions[-1].written.status.value == "damaged"

    missing = _update(
        _observation(attack=2),
        tick=2,
        prior=damaged,
        social_norms=_norm(),
    )
    missing_rule = missing.rules[0]
    assert missing_rule.stage is FormalRuleStage.DOCUMENTED
    assert missing_rule.versions[-1].written is not None
    assert missing_rule.versions[-1].written.status.value == "missing"
    assert "representation_missing" in missing_rule.notices


def test_versions_append_only_on_material_change() -> None:
    first = _update(_observation(), tick=1, social_norms=_norm())
    assert len(first.rules[0].versions) == 1

    second = _update(
        _observation(attack=2, artifacts=(_artifact(),)),
        tick=2,
        prior=first,
        social_norms=_norm(),
        artifact_interpretations=_interpretations(ACTION),
    )
    assert second.rules[0].stage is FormalRuleStage.DOCUMENTED
    assert len(second.rules[0].versions) == 2
    assert second.rules[0].versions[1].supersedes_version_id == (
        second.rules[0].versions[0].version_id
    )

    third = _update(
        _observation(attack=3, artifacts=(_artifact(),)),
        tick=3,
        prior=second,
        social_norms=_norm(),
        artifact_interpretations=_interpretations(ACTION),
    )
    assert len(third.rules[0].versions) == 2


def test_out_of_order_version_keeps_prior_and_notices() -> None:
    first = _update(_observation(), tick=1, social_norms=_norm())
    amendment = FormalRuleClaim(
        act=FormalRuleAct.AMEND,
        system_ref=_system_id(FormalRuleAuthorityKind.CUSTOM),
        rule_ref=_rule_id(
            FormalRuleAuthorityKind.CUSTOM,
            FormalRuleConstraintKind.OBLIGATION,
        ),
        revision=5,
    )
    second = _update(
        _claim_observation(amendment, attack=2),
        tick=2,
        prior=first,
        social_norms=_norm(),
    )
    rule = second.rules[0]
    assert len(rule.versions) == 1
    assert "formal_rule_version_out_of_order" in rule.notices


def test_two_owners_opposite_constraints_form_competing_systems() -> None:
    first = _update(_observation(), tick=1, social_norms=_norm())
    second = _update(
        _observation(attack=2),
        tick=2,
        prior=first,
        social_norms=_norm(),
        office_concepts=_office(),
    )
    assert len(second.rules) == 2
    assert len(second.systems) == 2
    left, right = second.systems
    assert left.competing_system_ids == (right.system_id,)
    assert right.competing_system_ids == (left.system_id,)
    assert left.status is FormalRuleStatus.CONTESTED
    assert right.status is FormalRuleStatus.CONTESTED
    assert {rule.status for rule in second.rules} == {FormalRuleStatus.CONTESTED}


def test_claim_without_matching_system_is_orphaned() -> None:
    orphan = FormalRuleClaim(
        act=FormalRuleAct.SUPPORT,
        system_ref="frs-" + "0" * 16,
        rule_ref="frl-" + "0" * 16,
    )
    ledger = _update(
        _claim_observation(orphan),
        tick=1,
    )
    assert ledger.rules == ()
    assert "orphaned_rule_system" in ledger.notices


def test_update_rejects_world_state_events_rules_and_metrics() -> None:
    for name in ("WorldState", "WorldEvent", "PhysicalRules", "MetricDocument"):
        forbidden = type(name, (), {})()
        with pytest.raises(FormalRuleError) as excinfo:
            _update(forbidden, tick=1)
        assert excinfo.value.code == "formal_rule_forbidden_input"

    foreign = FormalRuleLedger(owner_id=OTHER)
    with pytest.raises(FormalRuleError) as excinfo:
        _update(_observation(), tick=1, prior=foreign)
    assert excinfo.value.code == "formal_rule_owner_mismatch"


def test_repeated_updates_are_identical() -> None:
    first = _update(
        _observation(artifacts=(_artifact(),)),
        tick=1,
        social_norms=_norm(),
        artifact_interpretations=_interpretations(ACTION),
    )
    second = _update(
        _observation(artifacts=(_artifact(),)),
        tick=1,
        social_norms=_norm(),
        artifact_interpretations=_interpretations(ACTION),
    )
    assert formal_rule_ledger_digest(first) == formal_rule_ledger_digest(second)
    assert first == second
