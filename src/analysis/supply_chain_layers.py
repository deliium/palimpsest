"""Strictly separated supply-chain objective, analytical, and owner layers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.supply_chain_bottlenecks import SupplyBottleneck
from analysis.supply_chain_contract import (
    SUPPLY_FORBIDDEN_KEYS,
    SupplyChainError,
    SupplyLayer,
)
from analysis.supply_chain_events import SupplyStageObservation
from analysis.supply_chain_graph import (
    SupplyChainPath,
    SupplyDependencyEdge,
    SupplyLocationRow,
    SupplyOrganizationRow,
)
from analysis.supply_chain_identity import SupplyChainLineageRow

__all__ = [
    "SupplyChainLayerView",
    "assert_supply_chain_layer_separation",
    "project_supply_chain_layers",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.supply_chain.layers")


@dataclass(frozen=True, slots=True)
class SupplyChainLayerView:
    objective_derived: tuple[object, ...] = ()
    analytical: tuple[object, ...] = ()
    owner_claims: tuple[object, ...] = ()


_OBJECTIVE_TYPES: Final[frozenset[type]] = frozenset(
    {SupplyStageObservation, SupplyDependencyEdge, SupplyLocationRow}
)
_ANALYTICAL_TYPES: Final[frozenset[type]] = frozenset(
    {SupplyChainPath, SupplyChainLineageRow, SupplyBottleneck}
)
_OWNER_TYPES: Final[frozenset[type]] = frozenset({SupplyOrganizationRow})


def _forbidden_fields(row: object) -> set[str]:
    names = getattr(type(row), "__dataclass_fields__", {})
    return set(names) & SUPPLY_FORBIDDEN_KEYS


def project_supply_chain_layers(
    *,
    stages: tuple[SupplyStageObservation, ...],
    edges: tuple[SupplyDependencyEdge, ...],
    chains: tuple[SupplyChainPath, ...],
    lineage: tuple[SupplyChainLineageRow, ...],
    bottlenecks: tuple[SupplyBottleneck, ...],
    locations: tuple[SupplyLocationRow, ...],
    organizations: tuple[SupplyOrganizationRow, ...],
) -> SupplyChainLayerView:
    objective: tuple[object, ...] = (*stages, *edges, *locations)
    analytical: tuple[object, ...] = (*chains, *lineage, *bottlenecks)
    owner: tuple[object, ...] = tuple(organizations)
    for row in (*objective, *analytical, *owner):
        if _forbidden_fields(row):
            _LOG.error("supply_chain_layer_leak reason_code=forbidden_field")
            raise SupplyChainError("supply_chain_layer_leak")
    view = SupplyChainLayerView(
        objective_derived=objective,
        analytical=analytical,
        owner_claims=owner,
    )
    assert_supply_chain_layer_separation(view)
    return view


def assert_supply_chain_layer_separation(view: object) -> None:
    if type(view) is not SupplyChainLayerView:
        raise SupplyChainError("supply_chain_layer_leak")
    expected = (
        (view.objective_derived, _OBJECTIVE_TYPES),
        (view.analytical, _ANALYTICAL_TYPES),
        (view.owner_claims, _OWNER_TYPES),
    )
    for rows, allowed in expected:
        for row in rows:
            if type(row) not in allowed:
                _LOG.error(
                    "supply_chain_layer_leak layer=%s reason_code=wrong_layer",
                    _layer_for(allowed).value,
                )
                raise SupplyChainError("supply_chain_layer_leak")
            if _forbidden_fields(row):
                raise SupplyChainError("supply_chain_layer_leak")


def _layer_for(allowed: frozenset[type]) -> SupplyLayer:
    if allowed is _OBJECTIVE_TYPES:
        return SupplyLayer.OBJECTIVE_DERIVED
    if allowed is _ANALYTICAL_TYPES:
        return SupplyLayer.ANALYTICAL
    return SupplyLayer.OWNER_CLAIMS
