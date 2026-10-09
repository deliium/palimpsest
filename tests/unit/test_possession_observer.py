"""Observer labels for corpse custody, corpse take, and possession claims."""

from __future__ import annotations

from observer.adapt import adapt_event
from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES
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


def _event(details: object, cause: object, sequence: int):
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{sequence}"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=sequence,
        cause=cause,  # type: ignore[arg-type]
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V16,
    )


def test_new_kinds_export_new_labels_and_protocol_stays() -> None:
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert len(SEMANTIC_EVENT_TYPES) == 57
    assert "AGENT_TOOK_ITEM" in SEMANTIC_EVENT_TYPES
    system = SystemCause(
        RequestId("cause-1"),
        SystemEffectFamily.COMBINED_NEEDS,
        EntityId("body-dead"),
        0,
    )
    action = ActionCause(request_id=RequestId("req-1"), actor_id=EntityId("body-live"))
    custody = adapt_event(
        _event(
            CorpseCustodyOpened(
                EntityId("body-dead"), EntityId("loc-1"), (EntityId("item-1"),)
            ),
            system,
            0,
        )
    )
    taken = adapt_event(
        _event(
            TakenFromCorpse(
                EntityId("item-1"), EntityId("body-dead"), EntityId("body-live")
            ),
            action,
            1,
        )
    )
    claim = adapt_event(
        _event(
            PossessionClaimAsserted(
                EntityId("body-dead"), "nobody_owns", EntityId("item-1")
            ),
            action,
            2,
        )
    )
    assert custody.type == "CORPSE_CUSTODY_OPENED"
    assert custody.domain_kind == "corpse_custody_opened"
    assert taken.type == "AGENT_TOOK_FROM_CORPSE"
    assert taken.item_id == "item-1"
    assert claim.type == "POSSESSION_CLAIM_ASSERTED"
    assert claim.target_id == "body-dead"
