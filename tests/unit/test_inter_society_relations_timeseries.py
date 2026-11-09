"""ISR window series and vectorial comparison."""

from __future__ import annotations

from typing import Any, cast

import pytest

from analysis.inter_society_relations_contract import (
    INTER_SOCIETY_RELATION_WINDOW_TICKS,
    InterSocietyRelationsError,
)
from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
    harvest_inter_society_relations,
)
from analysis.inter_society_relations_evidence import InterSocietyEvidenceInputs
from analysis.inter_society_relations_timeseries import (
    build_pair_window_series,
    compare_inter_society_pairs,
    compare_inter_society_windows,
    window_index_for_tick,
)
from analysis.macro_society_contract import MacroSocietyLane, derive_macro_society_id

pytestmark = pytest.mark.unit


def _msoc(label: str, *, tick: int = 0) -> str:
    return derive_macro_society_id(
        creation_tick=tick,
        founding_member_ids=tuple(f"{label}-p{i}" for i in range(1, 5)),
        lane_signature=(MacroSocietyLane.MIGRATION.value,),
    )


def _pair(*, tick: int, exchange: int) -> Any:
    left = _msoc("l", tick=0)
    right = _msoc("r", tick=1)
    analysis = harvest_inter_society_relations(
        [
            InterSocietyMacroCandidate(
                society_id=left,
                member_ids=tuple(f"l-p{i}" for i in range(1, 5)),
                window_tick=tick,
            ),
            InterSocietyMacroCandidate(
                society_id=right,
                member_ids=tuple(f"r-p{i}" for i in range(1, 5)),
                window_tick=tick,
            ),
        ],
        evidence_by_pair={
            cast(tuple[str, str], tuple(sorted((left, right)))): (
                InterSocietyEvidenceInputs(exchange_event_count=exchange)
            )
        },
    )
    return analysis.pairs[0]


def test_window_ticks_match_civilization_flow() -> None:
    assert INTER_SOCIETY_RELATION_WINDOW_TICKS == 32
    assert window_index_for_tick(0) == 0
    assert window_index_for_tick(31) == 0
    assert window_index_for_tick(32) == 1


def test_three_window_series_deterministic() -> None:
    pairs = [
        _pair(tick=0, exchange=1),
        _pair(tick=32, exchange=2),
        _pair(tick=64, exchange=3),
    ]
    series = build_pair_window_series(pairs)
    assert len(series) == 1
    assert len(series[0].points) == 3
    assert [point.window_index for point in series[0].points] == [0, 1, 2]


def test_compare_pairs_vectorial_no_composite() -> None:
    left = _pair(tick=0, exchange=1)
    right = _pair(tick=32, exchange=4)
    view = compare_inter_society_pairs(left, right)
    exchange = next(item for item in view.domain_deltas if item[0] == "exchange")
    assert exchange[1] == 3
    payload_keys = {item[0] for item in view.domain_deltas}
    assert "score" not in payload_keys
    assert len(view.domain_deltas) == 8


def test_compare_windows_and_mixed_absent() -> None:
    left = _pair(tick=0, exchange=1)
    right_society_l = _msoc("l")
    right_society_r = _msoc("r", tick=1)
    right = harvest_inter_society_relations(
        [
            InterSocietyMacroCandidate(
                society_id=right_society_l,
                member_ids=tuple(f"l-p{i}" for i in range(1, 5)),
                window_tick=32,
            ),
            InterSocietyMacroCandidate(
                society_id=right_society_r,
                member_ids=tuple(f"r-p{i}" for i in range(1, 5)),
                window_tick=32,
            ),
        ],
        evidence_by_pair={
            cast(tuple[str, str], tuple(sorted((right_society_l, right_society_r)))): (
                InterSocietyEvidenceInputs()
            )
        },
    ).pairs[0]
    series = build_pair_window_series([left, right])
    view = compare_inter_society_windows(series[0].points[0], series[0].points[1])
    exchange = next(item for item in view.domain_deltas if item[0] == "exchange")
    assert exchange[2] == "present"
    assert exchange[3] in {"absent", "partial"}


def test_comparison_rejects_non_candidates() -> None:
    with pytest.raises(
        InterSocietyRelationsError, match="inter_society_relations_comparison_invalid"
    ):
        compare_inter_society_pairs(object(), object())  # type: ignore[arg-type]
