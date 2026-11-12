"""Purpose-bound paging for credit snapshot rows."""

from __future__ import annotations

import pytest

from simulation.credit_relationships_paging import (
    CREDIT_RELATIONSHIPS_PAGE_DEFAULT,
    CREDIT_RELATIONSHIPS_PAGE_MAX,
    page_credit_relationships,
)
from tests.unit.credit_relationships_snapshot_helpers import (
    alignment,
    claim,
    counterparty,
    distribution,
    performance,
    relationship,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("purpose", "row"),
    (
        ("relationships", relationship()),
        ("claims", claim()),
        ("performances", performance()),
        ("distributions", distribution()),
        ("counterparties", counterparty()),
        ("alignment", alignment()),
    ),
)
def test_each_purpose_pages_its_own_rows(purpose: str, row: object) -> None:
    assert page_credit_relationships([row], purpose=purpose) == (row,)


def test_default_and_max_limits() -> None:
    assert CREDIT_RELATIONSHIPS_PAGE_DEFAULT == 100
    assert CREDIT_RELATIONSHIPS_PAGE_MAX == 500
    rows = tuple(
        relationship(relationship_id=f"credo-{index:016x}")
        for index in range(3)
    )
    assert len(page_credit_relationships(rows, purpose="relationships")) == 3
    with pytest.raises(ValueError):
        page_credit_relationships(
            rows, purpose="relationships", limit=CREDIT_RELATIONSHIPS_PAGE_MAX + 1
        )


def test_window_filter_and_after_key() -> None:
    from dataclasses import replace

    first = relationship()
    second = replace(
        relationship(relationship_id="credo-0000000000000002"),
        window_index=1,
    )
    rows = (first, second)
    assert page_credit_relationships(
        rows, purpose="relationships", window_index=0
    ) == (first,)
    assert page_credit_relationships(
        rows,
        purpose="relationships",
        after_key=(0, first.relationship_id),
    ) == (second,)


def test_invalid_purpose_limit_and_window_are_rejected() -> None:
    rows = (relationship(),)
    with pytest.raises(ValueError):
        page_credit_relationships(rows, purpose="unknown")
    with pytest.raises(ValueError):
        page_credit_relationships(rows, purpose="relationships", limit=0)
    with pytest.raises(ValueError):
        page_credit_relationships(
            rows, purpose="relationships", window_index=512
        )


def test_wrong_row_type_is_rejected() -> None:
    with pytest.raises(ValueError):
        page_credit_relationships([claim()], purpose="relationships")
