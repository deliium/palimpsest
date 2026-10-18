"""Experiment BE: multi-generational owner-scoped historical narratives."""

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
from experiments.multiple_societies_scenario import _scenario
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V21,
    RUNNER_SCHEMA_VERSION_V48,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CulturalNarrativeMode,
    GenerationalNarrativesSpec,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    example_cultural_feature_provenance_spec,
    example_population_lifecycle_spec,
)
from world.actions import AgentCommand, Inscribe, Talk, Wait
from world.artifacts import ArtifactContent, ArtifactKind
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.events import WorldEvent
from world.identifiers import EntityId

__all__ = [
    "assert_generational_narrative_structure",
    "be_unsupported_config",
    "generational_narrative_arbiter",
    "generational_narratives_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_narratives_scenario"
)

_AGENTS: Final[tuple[tuple[str, str], ...]] = (
    ("agent-a", "body-a"),
    ("agent-b", "body-b"),
    ("agent-e", "body-e"),
    ("agent-c", "body-c"),
    ("agent-d", "body-d"),
)
_OFF_ARMS: Final[frozenset[str]] = frozenset({"be-off", "be-unsupported"})
_ENABLED_ARMS: Final[frozenset[str]] = frozenset(
    {
        "be-witness-death",
        "be-record-backed",
        "be-record-loss",
        "be-merge-edit",
        "be-theme-coverage",
        "be-objective-comparison",
    }
)


def _agent_specs(*, narrative: bool) -> tuple[AgentRunnerSpec, ...]:
    return tuple(
        AgentRunnerSpec(
            agent_id=AgentId(agent_id),
            entity_id=EntityId(body_id),
            cognition=AgentCognitionSpec(
                agent_id=AgentId(agent_id),
                cultural_narrative_mode=(
                    CulturalNarrativeMode.DETERMINISTIC
                    if narrative
                    else CulturalNarrativeMode.DISABLED
                ),
            ),
            initial_goals=(),
        )
        for agent_id, body_id in _AGENTS
    )


def generational_narratives_scenario(
    *,
    seed: int = 40,
    max_ticks: int = 16,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    if base is not None and type(base) is not SimulationRunnerConfig:
        raise TypeError("base must be SimulationRunnerConfig or None")
    active_seed = seed if base is None else base.seed
    stochastic_identity = (
        require_stochastic("generational-narratives-be")
        if base is None
        else base.stochastic_identity
    )
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(active_seed,))
    scenario = _scenario()

    def config(
        *,
        enabled: bool,
        durable_records: bool = False,
        historical_layers: bool = False,
    ) -> SimulationRunnerConfig:
        if not enabled:
            return SimulationRunnerConfig(
                seed=active_seed,
                stochastic_identity=stochastic_identity,
                scenario=scenario,
                agents=_agent_specs(narrative=True),
                stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
                mortality_mode=(
                    MortalityMode.DISABLED if base is None else base.mortality_mode
                ),
                schema_version=RUNNER_SCHEMA_VERSION_V21,
            )
        from simulation.runner_models import (
            DurableRecordsSpec,
            HistoricalMemoryLayersSpec,
        )

        return SimulationRunnerConfig(
            seed=active_seed,
            stochastic_identity=stochastic_identity,
            scenario=scenario,
            agents=_agent_specs(narrative=True),
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            mortality_mode=(
                MortalityMode.ENABLED if base is None else base.mortality_mode
            ),
            schema_version=RUNNER_SCHEMA_VERSION_V48,
            v3_capability_flags=V3CapabilityFlags(
                generational_population=True,
                cultural_historical_memory=True,
            ),
            population_lifecycle=example_population_lifecycle_spec(
                lifespan_ticks=8,
                policy_id="fixed_interval_entry",
            ),
            new_agent_initialization=default_new_agent_initialization_spec(),
            cultural_feature_provenance=(
                example_cultural_feature_provenance_spec()
            ),
            durable_records=(
                DurableRecordsSpec(enabled_genres=("story", "chronicle"))
                if durable_records
                else None
            ),
            historical_memory_layers=(
                HistoricalMemoryLayersSpec() if historical_layers else None
            ),
            generational_narratives=GenerationalNarrativesSpec(),
        )

    arms = (
        ("be-off", "generational_narratives_off", config(enabled=False)),
        (
            "be-witness-death",
            "generational_narratives_witness_death",
            config(enabled=True),
        ),
        (
            "be-record-backed",
            "generational_narratives_record_backed",
            config(enabled=True, durable_records=True),
        ),
        (
            "be-record-loss",
            "generational_narratives_record_loss",
            config(enabled=True, durable_records=True, historical_layers=True),
        ),
        (
            "be-merge-edit",
            "generational_narratives_merge_edit",
            config(enabled=True, durable_records=True),
        ),
        (
            "be-theme-coverage",
            "generational_narratives_theme_coverage",
            config(enabled=True),
        ),
        (
            "be-objective-comparison",
            "generational_narratives_objective_comparison",
            config(enabled=True, historical_layers=True),
        ),
    )
    _LOG.info(
        "generational_narratives_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(_AGENTS),
    )
    return ExperimentDefinition(
        experiment_id="generational_narratives@1",
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
        paired_world_group="generational-narratives-be-world",
    )


