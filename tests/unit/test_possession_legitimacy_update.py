"""Possession beliefs update from one owner's observations only."""

from __future__ import annotations

import agents.cognition.possession_legitimacy as legitimacy
from agents.cognition.possession_legitimacy import (
    PossessionAlignmentContext,
    apply_possession_legitimacy_update,
    empty_possession_legitimacy,
    note_doctrine_support,
)
from agents.models import AgentId
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

_DOCTRINES = (
    "children_should_inherit",
    "group_owns",
    "caregiver_inherits",
    "first_claimant_owns",
    "nobody_owns",
)


def _occurrence(
    kind: str, facts: dict[str, object], actor: str | None
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=3,
            source_event_id=EventId("evt-1"),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=None if actor is None else EntityId(actor),
        public_facts=facts,
    )


def _observation(
    *occurrences: ObservedOccurrence, observer: str = "body-live"
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId(observer),
        revision=WorldRevision(1),
        tick=4,
        occurrences=occurrences,
    )


def _claim(doctrine: str, actor: str = "body-other") -> ObservedOccurrence:
    return _occurrence(
        "possession_claim_asserted",
        {
            "decedent_id": "body-dead",
            "doctrine": doctrine,
            "item_ids": ["item-1"],
        },
        actor,
    )


def _take(actor: str = "body-taker") -> ObservedOccurrence:
    return _occurrence(
        "taken_from_corpse",
        {"decedent_id": "body-dead", "item_ids": ["item-1"]},
        actor,
    )


def test_each_witnessed_doctrine_increments_once() -> None:
    owner = AgentId("owner-1")
    for doctrine in _DOCTRINES:
        updated = apply_possession_legitimacy_update(
            _observation(_claim(doctrine)),
            empty_possession_legitimacy(owner),
            owner_id=owner,
        )
        assert updated.support_count(doctrine) == 1
        assert updated.claims[-1].doctrine == doctrine


def test_nobody_owns_take_adds_no_sanction_and_no_attack() -> None:
    owner = AgentId("owner-1")
    seeded = note_doctrine_support(
        note_doctrine_support(empty_possession_legitimacy(owner), "nobody_owns"),
        "nobody_owns",
    )
    updated = apply_possession_legitimacy_update(
        _observation(_take()),
        seeded,
        owner_id=owner,
    )
    assert updated.sanctions == ()
    assert not hasattr(legitimacy, "Attack")
    assert updated.support_count("first_claimant_owns") == 1


def test_two_owners_keep_separate_ledgers_after_one_claim() -> None:
    claim = _claim("children_should_inherit")
    observation = _observation(claim)
    parent = note_doctrine_support(
        empty_possession_legitimacy(AgentId("parent")), "group_owns"
    )
    neighbor = note_doctrine_support(
        empty_possession_legitimacy(AgentId("neighbor")), "caregiver_inherits"
    )
    parent_next = apply_possession_legitimacy_update(
        observation, parent, owner_id=AgentId("parent")
    )
    neighbor_next = apply_possession_legitimacy_update(
        observation, neighbor, owner_id=AgentId("neighbor")
    )
    assert parent_next.support_count("children_should_inherit") == 1
    assert parent_next.support_count("group_owns") == 1
    assert neighbor_next.support_count("children_should_inherit") == 1
    assert neighbor_next.support_count("caregiver_inherits") == 1
    assert parent_next.claims[0].claimant_id != neighbor.owner_id


def test_blank_child_does_not_receive_parent_doctrines() -> None:
    parent = note_doctrine_support(
        empty_possession_legitimacy(AgentId("parent")), "children_should_inherit"
    )
    child = apply_possession_legitimacy_update(
        _observation(
            _occurrence(
                "corpse_custody_opened",
                {"decedent_id": "body-dead", "item_ids": ["item-1"]},
                None,
            )
        ),
        None,
        owner_id=AgentId("child"),
    )
    assert parent.support_count("children_should_inherit") == 1
    assert child.supports == ()
    assert child.owner_id == AgentId("child")


def test_unaligned_take_records_criticism_only() -> None:
    owner = AgentId("owner-1")
    seeded = empty_possession_legitimacy(owner)
    for _ in range(2):
        seeded = note_doctrine_support(seeded, "children_should_inherit")
    updated = apply_possession_legitimacy_update(
        _observation(_take("body-stranger")),
        seeded,
        owner_id=owner,
        alignment=PossessionAlignmentContext(
            kinship_on=True,
            children_of={"body-dead": ("body-child",)},
        ),
    )
    assert [note.token for note in updated.sanctions] == ["criticism"]
    assert "retaliation_considered" not in [note.token for note in updated.sanctions]
