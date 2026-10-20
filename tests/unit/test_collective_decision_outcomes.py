"""Owner-visible collective-decision outcomes and compliance appraisal."""

from __future__ import annotations

from agents.cognition.collective_decisions import (
    CollectiveComplianceStatus,
    CollectiveDecisionLedger,
    CollectiveEvidence,
    CollectiveEvidenceChannel,
    CollectivePosition,
    CollectivePositionStance,
    CollectiveProposal,
    CollectiveTopic,
    appraise_collective_compliance,
    collective_decision_evidence_id,
    collective_proposal_id,
    collective_proposal_ref,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from analysis.collective_decisions import (
    harvest_collective_decision_rows,
    harvest_collective_decision_snapshot,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_OWNER = AgentId("ada")
_BEN = AgentId("ben")
_CONTEXT = "a" * 16


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_BEN, entity_id=EntityId("body-ben")),
        ),
    )


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-ada"),
        location_id=EntityId("clearing"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _occurrence(kind: str, actor: str, tick: int) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=max(tick - 1, 0),
            source_event_id=EventId(f"event-{tick}-{kind}-{actor}"),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId(actor),
        success=True,
    )


def _observation(
    *, tick: int, occurrences: tuple[ObservedOccurrence, ...] = ()
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(),
        occurrences=occurrences,
        communications=(),
    )


def _proposal(
    *,
    topic: CollectiveTopic = CollectiveTopic.MIGRATION,
    window_last: int = 10,
    actor: AgentId = _BEN,
) -> CollectiveProposal:
    ref = collective_proposal_ref(
        _OWNER,
        originator_id=actor,
        topic=topic,
        context_key=_CONTEXT,
        inception_tick=1,
        inception_lineage="outcome",
    )
    evidence = CollectiveEvidence(
        evidence_id=collective_decision_evidence_id(
            ref, 0, CollectiveEvidenceChannel.OBSERVED, "lineage"
        ),
        ordinal=0,
        channel=CollectiveEvidenceChannel.OBSERVED,
        lineage_ref="lineage",
        root_ref="root",
        tick=1,
    )
    return CollectiveProposal(
        proposal_id=collective_proposal_id(_OWNER, ref, 0),
        owner_id=_OWNER,
        proposal_ref=ref,
        revision=0,
        topic=topic,
        context_key=_CONTEXT,
        action_token="move",
        first_tick=1,
        last_tick=1,
        window_first_tick=1,
        window_last_tick=window_last,
        originator_id=actor,
        evidence=(evidence,),
    )


def _ledger(
    *,
    topic: CollectiveTopic = CollectiveTopic.MIGRATION,
    actor: AgentId = _BEN,
    window_last: int = 10,
) -> CollectiveDecisionLedger:
    proposal = _proposal(topic=topic, actor=actor, window_last=window_last)
    position = CollectivePosition(
        position_id="a" * 64,
        actor_id=actor,
        proposal_ref=proposal.proposal_ref,
        revision=0,
        stance=CollectivePositionStance.SUPPORT,
        strength=0.7,
        channel=CollectiveEvidenceChannel.OBSERVED,
        root_ref="root",
        independently_evidenced=True,
        first_tick=1,
        last_tick=1,
        evidence_id="b" * 64,
    )
    return CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(proposal,),
        positions=(position,),
    )


def _appraise(ledger, *, tick: int, occurrences) -> object:
    return appraise_collective_compliance(
        ledger,
        _observation(tick=tick, occurrences=occurrences),
        _identity(),
    )


def test_matching_action_is_matched_and_harvested() -> None:
    updated = _appraise(
        _ledger(),
        tick=3,
        occurrences=(_occurrence("move", "body-ben", 3),),
    )
    assert len(updated.compliance) == 1
    assert updated.compliance[0].status is CollectiveComplianceStatus.MATCHED
    snapshot = harvest_collective_decision_snapshot(updated)
    assert snapshot.compliance[0].status == "matched"
    assert snapshot.compliance[0].observed_action_token == "move"


def test_contrary_action_is_descriptive_not_punitive() -> None:
    updated = _appraise(
        _ledger(),
        tick=3,
        occurrences=(_occurrence("fled", "body-ben", 3),),
    )
    assert updated.compliance[0].status is CollectiveComplianceStatus.CONTRARY
    assert updated.outcomes == ()


def test_wrong_actor_and_absent_visibility_remain_unknown() -> None:
    updated = _appraise(
        _ledger(),
        tick=3,
        occurrences=(_occurrence("move", "body-carol", 3),),
    )
    assert updated.compliance[0].status is CollectiveComplianceStatus.UNKNOWN
    empty = _appraise(_ledger(), tick=3, occurrences=())
    assert empty.compliance[0].status is CollectiveComplianceStatus.UNKNOWN


def test_death_is_not_defiance() -> None:
    updated = _appraise(
        _ledger(),
        tick=3,
        occurrences=(_occurrence("died", "body-ben", 3),),
    )
    assert updated.compliance[0].status is CollectiveComplianceStatus.UNKNOWN


def test_action_outside_the_window_does_not_count() -> None:
    updated = _appraise(
        _ledger(window_last=2),
        tick=4,
        occurrences=(_occurrence("move", "body-ben", 4),),
    )
    assert updated.compliance[0].window_last_tick == 2
    assert updated.compliance[0].status is CollectiveComplianceStatus.UNKNOWN


def test_different_topic_kinds_do_not_match() -> None:
    updated = _appraise(
        _ledger(topic=CollectiveTopic.COLLECTIVE_PROJECT),
        tick=3,
        occurrences=(_occurrence("move", "body-ben", 3),),
    )
    assert updated.compliance[0].status is CollectiveComplianceStatus.UNKNOWN


def test_harvest_preserves_multiple_owners_and_coverage() -> None:
    first = harvest_collective_decision_snapshot(_ledger())
    second = harvest_collective_decision_snapshot(
        CollectiveDecisionLedger(
            owner_id=AgentId("carol"),
            first_observed_tick=2,
            last_observed_tick=4,
            observation_count=3,
            pruned_evidence_count=2,
        )
    )
    rows = harvest_collective_decision_rows(
        [_ledger(), CollectiveDecisionLedger(owner_id=AgentId("carol"))]
    )
    assert [item.owner_id for item in rows] == ["ada", "carol"]
    assert first.enabled and first.coverage == "complete"
    assert second.coverage == "partial"
    assert second.first_observed_tick == 2
    assert second.observation_count == 3
