"""Observed and remembered composition learning stays owner-scoped."""

from __future__ import annotations

from dataclasses import replace

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
    SymbolicCueSummary,
    SymbolicStatus,
    apply_symbolic_update,
)
from agents.models import AgentId
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


def _binding(owner: AgentId, token: str, entity: str = "loc-1") -> LabelBinding:
    return LabelBinding(
        binding_id=label_binding_id(owner, NamingReferentKind.LOCATION, token),
        owner_id=owner,
        label_token=token,
        referent_kind=NamingReferentKind.LOCATION,
        status=NamingStatus.ACTIVE,
        strength=0.5,
        candidates=(
            NamingCandidate(
                kind=NamingReferentKind.LOCATION, entity_id=entity, confidence=0.5
            ),
        ),
        evidence_count=3,
    )


def _observation(tick: int, observer: str = "body-1") -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId(observer),
        revision=WorldRevision(1),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId(observer),
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


def _setup() -> tuple[AgentId, OwnerSafeSocialIdentity, TerminologyLedger]:
    owner = AgentId("a")
    identity = OwnerSafeSocialIdentity(
        owner_id=owner, owner_entity_id=EntityId("body-1")
    )
    terminology = TerminologyLedger(
        owner_id=owner,
        bindings=(_binding(owner, "alpha"), _binding(owner, "beta")),
    )
    return owner, identity, terminology


def test_repeated_cooccurrence_promotes_relational_composition() -> None:
    _, identity, terminology = _setup()
    ledger = None
    for tick in range(1, 5):
        ledger = apply_symbolic_update(
            _observation(tick), identity, ledger, terminology
        )
    assert ledger is not None
    assert len(ledger.compositions) == 1
    composition = ledger.compositions[0]
    assert composition.kind.value == "relational"
    assert composition.parts == ("alpha", "beta")
    assert composition.status is SymbolicStatus.ACTIVE
    assert composition.evidence_count == 4


def test_one_observation_does_not_mint() -> None:
    _, identity, terminology = _setup()
    ledger = apply_symbolic_update(_observation(1), identity, None, terminology)
    assert ledger is not None
    assert all(item.status is not SymbolicStatus.ACTIVE for item in ledger.compositions)


def test_inactive_constituent_resolves_to_no_composition() -> None:
    owner, identity, terminology = _setup()
    partial = replace(
        terminology,
        bindings=(_binding(owner, "alpha"),),
    )
    ledger = apply_symbolic_update(_observation(1), identity, None, partial)
    assert ledger is not None
    assert ledger.compositions == ()


def test_cues_extend_observed_keys_without_other_owners() -> None:
    _, identity, terminology = _setup()
    cues = SymbolicCueSummary(observed_entity_keys=("loc-1",))
    ledger = apply_symbolic_update(
        _observation(1), identity, None, terminology, cues=cues
    )
    assert ledger is not None
    assert ledger.compositions


def test_owner_mismatch_rejected() -> None:
    _, identity, terminology = _setup()
    foreign_identity = OwnerSafeSocialIdentity(
        owner_id=AgentId("b"), owner_entity_id=EntityId("body-2")
    )
    ledger = apply_symbolic_update(_observation(1), identity, None, terminology)
    assert ledger is not None
    try:
        apply_symbolic_update(_observation(2), foreign_identity, ledger, terminology)
    except ValueError as error:
        assert "mismatch" in str(error)
    else:  # pragma: no cover
        raise AssertionError("foreign ledger accepted")
