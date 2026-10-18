"""Experiment BD: owner-scoped cross-cultural translation.

Arms compare bounded, owner-scoped translation hypotheses only. No arm asserts
that a translation is correct, that meanings converge, or that a shared
dictionary exists.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
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
    RUNNER_SCHEMA_VERSION_V20,
    RUNNER_SCHEMA_VERSION_V47,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    SemanticNamingMode,
    SimulationRunnerConfig,
    SymbolicLanguageMode,
    TranslationMode,
    V3CapabilityFlags,
)
from world.actions import AgentCommand, Talk, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.contact import ContactMode, CulturalContactSpec
from world.events import WorldEvent
from world.identifiers import EntityId
from world.regions import CognitionMode

__all__ = [
    "assert_translation_structure",
    "bd_unsupported_config",
    "translation_arbiter",
    "translation_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.translation_scenario"
)

_AGENTS: Final[tuple[tuple[str, str], ...]] = (
    ("agent-a", "body-a"),
    ("agent-b", "body-b"),
    ("agent-e", "body-e"),
    ("agent-c", "body-c"),
    ("agent-d", "body-d"),
)
_OFF_ARMS: Final[frozenset[str]] = frozenset({"bd-off", "bd-unsupported"})
_ENABLED_ARMS: Final[frozenset[str]] = frozenset(
    {
        "bd-naming-only",
        "bd-shared-observation",
        "bd-demonstration",
        "bd-repeated-teaching-artifact",
        "bd-ambiguous-wrong",
    }
)


def _agent_specs(
    *, naming: bool, translation: bool, symbolic: bool = False
) -> tuple[AgentRunnerSpec, ...]:
    return tuple(
        AgentRunnerSpec(
            agent_id=AgentId(agent_id),
            entity_id=EntityId(body_id),
            cognition=AgentCognitionSpec(
                agent_id=AgentId(agent_id),
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
            initial_goals=(),
        )
        for agent_id, body_id in _AGENTS
    )


def translation_scenario(
    *,
    seed: int = 35,
    max_ticks: int = 16,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    if base is not None and type(base) is not SimulationRunnerConfig:
        raise TypeError("base must be SimulationRunnerConfig or None")
    active_seed = seed if base is None else base.seed
    stochastic_identity = (
        require_stochastic("translation-bd")
        if base is None
        else base.stochastic_identity
    )
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(active_seed,))
    scenario = _scenario()

    def config(
        *,
        naming: bool,
        translation: bool,
        regions: bool = False,
        contact: bool = False,
        symbolic: bool = False,
    ) -> SimulationRunnerConfig:
        regions_on = regions or contact
        if translation:
            schema_version = RUNNER_SCHEMA_VERSION_V47
        elif naming:
            schema_version = RUNNER_SCHEMA_VERSION_V20
        else:
            schema_version = RUNNER_SCHEMA_VERSION_V4
        return SimulationRunnerConfig(
            seed=active_seed,
            stochastic_identity=stochastic_identity,
            scenario=scenario,
            agents=_agent_specs(
                naming=naming, translation=translation, symbolic=symbolic
            ),
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            mortality_mode=(
                MortalityMode.DISABLED if base is None else base.mortality_mode
            ),
            schema_version=schema_version,
            v3_capability_flags=(
                V3CapabilityFlags(multi_polity_migration=True)
                if regions_on
                else V3CapabilityFlags()
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
            "bd-off",
            "translation_off",
            config(naming=False, translation=False),
        ),
        (
            "bd-naming-only",
            "translation_naming_only",
            config(naming=True, translation=False),
        ),
        (
            "bd-shared-observation",
            "translation_shared_observation",
            config(
                naming=True,
                translation=True,
                regions=True,
                contact=True,
            ),
        ),
        (
            "bd-demonstration",
            "translation_demonstration",
            config(naming=True, translation=True),
        ),
        (
            "bd-repeated-teaching-artifact",
            "translation_repeated_teaching_artifact",
            config(naming=True, translation=True, regions=True),
        ),
        (
            "bd-ambiguous-wrong",
            "translation_ambiguous_wrong",
            config(naming=True, translation=True, regions=True),
        ),
    )
    _LOG.info(
        "translation_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(_AGENTS),
    )
    return ExperimentDefinition(
        experiment_id="cross_cultural_translation@1",
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
        paired_world_group="translation-bd-world",
    )


def bd_unsupported_config() -> SimulationRunnerConfig:
    """Non-run fixture: translation without deterministic naming fails closed."""
    base = translation_scenario().conditions[0].runner_config
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                translation_mode=TranslationMode.DETERMINISTIC,
                semantic_naming_mode=SemanticNamingMode.DISABLED,
            ),
        )
        for agent in base.agents
    )
    return replace(base, agents=agents, schema_version=RUNNER_SCHEMA_VERSION_V47)


def translation_arbiter(
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
        _call(commands, tick, "body-a", "body-b", "foreign_a", "location")
        if condition_id in {
            "bd-repeated-teaching-artifact",
            "bd-ambiguous-wrong",
        }:
            _call(commands, tick, "body-c", "body-d", "foreign_b", "location")
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


def _call(
    commands: dict[tuple[int, str], AgentCommand],
    tick: int,
    speaker: str,
    recipient: str,
    token: str,
    kind: str,
) -> None:
    agent_id = f"agent-{speaker.removeprefix('body-')}"
    commands[tick, agent_id] = Talk(
        recipient_id=EntityId(recipient),
        utterance=origin_utterance(
            speaker_id=EntityId(speaker),
            communication_id=f"bd-{tick}-{token}",
            text="call",
            sender_confidence=0.7,
            relations=(
                CommunicationRelation(
                    subject=token, predicate="call", object=kind
                ),
            ),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _command_factory(command: AgentCommand) -> Callable[[], AgentCommand]:
    def build() -> AgentCommand:
        return command

    return build


def _ledgers(value: object) -> tuple[object, ...]:
    if isinstance(value, Mapping):
        return tuple(value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(value)
    return ()


def assert_translation_structure(
    condition_id: str,
    config: SimulationRunnerConfig,
    events: Sequence[WorldEvent] = (),
    *,
    translation_ledgers: object = (),
    naming_ledgers: object = (),
) -> dict[str, int]:
    """Assert only structural facts; never that translation succeeded."""
    del events
    modes = tuple(agent.cognition.translation_mode for agent in config.agents)
    naming_modes = tuple(
        agent.cognition.semantic_naming_mode for agent in config.agents
    )
    ledgers = _ledgers(translation_ledgers)
    mapping_count = sum(
        len(getattr(ledger, "mappings", ()) or ()) for ledger in ledgers
    )
    if condition_id in _OFF_ARMS:
        if any(mode is TranslationMode.DETERMINISTIC for mode in modes):
            raise AssertionError("translation_mode_present_in_off_arm")
        if mapping_count:
            raise AssertionError("translation_mapping_present_in_off_arm")
    elif condition_id in _ENABLED_ARMS:
        if not all(mode is TranslationMode.DETERMINISTIC for mode in modes):
            raise AssertionError("translation_mode_missing")
        if condition_id == "bd-naming-only" and mapping_count:
            raise AssertionError("translation_mapping_without_mode")
        if condition_id != "bd-naming-only" and not all(
            mode is SemanticNamingMode.DETERMINISTIC for mode in naming_modes
        ):
            raise AssertionError("semantic_naming_missing")
        for ledger in ledgers:
            previous_tick = -1
            for mapping in getattr(ledger, "mappings", ()) or ():
                if int(getattr(mapping, "last_tick", 0)) < previous_tick:
                    raise AssertionError("mapping_ticks_not_monotonic")
                previous_tick = int(getattr(mapping, "last_tick", 0))
                if len(getattr(mapping, "targets", ()) or ()) > 3:
                    raise AssertionError("mapping_target_cap_exceeded")
                if getattr(mapping, "status", None) is None:
                    raise AssertionError("mapping_status_missing")
    else:
        raise AssertionError("unknown_condition")
    _LOG.debug(
        "translation_structure condition_id=%s ledger_count=%s mapping_count=%s",
        condition_id,
        len(ledgers),
        mapping_count,
    )
    return {
        "mapping_count": mapping_count,
        "translation_agent_count": sum(
            mode is TranslationMode.DETERMINISTIC for mode in modes
        ),
        "naming_agent_count": sum(
            mode is SemanticNamingMode.DETERMINISTIC for mode in naming_modes
        ),
        "naming_ledger_count": len(_ledgers(naming_ledgers)),
    }
