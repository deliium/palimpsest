"""Objective developmental-stage capability effects (no social authority).

Effects scale ephemeral physical capacity, fatigue accrual, and skill growth
inside WorldEngine only. Stage ids remain opaque strings. Denied action kinds
are concrete ``AgentCommand.kind`` tokens from a closed allowlist — never
invented class tokens, leadership roles, or SelfModel writes.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from world.identifiers import require_exact_nonneg_int
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold

_LOGGER: Final[logging.Logger] = logging.getLogger("world.lifecycle_effects")

__all__ = [
    "ContinuousLifecycleFactors",
    "LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST",
    "PASSTHROUGH_CONTINUOUS_FACTORS",
    "StageCapabilityEffect",
    "interpolate_continuous_factors",
    "require_lifecycle_denied_command_kinds",
    "require_positive_factor_in_unit_two",
    "resolve_stage_effect",
    "validate_stage_capability_effects_cover",
]

# Concrete AgentCommand.kind values only. Teaching is a cognition mode, not a
# deny token. No social/authority kind families.
LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "attack",
        "harvest",
        "craft",
        "build",
        "repair",
        "flee",
    }
)

_FACTOR_MAX: Final[float] = 2.0
_FORBIDDEN_EFFECT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "authority",
        "leader",
        "social_rank",
        "respect",
        "role",
        "parent_id",
        "parent_ids",
        "child_id",
        "child_ids",
        "kinship",
        "heavy_labor",
        "long_travel",
        "teach",
        "combat_initiate",
    }
)


@dataclass(frozen=True, slots=True)
class ContinuousLifecycleFactors:
    """Interpolatable continuous stage factors (denied kinds stay discrete)."""

    physical_capacity_factor: float
    learning_rate_factor: float
    fatigue_accrual_factor: float


PASSTHROUGH_CONTINUOUS_FACTORS: Final[ContinuousLifecycleFactors] = (
    ContinuousLifecycleFactors(
        physical_capacity_factor=1.0,
        learning_rate_factor=1.0,
        fatigue_accrual_factor=1.0,
    )
)


def require_positive_factor_in_unit_two(name: str, value: object) -> float:
    """Accept a positive float in the closed range ``(0, 2]``."""
    if isinstance(value, bool) or type(value) is not float and type(value) is not int:
        raise TypeError(f"{name} must be a number (code=lifecycle_factor_type)")
    factor = float(value)
    if not (0.0 < factor <= _FACTOR_MAX):
        _LOGGER.error(
            "lifecycle_factor_out_of_range code=lifecycle_factor_range name=%s",
            name,
        )
        raise ValueError(
            f"{name} must be in (0, 2] (code=lifecycle_factor_range)"
        )
    return factor


def require_lifecycle_denied_command_kinds(
    value: object,
) -> tuple[str, ...]:
    """Validate and freeze denied ``AgentCommand.kind`` tokens."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(
            "denied_command_kinds must be a sequence "
            "(code=lifecycle_denied_command_kinds_type)"
        )
    kinds: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if type(item) is not str:
            raise TypeError(
                "denied_command_kinds entries must be str "
                f"(code=lifecycle_denied_command_kind_type index={index})"
            )
        if item in _FORBIDDEN_EFFECT_KEYS or item == "teach":
            _LOGGER.error(
                "lifecycle_denied_command_kind_forbidden code="
                "lifecycle_denied_command_kind_unknown kind=%s",
                item,
            )
            raise ValueError(
                "unknown denied_command_kind "
                f"{item!r} (code=lifecycle_denied_command_kind_unknown)"
            )
        if item not in LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST:
            _LOGGER.error(
                "lifecycle_denied_command_kind_unknown code="
                "lifecycle_denied_command_kind_unknown kind=%s",
                item,
            )
            raise ValueError(
                "unknown denied_command_kind "
                f"{item!r} (code=lifecycle_denied_command_kind_unknown)"
            )
        if item in seen:
            raise ValueError(
                "denied_command_kinds must be unique "
                f"(code=lifecycle_denied_command_kind_duplicate index={index})"
            )
        seen.add(item)
        kinds.append(item)
    _LOGGER.debug(
        "lifecycle_denied_command_kinds_validated count=%s",
        len(kinds),
    )
    return tuple(kinds)


