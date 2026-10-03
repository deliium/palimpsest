"""Phenomenon mapping and support_band rule tests."""

from __future__ import annotations

import dataclasses

from analysis.phenomenon_models import (
    PhenomenonId,
    PhenomenonIndicatorPanel,
    PhenomenonIndicatorReading,
    SupportBand,
)
from analysis.phenomenon_specifications import (
    SUPPORT_BAND_RULES,
    resolve_support_band,
    validate_phenomenon_mappings,
)


def test_mappings_cover_all_phenomena() -> None:
    validate_phenomenon_mappings()
    assert len(PhenomenonId) == 18
    assert SupportBand.ABSENT.value in SUPPORT_BAND_RULES


def test_support_band_rules() -> None:
    assert (
        resolve_support_band(
            present_count=0,
            meets_weak=0,
            meets_moderate=0,
            meets_strong=0,
            unary_allowed=True,
        )
        is SupportBand.ABSENT
    )
    assert (
        resolve_support_band(
            present_count=1,
            meets_weak=1,
            meets_moderate=0,
            meets_strong=0,
            unary_allowed=True,
        )
        is SupportBand.WEAK
    )
    assert (
        resolve_support_band(
            present_count=2,
            meets_weak=2,
            meets_moderate=1,
            meets_strong=0,
            unary_allowed=False,
        )
        is SupportBand.MODERATE
    )
    assert (
        resolve_support_band(
            present_count=2,
            meets_weak=2,
            meets_moderate=2,
            meets_strong=2,
            unary_allowed=False,
        )
        is SupportBand.STRONG
    )


def test_no_emergence_boolean_fields() -> None:
    forbidden = {
        "emerged",
        "culture_emerged",
        "norm_emerged",
        "society_formed",
        "detected",
    }
    for model in (PhenomenonIndicatorPanel, PhenomenonIndicatorReading):
        names = {field.name for field in dataclasses.fields(model)}
        assert names.isdisjoint(forbidden)
