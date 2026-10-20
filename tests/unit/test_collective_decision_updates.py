"""Deterministic owner-local collective-decision updates and provenance."""

from __future__ import annotations

import pytest

from agents.cognition.collective_decisions import (
    CollectiveEvidenceChannel,
    CollectiveExecutionStatus,
    CollectivePositionStance,
    CollectiveProposalStatus,
    CollectiveTopic,
    apply_collective_decision_update,
    collective_context_key,
    collective_proposal_id,
    collective_proposal_ref,
    create_collective_proposal,
    empty_collective_decision_ledger,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
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
_CAROL = AgentId("carol")
_TOPIC = CollectiveTopic.COLLECTIVE_PROJECT


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_BEN, entity_id=EntityId("body-ben")),
            CounterpartBinding(agent_id=_CAROL, entity_id=EntityId("body-carol")),
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


def _observation(
    *,
    tick: int,
    communications: tuple[ObservedCommunication, ...] = (),
    occurrences: tuple[object, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(),
        occurrences=occurrences,
        communications=communications,
    )


def _message(
    *,
    tick: int,
    speaker: str,
    root: str,
    relation: CommunicationRelation,
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="collective",
        speaker_id=EntityId(speaker),
        communication_id=root,
        relations=(relation,),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=max(tick - 1, 0),
            source_event_id=EventId(f"event-{root}"),
        ),
        speaker_id=EntityId(speaker),
        listener_id=EntityId("body-ada"),
        utterance=utterance,
        action_kind="tell",
    )


def _ref(
    *,
    owner: AgentId = _OWNER,
    tick: int = 1,
    lineage: str = "first",
    topic: CollectiveTopic = _TOPIC,
) -> str:
    context = collective_context_key(_observation(tick=tick))
    return collective_proposal_ref(
        owner,
        originator_id=_OWNER,
        topic=topic,
        context_key=context,
        inception_tick=tick,
        inception_lineage=lineage,
    )


def _propose(
    *,
    tick: int,
    ref: str,
    speaker: str = "body-ben",
    revision: int = 0,
    action: str = "start_project",
    target: str = "-",
    terms: str = "-",
    first: int | None = None,
    last: int | None = None,
    context: str | None = None,
    root: str | None = None,
) -> ObservedCommunication:
    first_window = tick if first is None else first
    last_window = tick + 8 if last is None else last
    context_key = context or collective_context_key(_observation(tick=tick))
    payload = (
        f"{ref}|{revision}|{action}|{target}|{terms}|"
        f"{first_window}|{last_window}|{context_key}"
    )
    return _message(
        tick=tick,
        speaker=speaker,
        root=root or f"propose-{tick}-{revision}",
        relation=CommunicationRelation(
            subject=_TOPIC.value,
            predicate="collective_propose",
            object=payload,
        ),
    )


def _act(
    *,
    tick: int,
    speaker: str,
    ref: str,
    revision: int,
    predicate: str,
    object_payload: str,
    root: str | None = None,
) -> ObservedCommunication:
    return _message(
        tick=tick,
        speaker=speaker,
        root=root or f"{predicate}-{tick}-{revision}",
        relation=CommunicationRelation(
            subject=_TOPIC.value,
            predicate=predicate,
            object=f"{ref}|{revision}|{object_payload}",
        ),
    )


def _apply(
    *communications: ObservedCommunication,
    tick: int,
    previous: object = None,
) -> object:
    return apply_collective_decision_update(
        _observation(tick=tick, communications=tuple(communications)),
        _identity(),
        previous,
    )


def test_proposal_generation_is_a_draft_not_a_decision() -> None:
    observation = _observation(tick=1)
    proposal = create_collective_proposal(
        _OWNER,
        topic=_TOPIC,
        context_key=collective_context_key(observation),
        action_token="start_project",
        tick=1,
        originator_id=_OWNER,
        terms=("dig_channel",),
    )
    assert proposal.status is CollectiveProposalStatus.DRAFT
    assert proposal.evidence == ()
    assert proposal.owner_id == _OWNER
    assert proposal.proposal_id == collective_proposal_id(
        _OWNER, proposal.proposal_ref, 0
    )
    with pytest.raises(ValueError):
        create_collective_proposal(
            _OWNER,
            topic=_TOPIC,
            context_key=collective_context_key(observation),
            action_token="start_project",
            tick=1,
            window_first_tick=0,
            window_last_tick=99,
        )


def test_observed_proposal_and_idempotent_replay() -> None:
    ref = _ref()
    message = _propose(tick=1, ref=ref)
    first = _apply(message, tick=1)
    second = _apply(message, tick=1, previous=first)
    assert first.has_content
    assert second == first
    assert len(first.proposals) == 1
    proposal = first.proposals[0]
    assert proposal.status is CollectiveProposalStatus.ACTIVE
    assert proposal.originator_id == _BEN
    assert proposal.supports_tick(2)
    assert first.first_observed_tick == 1
    assert first.observation_count == 1


