"""V4-08 evidence-testimony seam: legal_disputes ownership and cognition mode."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    EVIDENCE_TESTIMONY_CONTEXT_ID,
    EVIDENCE_TESTIMONY_IS_CAPABILITY_FLAG,
    EVIDENCE_TESTIMONY_POLICY_VERSION,
    EVIDENCE_TESTIMONY_REQUIRED_RUNNER_SCHEMA,
    default_evidence_policy,
)
from agents.cognition.configuration import (
    CognitionEvidenceMode,
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner import _cognition_config_for, _evidence_testimony_enabled
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import encode_runner_config
from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-evidence-testimony-config",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-evidence-testimony"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=2,
    )


def _config(
    *,
    legal_disputes: bool = False,
    formal_rules: bool = False,
) -> SimulationRunnerConfig:
    return replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(
            legal_disputes=legal_disputes,
            formal_rules=formal_rules,
        ),
    )


def test_evidence_context_pins_the_existing_flag() -> None:
    assert EVIDENCE_TESTIMONY_CONTEXT_ID == "legal_disputes"
    assert EVIDENCE_TESTIMONY_REQUIRED_RUNNER_SCHEMA == "runner-config-v56"
    assert EVIDENCE_TESTIMONY_IS_CAPABILITY_FLAG is False
    assert EVIDENCE_TESTIMONY_POLICY_VERSION == "evidence-testimony.v1"
    assert "evidence" not in V4_CAPABILITY_FLAGS


def test_v4_registry_keeps_fourteen_contexts_and_twelve_flags() -> None:
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    owned = {
        name
        for name in V4_CAPABILITY_FLAGS
        if V4CapabilityFlags(**{name: True}).owned_enabled_names() == (name,)
    }
    assert owned == {"organizations", "formal_rules", "legal_disputes", "diplomacy"}


@pytest.mark.parametrize(
    "schema_version",
    (RUNNER_SCHEMA_VERSION_V4, RUNNER_SCHEMA_VERSION_V55),
)
def test_legal_disputes_requires_v56_on_older_schemas(
    schema_version: str,
) -> None:
    with pytest.raises(ValueError, match="code=v4_capability_requires_v56"):
        replace(
            _base(),
            schema_version=schema_version,
            v4_capability_flags=V4CapabilityFlags(legal_disputes=True),
        )


def test_legal_disputes_on_v56_without_formal_rules_enables_evidence() -> None:
    config = _config(legal_disputes=True, formal_rules=False)

    assert config.v4_capability_flags.legal_disputes is True
    assert config.v4_capability_flags.formal_rules is False
    assert config.v4_capability_flags.unimplemented_enabled_names() == ()
    assert _evidence_testimony_enabled(config) is True


def test_legal_disputes_on_v56_with_formal_rules_enables_evidence() -> None:
    config = _config(legal_disputes=True, formal_rules=True)

    assert config.v4_capability_flags.owned_enabled_names() == (
        "organizations",
        "formal_rules",
        "legal_disputes",
    ) or config.v4_capability_flags.owned_enabled_names() == (
        "formal_rules",
        "legal_disputes",
    )
    assert _evidence_testimony_enabled(config) is True


def test_all_v4_flags_off_disables_evidence() -> None:
    config = _config()

    assert config.v4_capability_flags.any_enabled() is False
    assert _evidence_testimony_enabled(config) is False


def test_no_per_agent_or_root_evidence_runner_key() -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))

    assert not hasattr(spec, "evidence_mode")
    assert not hasattr(spec, "evidence_policy")
    assert "evidence_mode" not in SimulationRunnerConfig.__dataclass_fields__
    assert "evidence_policy" not in SimulationRunnerConfig.__dataclass_fields__


def test_disabled_evidence_mode_allocates_nothing() -> None:
    config = CognitionLoopConfig()
    assert config.evidence_mode is CognitionEvidenceMode.DISABLED
    assert config.evidence_policy is None
    assert "evidence_mode" not in config.condition_fingerprint_material()

    loop = build_cognitive_loop(config)
    assert loop._evidence_mode is CognitionEvidenceMode.DISABLED
    assert loop._evidence_policy is None
    assert loop._prepared_evidence is None


def test_deterministic_evidence_mode_installs_locked_policy() -> None:
    config = CognitionLoopConfig(evidence_mode=CognitionEvidenceMode.DETERMINISTIC)
    assert config.evidence_policy is not None
    assert config.evidence_policy.version == EVIDENCE_TESTIMONY_POLICY_VERSION

    loop = build_cognitive_loop(config)
    assert loop._evidence_mode is CognitionEvidenceMode.DETERMINISTIC
    assert loop._evidence_policy is not None
    assert loop._prepared_evidence is None


def test_disabled_mode_clears_supplied_policy_and_rejects_foreign_types() -> None:
    config = CognitionLoopConfig(
        evidence_mode=CognitionEvidenceMode.DISABLED,
        evidence_policy=default_evidence_policy(),
    )
    assert config.evidence_policy is None

    with pytest.raises(TypeError, match="evidence_mode"):
        CognitionLoopConfig(evidence_mode="deterministic")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="evidence_policy"):
        CognitionLoopConfig(
            evidence_mode=CognitionEvidenceMode.DETERMINISTIC,
            evidence_policy=object(),  # type: ignore[arg-type]
        )


def test_evidence_fingerprint_material_is_additive_and_disabled_stable() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "evidence_mode" not in disabled
    assert "evidence_policy_version" not in disabled
    assert CognitionLoopConfig().condition_fingerprint_material() == disabled

    deterministic = CognitionLoopConfig(
        evidence_mode=CognitionEvidenceMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert deterministic["evidence_mode"] == "deterministic"
    assert deterministic["evidence_policy_version"] == (
        EVIDENCE_TESTIMONY_POLICY_VERSION
    )


def test_legal_disputes_flag_derives_deterministic_evidence_mode() -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))

    disabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        legal_disputes_enabled=False,
    )
    assert disabled.evidence_mode is CognitionEvidenceMode.DISABLED
    assert disabled.evidence_policy is None

    enabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        legal_disputes_enabled=True,
    )
    assert enabled.evidence_mode is CognitionEvidenceMode.DETERMINISTIC
    assert enabled.evidence_policy is not None
    assert enabled.evidence_policy.version == EVIDENCE_TESTIMONY_POLICY_VERSION


def test_runner_serialization_gains_no_evidence_key() -> None:
    encoded = encode_runner_config(_config(legal_disputes=True)).decode("utf-8")

    assert "evidence_mode" not in encoded
    assert "evidence_policy" not in encoded
