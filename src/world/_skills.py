"""Objective skill levels folded from committed events.

Only ``WorldEngine`` reads this ledger, and only while resolving an action
that already has a probability or an efficiency constant. This module does
not import agents or cognition.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import EntityId
from world.values import clamp_unit_interval

_LOG: Final[logging.Logger] = logging.getLogger("world._skills")

OBJECTIVE_SKILL_POLICY_VERSION: Final[str] = "objective-skill-v1"
_SKILL_QUANTUM: Final[float] = 1e-6


class SkillDomain(StrEnum):
    """Closed skill tokens. There is no profession, role, or culture label."""

    FORAGING = "foraging"
    NAVIGATION = "navigation"
    RESOURCE_DETECTION = "resource_detection"
    CRAFTING = "crafting"
    BUILDING = "building"
    HEALING = "healing"
    COMMUNICATION = "communication"
    TEACHING = "teaching"


class SkillGrowthChannel(StrEnum):
    """One committed-fact channel. The fold sums these before it quantizes."""

    PRACTICE = "practice"
    SUCCESS = "success"
    FAILURE = "failure"
    INSTRUCTION = "instruction"
    OBSERVATION = "observation"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "objective_skill_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _quantize(value: float) -> float:
    return round(value / _SKILL_QUANTUM) * _SKILL_QUANTUM


def _finite_number(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _nonnegative_rate(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number < 0.0:
        raise _fail(field_name, "negative_rate")
    return number


def _unit_gain(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _require_level(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _require_domain(value: object) -> SkillDomain:
    if type(value) is not SkillDomain:
        raise _fail("domain", "unknown_domain")
    return value


def _require_world_state(value: object) -> object:
    """Accept a world state without importing the private state module."""
    kind = type(value)
    if kind.__module__ != "world._state" or kind.__name__ != "WorldState":
        raise TypeError("world_state must be WorldState")
    return value


def _clamp_quantized(value: float) -> float:
    quantized = _quantize(value)
    if quantized < 0.0:
        return 0.0
    if quantized > 1.0:
        return 1.0
    return float(quantized)


@dataclass(frozen=True, slots=True)
class SkillEfficiencyOverride:
    """Per-actor costs already adjusted. Absent means the caller uses rules."""

    move_fatigue: float
    flee_fatigue: float
    help_health_gain: float


@dataclass(frozen=True, slots=True)
class ObjectiveSkillPolicy:
    """Locked objective rates. Version ``objective-skill-v1``."""

    practice_rate: float = 0.02
    success_rate: float = 0.05
    failure_rate: float = 0.01
    instruction_rate: float = 0.04
    observation_rate: float = 0.01
    probability_gain: float = 0.50
    efficiency_gain: float = 0.50
    version: str = OBJECTIVE_SKILL_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.version != OBJECTIVE_SKILL_POLICY_VERSION:
            raise _fail("version", "unsupported_version")
        object.__setattr__(
            self,
            "practice_rate",
            _nonnegative_rate("practice_rate", self.practice_rate),
        )
        object.__setattr__(
            self, "success_rate", _nonnegative_rate("success_rate", self.success_rate)
        )
        object.__setattr__(
            self, "failure_rate", _nonnegative_rate("failure_rate", self.failure_rate)
        )
        object.__setattr__(
            self,
            "instruction_rate",
            _nonnegative_rate("instruction_rate", self.instruction_rate),
        )
        object.__setattr__(
            self,
            "observation_rate",
            _nonnegative_rate("observation_rate", self.observation_rate),
        )
        object.__setattr__(
            self,
            "probability_gain",
            _unit_gain("probability_gain", self.probability_gain),
        )
        object.__setattr__(
            self,
            "efficiency_gain",
            _unit_gain("efficiency_gain", self.efficiency_gain),
        )
        _LOG.debug(
            "objective_skill_policy_built policy_version=%s domain_count=%s",
            self.version,
            len(SkillDomain),
        )


def default_objective_skill_policy() -> ObjectiveSkillPolicy:
    """Locked objective defaults."""
    return ObjectiveSkillPolicy()


@dataclass(frozen=True, slots=True)
class _EntitySkillLevels:
    entity_id: EntityId
    levels: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ObjectiveSkillLedger:
    """Entity id to eight quantized levels. Absent entities are not enabled."""

    _entries: tuple[_EntitySkillLevels, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self._entries, (str, bytes, set, frozenset)) or not isinstance(
            self._entries, tuple
        ):
            raise _fail("entries", "invalid_type")
        seen: set[EntityId] = set()
        normalized: list[_EntitySkillLevels] = []
        for entry in self._entries:
            if type(entry) is not _EntitySkillLevels:
                raise _fail("entries", "invalid_type")
            if type(entry.entity_id) is not EntityId:
                raise _fail("entity_id", "invalid_type")
            if entry.entity_id in seen:
                raise _fail("entity_id", "duplicate_entity")
            seen.add(entry.entity_id)
            if len(entry.levels) != len(SkillDomain):
                raise _fail("levels", "unknown_domain")
            levels: list[float] = []
            for index, level in enumerate(entry.levels):
                levels.append(_require_level(f"level.{index}", level))
            normalized.append(
                _EntitySkillLevels(entity_id=entry.entity_id, levels=tuple(levels))
            )
        object.__setattr__(self, "_entries", tuple(normalized))

    @classmethod
    def bootstrap(cls, entity_ids: Sequence[EntityId]) -> ObjectiveSkillLedger:
        """Every domain on every enabled body starts at ``0``."""
        if isinstance(entity_ids, (str, bytes, set, frozenset)) or not isinstance(
            entity_ids, Sequence
        ):
            raise _fail("entity_ids", "invalid_type")
        zeros = tuple(0.0 for _ in SkillDomain)
        entries = tuple(
            _EntitySkillLevels(entity_id=entity_id, levels=zeros)
            for entity_id in entity_ids
        )
        return cls(entries)

    def entity_ids(self) -> tuple[EntityId, ...]:
        return tuple(entry.entity_id for entry in self._entries)

    def level(self, entity_id: EntityId, domain: SkillDomain) -> float:
        """Return the start-of-tick level. Missing rows fail closed."""
        if type(entity_id) is not EntityId:
            raise _fail("entity_id", "invalid_type")
        checked = _require_domain(domain)
        for entry in self._entries:
            if entry.entity_id == entity_id:
                return entry.levels[list(SkillDomain).index(checked)]
        raise _fail("entity_id", "missing_entity")

    def apply_summed_deltas(
        self,
        additions: Mapping[EntityId, Mapping[SkillDomain, float]],
    ) -> ObjectiveSkillLedger:
        """Quantize each summed delta once, then clamp into ``[0, 1]``."""
        if not isinstance(additions, Mapping):
            raise _fail("additions", "invalid_type")
        by_entity = {entry.entity_id: entry.levels for entry in self._entries}
        updated = dict(by_entity)
        for entity_id, domain_deltas in additions.items():
            if type(entity_id) is not EntityId:
                raise _fail("entity_id", "invalid_type")
            current = by_entity.get(entity_id)
            if current is None:
                _LOG.debug(
                    "skill_growth_dropped entity_id=%s reason_code=actor_disabled",
                    entity_id.value,
                )
                continue
            if not isinstance(domain_deltas, Mapping):
                raise _fail("additions", "invalid_type")
            levels = list(current)
            domains = list(SkillDomain)
            for domain, delta in domain_deltas.items():
                checked = _require_domain(domain)
                amount = _finite_number("delta", delta)
                index = domains.index(checked)
                levels[index] = _clamp_quantized(levels[index] + amount)
            updated[entity_id] = tuple(levels)
        entries = tuple(
            _EntitySkillLevels(
                entity_id=entry.entity_id, levels=updated[entry.entity_id]
            )
            for entry in self._entries
        )
        return ObjectiveSkillLedger(entries)


def growth_delta(
    channel: SkillGrowthChannel,
    policy: ObjectiveSkillPolicy,
    *,
    teacher_teaching_level: float = 0.0,
) -> float:
    """One channel's unquantized contribution. Success still adds practice."""
    if type(channel) is not SkillGrowthChannel:
        raise _fail("channel", "unknown_channel")
    if type(policy) is not ObjectiveSkillPolicy:
        raise TypeError("policy must be ObjectiveSkillPolicy")
    if channel is SkillGrowthChannel.PRACTICE:
        return policy.practice_rate
    if channel is SkillGrowthChannel.SUCCESS:
        return policy.success_rate
    if channel is SkillGrowthChannel.FAILURE:
        return policy.failure_rate
    if channel is SkillGrowthChannel.OBSERVATION:
        return policy.observation_rate
    teaching = _require_level("teacher_teaching_level", teacher_teaching_level)
    return policy.instruction_rate * teaching


