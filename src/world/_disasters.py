"""Private objective disaster stock pulses and frozen disaster state.

Engine/bootstrap only. Agents never import this module. Stock shocks edit a
private tick candidate after ordinary renewal and never enter the just-finished
pressure budget. Applied-rule ledger lives on the objective candidate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from world._ecological_resources import (
    EcologicalStockRow,
    effective_capacity_tenths,
)
from world.disasters import (
    DISASTER_RULE_ID_PATTERN,
    MAX_DISASTER_RULES,
    DisasterCandidate,
    DisasterCollapseEffect,
    DisasterKind,
    DisasterLossEffect,
    DisasterOrigin,
    DisasterResourceTarget,
    DisasterSkipReason,
)
from world.events import ResourceNodeDepleted, node_quantity_witness
from world.identifiers import EntityId
from world.models import Resource, copy_resource
from world.values import ResourceKind, WeatherCondition, round_physical

if TYPE_CHECKING:
    from world._state import WorldState

__all__ = [
    "DisasterInvariantError",
    "DisasterState",
    "DisasterStockPulse",
    "apply_recorded_stock_disaster",
    "apply_stock_disaster",
    "mark_disaster_rule_applied",
    "require_disaster_state",
]

_LOG: Final[logging.Logger] = logging.getLogger("world.disasters")

_STOCK_KINDS: Final[frozenset[DisasterKind]] = frozenset(
    {
        DisasterKind.FLOOD_LIKE,
        DisasterKind.FIRE,
        DisasterKind.DROUGHT,
        DisasterKind.RESOURCE_COLLAPSE,
    }
)
_KIND_RESOURCE_REQUIREMENTS: Final[dict[DisasterKind, frozenset[ResourceKind]]] = {
    DisasterKind.FLOOD_LIKE: frozenset({ResourceKind.FOOD}),
    DisasterKind.FIRE: frozenset({ResourceKind.FOOD, ResourceKind.MATERIAL}),
    DisasterKind.DROUGHT: frozenset({ResourceKind.WATER}),
    DisasterKind.RESOURCE_COLLAPSE: frozenset(
        {ResourceKind.FOOD, ResourceKind.WATER, ResourceKind.MATERIAL}
    ),
}
_WET: Final[frozenset[WeatherCondition]] = frozenset(
    {WeatherCondition.RAIN, WeatherCondition.STORM}
)


class DisasterInvariantError(ValueError):
    """Malformed private disaster working state with a stable safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> DisasterInvariantError:
    _LOG.error("disaster_state_invalid reason_code=%s", code)
    return DisasterInvariantError(code)


@dataclass(frozen=True, slots=True)
class DisasterState:
    """Frozen private disaster ledger under checkpoint key ``disaster_state``."""

    policy_sha256: str
    overexploitation_active: bool
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.policy_sha256) is not str or len(self.policy_sha256) != 64:
            raise _fail("disaster_policy_digest_invalid")
        if any(ch not in "0123456789abcdef" for ch in self.policy_sha256):
            raise _fail("disaster_policy_digest_invalid")
        if type(self.overexploitation_active) is not bool:
            raise _fail("disaster_overexploitation_flag_invalid")
        if isinstance(self.applied_rule_ids, (str, bytes)) or not isinstance(
            self.applied_rule_ids, tuple
        ):
            raise _fail("disaster_applied_ids_invalid")
        if len(self.applied_rule_ids) > MAX_DISASTER_RULES:
            raise _fail("disaster_applied_ids_count")
        seen: set[str] = set()
        previous = ""
        for rule_id in self.applied_rule_ids:
            if type(rule_id) is not str or not DISASTER_RULE_ID_PATTERN.fullmatch(
                rule_id
            ):
                raise _fail("disaster_applied_id_invalid")
            if rule_id in seen:
                raise _fail("disaster_applied_ids_duplicate")
            if previous and rule_id < previous:
                raise _fail("disaster_applied_ids_order")
            seen.add(rule_id)
            previous = rule_id


def require_disaster_state(value: object) -> DisasterState:
    if type(value) is not DisasterState:
        raise TypeError("disaster_state must be DisasterState")
    return value


def mark_disaster_rule_applied(
    state: DisasterState, rule_id: str
) -> DisasterState:
    """Return a new ledger with ``rule_id`` inserted in sorted unique order."""
    require_disaster_state(state)
    if type(rule_id) is not str or not DISASTER_RULE_ID_PATTERN.fullmatch(rule_id):
        raise _fail("disaster_applied_id_invalid")
    if rule_id in state.applied_rule_ids:
        raise _fail("disaster_applied_id_reuse")
    merged = tuple(sorted({*state.applied_rule_ids, rule_id}))
    if len(merged) > MAX_DISASTER_RULES:
        raise _fail("disaster_applied_ids_count")
    return DisasterState(
        policy_sha256=state.policy_sha256,
        overexploitation_active=state.overexploitation_active,
        applied_rule_ids=merged,
    )


def _exact_tenths(value: float, *, code: str) -> int:
    rounded = round_physical(value)
    if rounded != float(value):
        raise _fail(code)
    return round(rounded * 10.0)


