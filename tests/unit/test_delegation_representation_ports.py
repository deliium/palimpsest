"""V4-09 representation paging, ports, and digest-bound cursors."""

from __future__ import annotations

import pytest

from simulation.delegation_representation_codec import (
    finalize_delegation_representation_snapshot,
)
from simulation.delegation_representation_models import (
    DelegationRepresentationMandateRow,
    DelegationRepresentationSnapshot,
    DelegationRepresentationSummaryRow,
)
from simulation.delegation_representation_paging import (
    select_representation_candidates,
    select_representation_lineage,
    select_representation_mandates,
    select_representation_positions,
    select_representation_revocations,
)
from simulation.delegation_representation_ports import (
    DELEGATION_REPRESENTATION_CURSOR_PURPOSES,
    DelegationRepresentationCursor,
    DelegationRepresentationPortError,
    bounded_detail_rows,
    delegation_representation_cursor_matches,
    delegation_representation_query_fingerprint,
)

pytestmark = pytest.mark.unit

_OWNER = "a" * 16
_REP = "b" * 16
_PRINCIPAL = "c" * 16
_RUN = "run-representation-ports"


def _mandate(index: int) -> DelegationRepresentationMandateRow:
    return DelegationRepresentationMandateRow(
        mandate_id="rmd-" + f"{index:016x}",
        owner_token=_OWNER,
        principal_kind="agent",
        principal_token=_PRINCIPAL,
        representative_token=_REP,
        scope_kind="speak_for",
        scope_subject_token="border",
        duration_kind="until_revoked",
        start_tick=index,
        end_tick=None,
        provenance="self_declared",
        status="claimed",
        recognition_basis="none",
        support_roots=0,
        opposition_roots=0,
        confidence_band="mid",
        coverage="complete",
    )


def _snapshot(count: int = 5) -> DelegationRepresentationSnapshot:
    mandates = tuple(_mandate(index) for index in range(count))
    summary = DelegationRepresentationSummaryRow(
        mandate_count=count,
        owner_count=1 if count else 0,
    )
    return finalize_delegation_representation_snapshot(
        DelegationRepresentationSnapshot(
            run_id=_RUN,
            generated_tick=5,
            created_from="d" * 64,
            mandates=mandates,
            summary=summary,
        )
    )


def test_all_selectors_page_deterministically() -> None:
    snapshot = _snapshot()
    selectors = (
        select_representation_mandates,
        select_representation_candidates,
        select_representation_positions,
        select_representation_revocations,
        select_representation_lineage,
    )
    for selector in selectors:
        first = selector(snapshot, cursor_offset=0, limit=2)
        second = selector(snapshot, cursor_offset=0, limit=2)
        assert first == second
        assert first.offset == 0
        assert len(first.rows) <= 2


def test_limit_clamping_and_next_offset() -> None:
    snapshot = _snapshot(5)
    page = select_representation_mandates(snapshot, cursor_offset=0, limit=10_000)
    assert len(page.rows) == 5
    assert page.next_offset is None
    assert page.truncated is False

    first = select_representation_mandates(snapshot, cursor_offset=0, limit=2)
    second = select_representation_mandates(
        snapshot, cursor_offset=first.next_offset or 0, limit=2
    )
    assert first.next_offset == 2
    assert second.rows[0] == snapshot.mandates[2]


def test_six_cursor_purposes_are_exact() -> None:
    assert DELEGATION_REPRESENTATION_CURSOR_PURPOSES == (
        "summary",
        "mandates",
        "mandate",
        "positions",
        "revocations",
        "lineage",
    )


def test_fingerprint_changes_with_each_field() -> None:
    base = delegation_representation_query_fingerprint(
        purpose="mandates",
        run_id=_RUN,
        publication_id="drep-pub-" + "1" * 16,
        snapshot_digest="d" * 64,
        filters=(("candidate_id", "rep-" + "1" * 16),),
    )
    variants = {
        delegation_representation_query_fingerprint(
            purpose="positions",
            run_id=_RUN,
            publication_id="drep-pub-" + "1" * 16,
            snapshot_digest="d" * 64,
            filters=(("candidate_id", "rep-" + "1" * 16),),
        ),
        delegation_representation_query_fingerprint(
            purpose="mandates",
            run_id="other-run",
            publication_id="drep-pub-" + "1" * 16,
            snapshot_digest="d" * 64,
            filters=(("candidate_id", "rep-" + "1" * 16),),
        ),
        delegation_representation_query_fingerprint(
            purpose="mandates",
            run_id=_RUN,
            publication_id="drep-pub-" + "2" * 16,
            snapshot_digest="d" * 64,
            filters=(("candidate_id", "rep-" + "1" * 16),),
        ),
        delegation_representation_query_fingerprint(
            purpose="mandates",
            run_id=_RUN,
            publication_id="drep-pub-" + "1" * 16,
            snapshot_digest="e" * 64,
            filters=(("candidate_id", "rep-" + "1" * 16),),
        ),
        delegation_representation_query_fingerprint(
            purpose="mandates",
            run_id=_RUN,
            publication_id="drep-pub-" + "1" * 16,
            snapshot_digest="d" * 64,
            filters=(),
        ),
    }
    assert len(variants | {base}) == 6


def test_cursor_matching_covers_run_publication_digest_and_fingerprint() -> None:
    fingerprint = delegation_representation_query_fingerprint(
        purpose="summary",
        run_id=_RUN,
        publication_id="drep-pub-" + "1" * 16,
        snapshot_digest="d" * 64,
    )
    cursor = DelegationRepresentationCursor(
        purpose="summary",
        run_id=_RUN,
        publication_id="drep-pub-" + "1" * 16,
        snapshot_digest="d" * 64,
        offset=2,
        query_fingerprint=fingerprint,
    )
    assert delegation_representation_cursor_matches(
        cursor,
        run_id=_RUN,
        publication_id="drep-pub-" + "1" * 16,
        snapshot_digest="d" * 64,
        fingerprint=fingerprint,
    )
    assert not delegation_representation_cursor_matches(
        cursor,
        run_id="other",
        publication_id="drep-pub-" + "1" * 16,
        snapshot_digest="d" * 64,
        fingerprint=fingerprint,
    )
    with pytest.raises(DelegationRepresentationPortError):
        DelegationRepresentationCursor(
            purpose="unknown",
            run_id=_RUN,
            publication_id="drep-pub-" + "1" * 16,
            snapshot_digest="d" * 64,
            offset=0,
            query_fingerprint=fingerprint,
        )


def test_detail_rows_are_bounded() -> None:
    rows, truncated = bounded_detail_rows(tuple(range(600)), maximum=500)
    assert len(rows) == 500
    assert truncated is True
