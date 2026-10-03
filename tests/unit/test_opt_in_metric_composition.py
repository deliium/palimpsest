"""Composition helpers for expanded opt-in metric families."""

from __future__ import annotations

from analysis.metric_service import MetricComputationInputs
from analysis.prediction_calibration_metrics import CalibrationRow
from analysis.spatial_control_metrics import SpatialActionRow
from analysis.territorial_concentration_metrics import TerritorialConcentrationRow
from experiments.composition import (
    CulturalChannelRow,
    cultural_channel_rows_from_convention_habits,
    cultural_channel_rows_from_norm_beliefs,
    territorial_control_rows_from_spatial_actions,
    territorial_presence_rows_from_spatial_actions,
)
from experiments.metric_collection import inputs_with_opt_in_metric_rows


def test_territorial_rows_from_spatial_actions() -> None:
    actions = (
        SpatialActionRow(
            tick=0, ordinal=0, agent_id="a1", action_kind="move", location_id="loc-a"
        ),
        SpatialActionRow(
            tick=1,
            ordinal=0,
            agent_id="a1",
            action_kind="take",
            location_id="loc-b",
        ),
        SpatialActionRow(
            tick=2,
            ordinal=0,
            agent_id="a2",
            action_kind="sleep",
            location_id="loc-a",
            success=False,
        ),
    )
    presence = territorial_presence_rows_from_spatial_actions(actions)
    control = territorial_control_rows_from_spatial_actions(actions)
    assert len(presence) == 2
    assert all(type(row) is TerritorialConcentrationRow for row in presence)
    assert {row.location_id for row in presence} == {"loc-a", "loc-b"}
    assert len(control) == 1
    assert control[0].location_id == "loc-b"


def test_cultural_channel_rows_from_norm_and_convention_dicts() -> None:
    norms = cultural_channel_rows_from_norm_beliefs(
        (
            {
                "owner_id": "a1",
                "pattern": "share",
                "status": "active",
                "response": "comply",
            },
        )
    )
    conventions = cultural_channel_rows_from_convention_habits(
        (
            {
                "owner_id": "a2",
                "situation": "morning",
                "usual_action": "greet",
            },
        )
    )
    assert norms == (
        CulturalChannelRow(owner_id="a1", token="share|active|comply"),
    )
    assert conventions == (
        CulturalChannelRow(owner_id="a2", token="morning|greet"),
    )


def test_inputs_with_opt_in_attaches_territorial_from_events_none_safe() -> None:
    base = MetricComputationInputs(
        run_id="run-opt",
        input_revision="rev-opt",
        window_end=0,
    )
    untouched = inputs_with_opt_in_metric_rows(base, events=None)
    assert untouched.spatial_action_rows is None
    assert untouched.territorial_presence_rows is None
    assert untouched.prediction_calibration_rows is None

    with_claims = inputs_with_opt_in_metric_rows(
        base,
        belief_convergence_claims=(),
        cultural_naming_rows=(CulturalChannelRow(owner_id="a1", token="rock"),),
    )
    # Empty-but-present claim sequence still wires the opt-in field.
    assert with_claims.belief_convergence_claims is not None
    assert with_claims.cultural_naming_rows is not None
    assert with_claims.prediction_calibration_rows is None


def test_calibration_row_type_is_exported_shape() -> None:
    row = CalibrationRow(predicted_confidence=0.75, empirical_outcome=0.5)
    assert 0.0 <= row.predicted_confidence <= 1.0
