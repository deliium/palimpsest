"""Experiment AA stays off the V1 gate and pairs a disabled arm with v20."""

from __future__ import annotations

import inspect
import logging

import pytest

from analysis.models import MetricAvailability
from analysis.semantic_naming_metrics import compute_emergent_semantic_naming
from analysis.specifications import MetricFamilyId, metric_specification
from experiments.catalog import experiment_aa_emergent_naming
from experiments.emergent_naming_scenario import emergent_naming_scenario
from simulation.runner_models import SemanticNamingMode
from world.identifiers import EntityId


def test_emergent_semantic_naming_family_is_registered() -> None:
    spec = metric_specification(MetricFamilyId.EMERGENT_SEMANTIC_NAMING)
    assert spec.version_identifier == "emergent_semantic_naming@1"
    assert "shared_label_rate" in spec.value_keys
    assert "meaning_shift_rate" in spec.value_keys


def test_experiment_aa_pairs_v4_and_v20(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    parameters = inspect.signature(emergent_naming_scenario).parameters
    assert set(parameters) == {"seed", "max_ticks"}
    assert "language" not in parameters
    assert "lexicon" not in parameters
    assert "glossary" not in parameters
    assert "dialect" not in parameters
    definition = experiment_aa_emergent_naming()
    assert definition.experiment_id == "experiment-aa-emergent-naming"
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["aa-disabled"].runner_config
    enabled = by_id["aa-enabled"].runner_config
    assert disabled.schema_version == "runner-config-v4"
    assert enabled.schema_version == "runner-config-v20"
    assert disabled.seed == enabled.seed
    assert disabled.scenario == enabled.scenario
    assert disabled.stochastic_identity == enabled.stochastic_identity
    scenario_fields = set(disabled.scenario.__dataclass_fields__)
    assert scenario_fields.isdisjoint(
        {
            "language",
            "lexicon",
            "glossary",
            "dialect",
            "shared_name",
            "culture",
        }
    )
    places = {place.entity_id.value: place for place in disabled.scenario.locations}
    assert set(places) == {"loc-forest", "loc-clearing"}
    assert places["loc-forest"].name == "Northern Forest"
    assert places["loc-clearing"].name == "Clearing"
    bindings = {
        agent.agent_id.value: agent.entity_id.value for agent in disabled.agents
    }
    assert bindings == {
        "alice": "body-alice",
        "bob": "body-bob",
        "cy": "body-cy",
    }
    assert all(
        body.location_id == EntityId("loc-forest") for body in disabled.scenario.bodies
    )
    assert {
        agent.cognition.semantic_naming_mode for agent in disabled.agents
    } == {SemanticNamingMode.DISABLED}
    assert {
        agent.cognition.semantic_naming_mode for agent in enabled.agents
    } == {SemanticNamingMode.DETERMINISTIC}
    assert any("experiment_aa_built" in record.getMessage() for record in caplog.records)


def test_enabled_arm_metric_blocks_requested_when_rows_exist() -> None:
    document = compute_emergent_semantic_naming(
        (
            {
                "tick": 4,
                "owner_id": "alice",
                "label_token": "place_aaaa1111",
                "referent_kind": "location",
                "top_candidate_id": "loc-forest",
                "status": "active",
                "strength": 0.5,
                "sense_revision": 0,
                "transmission": "observed",
            },
            {
                "tick": 4,
                "owner_id": "bob",
                "label_token": "place_aaaa1111",
                "referent_kind": "location",
                "top_candidate_id": "loc-forest",
                "status": "active",
                "strength": 0.55,
                "sense_revision": 0,
                "transmission": "communicated",
            },
        ),
        run_id="run-aa",
        input_revision="rev-aa",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert "shared_label_rate" in document.values
    assert "preferred_label_agreement" in document.values
    assert "meaning_shift_rate" in document.values
    assert "label_turnover_rate" in document.values
