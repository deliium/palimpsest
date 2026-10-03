"""Experiment-facing expansion of named cognitive architecture variants.

Authoritative path: ``expand_architecture`` → ``SimulationRunnerConfig``.
Architecture ids stay on the experiments/registry layer — never runner JSON keys.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from agents.cognition.architectures import (
    ARCHITECTURES,
    ArchitectureDefinition,
    ArchitectureModeSnapshot,
    architecture_definition_digest,
    get_architecture,
    validate_architecture_compatibility,
)
from simulation.runner_models import (
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    ProspectiveImaginationMode,
    ReflectionMode,
    SimulationRunnerConfig,
    V2CapabilityFlags,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.architectures")

__all__ = [
    "expand_architecture",
    "mode_snapshot_from_runner_config",
    "registered_architecture_ids",
]


def registered_architecture_ids() -> tuple[str, ...]:
    """Stable ordered architecture ids from the cognition registry."""
    return tuple(sorted(ARCHITECTURES))


def _flags_for_definition(definition: ArchitectureDefinition) -> V2CapabilityFlags:
    enabled = set(definition.capabilities.required_flags)
    return V2CapabilityFlags(
        advanced_social_inference="advanced_social_inference" in enabled,
        multi_hop_testimony_tracking=False,
        predictive_world_model="predictive_world_model" in enabled,
        extended_self_model="extended_self_model" in enabled,
        short_term_emotional_state="short_term_emotional_state" in enabled,
    )


def mode_snapshot_from_runner_config(
    config: SimulationRunnerConfig,
) -> ArchitectureModeSnapshot:
    """Build a cognition-local snapshot from an expanded runner config."""
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("config must be SimulationRunnerConfig")
    if not config.agents:
        raise ValueError("config.agents must be non-empty")
    cognition = config.agents[0].cognition
    flags = {
        "advanced_social_inference": config.capability_flags.advanced_social_inference,
        "multi_hop_testimony_tracking": (
            config.capability_flags.multi_hop_testimony_tracking
        ),
        "predictive_world_model": config.capability_flags.predictive_world_model,
        "extended_self_model": config.capability_flags.extended_self_model,
        "short_term_emotional_state": (
            config.capability_flags.short_term_emotional_state
        ),
    }
    modes = {
        "memory_mode": cognition.memory_mode.value,
        "imagination_mode": cognition.imagination_mode.value,
        "reflection_mode": cognition.reflection_mode.value,
        "prospective_mode": cognition.prospective_mode.value,
        "mortality_appraisal": config.mortality_mode.value,
    }
    return ArchitectureModeSnapshot(flags=flags, modes=modes)


def expand_architecture(
    base: SimulationRunnerConfig,
    architecture_id: str,
    *,
    _with_agent_modes: object | None = None,
) -> SimulationRunnerConfig:
    """Expand a named architecture into an ordinary ``SimulationRunnerConfig``.

    Sets per-agent modes and ``capability_flags`` / ``schema_version`` /
    ``mortality_mode`` from the locked preset table. Does not invent
    ``architecture_id`` runner JSON keys.
    """
    if type(base) is not SimulationRunnerConfig:
        raise TypeError("base must be SimulationRunnerConfig")

    definition = get_architecture(architecture_id)
    modes = definition.capabilities.required_modes
    digest = architecture_definition_digest(definition)

    memory_mode = MemoryMode(modes["memory_mode"])
    imagination_mode = ImaginationMode(modes["imagination_mode"])
    reflection_mode = ReflectionMode(modes["reflection_mode"])
    prospective_mode = ProspectiveImaginationMode(modes["prospective_mode"])
    mortality_mode = MortalityMode(modes["mortality_appraisal"])
    capability_flags = _flags_for_definition(definition)

    if _with_agent_modes is None:
        from experiments.catalog import _with_agent_modes as apply_modes
    else:
        apply_modes = _with_agent_modes  # type: ignore[assignment]

    expanded = apply_modes(
        base,
        memory_mode=memory_mode,
        imagination_mode=imagination_mode,
        reflection_mode=reflection_mode,
        prospective_mode=prospective_mode,
        mortality_mode=mortality_mode,
        schema_version=definition.schema_version,
    )
    expanded = replace(expanded, capability_flags=capability_flags)

    snapshot = mode_snapshot_from_runner_config(expanded)
    validate_architecture_compatibility(definition, snapshot)

    enabled = ",".join(capability_flags.enabled_names()) or "-"
    _LOG.debug(
        "architecture_expand_diff architecture_id=%s memory_mode=%s "
        "imagination_mode=%s reflection_mode=%s prospective_mode=%s "
        "mortality_mode=%s schema_version=%s digest=%s",
        definition.architecture_id,
        memory_mode.value,
        imagination_mode.value,
        reflection_mode.value,
        prospective_mode.value,
        mortality_mode.value,
        definition.schema_version,
        digest,
    )
    _LOG.info(
        "architecture_expanded architecture_id=%s schema_version=%s "
        "enabled_flags=%s memory_mode=%s reflection_mode=%s "
        "prospective_mode=%s digest=%s",
        definition.architecture_id,
        definition.schema_version,
        enabled,
        memory_mode.value,
        reflection_mode.value,
        prospective_mode.value,
        digest,
    )
    return expanded


def expand_all_architectures(
    base: SimulationRunnerConfig,
) -> Mapping[str, SimulationRunnerConfig]:
    """Expand every registered architecture against a shared base config."""
    return {
        architecture_id: expand_architecture(base, architecture_id)
        for architecture_id in registered_architecture_ids()
    }
