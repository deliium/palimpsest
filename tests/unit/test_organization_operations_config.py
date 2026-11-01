"""V4-04 operation policy seam: cognition config, loop, and runner wiring."""

from __future__ import annotations

import pytest

from agents.cognition import (
    ORGANIZATION_OPERATION_POLICY_VERSION,
    OrganizationOperationPolicy,
    build_cognitive_loop,
    default_organization_concept_policy,
    default_organization_operation_policy,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionOrganizationMode,
)
from agents.models import AgentId
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    MortalityMode,
    V2CapabilityFlags,
    V4CapabilityFlags,
)

pytestmark = pytest.mark.unit


def test_disabled_mode_allocates_no_operation_policy() -> None:
    config = CognitionLoopConfig()
    assert config.organization_concept_mode is CognitionOrganizationMode.DISABLED
    assert config.organization_operation_policy is None


def test_deterministic_mode_installs_the_locked_operation_policy() -> None:
    config = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    )
    assert config.organization_operation_policy is (
        default_organization_operation_policy()
    )
    assert config.organization_operation_policy.max_actions == 64


def test_custom_operation_policy_is_preserved() -> None:
    custom = OrganizationOperationPolicy()
    config = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC,
        organization_concept_policy=default_organization_concept_policy(),
        organization_operation_policy=custom,
    )
    assert config.organization_operation_policy is custom


def test_invalid_operation_policy_type_fails_closed() -> None:
    with pytest.raises(TypeError):
        CognitionLoopConfig(
            organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC,
            organization_operation_policy=object(),  # type: ignore[arg-type]
        )


def test_fingerprint_includes_operation_version_only_when_enabled() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "organization_operation_policy_version" not in disabled

    enabled = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert enabled["organization_operation_policy_version"] == (
        ORGANIZATION_OPERATION_POLICY_VERSION
    )


def test_build_cognitive_loop_forwards_the_operation_policy() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
        )
    )
    assert loop._organization_operation_policy is (
        default_organization_operation_policy()
    )


def test_runner_seam_keeps_v56_and_allocates_the_operation_policy() -> None:
    from simulation.runner import _cognition_config_for

    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V55 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert V4CapabilityFlags(organizations=True).owned_enabled_names() == (
        "organizations",
    )

    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    disabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=False,
    )
    assert disabled.organization_concept_mode is CognitionOrganizationMode.DISABLED
    assert disabled.organization_operation_policy is None

    enabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=True,
    )
    assert enabled.organization_concept_mode is CognitionOrganizationMode.DETERMINISTIC
    assert enabled.organization_operation_policy is (
        default_organization_operation_policy()
    )
