"""Append-only filesystem evidence spool contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.persistence import EvidenceSpoolStatus
from persistence.evidence_spool_filesystem import (
    EvidenceSpoolConflict,
    EvidenceSpoolError,
    EvidenceSpoolFull,
    EvidenceSpoolSealed,
    create_evidence_spool,
)

pytestmark = pytest.mark.unit


def test_append_lookup_boundary_and_ordered_iteration(tmp_path: Path) -> None:
    spool = create_evidence_spool(tmp_path, segment_rows=2, segment_bytes=4096)
    assert spool.append(
        lane="cultural", boundary_tick=2, identity="frame-2", payload=b"two"
    )
    assert spool.append(
        lane="cultural", boundary_tick=1, identity="frame-1", payload=b"one"
    )
    assert spool.append(
        lane="cultural", boundary_tick=3, identity="frame-3", payload=b"three"
    )
    assert spool.get(lane="cultural", identity="frame-2") == b"two"
    assert spool.get(lane="cultural", identity="missing") is None
    assert spool.read_boundary(lane="cultural", boundary_tick=2) == (b"two",)
    assert spool.iter_lane(
        lane="cultural", after_boundary=None, limit=10
    ) == (b"one", b"two", b"three")
    assert spool.iter_lane(
        lane="cultural", after_boundary=1, limit=1
    ) == (b"two",)
    status = spool.status()
    assert status.record_count == 3
    assert status.byte_count == 11
    assert status.first_boundary == 1
    assert status.last_boundary == 3
    assert status.sealed is False


def test_duplicate_is_idempotent_and_conflict_fails(tmp_path: Path) -> None:
    spool = create_evidence_spool(tmp_path)
    assert spool.append(
        lane="civilization", boundary_tick=1, identity="events-1", payload=b"a"
    )
    assert not spool.append(
        lane="civilization", boundary_tick=1, identity="events-1", payload=b"a"
    )
    with pytest.raises(EvidenceSpoolConflict):
        spool.append(
            lane="civilization",
            boundary_tick=1,
            identity="events-1",
            payload=b"b",
        )
    assert spool.status().record_count == 1


def test_seal_and_quota_fail_closed(tmp_path: Path) -> None:
    spool = create_evidence_spool(tmp_path, max_records=1, max_bytes=8)
    spool.append(lane="cultural", boundary_tick=1, identity="a", payload=b"1234")
    with pytest.raises(EvidenceSpoolFull):
        spool.append(
            lane="cultural", boundary_tick=2, identity="b", payload=b"1234"
        )
    status = spool.seal()
    assert status.sealed is True
    with pytest.raises(EvidenceSpoolSealed):
        spool.append(
            lane="cultural", boundary_tick=3, identity="c", payload=b"x"
        )


def test_restart_reads_committed_records(tmp_path: Path) -> None:
    first = create_evidence_spool(tmp_path)
    first.append(lane="cultural", boundary_tick=1, identity="a", payload=b"alpha")
    second = create_evidence_spool(tmp_path)
    assert second.get(lane="cultural", identity="a") == b"alpha"
    assert second.iter_lane(
        lane="cultural", after_boundary=None, limit=10
    ) == (b"alpha",)


def test_corrupt_segment_and_bad_lane_fail_closed(tmp_path: Path) -> None:
    spool = create_evidence_spool(tmp_path)
    spool.append(lane="cultural", boundary_tick=1, identity="a", payload=b"alpha")
    segment = next((tmp_path / "lanes" / "cultural" / "segments").glob("*.jsonl"))
    content = segment.read_bytes()
    segment.write_bytes(content.replace(b"YWxwaGE=", b"YmFk"))
    with pytest.raises(EvidenceSpoolError):
        spool.get(lane="cultural", identity="a")
    with pytest.raises(ValueError):
        spool.append(lane="../escape", boundary_tick=1, identity="x", payload=b"x")


def _cultural_frame(tick: int):
    from agents.cognition.cultural_features import CulturalFeatureLedger
    from agents.cognition.cultural_narratives import NarrativeLedger
    from agents.cognition.practical_knowledge import PracticalKnowledgeLedger
    from agents.cognition.semantic_naming import TerminologyLedger
    from agents.models import AgentId
    from simulation.cultural_evidence import (
        CulturalBoundaryExport,
        CulturalChannelExport,
        CulturalOwnerExport,
    )

    owner = AgentId("agent-a")
    channels = (
        CulturalChannelExport(
            "cultural_features",
            True,
            "complete",
            "carried_ledger",
            CulturalFeatureLedger(owner_id=owner),
        ),
        CulturalChannelExport(
            "terminology",
            True,
            "complete",
            "carried_ledger",
            TerminologyLedger(owner_id=owner),
        ),
        CulturalChannelExport(
            "narratives",
            True,
            "complete",
            "carried_ledger",
            NarrativeLedger(owner_id=owner),
        ),
        CulturalChannelExport(
            "practical_knowledge",
            True,
            "complete",
            "carried_ledger",
            PracticalKnowledgeLedger(owner_id=owner),
        ),
    )
    return CulturalBoundaryExport(
        "run-spool", tick, (CulturalOwnerExport(owner, 0, True, channels),)
    )


@pytest.mark.asyncio
async def test_spooled_cultural_recorder_source_parity_and_no_hot_frames(
    tmp_path: Path,
) -> None:
    from experiments.cultural_evidence import CulturalEvidenceRecorder

    spool = create_evidence_spool(tmp_path)
    recorder = CulturalEvidenceRecorder(spool=spool)
    frames = (_cultural_frame(0), _cultural_frame(1))
    for frame in frames:
        recorder.capture(frame)
        recorder.capture(frame)
    assert recorder.frame_count == 2
    assert recorder.result().frames == frames
    assert tuple(recorder.source().iter_boundaries()) == frames
    assert recorder.source().read_boundary(1) == frames[1]
    assert recorder.source().boundary_ticks() == (0, 1)
    assert recorder._frames == []


def test_spooled_cultural_recorder_rejects_conflicting_boundary(
    tmp_path: Path,
) -> None:
    from experiments.cultural_evidence import CulturalEvidenceRecorder

    recorder = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path))
    recorder.capture(_cultural_frame(0))
    with pytest.raises(ValueError, match="cultural_evidence_conflict"):
        recorder.capture(_cultural_frame(1).__class__("run-spool", 0, ()))


def test_cultural_and_civilization_codecs_round_trip_typed_contracts() -> None:
    from experiments.evidence_codecs import (
        decode_civilization_boundary,
        decode_civilization_event_batch,
        decode_cultural_boundary,
        encode_civilization_boundary,
        encode_civilization_event_batch,
        encode_cultural_boundary,
    )
    from simulation.civilization_capture import project_civilization_events
    from tests.unit.test_civilization_publication import _frame, _inventory

    cultural = _cultural_frame(4)
    assert decode_cultural_boundary(encode_cultural_boundary(cultural)) == cultural

    boundary = _frame(4, inventories=(_inventory("agent-a"),))
    assert (
        decode_civilization_boundary(encode_civilization_boundary(boundary))
        == boundary
    )
    batch = project_civilization_events(
        "run-capture",
        4,
        (),
        expected_count=0,
        source="committed_result",
    )
    assert (
        decode_civilization_event_batch(encode_civilization_event_batch(batch))
        == batch
    )


@pytest.mark.asyncio
async def test_spooled_civilization_recorder_source_parity(tmp_path: Path) -> None:
    from experiments.civilization_capture import CivilizationEvidenceRecorder
    from simulation.civilization_capture import (
        CivilizationCaptureOptions,
        project_civilization_events,
    )
    from tests.unit.test_civilization_publication import _frame, _inventory

    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, cadence=1),
        spool=create_evidence_spool(tmp_path),
    )
    frames = (_frame(0, inventories=(_inventory("agent-a"),)),)
    batches = (
        project_civilization_events(
            "run-capture",
            0,
            (),
            expected_count=0,
            source="committed_result",
        ),
    )
    for batch in batches:
        assert recorder.capture_events(batch)
        assert recorder.capture_events(batch)
    for frame in frames:
        assert recorder.capture_boundary(frame)
        assert recorder.capture_boundary(frame)
    source = recorder.source()
    assert tuple(source.iter_boundaries()) == frames
    assert tuple(source.iter_event_batches()) == batches
    assert source.read_boundary(0) == frames[0]
    assert source.read_event_batch(0) == batches[0]
    assert recorder.boundaries == frames
    assert recorder.event_batches == batches
    assert recorder._boundaries == {}
    assert recorder._batches == {}


def test_source_backed_publication_matches_legacy_without_history_tuple() -> None:
    from experiments.civilization_publication import (
        CivilizationCapturedHistory,
        compose_civilization_boundary,
        compose_civilization_boundary_from_source,
    )
    from experiments.evidence_sources import MemoryCivilizationHistorySource
    from tests.unit.test_civilization_publication import _frame, _inventory

    frame = _frame(0, inventories=(_inventory("agent-a"),))
    legacy = compose_civilization_boundary(
        CivilizationCapturedHistory("run-capture", "world-capture", (frame,), ()),
        0,
    )

    inner = MemoryCivilizationHistorySource(
        "run-capture",
        "world-capture",
        (frame,),
        (),
        EvidenceSpoolStatus(
            active=True,
            failed=False,
            sealed=False,
            truncated=False,
            failure_code=None,
            record_count=1,
            byte_count=0,
            first_boundary=0,
            last_boundary=0,
        ),
    )

    class SourceWithoutHistoryAccessor:
        run_id = inner.run_id
        world_id = inner.world_id
        status = inner.status

        def boundary_ticks(self):
            return inner.boundary_ticks()

        def event_ticks(self):
            return inner.event_ticks()

        def iter_boundaries(self, *, after_boundary=None):
            return inner.iter_boundaries(after_boundary=after_boundary)

        def read_boundary(self, tick):
            return inner.read_boundary(tick)

        def iter_event_batches(self, *, after_tick=None, through_tick=None):
            return inner.iter_event_batches(
                after_tick=after_tick, through_tick=through_tick
            )

        def read_event_batch(self, tick):
            return inner.read_event_batch(tick)

    source = SourceWithoutHistoryAccessor()
    assert compose_civilization_boundary_from_source(source, 0) == legacy


def test_capture_off_never_touches_spool() -> None:
    from experiments.civilization_capture import CivilizationEvidenceRecorder
    from simulation.civilization_capture import CivilizationCaptureOptions

    class ExplodingSpool:
        def __getattr__(self, name):
            raise AssertionError(f"spool must not be touched: {name}")

    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=False), spool=ExplodingSpool()
    )
    assert recorder.capture_events(object()) is False  # type: ignore[arg-type]
    assert recorder.source().boundary_ticks() == ()
