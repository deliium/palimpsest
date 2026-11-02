"""V4-05 agency policy seam: cognition config, loop, and runner wiring."""

from __future__ import annotations

import pytest

from agents.cognition import (
    ORGANIZATION_AGENCY_POLICY_VERSION,
    OrganizationAgencyPolicy,
    build_cognitive_loop,
    default_organization_agency_policy,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionOrganizationMode,
)
from agents.models import AgentId
from simulation.runner import _cognition_config_for
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


def test_disabled_mode_allocates_no_agency_policy() -> None:
    config = CognitionLoopConfig()
    assert config.organization_concept_mode is CognitionOrganizationMode.DISABLED
    assert config.organization_agency_policy is None


def test_deterministic_mode_installs_the_locked_agency_policy() -> None:
    config = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    )
    assert config.organization_agency_policy is default_organization_agency_policy()
    assert config.organization_agency_policy.max_decisions == 32


def test_disabled_mode_normalizes_a_supplied_policy_to_none() -> None:
    config = CognitionLoopConfig(organization_agency_policy=OrganizationAgencyPolicy())
    assert config.organization_agency_policy is None


def test_custom_agency_policy_is_preserved() -> None:
    custom = OrganizationAgencyPolicy()
    config = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC,
        organization_agency_policy=custom,
    )
    assert config.organization_agency_policy is custom


def test_invalid_agency_policy_type_fails_closed() -> None:
    with pytest.raises(TypeError):
        CognitionLoopConfig(
            organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC,
            organization_agency_policy=object(),  # type: ignore[arg-type]
        )


def test_fingerprint_includes_agency_version_only_when_enabled() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "organization_agency_policy_version" not in disabled

    enabled = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert enabled["organization_agency_policy_version"] == (
        ORGANIZATION_AGENCY_POLICY_VERSION
    )


def test_build_cognitive_loop_forwards_the_agency_policy() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
        )
    )
    assert loop._organization_agency_policy is default_organization_agency_policy()
    assert loop._prepared_organization_agency is None


def test_runner_seam_keeps_v56_and_allocates_the_agency_policy() -> None:
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
    assert disabled.organization_agency_policy is None

    enabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=True,
    )
    assert enabled.organization_concept_mode is CognitionOrganizationMode.DETERMINISTIC
    assert enabled.organization_agency_policy is default_organization_agency_policy()
