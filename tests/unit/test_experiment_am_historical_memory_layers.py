"""Off-gate Experiment AM for historical memory layers on runner-config-v32."""

from __future__ import annotations

import logging
from dataclasses import fields, replace
from types import SimpleNamespace

import pytest

from agents.models import AgentId
from analysis.historical_memory import (
    HistoricalMemoryLayerId,
    HistoricalMemoryQueryId,
    HistoricalSourceRef,
    answer_historical_memory_queries,
    build_historical_provenance_graph,
    classify_historical_memory_layer,
)
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    cultural_transmission_provenance_profile,
    experiment_am_historical_memory_layers,
    historical_memory_layers_profile,
)
from experiments.catalog import base_runner_config_from_scenario, v3_scaffolding_profile
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CulturalNarrativeMode,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_historical_memory_layers_spec,
)
from simulation.runner_serialization import build_runner_result_document
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.observations import Observation

_LOG = logging.getLogger("tests.experiment_am_historical_memory_layers")

_AM_ARM_IDS = (
    "am-layers-off",
    "am-living",
    "am-witness-death",
    "am-communicative",
    "am-cultural-only",
    "am-narrative-join",
    "am-flags-off",
)


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=210,
        stochastic_identity="cmp-am-historical-memory",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-am-historical"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-a"),
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-b"),
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-b")),
            ),
        ),
        max_ticks=8,
    )


def _arm(definition, arm_id: str):
    return next(
        item for item in definition.conditions if item.condition_id == arm_id
    ).runner_config


def test_am_profile_gates_and_arms() -> None:
    _LOG.debug("case_id=am_catalog_arms")
    definition = experiment_am_historical_memory_layers(_base(), max_ticks=6)
    assert definition.experiment_id == "experiment-am-historical-memory-layers"
    condition_ids = tuple(item.condition_id for item in definition.conditions)
    assert condition_ids == _AM_ARM_IDS
    assert "experiment-am-historical-memory-layers" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "experiment-a-memory" not in OFF_GATE_MATRIX_EXPERIMENT_IDS

    layers_off = _arm(definition, "am-layers-off")
    assert layers_off.schema_version == RUNNER_SCHEMA_VERSION_V31
    assert layers_off.historical_memory_layers is None
    assert layers_off.cultural_feature_provenance is not None
    assert cultural_transmission_provenance_profile(layers_off) is layers_off

    living = _arm(definition, "am-living")
    assert living.schema_version == RUNNER_SCHEMA_VERSION_V32
    assert historical_memory_layers_profile(living) is living
    assert living.historical_memory_layers is not None
    assert living.cultural_feature_provenance is not None
    assert living.v3_capability_flags.cultural_historical_memory is True

    witness = _arm(definition, "am-witness-death")
    assert witness.population_lifecycle is not None
    assert witness.v3_capability_flags.generational_population is True

    cultural = _arm(definition, "am-cultural-only")
    assert cultural.population_lifecycle is not None

    narrative = _arm(definition, "am-narrative-join")
    assert narrative.historical_memory_layers.include_narrative_lineage is True
    modes = {
        agent.cognition.cultural_narrative_mode for agent in narrative.agents
    }
    assert CulturalNarrativeMode.DETERMINISTIC in modes

    flags_off = _arm(definition, "am-flags-off")
    assert flags_off.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert flags_off.historical_memory_layers is None
    assert flags_off.cultural_feature_provenance is None
    assert flags_off.v3_capability_flags.any_enabled() is False


def test_am_profile_rejects_unowned_flags_and_missing_objects() -> None:
    living = _arm(
        experiment_am_historical_memory_layers(_base(), max_ticks=4), "am-living"
    )
    forbidden = replace(
        living,
        v3_capability_flags=V3CapabilityFlags(
            cultural_historical_memory=True,
            multi_polity_migration=True,
        ),
    )
    with pytest.raises(ValueError, match="historical_memory_profile_extra_flags"):
        historical_memory_layers_profile(forbidden)

    # Duck-type missing objects: SimulationRunnerConfig forbids stripping
    # layers/provenance on v32, so profile against a stand-in.
    duck_missing_layers = SimpleNamespace(
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        v3_capability_flags=SimpleNamespace(
            cultural_historical_memory=True,
            enabled_names=lambda: ("cultural_historical_memory",),
        ),
        cultural_feature_provenance=object(),
        historical_memory_layers=None,
    )
    with pytest.raises(ValueError, match="historical_memory_profile_missing_layers"):
        historical_memory_layers_profile(duck_missing_layers)  # type: ignore[arg-type]

    duck_missing_prov = SimpleNamespace(
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        v3_capability_flags=SimpleNamespace(
            cultural_historical_memory=True,
            enabled_names=lambda: ("cultural_historical_memory",),
        ),
        cultural_feature_provenance=None,
        historical_memory_layers=object(),
    )
    with pytest.raises(
        ValueError, match="historical_memory_profile_missing_provenance"
    ):
        historical_memory_layers_profile(duck_missing_prov)  # type: ignore[arg-type]


