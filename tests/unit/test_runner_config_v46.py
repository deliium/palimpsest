"""runner-config-v46 is a mode-only per-agent symbolic-language increment."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.matrix_schema import finalize_matrix_cell_config
from experiments.regional_migration_scenario import (
    _regions,
    regional_migration_scenario,
)
from simulation.compatibility import COMPATIBILITY_MATRIX
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V45,
    RUNNER_SCHEMA_VERSION_V46,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentRunnerSpec,
    SemanticNamingMode,
    SimulationRunnerConfig,
    SymbolicLanguageMode,
    V3CapabilityFlags,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from world.contact import ContactMode, CulturalContactSpec
from world.regions import CognitionMode

_OFF_ARM = regional_migration_scenario().conditions[0].runner_config


def _agents(
    config: SimulationRunnerConfig, *, symbolic: bool, naming: bool | None = None
) -> tuple[AgentRunnerSpec, ...]:
    naming = symbolic if naming is None else naming
    return tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                semantic_naming_mode=(
                    SemanticNamingMode.DETERMINISTIC
                    if naming
                    else SemanticNamingMode.DISABLED
                ),
                symbolic_language_mode=(
                    SymbolicLanguageMode.DETERMINISTIC
                    if symbolic
                    else SymbolicLanguageMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )


def _v46(**overrides: object) -> SimulationRunnerConfig:
    values: dict[str, object] = {
        "schema_version": RUNNER_SCHEMA_VERSION_V46,
        "agents": _agents(_OFF_ARM, symbolic=True),
        "v3_capability_flags": V3CapabilityFlags(multi_polity_migration=True),
        "regions_migration": _regions(cognition_mode=CognitionMode.DISABLED),
    }
    values.update(overrides)
    return replace(_OFF_ARM, **values)  # type: ignore[arg-type]


def test_v46_is_supported_and_compat_map_lists_it() -> None:
    assert RUNNER_SCHEMA_VERSION_V46 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    entry = COMPATIBILITY_MATRIX["runner_config"]
    assert RUNNER_SCHEMA_VERSION_V46 in entry.accepted_restore


def test_v46_round_trips_with_contact_off() -> None:
    config = _v46()
    document = json.loads(encode_runner_config(config))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V46
    assert "cultural_contact" not in document
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V46
    assert all(
        agent.cognition.symbolic_language_mode is SymbolicLanguageMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_v46_round_trips_without_regions_or_contact() -> None:
    config = _v46(
        regions_migration=None,
        v3_capability_flags=V3CapabilityFlags(),
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V46
    assert decoded.regions_migration is None
    assert decoded.cultural_contact is None


def test_v46_round_trips_with_contact_on() -> None:
    config = _v46(cultural_contact=CulturalContactSpec(mode=ContactMode.DETERMINISTIC))
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V46
    assert decoded.cultural_contact == CulturalContactSpec(
        mode=ContactMode.DETERMINISTIC
    )


def test_v46_requires_deterministic_symbolic_mode() -> None:
    with pytest.raises(ValueError, match="v46_requires_symbolic_language"):
        _v46(agents=_agents(_OFF_ARM, symbolic=False))


def test_symbolic_mode_requires_v46() -> None:
    with pytest.raises(ValueError, match="symbolic_language_requires_v46"):
        _v46(
            schema_version=RUNNER_SCHEMA_VERSION_V45,
            cultural_contact=CulturalContactSpec(mode=ContactMode.DISABLED),
        )


def test_symbolic_mode_requires_semantic_naming() -> None:
    with pytest.raises(ValueError, match="symbolic_language_requires_semantic_naming"):
        _v46(agents=_agents(_OFF_ARM, symbolic=True, naming=False))


def test_v45_keyset_unchanged() -> None:
    v45 = _v46(
        schema_version=RUNNER_SCHEMA_VERSION_V45,
        agents=_agents(_OFF_ARM, symbolic=False),
        cultural_contact=CulturalContactSpec(mode=ContactMode.DISABLED),
    )
    document = json.loads(encode_runner_config(v45))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V45
    assert "symbolic_language_mode" not in document["agents"][0]["cognition"]


def test_matrix_finalize_selects_v46_for_symbolic_mode() -> None:
    from experiments.matrix_factors import clone_runner_config

    provisional = clone_runner_config(_v46(), schema_version=RUNNER_SCHEMA_VERSION_V4)
    config = finalize_matrix_cell_config(provisional)
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V46
