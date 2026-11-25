"""Closed objective disaster rule, target, candidate, and effect contracts.

Domain-only: no simulation imports. Policies configure timing and magnitude;
these types never mutate a world and never carry callables or narrative labels.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import EntityId
from world.infrastructure import InfrastructureKind

__all__ = [
    "DISASTERS_POLICY_ID",
    "DISASTER_RULE_ID_PATTERN",
    "MAX_DISASTER_CHANCE_PPM",
    "MAX_DISASTER_RULES",
    "MAX_DISASTER_STRENGTH_TENTHS",
    "MAX_SURGE_OPPORTUNITY_MILLI",
    "MIN_DISASTER_RULES",
    "MIN_DISASTER_STRENGTH_TENTHS",
    "MIN_SURGE_OPPORTUNITY_MILLI",
    "DisasterCandidate",
    "DisasterCollapseEffect",
    "DisasterEffect",
    "DisasterInfrastructureEffect",
    "DisasterInfrastructureTarget",
    "DisasterKind",
    "DisasterLocationTarget",
    "DisasterLossEffect",
    "DisasterOrigin",
    "DisasterResourceTarget",
    "DisasterRule",
    "DisasterScheduleEntry",
    "DisasterSkipReason",
    "DisasterSurgeEffect",
    "DisasterTarget",
]

_LOGGER: Final[logging.Logger] = logging.getLogger("world.disasters")

DISASTERS_POLICY_ID: Final[str] = "disasters.v1"
DISASTER_RULE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-z][a-z0-9-]{0,31}$"
)
MIN_DISASTER_RULES: Final[int] = 1
MAX_DISASTER_RULES: Final[int] = 32
MAX_DISASTER_CHANCE_PPM: Final[int] = 10_000
MIN_DISASTER_STRENGTH_TENTHS: Final[int] = 1
MAX_DISASTER_STRENGTH_TENTHS: Final[int] = 10_000
MIN_SURGE_OPPORTUNITY_MILLI: Final[int] = 1
MAX_SURGE_OPPORTUNITY_MILLI: Final[int] = 1_000


class DisasterKind(StrEnum):
    FLOOD_LIKE = "flood_like"
    FIRE = "fire"
    DROUGHT = "drought"
    RESOURCE_COLLAPSE = "resource_collapse"
    INFRASTRUCTURE_DESTRUCTION = "infrastructure_destruction"
    EPIDEMIC_SURGE = "epidemic_surge"


class DisasterOrigin(StrEnum):
    SCHEDULED = "scheduled"
    SPONTANEOUS = "spontaneous"


class DisasterSkipReason(StrEnum):
    """Bounded skip codes for scheduled no-effect attempts and ineligible pulses."""

    NO_EFFECT = "no_effect"
    WEATHER_INELIGIBLE = "weather_ineligible"
    NO_LIVE_ASSET = "no_live_asset"
    ASSET_AMBIGUOUS = "asset_ambiguous"
    TARGET_MISSING = "target_missing"


def _fail(field: str, code: str) -> ValueError:
    _LOGGER.error(
        "disaster_contract_invalid field=%s reason_code=%s",
        field,
        code,
    )
    return ValueError(f"{field}: {code}")


def _require_strict_int(
    value: object,
    *,
    field: str,
    code: str,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise _fail(field, code)
    if value < minimum or value > maximum:
        raise _fail(field, code)
    return value


@dataclass(frozen=True, slots=True)
class DisasterResourceTarget:
    """One managed renewable stock identified by resource id."""

    resource_id: EntityId

    def __post_init__(self) -> None:
        if type(self.resource_id) is not EntityId:
            raise TypeError("resource_id must be EntityId")
        if self.resource_id.value == "":
            raise _fail("DisasterResourceTarget.resource_id", "disaster_target_invalid")


@dataclass(frozen=True, slots=True)
class DisasterInfrastructureTarget:
    """One infrastructure node or directed edge endpoint pair."""

    location_id: EntityId
    endpoint_location_id: EntityId | None
    infrastructure_kind: InfrastructureKind

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("location_id must be EntityId")
        if self.location_id.value == "":
            raise _fail(
                "DisasterInfrastructureTarget.location_id",
                "disaster_target_invalid",
            )
        if self.endpoint_location_id is not None:
            if type(self.endpoint_location_id) is not EntityId:
                raise TypeError("endpoint_location_id must be EntityId or None")
            if self.endpoint_location_id.value == "":
                raise _fail(
                    "DisasterInfrastructureTarget.endpoint_location_id",
                    "disaster_target_invalid",
                )
            if self.endpoint_location_id.value == self.location_id.value:
                raise _fail(
                    "DisasterInfrastructureTarget.endpoint_location_id",
                    "disaster_edge_endpoints_invalid",
                )
        if type(self.infrastructure_kind) is not InfrastructureKind:
            raise TypeError("infrastructure_kind must be InfrastructureKind")


@dataclass(frozen=True, slots=True)
class DisasterLocationTarget:
    """One location for a fictional epidemic-surge opportunity."""

    location_id: EntityId

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("location_id must be EntityId")
        if self.location_id.value == "":
            raise _fail(
                "DisasterLocationTarget.location_id",
                "disaster_target_invalid",
            )


DisasterTarget = (
    DisasterResourceTarget | DisasterInfrastructureTarget | DisasterLocationTarget
)


@dataclass(frozen=True, slots=True)
class DisasterLossEffect:
    """Exact tenths loss pulse for flood-like, fire, or drought."""

    loss_tenths: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "loss_tenths",
            _require_strict_int(
                self.loss_tenths,
                field="DisasterLossEffect.loss_tenths",
                code="disaster_effect_strength_invalid",
                minimum=MIN_DISASTER_STRENGTH_TENTHS,
                maximum=MAX_DISASTER_STRENGTH_TENTHS,
            ),
        )


@dataclass(frozen=True, slots=True)
class DisasterCollapseEffect:
    """Capacity damage for resource collapse; quantity depletes to zero."""

    capacity_damage_tenths: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "capacity_damage_tenths",
            _require_strict_int(
                self.capacity_damage_tenths,
                field="DisasterCollapseEffect.capacity_damage_tenths",
                code="disaster_effect_strength_invalid",
                minimum=MIN_DISASTER_STRENGTH_TENTHS,
                maximum=MAX_DISASTER_STRENGTH_TENTHS,
            ),
        )


@dataclass(frozen=True, slots=True)
class DisasterInfrastructureEffect:
    """Fixed full integrity loss; empty structured payload."""


@dataclass(frozen=True, slots=True)
class DisasterSurgeEffect:
    """Extra fictional exposure opportunity in parts-per-thousand."""

    extra_opportunity_milli: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "extra_opportunity_milli",
            _require_strict_int(
                self.extra_opportunity_milli,
                field="DisasterSurgeEffect.extra_opportunity_milli",
                code="disaster_surge_opportunity_invalid",
                minimum=MIN_SURGE_OPPORTUNITY_MILLI,
                maximum=MAX_SURGE_OPPORTUNITY_MILLI,
            ),
        )


DisasterEffect = (
    DisasterLossEffect
    | DisasterCollapseEffect
    | DisasterInfrastructureEffect
    | DisasterSurgeEffect
)


@dataclass(frozen=True, slots=True)
class DisasterRule:
    """One closed disaster rule with exact timing chance and structured impact."""

    rule_id: str
    kind: DisasterKind
    chance_ppm: int
    target: DisasterTarget
    effect: DisasterEffect

    def __post_init__(self) -> None:
        if type(self.rule_id) is not str or not DISASTER_RULE_ID_PATTERN.fullmatch(
            self.rule_id
        ):
            raise _fail("DisasterRule.rule_id", "disaster_rule_id_invalid")
        if type(self.kind) is not DisasterKind:
            raise TypeError("kind must be DisasterKind")
        object.__setattr__(
            self,
            "chance_ppm",
            _require_strict_int(
                self.chance_ppm,
                field="DisasterRule.chance_ppm",
                code="disaster_chance_ppm_invalid",
                minimum=0,
                maximum=MAX_DISASTER_CHANCE_PPM,
            ),
        )
        _validate_rule_shape(
            kind=self.kind,
            target=self.target,
            effect=self.effect,
            field="DisasterRule",
        )


@dataclass(frozen=True, slots=True)
class DisasterScheduleEntry:
    """One absolute-tick injection of a known rule; does not alter impact."""

    tick: int
    rule_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            _require_strict_int(
                self.tick,
                field="DisasterScheduleEntry.tick",
                code="disaster_schedule_tick_invalid",
                minimum=0,
                maximum=2**63 - 1,
            ),
        )
        if type(self.rule_id) is not str or not DISASTER_RULE_ID_PATTERN.fullmatch(
            self.rule_id
        ):
            raise _fail(
                "DisasterScheduleEntry.rule_id",
                "disaster_schedule_rule_invalid",
            )


@dataclass(frozen=True, slots=True)
class DisasterCandidate:
    """Immutable selected rule with scheduled or spontaneous origin."""

    rule: DisasterRule
    origin: DisasterOrigin

    def __post_init__(self) -> None:
        if type(self.rule) is not DisasterRule:
            raise TypeError("rule must be DisasterRule")
        if type(self.origin) is not DisasterOrigin:
            raise TypeError("origin must be DisasterOrigin")


def _validate_rule_shape(
    *,
    kind: DisasterKind,
    target: DisasterTarget,
    effect: DisasterEffect,
    field: str,
) -> None:
    stock_kinds = {
        DisasterKind.FLOOD_LIKE,
        DisasterKind.FIRE,
        DisasterKind.DROUGHT,
    }
    if kind in stock_kinds:
        if type(target) is not DisasterResourceTarget:
            raise _fail(f"{field}.target", "disaster_target_kind_mismatch")
        if type(effect) is not DisasterLossEffect:
            raise _fail(f"{field}.effect", "disaster_effect_kind_mismatch")
        return
    if kind is DisasterKind.RESOURCE_COLLAPSE:
        if type(target) is not DisasterResourceTarget:
            raise _fail(f"{field}.target", "disaster_target_kind_mismatch")
        if type(effect) is not DisasterCollapseEffect:
            raise _fail(f"{field}.effect", "disaster_effect_kind_mismatch")
        return
    if kind is DisasterKind.INFRASTRUCTURE_DESTRUCTION:
        if type(target) is not DisasterInfrastructureTarget:
            raise _fail(f"{field}.target", "disaster_target_kind_mismatch")
        if type(effect) is not DisasterInfrastructureEffect:
            raise _fail(f"{field}.effect", "disaster_effect_kind_mismatch")
        return
    if kind is DisasterKind.EPIDEMIC_SURGE:
        if type(target) is not DisasterLocationTarget:
            raise _fail(f"{field}.target", "disaster_target_kind_mismatch")
        if type(effect) is not DisasterSurgeEffect:
            raise _fail(f"{field}.effect", "disaster_effect_kind_mismatch")
        return
    raise _fail(f"{field}.kind", "disaster_kind_invalid")
