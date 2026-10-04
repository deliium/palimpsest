"""Deterministic observer-graphical-v2 world for Godot validation.

Composes the five-agent reference scenario with environmental dynamics and an
external artifact channel. Off the V1 regression gate. Short CI arms use a
small ``max_ticks``; seek-jump tests may use a synthetic high-water cursor in
the Godot fixture (≥ 1000) without generating that many live ticks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Final

from experiments.external_artifacts_scenario import scarce_resource_record
from experiments.reference_scenario import (
    REFERENCE_DEFAULT_SEED,
    ReferenceScenarioBundle,
    build_reference_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V19,
    ArtifactInterpretationMode,
    SimulationRunnerConfig,
)
from world.environment import scarcity_scenario_dynamics

_LOG: Final[logging.Logger] = logging.getLogger("experiments.observer_graphical")

OBSERVER_GRAPHICAL_SCENARIO_ID: Final[str] = "observer-graphical-v2"
OBSERVER_GRAPHICAL_CI_MAX_TICKS: Final[int] = 16
OBSERVER_GRAPHICAL_SEEK_HIGH_WATER: Final[int] = 1000

# Semantic / mechanism checklist the graphical fixture and builder must cover.
REQUIRED_GRAPHICAL_FEATURES: Final[tuple[str, ...]] = (
    "agents_ge_5",
    "multi_location",
    "movement",
    "resources",
    "communication_talk_ask_tell",
    "item_exchange",
    "environmental_dynamics",
    "crafting_building",
    "terminal_death",
    "external_artifact",
    "social_information_transmission",
)

REQUIRED_FIXTURE_EVENT_TYPES: Final[tuple[str, ...]] = (
    "AGENT_MOVED",
    "AGENT_TALKED",
    "AGENT_ASKED",
    "AGENT_TOLD",
    "AGENT_GAVE_ITEM",
    "AGENT_TOOK_ITEM",
    "WEATHER_CHANGED",
    "RESOURCE_HARVESTED",
    "CRAFT_STARTED",
    "ITEM_CRAFTED",
    "STRUCTURE_BUILT",
    "AGENT_DIED",
)


@dataclass(frozen=True, slots=True)
class ObserverGraphicalScenarioBundle:
    """Runner config plus checklist metadata for the graphical observer world."""

    scenario_id: str
    config: SimulationRunnerConfig
    reference: ReferenceScenarioBundle
    features: tuple[str, ...]
    ci_max_ticks: int
    seek_high_water: int


def build_observer_graphical_scenario(
    *,
    seed: int = REFERENCE_DEFAULT_SEED,
    max_ticks: int = OBSERVER_GRAPHICAL_CI_MAX_TICKS,
    death_tick: int | None = None,
) -> ObserverGraphicalScenarioBundle:
    """Build the observer-graphical-v2 world (off the V1 gate)."""
    if death_tick is None:
        death_tick = min(4, max(0, max_ticks // 2 - 1))
    reference = build_reference_scenario(
        seed=seed,
        max_ticks=max_ticks,
        death_tick=death_tick,
    )
    env = scarcity_scenario_dynamics()
    camp_id = reference.config.scenario.locations[0].entity_id
    artifact = replace(
        scarce_resource_record(
            author_id=reference.config.agents[0].entity_id.value,
        ),
        location_id=camp_id,
    )
    scenario = replace(
        reference.config.scenario,
        artifacts=(artifact,),
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
            ),
        )
        for agent in reference.config.agents
    )
    config = replace(
        reference.config,
        scenario=scenario,
        agents=agents,
        environmental_dynamics=env,
        artifacts_enabled=True,
        schema_version=RUNNER_SCHEMA_VERSION_V19,
    )
    agent_count = len(config.agents)
    location_count = len(config.scenario.locations)
    resource_count = len(config.scenario.resources)
    missing: list[str] = []
    if agent_count < 5:
        missing.append("agents_ge_5")
    if location_count < 2:
        missing.append("multi_location")
    if resource_count < 1:
        missing.append("resources")
    if config.environmental_dynamics is None:
        missing.append("environmental_dynamics")
    if not config.scenario.artifacts:
        missing.append("external_artifact")
    if missing:
        _LOG.error(
            "observer_graphical_incomplete reason_code=missing_features "
            "missing=%s",
            ",".join(missing),
        )
        raise ValueError(f"observer_graphical_incomplete:{','.join(missing)}")
    _LOG.info(
        "observer_graphical_built scenario_id=%s agent_count=%s "
        "location_count=%s resource_count=%s max_ticks=%s "
        "artifact_count=%s env=%s",
        OBSERVER_GRAPHICAL_SCENARIO_ID,
        agent_count,
        location_count,
        resource_count,
        max_ticks,
        len(config.scenario.artifacts),
        config.environmental_dynamics is not None,
    )
    return ObserverGraphicalScenarioBundle(
        scenario_id=OBSERVER_GRAPHICAL_SCENARIO_ID,
        config=config,
        reference=reference,
        features=REQUIRED_GRAPHICAL_FEATURES,
        ci_max_ticks=OBSERVER_GRAPHICAL_CI_MAX_TICKS,
        seek_high_water=OBSERVER_GRAPHICAL_SEEK_HIGH_WATER,
    )
