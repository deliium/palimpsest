"""World-owned resolved effects and closed event causation.

Simulation resolves named seeded draws into these immutable facts, then passes
only world-owned values into pure rule modules. RNG objects, callbacks, and
simulation types must never appear here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Literal

from world.identifiers import (
    EntityId,
    RecipeId,
    RequestId,
    require_exact_nonneg_int,
)
from world.production import ProductionRecipe
from world.values import WeatherCondition

__all__ = [
    "ActionCause",
    "DeathCause",
    "EventCause",
    "ResolvedActionEffect",
    "ResolvedActionEffects",
    "ResolvedArtifactCopyEffect",
    "ResolvedArtifactInscribeEffect",
    "ResolvedAttackEffect",
    "ResolvedFleeEffect",
    "ResolvedProductionEffect",
    "ResolvedSearchEffect",
    "ResolvedSystemEffects",
    "ResolvedWeatherEffect",
    "SystemCause",
    "SystemEffectFamily",
    "require_event_cause",
    "require_resolved_action_effect",
]


class DeathCause(StrEnum):
    """Closed objective death causes recorded on ``Died`` events."""

    ATTACK = "attack"
    COMBINED_NEEDS = "combined_needs"
    EXPOSURE = "exposure"
    LIFESPAN = "lifespan"


class SystemEffectFamily(StrEnum):
    """Closed autonomous effect families for system cause derivation."""

    WEATHER = "weather"
    REGENERATION = "regeneration"
    COMBINED_NEEDS = "combined_needs"
    EXPOSURE = "exposure"
    PRODUCTION = "production"
    SEASON = "season"
    TEMPERATURE_BAND = "temperature_band"
    HAZARD = "hazard"
    RESOURCE_NODE = "resource_node"
    LIFECYCLE = "lifecycle"


@dataclass(frozen=True, slots=True)
class ActionCause:
    """Cause retained for agent-submitted actions."""

    request_id: RequestId
    actor_id: EntityId
    kind: Literal["action"] = field(default="action", init=False)

    def __post_init__(self) -> None:
        if type(self.request_id) is not RequestId:
            raise TypeError("ActionCause.request_id must be RequestId")
        if type(self.actor_id) is not EntityId:
            raise TypeError("ActionCause.actor_id must be EntityId")


@dataclass(frozen=True, slots=True)
class SystemCause:
    """Cause for autonomous system effects.

    ``cause_id`` is a deterministic request-shaped identity derived outside
    ``world`` (run, world, tick, family, entity, ordinal).
    """

    cause_id: RequestId
    effect_family: SystemEffectFamily
    entity_id: EntityId
    family_ordinal: int
    kind: Literal["system"] = field(default="system", init=False)

    def __post_init__(self) -> None:
        if type(self.cause_id) is not RequestId:
            raise TypeError("SystemCause.cause_id must be RequestId")
        if type(self.effect_family) is not SystemEffectFamily:
            raise TypeError("SystemCause.effect_family must be SystemEffectFamily")
        if type(self.entity_id) is not EntityId:
            raise TypeError("SystemCause.entity_id must be EntityId")
        object.__setattr__(
            self,
            "family_ordinal",
            require_exact_nonneg_int("SystemCause.family_ordinal", self.family_ordinal),
        )


EventCause = ActionCause | SystemCause

_CAUSE_TYPES: Final[frozenset[type]] = frozenset({ActionCause, SystemCause})


def require_event_cause(value: object) -> EventCause:
    if type(value) not in _CAUSE_TYPES:
        raise TypeError(f"unsupported event cause type {type(value).__name__}")
    return value  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ResolvedSearchEffect:
    """Pre-resolved search Bernoulli outcome and created item identity."""

    request_id: RequestId
    success: bool
    resource_id: EntityId
    created_item_id: EntityId | None = None
    kind: Literal["search"] = field(default="search", init=False)

    def __post_init__(self) -> None:
        if type(self.request_id) is not RequestId:
            raise TypeError("ResolvedSearchEffect.request_id must be RequestId")
        if type(self.success) is not bool:
            raise TypeError("ResolvedSearchEffect.success must be bool")
        if type(self.resource_id) is not EntityId:
            raise TypeError("ResolvedSearchEffect.resource_id must be EntityId")
        if self.success:
            if type(self.created_item_id) is not EntityId:
                raise ValueError(
                    "successful ResolvedSearchEffect requires created_item_id"
                )
        elif self.created_item_id is not None:
            raise ValueError(
                "failed ResolvedSearchEffect must not carry created_item_id"
            )


@dataclass(frozen=True, slots=True)
class ResolvedAttackEffect:
    """Pre-resolved attack hit Bernoulli and integer damage."""

    request_id: RequestId
    hit: bool
    damage: int | None = None
    kind: Literal["attack"] = field(default="attack", init=False)

    def __post_init__(self) -> None:
        if type(self.request_id) is not RequestId:
            raise TypeError("ResolvedAttackEffect.request_id must be RequestId")
        if type(self.hit) is not bool:
            raise TypeError("ResolvedAttackEffect.hit must be bool")
        if self.hit:
            if (
                isinstance(self.damage, bool)
                or type(self.damage) is not int
                or self.damage < 0
            ):
                raise ValueError("successful ResolvedAttackEffect requires damage >= 0")
        elif self.damage is not None:
            raise ValueError("missed ResolvedAttackEffect must not carry damage")


@dataclass(frozen=True, slots=True)
class ResolvedFleeEffect:
    """Pre-resolved flee success and destination selector index.

    World rules select the destination from the canonically sorted currently
    eligible set after success; the index is validated against that set length.
    """

    request_id: RequestId
    success: bool
    destination_index: int | None = None
    kind: Literal["flee"] = field(default="flee", init=False)

    def __post_init__(self) -> None:
        if type(self.request_id) is not RequestId:
            raise TypeError("ResolvedFleeEffect.request_id must be RequestId")
        if type(self.success) is not bool:
            raise TypeError("ResolvedFleeEffect.success must be bool")
        if self.success:
            object.__setattr__(
                self,
                "destination_index",
                require_exact_nonneg_int(
                    "ResolvedFleeEffect.destination_index",
                    self.destination_index,
                ),
            )
        elif self.destination_index is not None:
            raise ValueError(
                "failed ResolvedFleeEffect must not carry destination_index"
            )


@dataclass(frozen=True, slots=True)
class ResolvedWeatherEffect:
    """Pre-resolved weather sample for one location."""

    location_id: EntityId
    condition: WeatherCondition
    kind: Literal["weather"] = field(default="weather", init=False)

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("ResolvedWeatherEffect.location_id must be EntityId")
        if type(self.condition) is not WeatherCondition:
            raise TypeError("ResolvedWeatherEffect.condition must be WeatherCondition")


@dataclass(frozen=True, slots=True)
class ResolvedProductionEffect:
    """Pre-resolved production draw. A reason code rejects with no event."""

    request_id: RequestId
    recipe_id: RecipeId
    success: bool
    duration_ticks: int
    created_entity_id: EntityId | None = None
    reason_code: str | None = None
    recipe: ProductionRecipe | None = None
    kind: Literal["production"] = field(default="production", init=False)

    def __post_init__(self) -> None:
        if type(self.request_id) is not RequestId:
            raise TypeError("ResolvedProductionEffect.request_id must be RequestId")
        if type(self.recipe_id) is not RecipeId:
            raise TypeError("ResolvedProductionEffect.recipe_id must be RecipeId")
        if type(self.success) is not bool:
            raise TypeError("ResolvedProductionEffect.success must be bool")
        if (
            isinstance(self.duration_ticks, bool)
            or type(self.duration_ticks) is not int
            or self.duration_ticks < 1
        ):
            raise ValueError("ResolvedProductionEffect.duration_ticks must be >= 1")
        if self.reason_code is not None and type(self.reason_code) is not str:
            raise TypeError("ResolvedProductionEffect.reason_code must be str or None")
        if self.recipe is not None and type(self.recipe) is not ProductionRecipe:
            raise TypeError("ResolvedProductionEffect.recipe must be ProductionRecipe")
        if (
            self.created_entity_id is not None
            and type(self.created_entity_id) is not EntityId
        ):
            raise TypeError(
                "ResolvedProductionEffect.created_entity_id must be EntityId or None"
            )


@dataclass(frozen=True, slots=True)
class ResolvedArtifactInscribeEffect:
    """Pre-derived artifact identity for a successful Inscribe."""

    request_id: RequestId
    created_artifact_id: EntityId
    kind: Literal["artifact_inscribe"] = field(
        default="artifact_inscribe", init=False
    )

    def __post_init__(self) -> None:
        if type(self.request_id) is not RequestId:
            raise TypeError(
                "ResolvedArtifactInscribeEffect.request_id must be RequestId"
            )
        if type(self.created_artifact_id) is not EntityId:
            raise TypeError(
                "ResolvedArtifactInscribeEffect.created_artifact_id must be EntityId"
            )


@dataclass(frozen=True, slots=True)
class ResolvedArtifactCopyEffect:
    """Pre-derived artifact identity for a successful CopyRecord."""

    request_id: RequestId
    created_artifact_id: EntityId
    kind: Literal["artifact_copy"] = field(default="artifact_copy", init=False)

    def __post_init__(self) -> None:
        if type(self.request_id) is not RequestId:
            raise TypeError(
                "ResolvedArtifactCopyEffect.request_id must be RequestId"
            )
        if type(self.created_artifact_id) is not EntityId:
            raise TypeError(
                "ResolvedArtifactCopyEffect.created_artifact_id must be EntityId"
            )


ResolvedActionEffect = (
    ResolvedSearchEffect
    | ResolvedAttackEffect
    | ResolvedFleeEffect
    | ResolvedProductionEffect
    | ResolvedArtifactInscribeEffect
    | ResolvedArtifactCopyEffect
)

_ACTION_EFFECT_TYPES: Final[frozenset[type]] = frozenset(
    {
        ResolvedSearchEffect,
        ResolvedAttackEffect,
        ResolvedFleeEffect,
        ResolvedProductionEffect,
        ResolvedArtifactInscribeEffect,
        ResolvedArtifactCopyEffect,
    }
)


def require_resolved_action_effect(value: object) -> ResolvedActionEffect:
    if type(value) not in _ACTION_EFFECT_TYPES:
        raise TypeError(
            f"unsupported resolved action effect type {type(value).__name__}"
        )
    return value  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ResolvedActionEffects:
    """Request-keyed resolved stochastic facts for one tick's action stage."""

    by_request: Mapping[RequestId, ResolvedActionEffect]

    def __post_init__(self) -> None:
        if isinstance(self.by_request, (str, bytes)) or not isinstance(
            self.by_request, Mapping
        ):
            raise TypeError("ResolvedActionEffects.by_request must be a mapping")
        frozen: dict[RequestId, ResolvedActionEffect] = {}
        for key, value in self.by_request.items():
            if type(key) is not RequestId:
                raise TypeError("ResolvedActionEffects keys must be RequestId")
            effect = require_resolved_action_effect(value)
            if effect.request_id != key:
                raise ValueError(
                    "ResolvedActionEffects key must equal effect.request_id"
                )
            if key in frozen:
                raise ValueError("ResolvedActionEffects keys must be unique")
            frozen[key] = effect
        object.__setattr__(self, "by_request", frozen)

    def require(self, request_id: RequestId, expected: type) -> ResolvedActionEffect:
        if type(request_id) is not RequestId:
            raise TypeError("require requires RequestId")
        try:
            effect = self.by_request[request_id]
        except KeyError as exc:
            raise ValueError(
                f"missing resolved effect for request {request_id.value}"
            ) from exc
        if type(effect) is not expected:
            raise TypeError(
                f"resolved effect for {request_id.value} must be {expected.__name__}"
            )
        return effect


@dataclass(frozen=True, slots=True)
class ResolvedSystemEffects:
    """Location-keyed pre-resolved weather outcomes for autonomous stages."""

    weather_by_location: Mapping[EntityId, ResolvedWeatherEffect]

    def __post_init__(self) -> None:
        if isinstance(self.weather_by_location, (str, bytes)) or not isinstance(
            self.weather_by_location, Mapping
        ):
            raise TypeError(
                "ResolvedSystemEffects.weather_by_location must be a mapping"
            )
        frozen: dict[EntityId, ResolvedWeatherEffect] = {}
        for key, value in self.weather_by_location.items():
            if type(key) is not EntityId:
                raise TypeError("ResolvedSystemEffects weather keys must be EntityId")
            if type(value) is not ResolvedWeatherEffect:
                raise TypeError(
                    "ResolvedSystemEffects weather values must be ResolvedWeatherEffect"
                )
            if value.location_id != key:
                raise ValueError(
                    "ResolvedSystemEffects weather key must equal location_id"
                )
            if key in frozen:
                raise ValueError("ResolvedSystemEffects weather keys must be unique")
            frozen[key] = value
        object.__setattr__(self, "weather_by_location", frozen)