def adjusted_search_probability(
    *,
    search_base_probability: float,
    search_visibility_weight: float,
    visibility: float,
    foraging_level: float,
    resource_detection_level: float,
    policy: ObjectiveSkillPolicy,
) -> float:
    """Foraging scales the base term. Detection scales only the visibility term.

    At level ``0`` this equals today's search formula:
    base probability plus the visibility weight times visibility, clamped.
    """
    if type(policy) is not ObjectiveSkillPolicy:
        raise TypeError("policy must be ObjectiveSkillPolicy")
    base_probability = _finite_number(
        "search_base_probability", search_base_probability
    )
    visibility_weight = _finite_number(
        "search_visibility_weight", search_visibility_weight
    )
    visible = _finite_number("visibility", visibility)
    foraging = _require_level("foraging_level", foraging_level)
    detection = _require_level("resource_detection_level", resource_detection_level)
    base_term = base_probability * (1.0 + policy.probability_gain * foraging)
    visibility_term = (
        visibility_weight * visible * (1.0 + policy.probability_gain * detection)
    )
    return clamp_unit_interval(base_term + visibility_term)


def adjusted_move_fatigue(
    move_fatigue: float,
    navigation_level: float,
    policy: ObjectiveSkillPolicy,
) -> float:
    """Divide move fatigue before ``round_physical``. Level ``0`` is identity."""
    return _adjusted_fatigue("move_fatigue", move_fatigue, navigation_level, policy)