def test_support_and_opposition_are_separate_provenance_records() -> None:
    ref = _ref()
    proposed = _apply(_propose(tick=1, ref=ref), tick=1)
    support = _apply(
        _act(
            tick=2,
            speaker="body-carol",
            ref=ref,
            revision=0,
            predicate="collective_support",
            object_payload="-",
        ),
        tick=2,
        previous=proposed,
    )
    assert len(support.positions) == 1
    position = support.positions[0]
    assert position.actor_id == _CAROL
    assert position.stance is CollectivePositionStance.SUPPORT
    assert position.channel is CollectiveEvidenceChannel.COMMUNICATED
    oppose = _apply(
        _act(
            tick=3,
            speaker="body-ben",
            ref=ref,
            revision=0,
            predicate="collective_oppose",
            object_payload="-",
        ),
        tick=3,
        previous=support,
    )
    assert {item.stance for item in oppose.positions} == {
        CollectivePositionStance.SUPPORT,
        CollectivePositionStance.OPPOSE,
    }
    assert len(oppose.positions) == 2


def test_unknown_proposal_is_deferred_not_invented() -> None:
    ref = _ref(lineage="never-proposed")
    ledger = _apply(
        _act(
            tick=1,
            speaker="body-ben",
            ref=ref,
            revision=0,
            predicate="collective_support",
            object_payload="-",
        ),
        tick=1,
    )
    assert ledger.proposals == ()
    assert ledger.positions == ()
    assert "unknown_proposal" in ledger.notices


def test_same_root_repetition_is_not_independent() -> None:
    ref = _ref()
    proposed = _apply(_propose(tick=1, ref=ref), tick=1)
    first = _apply(
        _act(
            tick=2,
            speaker="body-carol",
            ref=ref,
            revision=0,
            predicate="collective_support",
            object_payload="-",
            root="root-x",
        ),
        tick=2,
        previous=proposed,
    )
    repeated = _apply(
        _act(
            tick=3,
            speaker="body-carol",
            ref=ref,
            revision=0,
            predicate="collective_support",
            object_payload="-",
            root="root-x",
        ),
        tick=3,
        previous=first,
    )
    assert len(repeated.positions) == 2
    ordered = sorted(repeated.positions, key=lambda item: item.first_tick)
    assert ordered[0].independently_evidenced
    assert not ordered[1].independently_evidenced
    assert "duplicate_root" in repeated.notices


def test_forged_unresolved_speaker_cannot_become_support() -> None:
    ref = _ref()
    proposed = _apply(_propose(tick=1, ref=ref), tick=1)
    forged = _apply(
        _act(
            tick=2,
            speaker="body-stranger",
            ref=ref,
            revision=0,
            predicate="collective_support",
            object_payload="-",
        ),
        tick=2,
        previous=proposed,
    )
    assert forged.positions == ()
    assert "unresolved_entity" in forged.notices


def test_withdrawal_before_support_is_not_applied() -> None:
    ref = _ref()
    proposed = _apply(_propose(tick=1, ref=ref), tick=1)
    target = "a" * 64
    ledger = _apply(
        _act(
            tick=2,
            speaker="body-carol",
            ref=ref,
            revision=0,
            predicate="collective_withdraw",
            object_payload=f"position|{target}",
        ),
        tick=2,
        previous=proposed,
    )
    assert ledger.retractions == ()
    assert "unknown_proposal" in ledger.notices


def test_withdrawal_retracts_own_support_and_keeps_history() -> None:
    ref = _ref()
    proposed = _apply(_propose(tick=1, ref=ref), tick=1)
    supported = _apply(
        _act(
            tick=2,
            speaker="body-carol",
            ref=ref,
            revision=0,
            predicate="collective_support",
            object_payload="-",
        ),
        tick=2,
        previous=proposed,
    )
    position = supported.positions[0]
    withdrawn = _apply(
        _act(
            tick=3,
            speaker="body-carol",
            ref=ref,
            revision=0,
            predicate="collective_withdraw",
            object_payload=f"position|{position.position_id}",
        ),
        tick=3,
        previous=supported,
    )
    assert len(withdrawn.positions) == 1
    assert not withdrawn.positions[0].active
    assert len(withdrawn.retractions) == 1
    assert withdrawn.retractions[0].actor_id == _CAROL


def test_delegation_is_one_hop_and_self_delegation_is_rejected() -> None:
    ref = _ref()
    proposed = _apply(_propose(tick=1, ref=ref), tick=1)
    delegated = _apply(
        _act(
            tick=2,
            speaker="body-carol",
            ref=ref,
            revision=0,
            predicate="collective_delegate",
            object_payload="body-ben",
        ),
        tick=2,
        previous=proposed,
    )
    assert len(delegated.delegations) == 1
    assert delegated.delegations[0].delegator_id == _CAROL
    assert delegated.delegations[0].delegate_id == _BEN
    assert delegated.delegations[0].expires_tick == 9
    self_delegation = _apply(
        _act(
            tick=3,
            speaker="body-carol",
            ref=ref,
            revision=0,
            predicate="collective_delegate",
            object_payload="body-carol",
        ),
        tick=3,
        previous=delegated,
    )
    assert len(self_delegation.delegations) == 1
    assert "self_delegation" in self_delegation.notices


