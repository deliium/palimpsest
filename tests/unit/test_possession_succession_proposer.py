"""Deterministic corpse claim and take proposals. No heir and no Attack."""

from __future__ import annotations

import agents.cognition.possession_legitimacy as legitimacy
from agents.cognition.possession_legitimacy import (
    apply_possession_proposal,
    empty_possession_legitimacy,
    note_doctrine_support,
    propose_possession_command,
)
from agents.models import AgentId
from world.actions import AssertPossessionClaim, Attack, Take, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservedItem,
    ObservedItemPlacement,
    VisibleBody,
)
from world.values import ItemKind, ItemLoad


def _observation(tick: int) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-live"),
        revision=WorldRevision(1),
        tick=tick,
        items=(
            ObservedItem(
                EntityId("item-0"),
                "stone",
                ItemKind.MATERIAL,
                ItemLoad(1),
                ObservedItemPlacement.GROUND_HERE,
            ),
            ObservedItem(
                EntityId("item-a"),
                "cup",
                ItemKind.GENERIC,
                ItemLoad(1),
                ObservedItemPlacement.CORPSE_HERE,
            ),
            ObservedItem(
                EntityId("item-b"),
                "blade",
                ItemKind.TOOL,
                ItemLoad(1),
                ObservedItemPlacement.CORPSE_HERE,
            ),
        ),
        visible_bodies=(
            VisibleBody(EntityId("body-dead"), LifeStatus.DEAD, CoarseHealth.DEAD),
            VisibleBody(EntityId("body-z"), LifeStatus.DEAD, CoarseHealth.DEAD),
        ),
    )


def test_empty_ledger_even_tick_takes_first_corpse_item() -> None:
    owner = AgentId("owner-1")
    command = propose_possession_command(
        _observation(4),
        empty_possession_legitimacy(owner),
        channel_on=True,
        owner_id=owner,
    )
    assert type(command) is Take
    assert command.item_id == EntityId("item-a")


def test_empty_ledger_odd_tick_asserts_nobody_owns() -> None:
    owner = AgentId("owner-1")
    command = propose_possession_command(
        _observation(5),
        empty_possession_legitimacy(owner),
        channel_on=True,
        owner_id=owner,
    )
    assert type(command) is AssertPossessionClaim
    assert command.doctrine == "nobody_owns"
    assert command.decedent_id == EntityId("body-dead")
    assert command.item_id == EntityId("item-a")


def test_highest_support_selects_that_doctrine() -> None:
    owner = AgentId("owner-1")
    ledger = note_doctrine_support(
        note_doctrine_support(
            empty_possession_legitimacy(owner), "children_should_inherit"
        ),
        "nobody_owns",
    )
    ledger = note_doctrine_support(ledger, "children_should_inherit")
    command = propose_possession_command(
        _observation(4),
        ledger,
        channel_on=True,
        owner_id=owner,
    )
    assert type(command) is AssertPossessionClaim
    assert command.doctrine == "children_should_inherit"


def test_channel_off_leaves_compiled_command_unchanged() -> None:
    owner = AgentId("owner-1")
    ranked = Wait()
    observation = _observation(4)
    assert (
        propose_possession_command(
            observation,
            empty_possession_legitimacy(owner),
            channel_on=False,
            owner_id=owner,
        )
        is None
    )
    assert (
        apply_possession_proposal(
            ranked,
            observation,
            empty_possession_legitimacy(owner),
            channel_on=False,
            owner_id=owner,
        )
        is ranked
    )


def test_proposal_is_not_attack() -> None:
    owner = AgentId("owner-1")
    command = propose_possession_command(
        _observation(4),
        empty_possession_legitimacy(owner),
        channel_on=True,
    )
    assert type(command) is not Attack
    assert not hasattr(legitimacy, "Attack")
