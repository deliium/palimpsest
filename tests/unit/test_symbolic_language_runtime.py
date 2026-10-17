"""Deterministic outbound composition selection and usage accounting."""

from __future__ import annotations

from agents.cognition.configuration import CognitionSymbolicLanguageMode
from agents.cognition.models import OwnerSafeSocialIdentity
from agents.cognition.semantic_naming import (
    LabelBinding,
    NamingCandidate,
    NamingReferentKind,
    NamingStatus,
    TerminologyLedger,
    label_binding_id,
)
from agents.cognition.symbolic_language import (
    SymbolicComposition,
    SymbolicCompositionKind,
    SymbolicLedger,
    SymbolicReferentHypothesis,
    SymbolicStatus,
    composition_id,
    symbolic_communicate_utterance,
    symbolic_usage_update,
)
from agents.models import AgentId
from world.actions import Ask, Talk
from world.communications import origin_utterance
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _binding(owner: AgentId, token: str) -> LabelBinding:
    return LabelBinding(
        binding_id=label_binding_id(owner, NamingReferentKind.LOCATION, token),
        owner_id=owner,
        label_token=token,
        referent_kind=NamingReferentKind.LOCATION,
        status=NamingStatus.ACTIVE,
        strength=0.5,
        candidates=(
            NamingCandidate(
                kind=NamingReferentKind.LOCATION, entity_id="loc-1", confidence=0.5
            ),
        ),
        evidence_count=3,
    )


def _setup() -> tuple[
    AgentId, OwnerSafeSocialIdentity, TerminologyLedger, SymbolicLedger
]:
    owner = AgentId("a")
    identity = OwnerSafeSocialIdentity(
        owner_id=owner, owner_entity_id=EntityId("body-1")
    )
    terminology = TerminologyLedger(
        owner_id=owner,
        bindings=(_binding(owner, "alpha"), _binding(owner, "beta")),
    )
    composition = SymbolicComposition(
        composition_id=composition_id(
            owner, SymbolicCompositionKind.RELATIONAL, ("alpha", "beta")
        ),
        owner_id=owner,
        kind=SymbolicCompositionKind.RELATIONAL,
        parts=("alpha", "beta"),
        referent_hypothesis=SymbolicReferentHypothesis(
            NamingReferentKind.LOCATION, 0.2
        ),
        status=SymbolicStatus.ACTIVE,
        strength=0.6,
        evidence_count=3,
        first_tick=1,
        last_tick=3,
    )
    return (
        owner,
        identity,
        terminology,
        SymbolicLedger(owner_id=owner, compositions=(composition,)),
    )


def _observation(tick: int = 5) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        occurrences=(),
        visible_bodies=(),
    )


def _talk() -> Talk:
    return Talk(
        recipient_id=EntityId("body-2"),
        utterance=origin_utterance(text="call", speaker_id=EntityId("body-1")),
    )


def test_disabled_mode_returns_same_command_object() -> None:
    owner, identity, terminology, ledger = _setup()
    command = _talk()
    result = symbolic_communicate_utterance(
        command,
        owner_id=owner,
        tick=5,
        observation=_observation(),
        identity=identity,
        ledger=ledger,
        terminology=terminology,
        mode=CognitionSymbolicLanguageMode.DISABLED,
    )
    assert result is command


def test_active_composition_stamps_bounded_relations() -> None:
    owner, identity, terminology, ledger = _setup()
    command = symbolic_communicate_utterance(
        _talk(),
        owner_id=owner,
        tick=5,
        observation=_observation(),
        identity=identity,
        ledger=ledger,
        terminology=terminology,
        mode=CognitionSymbolicLanguageMode.DETERMINISTIC,
    )
    assert type(command) is Talk
    relations = command.utterance.content.relations
    operators = [item for item in relations if item.predicate == "relational"]
    assert len(operators) == 1
    assert len(relations) == 3
    assert command.utterance.declared == _talk().utterance.declared


def test_ask_is_never_recomposed() -> None:
    owner, identity, terminology, ledger = _setup()
    ask = Ask(
        recipient_id=EntityId("body-2"),
        utterance=origin_utterance(text="call", speaker_id=EntityId("body-1")),
    )
    result = symbolic_communicate_utterance(
        ask,
        owner_id=owner,
        tick=5,
        observation=_observation(),
        identity=identity,
        ledger=ledger,
        terminology=terminology,
        mode=CognitionSymbolicLanguageMode.DETERMINISTIC,
    )
    assert result is ask


def test_usage_only_increments_selected_compositions() -> None:
    owner, identity, terminology, ledger = _setup()
    command = symbolic_communicate_utterance(
        _talk(),
        owner_id=owner,
        tick=5,
        observation=_observation(),
        identity=identity,
        ledger=ledger,
        terminology=terminology,
        mode=CognitionSymbolicLanguageMode.DETERMINISTIC,
    )
    updated = symbolic_usage_update(ledger, command, tick=5)
    assert isinstance(updated, SymbolicLedger)
    assert updated.compositions[0].usage_count == 1
    assert updated.compositions[0].last_utterance_tick == 5
    untouched = symbolic_usage_update(ledger, _talk(), tick=5)
    assert untouched is ledger
