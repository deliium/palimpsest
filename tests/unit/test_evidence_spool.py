"""Append-only filesystem evidence spool contracts."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from experiments.persistence import EvidenceSpoolStatus
from persistence.evidence_spool_filesystem import (
    EvidenceSpoolConflict,
    EvidenceSpoolError,
    EvidenceSpoolFull,
    EvidenceSpoolSealed,
    create_evidence_spool,
)
from simulation.cultural_evidence import CulturalBoundaryExport

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
    assert spool.iter_lane(lane="cultural", after_boundary=None, limit=10) == (
        b"one",
        b"two",
        b"three",
    )
    assert spool.iter_lane(lane="cultural", after_boundary=1, limit=1) == (b"two",)
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
        spool.append(lane="cultural", boundary_tick=2, identity="b", payload=b"1234")
    status = spool.seal()
    assert status.sealed is True
    with pytest.raises(EvidenceSpoolSealed):
        spool.append(lane="cultural", boundary_tick=3, identity="c", payload=b"x")


def test_restart_reads_committed_records(tmp_path: Path) -> None:
    first = create_evidence_spool(tmp_path)
    first.append(lane="cultural", boundary_tick=1, identity="a", payload=b"alpha")
    second = create_evidence_spool(tmp_path)
    assert second.get(lane="cultural", identity="a") == b"alpha"
    assert second.iter_lane(lane="cultural", after_boundary=None, limit=10) == (
        b"alpha",
    )


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


def _cultural_frame(tick: int) -> CulturalBoundaryExport:
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
        decode_civilization_boundary(encode_civilization_boundary(boundary)) == boundary
    )
    batch = project_civilization_events(
        "run-capture",
        4,
        (),
        expected_count=0,
        source="committed_result",
    )
    assert (
        decode_civilization_event_batch(encode_civilization_event_batch(batch)) == batch
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

        def boundary_ticks(self) -> Any:
            return inner.boundary_ticks()

        def event_ticks(self) -> Any:
            return inner.event_ticks()

        def iter_boundaries(self, *, after_boundary: int | None = None) -> Any:
            return inner.iter_boundaries(after_boundary=after_boundary)

        def read_boundary(self, tick: int) -> Any:
            return inner.read_boundary(tick)

        def iter_event_batches(
            self, *, after_tick: int | None = None, through_tick: int | None = None
        ) -> Any:
            return inner.iter_event_batches(
                after_tick=after_tick, through_tick=through_tick
            )

        def read_event_batch(self, tick: int) -> Any:
            return inner.read_event_batch(tick)

    source = SourceWithoutHistoryAccessor()
    assert compose_civilization_boundary_from_source(source, 0) == legacy


def test_capture_off_never_touches_spool() -> None:
    from experiments.civilization_capture import CivilizationEvidenceRecorder
    from simulation.civilization_capture import CivilizationCaptureOptions

    class ExplodingSpool:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"spool must not be touched: {name}")

    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=False), spool=ExplodingSpool()
    )
    assert recorder.capture_events(object()) is False  # type: ignore[arg-type]
    assert recorder.source().boundary_ticks() == ()


@pytest.mark.parametrize("stage", ["identity", "boundary", "state"])
def test_interrupted_append_is_hidden_and_retry_keeps_old_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    import persistence.evidence_spool_filesystem as module

    spool = create_evidence_spool(tmp_path)
    spool.append(lane="cultural", boundary_tick=1, identity="old", payload=b"old")
    write = module._atomic_write

    class Interrupted(BaseException):
        pass

    def interrupt(path: Path, payload: bytes) -> None:
        if (
            (stage == "identity" and path.parent.name == "identity")
            or (stage == "boundary" and path.parent.name == "boundaries")
            or (stage == "state" and path.name == "state.json")
        ):
            raise Interrupted()
        write(path, payload)

    with monkeypatch.context() as patch:
        patch.setattr(module, "_atomic_write", interrupt)
        with pytest.raises(Interrupted):
            spool.append(
                lane="cultural", boundary_tick=2, identity="lost", payload=b"lost"
            )

    restarted = create_evidence_spool(tmp_path)
    assert restarted.get(lane="cultural", identity="lost") is None
    assert restarted.read_boundary(lane="cultural", boundary_tick=2) == ()
    assert restarted.status().record_count == 1
    assert restarted.get(lane="cultural", identity="old") == b"old"
    assert restarted.append(
        lane="cultural", boundary_tick=2, identity="retry", payload=b"retry"
    )
    assert restarted.iter_lane(lane="cultural", after_boundary=None, limit=10) == (
        b"old",
        b"retry",
    )
    assert restarted.get(lane="cultural", identity="lost") is None
    assert restarted.status().record_count == 2


def test_duplicate_identity_at_different_boundary_is_a_conflict(
    tmp_path: Path,
) -> None:
    spool = create_evidence_spool(tmp_path)
    spool.append(lane="cultural", boundary_tick=1, identity="one", payload=b"same")
    with pytest.raises(EvidenceSpoolConflict):
        spool.append(lane="cultural", boundary_tick=2, identity="one", payload=b"same")


def test_spooled_cultural_duplicate_does_not_consume_logical_quota(
    tmp_path: Path,
) -> None:
    from experiments.cultural_evidence import CulturalEvidenceRecorder

    recorder = CulturalEvidenceRecorder(
        spool=create_evidence_spool(tmp_path), max_frames=1
    )
    frame = _cultural_frame(0)
    recorder.capture(frame)
    recorder.capture(frame)
    assert recorder.source().gaps == ()
    assert recorder.frame_count == 1


def test_spooled_cultural_io_failure_is_latched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from experiments.cultural_evidence import CulturalEvidenceRecorder
    from persistence.evidence_spool_filesystem import FilesystemEvidenceSpool

    spool = create_evidence_spool(tmp_path)
    recorder = CulturalEvidenceRecorder(spool=spool)

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("private disk details")

    monkeypatch.setattr(FilesystemEvidenceSpool, "append", fail)
    recorder.capture(_cultural_frame(0))
    assert recorder.source().capture_status.failed
    assert (
        recorder.source().capture_status.failure_code == "cultural_capture_spool_failed"
    )
    from simulation.cultural_evidence import CulturalCaptureStatus

    recorder.merge_capture_status(CulturalCaptureStatus(active=True, failed=False))
    assert recorder.source().capture_status.failed
    recorder.capture(_cultural_frame(1))
    assert recorder.frame_count == 0


def test_spooled_cultural_source_is_pinned_against_later_appends(
    tmp_path: Path,
) -> None:
    from experiments.cultural_evidence import CulturalEvidenceRecorder

    recorder = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path))
    empty = recorder.source()
    recorder.capture(_cultural_frame(0))
    pinned = recorder.source()
    recorder.capture(_cultural_frame(1))
    assert empty.boundary_ticks() == ()
    assert empty.read_boundary(0) is None
    assert pinned.boundary_ticks() == (0,)
    assert pinned.status.record_count == 1
    assert pinned.read_boundary(1) is None
    assert recorder.source().boundary_ticks() == (0, 1)


def test_spooled_cultural_source_rejects_backdated_new_frames(
    tmp_path: Path,
) -> None:
    from experiments.cultural_evidence import CulturalEvidenceRecorder

    recorder = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path))
    recorder.capture(_cultural_frame(2))
    source = recorder.source()
    with pytest.raises(ValueError, match="cultural_evidence_conflict"):
        recorder.capture(_cultural_frame(1))
    assert source.boundary_ticks() == (2,)


def test_spooled_civilization_source_is_pinned_and_duplicates_ignore_quota(
    tmp_path: Path,
) -> None:
    from experiments.civilization_capture import CivilizationEvidenceRecorder
    from simulation.civilization_capture import (
        CivilizationCaptureOptions,
        project_civilization_events,
    )
    from tests.unit.test_civilization_publication import _frame

    recorder = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, cadence=1, max_boundaries=2),
        spool=create_evidence_spool(tmp_path),
    )
    first = _frame(0)
    batch = project_civilization_events(
        "run-capture", 0, (), expected_count=0, source="committed_result"
    )
    assert recorder.capture_events(batch)
    assert recorder.capture_boundary(first)
    pinned = recorder.source()
    assert recorder.capture_boundary(_frame(1))
    assert recorder.capture_boundary(first)
    assert recorder.capture_events(
        project_civilization_events(
            "run-capture", 1, (), expected_count=0, source="committed_result"
        )
    )
    assert recorder.capture_events(batch)
    assert pinned.boundary_ticks() == (0,)
    assert pinned.event_ticks() == (0,)
    assert pinned.read_boundary(1) is None
    assert pinned.read_event_batch(1) is None
    assert pinned.status.record_count == 2
    assert recorder.source().boundary_ticks() == (0, 1)


def test_short_writes_preserve_complete_atomic_files_and_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    write = os.write

    def short_write(descriptor: int, payload: bytes) -> int:
        return write(descriptor, payload[:7])

    monkeypatch.setattr(os, "write", short_write)
    spool = create_evidence_spool(tmp_path)
    payload = b"test payload" * 50
    spool.append(lane="cultural", boundary_tick=1, identity="one", payload=payload)
    assert spool.get(lane="cultural", identity="one") == payload
    assert spool.seal().sealed
    assert create_evidence_spool(tmp_path).status().record_count == 1


def test_interruption_after_state_commit_keeps_committed_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import persistence.evidence_spool_filesystem as module

    write = module._atomic_write

    class Interrupted(BaseException):
        pass

    def interrupt_after_commit(path: Path, payload: bytes) -> None:
        write(path, payload)
        if path.name == "state.json":
            raise Interrupted()

    spool = create_evidence_spool(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(module, "_atomic_write", interrupt_after_commit)
        with pytest.raises(Interrupted):
            spool.append(
                lane="cultural", boundary_tick=0, identity="one", payload=b"one"
            )
    restarted = create_evidence_spool(tmp_path)
    assert restarted.get(lane="cultural", identity="one") == b"one"
    assert restarted.status().record_count == 1
    assert not restarted.append(
        lane="cultural", boundary_tick=0, identity="one", payload=b"one"
    )


def test_oversized_index_read_length_fails_before_allocating_payload(
    tmp_path: Path,
) -> None:
    import json

    spool = create_evidence_spool(tmp_path)
    spool.append(lane="cultural", boundary_tick=0, identity="one", payload=b"one")
    identity_root = tmp_path / "lanes" / "cultural" / "identity"
    index = next(identity_root.glob("*.json"))
    document = json.loads(index.read_bytes())
    document["entries"]["one"]["length"] = 2**60
    index.write_text(json.dumps(document))
    with pytest.raises(EvidenceSpoolError, match="evidence_spool_corrupt"):
        spool.get(lane="cultural", identity="one")


def _evidence_fixture_inputs() -> Any:
    from analysis.cultural_evolution_evidence import CulturalAnalysisWindow
    from experiments.cultural_evidence import cultural_evolution_inputs_from_capture
    from tests.unit.test_cultural_evolution_normalization import _frames

    return cultural_evolution_inputs_from_capture(
        _frames(),
        run_id="run-normalize",
        source_revision="rev-normalize",
        window=CulturalAnalysisWindow(end_boundary=1),
        parent_child_edges=(("teacher", "learner"),),
    )


def test_streamed_canonical_evidence_matches_legacy_bytes_and_digest() -> None:
    from experiments.cultural_evidence_serialization import (
        decode_cultural_evolution_evidence,
        encode_cultural_evolution_evidence,
        encode_cultural_evolution_evidence_streamed,
        evidence_digest,
        evidence_digest_from_inputs,
    )
    from simulation.cultural_evidence import CulturalCaptureStatus

    inputs = _evidence_fixture_inputs()
    status = CulturalCaptureStatus(active=True, failed=False)
    options = {"enabled": True, "max_frames": 10, "max_rows": 1000}
    fingerprint = "a" * 64
    legacy = encode_cultural_evolution_evidence(
        inputs,
        config_fingerprint=fingerprint,
        capture_options=options,
        capture_status=status,
    )
    streamed = encode_cultural_evolution_evidence_streamed(
        inputs,
        config_fingerprint=fingerprint,
        capture_options=options,
        capture_status=status,
    )
    assert streamed == legacy
    digest = evidence_digest(
        inputs,
        config_fingerprint=fingerprint,
        capture_options=options,
        capture_status=status,
    )
    assert (
        evidence_digest_from_inputs(
            inputs,
            config_fingerprint=fingerprint,
            capture_options=options,
            capture_status=status,
        )
        == digest
    )
    assert decode_cultural_evolution_evidence(streamed).digest == digest


def test_source_normalization_reopens_source_without_all_frames() -> None:
    from analysis.cultural_evolution_evidence import CulturalAnalysisWindow
    from experiments.cultural_evidence import cultural_evolution_inputs_from_source
    from simulation.cultural_evidence import CulturalBoundaryExport
    from tests.unit.test_cultural_evolution_normalization import _frames, _inputs

    frames = _frames()
    probe = {"calls": 0, "live": 0, "max_live": 0}

    class CountingSource:
        run_id = "run-normalize"
        source_revision = "rev-normalize"
        gaps: tuple[str, ...] = ()

        def iter_boundaries(
            self, *, after_boundary: int | None = None
        ) -> Iterator[CulturalBoundaryExport]:
            probe["calls"] += 1
            for frame in frames:
                if after_boundary is not None and frame.boundary_tick <= after_boundary:
                    continue
                probe["live"] += 1
                probe["max_live"] = max(probe["max_live"], probe["live"])
                try:
                    assert type(frame) is CulturalBoundaryExport
                    yield frame
                finally:
                    probe["live"] -= 1

    inputs = cultural_evolution_inputs_from_source(
        cast(Any, CountingSource()),
        run_id="run-normalize",
        source_revision="rev-normalize",
        window=CulturalAnalysisWindow(end_boundary=1),
        parent_child_edges=(("teacher", "learner"),),
    )
    assert inputs == _inputs()
    assert probe["calls"] >= 2
    assert probe["max_live"] == 1


def test_source_backed_arm_fields_publish_identical_artifact_bytes(
    tmp_path: Path,
) -> None:
    from experiments.cultural_evidence import (
        CulturalEvidenceRecorder,
        SourceBackedCulturalEvidence,
        build_cultural_arm_fields,
        materialize_cultural_evidence,
    )
    from experiments.cultural_evidence_serialization import (
        encode_cultural_evolution_evidence,
        write_cultural_evolution_evidence,
    )
    from experiments.cultural_metric_artifacts import (
        CulturalCaptureOptions,
        cultural_capture_policy,
        read_cultural_pair,
        write_cultural_pair,
    )
    from tests.unit.test_cultural_evolution_normalization import _frames

    recorder = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path / "spool"))
    for frame in _frames():
        recorder.capture(frame)
    options = CulturalCaptureOptions(enabled=True)
    fingerprint = "a" * 64
    fields = build_cultural_arm_fields(
        recorder,
        run_id="run-normalize",
        config_fingerprint=fingerprint,
        options=options,
        source_revision="rev-normalize",
        parent_child_edges=(("teacher", "learner"),),
    )
    evidence = fields["cultural_evolution_evidence"]
    assert type(evidence) is SourceBackedCulturalEvidence
    inputs = materialize_cultural_evidence(evidence)
    policy = cultural_capture_policy(options)
    legacy = encode_cultural_evolution_evidence(
        inputs,
        config_fingerprint=fingerprint,
        capture_options=policy,
        capture_status=evidence.capture_status,
    )

    chunks: list[int] = []

    class RecordingSink:
        def write(self, data: bytes) -> int:
            chunks.append(len(data))
            return len(data)

    digest = write_cultural_evolution_evidence(
        RecordingSink(),
        inputs,
        config_fingerprint=fingerprint,
        capture_options=policy,
        capture_status=evidence.capture_status,
    )
    assert digest == evidence.digest
    assert chunks and max(chunks) < len(legacy)

    root = tmp_path / "artifacts"

    def _writer(handle: Any) -> str:
        return write_cultural_evolution_evidence(
            handle,
            inputs,
            config_fingerprint=fingerprint,
            capture_options=policy,
            capture_status=evidence.capture_status,
        )

    write_cultural_pair(
        root,
        "cell-a",
        cell_metrics_bytes=b"metrics",
        evidence_writer=_writer,
    )
    pair = read_cultural_pair(root, "cell-a")
    assert pair is not None
    written, metrics = pair
    assert written == legacy
    assert metrics == b"metrics"


def test_materialize_cultural_evidence_enforces_explicit_batch_budget(
    tmp_path: Path,
) -> None:
    from experiments.cultural_evidence import (
        CulturalEvidenceBatchError,
        CulturalEvidenceRecorder,
        build_cultural_arm_fields,
        materialize_cultural_evidence,
    )
    from experiments.cultural_metric_artifacts import CulturalCaptureOptions

    recorder = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path / "spool"))
    for frame in _frames_for_budget():
        recorder.capture(frame)
    fields = build_cultural_arm_fields(
        recorder,
        run_id="run-spool",
        config_fingerprint="b" * 64,
        options=CulturalCaptureOptions(enabled=True),
        source_revision="rev-spool",
    )
    evidence = cast(Any, fields["cultural_evolution_evidence"])
    with pytest.raises(
        CulturalEvidenceBatchError, match="cultural_batch_budget_exceeded"
    ):
        materialize_cultural_evidence(evidence, max_boundaries=1)


def _frames_for_budget() -> tuple[CulturalBoundaryExport, ...]:
    from simulation.cultural_evidence import CulturalBoundaryExport

    return (
        CulturalBoundaryExport("run-spool", 0, ()),
        CulturalBoundaryExport("run-spool", 1, ()),
    )


def test_recorder_resume_reconstructs_logical_accounting_and_quota(
    tmp_path: Path,
) -> None:
    from experiments.cultural_evidence import CulturalEvidenceRecorder
    from simulation.cultural_evidence import CulturalBoundaryExport

    frames = _frames_for_resume()
    first = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path))
    for frame in frames:
        first.capture(frame)
    assert first.accounting.logical_frames == 2
    assert first.accounting.logical_rows == 3

    default_resume = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path))
    default_resume.capture(frames[1])
    assert default_resume.accounting.logical_frames == 2
    assert default_resume.accounting.logical_rows == 3
    default_resume.capture(CulturalBoundaryExport("run-normalize", 2, ()))
    assert default_resume.accounting.logical_frames == 3

    tight = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path), max_rows=2)
    tight.capture(CulturalBoundaryExport("run-normalize", 3, ()))
    assert tight.truncated is True
    assert tight.accounting.logical_frames == 3


def _frames_for_resume() -> tuple[CulturalBoundaryExport, ...]:
    from tests.unit.test_cultural_evolution_normalization import _frames

    return _frames()


def test_run_scoped_spool_factory_isolates_runs_and_capture_off_skips_it(
    tmp_path: Path,
) -> None:
    from experiments.civilization_capture import CivilizationEvidenceRecorder
    from experiments.cultural_evidence import CulturalEvidenceRecorder
    from simulation.civilization_capture import CivilizationCaptureOptions
    from simulation.cultural_evidence import CulturalBoundaryExport

    root = tmp_path / "spool-root"
    calls: list[str] = []

    def factory(run_id: str) -> Any:
        calls.append(run_id)
        return create_evidence_spool(root / run_id)

    first = CulturalEvidenceRecorder(spool=factory)
    first.capture(CulturalBoundaryExport("run-a", 0, ()))
    second = CulturalEvidenceRecorder(spool=factory)
    second.capture(CulturalBoundaryExport("run-b", 0, ()))
    assert calls == ["run-a", "run-b"]
    assert (root / "run-a").is_dir()
    assert (root / "run-b").is_dir()
    assert (root / "run-a").resolve() != (root / "run-b").resolve()

    def _explode(_run_id: str) -> Any:
        raise AssertionError("capture-off must not resolve a spool")

    off = CulturalEvidenceRecorder(spool=_explode)
    assert off.frame_count == 0
    assert off.source().boundary_ticks() == ()

    civilization = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=False), spool=_explode
    )
    assert civilization.capture_events(object()) is False  # type: ignore[arg-type]
    assert civilization.source().boundary_ticks() == ()


def test_recorder_seal_keeps_evidence_readable_and_latches_append(
    tmp_path: Path,
) -> None:
    from experiments.cultural_evidence import CulturalEvidenceRecorder
    from simulation.cultural_evidence import CulturalBoundaryExport

    spool = create_evidence_spool(tmp_path)
    recorder = CulturalEvidenceRecorder(spool=spool)
    frame = CulturalBoundaryExport("run-spool", 0, ())
    recorder.capture(frame)
    recorder.seal()
    assert spool.status().sealed is True
    assert recorder.source().read_boundary(0) == frame
    recorder.capture(CulturalBoundaryExport("run-spool", 1, ()))
    assert recorder.result().capture_status.failed is True
    assert recorder.accounting.logical_frames == 1


def test_spool_lane_tick_cache_is_reused_and_invalidated(tmp_path: Path) -> None:
    spool = create_evidence_spool(tmp_path)
    for tick in (2, 0, 1):
        spool.append(
            lane="cultural",
            boundary_tick=tick,
            identity=f"b{tick}",
            payload=str(tick).encode(),
        )
    assert spool.iter_lane(lane="cultural", after_boundary=None, limit=2) == (
        b"0",
        b"1",
    )
    assert spool._tick_cache["cultural"] == (0, 1, 2)
    assert spool.iter_lane(lane="cultural", after_boundary=1, limit=2) == (b"2",)
    spool.append(lane="cultural", boundary_tick=3, identity="b3", payload=b"3")
    assert "cultural" not in spool._tick_cache
    assert len(spool.iter_lane(lane="cultural", after_boundary=None, limit=10)) == 4


def test_civilization_recorder_resume_accounts_logical_rows(
    tmp_path: Path,
) -> None:
    from experiments.civilization_capture import CivilizationEvidenceRecorder
    from simulation.civilization_capture import (
        CivilizationCaptureOptions,
        project_civilization_events,
    )
    from tests.unit.test_civilization_publication import _frame, _inventory

    root = tmp_path / "civilization-spool"

    def factory(run_id: str) -> Any:
        return create_evidence_spool(root / run_id)

    first = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, cadence=1), spool=factory
    )
    batch = project_civilization_events(
        "run-capture", 0, (), expected_count=0, source="committed_result"
    )
    frame = _frame(0, inventories=(_inventory("agent-a"),))
    assert first.capture_events(batch)
    assert first.capture_boundary(frame)
    first_rows = first.accounting.logical_rows
    first_bytes = first.accounting.logical_bytes

    resumed = CivilizationEvidenceRecorder(
        CivilizationCaptureOptions(enabled=True, cadence=1), spool=factory
    )
    assert resumed.capture_events(batch)
    assert resumed.capture_boundary(frame)
    assert resumed.accounting.logical_rows == first_rows
    assert resumed.accounting.logical_bytes == first_bytes
    assert resumed.accounting.physical_records == 2
    assert resumed.accounting.spooled is True


def test_streamed_publication_peak_allocation_below_artifact_bytes() -> None:
    import tracemalloc

    from analysis.cultural_evolution_evidence import CulturalAnalysisWindow
    from experiments.cultural_evidence import cultural_evolution_inputs_from_capture
    from experiments.cultural_evidence_serialization import (
        encode_cultural_evolution_evidence,
        write_cultural_evolution_evidence,
    )
    from simulation.cultural_evidence import CulturalCaptureStatus

    frames = tuple(_cultural_frame(tick) for tick in range(150))
    inputs = cultural_evolution_inputs_from_capture(
        frames,
        run_id="run-spool",
        source_revision="rev-spool",
        window=CulturalAnalysisWindow(end_boundary=149),
    )
    status = CulturalCaptureStatus(active=True, failed=False)
    options = {"enabled": True, "max_frames": 1000, "max_rows": 100000}
    fingerprint = "c" * 64
    legacy = encode_cultural_evolution_evidence(
        inputs,
        config_fingerprint=fingerprint,
        capture_options=options,
        capture_status=status,
    )
    assert len(legacy) > 4096
    written = 0

    class CountingSink:
        def write(self, data: bytes) -> int:
            nonlocal written
            written += len(data)
            return len(data)

    tracemalloc.start()
    try:
        write_cultural_evolution_evidence(
            CountingSink(),
            inputs,
            config_fingerprint=fingerprint,
            capture_options=options,
            capture_status=status,
        )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert written == len(legacy)
    assert peak < len(legacy)


def test_streamed_artifact_limit_fails_without_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import experiments.cultural_metric_artifacts as module
    from experiments.cultural_evidence import (
        CulturalEvidenceRecorder,
        build_cultural_arm_fields,
        materialize_cultural_evidence,
    )
    from experiments.cultural_evidence_serialization import (
        CulturalEvidenceSerializationError,
        write_cultural_evolution_evidence,
    )
    from experiments.cultural_metric_artifacts import (
        CulturalCaptureOptions,
        cultural_capture_policy,
        write_cultural_pair,
    )

    recorder = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path / "spool"))
    for frame in _frames_for_resume():
        recorder.capture(frame)
    options = CulturalCaptureOptions(enabled=True)
    fields = build_cultural_arm_fields(
        recorder,
        run_id="run-normalize",
        config_fingerprint="d" * 64,
        options=options,
        source_revision="rev-normalize",
    )
    evidence = cast(Any, fields["cultural_evolution_evidence"])
    inputs = materialize_cultural_evidence(evidence)
    policy = cultural_capture_policy(options)
    monkeypatch.setattr(module, "MAX_CULTURAL_ARTIFACT_BYTES", 32)

    def _writer(handle: Any) -> str:
        return write_cultural_evolution_evidence(
            handle,
            inputs,
            config_fingerprint="d" * 64,
            capture_options=policy,
            capture_status=evidence.capture_status,
        )

    root = tmp_path / "limited"
    with pytest.raises(CulturalEvidenceSerializationError, match="too_large"):
        write_cultural_pair(
            root,
            "cell-a",
            cell_metrics_bytes=b"metrics",
            evidence_writer=_writer,
        )
    assert not (root / "cells" / "cell-a.cultural-evidence.json").exists()
    assert not (root / "cells" / "cell-a.cultural-metrics.json").exists()


def test_write_cultural_pair_rejects_ambiguous_evidence_source(
    tmp_path: Path,
) -> None:
    from experiments.cultural_metric_artifacts import (
        CulturalArtifactError,
        write_cultural_pair,
    )

    with pytest.raises(CulturalArtifactError, match="invalid_evidence_source"):
        write_cultural_pair(tmp_path, "cell-a", cell_metrics_bytes=b"m")
    with pytest.raises(CulturalArtifactError, match="invalid_evidence_source"):
        write_cultural_pair(
            tmp_path,
            "cell-a",
            cell_metrics_bytes=b"m",
            evidence_bytes=b"e",
            evidence_writer=lambda _handle: None,
        )


def test_interrupted_seal_leaves_committed_spool_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import persistence.evidence_spool_filesystem as module
    from experiments.cultural_evidence import CulturalEvidenceRecorder

    recorder = CulturalEvidenceRecorder(spool=create_evidence_spool(tmp_path))
    recorder.capture(_cultural_frame(0))
    write = module._atomic_write

    class Interrupted(BaseException):
        pass

    def interrupt(path: Path, payload: bytes) -> None:
        if path.name == "state.json":
            raise Interrupted()
        write(path, payload)

    with monkeypatch.context() as patch:
        patch.setattr(module, "_atomic_write", interrupt)
        with pytest.raises(Interrupted):
            recorder.seal()

    restarted = create_evidence_spool(tmp_path)
    assert restarted.status().sealed is False
    resumed = CulturalEvidenceRecorder(spool=restarted)
    assert resumed.source().boundary_ticks() == (0,)
    assert resumed.source().read_boundary(0) == _cultural_frame(0)
