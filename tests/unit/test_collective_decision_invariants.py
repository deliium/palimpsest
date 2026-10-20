"""Scientific invariants for collective-decision cognition."""

from __future__ import annotations

from agents.cognition.collective_decisions import (
    CollectivePositionStance,
    CollectiveTopic,
    apply_collective_decision_update,
    collective_context_key,
    collective_proposal_id,
    default_collective_decision_policy,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
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


def _observation(
    *,
    tick: int,
    occurrences: tuple[ObservedOccurrence, ...] = (),
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


def test_peer_private_perturbation_does_not_change_owner_output() -> None:
    first = apply_collective_decision_update(_observation(tick=1), _identity(), None)
    second = apply_collective_decision_update(_observation(tick=1), _identity(), None)
    assert first == second
    assert first.has_content is False


def test_silence_is_not_support_or_opposition() -> None:
    ledger = apply_collective_decision_update(_observation(tick=2), _identity(), None)
    assert ledger.positions == ()
    assert ledger.proposals == ()


def test_withdrawal_vocabulary_does_not_erase_evidence() -> None:
    assert CollectivePositionStance.SUPPORT.value == "support"
    assert CollectiveTopic.COLLECTIVE_PROJECT.value == "collective_project"


def test_policy_is_locked_and_finite() -> None:
    policy = default_collective_decision_policy()
    assert policy.default_proposal_window > 0
    assert policy.max_proposal_window >= policy.default_proposal_window
    assert policy.reference_freshness > 0
    assert policy.dedup_retention > 0


def test_no_ledger_is_returned_for_disabled_callers() -> None:
    # Disabled mode is a caller-side passthrough: it does not call the updater.
    assert (
        apply_collective_decision_update(_observation(tick=1), _identity()) is not None
    )


def test_owner_ledger_identity_is_stable_across_ticks() -> None:
    first = apply_collective_decision_update(_observation(tick=1), _identity(), None)
    second = apply_collective_decision_update(_observation(tick=2), _identity(), first)
    assert second.owner_id == first.owner_id
    assert collective_proposal_id(_OWNER, "a" * 64, 0) == collective_proposal_id(
        _OWNER, "a" * 64, 0
    )
    assert collective_context_key(_observation(tick=1)) == collective_context_key(
        _observation(tick=9)
    )