def adjusted_flee_fatigue(
    flee_fatigue: float,
    navigation_level: float,
    policy: ObjectiveSkillPolicy,
) -> float:
    """Divide flee fatigue before ``round_physical``. Level ``0`` is identity."""
    return _adjusted_fatigue("flee_fatigue", flee_fatigue, navigation_level, policy)


def adjusted_help_gain(
    help_health_gain: float,
    healing_level: float,
    policy: ObjectiveSkillPolicy,
) -> float:
    """Multiply help health gain before ``round_physical``. Level ``0`` is identity."""
    if type(policy) is not ObjectiveSkillPolicy:
        raise TypeError("policy must be ObjectiveSkillPolicy")
    gain = _finite_number("help_health_gain", help_health_gain)
    healing = _require_level("healing_level", healing_level)
    return gain * (1.0 + policy.efficiency_gain * healing)


def _adjusted_fatigue(
    field_name: str,
    fatigue: float,
    navigation_level: float,
    policy: ObjectiveSkillPolicy,
) -> float:
    if type(policy) is not ObjectiveSkillPolicy:
        raise TypeError("policy must be ObjectiveSkillPolicy")
    amount = _finite_number(field_name, fatigue)
    navigation = _require_level("navigation_level", navigation_level)
    return amount / (1.0 + policy.efficiency_gain * navigation)


@dataclass(frozen=True, slots=True)
class SkillGrowthInput:
    """One batch item, or one of its committed event details, at tick start."""

    actor_id: EntityId
    status: str
    action_kind: str
    details: object | None = None
    origin_location_id: EntityId | None = None
    untargeted_search: bool | None = None

    def __post_init__(self) -> None:
        if type(self.actor_id) is not EntityId:
            raise _fail("actor_id", "invalid_type")
        if type(self.status) is not str or not self.status:
            raise _fail("status", "invalid_type")
        if type(self.action_kind) is not str or not self.action_kind:
            raise _fail("action_kind", "invalid_type")
        if (
            self.origin_location_id is not None
            and type(self.origin_location_id) is not EntityId
        ):
            raise _fail("origin_location_id", "invalid_type")
        if (
            self.untargeted_search is not None
            and type(self.untargeted_search) is not bool
        ):
            raise _fail("untargeted_search", "invalid_type")


