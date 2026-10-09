"""Known answers for possession episodes. Doctrines are not holders."""

from __future__ import annotations

from analysis.possession_succession import (
    PossessionLedgerSnapshot,
    classify_possession_episodes,
)
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V16,
    CorpseCustodyOpened,
    Given,
    OccurrenceContext,
    PossessionClaimAsserted,
    TakenFromCorpse,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _event(details: object, *, tick: int, sequence: int, actor: str | None):
    cause = (
        SystemCause(
            cause_id=RequestId(f"sys-{sequence}"),
            effect_family=SystemEffectFamily.LIFECYCLE,
            entity_id=EntityId("body-dead"),
            family_ordinal=sequence,
        )
        if actor is None
        else ActionCause(
            request_id=RequestId(f"req-{sequence}"),
            actor_id=EntityId(actor),
        )
    )
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        cause=cause,
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V16,
    )


def _opened(*items: str):
    return _event(
        CorpseCustodyOpened(
            EntityId("body-dead"),
            EntityId("loc-1"),
            tuple(EntityId(item) for item in items),
        ),
        tick=1,
        sequence=0,
        actor=None,
    )


def test_channel_off_has_no_episodes() -> None:
    given = _event(
        Given(EntityId("body-live"), EntityId("item-1"), EntityId("body-live")),
        tick=2,
        sequence=0,
        actor="body-live",
    )
    assert classify_possession_episodes((given,), as_of_tick=2) == ()


def test_corpse_only_stays_on_the_corpse() -> None:
    episodes = classify_possession_episodes((_opened("item-1"),), as_of_tick=3)
    episode = episodes[0]
    assert episode.physical_possession == (("item-1", "corpse"),)
    assert episode.legitimacy_claims == ()
    assert episode.conflict is False
    assert episode.appropriation is False
    assert episode.voluntary_transfer is False
    assert episode.convention_token == "unformed"


def test_take_changes_physical_holder_only() -> None:
    take = _event(
        TakenFromCorpse(
            EntityId("item-1"), EntityId("body-dead"), EntityId("body-live")
        ),
        tick=2,
        sequence=0,
        actor="body-live",
    )
    episode = classify_possession_episodes((_opened("item-1"), take), as_of_tick=3)[0]
    assert episode.physical_possession == (("item-1", "body-live"),)
    assert episode.appropriation is True
    assert episode.legitimacy_claims == ()


def test_give_after_take_is_voluntary() -> None:
    take = _event(
        TakenFromCorpse(
            EntityId("item-1"), EntityId("body-dead"), EntityId("body-live")
        ),
        tick=2,
        sequence=0,
        actor="body-live",
    )
    given = _event(
        Given(EntityId("body-other"), EntityId("item-1"), EntityId("body-other")),
        tick=3,
        sequence=0,
        actor="body-live",
    )
    episode = classify_possession_episodes(
        (_opened("item-1"), take, given), as_of_tick=4
    )[0]
    assert episode.physical_possession == (("item-1", "body-other"),)
    assert episode.voluntary_transfer is True


def test_two_claims_conflict_without_a_winner() -> None:
    first = _event(
        PossessionClaimAsserted(EntityId("body-dead"), "children_should_inherit"),
        tick=2,
        sequence=0,
        actor="body-a",
    )
    second = _event(
        PossessionClaimAsserted(EntityId("body-dead"), "group_owns"),
        tick=2,
        sequence=1,
        actor="body-b",
    )
    episode = classify_possession_episodes(
        (_opened("item-1"), first, second), as_of_tick=3
    )[0]
    assert episode.conflict is True
    assert episode.physical_possession == (("item-1", "corpse"),)
    assert episode.appropriation is False
    assert len(episode.legitimacy_claims) == 2


def test_first_claimant_alignment() -> None:
    claim = _event(
        PossessionClaimAsserted(
            EntityId("body-dead"), "first_claimant_owns", EntityId("item-1")
        ),
        tick=2,
        sequence=0,
        actor="body-live",
    )
    take = _event(
        TakenFromCorpse(
            EntityId("item-1"), EntityId("body-dead"), EntityId("body-live")
        ),
        tick=3,
        sequence=0,
        actor="body-live",
    )
    episode = classify_possession_episodes(
        (_opened("item-1"), claim, take), as_of_tick=4
    )[0]
    assert dict(episode.alignment)["first_claimant_owns"] == "aligned"
    assert episode.appropriation is False


def test_child_alignment_requires_a_kinship_harvest() -> None:
    claim = _event(
        PossessionClaimAsserted(EntityId("body-dead"), "children_should_inherit"),
        tick=2,
        sequence=0,
        actor="body-child",
    )
    take = _event(
        TakenFromCorpse(
            EntityId("item-1"), EntityId("body-dead"), EntityId("body-child")
        ),
        tick=3,
        sequence=0,
        actor="body-child",
    )
    events = (_opened("item-1"), claim, take)
    missing = classify_possession_episodes(events, as_of_tick=4)[0]
    present = classify_possession_episodes(
        events,
        as_of_tick=4,
        children_of={"body-dead": frozenset({"body-child"})},
    )[0]
    assert dict(missing.alignment)["children_should_inherit"] == "not_applicable"
    assert dict(present.alignment)["children_should_inherit"] == "aligned"
    assert missing.appropriation is True
    assert present.appropriation is False


def test_parent_edge_does_not_make_a_caregiver() -> None:
    take = _event(
        TakenFromCorpse(
            EntityId("item-1"), EntityId("body-dead"), EntityId("body-child")
        ),
        tick=2,
        sequence=0,
        actor="body-child",
    )
    claim = _event(
        PossessionClaimAsserted(EntityId("body-dead"), "caregiver_inherits"),
        tick=2,
        sequence=1,
        actor="body-child",
    )
    episode = classify_possession_episodes(
        (_opened("item-1"), take, claim),
        as_of_tick=3,
        children_of={"body-dead": frozenset({"body-child"})},
    )[0]
    assert dict(episode.alignment)["caregiver_inherits"] == "not_applicable"
    assert dict(episode.alignment)["children_should_inherit"] == "aligned"


def test_plurality_tie_is_contested() -> None:
    ledgers = (
        PossessionLedgerSnapshot(
            "owner-a",
            True,
            "loc-1",
            (("nobody_owns", 2),),
        ),
        PossessionLedgerSnapshot(
            "owner-b",
            True,
            "loc-1",
            (("group_owns", 2),),
        ),
        PossessionLedgerSnapshot(
            "owner-away",
            True,
            "loc-2",
            (("children_should_inherit", 9),),
        ),
    )
    episode = classify_possession_episodes(
        (_opened("item-1"),), as_of_tick=2, ledgers=ledgers
    )[0]
    assert episode.convention_token == "contested"
