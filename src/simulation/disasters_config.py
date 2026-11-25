"""Exact opt-in runner configuration seam for objective disasters."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from world.disasters import (
    DISASTER_RULE_ID_PATTERN,
    DISASTERS_POLICY_ID,
    MAX_DISASTER_CHANCE_PPM,
    MAX_DISASTER_RULES,
    MAX_DISASTER_STRENGTH_TENTHS,
    MAX_SURGE_OPPORTUNITY_MILLI,
    MIN_DISASTER_RULES,
    MIN_DISASTER_STRENGTH_TENTHS,
    MIN_SURGE_OPPORTUNITY_MILLI,
    DisasterCollapseEffect,
    DisasterEffect,
    DisasterInfrastructureEffect,
    DisasterInfrastructureTarget,
    DisasterKind,
    DisasterLocationTarget,
    DisasterLossEffect,
    DisasterResourceTarget,
    DisasterRule,
    DisasterScheduleEntry,
    DisasterSurgeEffect,
    DisasterTarget,
)
from world.identifiers import EntityId
from world.infrastructure import (
    InfrastructureKind,
    InfrastructureTopology,
    catalog_row,
)
from world.values import ResourceKind

__all__ = [
    "DISASTERS_KEY",
    "DISASTERS_POLICY_ID",
    "DisastersConfigError",
    "DisastersSpec",
    "bind_disaster_targets",
    "decode_disasters",
    "encode_disasters",
    "policy_sha256_for_disasters",
]

_LOGGER: Final[logging.Logger] = logging.getLogger("simulation.disasters_config")

DISASTERS_KEY: Final[str] = "disasters"

_SPEC_KEYS: Final[frozenset[str]] = frozenset({"policy_id", "rules", "schedule"})
_RULE_KEYS: Final[frozenset[str]] = frozenset(
    {"rule_id", "kind", "chance_ppm", "target", "effect"}
)
_SCHEDULE_KEYS: Final[frozenset[str]] = frozenset({"tick", "rule_id"})
_RESOURCE_TARGET_KEYS: Final[frozenset[str]] = frozenset({"resource_id"})
_INFRA_TARGET_KEYS: Final[frozenset[str]] = frozenset(
    {"location_id", "endpoint_location_id", "infrastructure_kind"}
)
_LOCATION_TARGET_KEYS: Final[frozenset[str]] = frozenset({"location_id"})
_LOSS_EFFECT_KEYS: Final[frozenset[str]] = frozenset({"loss_tenths"})
_COLLAPSE_EFFECT_KEYS: Final[frozenset[str]] = frozenset({"capacity_damage_tenths"})
_EMPTY_EFFECT_KEYS: Final[frozenset[str]] = frozenset()
_SURGE_EFFECT_KEYS: Final[frozenset[str]] = frozenset({"extra_opportunity_milli"})

_STOCK_KINDS: Final[frozenset[DisasterKind]] = frozenset(
    {
        DisasterKind.FLOOD_LIKE,
        DisasterKind.FIRE,
        DisasterKind.DROUGHT,
        DisasterKind.RESOURCE_COLLAPSE,
    }
)
_KIND_RESOURCE_REQUIREMENTS: Final[Mapping[DisasterKind, frozenset[ResourceKind]]] = {
    DisasterKind.FLOOD_LIKE: frozenset({ResourceKind.FOOD}),
    DisasterKind.FIRE: frozenset({ResourceKind.FOOD, ResourceKind.MATERIAL}),
    DisasterKind.DROUGHT: frozenset({ResourceKind.WATER}),
    DisasterKind.RESOURCE_COLLAPSE: frozenset(
        {ResourceKind.FOOD, ResourceKind.WATER, ResourceKind.MATERIAL}
    ),
}


class DisastersConfigError(ValueError):
    """Strict configuration failure with a stable code and JSON-like path."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {code}")


