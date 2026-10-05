"""Unit tests for deterministic lifecycle stage resolution."""

from __future__ import annotations

import logging

import pytest

from world.lifecycle import (
    DependencyStatus,
    LifecycleStageId,
    LifecycleStageThreshold,
    resolve_dependency_status,
    resolve_lifecycle_stage,
)

_LOG = logging.getLogger("tests.lifecycle_stage_resolution")

_INFANT = LifecycleStageId("infant")
_JUVENILE = LifecycleStageId("juvenile")
_ADULT = LifecycleStageId("adult")
_THRESHOLDS = (
    LifecycleStageThreshold(_INFANT, 2),
    LifecycleStageThreshold(_JUVENILE, 5),
    LifecycleStageThreshold(_ADULT, 20),
)
_ORDER = (_INFANT, _JUVENILE, _ADULT)


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (0, _INFANT),
        (2, _INFANT),
        (3, _JUVENILE),
        (5, _JUVENILE),
        (6, _ADULT),
        (20, _ADULT),
    ],
)
def test_resolve_lifecycle_stage_inclusive_boundaries(
    age: int, expected: LifecycleStageId
) -> None:
    _LOG.debug("case_id=stage_boundary age=%s", age)
    assert resolve_lifecycle_stage(age, _THRESHOLDS) == expected


def test_resolve_lifecycle_stage_uncovered_age() -> None:
    _LOG.debug("case_id=stage_uncovered")
    with pytest.raises(ValueError, match="lifecycle_stage_uncovered"):
        resolve_lifecycle_stage(21, _THRESHOLDS)


def test_resolve_lifecycle_stage_rejects_non_increasing() -> None:
    _LOG.debug("case_id=stage_threshold_order")
    bad = (
        LifecycleStageThreshold(_INFANT, 5),
        LifecycleStageThreshold(_JUVENILE, 5),
    )
    with pytest.raises(ValueError, match="lifecycle_stage_threshold_order"):
        resolve_lifecycle_stage(0, bad)


def test_resolve_lifecycle_stage_rejects_duplicate_stage() -> None:
    _LOG.debug("case_id=stage_id_duplicate")
    bad = (
        LifecycleStageThreshold(_INFANT, 2),
        LifecycleStageThreshold(_INFANT, 5),
    )
    with pytest.raises(ValueError, match="lifecycle_stage_id_duplicate"):
        resolve_lifecycle_stage(0, bad)


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (_INFANT, DependencyStatus.DEPENDENT),
        (_JUVENILE, DependencyStatus.INDEPENDENT),
        (_ADULT, DependencyStatus.INDEPENDENT),
    ],
)
def test_resolve_dependency_status_at_or_above_independent(
    stage: LifecycleStageId, expected: DependencyStatus
) -> None:
    _LOG.debug("case_id=dependency stage=%s", stage.value)
    assert (
        resolve_dependency_status(
            stage,
            _JUVENILE,
            stage_order=_ORDER,
        )
        is expected
    )


def test_resolve_dependency_status_unknown_stage() -> None:
    _LOG.debug("case_id=dependency_unknown_stage")
    with pytest.raises(ValueError, match="lifecycle_stage_unknown"):
        resolve_dependency_status(
            LifecycleStageId("elder"),
            _JUVENILE,
            stage_order=_ORDER,
        )