def test_arm_living_query_and_layer() -> None:
    arm_id = "am-living"
    graph = build_historical_provenance_graph(
        as_of_tick=3,
        sources=(HistoricalSourceRef(source_event_id="evt-1"),),
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        death_ticks={},
        layers_spec=example_historical_memory_layers_spec(),
    )
    assignment = classify_historical_memory_layer(
        graph,
        HistoricalSourceRef(source_event_id="evt-1"),
        death_ticks={},
    )
    assert assignment is not None, f"{arm_id}: expected living assignment"
    assert assignment.layer is HistoricalMemoryLayerId.LIVING, (
        f"{arm_id}: expected layer=living got={assignment.layer}"
    )
    report = answer_historical_memory_queries(
        graph,
        (HistoricalSourceRef(source_event_id="evt-1"),),
        death_ticks={},
    )
    q1 = next(
        a
        for a in report.answers
        if a.query_id is HistoricalMemoryQueryId.ANY_DIRECT_WITNESSES_ALIVE
    )
    assert q1.answer is True, (
        f"{arm_id}: query_id=any_direct_witnesses_alive expected=true"
    )


def test_arm_witness_death_query_flip() -> None:
    arm_id = "am-witness-death"
    source = HistoricalSourceRef(source_event_id="evt-1")
    living_graph = build_historical_provenance_graph(
        as_of_tick=2,
        sources=(source,),
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        communication_edges=(
            SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=1),
        ),
        death_ticks={},
    )
    before = answer_historical_memory_queries(
        living_graph, (source,), death_ticks={}
    )
    q_alive_before = next(
        a
        for a in before.answers
        if a.query_id is HistoricalMemoryQueryId.ANY_DIRECT_WITNESSES_ALIVE
    )
    assert q_alive_before.answer is True, (
        f"{arm_id}: query_id=any_direct_witnesses_alive expected=true before death"
    )

    dead_graph = build_historical_provenance_graph(
        as_of_tick=4,
        sources=(source,),
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        communication_edges=(
            SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=1),
        ),
        death_ticks={"w1": 3},
    )
    after = answer_historical_memory_queries(
        dead_graph, (source,), death_ticks={"w1": 3}
    )
    q_alive_after = next(
        a
        for a in after.answers
        if a.query_id is HistoricalMemoryQueryId.ANY_DIRECT_WITNESSES_ALIVE
    )
    q_speak = next(
        a
        for a in after.answers
        if a.query_id
        is HistoricalMemoryQueryId.ANYONE_REMEMBERS_SPEAKING_TO_WITNESS
    )
    assignment = classify_historical_memory_layer(
        dead_graph, source, death_ticks={"w1": 3}
    )
    assert q_alive_after.answer is False, (
        f"{arm_id}: query_id=any_direct_witnesses_alive expected=false after death"
    )
    assert q_speak.answer is True, (
        f"{arm_id}: query_id=anyone_remembers_speaking_to_witness expected=true"
    )
    assert assignment is not None
    assert assignment.layer in {
        HistoricalMemoryLayerId.COMMUNICATIVE,
        HistoricalMemoryLayerId.CULTURAL,
    }, f"{arm_id}: expected communicative|cultural got={assignment.layer}"


