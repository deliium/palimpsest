"""Deterministic byte-bounded organization row paging."""

from __future__ import annotations

import pytest

from simulation.organization_models import MAX_PAGE_ROWS, OrganizationArtifactError
from simulation.organization_paging import (
    OrganizationRowSelection,
    row_encoded_bytes,
    select_organization_rows,
)
from tests.unit.organization_artifact_helpers import example_snapshot

pytestmark = pytest.mark.unit


def _rows():
    snapshot = example_snapshot()
    return tuple(snapshot.candidates) * 3


def test_selection_respects_row_and_byte_budgets() -> None:
    rows = _rows()
    selection = select_organization_rows(rows, offset=0, limit=2, max_bytes=1_000_000)
    assert isinstance(selection, OrganizationRowSelection)
    assert len(selection.rows) == 2
    assert selection.next_offset == 2
    assert selection.truncated is True
    assert selection.encoded_bytes == sum(row_encoded_bytes(row) for row in rows[:2])


def test_byte_budget_stops_before_splitting_a_row() -> None:
    rows = _rows()
    first_size = row_encoded_bytes(rows[0])
    selection = select_organization_rows(rows, offset=0, limit=10, max_bytes=first_size)
    assert len(selection.rows) == 1
    assert selection.encoded_bytes == first_size


def test_offset_and_limit_are_validated() -> None:
    rows = _rows()
    with pytest.raises(OrganizationArtifactError):
        select_organization_rows(rows, offset=-1, limit=1, max_bytes=10)
    with pytest.raises(OrganizationArtifactError):
        select_organization_rows(rows, offset=0, limit=0, max_bytes=10)
    with pytest.raises(OrganizationArtifactError):
        select_organization_rows(rows, offset=0, limit=MAX_PAGE_ROWS + 1, max_bytes=10)
    with pytest.raises(OrganizationArtifactError):
        select_organization_rows(rows, offset=99, limit=1, max_bytes=10)


def test_last_page_is_not_truncated() -> None:
    rows = _rows()
    selection = select_organization_rows(
        rows, offset=len(rows) - 1, limit=5, max_bytes=1_000_000
    )
    assert len(selection.rows) == 1
    assert selection.truncated is False
