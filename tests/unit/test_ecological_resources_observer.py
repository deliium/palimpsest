# mypy: ignore-errors

"""Ecology transitions stay off agent and observer presentation surfaces."""

from __future__ import annotations

import pytest

from api.errors import ApiError
from api.observer_service import ObserverReadService
from observer.adapt import (
    HIDDEN_OBSERVER_EVENT_TYPES,
    adapt_event,
    adapt_events,
    is_hidden_observer_event,
)
from observer.version import (
    OBSERVER_PROTOCOL_VERSION,
    SEMANTIC_EVENT_TYPES,
    SEMANTIC_TYPE_BY_KIND,
)
from simulation.clock import Tick
from simulation.journal import (
    compute_commit_hash,
    hash_tick_events,
    hash_tick_payload,
)
from simulation.models import RunId
from simulation.persistence import (
    CommitHash,
    TickAppendRequest,
    TickCommit,
)
from simulation.replay import ReplayService
from tests.unit.test_observer_replay import (
    BODY_ID,
    RUN_ID,
    WORLD_ID,
    FakeJournal,
    FakeRuns,
    FakeSnapshots,
    _manifest,
    _snapshot,
)
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V24,
    EVENT_SCHEMA_REPLAY_V25,
    DiseaseRowView,
    DiseaseStateChanged,
    EcologicalResourceChanged,
    OccurrenceContext,
    Waited,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit


def _wait(event_id: str, *, tick: int, sequence: int) -> WorldEvent:
    details = Waited()
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id=RUN_ID,
        world_id=WorldId(WORLD_ID),
        tick=tick,
        sequence=sequence,
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId(BODY_ID)),
        resulting_revision=WorldRevision(tick + 1),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId("loc-camp")
        ),
    )


def _ecology(
    event_id: str,
    *,
    tick: int,
    sequence: int,
    before: int = 0,
    after: int = 5,
) -> WorldEvent:
    resource_id = EntityId("res-food")
    details = EcologicalResourceChanged(
        resource_id=resource_id,
        before_damage_tenths=before,
        after_damage_tenths=after,
    )
    return WorldEvent(
        event_id=EventId(event_id),
        run_id=RUN_ID,
        world_id=WorldId(WORLD_ID),
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"sys-{event_id}"),
        resulting_revision=WorldRevision(tick + 1),
        schema_version=EVENT_SCHEMA_REPLAY_V25,
        details=details,
        actor_id=None,
        target_id=resource_id,
        cause=SystemCause(
            RequestId(f"sys-{event_id}"),
            SystemEffectFamily.REGENERATION,
            resource_id,
            0,
        ),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-camp"),
            destination_location_id=None,
            affected_entity_ids=(resource_id,),
            private_recipient_ids=(),
        ),
    )


def _disease(
    event_id: str,
    *,
    tick: int,
    sequence: int,
) -> WorldEvent:
    details = DiseaseStateChanged(
        body_id=EntityId(BODY_ID),
        before=None,
        after=DiseaseRowView(phase="latent", due_tick=2),
    )
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id=RUN_ID,
        world_id=WorldId(WORLD_ID),
        tick=tick,
        sequence=sequence,
        cause=SystemCause(
            RequestId(f"sys-{event_id}"),
            SystemEffectFamily.DISEASE,
            EntityId(BODY_ID),
            0,
        ),
        resulting_revision=WorldRevision(tick + 1),
        details=details,
        occurrence=build_occurrence_context(details, origin_location_id=None),
        schema_version=EVENT_SCHEMA_REPLAY_V24,
    )


def _mixed_events() -> tuple[WorldEvent, ...]:
    return (
        _wait("evt-v0", tick=0, sequence=0),
        _ecology("evt-eco0", tick=0, sequence=1),
        _disease("evt-dis0", tick=0, sequence=2),
        _wait("evt-v1", tick=0, sequence=3),
        _ecology("evt-eco1", tick=1, sequence=0, before=5, after=10),
        _wait("evt-v2", tick=1, sequence=1),
        _ecology("evt-eco2", tick=2, sequence=0, before=10, after=12),
        _disease("evt-dis1", tick=2, sequence=1),
    )


def _commit_for_tick(
    events: tuple[WorldEvent, ...],
    *,
    tick: int,
    predecessor: CommitHash | None,
) -> TickCommit:
    tick_events = tuple(event for event in events if event.tick == tick)
    request = TickAppendRequest(
        run_id=RunId(RUN_ID),
        tick=Tick(tick),
        expected_base_revision=WorldRevision(tick),
        expected_predecessor_commit_hash=predecessor,
        idempotency_key=f"idem-ecology-{tick}",
        events=tick_events,
    )
    payload = hash_tick_payload(request.events)
    event_hashes = hash_tick_events(request.events)
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=predecessor,
        run_id=request.run_id,
        tick=request.tick,
        base_revision=request.expected_base_revision,
        resulting_revision=WorldRevision(tick + 1),
        event_hashes=event_hashes,
        payload_hash=payload,
    )
    return TickCommit(
        run_id=request.run_id,
        tick=request.tick,
        resulting_tick=Tick(tick + 1),
        base_revision=request.expected_base_revision,
        resulting_revision=WorldRevision(tick + 1),
        predecessor_commit_hash=predecessor,
        commit_hash=commit_hash,
        idempotency_key=request.idempotency_key,
        event_count=len(request.events),
        payload_hash=payload,
        snapshot_id=None,
    )


