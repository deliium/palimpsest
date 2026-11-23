"""Private objective ecological stock-damage rows. Engine/bootstrap only.

Agents never import this module. ``None`` keeps the channel off; an empty
mapping is rejected. Actual stock remains ``Resource.quantity``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from world.identifiers import EntityId
from world.values import round_physical

if TYPE_CHECKING:
    from world._state import WorldState
    from world.models import Resource

__all__ = [
    "EcologicalInvariantError",
    "EcologicalStockRow",
    "advance_stock_damage",
    "bootstrap_ecological_rows",
    "effective_capacity_tenths",
    "index_ecological_resources",
    "project_ecological_resource_changed",
    "validate_ecological_resources_state",
]

_LOG: Final[logging.Logger] = logging.getLogger("world.ecological_resources")


class EcologicalInvariantError(ValueError):
    """Malformed private ecological state with a stable safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> EcologicalInvariantError:
    _LOG.error("ecological_state_invalid reason_code=%s", code)
    return EcologicalInvariantError(code)


def _exact_tenths(value: float, *, code: str) -> int:
    rounded = round_physical(value)
    if rounded != float(value):
        raise _fail(code)
    return round(rounded * 10.0)


@dataclass(frozen=True, slots=True)
class EcologicalStockRow:
    """One managed node's floor and accumulated capacity damage in tenths."""

    resource_id: EntityId
    minimum_capacity_tenths: int
    damage_tenths: int

    def __post_init__(self) -> None:
        if type(self.resource_id) is not EntityId:
            raise TypeError("EcologicalStockRow.resource_id must be EntityId")
        if type(self.minimum_capacity_tenths) is not int or isinstance(
            self.minimum_capacity_tenths, bool
        ):
            raise _fail("ecological_floor_invalid")
        if self.minimum_capacity_tenths < 1 or self.minimum_capacity_tenths > 10000:
            raise _fail("ecological_floor_invalid")
        if type(self.damage_tenths) is not int or isinstance(self.damage_tenths, bool):
            raise _fail("ecological_damage_invalid")
        if self.damage_tenths < 0:
            raise _fail("ecological_damage_invalid")


def index_ecological_resources(
    value: Mapping[EntityId, EcologicalStockRow]
    | Sequence[EcologicalStockRow]
    | None,
) -> MappingProxyType[EntityId, EcologicalStockRow] | None:
    """Index ecological rows. ``None`` keeps the channel off."""
    if value is None:
        _LOG.debug("ecological_channel_off")
        return None
    if isinstance(value, Mapping):
        rows = tuple(value.values())
    elif isinstance(value, (tuple, list)):
        rows = tuple(value)
    else:
        raise _fail("ecological_state_type")
    if not rows:
        raise _fail("ecological_state_empty")
    indexed: dict[EntityId, EcologicalStockRow] = {}
    for row in rows:
        if type(row) is not EcologicalStockRow:
            raise _fail("ecological_row_type")
        if row.resource_id in indexed:
            raise _fail("ecological_row_duplicate")
        indexed[row.resource_id] = row
    ordered_ids = sorted(indexed, key=lambda item: item.value)
    ordered = {entity_id: indexed[entity_id] for entity_id in ordered_ids}
    return MappingProxyType(ordered)


def bootstrap_ecological_rows(
    *,
    nodes: Sequence[tuple[EntityId, int]],
) -> MappingProxyType[EntityId, EcologicalStockRow]:
    """Build zero-damage rows from validated ``(resource_id, floor)`` pairs."""
    if isinstance(nodes, (str, bytes)) or not isinstance(nodes, (tuple, list)):
        raise TypeError("nodes must be a sequence of (EntityId, floor) pairs")
    rows = [
        EcologicalStockRow(
            resource_id=resource_id,
            minimum_capacity_tenths=floor,
            damage_tenths=0,
        )
        for resource_id, floor in nodes
    ]
    indexed = index_ecological_resources(rows)
    assert indexed is not None
    _LOG.debug("ecological_bootstrap_rows managed_count=%s", len(indexed))
    return indexed


def _require_tenths_int(name: str, value: object) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise _fail(f"ecological_{name}_invalid")
    if value < 0:
        raise _fail(f"ecological_{name}_invalid")
    return value


def effective_capacity_tenths(
    row: EcologicalStockRow, *, baseline_tenths: int
) -> int:
    """Return ``base - damage`` after validating the local capacity span."""
    base = _require_tenths_int("baseline", baseline_tenths)
    if not (1 <= row.minimum_capacity_tenths < base <= 10000):
        raise _fail("ecological_capacity_bounds")
    if row.damage_tenths > base - row.minimum_capacity_tenths:
        raise _fail("ecological_damage_above_span")
    return base - row.damage_tenths