def fold_skill_growth(
    ledger: ObjectiveSkillLedger,
    applied_actions: Sequence[object],
    policy: ObjectiveSkillPolicy,
    *,
    world_state: object,
    tick: int,
    rules: object,
) -> ObjectiveSkillLedger:
    """Sum this tick's channels from the start-of-tick state, then quantize once.

    Same-tick moves do not change the witness set. ``crafting`` and ``building``
    grow only through instruction. Attack adds nothing.
    """
    from world.models import PhysicalRules

    if type(ledger) is not ObjectiveSkillLedger:
        raise TypeError("ledger must be ObjectiveSkillLedger")
    if type(policy) is not ObjectiveSkillPolicy:
        raise TypeError("policy must be ObjectiveSkillPolicy")
    _require_world_state(world_state)
    if type(rules) is not PhysicalRules:
        raise TypeError("rules must be PhysicalRules")
    if isinstance(tick, bool) or type(tick) is not int:
        raise _fail("tick", "invalid_type")
    if isinstance(applied_actions, (str, bytes)) or not isinstance(
        applied_actions, Sequence
    ):
        raise TypeError("applied_actions must be an ordered sequence")
    sums: dict[EntityId, dict[SkillDomain, float]] = {}
    for action in applied_actions:
        if type(action) is not SkillGrowthInput:
            raise TypeError("applied_actions entries must be SkillGrowthInput")
        _fold_one(
            action,
            ledger=ledger,
            policy=policy,
            world_state=world_state,
            tick=tick,
            rules=rules,
            sums=sums,
        )
    return ledger.apply_summed_deltas(sums)


def _fold_one(
    action: SkillGrowthInput,
    *,
    ledger: ObjectiveSkillLedger,
    policy: ObjectiveSkillPolicy,
    world_state: object,
    tick: int,
    rules: object,
    sums: dict[EntityId, dict[SkillDomain, float]],
) -> None:
    from world.events import (
        Asked,
        Attacked,
        Fled,
        Helped,
        Moved,
        Searched,
        Talked,
        Told,
    )
    from world.models import PhysicalRules

    _require_world_state(world_state)
    assert type(rules) is PhysicalRules
    if action.status != "applied":
        if action.status == "rejected":
            _drop(tick, action.actor_id, "rejected")
        return
    details = action.details
    if type(details) is Attacked or details is None:
        return
    if type(details) is Searched:
        if action.untargeted_search is True:
            domain = SkillDomain.FORAGING
        elif action.untargeted_search is False:
            domain = SkillDomain.RESOURCE_DETECTION
        else:
            domain = (
                SkillDomain.FORAGING
                if details.target_id is None
                else SkillDomain.RESOURCE_DETECTION
            )
        _practice_outcome(
            action.actor_id,
            domain,
            success=details.success,
            ledger=ledger,
            policy=policy,
            world_state=world_state,
            tick=tick,
            sums=sums,
        )
        if details.success is True:
            _observe_public(
                action,
                domain,
                ledger=ledger,
                policy=policy,
                world_state=world_state,
                tick=tick,
                rules=rules,
                sums=sums,
            )
        return
    if type(details) is Fled:
        _practice_outcome(
            action.actor_id,
            SkillDomain.NAVIGATION,
            success=details.success,
            ledger=ledger,
            policy=policy,
            world_state=world_state,
            tick=tick,
            sums=sums,
        )
        if details.success is True:
            _observe_public(
                action,
                SkillDomain.NAVIGATION,
                ledger=ledger,
                policy=policy,
                world_state=world_state,
                tick=tick,
                rules=rules,
                sums=sums,
            )
        return
    if type(details) is Moved or type(details) is Helped:
        domain = (
            SkillDomain.NAVIGATION if type(details) is Moved else SkillDomain.HEALING
        )
        _add_channel(
            action.actor_id,
            domain,
            SkillGrowthChannel.PRACTICE,
            policy.practice_rate,
            ledger=ledger,
            world_state=world_state,
            tick=tick,
            sums=sums,
        )
        _add_channel(
            action.actor_id,
            domain,
            SkillGrowthChannel.SUCCESS,
            policy.success_rate,
            ledger=ledger,
            world_state=world_state,
            tick=tick,
            sums=sums,
        )
        _observe_public(
            action,
            domain,
            ledger=ledger,
            policy=policy,
            world_state=world_state,
            tick=tick,
            rules=rules,
            sums=sums,
        )
        return
    if type(details) is Talked or type(details) is Asked or type(details) is Told:
        _fold_utterance(
            action,
            details,
            ledger=ledger,
            policy=policy,
            world_state=world_state,
            tick=tick,
            sums=sums,
        )


