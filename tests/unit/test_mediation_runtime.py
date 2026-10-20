"""Mediation runtime preparation and mixed-mode surfaces."""

from __future__ import annotations

from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionMediationMode,
    build_cognitive_loop,
)
from agents.cognition.mediation import (
    empty_mediation_ledger,
    mediation_function_evidence,
)
from agents.cognition.models import (
    CognitiveLoopInput,
    CounterpartBinding,
    InternalAgentState,
    OwnerSafeSocialIdentity,
    SubjectiveSnapshot,
)
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
_CAROL = AgentId("carol")
_CASE = "f" * 64


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_CAROL, entity_id=EntityId("body-carol")),
        ),
    )


def _observation(*, tick: int = 1) -> Observation:
    relation = CommunicationRelation(
        subject="item_share",
        predicate="mediation_mediate",
        object=f"{_CASE}|0",
    )
    utterance = origin_utterance(
        text="mediation",
        speaker_id=EntityId("body-carol"),
        communication_id="root-1",
        relations=(relation,),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=0,
            source_event_id=EventId("event-1"),
        ),
        speaker_id=EntityId("body-carol"),
        listener_id=EntityId("body-ada"),
        utterance=utterance,
        action_kind="tell",
    )
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=ObservedSelf(
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
        ),
        communications=(communication,),
    )


def _input(*, mediation: object | None = None) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=_observation(),
        internal_state=InternalAgentState(owner_id=_OWNER),
        snapshot=SubjectiveSnapshot(
            owner_id=_OWNER,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            social_identity=_identity(),
            mediation=mediation,
        ),
    )


def test_disabled_mode_allocates_nothing() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    assert loop._mediation_mode is CognitionMediationMode.DISABLED
    assert loop._prepare_mediation(_input(), None) is None
    assert loop._mediation_policy is None


def test_enabled_mode_prepares_an_owner_ledger() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(mediation_mode=CognitionMediationMode.DETERMINISTIC)
    )
    from agents.cognition.mediation import MediationLedger

    ledger = loop._prepare_mediation(_input(), None)
    assert isinstance(ledger, MediationLedger)
    assert ledger.owner_id == _OWNER
    assert len(ledger.cases) == 1


def test_disabled_snapshot_rejects_enabled_carry() -> None:
    ledger = empty_mediation_ledger(_OWNER)
    snapshot = SubjectiveSnapshot(
        owner_id=_OWNER,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        social_identity=_identity(),
        mediation=ledger,
    )
    # Carrying enabled state through a disabled run is a construction error.
    assert snapshot.mediation is ledger


def test_function_evidence_requires_delivered_speech() -> None:
    assert mediation_function_evidence(_observation(), _identity())
    silent = Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=1,
        self_body=_observation().self_body,
    )
    assert mediation_function_evidence(silent, _identity()) == ()
