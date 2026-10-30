"""Metadata-only event-lane capture, independent cadence and atomic quotas.

Runner hooks and physical inventories are exercised below. Owner/grounding and
bounded journal-recovery proof remain separate Task4 acceptance work.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, replace
from typing import Any, Never

import pytest

from experiments.civilization_capture import CivilizationEvidenceRecorder
from simulation.civilization_boundaries import CivilizationBoundaryInput
from simulation.civilization_capture import (
    CivilizationCaptureOptions,
    CivilizationEventBatch,
    CivilizationEventKind,
    CivilizationOwnerConceptEvidence,
    CivilizationOwnerInventory,
    CivilizationReceiptItem,
    civilization_event_bytes,
    civilization_event_receipt,
    project_civilization_events,
    unavailable_civilization_events,
)
from simulation.civilization_models import (
    CivilizationCoverageState,
    CivilizationError,
    CivilizationWindow,
)
from simulation.clock import Tick
from simulation.lineage_ports import LineageBoundaryFrame
from simulation.models import RunId
from simulation.runner_models import SimulationRunnerConfig
from world.artifacts import ArtifactKind
from world.communications import origin_utterance
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V22,
    ArtifactCreated,
    EventDetails,
    ExchangeCompleted,
    ExchangeProposed,
    Given,
    JourneyArrived,
    JourneyEnded,
    JourneyStarted,
    OccurrenceContext,
    ProjectCompleted,
    ProjectContributed,
    ProjectCreated,
    PublicGoodMaintained,
    RepositoryMemberDeposited,
    Talked,
    Waited,
    WorldEvent,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.regions import Journey
from world.values import ItemKind

pytestmark = pytest.mark.unit


def _event(
    detail: EventDetails,
    *,
    tick: int = 0,
    sequence: int = 0,
    occurrence: OccurrenceContext | None = None,
) -> WorldEvent:
    return make_physical_replayable_event(
        event_id=EventId(f"event-{tick}-{sequence}"),
        run_id="run-capture",
        world_id=WorldId("world-capture"),
        tick=tick,
        sequence=sequence,
        cause=ActionCause(RequestId(f"request-{tick}-{sequence}"), EntityId("body-a")),
        resulting_revision=WorldRevision(tick + 1),
        details=detail,
        occurrence=occurrence
        or OccurrenceContext(origin_location_id=EntityId("loc-at-event")),
        schema_version=EVENT_SCHEMA_REPLAY_V22,
    )


def _exchange() -> ExchangeCompleted:
    return ExchangeCompleted(
        EntityId("body-a"),
        EntityId("body-b"),
        "accept",
        (EntityId("tool"),),
        (EntityId("food"),),
        ("tool",),
        ("food",),
    )


def _batch(*, tick: int = 0) -> CivilizationEventBatch:
    return project_civilization_events(
        "run-capture",
        tick,
        (_event(_exchange(), tick=tick),),
        expected_count=1,
        source="committed_result",
    )


def test_completed_exchange_has_exact_item_kinds_directions_and_event_time_endpoint(
) -> None:
    event = _event(_exchange())
    receipt = civilization_event_receipt(event)
    assert receipt is not None
    assert receipt.kind is CivilizationEventKind.EXCHANGE_COMPLETED
    assert receipt.participant_ids == ("body-a", "body-b")
    assert receipt.items == (
        CivilizationReceiptItem("tool", ItemKind.TOOL, "give"),
        CivilizationReceiptItem("food", ItemKind.FOOD, "take"),
    )
    assert receipt.origin_location_id == "loc-at-event"
    unplaced = civilization_event_receipt(
        replace(event, occurrence=OccurrenceContext())
    )
    assert unplaced is not None
    assert unplaced.origin_location_id is None
    assert unplaced.destination_location_id is None
    assert receipt.outcome == "completed"


def test_proposals_and_gifts_are_not_counted_as_trade() -> None:
    proposal = ExchangeProposed(
        EntityId("body-a"),
        EntityId("body-b"),
        "offer",
        (EntityId("tool"),),
        (EntityId("food"),),
    )
    events = (
        _event(proposal),
        _event(
            Given(EntityId("body-b"), EntityId("gift"), EntityId("body-b")), sequence=1
        ),
        _event(_exchange(), sequence=2),
    )
    batch = project_civilization_events(
        "run-capture", 0, events, expected_count=3, source="committed_result"
    )
    assert batch.examined_count == batch.expected_count == 3
    assert [receipt.kind for receipt in batch.receipts] == [
        CivilizationEventKind.GIVE,
        CivilizationEventKind.EXCHANGE_COMPLETED,
    ]
    assert batch.receipts[0].items[0].kind is None
    assert batch.receipts[0].items[0].direction == "transfer"


def test_known_empty_and_irrelevant_sources_differ_from_unavailable_recovery() -> None:
    empty = project_civilization_events(
        "run-capture", 0, (), expected_count=0, source="journal"
    )
    irrelevant = project_civilization_events(
        "run-capture",
        0,
        (_event(Waited()),),
        expected_count=1,
        source="committed_result",
    )
    unavailable = unavailable_civilization_events("run-capture", 0)
    assert empty.receipts == irrelevant.receipts == unavailable.receipts == ()
    assert empty.coverage.state is CivilizationCoverageState.COMPLETE
    assert irrelevant.examined_count == 1
    assert unavailable.coverage.state is CivilizationCoverageState.UNAVAILABLE
    assert unavailable.expected_count is None
    assert empty != unavailable


@pytest.mark.parametrize(
    "events,expected",
    [
        ((), 1),
        ((_event(Waited()),), 0),
        ((_event(Waited(), sequence=1),), 1),
        ((_event(Waited()), _event(Waited())), 2),
        ((_event(Waited(), tick=1),), 1),
    ],
)
def test_source_count_order_identity_or_tick_conflict_is_an_explicit_gap(
    events: tuple[WorldEvent, ...], expected: int
) -> None:
    batch = project_civilization_events(
        "run-capture", 0, events, expected_count=expected, source="journal"
    )
    assert batch.coverage.state is CivilizationCoverageState.UNAVAILABLE
    assert batch.coverage.reason == "event_gap"
    assert batch.expected_count == expected and batch.examined_count == len(events)
    assert not batch.receipts


def test_private_speech_is_discarded_without_payload_fingerprints_or_log_leaks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    speech = Talked(
        EntityId("body-b"),
        origin_utterance(text="CANARY_PRIVATE_SPEECH", speaker_id=EntityId("body-a")),
    )
    batch = project_civilization_events(
        "run-capture", 0, (_event(speech),), expected_count=1, source="committed_result"
    )
    encoded = civilization_event_bytes(batch)
    assert batch.examined_count == 1 and not batch.receipts
    for forbidden in (
        b"CANARY_PRIVATE_SPEECH",
        b"utterance",
        b"details",
        b"payload_hash",
        b"request_id",
        b"WorldEvent",
    ):
        assert forbidden not in encoded
    assert "CANARY_PRIVATE_SPEECH" not in caplog.text


@pytest.mark.parametrize(
    "detail,expected_kind",
    [
        (
            ProjectCreated(
                EntityId("project"), EntityId("place"), "well", EntityId("body-a"), 3, 2
            ),
            CivilizationEventKind.PROJECT_CREATED,
        ),
        (
            ProjectContributed(EntityId("project"), EntityId("body-a"), False, 1, 0),
            CivilizationEventKind.PROJECT_CONTRIBUTED,
        ),
        (
            ProjectCompleted(EntityId("project"), "well", EntityId("well")),
            CivilizationEventKind.PROJECT_COMPLETED,
        ),
        (
            PublicGoodMaintained(EntityId("project"), EntityId("body-a"), True, 1000),
            CivilizationEventKind.PUBLIC_GOOD_MAINTAINED,
        ),
        (
            RepositoryMemberDeposited(
                EntityId("repo"), EntityId("record"), 1, EntityId("body-a")
            ),
            CivilizationEventKind.REPOSITORY_MEMBER_DEPOSITED,
        ),
        (
            ArtifactCreated(
                EntityId("record"),
                ArtifactKind.NOTE,
                EntityId("body-a"),
                0,
                resulting_holder_id=EntityId("body-a"),
            ),
            CivilizationEventKind.ARTIFACT_CREATED,
        ),
    ],
)
def test_facility_receipts_copy_only_typed_physical_metadata(
    detail: EventDetails, expected_kind: CivilizationEventKind
) -> None:
    receipt = civilization_event_receipt(_event(detail))
    assert receipt is not None
    assert receipt.kind is expected_kind
    assert not {"marks", "content", "labels", "index_entries", "ledger"} & set(
        asdict(receipt)
    )


def test_journey_start_arrival_and_end_keep_their_distinct_outcomes() -> None:
    journey = Journey(
        "journey",
        (EntityId("body-a"),),
        EntityId("body-a"),
        EntityId("origin"),
        EntityId("destination"),
        "r1",
        "r2",
        0,
        2,
        3.0,
        3,
    )
    start = civilization_event_receipt(
        _event(JourneyStarted(journey, "move", 3.0, 3.0))
    )
    arrived = civilization_event_receipt(
        _event(
            JourneyArrived(
                "journey",
                (EntityId("body-a"),),
                EntityId("origin"),
                EntityId("destination"),
            )
        )
    )
    ended = civilization_event_receipt(
        _event(
            JourneyEnded(
                "journey",
                (EntityId("body-a"),),
                EntityId("origin"),
                EntityId("destination"),
                "arrival_timeout",
            )
        )
    )
    assert start is not None
    assert arrived is not None
    assert ended is not None
    assert start.origin_region_id == "r1" and start.destination_region_id == "r2"
    assert start.outcome is None
    assert arrived.outcome == "arrived"
    assert ended.outcome == "arrival_timeout"
    assert start.journey_id == arrived.journey_id == ended.journey_id == "journey"


def test_constructor_detaches_sequences_and_rejects_mutable_payloads_or_future_types(
) -> None:
    receipt = _batch().receipts[0]
    participants = ["a", "b"]
    # Mutable caller input must be detached by the frozen contract.
    copied = replace(receipt, participant_ids=participants)  # type: ignore[arg-type]
    participants.append("later")
    assert copied.participant_ids == ("a", "b")
    with pytest.raises(FrozenInstanceError):
        copied.tick = 2  # type: ignore[misc]  # Exercise frozen-field enforcement.
    with pytest.raises(CivilizationError):
        replace(receipt, tick=True)
    with pytest.raises(CivilizationError):
        # Deliberately malformed nested receipt input must be rejected.
        replace(receipt, items=({"payload": "secret"},))  # type: ignore[arg-type]
    with pytest.raises(CivilizationError):
        replace(receipt, participant_ids=("same", "same"))
    with pytest.raises(CivilizationError):
        # The boundary rejects strings in place of the closed enum.
        replace(receipt, kind="exchange_completed")  # type: ignore[arg-type]
    with pytest.raises(CivilizationError):
        replace(receipt, outcome="arrived")


def test_capture_defaults_off_and_disabled_does_not_build_or_retain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from experiments import civilization_capture as module

    def forbidden(_batch: CivilizationEventBatch) -> Never:
        raise AssertionError("disabled recorder encoded evidence")

    monkeypatch.setattr(module, "civilization_event_bytes", forbidden)
    recorder = CivilizationEvidenceRecorder()
    recorder.capture_events(_batch())
    assert not recorder.status.active and not recorder.status.failed
    assert not recorder.event_batches


def test_cadence_three_does_not_skip_event_source_coverage() -> None:
    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, cadence=3)
    )
    for tick in range(4):
        recorder.capture_events(_batch(tick=tick))
    assert [batch.tick for batch in recorder.event_batches] == [0, 1, 2, 3]
    assert recorder.covered_event_intervals == (CivilizationWindow(0, 4),)


def test_event_gaps_and_missing_prefix_are_not_repaired_by_later_complete_batches(
) -> None:
    recorder = CivilizationEvidenceRecorder(CivilizationCaptureOptions(enabled=True))
    recorder.capture_events(_batch(tick=3))
    recorder.capture_events(unavailable_civilization_events("run-capture", 4))
    recorder.capture_events(_batch(tick=5))
    assert recorder.status.first_event_tick == 3
    assert recorder.covered_event_intervals == (
        CivilizationWindow(3, 4),
        CivilizationWindow(5, 6),
    )
    assert not recorder.status.failed


def test_identical_batch_is_idempotent_and_conflicting_duplicate_latches_failure(
) -> None:
    recorder = CivilizationEvidenceRecorder(CivilizationCaptureOptions(enabled=True))
    batch = _batch()
    recorder.capture_events(batch)
    before = recorder.status
    recorder.capture_events(batch)
    assert recorder.status == before
    recorder.capture_events(unavailable_civilization_events("run-capture", 0))
    assert recorder.status.failure_code == "capture_conflict"
    assert recorder.status.failure_boundary == 1
    recorder.capture_events(_batch(tick=1))
    assert recorder.event_batches == (batch,)


@pytest.mark.parametrize("dimension", ["rows", "bytes"])
def test_quota_failure_is_atomic_and_includes_nested_items_and_batch_headers(
    dimension: str,
) -> None:
    batch = _batch()
    limits = (
        {"max_rows": 4}
        if dimension == "rows"
        else {"max_bytes": len(civilization_event_bytes(batch))}
    )
    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, **limits)
    )
    recorder.capture_events(batch)
    before = recorder.status
    assert before.retained_rows == 4  # batch, receipt and two item records
    recorder.capture_events(_batch(tick=1))
    assert recorder.event_batches == (batch,)
    assert recorder.status.retained_rows == before.retained_rows
    assert recorder.status.retained_bytes == before.retained_bytes
    assert recorder.status.failure_boundary == 2
    assert (
        recorder.status.failure_code
        == f"capture_{dimension[:-1] if dimension == 'rows' else 'byte'}_limit"
    )


def test_build_failure_is_latched_without_raw_exception_or_event_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from experiments import civilization_capture as module

    def failing(_batch: CivilizationEventBatch) -> Never:
        raise RuntimeError("CANARY_PRIVATE_EXCEPTION")

    recorder = CivilizationEvidenceRecorder(CivilizationCaptureOptions(enabled=True))
    monkeypatch.setattr(module, "civilization_event_bytes", failing)
    recorder.capture_events(_batch())
    assert recorder.status.failure_code == "capture_build_failed"
    assert recorder.status.retained_bytes == recorder.status.retained_rows == 0
    assert "CANARY_PRIVATE_EXCEPTION" not in caplog.text


@pytest.mark.parametrize(
    "field,value",
    [
        ("enabled", 1),
        ("cadence", True),
        ("cadence", 0),
        ("max_rows", 1_000_001),
        ("max_bytes", 268_435_457),
        ("max_boundaries", 10_001),
    ],
)
def test_options_are_exact_default_off_and_cannot_expand_hard_limits(
    field: str, value: Any
) -> None:
    with pytest.raises(CivilizationError):
        CivilizationCaptureOptions(**{field: value})


def test_physical_boundary_has_exact_bindings_but_never_pretends_private_capture(
) -> None:
    from simulation.civilization_boundaries import (
        civilization_boundary_bytes,
        project_civilization_boundary,
    )
    from tests.unit.test_observer_civilization import _physical_scene

    frame = project_civilization_boundary(_physical_scene())
    bindings = {row.body_id: row for row in frame.bodies}
    assert bindings["body-a"].owner_id == "not-the-body-id"
    assert bindings["body-dead"].living is False
    assert frame.cursor.boundary_tick == 4
    assert frame.private_coverage.state is CivilizationCoverageState.UNAVAILABLE
    assert frame.grounding_coverage.reason == "grounding_unavailable"
    assert b"WorldEvent" not in civilization_boundary_bytes(frame)
    with pytest.raises(CivilizationError):
        replace(frame, bodies=frame.bodies + frame.bodies[:1])


def test_sampled_boundary_cadence_duplicates_and_conflicts_are_explicit() -> None:
    from simulation.civilization_boundaries import project_civilization_boundary
    from tests.unit.test_observer_civilization import _physical_scene

    frame = project_civilization_boundary(_physical_scene())
    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, cadence=3)
    )
    assert not recorder.capture_boundary(frame)  # B4 is intentionally not sampled.
    assert not recorder.boundaries
    sampled = replace(
        frame,
        cursor=replace(frame.cursor, tick=6, boundary_tick=6),
        map_rows=tuple(
            replace(
                row,
                context=replace(
                    row.context,
                    source_refs=tuple(
                        replace(ref, tick=6) for ref in row.context.source_refs
                    ),
                    anchors=(),
                ),
            )
            for row in frame.map_rows
        ),
    )
    assert recorder.capture_boundary(sampled)
    assert recorder.boundaries == (sampled,)
    before = recorder.status
    assert recorder.capture_boundary(sampled)
    assert recorder.status == before
    conflict = replace(sampled, bodies=sampled.bodies[:-1])
    assert not recorder.capture_boundary(conflict)
    assert recorder.boundaries == (sampled,)
    assert recorder.status.failure_code == "capture_conflict"


def _runner_config(
    *, ticks: int = 3, two_owners: bool = False
) -> SimulationRunnerConfig:
    from agents.models import AgentId
    from simulation.runner_models import AgentCognitionSpec, AgentRunnerSpec
    from tests.simulation_helpers import alive_body
    from tests.unit.test_cultural_evidence_capture import _config

    config = _config(max_ticks=ticks)
    if not two_owners:
        return config
    body = alive_body("body-2")
    owner = AgentId("agent-2")
    return replace(
        config,
        agents=(
            *config.agents,
            AgentRunnerSpec(
                agent_id=owner,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=owner),
            ),
        ),
        scenario=replace(config.scenario, bodies=(*config.scenario.bodies, body)),
    )


@pytest.mark.asyncio
async def test_runner_capture_off_on_disabled_and_failing_have_identical_science(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from simulation.models import RunId
    from simulation.runner import SimulationRunner
    from simulation.runner_serialization import build_runner_result_document

    class Failing(CivilizationEvidenceRecorder):
        def capture_boundary(self, frame: CivilizationBoundaryInput) -> bool:
            raise RuntimeError("CANARY_SINK_EXCEPTION")

    outputs = []
    config = _runner_config(two_owners=True)
    for mode in ("off", "on", "disabled", "failing"):
        recorder = (
            Failing(CivilizationCaptureOptions(enabled=True))
            if mode == "failing"
            else CivilizationEvidenceRecorder(
                CivilizationCaptureOptions(enabled=mode == "on")
            )
        )
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-civilization-parity")
        ) as runner:
            if mode != "off":
                runner.set_civilization_boundary_sink(recorder)
            result = await runner.run()
            outputs.append(
                (
                    build_runner_result_document(
                        result=result, config=config
                    ).exact_trajectory_hash,
                    tuple(runner.engine._snapshot.event_history),
                    runner.export_runtime_checkpoint(),
                    runner.engine.detached_objective_facts(),
                )
            )
            status = runner.export_civilization_capture_status()
        if mode == "on":
            assert status is not None
            assert [frame.cursor.tick for frame in recorder.boundaries] == [0, 1, 2, 3]
            assert [batch.tick for batch in recorder.event_batches] == [0, 1, 2]
            assert not status.failed
        if mode == "failing":
            assert status is not None
            assert status.failed and status.failure_boundary == 0
            assert status.failure_code == "capture_failed"
        if mode == "disabled":
            assert not recorder.boundaries and not recorder.event_batches
    assert all(output == outputs[0] for output in outputs[1:])
    assert "CANARY_SINK_EXCEPTION" not in caplog.text


@pytest.mark.asyncio
async def test_runner_publishes_only_after_both_owners_finalize_and_acknowledge() -> (
    None
):
    from simulation.models import RunId
    from simulation.runner import SimulationRunner

    class Checked(CivilizationEvidenceRecorder):
        def capture_boundary(self, frame: CivilizationBoundaryInput) -> bool:
            checkpoint = runner.export_runtime_checkpoint()
            if frame.cursor.tick:
                assert checkpoint.pending_count == 0
                assert len(checkpoint.runtime_states) == 2
                assert all(
                    state.last_observation_key is not None
                    and state.last_observation_key[0] == frame.cursor.tick - 1
                    for state in checkpoint.runtime_states
                )
            return super().capture_boundary(frame)

    recorder = Checked(CivilizationCaptureOptions(enabled=True))
    async with await SimulationRunner.from_config(
        _runner_config(ticks=1, two_owners=True), run_id=RunId("run-finalized-capture")
    ) as runner:
        runner.set_civilization_boundary_sink(recorder)
        await runner.initialize_finalized_boundary()
        assert [frame.cursor.tick for frame in recorder.boundaries] == [0]
        await runner.run_tick()
    assert [frame.cursor.tick for frame in recorder.boundaries] == [0, 1]


@pytest.mark.asyncio
async def test_runner_sink_installation_is_once_and_before_start() -> None:
    from simulation.models import RunId
    from simulation.runner import SimulationRunner

    async with await SimulationRunner.from_config(
        _runner_config(ticks=1), run_id=RunId("run-install-capture")
    ) as runner:
        recorder = CivilizationEvidenceRecorder(
            CivilizationCaptureOptions(enabled=True)
        )
        runner.set_civilization_boundary_sink(recorder)
        with pytest.raises(ValueError, match="civilization_sink_replacement"):
            runner.set_civilization_boundary_sink(recorder)
        await runner.run_tick()
        with pytest.raises(ValueError, match="civilization_sink_after_start"):
            runner.set_civilization_boundary_sink(recorder)


@pytest.mark.asyncio
async def test_runner_cadence_three_keeps_all_events_and_only_sampled_boundaries(
) -> None:
    from simulation.models import RunId
    from simulation.runner import SimulationRunner

    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, cadence=3)
    )
    async with await SimulationRunner.from_config(
        _runner_config(ticks=4), run_id=RunId("run-cadence-capture")
    ) as runner:
        runner.set_civilization_boundary_sink(recorder)
        await runner.run()
    assert [frame.cursor.tick for frame in recorder.boundaries] == [0, 3]
    assert [batch.tick for batch in recorder.event_batches] == [0, 1, 2, 3]
    assert recorder.covered_event_intervals == (CivilizationWindow(0, 4),)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "point,ordinal",
    [("before_objective_commit", None), ("during_owner_finalization", 1)],
)
async def test_abort_or_partial_finalization_never_publishes_a_premature_boundary(
    point: str, ordinal: int | None
) -> None:
    from simulation.memory_finalization import InMemoryPendingFinalizationRepository
    from simulation.models import RunId
    from simulation.run_control import RunnerCrashInjected, RunnerCrashPoint
    from simulation.runner import RunnerDependencyFactories, SimulationRunner

    target = RunnerCrashPoint(point)

    def crash(current: RunnerCrashPoint, owner_ordinal: int | None) -> None:
        if current is target and owner_ordinal == ordinal:
            raise RunnerCrashInjected(current, ordinal=owner_ordinal)

    recorder = CivilizationEvidenceRecorder(CivilizationCaptureOptions(enabled=True))
    pending = InMemoryPendingFinalizationRepository()
    async with await SimulationRunner.from_config(
        _runner_config(ticks=2, two_owners=True),
        run_id=RunId("run-recovery-capture"),
        factories=RunnerDependencyFactories(pending_finalizations=pending),
    ) as runner:
        runner.set_civilization_boundary_sink(recorder)
        runner.set_crash_hook(crash)
        with pytest.raises(RunnerCrashInjected):
            await runner.run_tick()
        assert [frame.cursor.tick for frame in recorder.boundaries] == [0]
        assert not recorder.event_batches
        runner.set_crash_hook(None)
        if target is RunnerCrashPoint.DURING_OWNER_FINALIZATION:
            await runner.recover_pending_finalizations()
            assert [frame.cursor.tick for frame in recorder.boundaries] == [0, 1]
            assert (
                recorder.event_batches[0].coverage.state
                is CivilizationCoverageState.UNAVAILABLE
            )
            assert recorder.event_batches[0].expected_count is None


def test_disabled_coordinator_does_not_export_facts_even_at_boundary_zero() -> None:
    from simulation.civilization_boundaries import CivilizationCaptureCoordinator

    recorder = CivilizationEvidenceRecorder()
    coordinator = CivilizationCaptureCoordinator(recorder, "run-disabled")

    def forbidden() -> Never:
        raise AssertionError("disabled capture called the objective exporter")

    coordinator.publish(0, forbidden)
    coordinator.publish(1, forbidden)
    assert coordinator.status.last_finalized_boundary is None
    assert not coordinator.status.failed


def test_physical_capture_never_retains_artifact_marks_or_repository_index_contents(
) -> None:
    from simulation.civilization_boundaries import (
        civilization_boundary_bytes,
        project_civilization_boundary,
    )
    from tests.unit.test_observer_civilization import _physical_scene
    from world.artifacts import ArtifactContent, InformationArtifact
    from world.repositories import (
        KnowledgeRepository,
        RepositoryAccessMode,
        RepositoryIndexEntry,
    )

    record = InformationArtifact(
        EntityId("record"),
        ArtifactKind.NOTE,
        EntityId("body-a"),
        0,
        ArtifactContent(("canary_mark",), ()),
        location_id=EntityId("loc-1"),
    )
    repository = KnowledgeRepository(
        EntityId("repo"),
        EntityId("loc-1"),
        (EntityId("body-a"),),
        0,
        RepositoryAccessMode.OPEN,
        index_entries=(
            RepositoryIndexEntry("index", EntityId("record"), ("canary_index",), 0),
        ),
    )
    frame = project_civilization_boundary(
        replace(_physical_scene(), artifacts=(record,), repositories=(repository,))
    )
    encoded = civilization_boundary_bytes(frame)
    assert b"canary_mark" not in encoded and b"canary_index" not in encoded
    assert b"index_entries" not in encoded and b"content_revision" not in encoded


def test_boundary_cap_is_atomic_and_does_not_evict_the_earlier_boundary() -> None:
    from simulation.civilization_boundaries import project_civilization_boundary
    from tests.unit.test_observer_civilization import _physical_scene

    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, max_boundaries=1)
    )
    first = project_civilization_boundary(_physical_scene())
    second = project_civilization_boundary(
        replace(_physical_scene(), tick=5, revision=5)
    )
    assert recorder.capture_boundary(first)
    before = recorder.status
    assert not recorder.capture_boundary(second)
    assert recorder.boundaries == (first,)
    assert recorder.status.retained_rows == before.retained_rows
    assert recorder.status.retained_bytes == before.retained_bytes
    assert recorder.status.failure_code == "capture_boundary_limit"
    assert recorder.status.failure_boundary == 5


def test_event_and_physical_lanes_share_one_cumulative_byte_budget() -> None:
    from simulation.civilization_boundaries import (
        civilization_boundary_bytes,
        project_civilization_boundary,
    )
    from tests.unit.test_observer_civilization import _physical_scene

    frame = project_civilization_boundary(_physical_scene())

    def batch_for(tick: int) -> CivilizationEventBatch:
        batch = _batch(tick=tick)
        return replace(
            batch,
            run_id=frame.cursor.run_id,
            receipts=tuple(
                replace(receipt, run_id=frame.cursor.run_id)
                for receipt in batch.receipts
            ),
        )

    events = batch_for(4)
    limit = len(civilization_boundary_bytes(frame)) + len(
        civilization_event_bytes(events)
    )
    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, max_bytes=limit)
    )
    assert recorder.capture_boundary(frame)
    assert recorder.capture_events(events)
    assert recorder.status.retained_bytes == limit
    assert not recorder.capture_events(batch_for(5))
    assert recorder.status.failure_code == "capture_byte_limit"
    assert recorder.boundaries == (frame,) and recorder.event_batches == (events,)


@pytest.mark.asyncio
async def test_restored_runner_keeps_missing_prefix_without_boundary_zero_backfill(
) -> None:
    from simulation.models import RunId
    from simulation.runner import SimulationRunner

    config = _runner_config(ticks=2)
    run_id = RunId("run-restored-capture")
    async with await SimulationRunner.from_config(config, run_id=run_id) as source:
        await source.run_tick()
        checkpoint = source.export_runtime_checkpoint()
    recorder = CivilizationEvidenceRecorder(CivilizationCaptureOptions(enabled=True))
    async with await SimulationRunner.from_config(config, run_id=run_id) as restored:
        restored.set_civilization_boundary_sink(recorder)
        restored.apply_runtime_checkpoint(checkpoint)
        await restored.run_tick()
        status = restored.export_civilization_capture_status()
    assert [frame.cursor.tick for frame in recorder.boundaries] == [2]
    assert status is not None
    assert status.missing_prefix_through == 1
    assert [batch.tick for batch in recorder.event_batches] == [1]


@pytest.mark.asyncio
async def test_existing_cultural_and_lineage_sinks_stay_independent() -> None:
    from simulation.models import RunId
    from simulation.runner import SimulationRunner
    from tests.unit.test_cultural_evidence_capture import _RecordingSink
    from tests.unit.test_lineage_capture import _config as lineage_config

    class Lineage:
        def __init__(self) -> None:
            self.boundaries: list[int] = []

        async def capture(self, frame: LineageBoundaryFrame) -> None:
            self.boundaries.append(frame.boundary_tick)

    cultural = _RecordingSink()
    lineage = Lineage()
    recorder = CivilizationEvidenceRecorder(CivilizationCaptureOptions(enabled=True))
    async with await SimulationRunner.from_config(
        lineage_config(max_ticks=2), run_id=RunId("run-composed-capture")
    ) as runner:
        runner.set_cultural_boundary_sink(cultural)
        runner.set_lineage_boundary_sink(lineage)
        runner.set_civilization_boundary_sink(recorder)
        await runner.run()
        assert not runner.export_cultural_capture_status().failed
        status = runner.export_civilization_capture_status()
        assert status is not None
        assert not status.failed
    assert [frame.boundary_tick for frame in cultural.frames] == [0, 1, 2]
    assert set(lineage.boundaries) == {0, 1, 2}
    assert [frame.cursor.tick for frame in recorder.boundaries] == [0, 1, 2]


def test_cadence_skip_does_not_copy_physical_facts_for_a_known_empty_tick() -> None:
    from simulation.civilization_boundaries import CivilizationCaptureCoordinator
    from simulation.clock import Tick
    from simulation.lifecycle import TickResult

    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, cadence=3)
    )
    coordinator = CivilizationCaptureCoordinator(recorder, "run-skipped-boundary")

    def forbidden() -> Never:
        raise AssertionError("unsampled boundary exported objective facts")

    result = TickResult(Tick(0), Tick(1), WorldRevision(0), WorldRevision(0), (), ())
    coordinator.publish(1, forbidden, result=result)
    assert not coordinator.status.failed
    assert coordinator.status.last_finalized_boundary == 1
    assert not recorder.boundaries
    assert len(recorder.event_batches) == 1
    assert (
        recorder.event_batches[0].coverage.state is CivilizationCoverageState.COMPLETE
    )
    assert recorder.event_batches[0].expected_count == 0


def _owner_inventory_with_evidence(
    *evidence: CivilizationOwnerConceptEvidence,
) -> CivilizationOwnerInventory:
    from simulation.civilization_capture import (
        CivilizationInventoryChannel,
        CivilizationInventoryCoverage,
        CivilizationOwnerConcept,
        CivilizationOwnerInventory,
    )
    from simulation.civilization_models import (
        CivilizationCoverage,
        CivilizationCoverageState,
    )

    channels = tuple(
        CivilizationInventoryCoverage(
            channel,
            (
                CivilizationCoverage(CivilizationCoverageState.COMPLETE)
                if channel is CivilizationInventoryChannel.INSTITUTION_CONCEPTS
                else CivilizationCoverage(
                    CivilizationCoverageState.DISABLED, "capture_off"
                )
            ),
        )
        for channel in CivilizationInventoryChannel
    )
    concept = CivilizationOwnerConcept(
        "concept-1",
        "stable",
        "institutionalized",
        len(evidence),
        7,
        7,
        tuple(evidence),
    )
    return CivilizationOwnerInventory(
        "agent-1", 0, True, channels, concepts=(concept,)
    )


def test_exact_project_and_repository_grounding_witnesses() -> None:
    from simulation.civilization_capture import (
        CivilizationGroundingObservation,
        CivilizationGroundingProject,
        CivilizationGroundingRepository,
        CivilizationOwnerConceptEvidence,
        institution_grounding_witnesses,
    )

    inventory = _owner_inventory_with_evidence(
        CivilizationOwnerConceptEvidence(
            "evidence-project",
            8,
            "observed",
            "role_recognition",
            "project-0-1-7",
            "agent-1",
        ),
        CivilizationOwnerConceptEvidence(
            "evidence-repository",
            8,
            "observed",
            "role_recognition",
            "repository-0-0",
            "agent-2",
        ),
    )
    observation = CivilizationGroundingObservation(
        "agent-1",
        8,
        (CivilizationGroundingProject("project-1", "loc-1", ((1, 7),)),),
        (CivilizationGroundingRepository("repository-1", "loc-2", 1),),
    )
    witnesses, coverage = institution_grounding_witnesses(
        (inventory,), (observation,), complete=True
    )
    assert coverage.state is CivilizationCoverageState.COMPLETE
    assert [(row.source_kind, row.source_id, row.location_id) for row in witnesses] == [
        ("project", "project-1", "loc-1"),
        ("repository", "repository-1", "loc-2"),
    ]


def test_testimony_forged_or_out_of_range_ordinals_never_ground_institutions() -> None:
    from simulation.civilization_capture import (
        CivilizationGroundingObservation,
        CivilizationOwnerConceptEvidence,
        institution_grounding_witnesses,
    )

    inventory = _owner_inventory_with_evidence(
        CivilizationOwnerConceptEvidence(
            "evidence-testimony",
            8,
            "testimony",
            "role_recognition",
            "project-0-0-8",
            None,
        ),
        CivilizationOwnerConceptEvidence(
            "evidence-forged",
            8,
            "observed",
            "role_recognition",
            "project-9-0-8",
            "agent-1",
        ),
        CivilizationOwnerConceptEvidence(
            "evidence-nonrole",
            8,
            "observed",
            "procedure_recurrence",
            "project-0-0-8",
            None,
        ),
    )
    observation = CivilizationGroundingObservation("agent-1", 8, (), ())
    witnesses, coverage = institution_grounding_witnesses(
        (inventory,), (observation,), complete=True
    )
    assert witnesses == ()
    assert coverage.state is CivilizationCoverageState.PARTIAL
    assert coverage.reason == "grounding_unavailable"


def test_missing_or_incomplete_grounding_observation_is_explicit() -> None:
    from simulation.civilization_capture import (
        CivilizationGroundingObservation,
        CivilizationOwnerConceptEvidence,
        institution_grounding_witnesses,
    )

    inventory = _owner_inventory_with_evidence(
        CivilizationOwnerConceptEvidence(
            "evidence-project",
            8,
            "observed",
            "role_recognition",
            "project-0-0-8",
            "agent-1",
        )
    )
    _, missing = institution_grounding_witnesses((inventory,), (), complete=False)
    assert missing.state is CivilizationCoverageState.UNAVAILABLE
    assert missing.reason == "grounding_unavailable"
    observation = CivilizationGroundingObservation("agent-1", 8, (), ())
    _, partial = institution_grounding_witnesses(
        (inventory,), (observation,), complete=False
    )
    assert partial.state is CivilizationCoverageState.PARTIAL


class _JournalCommit:
    def __init__(self, run_id: str, tick: int, count: int) -> None:
        from simulation.clock import Tick
        from simulation.models import RunId

        self.run_id = RunId(run_id)
        self.tick = Tick(tick)
        self.event_count = count


class _Journal:
    def __init__(
        self,
        commit: _JournalCommit | None = None,
        events: tuple[WorldEvent, ...] = (),
    ) -> None:
        self.commit = commit
        self.events = tuple(events)
        self.pages: list[tuple[int, int, int, int]] = []

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> _JournalCommit | None:
        return self.commit

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        self.pages.append((from_tick.value, to_tick.value, limit, offset))
        return self.events[offset : offset + limit]


@pytest.mark.asyncio
async def test_journal_recovery_proves_known_empty_and_exact_nonempty_ticks() -> None:
    from simulation.civilization_capture import recover_civilization_events

    empty = await recover_civilization_events(
        _Journal(_JournalCommit("run-capture", 3, 0)), "run-capture", 3
    )
    assert empty.coverage.state is CivilizationCoverageState.COMPLETE
    assert empty.source == "journal"
    assert empty.expected_count == 0
    assert empty.receipts == ()

    event = _event(_exchange(), tick=3, sequence=0)
    batch = await recover_civilization_events(
        _Journal(_JournalCommit("run-capture", 3, 1), (event,)),
        "run-capture",
        3,
    )
    assert batch.coverage.state is CivilizationCoverageState.COMPLETE
    assert batch.source == "journal"
    assert [row.kind for row in batch.receipts] == [
        CivilizationEventKind.EXCHANGE_COMPLETED
    ]


@pytest.mark.asyncio
async def test_missing_or_mismatched_journal_evidence_is_never_known_empty() -> None:
    from simulation.civilization_capture import recover_civilization_events

    missing = await recover_civilization_events(_Journal(), "run-capture", 3)
    assert missing.coverage.state is CivilizationCoverageState.UNAVAILABLE
    assert missing.coverage.reason == "event_gap"

    wrong = await recover_civilization_events(
        _Journal(_JournalCommit("run-capture", 3, 2), (_event(_exchange(), tick=3),)),
        "run-capture",
        3,
    )
    assert wrong.coverage.state is CivilizationCoverageState.UNAVAILABLE
    assert wrong.expected_count == 2
    assert wrong.examined_count == 1

    oversized = await recover_civilization_events(
        _Journal(_JournalCommit("run-capture", 3, 3), (
            _event(_exchange(), tick=3, sequence=0),
            _event(_exchange(), tick=3, sequence=1),
            _event(_exchange(), tick=3, sequence=2),
        )),
        "run-capture",
        3,
        max_bytes=1,
    )
    assert oversized.coverage.state is CivilizationCoverageState.UNAVAILABLE


@pytest.mark.asyncio
async def test_runner_recovery_uses_journal_proof_instead_of_unknown_events() -> None:
    from simulation.memory_finalization import InMemoryPendingFinalizationRepository
    from simulation.models import RunId
    from simulation.run_control import RunnerCrashInjected, RunnerCrashPoint
    from simulation.runner import RunnerDependencyFactories, SimulationRunner

    pending = InMemoryPendingFinalizationRepository()
    journal = _Journal(_JournalCommit("run-recovery-journal", 0, 0))
    recorder = CivilizationEvidenceRecorder(CivilizationCaptureOptions(enabled=True))

    def crash(current: RunnerCrashPoint, owner_ordinal: int | None) -> None:
        if (
            current is RunnerCrashPoint.DURING_OWNER_FINALIZATION
            and owner_ordinal == 1
        ):
            raise RunnerCrashInjected(current, ordinal=owner_ordinal)

    async with await SimulationRunner.from_config(
        _runner_config(ticks=2, two_owners=True),
        run_id=RunId("run-recovery-journal"),
        factories=RunnerDependencyFactories(
            pending_finalizations=pending,
            journal=journal,  # type: ignore[arg-type]
        ),
    ) as runner:
        runner.set_civilization_boundary_sink(recorder)
        runner.set_crash_hook(crash)
        with pytest.raises(RunnerCrashInjected):
            await runner.run_tick()
        runner.set_crash_hook(None)
        await runner.recover_pending_finalizations()

    assert [frame.cursor.tick for frame in recorder.boundaries] == [0, 1]
    batch = recorder.event_batches[0]
    assert batch.source == "journal"
    assert batch.coverage.state is CivilizationCoverageState.COMPLETE
    assert batch.expected_count == 0
    assert batch.receipts == ()


def test_newborn_empty_owner_inventory_is_complete_empty_not_unavailable() -> None:
    from agents.models import AgentId
    from simulation.civilization_owner_export import (
        owner_inventory_from_runtime,
    )
    from simulation.cultural_evidence import (
        CULTURAL_EVIDENCE_CHANNELS,
        CulturalChannelExport,
        CulturalOwnerExport,
    )

    cultural = CulturalOwnerExport(
        AgentId("agent-newborn"),
        0,
        True,
        tuple(
            CulturalChannelExport(
                channel,
                True,
                "complete",
                "fresh_empty",
                None,
            )
            for channel in CULTURAL_EVIDENCE_CHANNELS
        ),
    )
    inventory = owner_inventory_from_runtime(
        cultural,
        groups=None,
        groups_enabled=False,
        concepts=None,
        concepts_enabled=False,
        offices=None,
        offices_enabled=False,
        decay=None,
        decay_enabled=False,
    )
    assert inventory.owner_id == "agent-newborn"
    assert inventory.living is True
    assert all(
        row.coverage.state in {
            CivilizationCoverageState.COMPLETE,
            CivilizationCoverageState.DISABLED,
        }
        for row in inventory.channels
    )
    assert (
        inventory.cultural_traits,
        inventory.terminology,
        inventory.narratives,
        inventory.knowledge,
        inventory.groups,
        inventory.concepts,
        inventory.offices,
        inventory.decay_samples,
    ) == ((), (), (), (), (), (), (), ())