def _fold_utterance(
    action: SkillGrowthInput,
    details: object,
    *,
    ledger: ObjectiveSkillLedger,
    policy: ObjectiveSkillPolicy,
    world_state: object,
    tick: int,
    sums: dict[EntityId, dict[SkillDomain, float]],
) -> None:
    from world.events import Asked, Talked, Told

    assert type(details) is Talked or type(details) is Asked or type(details) is Told
    _drop(tick, action.actor_id, "private_utterance")
    _add_channel(
        action.actor_id,
        SkillDomain.COMMUNICATION,
        SkillGrowthChannel.PRACTICE,
        policy.practice_rate,
        ledger=ledger,
        world_state=world_state,
        tick=tick,
        sums=sums,
    )
    _add_channel(
        action.actor_id,
        SkillDomain.COMMUNICATION,
        SkillGrowthChannel.SUCCESS,
        policy.success_rate,
        ledger=ledger,
        world_state=world_state,
        tick=tick,
        sums=sums,
    )
    instructed = _instruction_domain(details.utterance, tick, action.actor_id)
    if instructed is None:
        return
    _add_channel(
        action.actor_id,
        SkillDomain.TEACHING,
        SkillGrowthChannel.PRACTICE,
        policy.practice_rate,
        ledger=ledger,
        world_state=world_state,
        tick=tick,
        sums=sums,
    )
    _add_channel(
        action.actor_id,
        SkillDomain.TEACHING,
        SkillGrowthChannel.SUCCESS,
        policy.success_rate,
        ledger=ledger,
        world_state=world_state,
        tick=tick,
        sums=sums,
    )
    listener = details.recipient_id
    teaching = _start_level(ledger, action.actor_id, SkillDomain.TEACHING)
    _add_channel(
        listener,
        instructed,
        SkillGrowthChannel.INSTRUCTION,
        policy.instruction_rate * teaching,
        ledger=ledger,
        world_state=world_state,
        tick=tick,
        sums=sums,
    )


def _instruction_domain(
    utterance: object, tick: int, actor_id: EntityId
) -> SkillDomain | None:
    from world.communications import StructuredUtterance

    if type(utterance) is not StructuredUtterance:
        _drop(tick, actor_id, "not_instruction")
        return None
    relations = tuple(utterance.content.relations)
    if len(relations) != 1 or relations[0].predicate != "instruct":
        _drop(tick, actor_id, "not_instruction")
        return None
    token = relations[0].object
    try:
        return SkillDomain(token)
    except ValueError:
        _drop(tick, actor_id, "unknown_domain")
        return None


def _practice_outcome(
    actor_id: EntityId,
    domain: SkillDomain,
    *,
    success: bool | None,
    ledger: ObjectiveSkillLedger,
    policy: ObjectiveSkillPolicy,
    world_state: object,
    tick: int,
    sums: dict[EntityId, dict[SkillDomain, float]],
) -> None:
    if type(success) is not bool:
        return
    _add_channel(
        actor_id,
        domain,
        SkillGrowthChannel.PRACTICE,
        policy.practice_rate,
        ledger=ledger,
        world_state=world_state,
        tick=tick,
        sums=sums,
    )
    channel = SkillGrowthChannel.SUCCESS if success else SkillGrowthChannel.FAILURE
    rate = policy.success_rate if success else policy.failure_rate
    _add_channel(
        actor_id,
        domain,
        channel,
        rate,
        ledger=ledger,
        world_state=world_state,
        tick=tick,
        sums=sums,
    )