def _service(events: tuple[WorldEvent, ...]) -> ReplayService:
    ticks = sorted({event.tick for event in events})
    commits: list[TickCommit] = []
    predecessor: CommitHash | None = None
    for tick in ticks:
        commit = _commit_for_tick(events, tick=tick, predecessor=predecessor)
        commits.append(commit)
        predecessor = commit.commit_hash
    return ReplayService(
        FakeRuns(_manifest()),
        FakeJournal(commits[0], events, commits=tuple(commits)),
        FakeSnapshots(_snapshot()),
    )


def test_ecology_hidden_from_observer_adapt() -> None:
    event = _ecology("evt-eco-hide", tick=0, sequence=0)
    assert "ecological_resource_changed" in HIDDEN_OBSERVER_EVENT_TYPES
    assert "ecological_resource_changed" not in SEMANTIC_TYPE_BY_KIND
    assert "ecological_resource_changed" not in SEMANTIC_EVENT_TYPES
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert is_hidden_observer_event(event)
    with pytest.raises(ValueError, match="observer_event_not_found"):
        adapt_event(event)
    visible = _wait("evt-v", tick=0, sequence=1)
    adapted = adapt_events((event, visible, event))
    assert [item.event_id for item in adapted] == ["evt-v"]


@pytest.mark.asyncio
async def test_keyset_excludes_ecology_and_disease_before_limit() -> None:
    events = _mixed_events()
    service = _service(events)
    page = await service.read_event_keyset_page(
        RunId(RUN_ID),
        after_tick=0,
        after_sequence=-1,
        limit=2,
        exclude_event_types=HIDDEN_OBSERVER_EVENT_TYPES,
    )
    assert [event.event_id.value for event in page.events] == ["evt-v0", "evt-v1"]
    more = await service.read_event_keyset_page(
        RunId(RUN_ID),
        after_tick=0,
        after_sequence=3,
        limit=10,
        exclude_event_types=HIDDEN_OBSERVER_EVENT_TYPES,
    )
    assert [event.event_id.value for event in more.events] == ["evt-v2"]
    assert more.next_offset is None
    raw = await service.read_event_keyset_page(
        RunId(RUN_ID),
        after_tick=0,
        after_sequence=-1,
        limit=20,
    )
    kinds = [event.event_type for event in raw.events]
    assert kinds.count("ecological_resource_changed") == 3
    assert kinds.count("disease_state_changed") == 2


@pytest.mark.asyncio
async def test_observer_http_list_hides_ecology() -> None:
    events = _mixed_events()
    reader = ObserverReadService(_service(events))
    page = await reader.events(
        RUN_ID,
        after_tick=None,
        after_sequence=None,
        limit=10,
        layout_id="reference-v1",
    )
    ids = [item.event_id for item in page.events]
    assert ids == ["evt-v0", "evt-v1", "evt-v2"]
    assert all(
        item.domain_kind not in HIDDEN_OBSERVER_EVENT_TYPES for item in page.events
    )
    with pytest.raises(ApiError) as exc:
        await reader.event(RUN_ID, "evt-eco0")
    assert exc.value.code == "observer_event_not_found"


@pytest.mark.asyncio
async def test_hidden_only_batch_advances_cursor_then_budget() -> None:
    # Hidden-only prefix before visible rows; plural exclusion required.
    events = (
        _ecology("evt-h0", tick=0, sequence=0),
        _ecology("evt-h1", tick=0, sequence=1, before=5, after=8),
        _disease("evt-h2", tick=0, sequence=2),
        _wait("evt-v0", tick=0, sequence=3),
        _wait("evt-v1", tick=1, sequence=0),
    )
    service = _service(events)
    page = await service.read_event_keyset_page(
        RunId(RUN_ID),
        after_tick=0,
        after_sequence=-1,
        limit=1,
        exclude_event_types=HIDDEN_OBSERVER_EVENT_TYPES,
    )
    assert [event.event_id.value for event in page.events] == ["evt-v0"]
    assert page.next_offset == 0
    more = await service.read_event_keyset_page(
        RunId(RUN_ID),
        after_tick=0,
        after_sequence=3,
        limit=1,
        exclude_event_types=HIDDEN_OBSERVER_EVENT_TYPES,
    )
    assert [event.event_id.value for event in more.events] == ["evt-v1"]

    # Exclusive-scan budget is max(64, (limit+1)*16); 64 hidden-only rows exhaust it.
    hidden_only = tuple(
        _ecology(
            f"evt-budget-{index}",
            tick=0,
            sequence=index,
            before=index,
            after=index + 1,
        )
        for index in range(64)
    )
    exhausted = _service(hidden_only)
    with pytest.raises(ValueError, match="observer_read_budget_exhausted"):
        await exhausted.read_event_keyset_page(
            RunId(RUN_ID),
            after_tick=0,
            after_sequence=-1,
            limit=1,
            exclude_event_types=HIDDEN_OBSERVER_EVENT_TYPES,
        )
