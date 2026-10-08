"""runner-config-v36 bounded_experimentation encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V35,
    RUNNER_SCHEMA_VERSION_V36,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_bounded_experimentation_spec,
    example_cultural_feature_provenance_spec,
    example_experiment_law,
    example_knowledge_genealogy_spec,
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
        seed=36,
        stochastic_identity="cmp-v36-experiment",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v36"),
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


def _experiment_config(**extra):
    base = _plain_base()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V36,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        bounded_experimentation=example_bounded_experimentation_spec(),
        **extra,
    )


def test_v36_round_trip_without_genealogy() -> None:
    config = _experiment_config()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V36
    assert round_trip.bounded_experimentation is not None
    assert round_trip.bounded_experimentation.learn_into_genealogy is False
    assert len(round_trip.bounded_experimentation.laws) == 1
    assert round_trip.knowledge_genealogy is None
    assert round_trip.cultural_feature_provenance is not None


def test_v35_genealogy_only_still_loads() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V35,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V35
    assert round_trip.knowledge_genealogy is not None
    assert round_trip.bounded_experimentation is None


def test_v35_plus_experimentation_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="bounded_experimentation_requires_v36"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V35,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            knowledge_genealogy=example_knowledge_genealogy_spec(),
            bounded_experimentation=example_bounded_experimentation_spec(),
        )


def test_experimentation_without_cultural_flag_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="bounded_experimentation_without_cultural_flag"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V36,
            v3_capability_flags=V3CapabilityFlags(),
            bounded_experimentation=example_bounded_experimentation_spec(),
        )


def test_experimentation_without_provenance_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="bounded_experimentation_requires_cultural_provenance"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V36,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            bounded_experimentation=example_bounded_experimentation_spec(),
        )


def test_v36_without_object_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="v36_requires_bounded_experimentation"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V36,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        )


def test_v36_without_provenance_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="v36_requires_cultural_provenance"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V36,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        )


def test_empty_laws_rejected() -> None:
    with pytest.raises(ValueError, match="bounded_experimentation_laws_empty"):
        example_bounded_experimentation_spec(laws=())


def test_duplicate_law_keys_rejected() -> None:
    law = example_experiment_law()
    with pytest.raises(ValueError, match="experiment_law_duplicate"):
        example_bounded_experimentation_spec(laws=(law, law))


def test_unprefixed_operand_rejected() -> None:
    with pytest.raises(ValueError, match="experiment_law_operand_unprefixed"):
        example_experiment_law(operand_a_kind="material")


def test_unknown_product_rejected() -> None:
    law = example_experiment_law(
        outcome_class="success",
        delta="emit_catalog_product",
        product_id="not-a-recipe",
    )
    base = _plain_base()
    with pytest.raises(ValueError, match="experiment_law_unknown_product"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V36,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            bounded_experimentation=example_bounded_experimentation_spec(laws=(law,)),
        )


def test_known_product_round_trip() -> None:
    law = example_experiment_law(
        outcome_class="success",
        delta="emit_catalog_product",
        product_id="harvest_wood",
        public_technique_token="tech:wood_join",
    )
    config = _with_catalog(_experiment_config())
    config = replace(
        config,
        bounded_experimentation=example_bounded_experimentation_spec(
            laws=(law,),
            learn_into_genealogy=True,
        ),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.bounded_experimentation is not None
    stored = round_trip.bounded_experimentation.laws[0]
    assert stored.product_id == "harvest_wood"
    assert stored.public_technique_token == "tech:wood_join"
    assert round_trip.bounded_experimentation.learn_into_genealogy is True


def test_mode_disabled_rejected() -> None:
    config = _experiment_config()
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    document["bounded_experimentation"]["mode"] = "disabled"
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    with pytest.raises(
        RunnerSerializationError, match="bounded_experimentation_mode_invalid"
    ):
        decode_runner_config(payload)


def test_forbidden_alias_rejected() -> None:
    config = _experiment_config()
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    document["bounded_experimentation"]["llm_physics"] = True
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    with pytest.raises(
        RunnerSerializationError, match="bounded_experimentation_forbidden_alias"
    ):
        decode_runner_config(payload)


def test_decode_v35_synthesizes_experimentation_none() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V35,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.bounded_experimentation is None