def test_arm_communicative_and_cultural_only() -> None:
    arm_comm = "am-communicative"
    source = HistoricalSourceRef(source_event_id="evt-1")
    graph = build_historical_provenance_graph(
        as_of_tick=4,
        sources=(source,),
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        communication_edges=(
            SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=1),
        ),
        death_ticks={"w1": 2},
    )
    assignment = classify_historical_memory_layer(
        graph, source, death_ticks={"w1": 2}
    )
    assert assignment is not None
    assert assignment.layer is HistoricalMemoryLayerId.COMMUNICATIVE, (
        f"{arm_comm}: expected layer=communicative got={assignment.layer}"
    )

    arm_cult = "am-cultural-only"
    cultural_graph = build_historical_provenance_graph(
        as_of_tick=5,
        sources=(source,),
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        artifact_rows=(
            SimpleNamespace(
                source_event_id="evt-1",
                carrier_agent_id="a1",
                artifact_id="mark-1",
            ),
        ),
        death_ticks={"w1": 2},
        include_artifact_edges=True,
    )
    cultural = classify_historical_memory_layer(
        cultural_graph, source, death_ticks={"w1": 2}
    )
    assert cultural is not None
    assert cultural.layer is HistoricalMemoryLayerId.CULTURAL, (
        f"{arm_cult}: expected layer=cultural got={cultural.layer}"
    )
    report = answer_historical_memory_queries(
        cultural_graph, (source,), death_ticks={"w1": 2}
    )
    q3 = next(
        a
        for a in report.answers
        if a.query_id
        is HistoricalMemoryQueryId.EVENT_KNOWN_ONLY_FROM_STORIES_OR_ARTIFACTS
    )
    assert q3.answer is True, (
        f"{arm_cult}: query_id=event_known_only_from_stories_or_artifacts "
        "expected=true"
    )


def test_arm_narrative_join_has_narrative_edges() -> None:
    arm_id = "am-narrative-join"
    source = HistoricalSourceRef(source_event_id="evt-1")
    graph = build_historical_provenance_graph(
        as_of_tick=2,
        sources=(source,),
        narrative_rows=(
            SimpleNamespace(
                source_event_id="evt-1",
                carrier_agent_id="n1",
                parent_agent_id="w1",
            ),
        ),
        include_narrative_lineage=True,
    )
    assert any(
        edge.edge_kind.value == "narrative_transmitted" for edge in graph.edges
    ), f"{arm_id}: expected narrative_transmitted edges"


def test_no_layer_labels_on_observation_or_belief_field_names() -> None:
    forbidden = {
        "historical_memory_layer",
        "HistoricalMemoryLayer",
        "living_memory",
        "communicative_memory",
        "cultural_memory",
        "assmann_layer",
    }
    names = {field.name for field in fields(Observation)}
    overlap = names & forbidden
    assert not overlap, f"Observation has forbidden layer fields: {overlap}"


@pytest.mark.asyncio
async def test_am_flags_off_hash_stability() -> None:
    _LOG.info("case_id=am_flags_off_traj_hash")
    definition = experiment_am_historical_memory_layers(_base(), max_ticks=3)
    flags_off = _arm(definition, "am-flags-off")
    plain_v4 = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=3),
        v3_capability_flags=V3CapabilityFlags(),
        cultural_feature_provenance=None,
        historical_memory_layers=None,
    )
    v3_scaffolding_profile(flags_off)
    v3_scaffolding_profile(plain_v4)
    run_id = RunId("run-am-flags-off")
    async with await SimulationRunner.from_config(
        plain_v4, run_id=run_id
    ) as runner:
        result_v4 = await runner.run()
    async with await SimulationRunner.from_config(
        flags_off, run_id=run_id
    ) as runner:
        result_off = await runner.run()
    doc_v4 = build_runner_result_document(result=result_v4, config=plain_v4)
    doc_off = build_runner_result_document(result=result_off, config=flags_off)
    assert doc_v4.exact_trajectory_hash == doc_off.exact_trajectory_hash, (
        "am-flags-off: expected hash stability vs plain v4"
    )
    _LOG.info("case_id=am_flags_off_traj_hash status=pass")


def test_matrix_finalize_historical_memory_before_cultural() -> None:
    base = _base()
    both = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=example_historical_memory_layers_spec(),
        population_lifecycle=None,
        new_agent_initialization=None,
        mentorship=None,
    )
    finalized = finalize_matrix_cell_config(both)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V32

    cultural_only = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=None,
        population_lifecycle=None,
        new_agent_initialization=None,
        mentorship=None,
    )
    finalized_al = finalize_matrix_cell_config(cultural_only)
    assert finalized_al.schema_version == RUNNER_SCHEMA_VERSION_V31
