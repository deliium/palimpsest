"""Objective population lifecycle domain types (no biological reproduction).

Chronological age is a pure function of ``(entry_tick, current_tick)`` and is
never stored as a mutable field that can drift from logical time. Stage and
dependency status are derived from run-level thresholds owned by WorldEngine.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import (
    EntityId,
    require_exact_nonneg_int,
    require_stable_id,
)
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_LOGGER: Final[logging.Logger] = logging.getLogger("world.lifecycle")

__all__ = [
    "AgentLifecycleRecord",
    "DependencyStatus",
    "LifecycleStageId",
    "LifecycleStageThreshold",
    "OriginProvenance",
    "chronological_age",
    "default_entrant_body",
    "require_assigned_lifespan_ticks",
    "require_lifecycle_stage_id",
    "resolve_dependency_status",
    "resolve_lifecycle_stage",
    "validate_assigned_lifespan_stage_coverage",
]


class DependencyStatus(StrEnum):
    """Closed dependency status derived from stage vs dependent_until_stage."""

    DEPENDENT = "dependent"
    INDEPENDENT = "independent"


class OriginProvenance(StrEnum):
    """Closed origin provenance for an agent lifecycle record.

    These are experimental entry labels, not biological birth.
    """

    BOOTSTRAP = "bootstrap"
    DEMOGRAPHIC_POLICY = "demographic_policy"
    EXTERNAL_ENTRY = "external_entry"


@dataclass(frozen=True, slots=True)
class LifecycleStageId:
    """Opaque closed stage identity validated against run-level thresholds."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("LifecycleStageId.value", self.value)


def require_lifecycle_stage_id(value: object) -> LifecycleStageId:
    """Coerce a stage id string or return an existing ``LifecycleStageId``."""
    if type(value) is LifecycleStageId:
        return value
    if type(value) is not str:
        raise TypeError("lifecycle stage id must be str or LifecycleStageId")
    return LifecycleStageId(value)


@dataclass(frozen=True, slots=True)
class LifecycleStageThreshold:
    """One ordered stage boundary: inclusive max chronological age."""

    stage_id: LifecycleStageId
    inclusive_max_age: int

    def __post_init__(self) -> None:
        if type(self.stage_id) is not LifecycleStageId:
            raise TypeError(
                "LifecycleStageThreshold.stage_id must be LifecycleStageId"
            )
        object.__setattr__(
            self,
            "inclusive_max_age",
            require_exact_nonneg_int(
                "LifecycleStageThreshold.inclusive_max_age",
                self.inclusive_max_age,
            ),
        )


def require_assigned_lifespan_ticks(name: str, value: object) -> int:
    """Require a positive assigned lifespan in ticks."""
    if isinstance(value, bool) or type(value) is not int or value < 1:
        _LOGGER.error(
            "assigned_lifespan_invalid code=lifecycle_assigned_lifespan_invalid "
            "name=%s",
            name,
        )
        raise ValueError(
            f"{name} must be a positive integer "
            "(code=lifecycle_assigned_lifespan_invalid)"
        )
    return value


def validate_assigned_lifespan_stage_coverage(
    assigned_lifespan_ticks: int,
    stage_thresholds: Sequence[LifecycleStageThreshold],
) -> None:
    """Fail closed when stages do not cover ages through ``assigned - 1``."""
    assigned = require_assigned_lifespan_ticks(
        "assigned_lifespan_ticks", assigned_lifespan_ticks
    )
    if isinstance(stage_thresholds, (str, bytes)) or not isinstance(
        stage_thresholds, Sequence
    ):
        raise TypeError("stage_thresholds must be a sequence")
    if len(stage_thresholds) == 0:
        raise ValueError(
            "stage_thresholds must be non-empty "
            "(code=lifecycle_stage_thresholds_empty)"
        )
    # Reuse ordering validation via age-0 resolve, then check coverage.
    resolve_lifecycle_stage(0, stage_thresholds)
    final_max = stage_thresholds[-1].inclusive_max_age
    if type(final_max) is not int:
        raise TypeError("inclusive_max_age must be int")
    if assigned - 1 > final_max:
        _LOGGER.error(
            "assigned_lifespan_uncovered code=lifecycle_stage_uncovered_lifespan "
            "assigned_lifespan_ticks=%s final_max=%s",
            assigned,
            final_max,
        )
        raise ValueError(
            "stage_thresholds must cover ages through "
            "assigned_lifespan_ticks-1 "
            "(code=lifecycle_stage_uncovered_lifespan)"
        )


@dataclass(frozen=True, slots=True)
class AgentLifecycleRecord:
    """World-owned objective lifecycle binding for one registered body.

    Chronological age is not stored; callers use ``chronological_age``.
    ``assigned_lifespan_ticks`` is drawn once at entry and never re-drawn.
    Forbidden fields: sex, fertility, mating, pregnancy, parentage, kinship.
    """

    body_id: EntityId
    agent_id: str
    entry_tick: int
    stage: LifecycleStageId
    dependency_status: DependencyStatus
    generation_index: int
    cohort_id: str
    provenance: OriginProvenance
    assigned_lifespan_ticks: int

    def __post_init__(self) -> None:
        if type(self.body_id) is not EntityId:
            raise TypeError("AgentLifecycleRecord.body_id must be EntityId")
        object.__setattr__(
            self,
            "agent_id",
            require_stable_id("AgentLifecycleRecord.agent_id", self.agent_id),
        )
        object.__setattr__(
            self,
            "entry_tick",
            require_exact_nonneg_int(
                "AgentLifecycleRecord.entry_tick", self.entry_tick
            ),
        )
        if type(self.stage) is not LifecycleStageId:
            raise TypeError("AgentLifecycleRecord.stage must be LifecycleStageId")
        if type(self.dependency_status) is not DependencyStatus:
            raise TypeError(
                "AgentLifecycleRecord.dependency_status must be DependencyStatus"
            )
        object.__setattr__(
            self,
            "generation_index",
            require_exact_nonneg_int(
                "AgentLifecycleRecord.generation_index",
                self.generation_index,
            ),
        )
        object.__setattr__(
            self,
            "cohort_id",
            require_stable_id("AgentLifecycleRecord.cohort_id", self.cohort_id),
        )
        if type(self.provenance) is not OriginProvenance:
            raise TypeError(
                "AgentLifecycleRecord.provenance must be OriginProvenance"
            )
        object.__setattr__(
            self,
            "assigned_lifespan_ticks",
            require_assigned_lifespan_ticks(
                "AgentLifecycleRecord.assigned_lifespan_ticks",
                self.assigned_lifespan_ticks,
            ),
        )


