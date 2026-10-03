"""Experiment Y stays off the V1 gate and pairs a disabled arm with v18."""

from __future__ import annotations

import inspect
import logging

import pytest

from analysis.models import MetricAvailability
from analysis.social_convention_metrics import compute_persistent_social_conventions
from analysis.specifications import MetricFamilyId, metric_specification
from experiments.catalog import experiment_y_social_conventions
from experiments.composition import convention_habit_rows_from_ledgers
from experiments.social_conventions_scenario import social_conventions_scenario
from simulation.runner_models import SocialConventionMode
from world.identifiers import EntityId


def test_repeated_conventions_value_keys_stay_unchanged() -> None:
    spec = metric_specification(MetricFamilyId.REPEATED_CONVENTIONS)
    assert spec.value_keys == (
        "top_motif_support",
        "motif_count",
        "motif_opportunity_coverage",
        "ngram_order_max",
    )


def test_experiment_y_pairs_v4_and_v18(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    parameters = inspect.signature(social_conventions_scenario).parameters
    assert set(parameters) == {"seed", "max_ticks"}
    definition = experiment_y_social_conventions()
    assert definition.experiment_id == "experiment-y-social-conventions"
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["y-disabled"].runner_config
    enabled = by_id["y-enabled"].runner_config
    assert disabled.schema_version == "runner-config-v4"
    assert enabled.schema_version == "runner-config-v18"
    assert disabled.seed == enabled.seed
    assert disabled.scenario == enabled.scenario
    assert disabled.stochastic_identity == enabled.stochastic_identity
    scenario_fields = set(disabled.scenario.__dataclass_fields__)
    assert scenario_fields.isdisjoint(
        {
            "tradition",
            "ritual",
            "convention",
            "culture",
            "ceremony",
            "roster",
            "custom",
        }
    )
    places = {place.entity_id.value: place for place in disabled.scenario.locations}
    assert set(places) == {"clearing"}
    assert places["clearing"].adjacent == ()
    bindings = {
        agent.agent_id.value: agent.entity_id.value for agent in disabled.agents
    }
    assert bindings == {
        "ada": "body-ada",
        "ben": "body-ben",
        "cy": "body-cy",
    }
    assert all(
        body.location_id == EntityId("clearing") for body in disabled.scenario.bodies
    )
    assert {
        agent.cognition.social_convention_mode for agent in disabled.agents
    } == {SocialConventionMode.DISABLED}
    assert {
        agent.cognition.social_convention_mode for agent in enabled.agents
    } == {SocialConventionMode.DETERMINISTIC}
    assert any("experiment_y_built" in record.getMessage() for record in caplog.records)
    text = "".join(record.getMessage() for record in caplog.records)
    assert "ritual" not in text
    assert "tradition" not in text


def test_experiment_metric_harvest_includes_both_blocks() -> None:
    class _Content:
        situation = type("Situation", (), {"value": "colocated_meeting"})()
        usual_action = "wait"

    class _Ledger:
        owner_id = type("Owner", (), {"value": "ada"})()
        beliefs = (
            type(
                "Belief",
                (),
                {
                    "content": _Content(),
                    "status": type("Status", (), {"value": "active"})(),
                    "strength": 0.5,
                    "participant_ids": ("ada", "ben"),
                    "transmission": type(
                        "Transmission", (), {"value": "observed"}
                    )(),
                    "remembered_explanation": type(
                        "Explanation", (), {"value": "social_contact"}
                    )(),
                    "conceptualization": type(
                        "Conceptualization", (), {"value": "none"}
                    )(),
                    "first_tick": 1,
                    "last_tick": 6,
                    "competing_variant_ids": (),
                },
            )(),
        )

    habit_rows = convention_habit_rows_from_ledgers([_Ledger()], tick=3)
    document = compute_persistent_social_conventions(
        {
            "objective_rows": (
                {
                    "tick": 1,
                    "actor_id": "ada",
                    "kind": "wait",
                    "other_id": None,
                    "success": True,
                    "location_id": "clearing",
                    "day_phase": None,
                },
                {
                    "tick": 1,
                    "actor_id": "ben",
                    "kind": "wait",
                    "other_id": None,
                    "success": True,
                    "location_id": "clearing",
                    "day_phase": None,
                },
            ),
            "habit_rows": habit_rows,
        },
        run_id="run-y",
        input_revision="rev-y",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert "recurrent_meeting_rate" in document.values
    assert document.values["active_habit_count"] == 1
    assert "mean_habit_strength" in document.values
