"""Runner-config-v19 accepts artifact interpretation mode."""

from __future__ import annotations

import json
import logging
from dataclasses import replace

import pytest

from agents.cognition.artifacts import (
    ArtifactInterpretationMode as CognitionArtifactInterpretationMode,
)
from simulation.persistence import EVENT_SCHEMA_VERSION, PERSISTENCE_CODEC_VERSION
from simulation.runner import _cognition_config_for
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V18,
    RUNNER_SCHEMA_VERSION_V19,
    ArtifactInterpretationMode,
    CognitionTraceDetail,
    CognitionTraceSpec,
    GroupFormationMode,
    MortalityMode,
    SocialConventionMode,
    SocialNormMode,
    V2CapabilityFlags,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.unit.test_runner_serialization import _configured
from world.environment import example_environmental_dynamics

pytestmark = pytest.mark.unit


def test_runner_v19_wires_deterministic_artifact_interpretation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    assert EVENT_SCHEMA_VERSION == 5
    assert PERSISTENCE_CODEC_VERSION == "v2"
    flags = V2CapabilityFlags(multi_hop_testimony_tracking=True)
    assert flags.unimplemented_enabled_names() == ("multi_hop_testimony_tracking",)
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    quiet = json.loads(encode_runner_config(base).decode("utf-8"))
    assert quiet["schema_version"] == "runner-config-v4"
    assert "artifact_interpretation_mode" not in quiet["agents"][0]["cognition"]
    agent = base.agents[0]
    early = replace(
        agent,
        cognition=replace(
            agent.cognition,
            artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
        ),
    )
    with pytest.raises(ValueError, match="artifact_interpretation_mode_requires_v19"):
        replace(base, agents=(early,))
    conventions_only = replace(
        agent,
        cognition=replace(
            agent.cognition,
            social_convention_mode=SocialConventionMode.DETERMINISTIC,
        ),
    )
    conventions_config = replace(
        base, agents=(conventions_only,), schema_version=RUNNER_SCHEMA_VERSION_V18
    )
    conventions_doc = json.loads(encode_runner_config(conventions_config).decode("utf-8"))
    assert conventions_doc["schema_version"] == "runner-config-v18"
    assert "artifact_interpretation_mode" not in conventions_doc["agents"][0]["cognition"]
    assert (
        conventions_doc["agents"][0]["cognition"]["social_convention_mode"]
        == "deterministic"
    )
    with pytest.raises(ValueError, match="v19_requires_artifact_interpretation"):
        replace(conventions_config, schema_version=RUNNER_SCHEMA_VERSION_V19)
    enabled = replace(base, agents=(early,), schema_version=RUNNER_SCHEMA_VERSION_V19)
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v19"
    assert (
        document["agents"][0]["cognition"]["artifact_interpretation_mode"]
        == "deterministic"
    )
    assert document["agents"][0]["cognition"]["social_convention_mode"] == "disabled"
    assert decode_runner_config(encoded) == enabled
    both = replace(
        early,
        cognition=replace(
            early.cognition,
            social_convention_mode=SocialConventionMode.DETERMINISTIC,
            social_norm_mode=SocialNormMode.DETERMINISTIC,
            group_formation_mode=GroupFormationMode.DETERMINISTIC,
        ),
    )
    traced = replace(
        base,
        agents=(both,),
        schema_version=RUNNER_SCHEMA_VERSION_V19,
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
    assert decode_runner_config(encode_runner_config(traced)) == traced
    caplog.set_level(logging.INFO, logger="simulation.runner")
    replace(base, agents=(early,), schema_version=RUNNER_SCHEMA_VERSION_V19)
    assert any(
        "artifact_config schema_version=runner-config-v19 mode_count=1 "
        "artifacts_active=False" in record.getMessage()
        for record in caplog.records
    )
    built = _cognition_config_for(
        early.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert (
        built.artifact_interpretation_mode
        is CognitionArtifactInterpretationMode.DETERMINISTIC
    )


def test_empty_artifacts_disabled_keeps_default_write_pair() -> None:
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    document = json.loads(encode_runner_config(base).decode("utf-8"))
    assert document["schema_version"] == "runner-config-v4"
    assert "artifact_interpretation_mode" not in document["agents"][0]["cognition"]
    assert EVENT_SCHEMA_VERSION == 5
    assert PERSISTENCE_CODEC_VERSION == "v2"
    assert base.scenario.artifacts == ()
    assert all(
        agent.cognition.artifact_interpretation_mode
        is ArtifactInterpretationMode.DISABLED
        for agent in base.agents
    )
