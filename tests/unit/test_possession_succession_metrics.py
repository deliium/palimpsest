"""Known answers for possession metric families. Channel off stays empty."""

from __future__ import annotations

from analysis.models import MetricAvailability
from analysis.possession_succession import PossessionLedgerSnapshot
from analysis.possession_succession_metrics import (
    assemble_possession_succession_metrics,
)
from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V16,
    CorpseCustodyOpened,
    OccurrenceContext,
    PossessionClaimAsserted,
    TakenFromCorpse,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _event(details: object, *, tick: int, sequence: int, actor: str | None):
    if actor is None:
        cause = SystemCause(
            cause_id=RequestId(f"sys-{sequence}"),
            effect_family=SystemEffectFamily.LIFECYCLE,
            entity_id=EntityId("body-dead"),
            family_ordinal=sequence,
        )
    else:
        cause = ActionCause(
            request_id=RequestId(f"req-{sequence}"),
            actor_id=EntityId(actor),
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


def test_family_count_is_74() -> None:
    assert METRIC_FAMILY_COUNT == 74
    assert MetricFamilyId.POSSESSION_CUSTODY_OUTCOMES.value == (
        "possession_custody_outcomes"
    )


def test_channel_off_harvest_is_empty() -> None:
    assert (
        assemble_possession_succession_metrics(
            (),
            run_id="run-1",
            input_revision="rev-1",
            spec=None,
            as_of_tick=1,
        )
        == ()
    )


def test_take_conflict_and_contested_convention() -> None:
    opened = _event(
        CorpseCustodyOpened(
            EntityId("body-dead"),
            EntityId("loc-1"),
            (EntityId("item-1"),),
        ),
        tick=1,
        sequence=0,
        actor=None,
    )
    claim_a = _event(
        PossessionClaimAsserted(EntityId("body-dead"), "nobody_owns"),
        tick=2,
        sequence=0,
        actor="body-a",
    )
    claim_b = _event(
        PossessionClaimAsserted(EntityId("body-dead"), "group_owns"),
        tick=2,
        sequence=1,
        actor="body-b",
    )
    take = _event(
        TakenFromCorpse(
            EntityId("item-1"), EntityId("body-dead"), EntityId("body-a")
        ),
        tick=3,
        sequence=0,
        actor="body-a",
    )
    ledgers = (
        PossessionLedgerSnapshot("owner-a", True, "loc-1", (("nobody_owns", 1),)),
        PossessionLedgerSnapshot("owner-b", True, "loc-1", (("group_owns", 1),)),
    )
    docs = assemble_possession_succession_metrics(
        (opened, claim_a, claim_b, take),
        run_id="run-1",
        input_revision="rev-1",
        spec=object(),
        as_of_tick=4,
        ledgers=ledgers,
    )
    by_family = {doc.metric_family: doc for doc in docs}
    custody = by_family["possession_custody_outcomes"]
    conflict = by_family["possession_claim_conflict"]
    convention = by_family["inheritance_convention_distribution"]
    assert custody.availability is MetricAvailability.PRESENT
    assert custody.values["taken_item_count"] == 1
    assert custody.values["corpse_item_count"] == 0
    assert "nobody_owns" not in custody.values
    assert conflict.values["conflict_episode_count"] == 1
    assert conflict.values["claim_count"] == 2
    assert convention.values["contested_count"] == 1
    assert convention.values["convention_histogram"] == "contested:1"
