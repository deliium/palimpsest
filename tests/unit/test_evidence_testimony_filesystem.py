"""V4-08 atomic filesystem store, quotas, and duplicate handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from experiments.evidence_testimony_harvest import (
    build_completed_run_evidence_harvest,
)
from experiments.evidence_testimony_publication import (
    build_evidence_testimony_harvest_result,
    publish_evidence_testimony_snapshot,
)
from persistence.evidence_testimony_filesystem import (
    FilesystemEvidenceTestimonyPublisher,
    FilesystemEvidenceTestimonyReader,
    create_evidence_testimony_publisher,
    create_evidence_testimony_reader,
)
from simulation.evidence_testimony_codec import encode_evidence_testimony_snapshot
from simulation.evidence_testimony_models import EvidenceTestimonyArtifactError
from simulation.evidence_testimony_ports import (
    EvidenceTestimonyPortError,
    EvidenceTestimonyPublication,
)
from tests.unit.evidence_testimony_helpers import make_parts

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _StopReason:
    value: str = "completed"


@dataclass(frozen=True)
class _RunnerResult:
    evidence_ledgers: tuple[object, ...]
    run_id: str = "run-evidence-fs"
    ticks_committed: int = 2


def _result(run_id: str = "run-evidence-fs", ticks: int = 2):
    harvest = build_completed_run_evidence_harvest(
        _RunnerResult((make_parts().ledger(),), run_id=run_id, ticks_committed=ticks)
    )
    return build_evidence_testimony_harvest_result(harvest)


def test_publish_then_read_summary_and_pages(tmp_path: Path) -> None:
    publisher = FilesystemEvidenceTestimonyPublisher(tmp_path / "store")
    result = _result()
    publish_evidence_testimony_snapshot(result, publisher)

    reader = FilesystemEvidenceTestimonyReader(tmp_path / "store")
    summary = reader.summary(run_id=result.snapshot.run_id)
    assert summary.publication_id == result.snapshot.publication_id
    assert summary.source_count == 1
    assert summary.schema_version == "evidence-testimony-snapshot-v1"

    candidates = reader.candidates(run_id=result.snapshot.run_id)
    assert candidates.rows
    detail = reader.candidate(
        run_id=result.snapshot.run_id,
        candidate_id=result.snapshot.candidates[0].candidate_id,
    )
    assert detail.candidate_id == result.snapshot.candidates[0].candidate_id
    assert reader.sources(run_id=result.snapshot.run_id).rows
    assert len(reader.contradictions(run_id=result.snapshot.run_id).rows) == 1
    assert len(reader.lineage(run_id=result.snapshot.run_id).rows) == 1

    with pytest.raises(EvidenceTestimonyPortError):
        reader.candidate(run_id=result.snapshot.run_id, candidate_id="evid-" + "9" * 16)


def test_same_bytes_are_idempotent_and_changed_bytes_fail(tmp_path: Path) -> None:
    store = tmp_path / "store"
    publisher = FilesystemEvidenceTestimonyPublisher(store)
    result = _result()
    publication = EvidenceTestimonyPublication(
        run_id=result.snapshot.run_id,
        publication_id=result.snapshot.publication_id,
        snapshot_digest=result.snapshot.snapshot_digest,
        payload=encode_evidence_testimony_snapshot(result.snapshot),
        generated_tick=result.snapshot.generated_tick,
    )
    publisher.publish(publication)
    publisher.publish(publication)

    stored = store / "publications" / f"{publication.publication_id}.json"
    stored.write_text("{}\n", encoding="utf-8")
    with pytest.raises(EvidenceTestimonyArtifactError) as error:
        publisher.publish(publication)
    assert error.value.code == "evidence_testimony_publication_exists"


def test_quotas_fail_closed(tmp_path: Path) -> None:
    store = tmp_path / "store"
    publisher = FilesystemEvidenceTestimonyPublisher(
        store, max_publications=1, max_bytes=10 * 1024 * 1024
    )
    publish_evidence_testimony_snapshot(_result("run-a", ticks=2), publisher)
    with pytest.raises(EvidenceTestimonyArtifactError) as error:
        publish_evidence_testimony_snapshot(_result("run-a", ticks=3), publisher)
    assert error.value.code == "evidence_testimony_size_limit"

    tiny = FilesystemEvidenceTestimonyPublisher(tmp_path / "tiny", max_bytes=1)
    with pytest.raises(EvidenceTestimonyArtifactError) as error:
        publish_evidence_testimony_snapshot(_result("run-c"), tiny)
    assert error.value.code == "evidence_testimony_size_limit"


def test_corrupted_publication_fails_digest_verification(tmp_path: Path) -> None:
    store = tmp_path / "store"
    result = _result()
    publish_evidence_testimony_snapshot(
        result, FilesystemEvidenceTestimonyPublisher(store)
    )
    stored = store / "publications" / f"{result.snapshot.publication_id}.json"
    stored.write_text('{"tampered":true}\n', encoding="utf-8")
    reader = FilesystemEvidenceTestimonyReader(store)
    with pytest.raises(EvidenceTestimonyPortError):
        reader.summary(run_id=result.snapshot.run_id)


def test_factories_return_none_without_a_root() -> None:
    assert create_evidence_testimony_publisher(None) is None
    assert create_evidence_testimony_reader(None) is None
