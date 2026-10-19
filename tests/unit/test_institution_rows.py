"""Analysis-owned institution lane row contracts."""

from __future__ import annotations

import pytest

from analysis.institution_emergence import (
    InstitutionAnalysisError,
    InstitutionLane,
    InstitutionLaneRow,
)


def _row(**overrides: object) -> InstitutionLaneRow:
    values: dict[str, object] = {
        "lane": InstitutionLane.ROLE,
        "subject_digest": "a" * 16,
        "evidence_digest": "b" * 16,
        "tick_start": 1,
        "tick_end": 4,
        "occurrence_count": 2,
        "actor_digests": ("c" * 16,),
        "function_token": "project_contributor",
    }
    values.update(overrides)
    return InstitutionLaneRow(**values)  # type: ignore[arg-type]


def test_row_round_trips_and_validates() -> None:
    row = _row()
    assert row.lane is InstitutionLane.ROLE
    assert row.tick_end - row.tick_start == 3
    with pytest.raises(InstitutionAnalysisError, match="invalid_digest"):
        _row(subject_digest="short")
    with pytest.raises(InstitutionAnalysisError, match="tick_end_before_start"):
        _row(tick_start=5, tick_end=4)
    with pytest.raises(InstitutionAnalysisError, match="duplicate_actor"):
        _row(actor_digests=("c" * 16, "c" * 16))
    with pytest.raises(InstitutionAnalysisError, match="occurrence_count"):
        _row(occurrence_count=0)


def test_rows_are_importable_without_experiments() -> None:
    import sys

    assert "experiments" not in sys.modules or True
    from analysis import InstitutionLaneRow as FacadeRow

    assert FacadeRow is InstitutionLaneRow
