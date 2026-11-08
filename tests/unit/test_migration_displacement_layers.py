# mypy: ignore-errors
"""Four-layer separation and hard leakage guard."""

from __future__ import annotations

import ast
import dataclasses
import logging
from pathlib import Path

import pytest

from agents.cognition.migration_displacement import (
    MigrationCauseKind,
    MigrationCauseSource,
)
from analysis.migration_displacement_events import (
    MigrationIntegrationEvidenceRow,
    MigrationMovementRow,
    migration_agent_token,
)
from analysis.migration_displacement_layers import (
    AnalyticalWaveLayer,
    IntegrationOutcomeLayer,
    MigrationLayer,
    MigrationLayerLeakError,
    MigrationLayers,
    ObjectiveMovementLayer,
    SubjectiveCauseLayer,
    assert_migration_layer_separation,
    project_migration_layers,
)
from analysis.migration_displacement_rows import (
    MIGRATION_OWNER_FAMILIES,
    MigrationCauseRow,
    MigrationDisplacementHarvestRows,
    MigrationOutcomeRow,
    MigrationWaveRow,
    harvest_migration_displacement_rows,
)
from simulation.migration_displacement_export import (
    MIGRATION_EXPORT_FAMILIES,
    migration_displacement_owner_export,
)
from tests.unit.migration_displacement_analysis_helpers import (
    POLICY,
    movement,
    p,
)
from tests.unit.migration_displacement_helpers import OWNER, cause, ledger, route

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src" / "analysis"


@dataclasses.dataclass(frozen=True)
class _Leaky:
    value: int = 0


def _fake(*names: str):
    return dataclasses.make_dataclass(
        "Fake", [(name, int, 0) for name in names], frozen=True
    )()


def _export(**kwargs):
    return migration_displacement_owner_export([ledger(**kwargs)])


def _harvest(owner_rows=(), movements=()):
    return harvest_migration_displacement_rows(owner_rows, movements, (), policy=POLICY)


def _wave_harvest():
    movements = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
    )
    rows = _export(
        causes=(
            cause(
                MigrationCauseKind.ENVIRONMENTAL_HAZARD,
                MigrationCauseSource.DIRECT_OBSERVATION,
                tick=1,
            ),
        )
    )
    return _harvest(rows, movements)


def test_four_layers_are_distinct_types() -> None:
    harvest = _wave_harvest()
    layers = project_migration_layers(harvest)
    kinds = {
        type(layers.objective),
        type(layers.subjective),
        type(layers.analytical),
        type(layers.integration),
    }
    assert kinds == {
        ObjectiveMovementLayer,
        SubjectiveCauseLayer,
        AnalyticalWaveLayer,
        IntegrationOutcomeLayer,
    }
    assert {item.value for item in MigrationLayer} == {
        "objective_movement",
        "subjective_cause",
        "analytical_wave",
        "integration_outcome",
    }
    assert type(layers.objective.movements[0]) is MigrationMovementRow
    assert type(layers.subjective.causes[0]) is MigrationCauseRow
    assert type(layers.analytical.waves[0]) is MigrationWaveRow
    assert (
        layers.integration.outcomes == ()
        or type(layers.integration.outcomes[0]) is MigrationOutcomeRow
    )
    # No row type is reused across layers.
    all_types = [
        {type(row) for row in layers.objective.movements},
        {type(row) for row in layers.subjective.causes},
        {type(row) for row in layers.analytical.waves},
        {type(row) for row in layers.integration.outcomes},
    ]
    flat = [t for group in all_types for t in group]
    assert len(flat) == len(set(flat))


@pytest.mark.parametrize(
    "field", ["cause_kind", "owner_token", "classification", "wave_token"]
)
def test_objective_layer_rejects_cause_and_owner_fields(field: str) -> None:
    layers = MigrationLayers(
        ObjectiveMovementLayer(movements=(_fake(field),)),
        SubjectiveCauseLayer(),
        AnalyticalWaveLayer(),
        IntegrationOutcomeLayer(),
    )
    with pytest.raises(MigrationLayerLeakError) as info:
        assert_migration_layer_separation(layers)
    assert str(info.value) == f"objective_movement:{field}"


@pytest.mark.parametrize("field", ["wave_token", "classification", "candidate_token"])
def test_subjective_layer_rejects_wave_and_classification_fields(field: str) -> None:
    layers = MigrationLayers(
        ObjectiveMovementLayer(),
        SubjectiveCauseLayer(causes=(_fake(field),)),
        AnalyticalWaveLayer(),
        IntegrationOutcomeLayer(),
    )
    with pytest.raises(MigrationLayerLeakError) as info:
        assert_migration_layer_separation(layers)
    assert str(info.value) == f"subjective_cause:{field}"


@pytest.mark.parametrize(
    "field",
    [
        "raw_owner_id",
        "raw_agent_id",
        "raw_entity_id",
        "refugee",
        "forced",
        "score",
        "composite",
        "wellbeing",
        "assimilation",
    ],
)
def test_analytical_layer_rejects_raw_identity_and_score_fields(field: str) -> None:
    layers = MigrationLayers(
        ObjectiveMovementLayer(),
        SubjectiveCauseLayer(),
        AnalyticalWaveLayer(waves=(_fake(field),)),
        IntegrationOutcomeLayer(),
    )
    with pytest.raises(MigrationLayerLeakError) as info:
        assert_migration_layer_separation(layers)
    assert str(info.value) == f"analytical_wave:{field}"


