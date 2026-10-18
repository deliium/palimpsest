"""runner-config-v47 is a mode-only per-agent translation increment."""

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
    RUNNER_SCHEMA_VERSION_V46,
    RUNNER_SCHEMA_VERSION_V47,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentRunnerSpec,
    SemanticNamingMode,
    SimulationRunnerConfig,
    SymbolicLanguageMode,
    TranslationMode,
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
    config: SimulationRunnerConfig,
    *,
    translation: bool,
    naming: bool | None = None,
    symbolic: bool = False,
) -> tuple[AgentRunnerSpec, ...]:
    naming = translation if naming is None else naming
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
                translation_mode=(
                    TranslationMode.DETERMINISTIC
                    if translation
                    else TranslationMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )


def _v47(**overrides: object) -> SimulationRunnerConfig:
    values: dict[str, object] = {
        "schema_version": RUNNER_SCHEMA_VERSION_V47,
        "agents": _agents(_OFF_ARM, translation=True),
        "v3_capability_flags": V3CapabilityFlags(multi_polity_migration=True),
        "regions_migration": _regions(cognition_mode=CognitionMode.DISABLED),
    }
    values.update(overrides)
    return replace(_OFF_ARM, **values)  # type: ignore[arg-type]


def test_v47_is_supported_and_compat_map_lists_it() -> None:
    assert RUNNER_SCHEMA_VERSION_V47 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    entry = COMPATIBILITY_MATRIX["runner_config"]
    assert RUNNER_SCHEMA_VERSION_V47 in entry.accepted_restore


def test_v47_round_trips_with_contact_off() -> None:
    config = _v47()
    document = json.loads(encode_runner_config(config))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V47
    assert "cultural_contact" not in document
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V47
    assert all(
        agent.cognition.translation_mode is TranslationMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_v47_round_trips_without_regions_or_contact() -> None:
    config = _v47(
        regions_migration=None,
        v3_capability_flags=V3CapabilityFlags(),
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V47
    assert decoded.regions_migration is None
    assert decoded.cultural_contact is None


def test_v47_round_trips_with_contact_on() -> None:
    config = _v47(cultural_contact=CulturalContactSpec(mode=ContactMode.DETERMINISTIC))
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V47
    assert decoded.cultural_contact == CulturalContactSpec(
        mode=ContactMode.DETERMINISTIC
    )


def test_v47_round_trips_with_symbolic_mode() -> None:
    config = _v47(agents=_agents(_OFF_ARM, translation=True, symbolic=True))
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V47
    assert all(
        agent.cognition.symbolic_language_mode is SymbolicLanguageMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_v47_requires_deterministic_translation_mode() -> None:
    with pytest.raises(ValueError, match="v47_requires_translation"):
        _v47(agents=_agents(_OFF_ARM, translation=False))


def test_translation_mode_requires_v47() -> None:
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V20

    with pytest.raises(ValueError, match="translation_requires_v47"):
        _v47(
            schema_version=RUNNER_SCHEMA_VERSION_V20,
            regions_migration=None,
            v3_capability_flags=V3CapabilityFlags(),
        )


def test_translation_requires_deterministic_naming() -> None:
    with pytest.raises(ValueError, match="translation_requires_semantic_naming"):
        _v47(
            agents=_agents(
                _OFF_ARM, translation=True, naming=False, symbolic=False
            )
        )


def test_symbolic_only_stays_v46() -> None:
    config = replace(
        _OFF_ARM,
        schema_version=RUNNER_SCHEMA_VERSION_V46,
        agents=_agents(
            _OFF_ARM, translation=False, naming=True, symbolic=True
        ),
        v3_capability_flags=V3CapabilityFlags(multi_polity_migration=True),
        regions_migration=_regions(cognition_mode=CognitionMode.DISABLED),
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V46


def test_matrix_finalize_selects_v47_for_translation() -> None:
    from experiments.matrix_factors import clone_runner_config

    config = clone_runner_config(
        _v47(agents=_agents(_OFF_ARM, translation=True)),
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    finalized = finalize_matrix_cell_config(config)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V47
    assert all(
        agent.cognition.translation_mode is TranslationMode.DETERMINISTIC
        for agent in finalized.agents
    )