def _observe_public(
    action: SkillGrowthInput,
    domain: SkillDomain,
    *,
    ledger: ObjectiveSkillLedger,
    policy: ObjectiveSkillPolicy,
    world_state: object,
    tick: int,
    rules: object,
    sums: dict[EntityId, dict[SkillDomain, float]],
) -> None:
    from world.models import LifeStatus, PhysicalRules
    from world.values import WeatherCondition

    _require_world_state(world_state)
    assert type(rules) is PhysicalRules
    origin = action.origin_location_id
    if origin is None or origin not in world_state.locations:
        return
    location = world_state.locations[origin]
    weather = world_state.weather.get(origin)
    condition = weather.condition if weather is not None else WeatherCondition.CLEAR
    visibility = rules.effective_visibility(
        location_visibility=location.visibility_factor.value,
        phase=rules.day_phase_for_tick(tick),
        condition=condition,
    )
    if visibility < 0.5:
        _drop(tick, action.actor_id, "not_visible")
        return
    for body in world_state.bodies.values():
        if body.entity_id == action.actor_id or body.location_id != origin:
            continue
        if body.life_status is not LifeStatus.ALIVE:
            continue
        _add_channel(
            body.entity_id,
            domain,
            SkillGrowthChannel.OBSERVATION,
            policy.observation_rate,
            ledger=ledger,
            world_state=world_state,
            tick=tick,
            sums=sums,
        )


def _add_channel(
    entity_id: EntityId,
    domain: SkillDomain,
    channel: SkillGrowthChannel,
    delta: float,
    *,
    ledger: ObjectiveSkillLedger,
    world_state: object,
    tick: int,
    sums: dict[EntityId, dict[SkillDomain, float]],
) -> None:
    from world.models import LifeStatus

    _require_world_state(world_state)
    if entity_id not in ledger.entity_ids():
        _drop(tick, entity_id, "actor_disabled")
        return
    body = world_state.bodies.get(entity_id)
    if body is None or body.life_status is not LifeStatus.ALIVE:
        return
    _LOG.debug(
        "skill_growth tick=%s entity_id=%s domain=%s channel=%s delta=%s",
        tick,
        entity_id.value,
        domain.value,
        channel.value,
        delta,
    )
    domains = sums.setdefault(entity_id, {})
    domains[domain] = domains.get(domain, 0.0) + delta


def _start_level(
    ledger: ObjectiveSkillLedger, entity_id: EntityId, domain: SkillDomain
) -> float:
    if entity_id not in ledger.entity_ids():
        return 0.0
    return ledger.level(entity_id, domain)


def _drop(tick: int, entity_id: EntityId, reason_code: str) -> None:
    _LOG.debug(
        "skill_growth_dropped tick=%s entity_id=%s reason_code=%s",
        tick,
        entity_id.value,
        reason_code,
    )


def _untargeted_request_ids(value: object | None) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, (str, bytes)) or not isinstance(value, frozenset):
        raise TypeError("untargeted_request_ids must be a frozenset of request ids")
    checked: set[str] = set()
    for item in value:
        if type(item) is not str or not item:
            raise TypeError("untargeted_request_ids entries must be request ids")
        checked.add(item)
    return frozenset(checked)


