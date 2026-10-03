"""Experiment AB cultural narratives paired arms."""

from __future__ import annotations

import inspect
import logging

import pytest

from analysis.cultural_narrative_metrics import compute_cultural_narrative_lineage
from analysis.models import MetricAvailability
from analysis.specifications import MetricFamilyId, metric_specification
from experiments.catalog import experiment_ab_cultural_narratives
from experiments.cultural_narratives_scenario import cultural_narratives_scenario
from simulation.runner_models import CulturalNarrativeMode


def test_cultural_narrative_lineage_family_is_registered() -> None:
    spec = metric_specification(MetricFamilyId.CULTURAL_NARRATIVE_LINEAGE)
    assert spec.version_identifier == "cultural_narrative_lineage@1"
    assert "persistence_rate" in spec.value_keys
    assert "inaccuracy_vs_objective" in spec.value_keys


def test_experiment_ab_pairs_disabled_v4_and_deterministic_v21(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    parameters = inspect.signature(cultural_narratives_scenario).parameters
    assert set(parameters) == {"seed", "max_ticks"}
    for forbidden in ("myth", "myths", "legend", "culture", "tradition", "narrative"):
        assert forbidden not in parameters
    definition = experiment_ab_cultural_narratives()
    assert definition.experiment_id == "experiment-ab-cultural-narratives"
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["ab-disabled"].runner_config
    enabled = by_id["ab-enabled"].runner_config
    assert disabled.schema_version == "runner-config-v4"
    assert enabled.schema_version == "runner-config-v21"
    assert disabled.seed == enabled.seed
    assert disabled.scenario == enabled.scenario
    assert disabled.stochastic_identity == enabled.stochastic_identity
    scenario_fields = set(disabled.scenario.__dataclass_fields__)
    assert scenario_fields.isdisjoint(
        {"myth", "myths", "legend", "culture", "tradition", "narrative"}
    )
    places = {place.entity_id.value: place for place in disabled.scenario.locations}
    assert set(places) == {"loc-clearing", "loc-ridge"}
    assert places["loc-clearing"].name == "Clearing"
    assert places["loc-ridge"].name == "Ridge"
    bindings = {
        agent.agent_id.value: agent.entity_id.value for agent in disabled.agents
    }
    assert bindings == {
        "ada": "body-ada",
        "ben": "body-ben",
        "cy": "body-cy",
        "dia": "body-dia",
    }
    assert {
        agent.cognition.cultural_narrative_mode for agent in disabled.agents
    } == {CulturalNarrativeMode.DISABLED}
    assert {
        agent.cognition.cultural_narrative_mode for agent in enabled.agents
    } == {CulturalNarrativeMode.DETERMINISTIC}
    assert any(
        "experiment_ab_built" in record.getMessage() for record in caplog.records
    )


def test_enabled_arm_metric_blocks_when_rows_diverge() -> None:
    document = compute_cultural_narrative_lineage(
        (
            {
                "tick": 1,
                "owner_id": "ada",
                "variant_id": "v1",
                "fingerprint": "fp-founding",
                "status": "active",
                "strength": 0.6,
                "origin": "observed_event",
                "founding_origin": "observed_event",
                "repetition_count": 3,
                "mutation_generation": 0,
                "has_source_event": True,
                "founding_had_source_event": True,
                "location_count": 1,
                "carrier_count": 1,
                "first_tick": 1,
                "last_tick": 1,
                "parent_count": 0,
                "competing_count": 0,
                "covers_source": True,
            },
            {
                "tick": 8,
                "owner_id": "ada",
                "variant_id": "v2",
                "fingerprint": "fp-child",
                "status": "active",
                "strength": 0.7,
                "origin": "retold_story",
                "founding_origin": "observed_event",
                "repetition_count": 4,
                "mutation_generation": 1,
                "has_source_event": False,
                "founding_had_source_event": True,
                "location_count": 2,
                "carrier_count": 3,
                "first_tick": 2,
                "last_tick": 8,
                "parent_count": 1,
                "competing_count": 1,
                "token_add_rate": 0.5,
                "token_loss_rate": 0.25,
                "covers_source": False,
                "transmission_root_id": "root-1",
            },
        ),
        run_id="run-ab",
        input_revision="rev-ab",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["inaccuracy_vs_objective"] == 1.0
    assert document.values["persistence_rate"] is not None
    assert document.values["active_variant_count"] == 1


def test_scenario_rejects_myth_roster_kwargs() -> None:
    with pytest.raises(TypeError):
        cultural_narratives_scenario(myths=("flood",))  # type: ignore[call-arg]
