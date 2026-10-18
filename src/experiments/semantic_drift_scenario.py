"""Experiment BC: longitudinal owner-scoped semantic drift.

Arms compare recorded stability, drift, and divergence only. No arm asserts
that a meaning should change, converge, or be correct, and no meaning is
injected outside ordinary observation, communication, memory, and policy.
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
    example_population_lifecycle_spec,
)
from world.actions import AgentCommand, Talk, Wait
from world.communications import origin_utterance
from world.contact import ContactMode, CulturalContactSpec
from world.events import WorldEvent
from world.identifiers import EntityId
from world.regions import CognitionMode

__all__ = [
    "assert_semantic_drift_structure",
    "bc_unsupported_config",
    "semantic_drift_arbiter",
    "semantic_drift_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.semantic_drift_scenario"
)

_AGENTS: Final[tuple[tuple[str, str], ...]] = (
    ("agent-a", "body-a"),
    ("agent-b", "body-b"),
    ("agent-e", "body-e"),
    ("agent-c", "body-c"),
    ("agent-d", "body-d"),
)
_OFF_ARMS: Final[frozenset[str]] = frozenset({"bc-off", "bc-unsupported"})
_ENABLED_ARMS: Final[frozenset[str]] = frozenset(
    {"bc-stable", "bc-isolated", "bc-contact", "bc-generation"}
)


def _agent_specs(*, semantic: bool) -> tuple[AgentRunnerSpec, ...]:
    return tuple(
        AgentRunnerSpec(
            agent_id=AgentId(agent_id),
            entity_id=EntityId(body_id),
            cognition=AgentCognitionSpec(
                agent_id=AgentId(agent_id),
                semantic_naming_mode=(
                    SemanticNamingMode.DETERMINISTIC
                    if semantic
                    else SemanticNamingMode.DISABLED
                ),
                symbolic_language_mode=(
                    SymbolicLanguageMode.DETERMINISTIC
                    if semantic
                    else SymbolicLanguageMode.DISABLED
                ),
                cultural_narrative_mode=CulturalNarrativeMode.DISABLED,
            ),
            initial_goals=(),
        )
        for agent_id, body_id in _AGENTS
    )


def semantic_drift_scenario(
    *,
    seed: int = 32,
    max_ticks: int = 24,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    if base is not None and type(base) is not SimulationRunnerConfig:
        raise TypeError("base must be SimulationRunnerConfig or None")
    active_seed = seed if base is None else base.seed
    stochastic_identity = (
        require_stochastic("semantic-drift-bc")
        if base is None
        else base.stochastic_identity
    )
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(active_seed,))
    scenario = _scenario()

    def config(
        *,
        semantic: bool,
        isolated: bool,
        contact: bool,
        generational: bool = False,
    ) -> SimulationRunnerConfig:
        regions_on = isolated or contact
        lifecycle = None
        if generational:
            lifecycle = example_population_lifecycle_spec(
                lifespan_ticks=12,
                max_population=6,
                policy_id="fixed_interval_entry",
            )
            lifecycle = replace(
                lifecycle,
                demographic_policy_params={
                    **dict(lifecycle.demographic_policy_params),
                    "spawn_location_id": "loc-north",
                },
            )
        if generational:
            from simulation.new_agent_initialization import (
                default_new_agent_initialization_spec,
            )

            initialization = default_new_agent_initialization_spec()
        else:
            initialization = None
        flags = V3CapabilityFlags(
            multi_polity_migration=regions_on,
            generational_population=generational,
        )
        return SimulationRunnerConfig(
            seed=active_seed,
            stochastic_identity=stochastic_identity,
            scenario=scenario,
            agents=_agent_specs(semantic=semantic),
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            mortality_mode=(
                MortalityMode.DISABLED if base is None else base.mortality_mode
            ),
            schema_version=(
                RUNNER_SCHEMA_VERSION_V4 if not semantic else RUNNER_SCHEMA_VERSION_V46
            ),
            v3_capability_flags=(V3CapabilityFlags() if not semantic else flags),
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
            population_lifecycle=lifecycle,
            new_agent_initialization=initialization,
        )

    arms = (
        (
            "bc-off",
            "semantic_drift_off",
            config(semantic=False, isolated=False, contact=False),
        ),
        (
            "bc-stable",
            "semantic_drift_single_population",
            config(semantic=True, isolated=False, contact=False),
        ),
        (
            "bc-isolated",
            "semantic_drift_isolated_populations",
            config(semantic=True, isolated=True, contact=False),
        ),
        (
            "bc-contact",
            "semantic_drift_contact_populations",
            config(semantic=True, isolated=True, contact=True),
        ),
        (
            "bc-generation",
            "semantic_drift_generational_population",
            config(
                semantic=True,
                isolated=False,
                contact=False,
                generational=True,
            ),
        ),
    )
    _LOG.info(
        "semantic_drift_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(_AGENTS),
    )
    return ExperimentDefinition(
        experiment_id="semantic_drift@1",
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
        paired_world_group="semantic-drift-bc-world",
    )


def bc_unsupported_config() -> SimulationRunnerConfig:
    """Non-run fixture: deterministic symbolic mode without semantic naming."""
    base = semantic_drift_scenario().conditions[0].runner_config
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


def semantic_drift_arbiter(
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
    if condition_id == "bc-contact" and horizon > 6:
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
            communication_id=f"bc-{suffix}-{tick}",
            text="call",
            concepts=("place_shared",),
            sender_confidence=0.7,
        ),
    )


def _command_factory(command: AgentCommand) -> Callable[[], AgentCommand]:
    def build() -> AgentCommand:
        return command

    return build


def _history(ledgers: object) -> tuple[tuple[int, int, str], ...]:
    records: list[tuple[int, int, str]] = []
    if isinstance(ledgers, Mapping):
        values = tuple(ledgers.values())
    elif isinstance(ledgers, Sequence) and not isinstance(ledgers, (str, bytes)):
        values = tuple(ledgers)
    else:
        values = ()
    for ledger in values:
        items = (
            *getattr(ledger, "bindings", ()),
            *getattr(ledger, "compositions", ()),
        )
        for item in items:
            history = tuple(getattr(item, "sense_history", ()) or ())
            revision = int(getattr(item, "sense_revision", 0))
            shifted = sum(
                1
                for record in history
                if getattr(getattr(record, "trigger", None), "value", None) == "shifted"
            )
            if shifted > revision:
                raise AssertionError("sense_history_exceeds_revision")
            previous_ordinal = -1
            previous_tick = -1
            for record in history:
                ordinal = int(getattr(record, "ordinal", -1))
                tick = int(getattr(record, "tick", -1))
                if ordinal <= previous_ordinal or tick < previous_tick:
                    raise AssertionError("sense_history_not_monotonic")
                previous_ordinal = ordinal
                previous_tick = tick
            if len(history) > 16:
                raise AssertionError("sense_history_cap_exceeded")
            for record in history:
                records.append(
                    (
                        int(getattr(record, "tick", 0)),
                        int(getattr(record, "ordinal", 0)),
                        str(
                            getattr(
                                getattr(record, "trigger", None), "value", "unknown"
                            )
                        ),
                    )
                )
    return tuple(records)


def assert_semantic_drift_structure(
    condition_id: str,
    config: SimulationRunnerConfig,
    events: Sequence[WorldEvent] = (),
    *,
    naming_ledgers: object = (),
    symbolic_ledgers: object = (),
    initial_lifecycle_records: Sequence[object] = (),
) -> dict[str, int]:
    """Assert only structural facts; never that drift or convergence occurs."""
    del events
    naming_modes = tuple(
        agent.cognition.semantic_naming_mode for agent in config.agents
    )
    symbolic_modes = tuple(
        agent.cognition.symbolic_language_mode for agent in config.agents
    )
    naming_history = _history(naming_ledgers)
    symbolic_history = _history(symbolic_ledgers)
    if condition_id in _OFF_ARMS:
        if any(mode is SemanticNamingMode.DETERMINISTIC for mode in naming_modes):
            raise AssertionError("naming_mode_present_in_off_arm")
        if any(mode is SymbolicLanguageMode.DETERMINISTIC for mode in symbolic_modes):
            raise AssertionError("symbolic_mode_present_in_off_arm")
        if naming_history or symbolic_history:
            raise AssertionError("sense_history_present_in_off_arm")
    elif condition_id in _ENABLED_ARMS:
        if not all(
            mode is SemanticNamingMode.DETERMINISTIC for mode in naming_modes
        ):
            raise AssertionError("semantic_naming_missing")
        if not all(
            mode is SymbolicLanguageMode.DETERMINISTIC for mode in symbolic_modes
        ):
            raise AssertionError("symbolic_mode_missing")
        if condition_id == "bc-isolated" and config.cultural_contact is not None:
            raise AssertionError("isolated_arm_has_contact")
        if condition_id == "bc-contact" and config.cultural_contact is None:
            raise AssertionError("contact_arm_missing_contact")
        if condition_id == "bc-generation":
            if config.population_lifecycle is None:
                raise AssertionError("generation_arm_missing_lifecycle")
            if config.new_agent_initialization is None:
                raise AssertionError("generation_arm_missing_initialization")
            if not initial_lifecycle_records:
                raise AssertionError("generation_arm_missing_lifecycle_records")
    else:
        raise AssertionError("unknown_condition")
    generations = {
        int(getattr(record, "generation_index", -1))
        for record in initial_lifecycle_records
    }
    _LOG.debug(
        "semantic_drift_structure condition_id=%s naming_records=%s "
        "symbolic_records=%s generations=%s",
        condition_id,
        len(naming_history),
        len(symbolic_history),
        len(generations),
    )
    return {
        "sense_record_count": len(naming_history) + len(symbolic_history),
        "generation_count": len(generations),
        "semantic_agent_count": sum(
            mode is SemanticNamingMode.DETERMINISTIC for mode in naming_modes
        ),
    }
