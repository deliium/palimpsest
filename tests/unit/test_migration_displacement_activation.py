# mypy: ignore-errors
"""Migration-displacement cognition activates only on the owned V4/V3 seam."""

from __future__ import annotations

import dataclasses
import inspect
import re

import pytest

from agents.cognition.architectures import (
    ArchitectureModeSnapshot,
    compose_loop_config_from_snapshot,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionMigrationDisplacementMode,
)
from agents.cognition.loop import CognitiveLoop
from agents.cognition.migration_displacement import (
    MigrationDisplacementPolicy,
    default_migration_displacement_policy,
)
from agents.models import AgentId
from simulation import cognition_contracts
from simulation import runner as runner_module
from simulation import runner_models as runner_models_module
from simulation.runner import _cognition_config_for
from simulation.runner_models import (
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    MortalityMode,
    V2CapabilityFlags,
    V3CapabilityFlags,
    V4CapabilityFlags,
)
from simulation.v4_architecture import v4_context_for_flag

pytestmark = pytest.mark.unit

AGENT = AgentId("agent-1")
_DISABLED = CognitionMigrationDisplacementMode.DISABLED


def _config(
    *,
    organizations: bool = True,
    multi_polity_migration: bool = True,
    regional_mode: str | None = "deterministic",
    **extra: bool,
) -> CognitionLoopConfig:
    return _cognition_config_for(
        AgentCognitionSpec(agent_id=AGENT),
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=organizations,
        regional_migration_mode=regional_mode,
        multi_polity_migration_enabled=multi_polity_migration,
        **extra,
    )


def test_v56_organizations_and_deterministic_regional_mode_enable_migration() -> None:
    config = _config()
    assert (
        config.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DETERMINISTIC
    )
    assert config.migration_displacement_policy == (
        default_migration_displacement_policy()
    )


def test_v56_without_organizations_stays_disabled() -> None:
    config = _config(organizations=False)
    assert (
        config.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DISABLED
    )
    assert config.migration_displacement_policy is None


def test_v56_without_multi_polity_migration_stays_disabled() -> None:
    config = _config(multi_polity_migration=False)
    assert (
        config.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DISABLED
    )
    assert config.migration_displacement_policy is None


def test_v56_without_regions_migration_stays_disabled() -> None:
    config = _config(regional_mode=None)
    assert (
        config.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DISABLED
    )
    assert config.migration_displacement_policy is None
    default_call = _cognition_config_for(
        AgentCognitionSpec(agent_id=AGENT),
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=True,
    )
    assert (
        default_call.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DISABLED
    )


def test_v56_with_regional_cognition_disabled_stays_disabled() -> None:
    config = _config(regional_mode="disabled")
    assert (
        config.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DISABLED
    )
    assert config.migration_displacement_policy is None


def test_v15_v44_v55_are_unchanged() -> None:
    # Earlier schemas never expose the organizations context, so the derived
    # mode is disabled even when migration and regional cognition are active.
    config = _config(organizations=False)
    assert (
        config.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DISABLED
    )
    assert config.migration_displacement_policy is None
    defaults = CognitionLoopConfig()
    assert (
        defaults.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DISABLED
    )
    assert defaults.migration_displacement_policy is None


def test_architectures_compose_migration_displacement_disabled_by_default() -> None:
    snapshot = ArchitectureModeSnapshot(
        flags={"extended_self_model": False},
        modes={"territorial_claim_mode": "deterministic"},
    )
    composed = compose_loop_config_from_snapshot(snapshot)
    assert (
        composed.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DISABLED
    )
    assert composed.migration_displacement_policy is None


def test_cognition_factory_version_stays_v1_and_payload_includes_migration() -> None:
    config = _config()
    assert config.factory_version == "cognition-factory-v1"
    material = config.condition_fingerprint_material()
    assert material["migration_displacement_mode"] == "deterministic"
    assert material["migration_displacement_policy_version"] == (
        "migration-displacement.v1"
    )
    disabled = _config(organizations=False).condition_fingerprint_material()
    assert disabled["migration_displacement_mode"] == "disabled"
    assert disabled["migration_displacement_policy_version"] is None