@dataclass(frozen=True, slots=True)
class StageCapabilityEffect:
    """Per-stage objective capability effects (self-legality only)."""

    stage_id: LifecycleStageId
    physical_capacity_factor: float
    learning_rate_factor: float
    fatigue_accrual_factor: float
    denied_command_kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.stage_id) is not LifecycleStageId:
            raise TypeError(
                "StageCapabilityEffect.stage_id must be LifecycleStageId"
            )
        object.__setattr__(
            self,
            "physical_capacity_factor",
            require_positive_factor_in_unit_two(
                "physical_capacity_factor", self.physical_capacity_factor
            ),
        )
        object.__setattr__(
            self,
            "learning_rate_factor",
            require_positive_factor_in_unit_two(
                "learning_rate_factor", self.learning_rate_factor
            ),
        )
        object.__setattr__(
            self,
            "fatigue_accrual_factor",
            require_positive_factor_in_unit_two(
                "fatigue_accrual_factor", self.fatigue_accrual_factor
            ),
        )
        object.__setattr__(
            self,
            "denied_command_kinds",
            require_lifecycle_denied_command_kinds(self.denied_command_kinds),
        )

    @property
    def continuous_factors(self) -> ContinuousLifecycleFactors:
        return ContinuousLifecycleFactors(
            physical_capacity_factor=self.physical_capacity_factor,
            learning_rate_factor=self.learning_rate_factor,
            fatigue_accrual_factor=self.fatigue_accrual_factor,
        )


def _passthrough_effect(stage_id: LifecycleStageId) -> StageCapabilityEffect:
    return StageCapabilityEffect(
        stage_id=stage_id,
        physical_capacity_factor=1.0,
        learning_rate_factor=1.0,
        fatigue_accrual_factor=1.0,
        denied_command_kinds=(),
    )


def validate_stage_capability_effects_cover(
    effects: Sequence[StageCapabilityEffect],
    stage_order: Sequence[LifecycleStageId],
) -> tuple[StageCapabilityEffect, ...]:
    """Require an exact cover of configured stages when effects are present."""
    if isinstance(effects, (str, bytes)) or not isinstance(effects, Sequence):
        raise TypeError("stage_capability_effects must be a sequence")
    if isinstance(stage_order, (str, bytes)) or not isinstance(stage_order, Sequence):
        raise TypeError("stage_order must be a sequence")
    if len(effects) == 0:
        return ()
    expected = [item.value for item in stage_order]
    actual: list[str] = []
    seen: set[str] = set()
    frozen: list[StageCapabilityEffect] = []
    for index, effect in enumerate(effects):
        if type(effect) is not StageCapabilityEffect:
            raise TypeError(
                "stage_capability_effects entries must be StageCapabilityEffect"
            )
        key = effect.stage_id.value
        if key in seen:
            raise ValueError(
                "stage_capability_effects stage ids must be unique "
                f"(code=lifecycle_effect_stage_duplicate index={index})"
            )
        seen.add(key)
        actual.append(key)
        frozen.append(effect)
    if sorted(actual) != sorted(expected):
        _LOGGER.error(
            "lifecycle_effect_stage_cover_mismatch code="
            "lifecycle_effect_stage_cover expected=%s actual=%s",
            expected,
            actual,
        )
        raise ValueError(
            "stage_capability_effects must cover every configured stage "
            "exactly once (code=lifecycle_effect_stage_cover)"
        )
    # Preserve stage_order sequence rather than input order for stable resolve.
    by_id = {item.stage_id.value: item for item in frozen}
    ordered = tuple(by_id[stage.value] for stage in stage_order)
    _LOGGER.debug(
        "stage_capability_effects_validated count=%s",
        len(ordered),
    )
    return ordered


def resolve_stage_effect(
    stage: LifecycleStageId,
    effects: Sequence[StageCapabilityEffect] | Mapping[str, StageCapabilityEffect] | None,
) -> StageCapabilityEffect:
    """Return the effect for ``stage``, or passthrough when effects are absent."""
    if type(stage) is not LifecycleStageId:
        raise TypeError("stage must be LifecycleStageId")
    if effects is None:
        resolved = _passthrough_effect(stage)
        _LOGGER.debug(
            "resolve_stage_effect stage_id=%s age=- factors=passthrough "
            "denied_count=0",
            stage.value,
        )
        return resolved
    if isinstance(effects, Mapping):
        effect = effects.get(stage.value)
        if effect is None:
            resolved = _passthrough_effect(stage)
            _LOGGER.debug(
                "resolve_stage_effect stage_id=%s missing=map "
                "factors=passthrough denied_count=0",
                stage.value,
            )
            return resolved
        if type(effect) is not StageCapabilityEffect:
            raise TypeError("effects map values must be StageCapabilityEffect")
        _LOGGER.debug(
            "resolve_stage_effect stage_id=%s physical=%s learning=%s "
            "fatigue=%s denied_count=%s",
            stage.value,
            effect.physical_capacity_factor,
            effect.learning_rate_factor,
            effect.fatigue_accrual_factor,
            len(effect.denied_command_kinds),
        )
        return effect
    if isinstance(effects, (str, bytes)) or not isinstance(effects, Sequence):
        raise TypeError("effects must be a sequence, mapping, or None")
    if len(effects) == 0:
        resolved = _passthrough_effect(stage)
        _LOGGER.debug(
            "resolve_stage_effect stage_id=%s factors=passthrough denied_count=0",
            stage.value,
        )
        return resolved
    for effect in effects:
        if type(effect) is not StageCapabilityEffect:
            raise TypeError("effects entries must be StageCapabilityEffect")
        if effect.stage_id.value == stage.value:
            _LOGGER.debug(
                "resolve_stage_effect stage_id=%s physical=%s learning=%s "
                "fatigue=%s denied_count=%s",
                stage.value,
                effect.physical_capacity_factor,
                effect.learning_rate_factor,
                effect.fatigue_accrual_factor,
                len(effect.denied_command_kinds),
            )
            return effect
    resolved = _passthrough_effect(stage)
    _LOGGER.debug(
        "resolve_stage_effect stage_id=%s missing=list factors=passthrough "
        "denied_count=0",
        stage.value,
    )
    return resolved