def chronological_age(*, entry_tick: int, current_tick: int) -> int:
    """Derive objective chronological age from logical ticks.

    Age at the entry tick is ``0``. ``current_tick`` must be ``>= entry_tick``.
    """
    entry = require_exact_nonneg_int("entry_tick", entry_tick)
    current = require_exact_nonneg_int("current_tick", current_tick)
    if current < entry:
        raise ValueError(
            "current_tick must be >= entry_tick "
            "(code=lifecycle_age_tick_order)"
        )
    return current - entry


def default_entrant_body(*, body_id: EntityId, location_id: EntityId) -> AgentBody:
    """Deterministic default body shell for mid-run demographic entry."""
    if type(body_id) is not EntityId:
        raise TypeError("body_id must be EntityId")
    if type(location_id) is not EntityId:
        raise TypeError("location_id must be EntityId")
    return AgentBody(
        entity_id=body_id,
        location_id=location_id,
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def resolve_lifecycle_stage(
    age: int,
    stage_thresholds: Sequence[LifecycleStageThreshold],
) -> LifecycleStageId:
    """Return the first ordered threshold whose inclusive max age covers ``age``.

    Thresholds must be non-empty, unique by stage id, and strictly increasing
    by ``inclusive_max_age``. Ages beyond the final threshold fail closed.
    Full sequence validation runs before age matching so invalid specs fail
    closed even when an early threshold would otherwise cover the age.
    """
    age_value = require_exact_nonneg_int("age", age)
    if isinstance(stage_thresholds, (str, bytes)) or not isinstance(
        stage_thresholds, Sequence
    ):
        raise TypeError("stage_thresholds must be a sequence")
    if len(stage_thresholds) == 0:
        raise ValueError(
            "stage_thresholds must be non-empty "
            "(code=lifecycle_stage_thresholds_empty)"
        )
    seen_stages: set[str] = set()
    previous_max: int | None = None
    validated: list[LifecycleStageThreshold] = []
    for index, threshold in enumerate(stage_thresholds):
        if type(threshold) is not LifecycleStageThreshold:
            raise TypeError(
                "stage_thresholds entries must be LifecycleStageThreshold"
            )
        stage_key = threshold.stage_id.value
        if stage_key in seen_stages:
            raise ValueError(
                "stage_thresholds stage ids must be unique "
                f"(code=lifecycle_stage_id_duplicate index={index})"
            )
        seen_stages.add(stage_key)
        if previous_max is not None and threshold.inclusive_max_age <= previous_max:
            raise ValueError(
                "stage_thresholds inclusive_max_age must strictly increase "
                f"(code=lifecycle_stage_threshold_order index={index})"
            )
        previous_max = threshold.inclusive_max_age
        validated.append(threshold)
    for threshold in validated:
        if age_value <= threshold.inclusive_max_age:
            return threshold.stage_id
    raise ValueError(
        "age exceeds final stage threshold "
        "(code=lifecycle_stage_uncovered)"
    )


def resolve_dependency_status(
    stage: LifecycleStageId,
    dependent_until_stage: LifecycleStageId,
    *,
    stage_order: Sequence[LifecycleStageId],
) -> DependencyStatus:
    """Derive dependency from ordered stages.

    Agents strictly below ``dependent_until_stage`` are ``DEPENDENT``;
    agents at or above that stage are ``INDEPENDENT``.
    """
    if type(stage) is not LifecycleStageId:
        raise TypeError("stage must be LifecycleStageId")
    if type(dependent_until_stage) is not LifecycleStageId:
        raise TypeError("dependent_until_stage must be LifecycleStageId")
    if isinstance(stage_order, (str, bytes)) or not isinstance(stage_order, Sequence):
        raise TypeError("stage_order must be a sequence")
    if len(stage_order) == 0:
        raise ValueError(
            "stage_order must be non-empty (code=lifecycle_stage_order_empty)"
        )
    order_keys: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(stage_order):
        if type(item) is not LifecycleStageId:
            raise TypeError("stage_order entries must be LifecycleStageId")
        if item.value in seen:
            raise ValueError(
                "stage_order stage ids must be unique "
                f"(code=lifecycle_stage_order_duplicate index={index})"
            )
        seen.add(item.value)
        order_keys.append(item.value)
    try:
        stage_index = order_keys.index(stage.value)
    except ValueError as exc:
        raise ValueError(
            "stage not present in stage_order (code=lifecycle_stage_unknown)"
        ) from exc
    try:
        until_index = order_keys.index(dependent_until_stage.value)
    except ValueError as exc:
        raise ValueError(
            "dependent_until_stage not present in stage_order "
            "(code=lifecycle_dependent_until_unknown)"
        ) from exc
    if stage_index < until_index:
        return DependencyStatus.DEPENDENT
    return DependencyStatus.INDEPENDENT
