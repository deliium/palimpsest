"""runner-config-v37 technique_lifecycle encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V36,
    RUNNER_SCHEMA_VERSION_V37,
    AgentCognitionSpec,
    AgentRunnerSpec,
    TechniqueMaterialAnchor,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_bounded_experimentation_spec,
    example_cultural_feature_provenance_spec,
    example_knowledge_genealogy_spec,
    example_technique_lifecycle_spec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog


def _plain_base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=37,
        stochastic_identity="cmp-v37-lifecycle",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v37"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_a,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_a),
            ),
            AgentRunnerSpec(
                agent_id=agent_b,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_b),
            ),
        ),
        max_ticks=2,
    )


def _with_catalog(config):
    catalog = example_production_catalog()
    agents = tuple(
        replace(
            agent,
            cognition=replace(agent.cognition, production_catalog=catalog),
        )
        for agent in config.agents
    )
    return replace(config, agents=agents)


def _lifecycle_config(**extra):
    base = _plain_base()
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V37,
        "v3_capability_flags": V3CapabilityFlags(cultural_historical_memory=True),
        "cultural_feature_provenance": example_cultural_feature_provenance_spec(),
        "knowledge_genealogy": example_knowledge_genealogy_spec(),
        "technique_lifecycle": example_technique_lifecycle_spec(),
    }
    fields.update(extra)
    return replace(base, **fields)


def test_v37_round_trip_with_anchor() -> None:
    anchor = TechniqueMaterialAnchor(
        content_key="tech:hafting", recipe_id="harvest_wood"
    )
    config = replace(
        _with_catalog(_lifecycle_config()),
        technique_lifecycle=example_technique_lifecycle_spec(
            material_anchors=(anchor,),
            diffusion_window_ticks=8,
            rare_max=1,
            rediscovery_latch_ticks=4,
        ),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V37
    assert round_trip.technique_lifecycle is not None
    assert round_trip.technique_lifecycle.diffusion_window_ticks == 8
    assert (
        round_trip.technique_lifecycle.material_anchors[0].recipe_id == "harvest_wood"
    )
    assert round_trip.knowledge_genealogy is not None
    assert round_trip.bounded_experimentation is None


def test_v36_experimentation_only_still_loads() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V36,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        bounded_experimentation=example_bounded_experimentation_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V36
    assert round_trip.bounded_experimentation is not None
    assert round_trip.technique_lifecycle is None


def test_v37_plus_optional_experimentation_loads() -> None:
    config = _lifecycle_config(
        bounded_experimentation=example_bounded_experimentation_spec()
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.bounded_experimentation is not None
    assert round_trip.technique_lifecycle is not None


def test_cultural_only_v37_loads_without_population_lifecycle() -> None:
    config = _lifecycle_config()
    assert config.population_lifecycle is None
    assert config.v3_capability_flags.generational_population is False
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.technique_lifecycle is not None
    assert round_trip.population_lifecycle is None


def test_v37_without_lifecycle_object_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="v37_requires_technique_lifecycle"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V37,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            knowledge_genealogy=example_knowledge_genealogy_spec(),
        )


def test_lifecycle_without_cultural_flag_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="technique_lifecycle_without_cultural_flag"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V37,
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            knowledge_genealogy=example_knowledge_genealogy_spec(),
            technique_lifecycle=example_technique_lifecycle_spec(),
        )


def test_lifecycle_without_provenance_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="technique_lifecycle_requires_cultural_provenance"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V37,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            knowledge_genealogy=example_knowledge_genealogy_spec(),
            technique_lifecycle=example_technique_lifecycle_spec(),
        )


def test_lifecycle_without_genealogy_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="technique_lifecycle_requires_knowledge_genealogy"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V37,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            technique_lifecycle=example_technique_lifecycle_spec(),
        )


def test_v36_plus_lifecycle_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="technique_lifecycle_requires_v37"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V36,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            knowledge_genealogy=example_knowledge_genealogy_spec(),
            bounded_experimentation=example_bounded_experimentation_spec(),
            technique_lifecycle=example_technique_lifecycle_spec(),
        )


def test_duplicate_anchor_rejected() -> None:
    anchor = TechniqueMaterialAnchor(
        content_key="tech:hafting", recipe_id="harvest_wood"
    )
    with pytest.raises(ValueError, match="technique_anchor_duplicate"):
        example_technique_lifecycle_spec(material_anchors=(anchor, anchor))


def test_unknown_recipe_rejected() -> None:
    anchor = TechniqueMaterialAnchor(
        content_key="tech:hafting", recipe_id="missing_recipe"
    )
    with pytest.raises(ValueError, match="technique_anchor_unknown_recipe"):
        _lifecycle_config(
            technique_lifecycle=example_technique_lifecycle_spec(
                material_anchors=(anchor,)
            )
        )


def test_content_key_without_tech_prefix_rejected() -> None:
    with pytest.raises(ValueError, match="technique_anchor_content_key"):
        TechniqueMaterialAnchor(content_key="hafting", recipe_id="harvest_wood")


def test_mode_disabled_rejected() -> None:
    config = _lifecycle_config()
    document = json.loads(encode_runner_config(config))
    document["technique_lifecycle"]["mode"] = "disabled"
    with pytest.raises(
        RunnerSerializationError, match="technique_lifecycle_mode_invalid"
    ):
        decode_runner_config(json.dumps(document).encode())


def test_requires_technique_rejected() -> None:
    anchor = TechniqueMaterialAnchor(
        content_key="tech:hafting", recipe_id="harvest_wood"
    )
    config = replace(
        _with_catalog(_lifecycle_config()),
        technique_lifecycle=example_technique_lifecycle_spec(
            material_anchors=(anchor,)
        ),
    )
    document = json.loads(encode_runner_config(config))
    document["technique_lifecycle"]["material_anchors"][0]["requires_technique"] = (
        "tech:other"
    )
    with pytest.raises(
        RunnerSerializationError, match="technique_anchor_prerequisite_forbidden"
    ):
        decode_runner_config(json.dumps(document).encode())


def test_technology_tree_alias_rejected() -> None:
    config = _lifecycle_config()
    document = json.loads(encode_runner_config(config))
    document["technique_lifecycle"]["technology_tree"] = True
    with pytest.raises(
        RunnerSerializationError, match="technique_lifecycle_forbidden_alias"
    ):
        decode_runner_config(json.dumps(document).encode())
