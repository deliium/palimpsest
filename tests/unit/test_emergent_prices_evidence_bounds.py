"""Property bounds: no ratio without one homogeneous kind per side."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.emergent_prices_contract import PricePairing
from analysis.emergent_prices_events import price_evidence_rows_from_events
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit

KINDS = st.sampled_from(["food", "water", "tool"])


@given(
    st.lists(KINDS, min_size=1, max_size=4),
    st.lists(KINDS, min_size=1, max_size=4),
)
@settings(max_examples=100)
def test_no_ratio_without_homogeneous_distinct_sides(
    give_kinds: list[str], take_kinds: list[str]
) -> None:
    harvest = price_evidence_rows_from_events(
        [
            completed(
                "event-1",
                give_kinds=tuple(give_kinds),
                take_kinds=tuple(take_kinds),
            )
        ]
    )
    for row in harvest.exchanges:
        if row.ratio_milli is not None:
            assert row.pairing is PricePairing.PAIRED
            assert len(set(give_kinds)) == 1
            assert len(set(take_kinds)) == 1
            assert give_kinds[0] != take_kinds[0]
        if row.pairing is not PricePairing.PAIRED:
            assert row.ratio_milli is None
