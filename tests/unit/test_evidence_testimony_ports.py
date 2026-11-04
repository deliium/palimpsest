"""V4-08 evidence paging, detail bounds, and cursor binding."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.evidence_testimony_codec import finalize_evidence_testimony_snapshot
from simulation.evidence_testimony_models import (
    EvidenceCandidateRecord,
    EvidenceTestimonyArtifactError,
    EvidenceTestimonyCounts,
    EvidenceTestimonySnapshot,
    empty_evidence_testimony_snapshot,
)
from simulation.evidence_testimony_paging import (
    _select,
    select_evidence_candidates,
    select_evidence_lineage,
    select_evidence_sources,
)
from simulation.evidence_testimony_ports import (
    EVIDENCE_TESTIMONY_CURSOR_PURPOSES,
    MAX_CANDIDATE_DETAIL_ROWS,
    EvidenceTestimonyCursor,
    EvidenceTestimonyPortError,
    bounded_detail_rows,
    evidence_testimony_cursor_matches,
    evidence_testimony_query_fingerprint,
    require_known_evidence_candidate,
)

pytestmark = pytest.mark.unit


def _candidate(index: int) -> EvidenceCandidateRecord:
    return EvidenceCandidateRecord(
        candidate_id=f"evid-{index:016x}",
        subject_token=f"subject-{index}",
        source_kind_family="documentary",
        owner_tokens=("0" * 16,),
        item_count=1,
        source_count=1,
        testimony_count=0,
        contradiction_count=0,
        status="isolated",
        coverage="complete",
        first_tick=index,
        last_tick=index,
        creation_digest=f"{index:064x}",
    )


def _snapshot(count: int) -> EvidenceTestimonySnapshot:
    candidates = tuple(_candidate(index) for index in range(count))
    return finalize_evidence_testimony_snapshot(
        EvidenceTestimonySnapshot(
            run_id="run-1",
            generated_tick=1,
            candidates=candidates,
            counts=EvidenceTestimonyCounts(candidate_count=count),
        )
    )


def test_limit_clamps_and_next_offset_is_correct() -> None:
    snapshot = _snapshot(3)
    page = select_evidence_candidates(snapshot, offset=0, limit=5000)
    assert len(page.rows) == 3
    assert page.next_offset is None
    assert page.truncated is False

    first = select_evidence_candidates(snapshot, offset=0, limit=1)
    assert first.next_offset == 1
    assert first.truncated is True
    second = select_evidence_candidates(snapshot, offset=1, limit=1)
    assert second.next_offset == 2

    with pytest.raises(EvidenceTestimonyArtifactError):
        select_evidence_candidates(snapshot, offset=-1)


def test_single_row_over_byte_budget_fails() -> None:
    huge = "x" * (2 * 1024 * 1024 + 1)

    with pytest.raises(EvidenceTestimonyArtifactError) as error:
        _select((huge,), 0, 10)
    assert error.value.code == "evidence_testimony_size_limit"


def test_empty_tables_page_cleanly() -> None:
    snapshot = finalize_evidence_testimony_snapshot(
        empty_evidence_testimony_snapshot("run-empty", generated_tick=0)
    )
    assert select_evidence_sources(snapshot).rows == ()
    assert select_evidence_lineage(snapshot).rows == ()


def test_cursor_purposes_are_exactly_six() -> None:
    assert EVIDENCE_TESTIMONY_CURSOR_PURPOSES == (
        "summary",
        "candidates",
        "candidate",
        "sources",
        "contradictions",
        "lineage",
    )


def test_cursor_binds_run_publication_digest_purpose_and_filter() -> None:
    fingerprint = evidence_testimony_query_fingerprint(
        purpose="candidates",
        run_id="run-1",
        publication_id="evid-pub-0000000000000000",
        snapshot_digest="a" * 64,
        filters=(("status", "contested"),),
    )
    cursor = EvidenceTestimonyCursor(
        purpose="candidates",
        run_id="run-1",
        publication_id="evid-pub-0000000000000000",
        snapshot_digest="a" * 64,
        offset=0,
        query_fingerprint=fingerprint,
    )
    kwargs = {
        "purpose": "candidates",
        "run_id": "run-1",
        "publication_id": "evid-pub-0000000000000000",
        "snapshot_digest": "a" * 64,
        "query_fingerprint": fingerprint,
    }
    assert evidence_testimony_cursor_matches(cursor, **kwargs) is True
    assert (
        evidence_testimony_cursor_matches(cursor, **{**kwargs, "run_id": "run-2"})
        is False
    )
    assert (
        evidence_testimony_cursor_matches(cursor, **{**kwargs, "purpose": "sources"})
        is False
    )
    assert (
        evidence_testimony_cursor_matches(
            cursor, **{**kwargs, "query_fingerprint": "b" * 64}
        )
        is False
    )

    with pytest.raises(EvidenceTestimonyPortError):
        replace(cursor, purpose="unknown")
    with pytest.raises(EvidenceTestimonyPortError):
        replace(cursor, offset=-1)


def test_unknown_candidate_fails_and_detail_rows_are_bounded() -> None:
    snapshot = _snapshot(1)
    candidate = snapshot.candidates[0]
    assert (
        require_known_evidence_candidate(snapshot, candidate.candidate_id) is candidate
    )
    with pytest.raises(EvidenceTestimonyArtifactError) as error:
        require_known_evidence_candidate(snapshot, "evid-" + "9" * 16)
    assert error.value.code == "evidence_testimony_not_found"

    rows = tuple(range(MAX_CANDIDATE_DETAIL_ROWS + 10))
    bounded, truncated = bounded_detail_rows(rows)
    assert len(bounded) == MAX_CANDIDATE_DETAIL_ROWS
    assert truncated is True
    assert bounded_detail_rows(rows[:2]) == ((0, 1), False)