def be_unsupported_config() -> SimulationRunnerConfig:
    """Non-run fixture: generational narratives without lifecycle fails closed."""
    base = generational_narratives_scenario().conditions[1].runner_config
    return replace(base, population_lifecycle=None)


def generational_narrative_arbiter(
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
    if condition_id in {"be-record-backed", "be-record-loss"}:
        commands[0, "agent-a"] = Inscribe(
            kind=ArtifactKind.RECORD
            if condition_id == "be-record-backed"
            else ArtifactKind.NOTE,
            content=ArtifactContent(),
            hold=False,
        )
    if condition_id in {"be-witness-death", "be-record-backed", "be-record-loss"}:
        _story_talk(
            commands,
            tick=1,
            speaker="body-a",
            recipient="body-b",
            token="founding",
        )
    if condition_id == "be-merge-edit":
        _story_talk(
            commands, tick=1, speaker="body-a", recipient="body-b", token="founding"
        )
        _story_talk(
            commands, tick=2, speaker="body-b", recipient="body-c", token="founding"
        )
    if condition_id == "be-theme-coverage":
        for tick, token in enumerate(
            ("founding", "disaster", "discovery", "conflict", "migration", "craft")
        ):
            _story_talk(
                commands,
                tick=tick,
                speaker="body-a",
                recipient="body-b",
                token=token,
            )
    if condition_id == "be-objective-comparison":
        _story_talk(
            commands, tick=1, speaker="body-a", recipient="body-b", token="founding"
        )
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


def _story_talk(
    commands: dict[tuple[int, str], AgentCommand],
    *,
    tick: int,
    speaker: str,
    recipient: str,
    token: str,
) -> None:
    agent_id = f"agent-{speaker.removeprefix('body-')}"
    commands[tick, agent_id] = Talk(
        recipient_id=EntityId(recipient),
        utterance=origin_utterance(
            speaker_id=EntityId(speaker),
            communication_id=f"be-{tick}-{token}",
            text="retell",
            relations=(
                CommunicationRelation(
                    subject=token, predicate="retell", object="event"
                ),
            ),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _command_factory(command: AgentCommand) -> Callable[[], AgentCommand]:
    def build() -> AgentCommand:
        return command

    return build


def assert_generational_narrative_structure(
    condition_id: str,
    config: SimulationRunnerConfig,
    events: Sequence[WorldEvent] = (),
    *,
    cultural_narrative_ledgers: object = (),
) -> dict[str, int]:
    """Assert bounded structural facts only; never truth or convergence."""
    del events
    if condition_id in _OFF_ARMS:
        if condition_id == "be-off":
            if config.generational_narratives is not None:
                raise AssertionError("generational_spec_present_in_off_arm")
            if config.schema_version == RUNNER_SCHEMA_VERSION_V48:
                raise AssertionError("v48_in_off_arm")
        return {
            "variant_count": 0,
            "witness_count": 0,
            "record_count": 0,
            "transition_count": 0,
        }
    if condition_id not in _ENABLED_ARMS:
        raise AssertionError("unknown_condition")
    spec = config.generational_narratives
    if spec is None:
        raise AssertionError("generational_spec_missing")
    if config.schema_version != RUNNER_SCHEMA_VERSION_V48:
        raise AssertionError("v48_missing")
    if not config.v3_capability_flags.generational_population:
        raise AssertionError("generational_flag_missing")
    if config.population_lifecycle is None:
        raise AssertionError("lifecycle_missing")
    if config.cultural_feature_provenance is None:
        raise AssertionError("cultural_provenance_missing")
    ledgers = _ledgers(cultural_narrative_ledgers)
    variant_count = witness_count = record_count = transition_count = 0
    for ledger in ledgers:
        for variant in getattr(ledger, "variants", ()) or ():
            variant_count += 1
            witness_count += len(getattr(variant, "source_witnesses", ()) or ())
            record_count += len(getattr(variant, "record_refs", ()) or ())
            transition_count += len(getattr(variant, "transitions", ()) or ())
            if witness_count > spec.max_witnesses * max(len(ledgers), 1) * 8:
                raise AssertionError("witness_cap_exceeded")
    return {
        "variant_count": variant_count,
        "witness_count": witness_count,
        "record_count": record_count,
        "transition_count": transition_count,
    }


def _ledgers(value: object) -> tuple[object, ...]:
    if isinstance(value, dict):
        return tuple(value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(value)
    return ()
