"""Experiment BB: bounded compositional symbols over private terminology.

Symbolic composition is owner-scoped and analysis-only. Arms never assert
convergence, agreement, or a "better language"; they compare structural
presence, isolation, and delivered-message borrowing only.
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
    RUNNER_SCHEMA_VERSION_V46,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CulturalNarrativeMode,
    MortalityMode,
    RunnerStopPolicy,
    SemanticNamingMode,
    SimulationRunnerConfig,
    SymbolicLanguageMode,
    V3CapabilityFlags,
)
from world.actions import AgentCommand, Talk, Wait
from world.communications import origin_utterance
from world.contact import ContactMode, CulturalContactSpec
from world.events import WorldEvent
from world.identifiers import EntityId
from world.regions import CognitionMode

__all__ = [
    "assert_symbolic_language_structure",
    "bb_unsupported_config",
    "symbolic_language_arbiter",
    "symbolic_language_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.symbolic_language_scenario"
)

_AGENTS: Final[tuple[tuple[str, str], ...]] = (
    ("agent-a", "body-a"),
    ("agent-b", "body-b"),
    ("agent-e", "body-e"),
    ("agent-c", "body-c"),
    ("agent-d", "body-d"),
)
_OFF_ARMS: Final[frozenset[str]] = frozenset({"bb-off", "bb-unsupported"})
_SYMBOLIC_ARMS: Final[frozenset[str]] = frozenset(
    {"bb-single", "bb-isolated", "bb-contact"}
)


def _agent_specs(
    *, symbolic: bool, base: SimulationRunnerConfig | None
) -> tuple[AgentRunnerSpec, ...]:
    del base
    return tuple(
        AgentRunnerSpec(
            agent_id=AgentId(agent_id),
            entity_id=EntityId(body_id),
            cognition=AgentCognitionSpec(
                agent_id=AgentId(agent_id),
                semantic_naming_mode=(
                    SemanticNamingMode.DETERMINISTIC
                    if symbolic
                    else SemanticNamingMode.DISABLED
                ),
                symbolic_language_mode=(
                    SymbolicLanguageMode.DETERMINISTIC
                    if symbolic
                    else SymbolicLanguageMode.DISABLED
                ),
                cultural_narrative_mode=CulturalNarrativeMode.DISABLED,
            ),
            initial_goals=(),
        )
        for agent_id, body_id in _AGENTS
    )


def symbolic_language_scenario(
    *,
    seed: int = 31,
    max_ticks: int = 16,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    if base is not None and type(base) is not SimulationRunnerConfig:
        raise TypeError("base must be SimulationRunnerConfig or None")
    active_seed = seed if base is None else base.seed
    stochastic_identity = (
        require_stochastic("symbolic-language-bb")
        if base is None
        else base.stochastic_identity
    )
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(active_seed,))
    scenario = _scenario()

    def config(
        *, symbolic: bool, isolated: bool, contact: bool
    ) -> SimulationRunnerConfig:
        regions_on = isolated or contact
        return SimulationRunnerConfig(
            seed=active_seed,
            stochastic_identity=stochastic_identity,
            scenario=scenario,
            agents=_agent_specs(symbolic=symbolic, base=base),
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            mortality_mode=(
                MortalityMode.DISABLED if base is None else base.mortality_mode
            ),
            schema_version=(
                RUNNER_SCHEMA_VERSION_V4 if not symbolic else RUNNER_SCHEMA_VERSION_V46
            ),
            v3_capability_flags=(
                V3CapabilityFlags()
                if not regions_on
                else V3CapabilityFlags(multi_polity_migration=True)
            ),
            regions_migration=(
                None
                if not regions_on
                else _regions(cognition_mode=CognitionMode.DETERMINISTIC)
            ),
            cultural_contact=(
                None
                if not contact
                else CulturalContactSpec(mode=ContactMode.DETERMINISTIC)
            ),
        )

    arms = (
        (
            "bb-off",
            "symbolic_language_off",
            config(symbolic=False, isolated=False, contact=False),
        ),
        (
            "bb-single",
            "symbolic_language_single_population",
            config(symbolic=True, isolated=False, contact=False),
        ),
        (
            "bb-isolated",
            "symbolic_language_isolated_populations",
            config(symbolic=True, isolated=True, contact=False),
        ),
        (
            "bb-contact",
            "symbolic_language_contact_populations",
            config(symbolic=True, isolated=True, contact=True),
        ),
    )
    _LOG.info(
        "symbolic_language_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(_AGENTS),
    )
    return ExperimentDefinition(
        experiment_id="compositional_symbols@1",
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
        paired_world_group="symbolic-language-bb-world",
    )


def bb_unsupported_config() -> SimulationRunnerConfig:
    """Non-run fixture: deterministic symbolic mode without semantic naming."""
    base = symbolic_language_scenario().conditions[0].runner_config
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                symbolic_language_mode=SymbolicLanguageMode.DETERMINISTIC,
                semantic_naming_mode=SemanticNamingMode.DISABLED,
            ),
        )
        for agent in base.agents
    )
    return replace(
        base,
        agents=agents,
        schema_version=RUNNER_SCHEMA_VERSION_V46,
    )


def symbolic_language_arbiter(
    condition_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    if condition_id in _OFF_ARMS:
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
    if condition_id in {"bb-contact"} and horizon > 6:
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
            communication_id=f"bb-{suffix}-{tick}",
            text="call",
            concepts=("place_shared",),
            sender_confidence=0.7,
        ),
    )


def _command_factory(command: AgentCommand) -> Callable[[], AgentCommand]:
    def build() -> AgentCommand:
        return command

    return build


def assert_symbolic_language_structure(
    condition_id: str,
    config: SimulationRunnerConfig,
    events: Sequence[WorldEvent],
    compositions: Sequence[object] = (),
) -> dict[str, int]:
    """Assert only structural symbolic facts; never convergence success."""
    composed: list[WorldEvent] = []
    for event in events:
        details = getattr(event, "details", None)
        utterance = getattr(details, "utterance", None)
        if utterance is None:
            continue
        if any(
            relation.predicate in {"attributive", "relational"}
            for relation in utterance.content.relations
        ):
            composed.append(event)
    modes = tuple(agent.cognition.symbolic_language_mode for agent in config.agents)
    naming_modes = tuple(
        agent.cognition.semantic_naming_mode for agent in config.agents
    )
    active = tuple(
        item
        for item in compositions
        if str(
            getattr(
                getattr(item, "status", None),
                "value",
                getattr(item, "status", ""),
            )
        )
        == "active"
    )
    if condition_id in _OFF_ARMS:
        if any(mode is SymbolicLanguageMode.DETERMINISTIC for mode in modes):
            raise AssertionError("symbolic_mode_present_in_off_arm")
        if composed:
            raise AssertionError("composed_message_in_off_arm")
        if compositions:
            raise AssertionError("composition_present_in_off_arm")
    elif condition_id in _SYMBOLIC_ARMS:
        if not all(mode is SymbolicLanguageMode.DETERMINISTIC for mode in modes):
            raise AssertionError("symbolic_mode_missing")
        if not all(mode is SemanticNamingMode.DETERMINISTIC for mode in naming_modes):
            raise AssertionError("semantic_naming_missing")
        if condition_id == "bb-single":
            if compositions and not active:
                raise AssertionError("single_arm_without_active_composition")
            if events and not composed:
                raise AssertionError("single_arm_without_composed_talk")
        if condition_id == "bb-isolated" and config.cultural_contact is not None:
            raise AssertionError("isolated_arm_has_contact")
        if condition_id == "bb-contact" and config.cultural_contact is None:
            raise AssertionError("contact_arm_missing_contact")
    _LOG.debug(
        "symbolic_language_structure condition_id=%s composed=%s",
        condition_id,
        len(composed),
    )
    return {
        "composed_message_count": len(composed),
        "symbolic_agent_count": sum(
            mode is SymbolicLanguageMode.DETERMINISTIC for mode in modes
        ),
    }