def _quantity_from_tenths(tenths: int) -> float:
    return round_physical(tenths / 10.0)


@dataclass(frozen=True, slots=True)
class DisasterStockPulse:
    """Exact tenths transition for one applied stock shock."""

    rule_id: str
    kind: DisasterKind
    origin: DisasterOrigin
    resource_id: EntityId
    quantity_before_tenths: int
    quantity_after_tenths: int
    damage_before_tenths: int
    damage_after_tenths: int

    def __post_init__(self) -> None:
        if type(self.rule_id) is not str or self.rule_id == "":
            raise TypeError("rule_id must be a non-empty str")
        if type(self.kind) is not DisasterKind or self.kind not in _STOCK_KINDS:
            raise TypeError("kind must be a stock DisasterKind")
        if type(self.origin) is not DisasterOrigin:
            raise TypeError("origin must be DisasterOrigin")
        if type(self.resource_id) is not EntityId:
            raise TypeError("resource_id must be EntityId")
        for name in (
            "quantity_before_tenths",
            "quantity_after_tenths",
            "damage_before_tenths",
            "damage_after_tenths",
        ):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a nonnegative int")
        if self.quantity_after_tenths > self.quantity_before_tenths:
            raise ValueError("quantity must not increase under a stock pulse")
        if self.damage_after_tenths < self.damage_before_tenths:
            raise ValueError("damage must not decrease under a stock pulse")
        if (
            self.quantity_after_tenths == self.quantity_before_tenths
            and self.damage_after_tenths == self.damage_before_tenths
        ):
            raise ValueError("stock pulse must change quantity or damage")


def _weather_eligible(
    kind: DisasterKind, condition: WeatherCondition | None
) -> bool:
    if condition is None:
        return False
    if kind is DisasterKind.FLOOD_LIKE:
        return condition in _WET
    if kind is DisasterKind.FIRE:
        return condition is WeatherCondition.CLEAR
    if kind is DisasterKind.DROUGHT:
        return condition is WeatherCondition.CLEAR
    if kind is DisasterKind.RESOURCE_COLLAPSE:
        return True
    return False


def apply_stock_disaster(
    state: WorldState,
    candidate: DisasterCandidate,
) -> tuple[
    WorldState,
    DisasterStockPulse | DisasterSkipReason,
    ResourceNodeDepleted | None,
]:
    """Apply one stock shock to a private candidate after ordinary renewal.

    Returns the unchanged state with ``weather_ineligible`` / ``no_effect``, or
    a rebuilt state with an applied pulse and optional depletion witness.
    """
    from world._state import WorldState as _WorldState

    if type(state) is not _WorldState:
        raise TypeError("apply_stock_disaster requires WorldState")
    if type(candidate) is not DisasterCandidate:
        raise TypeError("candidate must be DisasterCandidate")
    rule = candidate.rule
    if rule.kind not in _STOCK_KINDS:
        raise TypeError("candidate must be a stock disaster kind")
    if type(rule.target) is not DisasterResourceTarget:
        raise _fail("disaster_target_kind_mismatch")
    resource_id = rule.target.resource_id
    ecology = state.ecological_resources
    if ecology is None:
        raise _fail("disaster_ecology_channel_off")
    resource = state.resources.get(resource_id)
    row = ecology.get(resource_id)
    if resource is None or row is None:
        raise _fail("disaster_stock_missing")
    allowed = _KIND_RESOURCE_REQUIREMENTS[rule.kind]
    if resource.kind not in allowed:
        raise _fail("disaster_stock_kind_mismatch")
    weather = state.weather.get(resource.location_id)
    condition = None if weather is None else weather.condition
    if not _weather_eligible(rule.kind, condition):
        _LOG.debug(
            "disaster_stock_skipped kind=%s origin=%s outcome=%s",
            rule.kind.value,
            candidate.origin.value,
            DisasterSkipReason.WEATHER_INELIGIBLE.value,
        )
        return state, DisasterSkipReason.WEATHER_INELIGIBLE, None

    baseline_tenths = _exact_tenths(
        resource.maximum_quantity, code="disaster_baseline_grid_invalid"
    )
    quantity_before = _exact_tenths(
        resource.quantity, code="disaster_quantity_grid_invalid"
    )
    damage_before = row.damage_tenths
    capacity_before = effective_capacity_tenths(row, baseline_tenths=baseline_tenths)
    if quantity_before > capacity_before:
        raise _fail("disaster_quantity_above_capacity")

    if rule.kind is DisasterKind.RESOURCE_COLLAPSE:
        if type(rule.effect) is not DisasterCollapseEffect:
            raise _fail("disaster_effect_kind_mismatch")
        span_remaining = capacity_before - row.minimum_capacity_tenths
        damage_delta = min(rule.effect.capacity_damage_tenths, span_remaining)
        quantity_after = 0
        damage_after = damage_before + damage_delta
    else:
        if type(rule.effect) is not DisasterLossEffect:
            raise _fail("disaster_effect_kind_mismatch")
        loss = min(quantity_before, rule.effect.loss_tenths)
        quantity_after = quantity_before - loss
        damage_after = damage_before

    if quantity_after == quantity_before and damage_after == damage_before:
        _LOG.debug(
            "disaster_stock_skipped kind=%s origin=%s outcome=%s",
            rule.kind.value,
            candidate.origin.value,
            DisasterSkipReason.NO_EFFECT.value,
        )
        return state, DisasterSkipReason.NO_EFFECT, None

    pulse = DisasterStockPulse(
        rule_id=rule.rule_id,
        kind=rule.kind,
        origin=candidate.origin,
        resource_id=resource_id,
        quantity_before_tenths=quantity_before,
        quantity_after_tenths=quantity_after,
        damage_before_tenths=damage_before,
        damage_after_tenths=damage_after,
    )
    next_state, witness = _commit_stock_pulse(
        state, resource=resource, row=row, pulse=pulse
    )
    _LOG.debug(
        "disaster_stock_applied kind=%s origin=%s outcome=applied",
        rule.kind.value,
        candidate.origin.value,
    )
    return next_state, pulse, witness