def test_competing_revision_supersedes_old_terms() -> None:
    ref = _ref()
    first = _apply(_propose(tick=1, ref=ref, terms="dig_channel"), tick=1)
    second = _apply(
        _propose(tick=2, ref=ref, revision=1, terms="raise_wall"),
        tick=2,
        previous=first,
    )
    statuses = {(item.revision, item.status) for item in second.proposals}
    assert (0, CollectiveProposalStatus.SUPERSEDED) in statuses
    assert (1, CollectiveProposalStatus.ACTIVE) in statuses
    older_support = _apply(
        _act(
            tick=3,
            speaker="body-carol",
            ref=ref,
            revision=0,
            predicate="collective_support",
            object_payload="-",
        ),
        tick=3,
        previous=second,
    )
    assert older_support.positions[0].revision == 0


def test_coordinate_records_a_claim_not_a_resolution() -> None:
    ref = _ref()
    proposed = _apply(_propose(tick=1, ref=ref), tick=1)
    coordinated = _apply(
        _act(
            tick=2,
            speaker="body-ben",
            ref=ref,
            revision=0,
            predicate="collective_coordinate",
            object_payload="start_project|-|unknown",
        ),
        tick=2,
        previous=proposed,
    )
    assert len(coordinated.outcomes) == 1
    outcome = coordinated.outcomes[0]
    assert outcome.claimed
    assert outcome.execution_status is CollectiveExecutionStatus.UNKNOWN


def test_expiry_is_local_and_finite() -> None:
    ref = _ref()
    proposed = _apply(_propose(tick=1, ref=ref, last=3), tick=1)
    expired = _apply(tick=4, previous=proposed)
    assert expired.proposals[0].status is CollectiveProposalStatus.EXPIRED
    assert not expired.proposals[0].actionable


def test_capacity_pressure_retires_references_and_rejects_replay() -> None:
    ledgers = []
    previous = empty_collective_decision_ledger(_OWNER)
    refs = []
    for index in range(17):
        ref = _ref(tick=index + 1, lineage=f"proposal-{index}")
        refs.append(ref)
        previous = _apply(
            _propose(tick=index + 1, ref=ref, root=f"propose-root-{index}"),
            tick=index + 1,
            previous=previous,
        )
        ledgers.append(previous)
    assert len(previous.proposals) == 16
    assert refs[0] in previous.retired_proposal_refs
    replayed = _apply(
        _propose(tick=18, ref=refs[0], root="late-replay"),
        tick=18,
        previous=previous,
    )
    assert "retired_reference" in replayed.notices
    assert all(item.proposal_ref != refs[0] for item in replayed.proposals)


def test_empty_observation_has_observed_window_coverage() -> None:
    ledger = _apply(tick=5)
    assert ledger.first_observed_tick == 5
    assert ledger.last_observed_tick == 5
    assert ledger.observation_count == 1
    assert ledger.proposals == ()
    assert ledger.coverage == "complete"


def test_update_is_deterministic() -> None:
    ref = _ref()
    proposal = _propose(tick=1, ref=ref, root="root-proposal")
    support = _act(
        tick=1,
        speaker="body-carol",
        ref=ref,
        revision=0,
        predicate="collective_support",
        object_payload="-",
        root="root-support",
    )
    first = _apply(proposal, support, tick=1)
    second = _apply(proposal, support, tick=1)
    assert first == second
    assert first.positions == second.positions
    assert first.proposals == second.proposals


def test_autonomous_proposal_generation_bootstraps_from_opportunity() -> None:
    from agents.cognition.collective_decisions import (
        CollectiveProposalStatus,
        collective_decision_preference,
        empty_collective_decision_ledger,
        generate_collective_decision_proposal,
    )
    from world.identifiers import EventId
    from world.observations import (
        ObservationAudienceRole,
        ObservationProvenance,
        ObservationSourceKind,
        ObservedOccurrence,
    )

    occurrence = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=0,
            source_event_id=EventId("event-project-started"),
        ),
        kind="collective_project_started",
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId("body-ben"),
        success=True,
    )
    observation = _observation(tick=1, occurrences=(occurrence,))
    ledger = empty_collective_decision_ledger(_OWNER)
    generated = generate_collective_decision_proposal(ledger, observation, _identity())
    assert len(generated.proposals) == 1
    proposal = generated.proposals[0]
    assert proposal.status is CollectiveProposalStatus.ACTIVE
    assert proposal.topic is CollectiveTopic.COLLECTIVE_PROJECT
    assert proposal.originator_id == _OWNER
    preference = collective_decision_preference(generated, tick=1)
    assert preference is not None
    assert preference.direction.value == "help"
    repeated = generate_collective_decision_proposal(
        generated, _observation(tick=2, occurrences=(occurrence,)), _identity()
    )
    assert len(repeated.proposals) == 1