def advance_stock_damage(
    row: EcologicalStockRow,
    *,
    baseline_tenths: int,
    start_quantity_tenths: int,
    post_command_quantity_tenths: int,
    allowance_tenths: int,
    recovery_tenths: int,
) -> EcologicalStockRow:
    """Pure one-tick damage update from actual net withdrawal or idle recovery.

    Capacity is ``base - damage``. Zero withdrawal recovers; positive
    withdrawal above the allowance adds damage. Never mutates ``row``.
    """
    if type(row) is not EcologicalStockRow:
        raise TypeError("advance_stock_damage requires EcologicalStockRow")
    base = _require_tenths_int("baseline", baseline_tenths)
    start = _require_tenths_int("start_quantity", start_quantity_tenths)
    post = _require_tenths_int("post_quantity", post_command_quantity_tenths)
    allowance = _require_tenths_int("allowance", allowance_tenths)
    recovery = _require_tenths_int("recovery", recovery_tenths)
    if allowance > 10000:
        raise _fail("ecological_allowance_invalid")
    if recovery < 1 or recovery > 10000:
        raise _fail("ecological_recovery_invalid")
    if not (1 <= row.minimum_capacity_tenths < base <= 10000):
        raise _fail("ecological_capacity_bounds")
    span = base - row.minimum_capacity_tenths
    if row.damage_tenths > span:
        raise _fail("ecological_damage_above_span")
    capacity = base - row.damage_tenths
    if start > capacity or post > capacity:
        raise _fail("ecological_quantity_above_capacity")
    if post > start:
        raise _fail("ecological_post_above_start")
    withdrawn = start - post
    if withdrawn == 0:
        next_damage = max(0, row.damage_tenths - recovery)
    else:
        next_damage = min(span, row.damage_tenths + max(0, withdrawn - allowance))
    next_capacity = base - next_damage
    if not (row.minimum_capacity_tenths <= next_capacity <= base):
        raise _fail("ecological_capacity_bounds")
    if post > next_capacity:
        raise _fail("ecological_quantity_above_capacity")
    return EcologicalStockRow(
        resource_id=row.resource_id,
        minimum_capacity_tenths=row.minimum_capacity_tenths,
        damage_tenths=next_damage,
    )


def project_ecological_resource_changed(
    state: object,
    *,
    details: object,
) -> WorldState:
    """Fold one recorded capacity-damage transition without re-running policy."""
    from world._state import WorldState, rebuild_world_state
    from world.events import EcologicalResourceChanged

    if type(state) is not WorldState:
        raise TypeError("project_ecological_resource_changed requires WorldState")
    if type(details) is not EcologicalResourceChanged:
        raise TypeError("details must be EcologicalResourceChanged")
    if state.ecological_resources is None:
        raise EcologicalInvariantError("ecological_channel_off")
    current = dict(state.ecological_resources)
    existing = current.get(details.resource_id)
    if existing is None:
        raise EcologicalInvariantError("ecological_resource_missing")
    if existing.damage_tenths != details.before_damage_tenths:
        raise EcologicalInvariantError("ecological_before_mismatch")
    resource = state.resources.get(details.resource_id)
    if resource is None:
        raise EcologicalInvariantError("ecological_resource_missing")
    baseline = _exact_tenths(
        resource.maximum_quantity, code="ecological_baseline_grid_invalid"
    )
    quantity = _exact_tenths(
        resource.quantity, code="ecological_quantity_grid_invalid"
    )
    if not (1 <= existing.minimum_capacity_tenths < baseline <= 10000):
        raise EcologicalInvariantError("ecological_capacity_bounds")
    span = baseline - existing.minimum_capacity_tenths
    if details.after_damage_tenths > span:
        raise EcologicalInvariantError("ecological_damage_above_span")
    capacity = baseline - details.after_damage_tenths
    if quantity > capacity:
        raise EcologicalInvariantError("ecological_quantity_above_capacity")
    current[details.resource_id] = EcologicalStockRow(
        resource_id=details.resource_id,
        minimum_capacity_tenths=existing.minimum_capacity_tenths,
        damage_tenths=details.after_damage_tenths,
    )
    return rebuild_world_state(
        state,
        ecological_resources=current,
        ecological_policy_digest=state.ecological_policy_digest,
        replace_ecological_resources=True,
    )


def validate_ecological_resources_state(
    rows: Mapping[EntityId, EcologicalStockRow] | None,
    *,
    resources: Mapping[EntityId, Resource],
    policy_digest: str | None,
    expected_digest: str | None,
    expected_floors: Mapping[EntityId, int] | None = None,
) -> None:
    """Reject inconsistent active ecology state at bind/restore boundaries."""
    if rows is None:
        if expected_digest is not None or expected_floors is not None:
            raise _fail("ecological_state_missing")
        if policy_digest is not None:
            raise _fail("ecological_digest_without_state")
        return
    if expected_digest is None:
        raise _fail("ecological_digest_required")
    if type(policy_digest) is not str or policy_digest != expected_digest:
        raise _fail("ecological_digest_mismatch")
    if len(policy_digest) != 64 or any(
        ch not in "0123456789abcdef" for ch in policy_digest
    ):
        raise _fail("ecological_digest_invalid")
    indexed = index_ecological_resources(rows)
    assert indexed is not None
    if expected_floors is not None:
        if set(indexed) != set(expected_floors):
            raise _fail("ecological_node_set_mismatch")
        for entity_id, floor in expected_floors.items():
            if indexed[entity_id].minimum_capacity_tenths != floor:
                raise _fail("ecological_floor_mismatch")
    previous: str | None = None
    for entity_id, row in indexed.items():
        if previous is not None and entity_id.value < previous:
            raise _fail("ecological_row_order")
        previous = entity_id.value
        resource = resources.get(entity_id)
        if resource is None:
            raise _fail("ecological_resource_missing")
        baseline = _exact_tenths(
            resource.maximum_quantity,
            code="ecological_baseline_grid_invalid",
        )
        quantity = _exact_tenths(
            resource.quantity,
            code="ecological_quantity_grid_invalid",
        )
        if not (1 <= row.minimum_capacity_tenths < baseline <= 10000):
            raise _fail("ecological_capacity_bounds")
        if row.damage_tenths > baseline - row.minimum_capacity_tenths:
            raise _fail("ecological_damage_above_span")
        capacity = baseline - row.damage_tenths
        if quantity > capacity:
            raise _fail("ecological_quantity_above_capacity")
        if quantity > baseline - row.damage_tenths:
            raise _fail("ecological_quantity_above_capacity")
    _LOG.debug(
        "ecological_state_validated managed_count=%s",
        len(indexed),
    )