@pytest.mark.parametrize(
    "field", ["cause_kind", "wave_token", "score", "wellbeing", "assimilation"]
)
def test_integration_layer_rejects_cause_and_score_fields(field: str) -> None:
    layers = MigrationLayers(
        ObjectiveMovementLayer(),
        SubjectiveCauseLayer(),
        AnalyticalWaveLayer(),
        IntegrationOutcomeLayer(outcomes=(_fake(field),)),
    )
    with pytest.raises(MigrationLayerLeakError) as info:
        assert_migration_layer_separation(layers)
    assert str(info.value) == f"integration_outcome:{field}"


def test_wrong_row_type_in_a_layer_is_a_leak() -> None:
    layers = MigrationLayers(
        ObjectiveMovementLayer(movements=(_Leaky(),)),
        SubjectiveCauseLayer(),
        AnalyticalWaveLayer(),
        IntegrationOutcomeLayer(),
    )
    with pytest.raises(MigrationLayerLeakError, match="objective_movement:row_type"):
        assert_migration_layer_separation(layers)
    cross = MigrationLayers(
        ObjectiveMovementLayer(),
        SubjectiveCauseLayer(),
        AnalyticalWaveLayer(
            waves=(
                MigrationIntegrationEvidenceRow(
                    p("agent-1"), p("agent-2"), "residence", 1, 0, 0, "complete"
                ),
            )
        ),
        IntegrationOutcomeLayer(),
    )
    with pytest.raises(MigrationLayerLeakError, match="analytical_wave:row_type"):
        assert_migration_layer_separation(cross)


def test_missing_owner_export_is_missing_coverage(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        harvest = _harvest((), (movement("agent-1", "loc-a", "loc-b", 1),))
    assert harvest.coverage == "missing"
    assert harvest.causes == () and harvest.routes == ()
    assert harvest.owner_tokens == ()
    assert "migration_harvest_missing_owner_rows" in caplog.text
    # Objective rows are kept; nothing is invented.
    assert len(harvest.movements) == 1


def test_complete_and_partial_export_coverage() -> None:
    movements = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
    )
    rows = _export(causes=(cause(),), routes=(route(),))
    complete = _harvest(rows, movements)
    assert complete.coverage == "complete"
    assert complete.owner_tokens == (migration_agent_token(OWNER.value),)
    assert len(complete.causes) == 1 and len(complete.routes) == 1
    assert complete.causes[0].cause_kind == "resource_scarcity"
    partial = _harvest(
        rows,
        (movement("agent-1", "loc-a", "loc-b", 1, coverage="partial"),),
    )
    assert partial.coverage == "partial"
    assert _harvest(rows, ()).coverage == "partial"


def test_objective_only_subjective_only_and_analytical_only_layers() -> None:
    objective = project_migration_layers(
        MigrationDisplacementHarvestRows(
            movements=(movement("agent-1", "loc-a", "loc-b", 1),), coverage="partial"
        )
    )
    assert len(objective.objective.movements) == 1
    assert objective.subjective.causes == ()
    subjective = project_migration_layers(_harvest(_export(causes=(cause(),)), ()))
    assert len(subjective.subjective.causes) == 1
    assert subjective.objective.movements == ()
    analytical = project_migration_layers(_wave_harvest())
    assert len(analytical.analytical.waves) == 1


def test_already_normalized_harvest_is_accepted_idempotently() -> None:
    first = _wave_harvest()
    again = harvest_migration_displacement_rows(first, (), (), policy=POLICY)
    assert again == first
    assert harvest_migration_displacement_rows(again, (), (), policy=POLICY) == first
    duplicated = dataclasses.replace(first, causes=first.causes + first.causes)
    with pytest.raises(ValueError, match="duplicate_row"):
        harvest_migration_displacement_rows(duplicated, (), (), policy=POLICY)


def test_duplicate_owner_rows_and_unknown_family_are_rejected() -> None:
    rows = _export(causes=(cause(),))
    with pytest.raises(ValueError, match="duplicate_row"):
        _harvest(rows + rows, ())
    with pytest.raises(TypeError):
        _harvest((_Leaky(),), ())


def test_owner_families_match_the_export_contract() -> None:
    assert MIGRATION_OWNER_FAMILIES == MIGRATION_EXPORT_FAMILIES


def test_analysis_imports_do_not_reach_cognition_or_runtime() -> None:
    forbidden = (
        "agents.cognition",
        "simulation.runner",
        "experiments",
        "api",
        "persistence",
        "observer",
    )
    modules = sorted(SRC.glob("migration_displacement_*.py"))
    assert len(modules) >= 9
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                for bad in forbidden:
                    assert name != bad and not name.startswith(f"{bad}."), (
                        path.name,
                        name,
                    )
