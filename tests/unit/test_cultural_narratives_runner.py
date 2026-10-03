"""Runner-config-v21 accepts cultural narrative mode."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.cognition.configuration import CognitionCulturalNarrativeMode
from simulation.persistence import EVENT_SCHEMA_VERSION, PERSISTENCE_CODEC_VERSION
from simulation.runner import _cognition_config_for
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V20,
    RUNNER_SCHEMA_VERSION_V21,
    ArtifactInterpretationMode,
    CognitionTraceDetail,
    CognitionTraceSpec,
    CulturalNarrativeMode,
    GroupFormationMode,
    MortalityMode,
    SemanticNamingMode,
    SocialConventionMode,
    SocialNormMode,
    V2CapabilityFlags,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.unit.test_runner_serialization import _configured
from world.environment import example_environmental_dynamics

pytestmark = pytest.mark.unit


def test_runner_v21_wires_deterministic_cultural_narratives() -> None:
    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    assert EVENT_SCHEMA_VERSION == 5
    assert PERSISTENCE_CODEC_VERSION == "v2"
    flags = V2CapabilityFlags(multi_hop_testimony_tracking=True)
    assert flags.unimplemented_enabled_names() == ("multi_hop_testimony_tracking",)
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    quiet = json.loads(encode_runner_config(base).decode("utf-8"))
    assert quiet["schema_version"] == "runner-config-v4"
    assert "cultural_narrative_mode" not in quiet["agents"][0]["cognition"]
    agent = base.agents[0]
    early = replace(
        agent,
        cognition=replace(
            agent.cognition,
            cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
        ),
    )
    with pytest.raises(ValueError, match="cultural_narrative_mode_requires_v21"):
        replace(base, agents=(early,))
    naming_only = replace(
        agent,
        cognition=replace(
            agent.cognition,
            semantic_naming_mode=SemanticNamingMode.DETERMINISTIC,
        ),
    )
    naming_config = replace(
        base, agents=(naming_only,), schema_version=RUNNER_SCHEMA_VERSION_V20
    )
    naming_doc = json.loads(encode_runner_config(naming_config).decode("utf-8"))
    assert naming_doc["schema_version"] == "runner-config-v20"
    assert "cultural_narrative_mode" not in naming_doc["agents"][0]["cognition"]
    assert (
        naming_doc["agents"][0]["cognition"]["semantic_naming_mode"] == "deterministic"
    )
    with pytest.raises(ValueError, match="v21_requires_cultural_narratives"):
        replace(naming_config, schema_version=RUNNER_SCHEMA_VERSION_V21)
    enabled = replace(base, agents=(early,), schema_version=RUNNER_SCHEMA_VERSION_V21)
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v21"
    assert (
        document["agents"][0]["cognition"]["cultural_narrative_mode"]
        == "deterministic"
    )
    assert document["agents"][0]["cognition"]["semantic_naming_mode"] == "disabled"
    assert decode_runner_config(encoded) == enabled
    both = replace(
        early,
        cognition=replace(
            early.cognition,
            semantic_naming_mode=SemanticNamingMode.DETERMINISTIC,
            artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
            social_convention_mode=SocialConventionMode.DETERMINISTIC,
            social_norm_mode=SocialNormMode.DETERMINISTIC,
            group_formation_mode=GroupFormationMode.DETERMINISTIC,
        ),
    )
    traced = replace(
        base,
        agents=(both,),
        schema_version=RUNNER_SCHEMA_VERSION_V21,
        environmental_dynamics=example_environmental_dynamics(),
        capability_flags=V2CapabilityFlags(extended_self_model=True),
        cognition_trace=CognitionTraceSpec(
            enabled=True,
            detail=CognitionTraceDetail.SUMMARY,
        ),
    )
    traced_doc = json.loads(encode_runner_config(traced).decode("utf-8"))
    assert traced_doc["capability_flags"]["extended_self_model"] is True
    assert traced_doc["cognition_trace"]["enabled"] is True
    assert "environmental_dynamics" in traced_doc
    cognition = traced_doc["agents"][0]["cognition"]
    assert cognition["social_norm_mode"] == "deterministic"
    assert cognition["social_convention_mode"] == "deterministic"
    assert cognition["group_formation_mode"] == "deterministic"
    assert cognition["artifact_interpretation_mode"] == "deterministic"
    assert cognition["semantic_naming_mode"] == "deterministic"
    assert cognition["cultural_narrative_mode"] == "deterministic"
    assert decode_runner_config(encode_runner_config(traced)) == traced
    built = _cognition_config_for(
        early.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.cultural_narrative_mode is CognitionCulturalNarrativeMode.DETERMINISTIC
    assert built.cultural_narrative_policy is not None
    assert built.cultural_narrative_policy.version == "cultural-narratives.v1"


def test_disabled_cultural_narratives_keeps_default_write() -> None:
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    document = json.loads(encode_runner_config(base).decode("utf-8"))
    assert document["schema_version"] == "runner-config-v4"
    assert "cultural_narrative_mode" not in document["agents"][0]["cognition"]
    assert all(
        agent.cognition.cultural_narrative_mode is CulturalNarrativeMode.DISABLED
        for agent in base.agents
    )
