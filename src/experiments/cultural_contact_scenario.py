"""Experiment BA: neutral cultural contact across region-separated populations.

Analysis-only contact adds no policy, attitude, assimilation, war, or diplomacy.
Contact arms schedule ordinary journeys so the engine can record co-presence.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from experiments.interventions import MilestoneInterventionArbiter, MilestoneOverride
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    require_stochastic,
)
from experiments.multiple_societies_scenario import _regions, _scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V45,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CommunicationStrategyMode,
    CulturalNarrativeMode,
    MortalityMode,
    RunnerStopPolicy,
    SemanticNamingMode,
    SimulationRunnerConfig,
    SocialConventionMode,
    SocialNormMode,
    V3CapabilityFlags,
)
from world.actions import AgentCommand, Move, Talk, Wait
from world.communications import origin_utterance
from world.contact import ContactMode, CulturalContactSpec
from world.events import WorldEvent
from world.identifiers import EntityId
from world.regions import CognitionMode

__all__ = [
    "assert_cultural_contact_structure",
    "cultural_contact_arbiter",
    "cultural_contact_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.cultural_contact_scenario")

_AGENTS: Final[tuple[tuple[str, str], ...]] = (
    ("agent-a", "body-a"),
    ("agent-b", "body-b"),
    ("agent-e", "body-e"),
    ("agent-c", "body-c"),
    ("agent-d", "body-d"),
)
_CONTACT_ARMS: Final[frozenset[str]] = frozenset(
    {
        "ba-contact-trade",
        "ba-contact-teaching",
        "ba-contact-conflict-cooperation",
        "ba-contact-kinship",
    }
)


def cultural_contact_scenario(
    *,
    seed: int = 29,
    max_ticks: int = 16,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    if base is not None and type(base) is not SimulationRunnerConfig:
        raise TypeError("base must be SimulationRunnerConfig or None")
    active_seed = seed if base is None else base.seed
    stochastic_identity = (
        require_stochastic("cultural-contact-ba")
        if base is None
        else base.stochastic_identity
    )
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(active_seed,))
    base_scenario = _scenario()
    scenario = replace(
        base_scenario,
        locations=tuple(
            replace(
                location,
                body_capacity=type(location.body_capacity)(4),
            )
            if location.entity_id == EntityId("loc-south-grove")
            else location
            for location in base_scenario.locations
        ),
        bodies=tuple(
            replace(body, location_id=EntityId("loc-south-grove"))
            if body.entity_id in {EntityId("body-b"), EntityId("body-e")}
            else body
            for body in base_scenario.bodies
        ),
    )

    def config(*, contact: bool, isolated: bool) -> SimulationRunnerConfig:
        agents = tuple(
            AgentRunnerSpec(
                agent_id=AgentId(agent_id),
                entity_id=EntityId(body_id),
                cognition=AgentCognitionSpec(
                    agent_id=AgentId(agent_id),
                    communication_strategy_mode=(
                        CommunicationStrategyMode.DISABLED
                        if not contact
                        else CommunicationStrategyMode.DETERMINISTIC
                    ),
                    semantic_naming_mode=(
                        SemanticNamingMode.DISABLED
                        if not contact
                        else SemanticNamingMode.DETERMINISTIC
                    ),
                    social_norm_mode=(
                        SocialNormMode.DISABLED
                        if not contact
                        else SocialNormMode.DETERMINISTIC
                    ),
                    social_convention_mode=(
                        SocialConventionMode.DISABLED
                        if not contact
                        else SocialConventionMode.DETERMINISTIC
                    ),
                    cultural_narrative_mode=CulturalNarrativeMode.DISABLED,
                ),
                initial_goals=(),
            )
            for agent_id, body_id in _AGENTS
        )
        return SimulationRunnerConfig(
            seed=active_seed,
            stochastic_identity=stochastic_identity,
            scenario=scenario,
            agents=agents,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            mortality_mode=(
                MortalityMode.DISABLED if base is None else base.mortality_mode
            ),
            schema_version=(
                RUNNER_SCHEMA_VERSION_V4 if not contact else RUNNER_SCHEMA_VERSION_V45
            ),
            v3_capability_flags=(
                V3CapabilityFlags()
                if not contact
                else V3CapabilityFlags(multi_polity_migration=True)
            ),
            regions_migration=(
                None
                if not contact
                else _regions(cognition_mode=CognitionMode.DETERMINISTIC)
            ),
            cultural_contact=(
                None
                if not contact
                else CulturalContactSpec(mode=ContactMode.DETERMINISTIC)
            ),
        )

    off = config(contact=False, isolated=False)
    isolated = config(contact=True, isolated=True)
    arms = (
        ("ba-channel-off", "cultural_contact_off", off),
        ("ba-isolated", "contact_recording_without_journeys", isolated),
        (
            "ba-contact-trade",
            "cross_region_exchange",
            config(contact=True, isolated=False),
        ),
        (
            "ba-contact-teaching",
            "cross_region_teaching",
            config(contact=True, isolated=False),
        ),
        (
            "ba-contact-conflict-cooperation",
            "cross_region_conflict_cooperation",
            config(contact=True, isolated=False),
        ),
        (
            "ba-contact-kinship",
            "cross_region_kinship_absent",
            config(contact=True, isolated=False),
        ),
    )
    _LOG.info(
        "cultural_contact_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(_AGENTS),
    )
    return ExperimentDefinition(
        experiment_id="cultural_contact@1",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=tuple(
            ExperimentCondition(
                condition_id=condition_id,
                label_code=label,
                runner_config=item,
            )
            for condition_id, label, item in arms
        ),
        paired_world_group="cultural-contact-ba-world",
    )


def cultural_contact_arbiter(
    condition_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    if condition_id == "ba-channel-off":
        return None
    horizon = config.stop_policy.max_ticks
    assert horizon is not None
    commands: dict[tuple[int, str], AgentCommand] = {}
    for tick in range(horizon):
        for agent in config.agents:
            commands[tick, agent.agent_id.value] = Wait()
    for tick in range(horizon):
        _talk(commands, tick, "body-b", "body-e")
        _talk(commands, tick, "body-c", "body-d")
    if condition_id in _CONTACT_ARMS and horizon > 6:
        commands[0, "agent-a"] = Move(EntityId("loc-north-hill"))
        commands[2, "agent-a"] = Move(EntityId("loc-south-grove"))
        commands[4, "agent-a"] = Move(EntityId("loc-south"))
        for tick in range(6, horizon):
            _talk(commands, tick, "body-a", "body-c", suffix="cross")
    milestones = tuple(
        MilestoneOverride(
            milestone_id=f"{condition_id}-{tick}-{agent}",
            tick=tick,
            agent_id=AgentId(agent),
            build_command=_command_factory(command),
        )
        for (tick, agent), command in sorted(commands.items())
        if tick < horizon
    )
    return MilestoneInterventionArbiter(milestones, override_budget=len(milestones))


def _talk(
    commands: dict[tuple[int, str], AgentCommand],
    tick: int,
    speaker: str,
    recipient: str,
    *,
    suffix: str = "local",
) -> None:
    agent_id = f"agent-{speaker.removeprefix('body-')}"
    commands[tick, agent_id] = Talk(
        recipient_id=EntityId(recipient),
        utterance=origin_utterance(
            speaker_id=EntityId(speaker),
            communication_id=f"ba-{suffix}-{tick}",
            text="We meet here.",
            concepts=("place_shared",),
            sender_confidence=0.7,
        ),
    )


def _command_factory(command: AgentCommand) -> Callable[[], AgentCommand]:
    def build() -> AgentCommand:
        return command

    return build


def assert_cultural_contact_structure(
    condition_id: str,
    events: Sequence[WorldEvent],
) -> dict[str, int]:
    """Assert structural contact evidence only; never a success outcome."""
    from world.events import ContactRecorded, Fled, JourneyArrived

    contacts: list[tuple[WorldEvent, ContactRecorded]] = []
    for event in events:
        if isinstance(event.details, ContactRecorded):
            contacts.append((event, event.details))
    arrivals = {
        (event.details.journey_id, event.tick)
        for event in events
        if isinstance(event.details, JourneyArrived)
    }
    flee_ticks = {
        (event.actor_id, event.tick)
        for event in events
        if isinstance(event.details, Fled) and event.details.success is True
    }
    exchange = sum(
        1
        for event in events
        if str(getattr(event.details, "kind", "")).lower() == "exchangecompleted"
    )
    teaching = sum(
        1
        for event in events
        if str(getattr(event.details, "kind", "")).lower() == "teachingaudit"
    )
    conflict = sum(
        1 for event in events if str(getattr(event.details, "kind", "")) == "attacked"
    )
    cooperation = sum(
        1 for event in events if str(getattr(event.details, "kind", "")) == "helped"
    )
    if condition_id in {"ba-channel-off", "ba-isolated"}:
        if contacts:
            raise AssertionError("contact_events_present_in_control_arm")
    elif condition_id in _CONTACT_ARMS:
        if not contacts:
            raise AssertionError("contact_events_missing_in_contact_arm")
    for event, details in contacts:
        if set(details.participant_ids) & set(details.present_ids):
            raise AssertionError("contact_sets_overlap")
        if list(details.participant_ids) != sorted(
            details.participant_ids, key=lambda item: item.value
        ):
            raise AssertionError("contact_participants_unsorted")
        if details.origin_region_id == details.destination_region_id:
            raise AssertionError("contact_same_region")
        if details.relocation_kind == "journey_arrived":
            if (details.journey_id, event.tick) not in arrivals:
                raise AssertionError("contact_without_arrival")
        elif details.relocation_kind == "fled":
            if (event.actor_id, event.tick) not in flee_ticks:
                raise AssertionError("contact_without_flee")
    _LOG.debug(
        "cultural_contact_structure condition_id=%s contacts=%s exchange=%s "
        "teaching=%s conflict=%s cooperation=%s",
        condition_id,
        len(contacts),
        exchange,
        teaching,
        conflict,
        cooperation,
    )
    return {
        "contact_event_count": len(contacts),
        "exchange_count": exchange,
        "teaching_count": teaching,
        "conflict_count": conflict,
        "cooperation_count": cooperation,
    }
