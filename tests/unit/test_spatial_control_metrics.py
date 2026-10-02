"""Spatial-control readings stay off the catalog until rows are supplied."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from analysis.spatial_control_metrics import (
    SPATIAL_CONTROL_METRIC_VERSION,
    SpatialControlError,
    compute_spatial_control,
)
from analysis.specifications import ACTION_VOCABULARY_V1
from experiments.composition import spatial_action_rows_from_events
from experiments.metric_collection import inputs_with_spatial_rows

_ROOT = Path(__file__).resolve().parents[2]


def _action(tick: int, agent: str, kind: str, *, ordinal: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        tick=tick,
        ordinal=ordinal,
        agent_id=agent,
        action_kind=kind,
        location_id="loc-1",
        success=True,
    )


def _claim(owner: str, strength: float, *, kind: str = "location") -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=owner,
        target_kind=kind,
        target_entity_id="loc-1",
        strength=strength,
    )


def _compute(actions: tuple[object, ...], claims: tuple[object, ...] | None):
    return compute_spatial_control(
        actions,
        claims,
        run_id="run-spatial",
        input_revision="rev-spatial",
    )


def test_two_windows_are_repeated_control_and_one_is_not() -> None:
    single = _compute((_action(0, "a", "move"), _action(1, "a", "sleep")), None)
    assert single.availability is MetricAvailability.PRESENT
    assert single.values["repeated_control"] is False
    assert single.metric_family == "spatial_control"
    assert (
        f"{single.metric_family}@{single.algorithm_version}"
        == SPATIAL_CONTROL_METRIC_VERSION
    )
    repeated = _compute(
        (
            _action(0, "a", "move"),
            _action(1, "a", "sleep"),
            _action(2, "a", "eat"),
            _action(3, "a", "move"),
            _action(4, "a", "sleep"),
        ),
        None,
    )
    assert repeated.values["repeated_control"] is True
    assert repeated.values["control_contest"] is False
    assert repeated.values["layer"] == "research_analytics"
    assert repeated.values["claim_contest"] == MetricAvailability.ABSENT.value


def test_two_agents_with_two_windows_yield_control_contest() -> None:
    document = _compute(
        (
            _action(0, "a", "move"),
            _action(1, "a", "sleep"),
            _action(2, "a", "eat"),
            _action(3, "a", "move"),
            _action(4, "a", "sleep"),
            _action(5, "b", "move"),
            _action(6, "b", "sleep"),
            _action(7, "b", "eat"),
            _action(8, "b", "move"),
            _action(9, "b", "sleep"),
        ),
        None,
    )
    assert document.values["control_contest"] is True
    assert document.values["contest_source"] == "objective_control"
    assert document.values["claim_contest"] == MetricAvailability.ABSENT.value


def test_claim_heads_at_threshold_contest_and_omission_stays_absent() -> None:
    contested = _compute(
        (_action(0, "a", "move"), _action(1, "a", "sleep")),
        (_claim("owner-a", 0.40), _claim("owner-b", 0.40)),
    )
    assert contested.values["claim_contest"] is True
    assert contested.values["contest_source"] == "subjective_claims"
    assert contested.values["claim_contest_source"] == "subjective_claims"
    omitted = _compute(
        (
            _action(0, "a", "move"),
            _action(1, "a", "sleep"),
            _action(2, "a", "eat"),
            _action(3, "a", "move"),
            _action(4, "a", "sleep"),
            _action(5, "b", "move"),
            _action(6, "b", "sleep"),
            _action(7, "b", "eat"),
            _action(8, "b", "move"),
            _action(9, "b", "sleep"),
        ),
        None,
    )
    assert omitted.values["control_contest"] is True
    assert omitted.values["claim_contest"] == MetricAvailability.ABSENT.value


def test_empty_action_rows_are_absent() -> None:
    document = _compute((), None)
    assert document.availability is MetricAvailability.ABSENT
    assert document.values["layer"] == "research_analytics"


def test_unknown_kind_and_non_finite_strength_fail_closed() -> None:
    with pytest.raises(SpatialControlError) as unknown:
        _compute((), (_claim("owner-a", 0.40, kind="territory"),))
    assert unknown.value.reason_code == "unknown_target_kind"
    with pytest.raises(SpatialControlError) as non_finite:
        _compute((), (_claim("owner-a", math.nan),))
    assert non_finite.value.reason_code == "not_finite"


def test_assemble_omits_spatial_control_when_rows_are_absent() -> None:
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-m",
            input_revision="rev-abc",
            window_end=1,
        )
    )
    assert "spatial_control" not in {doc.metric_family for doc in bundle.documents}
    present = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-m",
            input_revision="rev-abc",
            window_end=1,
            spatial_action_rows=(),
            spatial_claim_rows=None,
        )
    )
    spatial = [
        doc
        for doc in present.documents
        if doc.metric_family == "spatial_control"
    ]
    assert len(spatial) == 1
    assert spatial[0].availability is MetricAvailability.ABSENT


def test_vocabulary_stays_closed_and_metric_does_not_import_agents() -> None:
    assert "resource_harvested" not in ACTION_VOCABULARY_V1
    assert "structure_built" not in ACTION_VOCABULARY_V1
    source = (_ROOT / "src/analysis/spatial_control_metrics.py").read_text()
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(name == "agents" or name.startswith("agents.") for name in imported)
    assert "observer" not in imported
    assert not any("WorldEngine" in name for name in imported)
    assert "applied_actions_from_world_events" not in source


def test_event_log_keeps_production_kinds_outside_runner_result() -> None:
    events = (
        SimpleNamespace(
            tick=1,
            sequence=0,
            actor_id=SimpleNamespace(value="agent-a"),
            details=SimpleNamespace(
                kind="resource_harvested",
                success=True,
                location_id=SimpleNamespace(value="loc-1"),
            ),
            occurrence=None,
        ),
    )
    rows = spatial_action_rows_from_events(events)
    assert rows[0].action_kind == "resource_harvested"
    inputs = inputs_with_spatial_rows(
        MetricComputationInputs(
            run_id="run-m",
            input_revision="rev-abc",
            window_end=1,
        ),
        events,
        claim_ledgers=None,
    )
    assert inputs.spatial_action_rows is not None
    assert inputs.spatial_claim_rows == ()
    untouched = inputs_with_spatial_rows(
        MetricComputationInputs(
            run_id="run-m",
            input_revision="rev-abc",
            window_end=1,
        ),
        None,
    )
    assert untouched.spatial_action_rows is None
    result_source = (_ROOT / "src/simulation/runner_models.py").read_text()
    assert "spatial_action_rows" not in result_source
    assert "spatial_claim_rows" not in result_source
