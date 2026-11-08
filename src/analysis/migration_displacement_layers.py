"""Four-layer projection and hard leakage guard for migration displacement.

The layers are objective movement, subjective cause, analytical wave, and
integration outcome. Each layer has its own container and its own row types; no
row type is reused across layers. A leak between layers raises
``MigrationLayerLeakError`` and is never a warning. This module imports no
cognition, runtime, experiments, API, persistence, or observer module.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.migration_displacement_events import (
    MigrationIntegrationEvidenceRow,
    MigrationMovementRow,
)
from analysis.migration_displacement_rows import (
    MigrationAlignmentRow,
    MigrationCandidateRow,
    MigrationCauseRow,
    MigrationClusterRow,
    MigrationDisplacementHarvestRows,
    MigrationLineageRow,
    MigrationOutcomeRow,
    MigrationRouteRow,
    MigrationWaveRow,
)

__all__ = [
    "AnalyticalWaveLayer",
    "IntegrationOutcomeLayer",
    "MigrationLayer",
    "MigrationLayerLeakError",
    "MigrationLayers",
    "ObjectiveMovementLayer",
    "SubjectiveCauseLayer",
    "assert_migration_layer_separation",
    "project_migration_layers",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.migration_displacement.layers"
)


class MigrationLayer(StrEnum):
    """Closed layer names."""

    OBJECTIVE_MOVEMENT = "objective_movement"
    SUBJECTIVE_CAUSE = "subjective_cause"
    ANALYTICAL_WAVE = "analytical_wave"
    INTEGRATION_OUTCOME = "integration_outcome"


class MigrationLayerLeakError(ValueError):
    """A field or row type crossed a layer boundary. Message is ``layer:field``."""


_FORBIDDEN: Final[dict[MigrationLayer, frozenset[str]]] = {
    MigrationLayer.OBJECTIVE_MOVEMENT: frozenset(
        {"cause_kind", "owner_token", "classification", "wave_token"}
    ),
    MigrationLayer.SUBJECTIVE_CAUSE: frozenset(
        {"wave_token", "classification", "candidate_token"}
    ),
    MigrationLayer.ANALYTICAL_WAVE: frozenset(
        {
            "raw_owner_id",
            "raw_agent_id",
            "raw_entity_id",
            "refugee",
            "forced",
            "score",
            "composite",
            "wellbeing",
            "assimilation",
        }
    ),
    MigrationLayer.INTEGRATION_OUTCOME: frozenset(
        {"cause_kind", "wave_token", "score", "wellbeing", "assimilation"}
    ),
}
_ALLOWED_TYPES: Final[dict[MigrationLayer, tuple[type, ...]]] = {
    MigrationLayer.OBJECTIVE_MOVEMENT: (
        MigrationMovementRow,
        MigrationIntegrationEvidenceRow,
    ),
    MigrationLayer.SUBJECTIVE_CAUSE: (MigrationCauseRow, MigrationRouteRow),
    MigrationLayer.ANALYTICAL_WAVE: (
        MigrationWaveRow,
        MigrationClusterRow,
        MigrationCandidateRow,
        MigrationLineageRow,
        MigrationAlignmentRow,
    ),
    MigrationLayer.INTEGRATION_OUTCOME: (MigrationOutcomeRow,),
}


@dataclass(frozen=True, slots=True)
class ObjectiveMovementLayer:
    movements: tuple[object, ...] = ()
    integration_evidence: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class SubjectiveCauseLayer:
    causes: tuple[object, ...] = ()
    routes: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalyticalWaveLayer:
    waves: tuple[object, ...] = ()
    clusters: tuple[object, ...] = ()
    candidates: tuple[object, ...] = ()
    lineage: tuple[object, ...] = ()
    alignment: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class IntegrationOutcomeLayer:
    outcomes: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class MigrationLayers:
    objective: ObjectiveMovementLayer
    subjective: SubjectiveCauseLayer
    analytical: AnalyticalWaveLayer
    integration: IntegrationOutcomeLayer


def _field_names(row: object) -> set[str]:
    names: set[str] = set()
    if dataclasses.is_dataclass(row):
        names.update(item.name for item in dataclasses.fields(row))
    if isinstance(row, Mapping):
        names.update(str(key) for key in row)
    else:
        names.update(getattr(row, "__dict__", {}))
        for slot in getattr(type(row), "__slots__", ()) or ():
            if isinstance(slot, str):
                names.add(slot)
    return names


def _check(layer: MigrationLayer, row: object) -> None:
    leaked = _field_names(row) & _FORBIDDEN[layer]
    if leaked:
        field = sorted(leaked)[0]
        _LOG.error("migration_layer_leak layer=%s field=%s", layer.value, field)
        raise MigrationLayerLeakError(f"{layer.value}:{field}")
    if not isinstance(row, _ALLOWED_TYPES[layer]):
        _LOG.error("migration_layer_leak layer=%s field=row_type", layer.value)
        raise MigrationLayerLeakError(f"{layer.value}:row_type")


def assert_migration_layer_separation(layers: MigrationLayers) -> None:
    """Fail hard when any row leaks across the four layers."""
    if type(layers) is not MigrationLayers:
        raise TypeError("layers must be MigrationLayers")
    pairs: tuple[tuple[MigrationLayer, tuple[object, ...]], ...] = (
        (
            MigrationLayer.OBJECTIVE_MOVEMENT,
            (*layers.objective.movements, *layers.objective.integration_evidence),
        ),
        (
            MigrationLayer.SUBJECTIVE_CAUSE,
            (*layers.subjective.causes, *layers.subjective.routes),
        ),
        (
            MigrationLayer.ANALYTICAL_WAVE,
            (
                *layers.analytical.waves,
                *layers.analytical.clusters,
                *layers.analytical.candidates,
                *layers.analytical.lineage,
                *layers.analytical.alignment,
            ),
        ),
        (MigrationLayer.INTEGRATION_OUTCOME, tuple(layers.integration.outcomes)),
    )
    for layer, rows in pairs:
        for row in rows:
            _check(layer, row)


def project_migration_layers(rows: MigrationDisplacementHarvestRows) -> MigrationLayers:
    """Project one harvest into four separate layers and assert separation."""
    if type(rows) is not MigrationDisplacementHarvestRows:
        raise TypeError("rows must be MigrationDisplacementHarvestRows")
    layers = MigrationLayers(
        objective=ObjectiveMovementLayer(
            movements=rows.movements, integration_evidence=rows.integration_evidence
        ),
        subjective=SubjectiveCauseLayer(causes=rows.causes, routes=rows.routes),
        analytical=AnalyticalWaveLayer(
            waves=rows.waves,
            clusters=rows.clusters,
            candidates=rows.candidates,
            lineage=rows.lineage,
            alignment=rows.alignment,
        ),
        integration=IntegrationOutcomeLayer(outcomes=rows.outcomes),
    )
    assert_migration_layer_separation(layers)
    _LOG.debug(
        "migration_layers objective=%s subjective=%s analytical=%s integration=%s",
        len(rows.movements) + len(rows.integration_evidence),
        len(rows.causes) + len(rows.routes),
        len(rows.waves) + len(rows.clusters),
        len(rows.outcomes),
    )
    return layers
