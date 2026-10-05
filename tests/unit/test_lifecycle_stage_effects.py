"""Unit tests for developmental stage capability effects."""

from __future__ import annotations

import logging

import pytest

from world.lifecycle import LifecycleStageId, LifecycleStageThreshold
from world.lifecycle_effects import (
    ContinuousLifecycleFactors,
    PASSTHROUGH_CONTINUOUS_FACTORS,
    StageCapabilityEffect,
    interpolate_continuous_factors,
    resolve_stage_effect,
    validate_stage_capability_effects_cover,
)

_LOG = logging.getLogger("tests.lifecycle_stage_effects")

_DEPENDENT = LifecycleStageId("dependent")
_LEARNING = LifecycleStageId("learning")
_INDEPENDENT = LifecycleStageId("independent")
_ELDER = LifecycleStageId("elder")

_THRESHOLDS = (
    LifecycleStageThreshold(_DEPENDENT, 2),
    LifecycleStageThreshold(_LEARNING, 5),
    LifecycleStageThreshold(_INDEPENDENT, 10),
    LifecycleStageThreshold(_ELDER, 20),
)

_EFFECTS = (
    StageCapabilityEffect(
        stage_id=_DEPENDENT,
        physical_capacity_factor=0.5,
        learning_rate_factor=0.8,
        fatigue_accrual_factor=1.2,
        denied_command_kinds=("attack", "harvest"),
    ),
    StageCapabilityEffect(
        stage_id=_LEARNING,
        physical_capacity_factor=0.8,
        learning_rate_factor=1.5,
        fatigue_accrual_factor=1.0,
        denied_command_kinds=("attack",),
    ),
    StageCapabilityEffect(
        stage_id=_INDEPENDENT,
        physical_capacity_factor=1.0,
        learning_rate_factor=1.0,
        fatigue_accrual_factor=1.0,
        denied_command_kinds=(),
    ),
    StageCapabilityEffect(
        stage_id=_ELDER,
        physical_capacity_factor=0.7,
        learning_rate_factor=0.9,
        fatigue_accrual_factor=1.3,
        denied_command_kinds=(),
    ),
)


def test_resolve_stage_effect_passthrough_when_absent() -> None:
    _LOG.debug("case_id=resolve_passthrough_absent")
    effect = resolve_stage_effect(_DEPENDENT, None)
    assert effect.continuous_factors == PASSTHROUGH_CONTINUOUS_FACTORS
    assert effect.denied_command_kinds == ()


def test_resolve_stage_effect_passthrough_when_empty() -> None:
    _LOG.debug("case_id=resolve_passthrough_empty")
    effect = resolve_stage_effect(_LEARNING, ())
    assert effect.physical_capacity_factor == 1.0
    assert effect.denied_command_kinds == ()


def test_resolve_stage_effect_lookup() -> None:
    _LOG.debug("case_id=resolve_lookup")
    effect = resolve_stage_effect(_DEPENDENT, _EFFECTS)
    assert effect.physical_capacity_factor == 0.5
    assert effect.denied_command_kinds == ("attack", "harvest")


def test_interpolate_disabled_holds_stage_constants() -> None:
    _LOG.debug("case_id=interpolate_disabled")
    factors = interpolate_continuous_factors(
        4, _THRESHOLDS, _EFFECTS, enabled=False
    )
    assert factors == ContinuousLifecycleFactors(
        physical_capacity_factor=0.8,
        learning_rate_factor=1.5,
        fatigue_accrual_factor=1.0,
    )


def test_interpolate_enabled_lerps_within_band() -> None:
    _LOG.debug("case_id=interpolate_lerp")
    # learning band: ages 3..5; at age 3 (band_start) t=0 → learning factors
    start = interpolate_continuous_factors(
        3, _THRESHOLDS, _EFFECTS, enabled=True
    )
    assert start.physical_capacity_factor == pytest.approx(0.8)
    # at age 5 (band_end) t=1 → independent factors
    end = interpolate_continuous_factors(
        5, _THRESHOLDS, _EFFECTS, enabled=True
    )
    assert end.physical_capacity_factor == pytest.approx(1.0)
    mid = interpolate_continuous_factors(
        4, _THRESHOLDS, _EFFECTS, enabled=True
    )
    assert mid.physical_capacity_factor == pytest.approx(0.9)


def test_interpolate_final_stage_flat() -> None:
    _LOG.debug("case_id=interpolate_final_flat")
    early = interpolate_continuous_factors(
        11, _THRESHOLDS, _EFFECTS, enabled=True
    )
    late = interpolate_continuous_factors(
        20, _THRESHOLDS, _EFFECTS, enabled=True
    )
    assert early == late
    assert early.physical_capacity_factor == 0.7


def test_denied_kinds_not_interpolated() -> None:
    _LOG.debug("case_id=denied_kinds_discrete")
    effect = resolve_stage_effect(_LEARNING, _EFFECTS)
    assert effect.denied_command_kinds == ("attack",)


def test_effects_cover_validation() -> None:
    _LOG.debug("case_id=effects_cover")
    ordered = validate_stage_capability_effects_cover(
        _EFFECTS, (_DEPENDENT, _LEARNING, _INDEPENDENT, _ELDER)
    )
    assert [item.stage_id for item in ordered] == [
        _DEPENDENT,
        _LEARNING,
        _INDEPENDENT,
        _ELDER,
    ]
    with pytest.raises(ValueError, match="lifecycle_effect_stage_cover"):
        validate_stage_capability_effects_cover(
            _EFFECTS[:2], (_DEPENDENT, _LEARNING, _INDEPENDENT, _ELDER)
        )


def test_factor_range_rejected() -> None:
    _LOG.debug("case_id=factor_range")
    with pytest.raises(ValueError, match="lifecycle_factor_range"):
        StageCapabilityEffect(
            stage_id=_DEPENDENT,
            physical_capacity_factor=0.0,
            learning_rate_factor=1.0,
            fatigue_accrual_factor=1.0,
            denied_command_kinds=(),
        )
    with pytest.raises(ValueError, match="lifecycle_factor_range"):
        StageCapabilityEffect(
            stage_id=_DEPENDENT,
            physical_capacity_factor=2.1,
            learning_rate_factor=1.0,
            fatigue_accrual_factor=1.0,
            denied_command_kinds=(),
        )