def apply_recorded_stock_disaster(
    state: WorldState,
    pulse: DisasterStockPulse,
) -> tuple[WorldState, ResourceNodeDepleted | None]:
    """Fold one recorded stock pulse without policy or RNG.

    Checks recorded before values against the working state, monotone loss and
    damage, kind shape, and capacity bounds, then writes the exact after values.
    """
    from world._state import WorldState as _WorldState

    if type(state) is not _WorldState:
        raise TypeError("apply_recorded_stock_disaster requires WorldState")
    if type(pulse) is not DisasterStockPulse:
        raise TypeError("pulse must be DisasterStockPulse")
    ecology = state.ecological_resources
    if ecology is None:
        raise _fail("disaster_ecology_channel_off")
    resource = state.resources.get(pulse.resource_id)
    row = ecology.get(pulse.resource_id)
    if resource is None or row is None:
        raise _fail("disaster_stock_missing")
    allowed = _KIND_RESOURCE_REQUIREMENTS[pulse.kind]
    if resource.kind not in allowed:
        raise _fail("disaster_stock_kind_mismatch")
    baseline_tenths = _exact_tenths(
        resource.maximum_quantity, code="disaster_baseline_grid_invalid"
    )
    quantity_now = _exact_tenths(
        resource.quantity, code="disaster_quantity_grid_invalid"
    )
    if quantity_now != pulse.quantity_before_tenths:
        raise _fail("disaster_quantity_before_mismatch")
    if row.damage_tenths != pulse.damage_before_tenths:
        raise _fail("disaster_damage_before_mismatch")
    if pulse.quantity_after_tenths > pulse.quantity_before_tenths:
        raise _fail("disaster_quantity_increased")
    if pulse.damage_after_tenths < pulse.damage_before_tenths:
        raise _fail("disaster_damage_decreased")
    if not (1 <= row.minimum_capacity_tenths < baseline_tenths <= 10000):
        raise _fail("disaster_capacity_bounds")
    span = baseline_tenths - row.minimum_capacity_tenths
    if pulse.damage_after_tenths > span:
        raise _fail("disaster_damage_above_span")
    capacity_after = baseline_tenths - pulse.damage_after_tenths
    if pulse.quantity_after_tenths > capacity_after:
        raise _fail("disaster_quantity_above_capacity")
    if pulse.kind is DisasterKind.RESOURCE_COLLAPSE:
        if pulse.quantity_after_tenths != 0:
            raise _fail("disaster_collapse_quantity_nonzero")
    else:
        if pulse.damage_after_tenths != pulse.damage_before_tenths:
            raise _fail("disaster_loss_damage_changed")
    return _commit_stock_pulse(state, resource=resource, row=row, pulse=pulse)


def _commit_stock_pulse(
    state: WorldState,
    *,
    resource: Resource,
    row: EcologicalStockRow,
    pulse: DisasterStockPulse,
) -> tuple[WorldState, ResourceNodeDepleted | None]:
    from world._state import rebuild_world_state

    next_quantity = _quantity_from_tenths(pulse.quantity_after_tenths)
    next_resource = (
        resource
        if next_quantity == resource.quantity
        else copy_resource(resource, quantity=next_quantity)
    )
    next_row = (
        row
        if pulse.damage_after_tenths == row.damage_tenths
        else EcologicalStockRow(
            resource_id=row.resource_id,
            minimum_capacity_tenths=row.minimum_capacity_tenths,
            damage_tenths=pulse.damage_after_tenths,
        )
    )
    resources = dict(state.resources)
    resources[pulse.resource_id] = next_resource
    ecology = dict(state.ecological_resources or {})
    ecology[pulse.resource_id] = next_row
    next_state = rebuild_world_state(
        state,
        resources=resources,
        ecological_resources=ecology,
        ecological_policy_digest=state.ecological_policy_digest,
        replace_ecological_resources=True,
    )
    witness = node_quantity_witness(
        pulse.resource_id,
        resource.quantity,
        next_quantity,
    )
    if type(witness) is ResourceNodeDepleted:
        return next_state, witness
    return next_state, None