def test_loop_config_validates_mode_and_policy_types() -> None:
    with pytest.raises(TypeError, match="migration_displacement_mode must be"):
        CognitionLoopConfig(migration_displacement_mode="deterministic")
    with pytest.raises(TypeError, match="migration_displacement_policy must be"):
        CognitionLoopConfig(
            migration_displacement_mode=CognitionMigrationDisplacementMode.DETERMINISTIC,
            migration_displacement_policy=object(),
        )
    defaulted = CognitionLoopConfig(
        migration_displacement_mode=CognitionMigrationDisplacementMode.DETERMINISTIC
    )
    assert defaulted.migration_displacement_policy == MigrationDisplacementPolicy()
    forced_off = CognitionLoopConfig(
        migration_displacement_mode=CognitionMigrationDisplacementMode.DISABLED,
        migration_displacement_policy=MigrationDisplacementPolicy(),
    )
    assert forced_off.migration_displacement_policy is None


def test_loop_constructor_slots_validation_and_updater_exist() -> None:
    assert "_migration_displacement_mode" in CognitiveLoop.__slots__
    assert "_migration_displacement_policy" in CognitiveLoop.__slots__
    parameters = inspect.signature(CognitiveLoop.__init__).parameters
    assert parameters["migration_displacement_mode"].default is None
    assert parameters["migration_displacement_policy"].default is None
    assert hasattr(CognitiveLoop, "_prepare_migration_displacement")
    assert "_prepared_migration_displacement" in CognitiveLoop.__slots__


def test_no_runner_v57_or_new_flag_key_exists() -> None:
    source = inspect.getsource(runner_module)
    assert "runner-config-v57" not in source
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert not hasattr(runner_models_module, "RUNNER_SCHEMA_VERSION_V57")
    names = set(V4CapabilityFlags.__dataclass_fields__)
    assert len(names) == 12
    assert not any("migration" in name or "displacement" in name for name in names)
    assert "migration_displacement" not in V3CapabilityFlags.__dataclass_fields__
    with pytest.raises(ValueError):
        v4_context_for_flag("migration_displacement")
    spec_fields = {item.name for item in dataclasses.fields(AgentCognitionSpec)}
    assert not any("migration_displacement" in name for name in spec_fields)
    root_fields = {
        item.name
        for item in dataclasses.fields(runner_models_module.SimulationRunnerConfig)
    }
    assert not any("migration_displacement" in name for name in root_fields)


def test_every_cognition_config_call_site_passes_the_migration_inputs() -> None:
    source = inspect.getsource(runner_module)
    calls = len(re.findall(r"= _cognition_config_for\(", source))
    assert calls == 3
    assert source.count("regional_migration_mode=(") == calls
    assert source.count("multi_polity_migration_enabled=(") == calls
    assert source.count("v3_capability_flags.multi_polity_migration") >= calls


def test_existing_unowned_v4_flag_still_fails_closed() -> None:
    flags = V4CapabilityFlags(organizations=True)
    assert flags.unimplemented_enabled_names() == ()
    for name in (
        "supply_chains",
        "markets_credit",
        "science",
        "epidemics",
        "ecological_feedback",
        "disasters",
    ):
        unowned = V4CapabilityFlags(**{name: True})
        assert unowned.unimplemented_enabled_names() == (name,)
        assert getattr(flags, name) is False


def test_diplomacy_conflict_and_rules_are_not_required() -> None:
    config = _config(
        formal_rules_enabled=False,
        legal_disputes_enabled=False,
        diplomacy_enabled=False,
        organized_conflict_enabled=False,
    )
    assert (
        config.migration_displacement_mode
        is CognitionMigrationDisplacementMode.DETERMINISTIC
    )
    assert config.migration_displacement_policy is not None


def test_mode_is_reexported_for_the_simulation_layer() -> None:
    assert (
        cognition_contracts.CognitionMigrationDisplacementMode
        is CognitionMigrationDisplacementMode
    )
    assert (
        cognition_contracts.MigrationDisplacementPolicy is MigrationDisplacementPolicy
    )
    assert (
        cognition_contracts.default_migration_displacement_policy
        is default_migration_displacement_policy
    )
    from agents import cognition

    assert cognition.CognitionMigrationDisplacementMode is (
        CognitionMigrationDisplacementMode
    )
    assert cognition.MigrationIntentRow is cognition_contracts.MigrationIntentRow
