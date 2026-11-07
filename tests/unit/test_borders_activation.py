# mypy: ignore-errors
"""Border cognition activates only on the owned organizations seam."""

from __future__ import annotations

import inspect

import pytest

from agents.cognition.architectures import (
    ArchitectureModeSnapshot,
    compose_loop_config_from_snapshot,
)
from agents.cognition.borders import default_borders_policy
from agents.cognition.configuration import (
    CognitionBordersMode,
    CognitionLoopConfig,
    CognitionTerritorialClaimMode,
)
from agents.models import AgentId
from simulation import runner as runner_module
from simulation.runner import _cognition_config_for
from simulation.runner_models import (
    AgentCognitionSpec,
    MortalityMode,
    TerritorialClaimMode,
    V2CapabilityFlags,
    V4CapabilityFlags,
)
from simulation.v4_architecture import v4_context_for_flag

pytestmark = pytest.mark.unit

AGENT = AgentId("agent-1")


def _config(
    *,
    organizations: bool,
    territorial: TerritorialClaimMode = TerritorialClaimMode.DETERMINISTIC,
) -> CognitionLoopConfig:
    return _cognition_config_for(
        AgentCognitionSpec(
            agent_id=AGENT,
            territorial_claim_mode=territorial,
        ),
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=organizations,
    )


def test_v56_organizations_and_territorial_mode_enable_borders() -> None:
    config = _config(organizations=True)
    assert config.borders_mode is CognitionBordersMode.DETERMINISTIC
    assert config.borders_policy == default_borders_policy()


def test_v56_without_organizations_stays_disabled() -> None:
    config = _config(organizations=False)
    assert config.borders_mode is CognitionBordersMode.DISABLED
    assert config.borders_policy is None


def test_v56_without_territorial_mode_stays_disabled() -> None:
    config = _config(organizations=True, territorial=TerritorialClaimMode.DISABLED)
    assert config.borders_mode is CognitionBordersMode.DISABLED
    assert config.borders_policy is None


def test_v15_v44_v55_are_unchanged() -> None:
    config = _config(organizations=False)
    assert config.territorial_claim_mode is CognitionTerritorialClaimMode.DETERMINISTIC
    assert config.borders_mode is CognitionBordersMode.DISABLED
    assert config.borders_policy is None


def test_architectures_compose_borders_disabled_by_default() -> None:
    snapshot = ArchitectureModeSnapshot(
        flags={"extended_self_model": False},
        modes={"territorial_claim_mode": "deterministic"},
    )
    composed = compose_loop_config_from_snapshot(snapshot)
    assert composed.borders_mode is CognitionBordersMode.DISABLED
    assert composed.borders_policy is None


def test_cognition_factory_version_stays_v1_and_payload_includes_borders() -> None:
    config = _config(organizations=True)
    assert config.factory_version == "cognition-factory-v1"
    material = config.condition_fingerprint_material()
    assert material["borders_mode"] == "deterministic"
    assert material["borders_policy_version"] == "borders-claims.v1"
    disabled = _config(organizations=False).condition_fingerprint_material()
    assert disabled["borders_mode"] == "disabled"
    assert disabled["borders_policy_version"] is None


def test_no_runner_v57_or_new_flag_key_exists() -> None:
    source = inspect.getsource(runner_module)
    assert "runner-config-v57" not in source
    assert "borders" not in V4CapabilityFlags.__dataclass_fields__
    with pytest.raises(ValueError):
        v4_context_for_flag("borders")
    assert "borders" not in {name for name in V4CapabilityFlags.__dataclass_fields__}


def test_existing_unowned_v4_flag_still_fails_closed() -> None:
    flags = V4CapabilityFlags(organizations=True)
    assert flags.infrastructure_networks is False
    assert flags.supply_chains is False
    assert flags.markets_credit is False
    assert flags.science is False
    assert flags.epidemics is False
    assert flags.ecological_feedback is False
    assert flags.disasters is False


def test_diplomacy_is_not_required_for_border_cognition() -> None:
    config = _config(organizations=True)
    assert config.borders_mode is CognitionBordersMode.DETERMINISTIC
    assert config.borders_policy is not None
