# mypy: ignore-errors

"""Observer surfaces redact private disease transitions and death diagnostics."""

from __future__ import annotations

import json
from typing import Any

import pytest

from api.errors import ApiError
from api.observer_service import ObserverReadService
from api.routes.observer_stream import (
    ObserverStreamConfig,
    ObserverStreamPage,
    ObserverStreamSession,
)
from observer.adapt import (
    HIDDEN_OBSERVER_EVENT_TYPE,
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
from world.effects import ActionCause, DeathCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V24,
    Died,
    DiseaseRowView,
    DiseaseStateChanged,
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


def _disease(
    event_id: str,
    *,
    tick: int,
    sequence: int,
    before: DiseaseRowView | None,
    after: DiseaseRowView | None,
) -> WorldEvent:
    details = DiseaseStateChanged(
        body_id=EntityId(BODY_ID),
        before=before,
        after=after,
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


def _died(event_id: str, *, tick: int, sequence: int) -> WorldEvent:
    details = Died(EntityId(BODY_ID), DeathCause.DISEASE)
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
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId("loc-camp")
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V24,
    )


def _mixed_events() -> tuple[WorldEvent, ...]:
    # Visible / hidden / visible / hidden-only trailing tick.
    return (
        _wait("evt-v0", tick=0, sequence=0),
        _disease(
            "evt-h0",
            tick=0,
            sequence=1,
            before=None,
            after=DiseaseRowView(phase="latent", due_tick=2),
        ),
        _wait("evt-v1", tick=0, sequence=2),
        _disease(
            "evt-h1",
            tick=1,
            sequence=0,
            before=DiseaseRowView(phase="latent", due_tick=2),
            after=DiseaseRowView(phase="active", due_tick=5, symptomatic=True),
        ),
        _died("evt-death", tick=1, sequence=1),
        _disease(
            "evt-h2",
            tick=1,
            sequence=2,
            before=DiseaseRowView(phase="active", due_tick=5, symptomatic=True),
            after=None,
        ),
        _disease(
            "evt-h3",
            tick=2,
            sequence=0,
            before=None,
            after=DiseaseRowView(phase="latent", due_tick=4),
        ),
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
        idempotency_key=f"idem-disease-{tick}",
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


def test_semantic_count_unchanged_and_hidden_predicate() -> None:
    assert HIDDEN_OBSERVER_EVENT_TYPE not in SEMANTIC_TYPE_BY_KIND
    assert HIDDEN_OBSERVER_EVENT_TYPE not in SEMANTIC_EVENT_TYPES
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    hidden = _disease(
        "evt-h",
        tick=0,
        sequence=0,
        before=None,
        after=DiseaseRowView(phase="latent", due_tick=1),
    )
    visible = _wait("evt-v", tick=0, sequence=1)
    assert is_hidden_observer_event(hidden) is True
    assert is_hidden_observer_event(visible) is False
    with pytest.raises(ValueError, match="observer_event_not_found"):
        adapt_event(hidden)
    adapted = adapt_events((hidden, visible, hidden))
    assert [item.event_id for item in adapted] == ["evt-v"]


def test_death_projection_omits_disease_diagnostics() -> None:
    death = _died("evt-death", tick=0, sequence=0)
    adapted = adapt_event(death)
    payload = json.dumps(adapted.public_mapping())
    assert adapted.domain_kind == "died"
    assert adapted.target_id == BODY_ID
    assert "disease" not in payload.lower()
    assert "death_cause" not in payload
    assert "DISEASE" not in payload


@pytest.mark.asyncio
async def test_keyset_excludes_before_limit_and_objective_stays_raw() -> None:
    events = _mixed_events()
    service = _service(events)
    page = await service.read_event_keyset_page(
        RunId(RUN_ID),
        after_tick=0,
        after_sequence=-1,
        limit=2,
        exclude_event_type=HIDDEN_OBSERVER_EVENT_TYPE,
    )
    assert [event.event_id.value for event in page.events] == ["evt-v0", "evt-v1"]
    assert page.next_offset == 0
    more = await service.read_event_keyset_page(
        RunId(RUN_ID),
        after_tick=0,
        after_sequence=2,
        limit=10,
        exclude_event_type=HIDDEN_OBSERVER_EVENT_TYPE,
    )
    assert [event.event_id.value for event in more.events] == ["evt-death"]
    assert more.next_offset is None
    raw = await service.read_event_keyset_page(
        RunId(RUN_ID),
        after_tick=0,
        after_sequence=-1,
        limit=20,
    )
    kinds = [event.event_type for event in raw.events]
    assert HIDDEN_OBSERVER_EVENT_TYPE in kinds
    assert kinds.count(HIDDEN_OBSERVER_EVENT_TYPE) == 4


@pytest.mark.asyncio
async def test_observer_http_list_detail_ticks_and_frame() -> None:
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
    assert ids == ["evt-v0", "evt-v1", "evt-death"]
    assert all(item.domain_kind != HIDDEN_OBSERVER_EVENT_TYPE for item in page.events)
    with pytest.raises(ApiError) as exc:
        await reader.event(RUN_ID, "evt-h0")
    assert exc.value.code == "observer_event_not_found"
    death = await reader.event(RUN_ID, "evt-death")
    death_payload = death.model_dump(mode="json")
    assert "disease" not in json.dumps(death_payload).lower()
    ticks = await reader.ticks(RUN_ID, from_tick=0, to_tick=2, limit=10)
    by_tick = {row.tick: row for row in ticks.ticks}
    assert by_tick[0].event_count == 2
    assert by_tick[1].event_count == 1
    assert 2 not in by_tick  # hidden-only trailing tick omitted
    first = await reader.events(
        RUN_ID,
        after_tick=None,
        after_sequence=None,
        limit=1,
        layout_id="reference-v1",
    )
    assert [item.event_id for item in first.events] == ["evt-v0"]
    second = await reader.events(
        RUN_ID,
        after_tick=0,
        after_sequence=0,
        limit=10,
        layout_id="reference-v1",
    )
    assert [item.event_id for item in second.events] == ["evt-v1", "evt-death"]


@pytest.mark.asyncio
async def test_completed_stream_drains_visible_pages_and_hides_suffix() -> None:
    events = _mixed_events()
    replay = _service(events)

    async def read_events(
        after_tick: int, after_sequence: int, limit: int
    ) -> ObserverStreamPage:
        page = await replay.read_event_keyset_page(
            RunId(RUN_ID),
            after_tick=after_tick,
            after_sequence=after_sequence,
            limit=limit,
            exclude_event_type=HIDDEN_OBSERVER_EVENT_TYPE,
        )
        adapted = tuple(adapt_event(event) for event in page.events)
        return ObserverStreamPage(
            events=adapted,
            exhausted=page.next_offset is None,
        )

    async def head() -> int:
        return 3

    async def done() -> bool:
        return True

    session = ObserverStreamSession(
        read_events=read_events, head_tick=head, completed=done
    )
    config = ObserverStreamConfig(
        run_id=RUN_ID,
        after_tick=0,
        after_sequence=-1,
        queue_size=8,
        catchup_batch_size=1,
        heartbeat_seconds=30.0,
        poll_seconds=0.01,
        hello={"kind": "hello"},
        head_tick=3,
    )
    envelopes: list[dict[str, Any]] = [
        item async for item in session.subscribe(config)
    ]
    kinds = [item["kind"] for item in envelopes]
    assert kinds[0] == "hello"
    assert kinds[-1] == "completion"
    emitted = [
        item["event"]["event_id"] for item in envelopes if item["kind"] == "event"
    ]
    assert emitted == ["evt-v0", "evt-v1", "evt-death"]
    completion = envelopes[-1]
    assert completion["after_tick"] == 1
    assert completion["after_sequence"] == 1
    for item in envelopes:
        if item["kind"] != "event":
            continue
        payload = json.dumps(item["event"])
        assert HIDDEN_OBSERVER_EVENT_TYPE not in payload
        assert "disease_state_changed" not in payload