def refold_objective_ledger(
    initial_state: object,
    events: Sequence[object],
    policy: ObjectiveSkillPolicy,
    entity_ids: Sequence[EntityId],
    *,
    rules: object,
    expected_run_id: str,
    expected_world_id: object,
    project_prefix: object,
    untargeted_request_ids: object | None = None,
) -> ObjectiveSkillLedger:
    """Rebuild levels by folding each tick against that tick's start state.

    Projects only earlier ticks before witnesses are chosen, so a move in tick
    T does not change who can see T. ``project_prefix`` is supplied by the
    simulation engine so this module does not import the private replay module.
    ``untargeted_request_ids`` marks searches whose command had no target.
    A committed search still stores the found resource, so the command flag
    is the only signal that the domain is foraging.
    """
    from world.effects import ActionCause
    from world.events import Searched, WorldEvent
    from world.identifiers import WorldId
    from world.models import PhysicalRules

    _require_world_state(initial_state)
    if not callable(project_prefix):
        raise TypeError("project_prefix must be callable")
    untargeted_ids = _untargeted_request_ids(untargeted_request_ids)
    if type(policy) is not ObjectiveSkillPolicy:
        raise TypeError("policy must be ObjectiveSkillPolicy")
    if type(rules) is not PhysicalRules:
        raise TypeError("rules must be PhysicalRules")
    if type(expected_world_id) is not WorldId:
        raise TypeError("expected_world_id must be WorldId")
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("events must be an ordered sequence")
    if isinstance(entity_ids, (str, bytes, set, frozenset)) or not isinstance(
        entity_ids, Sequence
    ):
        raise TypeError("entity_ids must be an ordered sequence")
    ledger = ObjectiveSkillLedger.bootstrap(tuple(entity_ids))
    state = initial_state
    prior: list[WorldEvent] = []
    for tick, group in _event_groups(events):
        facts: list[SkillGrowthInput] = []
        for event in group:
            if type(event.cause) is not ActionCause or event.actor_id is None:
                continue
            occurrence = event.occurrence
            origin = None if occurrence is None else occurrence.origin_location_id
            untargeted = None
            if type(event.details) is Searched:
                request_id = event.request_id.value
                if request_id in untargeted_ids:
                    untargeted = True
                else:
                    untargeted = event.details.target_id is None
            facts.append(
                SkillGrowthInput(
                    actor_id=event.actor_id,
                    status="applied",
                    action_kind=getattr(event.details, "kind", "action"),
                    details=event.details,
                    origin_location_id=origin,
                    untargeted_search=untargeted,
                )
            )
        ledger = fold_skill_growth(
            ledger,
            tuple(facts),
            policy,
            world_state=state,
            tick=tick,
            rules=rules,
        )
        prior.extend(group)
        state = project_prefix(
            initial_state,
            tuple(prior),
            expected_run_id,
            expected_world_id,
        )
    return ledger


def _event_groups(
    events: Sequence[object],
) -> tuple[tuple[int, tuple[object, ...]], ...]:
    from world.events import WorldEvent

    groups: list[tuple[int, tuple[object, ...]]] = []
    current_tick: int | None = None
    bucket: list[WorldEvent] = []
    for event in events:
        if type(event) is not WorldEvent:
            raise TypeError("events entries must be WorldEvent")
        if current_tick is None or event.tick != current_tick:
            if bucket and current_tick is not None:
                groups.append((current_tick, tuple(bucket)))
            current_tick = event.tick
            bucket = [event]
        else:
            bucket.append(event)
    if bucket and current_tick is not None:
        groups.append((current_tick, tuple(bucket)))
    return tuple(groups)


def skill_ledger_mismatch(
    supplied: ObjectiveSkillLedger, refolded: ObjectiveSkillLedger
) -> tuple[EntityId, SkillDomain] | None:
    """Return the first entity and domain whose levels disagree."""
    if type(supplied) is not ObjectiveSkillLedger:
        raise TypeError("skill_ledger must be ObjectiveSkillLedger")
    if type(refolded) is not ObjectiveSkillLedger:
        raise TypeError("skill_ledger must be ObjectiveSkillLedger")
    if supplied.entity_ids() != refolded.entity_ids():
        left = set(supplied.entity_ids())
        right = set(refolded.entity_ids())
        missing = sorted(left.symmetric_difference(right), key=lambda item: item.value)
        entity_id = missing[0] if missing else EntityId("unknown")
        return entity_id, SkillDomain.FORAGING
    for entity_id in supplied.entity_ids():
        for domain in SkillDomain:
            if supplied.level(entity_id, domain) != refolded.level(entity_id, domain):
                return entity_id, domain
    return None