def _effects_by_stage(
    effects: Sequence[StageCapabilityEffect] | None,
) -> dict[str, StageCapabilityEffect]:
    if effects is None or len(effects) == 0:
        return {}
    by_stage: dict[str, StageCapabilityEffect] = {}
    for effect in effects:
        if type(effect) is not StageCapabilityEffect:
            raise TypeError("effects entries must be StageCapabilityEffect")
        by_stage[effect.stage_id.value] = effect
    return by_stage


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def interpolate_continuous_factors(
    age: int,
    thresholds: Sequence[LifecycleStageThreshold],
    effects: Sequence[StageCapabilityEffect] | None,
    *,
    enabled: bool,
) -> ContinuousLifecycleFactors:
    """Resolve continuous factors for ``age``, optionally interpolating.

    Lerp domain for a non-final stage is
    ``[prev_max + 1, inclusive_max_age]`` toward the next stage's factors.
    Final stage holds factors flat. Denied command kinds are never
    interpolated — callers use ``resolve_stage_effect`` for those.
    """
    age_value = require_exact_nonneg_int("age", age)
    if isinstance(thresholds, (str, bytes)) or not isinstance(thresholds, Sequence):
        raise TypeError("thresholds must be a sequence")
    if len(thresholds) == 0:
        raise ValueError(
            "thresholds must be non-empty (code=lifecycle_stage_thresholds_empty)"
        )
    by_stage = _effects_by_stage(effects)
    previous_max = -1
    for index, threshold in enumerate(thresholds):
        if type(threshold) is not LifecycleStageThreshold:
            raise TypeError("thresholds entries must be LifecycleStageThreshold")
        stage_key = threshold.stage_id.value
        current_effect = by_stage.get(stage_key)
        current_factors = (
            current_effect.continuous_factors
            if current_effect is not None
            else PASSTHROUGH_CONTINUOUS_FACTORS
        )
        band_start = previous_max + 1
        band_end = threshold.inclusive_max_age
        if age_value < band_start or age_value > band_end:
            previous_max = band_end
            continue
        is_final = index == len(thresholds) - 1
        if not enabled or is_final:
            _LOGGER.debug(
                "interpolate_continuous_factors stage_id=%s age=%s "
                "enabled=%s physical=%s learning=%s fatigue=%s",
                stage_key,
                age_value,
                enabled,
                current_factors.physical_capacity_factor,
                current_factors.learning_rate_factor,
                current_factors.fatigue_accrual_factor,
            )
            return current_factors
        next_threshold = thresholds[index + 1]
        next_effect = by_stage.get(next_threshold.stage_id.value)
        next_factors = (
            next_effect.continuous_factors
            if next_effect is not None
            else PASSTHROUGH_CONTINUOUS_FACTORS
        )
        span = band_end - band_start
        if span <= 0:
            t = 1.0
        else:
            t = (age_value - band_start) / float(span)
        result = ContinuousLifecycleFactors(
            physical_capacity_factor=_lerp(
                current_factors.physical_capacity_factor,
                next_factors.physical_capacity_factor,
                t,
            ),
            learning_rate_factor=_lerp(
                current_factors.learning_rate_factor,
                next_factors.learning_rate_factor,
                t,
            ),
            fatigue_accrual_factor=_lerp(
                current_factors.fatigue_accrual_factor,
                next_factors.fatigue_accrual_factor,
                t,
            ),
        )
        _LOGGER.debug(
            "interpolate_continuous_factors stage_id=%s age=%s t=%s "
            "physical=%s learning=%s fatigue=%s",
            stage_key,
            age_value,
            t,
            result.physical_capacity_factor,
            result.learning_rate_factor,
            result.fatigue_accrual_factor,
        )
        return result
    raise ValueError(
        "age exceeds final stage threshold (code=lifecycle_stage_uncovered)"
    )