def _fail(code: str, path: str) -> DisastersConfigError:
    _LOGGER.error(
        "disasters_config_invalid path=%s reason_code=%s",
        path,
        code,
    )
    return DisastersConfigError(code, path)


def _require_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("disasters_spec_invalid", path)
    return value


def _require_keys(value: dict[str, Any], keys: frozenset[str], path: str) -> None:
    if set(value) != keys:
        raise _fail("disasters_spec_invalid", path)


def _require_strict_int(
    value: object,
    *,
    path: str,
    code: str,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise _fail(code, path)
    if value < minimum or value > maximum:
        raise _fail(code, path)
    return value


def _require_entity_id(value: object, path: str) -> EntityId:
    try:
        if type(value) is EntityId:
            return value
        if type(value) is str:
            return EntityId(value)
    except (TypeError, ValueError) as exc:
        raise _fail("disaster_target_invalid", path) from exc
    raise _fail("disaster_target_invalid", path)


def _target_binding_key(
    kind: DisasterKind, target: DisasterTarget
) -> tuple[object, ...]:
    if isinstance(target, DisasterResourceTarget):
        return (kind.value, "resource", target.resource_id.value)
    if isinstance(target, DisasterInfrastructureTarget):
        endpoint = (
            None
            if target.endpoint_location_id is None
            else target.endpoint_location_id.value
        )
        return (
            kind.value,
            "infrastructure",
            target.location_id.value,
            endpoint,
            target.infrastructure_kind.value,
        )
    if isinstance(target, DisasterLocationTarget):
        return (kind.value, "location", target.location_id.value)
    raise TypeError("unsupported disaster target")


def _decode_target(kind: DisasterKind, raw: object, path: str) -> DisasterTarget:
    record = _require_mapping(raw, path)
    if kind in _STOCK_KINDS:
        _require_keys(record, _RESOURCE_TARGET_KEYS, path)
        return DisasterResourceTarget(
            resource_id=_require_entity_id(record["resource_id"], f"{path}.resource_id")
        )
    if kind is DisasterKind.INFRASTRUCTURE_DESTRUCTION:
        _require_keys(record, _INFRA_TARGET_KEYS, path)
        endpoint_raw = record["endpoint_location_id"]
        if endpoint_raw is None:
            endpoint: EntityId | None = None
        else:
            endpoint = _require_entity_id(
                endpoint_raw, f"{path}.endpoint_location_id"
            )
        kind_raw = record["infrastructure_kind"]
        if type(kind_raw) is not str:
            raise _fail(
                "disaster_infrastructure_kind_invalid",
                f"{path}.infrastructure_kind",
            )
        try:
            infrastructure_kind = InfrastructureKind(kind_raw)
        except ValueError as exc:
            raise _fail(
                "disaster_infrastructure_kind_invalid",
                f"{path}.infrastructure_kind",
            ) from exc
        return DisasterInfrastructureTarget(
            location_id=_require_entity_id(
                record["location_id"], f"{path}.location_id"
            ),
            endpoint_location_id=endpoint,
            infrastructure_kind=infrastructure_kind,
        )
    if kind is DisasterKind.EPIDEMIC_SURGE:
        _require_keys(record, _LOCATION_TARGET_KEYS, path)
        return DisasterLocationTarget(
            location_id=_require_entity_id(record["location_id"], f"{path}.location_id")
        )
    raise _fail("disaster_kind_invalid", path)


def _encode_target(target: DisasterTarget) -> dict[str, object]:
    if isinstance(target, DisasterResourceTarget):
        return {"resource_id": target.resource_id.value}
    if isinstance(target, DisasterInfrastructureTarget):
        return {
            "location_id": target.location_id.value,
            "endpoint_location_id": (
                None
                if target.endpoint_location_id is None
                else target.endpoint_location_id.value
            ),
            "infrastructure_kind": target.infrastructure_kind.value,
        }
    if isinstance(target, DisasterLocationTarget):
        return {"location_id": target.location_id.value}
    raise TypeError("unsupported disaster target")


def _decode_effect(kind: DisasterKind, raw: object, path: str) -> DisasterEffect:
    record = _require_mapping(raw, path)
    if kind in {
        DisasterKind.FLOOD_LIKE,
        DisasterKind.FIRE,
        DisasterKind.DROUGHT,
    }:
        _require_keys(record, _LOSS_EFFECT_KEYS, path)
        return DisasterLossEffect(
            loss_tenths=_require_strict_int(
                record["loss_tenths"],
                path=f"{path}.loss_tenths",
                code="disaster_effect_strength_invalid",
                minimum=MIN_DISASTER_STRENGTH_TENTHS,
                maximum=MAX_DISASTER_STRENGTH_TENTHS,
            )
        )
    if kind is DisasterKind.RESOURCE_COLLAPSE:
        _require_keys(record, _COLLAPSE_EFFECT_KEYS, path)
        return DisasterCollapseEffect(
            capacity_damage_tenths=_require_strict_int(
                record["capacity_damage_tenths"],
                path=f"{path}.capacity_damage_tenths",
                code="disaster_effect_strength_invalid",
                minimum=MIN_DISASTER_STRENGTH_TENTHS,
                maximum=MAX_DISASTER_STRENGTH_TENTHS,
            )
        )
    if kind is DisasterKind.INFRASTRUCTURE_DESTRUCTION:
        _require_keys(record, _EMPTY_EFFECT_KEYS, path)
        return DisasterInfrastructureEffect()
    if kind is DisasterKind.EPIDEMIC_SURGE:
        _require_keys(record, _SURGE_EFFECT_KEYS, path)
        return DisasterSurgeEffect(
            extra_opportunity_milli=_require_strict_int(
                record["extra_opportunity_milli"],
                path=f"{path}.extra_opportunity_milli",
                code="disaster_surge_opportunity_invalid",
                minimum=MIN_SURGE_OPPORTUNITY_MILLI,
                maximum=MAX_SURGE_OPPORTUNITY_MILLI,
            )
        )
    raise _fail("disaster_kind_invalid", path)


def _encode_effect(effect: DisasterEffect) -> dict[str, object]:
    if isinstance(effect, DisasterLossEffect):
        return {"loss_tenths": effect.loss_tenths}
    if isinstance(effect, DisasterCollapseEffect):
        return {"capacity_damage_tenths": effect.capacity_damage_tenths}
    if isinstance(effect, DisasterInfrastructureEffect):
        return {}
    if isinstance(effect, DisasterSurgeEffect):
        return {"extra_opportunity_milli": effect.extra_opportunity_milli}
    raise TypeError("unsupported disaster effect")


def _decode_rule(raw: object, path: str) -> DisasterRule:
    record = _require_mapping(raw, path)
    _require_keys(record, _RULE_KEYS, path)
    rule_id = record["rule_id"]
    if type(rule_id) is not str or not DISASTER_RULE_ID_PATTERN.fullmatch(rule_id):
        raise _fail("disaster_rule_id_invalid", f"{path}.rule_id")
    kind_raw = record["kind"]
    if type(kind_raw) is not str:
        raise _fail("disaster_kind_invalid", f"{path}.kind")
    try:
        kind = DisasterKind(kind_raw)
    except ValueError as exc:
        raise _fail("disaster_kind_invalid", f"{path}.kind") from exc
    chance_ppm = _require_strict_int(
        record["chance_ppm"],
        path=f"{path}.chance_ppm",
        code="disaster_chance_ppm_invalid",
        minimum=0,
        maximum=MAX_DISASTER_CHANCE_PPM,
    )
    target = _decode_target(kind, record["target"], f"{path}.target")
    effect = _decode_effect(kind, record["effect"], f"{path}.effect")
    return DisasterRule(
        rule_id=rule_id,
        kind=kind,
        chance_ppm=chance_ppm,
        target=target,
        effect=effect,
    )


def _decode_schedule_entry(raw: object, path: str) -> DisasterScheduleEntry:
    record = _require_mapping(raw, path)
    _require_keys(record, _SCHEDULE_KEYS, path)
    tick = _require_strict_int(
        record["tick"],
        path=f"{path}.tick",
        code="disaster_schedule_tick_invalid",
        minimum=0,
        maximum=2**63 - 1,
    )
    rule_id = record["rule_id"]
    if type(rule_id) is not str or not DISASTER_RULE_ID_PATTERN.fullmatch(rule_id):
        raise _fail("disaster_schedule_rule_invalid", f"{path}.rule_id")
    return DisasterScheduleEntry(tick=tick, rule_id=rule_id)


@dataclass(frozen=True, slots=True)
class DisastersSpec:
    """Exact opt-in disasters policy for one run."""

    policy_id: str
    rules: tuple[DisasterRule, ...]
    schedule: tuple[DisasterScheduleEntry, ...]

    def __post_init__(self) -> None:
        if self.policy_id != DISASTERS_POLICY_ID:
            raise _fail(
                "disasters_policy_invalid",
                f"{DISASTERS_KEY}.policy_id",
            )
        if isinstance(self.rules, (str, bytes)) or not isinstance(self.rules, tuple):
            raise TypeError("rules must be a tuple of DisasterRule")
        if not (MIN_DISASTER_RULES <= len(self.rules) <= MAX_DISASTER_RULES):
            raise _fail(
                "disaster_rule_count_invalid",
                f"{DISASTERS_KEY}.rules",
            )
        decoded_rules: list[DisasterRule] = []
        for rule in self.rules:
            if type(rule) is not DisasterRule:
                raise TypeError("rules must contain DisasterRule values")
            decoded_rules.append(
                DisasterRule(
                    rule_id=rule.rule_id,
                    kind=rule.kind,
                    chance_ppm=rule.chance_ppm,
                    target=rule.target,
                    effect=rule.effect,
                )
            )
        rule_ids = [rule.rule_id for rule in decoded_rules]
        if rule_ids != sorted(rule_ids):
            raise _fail(
                "disaster_rule_order_invalid",
                f"{DISASTERS_KEY}.rules",
            )
        if len(set(rule_ids)) != len(rule_ids):
            raise _fail(
                "disaster_rule_id_duplicate",
                f"{DISASTERS_KEY}.rules",
            )
        bindings = [
            _target_binding_key(rule.kind, rule.target) for rule in decoded_rules
        ]
        if len(set(bindings)) != len(bindings):
            raise _fail(
                "disaster_target_binding_duplicate",
                f"{DISASTERS_KEY}.rules",
            )
        if isinstance(self.schedule, (str, bytes)) or not isinstance(
            self.schedule, tuple
        ):
            raise TypeError("schedule must be a tuple of DisasterScheduleEntry")
        decoded_schedule: list[DisasterScheduleEntry] = []
        for entry in self.schedule:
            if type(entry) is not DisasterScheduleEntry:
                raise TypeError("schedule must contain DisasterScheduleEntry values")
            decoded_schedule.append(
                DisasterScheduleEntry(tick=entry.tick, rule_id=entry.rule_id)
            )
        schedule_keys = [(entry.tick, entry.rule_id) for entry in decoded_schedule]
        if schedule_keys != sorted(schedule_keys):
            raise _fail(
                "disaster_schedule_order_invalid",
                f"{DISASTERS_KEY}.schedule",
            )
        known = set(rule_ids)
        scheduled_rules: set[str] = set()
        for entry in decoded_schedule:
            if entry.rule_id not in known:
                raise _fail(
                    "disaster_schedule_rule_unknown",
                    f"{DISASTERS_KEY}.schedule",
                )
            if entry.rule_id in scheduled_rules:
                raise _fail(
                    "disaster_schedule_rule_duplicate",
                    f"{DISASTERS_KEY}.schedule",
                )
            scheduled_rules.add(entry.rule_id)
        by_id = {rule.rule_id: rule for rule in decoded_rules}
        for rule_id in scheduled_rules:
            if by_id[rule_id].chance_ppm != 0:
                raise _fail(
                    "disaster_scheduled_chance_nonzero",
                    f"{DISASTERS_KEY}.rules",
                )
        object.__setattr__(self, "rules", tuple(decoded_rules))
        object.__setattr__(self, "schedule", tuple(decoded_schedule))
        _LOGGER.debug(
            "disasters_configured policy_id=%s rule_count=%s schedule_count=%s",
            self.policy_id,
            len(self.rules),
            len(self.schedule),
        )


def encode_disasters(spec: DisastersSpec) -> dict[str, object]:
    """Encode the exact ``disasters`` sibling object."""
    if type(spec) is not DisastersSpec:
        raise TypeError("spec must be DisastersSpec")
    rules = [
        {
            "rule_id": rule.rule_id,
            "kind": rule.kind.value,
            "chance_ppm": rule.chance_ppm,
            "target": _encode_target(rule.target),
            "effect": _encode_effect(rule.effect),
        }
        for rule in spec.rules
    ]
    schedule = [
        {"tick": entry.tick, "rule_id": entry.rule_id} for entry in spec.schedule
    ]
    _LOGGER.debug(
        "disasters_encode rule_count=%s schedule_count=%s",
        len(spec.rules),
        len(spec.schedule),
    )
    return {
        "policy_id": spec.policy_id,
        "rules": rules,
        "schedule": schedule,
    }


def decode_disasters(value: object) -> DisastersSpec:
    """Decode the exact ``disasters`` sibling object."""
    path = f"$.{DISASTERS_KEY}"
    record = _require_mapping(value, path)
    _require_keys(record, _SPEC_KEYS, path)
    policy_id = record["policy_id"]
    if type(policy_id) is not str:
        raise _fail("disasters_policy_invalid", f"{path}.policy_id")
    raw_rules = record["rules"]
    if isinstance(raw_rules, (str, bytes)) or not isinstance(raw_rules, list):
        raise _fail("disasters_spec_invalid", f"{path}.rules")
    rules = tuple(
        _decode_rule(raw, f"{path}.rules[{index}]")
        for index, raw in enumerate(raw_rules)
    )
    raw_schedule = record["schedule"]
    if isinstance(raw_schedule, (str, bytes)) or not isinstance(raw_schedule, list):
        raise _fail("disasters_spec_invalid", f"{path}.schedule")
    schedule = tuple(
        _decode_schedule_entry(raw, f"{path}.schedule[{index}]")
        for index, raw in enumerate(raw_schedule)
    )
    return DisastersSpec(policy_id=policy_id, rules=rules, schedule=schedule)


def policy_sha256_for_disasters(spec: DisastersSpec) -> str:
    """Hash the exact canonical disasters encoding (policy object only)."""
    if type(spec) is not DisastersSpec:
        raise TypeError("spec must be DisastersSpec")
    payload = encode_disasters(spec)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    digest = hashlib.sha256(canonical).hexdigest()
    _LOGGER.debug(
        "disasters_policy_digest_ready rule_count=%s schedule_count=%s",
        len(spec.rules),
        len(spec.schedule),
    )
    return digest


@dataclass(frozen=True, slots=True)
class _ResourceView:
    resource_id: EntityId
    kind: ResourceKind
    location_id: EntityId
    regeneration_per_tick: float


def bind_disaster_targets(
    spec: DisastersSpec,
    *,
    managed_resource_ids: Sequence[EntityId],
    resources: Sequence[_ResourceView] | Sequence[Any],
    location_ids: Sequence[EntityId],
    adjacency: Mapping[EntityId, Sequence[EntityId]],
    tick_horizon: int | None,
) -> None:
    """Statically validate targets against scenario graph and managed stocks.

    ``tick_horizon`` is the inclusive last executable tick when finite; ``None``
    means no schedule upper bound is enforced here.
    """
    if type(spec) is not DisastersSpec:
        raise TypeError("spec must be DisastersSpec")
    managed = {entity.value for entity in managed_resource_ids}
    resources_by_id: dict[str, Any] = {}
    for resource in resources:
        resource_id = getattr(resource, "resource_id", None)
        if resource_id is None:
            resource_id = getattr(resource, "entity_id", None)
        if type(resource_id) is not EntityId:
            raise TypeError("resources must expose EntityId identity")
        resources_by_id[resource_id.value] = resource
    locations = {entity.value for entity in location_ids}
    for index, rule in enumerate(spec.rules):
        path = f"$.{DISASTERS_KEY}.rules[{index}]"
        if isinstance(rule.target, DisasterResourceTarget):
            resource_id = rule.target.resource_id.value
            if resource_id not in managed:
                raise _fail("disaster_stock_unmanaged", f"{path}.target.resource_id")
            resource = resources_by_id.get(resource_id)
            if resource is None:
                raise _fail("disaster_stock_unknown", f"{path}.target.resource_id")
            kind = getattr(resource, "kind", None)
            if type(kind) is not ResourceKind:
                raise TypeError("resource.kind must be ResourceKind")
            allowed = _KIND_RESOURCE_REQUIREMENTS[rule.kind]
            if kind not in allowed:
                raise _fail(
                    "disaster_stock_kind_mismatch",
                    f"{path}.target.resource_id",
                )
            regeneration = float(resource.regeneration_per_tick)
            if regeneration <= 0.0:
                raise _fail(
                    "disaster_stock_nonrenewable",
                    f"{path}.target.resource_id",
                )
            continue
        if isinstance(rule.target, DisasterInfrastructureTarget):
            location_id = rule.target.location_id.value
            if location_id not in locations:
                raise _fail(
                    "disaster_location_unknown",
                    f"{path}.target.location_id",
                )
            row = catalog_row(rule.target.infrastructure_kind)
            endpoint = rule.target.endpoint_location_id
            if row.topology is InfrastructureTopology.NODE:
                if endpoint is not None:
                    raise _fail(
                        "disaster_infrastructure_topology_mismatch",
                        f"{path}.target.endpoint_location_id",
                    )
            else:
                if endpoint is None:
                    raise _fail(
                        "disaster_infrastructure_topology_mismatch",
                        f"{path}.target.endpoint_location_id",
                    )
                if endpoint.value not in locations:
                    raise _fail(
                        "disaster_location_unknown",
                        f"{path}.target.endpoint_location_id",
                    )
                neighbors = {
                    neighbor.value
                    for neighbor in adjacency.get(rule.target.location_id, ())
                }
                if endpoint.value not in neighbors:
                    raise _fail(
                        "disaster_edge_not_adjacent",
                        f"{path}.target.endpoint_location_id",
                    )
            continue
        if isinstance(rule.target, DisasterLocationTarget):
            if rule.target.location_id.value not in locations:
                raise _fail(
                    "disaster_location_unknown",
                    f"{path}.target.location_id",
                )
            continue
        raise TypeError("unsupported disaster target")
    if tick_horizon is not None:
        if type(tick_horizon) is not int or isinstance(tick_horizon, bool):
            raise TypeError("tick_horizon must be int or None")
        if tick_horizon < 0:
            raise ValueError("tick_horizon must be nonnegative")
        for index, entry in enumerate(spec.schedule):
            if entry.tick > tick_horizon:
                raise _fail(
                    "disaster_schedule_tick_out_of_range",
                    f"$.{DISASTERS_KEY}.schedule[{index}].tick",
                )
    _LOGGER.debug(
        "disasters_targets_bound rule_count=%s schedule_count=%s",
        len(spec.rules),
        len(spec.schedule),
    )
