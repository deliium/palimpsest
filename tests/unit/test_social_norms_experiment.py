"""Experiment X stays off the V1 gate and pairs a disabled arm with v17."""

from __future__ import annotations

import inspect
import logging

import pytest

from analysis.models import MetricAvailability
from analysis.social_norm_metrics import compute_emergent_social_norms
from analysis.specifications import MetricFamilyId, metric_specification
from experiments.catalog import experiment_x_social_norms
from experiments.composition import norm_belief_rows_from_ledgers
from experiments.social_norms_scenario import social_norms_scenario
from simulation.runner_models import SocialNormMode
from world.identifiers import EntityId


def test_repeated_conventions_value_keys_stay_unchanged() -> None:
    spec = metric_specification(MetricFamilyId.REPEATED_CONVENTIONS)
    assert spec.value_keys == (
        "top_motif_support",
        "motif_count",
        "motif_opportunity_coverage",
        "ngram_order_max",
    )


def test_experiment_x_pairs_v4_and_v17(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    parameters = inspect.signature(social_norms_scenario).parameters
    assert set(parameters) == {"seed", "max_ticks"}
    definition = experiment_x_social_norms()
    assert definition.experiment_id == "experiment-x-social-norms"
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["x-disabled"].runner_config
    enabled = by_id["x-enabled"].runner_config
    assert disabled.schema_version == "runner-config-v4"
    assert enabled.schema_version == "runner-config-v17"
    assert disabled.seed == enabled.seed
    assert disabled.scenario == enabled.scenario
    assert disabled.stochastic_identity == enabled.stochastic_identity
    scenario_fields = set(disabled.scenario.__dataclass_fields__)
    assert scenario_fields.isdisjoint(
        {
            "norm",
            "obligation",
            "culture",
            "roster",
            "moral",
            "friend",
            "enemy",
            "leader",
            "team",
            "faction",
            "member",
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
        agent.cognition.social_norm_mode for agent in disabled.agents
    } == {SocialNormMode.DISABLED}
    assert {
        agent.cognition.social_norm_mode for agent in enabled.agents
    } == {SocialNormMode.DETERMINISTIC}
    assert any("experiment_x_built" in record.getMessage() for record in caplog.records)
    text = "".join(record.getMessage() for record in caplog.records)
    assert "return_transfer" not in text


def test_experiment_metric_harvest_includes_both_blocks() -> None:
    class _Ledger:
        owner_id = type("Owner", (), {"value": "ada"})()
        beliefs = (
            type(
                "Belief",
                (),
                {
                    "pattern": type("Pattern", (), {"value": "return_transfer"})(),
                    "status": type("Status", (), {"value": "active"})(),
                    "confidence": 0.5,
                    "supporters": ("ben",),
                    "consequences": (),
                    "response": type(
                        "Response", (), {"value": "follow"}
                    )(),
                },
            )(),
        )

    belief_rows = norm_belief_rows_from_ledgers([_Ledger()], tick=3)
    document = compute_emergent_social_norms(
        {
            "behavior_rows": (
                {
                    "tick": 1,
                    "actor_id": "ada",
                    "kind": "give",
                    "other_id": "ben",
                    "success": True,
                    "location_id": "clearing",
                    "food_quantity": 2.0,
                },
            ),
            "belief_rows": belief_rows,
        },
        run_id="run-x",
        input_revision="rev-x",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert "return_transfer_rate" in document.values
    assert document.values["active_belief_count"] == 1
    assert "mean_confidence" in document.values
