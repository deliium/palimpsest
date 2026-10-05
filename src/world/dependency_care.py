"""Objective dependency-care need types and pure resolvers.

Dependency is stage-derived ``DependencyStatus`` plus configurable need
deficits — not biology and not caregiver role assignment. WorldEngine owns
objective consequences; cognition decides whether care is offered.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.lifecycle import DependencyStatus

_LOGGER: Final[logging.Logger] = logging.getLogger("world.dependency_care")

__all__ = [
    "ALLOWED_CRITICAL_CONSEQUENCES",
    "CARE_ASSIST_KINDS",
    "CARE_NEED_IDS",
    "FORBIDDEN_NEED_ALIASES",
    "SELF_SATISFY_DENIED_KINDS",
    "CareAssistKind",
    "CareNeedId",
    "CareNeedPolicy",
    "DependencyCareRuleContext",
    "DependencyNeedRegister",
    "UnmetNeedTickEffect",
    "care_action_legal",
    "compute_unmet_tick_effects",
    "empty_need_register",
    "is_need_critical",
    "needs_requiring_assistance",
    "require_care_need_id",
    "require_care_need_policy",
    "self_satisfy_denied_kinds",
]


class CareNeedId(StrEnum):
    """Closed objective need ids for DEPENDENT agents."""

    FOOD = "food"
    WATER = "water"
    SAFETY = "safety"
    MOVEMENT = "movement"
    SHELTER = "shelter"
    LEARNING = "learning"


class CareAssistKind(StrEnum):
    """Closed caregiver assist kinds (not social roles)."""

    FEED = "feed"
    TRANSPORT = "transport"
    HELP_SAFETY = "help_safety"
    TEACH_LEARNING = "teach_learning"


CARE_NEED_IDS: Final[frozenset[str]] = frozenset(item.value for item in CareNeedId)
CARE_ASSIST_KINDS: Final[frozenset[str]] = frozenset(
    item.value for item in CareAssistKind
)

FORBIDDEN_NEED_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "love",
        "attention",
        "emotion",
        "parenting",
        "attachment",
        "sex",
        "fertility",
        "pregnancy",
        "lactation",
        "nanny",
        "guardian",
        "caregiver",
        "ward",
    }
)

# Physiology-backed needs use existing body/location signals; explicit register
# stores only non-physiology deficits (learning, optional movement markers).
PHYSIOLOGY_BACKED_NEEDS: Final[frozenset[CareNeedId]] = frozenset(
    {
        CareNeedId.FOOD,
        CareNeedId.WATER,
        CareNeedId.SAFETY,
        CareNeedId.SHELTER,
    }
)
REGISTER_BACKED_NEEDS: Final[frozenset[CareNeedId]] = frozenset(
    {
        CareNeedId.LEARNING,
        CareNeedId.MOVEMENT,
    }
)

SELF_SATISFY_DENIED_KINDS: Final[Mapping[CareNeedId, frozenset[str]]] = {
    CareNeedId.FOOD: frozenset({"eat"}),
    CareNeedId.WATER: frozenset({"drink"}),
    CareNeedId.MOVEMENT: frozenset({"move", "flee"}),
    CareNeedId.SHELTER: frozenset(),
    CareNeedId.SAFETY: frozenset(),
    CareNeedId.LEARNING: frozenset(),
}

ALLOWED_CRITICAL_CONSEQUENCES: Final[Mapping[CareNeedId, frozenset[str]]] = {
    CareNeedId.FOOD: frozenset(
        {
            "accelerate_hunger",
            "health_damage",
            "death_when_physiology_terminal",
        }
    ),
    CareNeedId.WATER: frozenset(
        {
            "accelerate_thirst",
            "health_damage",
            "death_when_physiology_terminal",
        }
    ),
    CareNeedId.SAFETY: frozenset({"health_damage", "no_extra"}),
    CareNeedId.MOVEMENT: frozenset({"no_extra"}),
    CareNeedId.SHELTER: frozenset(
        {"fatigue_accrual", "health_damage", "no_extra"}
    ),
    CareNeedId.LEARNING: frozenset({"learning_rate_zero", "no_extra"}),
}

_SELF_SATISFY_DENIAL_CODE: Final[str] = "dependency_care_self_satisfy_denied"


@dataclass(frozen=True, slots=True)
class DependencyCareRuleContext:
    """Ephemeral care-action gates for evaluate/apply (not checkpointed).

    Built by WorldEngine from lifecycle DEPENDENT body ids + care_action_policy.
    Absent context means the dependency-care channel is off.
    """

    dependent_body_ids: frozenset[EntityId]
    allow_feed: bool
    allow_transport: bool
    require_colocated: bool = True

    def __post_init__(self) -> None:
        if type(self.dependent_body_ids) is not frozenset:
            raise TypeError("dependent_body_ids must be frozenset")
        for body_id in self.dependent_body_ids:
            if type(body_id) is not EntityId:
                raise TypeError("dependent_body_ids entries must be EntityId")
        for name in ("allow_feed", "allow_transport", "require_colocated"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True, slots=True)
class CareNeedPolicy:
    """Per-need objective policy (exact keys owned by DependencyCareSpec)."""

    self_satisfy: bool
    unmet_accrual_per_tick: float
    critical_threshold: float
    critical_consequence: str

    def __post_init__(self) -> None:
        if type(self.self_satisfy) is not bool:
            raise TypeError("self_satisfy must be bool")
        if isinstance(self.unmet_accrual_per_tick, bool) or not isinstance(
            self.unmet_accrual_per_tick, (int, float)
        ):
            raise TypeError("unmet_accrual_per_tick must be a number")
        accrual = float(self.unmet_accrual_per_tick)
        if accrual < 0.0:
            _LOGGER.error(
                "dependency_care_accrual_negative code=dependency_care_accrual_negative"
            )
            raise ValueError(
                "unmet_accrual_per_tick must be non-negative "
                "(code=dependency_care_accrual_negative)"
            )
        object.__setattr__(self, "unmet_accrual_per_tick", accrual)
        if isinstance(self.critical_threshold, bool) or not isinstance(
            self.critical_threshold, (int, float)
        ):
            raise TypeError("critical_threshold must be a number")
        threshold = float(self.critical_threshold)
        if threshold < 0.0 or threshold > 1.0:
            _LOGGER.error(
                "dependency_care_threshold_invalid "
                "code=dependency_care_threshold_invalid"
            )
            raise ValueError(
                "critical_threshold must be in [0, 1] "
                "(code=dependency_care_threshold_invalid)"
            )
        object.__setattr__(self, "critical_threshold", threshold)
        if type(self.critical_consequence) is not str:
            raise TypeError("critical_consequence must be str")


@dataclass(frozen=True, slots=True)
class DependencyNeedRegister:
    """Sparse per-agent non-physiology need deficits (engine/journal only).

    Physiology-backed needs (food/water/safety/shelter) are NOT stored here —
    they read hunger/thirst/health/shelter_factor. Only ``learning`` and
    optional ``movement`` markers live in this register for codec v9.
    """

    agent_id: AgentId
    deficits: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        if isinstance(self.deficits, (str, bytes)) or not isinstance(
            self.deficits, Mapping
        ):
            raise TypeError("deficits must be a mapping")
        cleaned: dict[str, float] = {}
        for raw_key, raw_value in self.deficits.items():
            if type(raw_key) is not str:
                raise TypeError("deficit keys must be str")
            if raw_key in FORBIDDEN_NEED_ALIASES:
                _LOGGER.error(
                    "dependency_care_forbidden_need "
                    "code=dependency_care_forbidden_need need=%s",
                    raw_key,
                )
                raise ValueError(
                    f"forbidden need id {raw_key!r} "
                    "(code=dependency_care_forbidden_need)"
                )
            try:
                need = CareNeedId(raw_key)
            except ValueError as exc:
                _LOGGER.error(
                    "dependency_care_unknown_need code=dependency_care_unknown_need "
                    "need=%s",
                    raw_key,
                )
                raise ValueError(
                    f"unknown need id {raw_key!r} "
                    "(code=dependency_care_unknown_need)"
                ) from exc
            if need not in REGISTER_BACKED_NEEDS:
                _LOGGER.error(
                    "dependency_care_physiology_need_in_register "
                    "code=dependency_care_physiology_need_in_register need=%s",
                    raw_key,
                )
                raise ValueError(
                    f"physiology-backed need {raw_key!r} must not use register "
                    "(code=dependency_care_physiology_need_in_register)"
                )
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise TypeError(f"deficit for {raw_key!r} must be a number")
            value = float(raw_value)
            if value < 0.0:
                raise ValueError(
                    f"deficit for {raw_key!r} must be non-negative "
                    "(code=dependency_care_deficit_negative)"
                )
            cleaned[need.value] = value
        object.__setattr__(
            self,
            "deficits",
            dict(sorted(cleaned.items())),
        )

    def deficit_of(self, need: CareNeedId) -> float:
        if need not in REGISTER_BACKED_NEEDS:
            raise ValueError(
                f"need {need.value!r} is physiology-backed "
                "(code=dependency_care_physiology_need_query)"
            )
        return float(self.deficits.get(need.value, 0.0))

    def with_deficit(self, need: CareNeedId, value: float) -> DependencyNeedRegister:
        if need not in REGISTER_BACKED_NEEDS:
            raise ValueError(
                f"need {need.value!r} is physiology-backed "
                "(code=dependency_care_physiology_need_mutate)"
            )
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("deficit value must be a number")
        next_value = float(value)
        if next_value < 0.0:
            raise ValueError(
                "deficit must be non-negative (code=dependency_care_deficit_negative)"
            )
        updated = dict(self.deficits)
        if next_value == 0.0:
            updated.pop(need.value, None)
        else:
            updated[need.value] = next_value
        return DependencyNeedRegister(agent_id=self.agent_id, deficits=updated)


def require_care_need_id(value: object) -> CareNeedId:
    if type(value) is CareNeedId:
        return value
    if type(value) is not str:
        raise TypeError("need id must be str or CareNeedId")
    if value in FORBIDDEN_NEED_ALIASES:
        _LOGGER.error(
            "dependency_care_forbidden_need code=dependency_care_forbidden_need "
            "need=%s",
            value,
        )
        raise ValueError(
            f"forbidden need id {value!r} (code=dependency_care_forbidden_need)"
        )
    try:
        return CareNeedId(value)
    except ValueError as exc:
        _LOGGER.error(
            "dependency_care_unknown_need code=dependency_care_unknown_need need=%s",
            value,
        )
        raise ValueError(
            f"unknown need id {value!r} (code=dependency_care_unknown_need)"
        ) from exc


def require_care_need_policy(
    need: CareNeedId,
    policy: CareNeedPolicy,
) -> CareNeedPolicy:
    if type(policy) is not CareNeedPolicy:
        raise TypeError("policy must be CareNeedPolicy")
    allowed = ALLOWED_CRITICAL_CONSEQUENCES[need]
    if policy.critical_consequence not in allowed:
        _LOGGER.error(
            "dependency_care_consequence_invalid "
            "code=dependency_care_consequence_invalid need=%s consequence=%s",
            need.value,
            policy.critical_consequence,
        )
        raise ValueError(
            f"invalid critical_consequence {policy.critical_consequence!r} "
            f"for need {need.value!r} "
            "(code=dependency_care_consequence_invalid)"
        )
    return policy


def needs_requiring_assistance(
    status: DependencyStatus,
    policies: Mapping[CareNeedId, CareNeedPolicy],
) -> tuple[CareNeedId, ...]:
    """Return enabled needs that DEPENDENT agents cannot self-satisfy."""
    if type(status) is not DependencyStatus:
        raise TypeError("status must be DependencyStatus")
    if status is not DependencyStatus.DEPENDENT:
        return ()
    if isinstance(policies, (str, bytes)) or not isinstance(policies, Mapping):
        raise TypeError("policies must be a mapping")
    result: list[CareNeedId] = []
    for need in CareNeedId:
        policy = policies.get(need)
        if policy is None:
            continue
        if type(policy) is not CareNeedPolicy:
            raise TypeError("policies values must be CareNeedPolicy")
        if not policy.self_satisfy:
            result.append(need)
    ordered = tuple(result)
    _LOGGER.debug(
        "needs_requiring_assistance status=%s count=%s",
        status.value,
        len(ordered),
    )
    return ordered


def is_need_critical(
    *,
    deficit: float,
    policy: CareNeedPolicy,
) -> bool:
    if type(policy) is not CareNeedPolicy:
        raise TypeError("policy must be CareNeedPolicy")
    if isinstance(deficit, bool) or not isinstance(deficit, (int, float)):
        raise TypeError("deficit must be a number")
    value = float(deficit)
    if value < 0.0:
        raise ValueError("deficit must be non-negative")
    critical = value >= policy.critical_threshold
    _LOGGER.debug(
        "is_need_critical deficit=%s threshold=%s critical=%s",
        value,
        policy.critical_threshold,
        critical,
    )
    return critical


def self_satisfy_denied_kinds(
    status: DependencyStatus,
    enabled_needs: Sequence[CareNeedId],
    policies: Mapping[CareNeedId, CareNeedPolicy],
) -> frozenset[str]:
    """Command kinds denied for DEPENDENT agents when self_satisfy is false.

    Compose with stage ``denied_command_kinds`` via set union at admission time.
    ``INDEPENDENT`` agents are never denied by this map.
    """
    if type(status) is not DependencyStatus:
        raise TypeError("status must be DependencyStatus")
    if status is not DependencyStatus.DEPENDENT:
        return frozenset()
    if isinstance(enabled_needs, (str, bytes)) or not isinstance(
        enabled_needs, Sequence
    ):
        raise TypeError("enabled_needs must be a sequence")
    denied: set[str] = set()
    for raw_need in enabled_needs:
        need = require_care_need_id(raw_need)
        policy = policies.get(need)
        if policy is None:
            continue
        if type(policy) is not CareNeedPolicy:
            raise TypeError("policies values must be CareNeedPolicy")
        if policy.self_satisfy:
            continue
        kinds = SELF_SATISFY_DENIED_KINDS[need]
        if kinds:
            denied.update(kinds)
            _LOGGER.debug(
                "self_satisfy_denied need=%s kinds=%s code=%s",
                need.value,
                sorted(kinds),
                _SELF_SATISFY_DENIAL_CODE,
            )
    return frozenset(denied)


def care_action_legal(
    *,
    assist_kind: CareAssistKind | str,
    allow_feed: bool,
    allow_transport: bool,
    allow_help_safety: bool,
    allow_teach_learning: bool,
    require_colocated: bool,
    colocated: bool,
    target_status: DependencyStatus,
) -> bool:
    """Whether a structured care assist is legal under policy (no kinship check)."""
    if type(assist_kind) is CareAssistKind:
        kind = assist_kind
    elif type(assist_kind) is str:
        try:
            kind = CareAssistKind(assist_kind)
        except ValueError:
            _LOGGER.error(
                "dependency_care_unknown_assist "
                "code=dependency_care_unknown_assist kind=%s",
                assist_kind,
            )
            return False
    else:
        raise TypeError("assist_kind must be CareAssistKind or str")
    if type(target_status) is not DependencyStatus:
        raise TypeError("target_status must be DependencyStatus")
    if target_status is not DependencyStatus.DEPENDENT:
        return False
    allowed = {
        CareAssistKind.FEED: allow_feed,
        CareAssistKind.TRANSPORT: allow_transport,
        CareAssistKind.HELP_SAFETY: allow_help_safety,
        CareAssistKind.TEACH_LEARNING: allow_teach_learning,
    }[kind]
    if not allowed:
        return False
    if require_colocated and not colocated:
        return False
    return True


def empty_need_register(agent_id: AgentId) -> DependencyNeedRegister:
    return DependencyNeedRegister(agent_id=agent_id, deficits={})


def require_register_tick(name: str, value: object) -> int:
    """Validate non-negative tick for register accrual bookkeeping."""
    return require_exact_nonneg_int(name, value)


@dataclass(frozen=True, slots=True)
class UnmetNeedTickEffect:
    """Deterministic per-tick objective extras for one DEPENDENT body."""

    body_id: object  # EntityId — typed loosely to avoid import cycles in helpers
    hunger_extra: float = 0.0
    thirst_extra: float = 0.0
    health_damage_extra: float = 0.0
    fatigue_extra: float = 0.0
    learning_deficit_delta: float = 0.0
    movement_deficit_delta: float = 0.0
    learning_rate_zero: bool = False
    critical_needs: tuple[str, ...] = ()


def compute_unmet_tick_effects(
    *,
    body_id: object,
    status: DependencyStatus,
    enabled_needs: Sequence[CareNeedId],
    policies: Mapping[CareNeedId, CareNeedPolicy],
    hunger: float,
    thirst: float,
    health: float,
    fatigue: float,
    shelter_factor: float,
    learning_deficit: float = 0.0,
    movement_deficit: float = 0.0,
) -> UnmetNeedTickEffect:
    """Compute physiology extras and register deltas for one DEPENDENT agent.

    INDEPENDENT agents return zero extras. Accrual is seed-free given inputs.
    """
    if type(status) is not DependencyStatus:
        raise TypeError("status must be DependencyStatus")
    if status is not DependencyStatus.DEPENDENT:
        return UnmetNeedTickEffect(body_id=body_id)
    hunger_extra = 0.0
    thirst_extra = 0.0
    health_damage_extra = 0.0
    fatigue_extra = 0.0
    learning_delta = 0.0
    movement_delta = 0.0
    learning_rate_zero = False
    critical: list[str] = []
    for raw_need in enabled_needs:
        need = require_care_need_id(raw_need)
        policy = policies.get(need)
        if policy is None:
            continue
        if type(policy) is not CareNeedPolicy:
            raise TypeError("policies values must be CareNeedPolicy")
        if need is CareNeedId.FOOD:
            deficit = min(1.0, max(0.0, hunger / 100.0))
            hunger_extra += policy.unmet_accrual_per_tick * 100.0
            if is_need_critical(deficit=deficit, policy=policy):
                critical.append(need.value)
                if policy.critical_consequence == "accelerate_hunger":
                    hunger_extra += policy.unmet_accrual_per_tick * 100.0
                elif policy.critical_consequence == "health_damage":
                    health_damage_extra += 1.0
                # death_when_physiology_terminal reuses existing death path
        elif need is CareNeedId.WATER:
            deficit = min(1.0, max(0.0, thirst / 100.0))
            thirst_extra += policy.unmet_accrual_per_tick * 100.0
            if is_need_critical(deficit=deficit, policy=policy):
                critical.append(need.value)
                if policy.critical_consequence == "accelerate_thirst":
                    thirst_extra += policy.unmet_accrual_per_tick * 100.0
                elif policy.critical_consequence == "health_damage":
                    health_damage_extra += 1.0
        elif need is CareNeedId.SAFETY:
            deficit = min(1.0, max(0.0, 1.0 - (health / 100.0)))
            if is_need_critical(deficit=deficit, policy=policy):
                critical.append(need.value)
                if policy.critical_consequence == "health_damage":
                    health_damage_extra += policy.unmet_accrual_per_tick * 10.0
        elif need is CareNeedId.SHELTER:
            deficit = min(1.0, max(0.0, 1.0 - float(shelter_factor)))
            if is_need_critical(deficit=deficit, policy=policy):
                critical.append(need.value)
                if policy.critical_consequence == "fatigue_accrual":
                    fatigue_extra += policy.unmet_accrual_per_tick * 100.0
                elif policy.critical_consequence == "health_damage":
                    health_damage_extra += policy.unmet_accrual_per_tick * 10.0
            else:
                # Unmet shelter still accrues mild fatigue when self_satisfy false.
                if not policy.self_satisfy and float(shelter_factor) < 1.0:
                    fatigue_extra += policy.unmet_accrual_per_tick * 50.0
        elif need is CareNeedId.LEARNING:
            next_deficit = min(
                1.0, float(learning_deficit) + policy.unmet_accrual_per_tick
            )
            learning_delta = next_deficit - float(learning_deficit)
            if is_need_critical(deficit=next_deficit, policy=policy):
                critical.append(need.value)
                if policy.critical_consequence == "learning_rate_zero":
                    learning_rate_zero = True
        elif need is CareNeedId.MOVEMENT:
            next_deficit = min(
                1.0, float(movement_deficit) + policy.unmet_accrual_per_tick
            )
            movement_delta = next_deficit - float(movement_deficit)
            if is_need_critical(deficit=next_deficit, policy=policy):
                critical.append(need.value)
        _LOGGER.debug(
            "unmet_need_resolve agent_need=%s deficit_hint_logged=1 critical=%s",
            need.value,
            need.value in critical,
        )
    effect = UnmetNeedTickEffect(
        body_id=body_id,
        hunger_extra=hunger_extra,
        thirst_extra=thirst_extra,
        health_damage_extra=health_damage_extra,
        fatigue_extra=fatigue_extra,
        learning_deficit_delta=learning_delta,
        movement_deficit_delta=movement_delta,
        learning_rate_zero=learning_rate_zero,
        critical_needs=tuple(critical),
    )
    if effect.critical_needs:
        _LOGGER.info(
            "dependency_care_critical body_id=%s needs=%s",
            getattr(body_id, "value", body_id),
            list(effect.critical_needs),
        )
    return effect
