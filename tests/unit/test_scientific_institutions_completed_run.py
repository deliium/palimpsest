# mypy: ignore-errors
"""V4-32 completed-run projection: exact boundaries, receipts, and carriers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from analysis.scientific_institutions_contract import (
    PracticeCarrierKind,
    PracticeCoverageStatus,
    PracticeLane,
    ScientificInstitutionsError,
)
from experiments.scientific_institutions_completed_run import (
    ScientificInstitutionBoundaryInput,
    build_scientific_institution_windows,
)
from simulation.clock import Tick
from simulation.fork_checkpoint import (
    FinalizedResearchBoundary,
    FinalizedResearchOwnerSnapshot,
)
from simulation.models import RunId, StochasticIdentity
from simulation.observer_facts import ObjectiveFacts
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V34,
    AgentCognitionSpec,
    AgentRunnerSpec,
    FinalizedTickReceipt,
    RunnerStopPolicy,
    RunnerStopReasonCode,
    SimulationRunnerConfig,
    SimulationRunnerResult,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
    example_knowledge_repositories_spec,
)
from simulation.runner_serialization import runner_config_fingerprint
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    InformationArtifact,
    RecordIntegrity,
)
from world.effects import ActionCause
from world.events import (
    ArtifactAnnotated,
    ArtifactCreated,
    ArtifactDestroyed,
    ExperimentResolved,
    OccurrenceContext,
    RepositoryEstablished,
    RepositoryMemberDeposited,
    RepositoryMemberRetrieved,
    WorldEvent,
    target_id_for_details,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import default_physical_rules
from world.repositories import (
    KnowledgeRepository,
    RepositoryAccessMode,
    RepositoryStatus,
)

pytestmark = pytest.mark.unit

RUN = "run-sci-inst"
WORLD = WorldId("world-sci-inst")
ENTITY = "body-a"
ARTIFACT = "artifact-record-1"
REPOSITORY = "repo-1"


def _config(*, seed: int = 9, durable: bool = True, repo: bool = True):
    body = alive_body(ENTITY)
    return SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=StochasticIdentity(f"sci-inst-{seed}"),
        scenario=WorldScenarioSpec(
            world_id=WORLD,
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-a"),
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=64),
        schema_version=RUNNER_SCHEMA_VERSION_V34,
        v3_capability_flags=V3CapabilityFlags(
            cultural_historical_memory=durable or repo
        ),
        cultural_feature_provenance=(
            example_cultural_feature_provenance_spec() if durable or repo else None
        ),
        durable_records=example_durable_records_spec() if durable else None,
        knowledge_repositories=(
            example_knowledge_repositories_spec() if repo else None
        ),
    )


def _receipt(ticks: int, counts: dict[int, int] | None = None):
    mapping = counts or {}
    return tuple(
        FinalizedTickReceipt(
            tick=tick,
            resulting_tick=tick + 1,
            base_revision=tick,
            resulting_revision=tick + 1,
            resolutions=(),
            objective_state_hash=f"state-{tick}",
            event_count=mapping.get(tick, 0),
        )
        for tick in range(ticks)
    )


def _result(ticks: int, counts: dict[int, int] | None = None):
    return SimulationRunnerResult(
        run_id=RunId(RUN),
        ticks_committed=ticks,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        finalized_tick_receipts=_receipt(ticks, counts),
    )


def _owner() -> FinalizedResearchOwnerSnapshot:
    return FinalizedResearchOwnerSnapshot(
        owner_id=AgentId("agent-a"),
        entity_id=EntityId(ENTITY),
        generation_index=0,
        living=True,
        memories=(),
        memory_reconstructions=(),
        memory_access_operations=(),
        beliefs=(),
        belief_histories=(),
        relationship_profiles=(),
        relationship_histories=(),
    )


def _event(
    details: object,
    *,
    tick: int,
    sequence: int = 0,
    actor: str = ENTITY,
    event_id: str | None = None,
) -> WorldEvent:
    request = RequestId(f"req-{tick}-{sequence}")
    return WorldEvent(
        event_id=EventId(event_id or f"evt-{tick}-{sequence}"),
        run_id=RUN,
        world_id=WORLD,
        tick=tick,
        sequence=sequence,
        request_id=request,
        resulting_revision=WorldRevision(tick * 10 + sequence + 1),
        schema_version=22,
        details=details,
        actor_id=EntityId(actor),
        target_id=target_id_for_details(details),
        cause=ActionCause(request, EntityId(actor)),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _experiment(
    *,
    mode: str = "deliberate",
    operator: str = "vary_process",
    outcome: str = "failure",
) -> ExperimentResolved:
    return ExperimentResolved(
        operator=operator,
        operand_a_id=EntityId("item-tool-1"),
        process_token="harvest",
        outcome_class=outcome,
        delta="none",
        discovery_mode=mode,
    )


def _created(*, tick: int = 0) -> ArtifactCreated:
    return ArtifactCreated(
        artifact_id=EntityId(ARTIFACT),
        artifact_kind=ArtifactKind.RECORD,
        author_id=EntityId(ENTITY),
        content_revision=0,
        resulting_location_id=EntityId("loc-1"),
    )


def _artifact(
    *, integrity: RecordIntegrity = RecordIntegrity.INTACT
) -> InformationArtifact:
    return InformationArtifact(
        artifact_id=EntityId(ARTIFACT),
        kind=ArtifactKind.RECORD,
        author_id=EntityId(ENTITY),
        created_tick=0,
        content=ArtifactContent(),
        location_id=EntityId("loc-1"),
        record_genre=DurableRecordGenre.INSTRUCTION,
        integrity=integrity,
    )


def _repository(*, members: tuple[str, ...] = (ARTIFACT,)) -> KnowledgeRepository:
    return KnowledgeRepository(
        repository_id=EntityId(REPOSITORY),
        location_id=EntityId("loc-1"),
        founder_ids=(EntityId(ENTITY),),
        established_tick=0,
        access_mode=RepositoryAccessMode.OPEN,
        status=RepositoryStatus.INTACT,
        member_artifact_ids=tuple(EntityId(item) for item in members),
    )


def _boundary(
    config: SimulationRunnerConfig,
    *,
    tick: int,
    events: tuple[WorldEvent, ...] = (),
    artifacts: tuple[InformationArtifact, ...] = (),
    repositories: tuple[KnowledgeRepository, ...] = (),
    owner: FinalizedResearchOwnerSnapshot | None = None,
) -> ScientificInstitutionBoundaryInput:
    return ScientificInstitutionBoundaryInput(
        boundary=FinalizedResearchBoundary(
            run_id=RunId(RUN),
            boundary_tick=Tick(tick),
            boundary_revision=WorldRevision(tick),
            config_fingerprint=runner_config_fingerprint(config),
            owners=(owner or _owner(),),
            events=events,
            resource_holdings=(),
        ),
        inventory=ObjectiveFacts(
            run_id=RUN,
            world_id=WORLD.value,
            tick=tick,
            revision=tick,
            locations=(),
            bodies=(),
            items=(),
            resources=(),
            weather=(),
            registrations=(),
            artifacts=artifacts,
            repositories=repositories,
        ),
    )


def test_positive_two_windows_project_receipts_and_surviving_record() -> None:
    config = _config()
    created = _event(_created(), tick=5)
    experiment = _event(_experiment(), tick=6, sequence=1)
    annotated = _event(
        ArtifactAnnotated(
            artifact_id=EntityId(ARTIFACT),
            annotation_revisions=1,
            content_revision=1,
            integrity="intact",
        ),
        tick=40,
    )
    second = _event(_experiment(), tick=41, sequence=1)
    evidence = build_scientific_institution_windows(
        _result(64, {5: 1, 6: 1, 40: 1, 41: 1}),
        config,
        (
            _boundary(config, tick=0),
            _boundary(
                config,
                tick=32,
                events=(created, experiment),
                artifacts=(_artifact(),),
            ),
            _boundary(
                config,
                tick=64,
                events=(created, experiment, annotated, second),
                artifacts=(_artifact(),),
            ),
        ),
    )
    assert len(evidence.windows) == 2
    first, second_window = evidence.windows
    assert first.window.complete is True
    assert first.window.lane_status(PracticeLane.EXECUTION) is (
        PracticeCoverageStatus.COMPLETE
    )
    assert [row.tick for row in first.executions] == [6]
    assert [row.action.value for row in first.carriers] == ["create"]
    assert first.carriers[0].carrier_kind is PracticeCarrierKind.RECORD
    assert any(
        row.carrier_kind is PracticeCarrierKind.RECORD
        for row in first.surviving_carriers
    )
    assert [row.tick for row in second_window.executions] == [41]
    assert [row.action.value for row in second_window.carriers] == ["annotate"]
    assert any(
        row.carrier_kind is PracticeCarrierKind.RECORD
        for row in second_window.surviving_carriers
    )


def test_wrong_run_or_config_is_rejected() -> None:
    config = _config()
    other = _config(seed=10)
    with pytest.raises(ScientificInstitutionsError):
        build_scientific_institution_windows(
            _result(32),
            config,
            (_boundary(other, tick=0),),
        )
    broken = _boundary(config, tick=0)
    broken = ScientificInstitutionBoundaryInput(
        boundary=replace(broken.boundary, run_id=RunId("run-other")),
        inventory=broken.inventory,
    )
    with pytest.raises(ScientificInstitutionsError):
        build_scientific_institution_windows(_result(32), config, (broken,))


def test_same_event_id_with_changed_hash_is_rejected() -> None:
    config = _config()
    first = _event(_experiment(), tick=5, event_id="evt-shared")
    changed = _event(
        _experiment(operator="combine"), tick=5, event_id="evt-shared"
    )
    with pytest.raises(ScientificInstitutionsError):
        build_scientific_institution_windows(
            _result(64, {5: 1}),
            config,
            (
                _boundary(config, tick=0),
                _boundary(config, tick=32, events=(first,)),
                _boundary(config, tick=64, events=(changed,)),
            ),
        )


def test_tick_zero_bootstrap_baseline_is_excluded_from_facts() -> None:
    config = _config()
    bootstrap = _event(_created(), tick=0)
    evidence = build_scientific_institution_windows(
        _result(32, {0: 1}),
        config,
        (
            _boundary(config, tick=0),
            _boundary(
                config,
                tick=32,
                events=(bootstrap,),
                artifacts=(_artifact(),),
            ),
        ),
        baseline_events=(bootstrap,),
    )
    window = evidence.windows[0]
    assert window.carriers == ()
    assert window.window.lane_status(PracticeLane.CARRIER) is (
        PracticeCoverageStatus.COMPLETE
    )


def test_missing_endpoint_is_unavailable_and_has_no_facts() -> None:
    config = _config()
    experiment = _event(_experiment(), tick=40)
    evidence = build_scientific_institution_windows(
        _result(64, {40: 1}),
        config,
        (
            _boundary(config, tick=0),
            _boundary(config, tick=64, events=(experiment,)),
        ),
    )
    assert [item.window.window_index for item in evidence.windows] == [0, 1]
    for window in evidence.windows:
        assert window.window.lane_status(PracticeLane.EXECUTION) is (
            PracticeCoverageStatus.UNAVAILABLE
        )
        assert window.executions == ()
        assert window.carriers == ()


def test_complete_empty_window_is_distinct_from_absence() -> None:
    config = _config()
    evidence = build_scientific_institution_windows(
        _result(32),
        config,
        (_boundary(config, tick=0), _boundary(config, tick=32)),
    )
    window = evidence.windows[0]
    assert window.window.complete is True
    assert window.window.lane_status(PracticeLane.EXECUTION) is (
        PracticeCoverageStatus.COMPLETE
    )
    assert window.executions == ()
    assert window.carriers == ()
    assert window.surviving_carriers == ()


def test_earlier_windows_do_not_change_when_a_future_boundary_is_added() -> None:
    config = _config()
    experiment = _event(_experiment(), tick=5)
    later = _event(_experiment(), tick=40)
    prefix_inputs = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=(experiment,)),
    )
    full_inputs = (
        *prefix_inputs,
        _boundary(
            config,
            tick=64,
            events=(experiment, later),
        ),
    )
    short = build_scientific_institution_windows(
        _result(32, {5: 1}), config, prefix_inputs
    )
    long = build_scientific_institution_windows(
        _result(64, {5: 1, 40: 1}), config, full_inputs
    )
    assert short.windows[0] == long.windows[0]


def test_accidental_discovery_is_not_a_deliberate_execution() -> None:
    config = _config()
    accidental = _event(_experiment(mode="accidental"), tick=5)
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1}),
        config,
        (
            _boundary(config, tick=0),
            _boundary(config, tick=32, events=(accidental,)),
        ),
    )
    assert evidence.windows[0].executions == ()


def test_duplicate_event_id_inside_one_boundary_is_rejected() -> None:
    config = _config()
    first = _event(_experiment(), tick=5, event_id="evt-dup")
    second = _event(_experiment(), tick=6, sequence=1, event_id="evt-dup")
    with pytest.raises(ScientificInstitutionsError):
        build_scientific_institution_windows(
            _result(32, {5: 1, 6: 1}),
            config,
            (
                _boundary(config, tick=0),
                _boundary(config, tick=32, events=(first, second)),
            ),
        )


def test_unmapped_actor_is_rejected() -> None:
    config = _config()
    event = _event(_experiment(), tick=5, actor="entity-unknown")
    with pytest.raises(ScientificInstitutionsError):
        build_scientific_institution_windows(
            _result(32, {5: 1}),
            config,
            (
                _boundary(config, tick=0),
                _boundary(config, tick=32, events=(event,)),
            ),
        )


def test_destroyed_and_opaque_records_never_survive() -> None:
    config = _config()
    created = _event(_created(), tick=5)
    destroyed = _event(
        ArtifactDestroyed(
            artifact_id=EntityId(ARTIFACT),
            artifact_kind=ArtifactKind.RECORD,
            content_revision=2,
            tombstone=True,
        ),
        tick=6,
        sequence=1,
    )
    opaque = _event(
        ArtifactAnnotated(
            artifact_id=EntityId("artifact-opaque"),
            annotation_revisions=1,
            content_revision=1,
            integrity="intact",
        ),
        tick=7,
        sequence=2,
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 6: 1, 7: 1}),
        config,
        (
            _boundary(config, tick=0),
            _boundary(
                config,
                tick=32,
                events=(created, destroyed, opaque),
                artifacts=(_artifact(integrity=RecordIntegrity.DESTROYED),),
            ),
        ),
    )
    window = evidence.windows[0]
    assert [row.action.value for row in window.carriers] == ["create"]
    assert window.surviving_carriers == ()


def test_repository_member_service_is_typed_and_survives_when_listed() -> None:
    config = _config()
    established = _event(
        RepositoryEstablished(
            repository_id=EntityId(REPOSITORY),
            location_id=EntityId("loc-1"),
            structure_id=None,
            founder_ids=(EntityId(ENTITY),),
            access_mode="open",
            established_tick=2,
        ),
        tick=2,
    )
    deposited = _event(
        RepositoryMemberDeposited(
            repository_id=EntityId(REPOSITORY),
            artifact_id=EntityId(ARTIFACT),
            member_count=1,
            actor_id=EntityId(ENTITY),
        ),
        tick=6,
        sequence=1,
    )
    retrieved = _event(
        RepositoryMemberRetrieved(
            repository_id=EntityId(REPOSITORY),
            artifact_id=EntityId(ARTIFACT),
            member_count=0,
            actor_id=EntityId(ENTITY),
            hold=False,
        ),
        tick=7,
        sequence=2,
    )
    evidence = build_scientific_institution_windows(
        _result(32, {2: 1, 6: 1, 7: 1}),
        config,
        (
            _boundary(config, tick=0),
            _boundary(
                config,
                tick=32,
                events=(established, deposited, retrieved),
                artifacts=(_artifact(),),
                repositories=(_repository(),),
            ),
        ),
    )
    window = evidence.windows[0]
    actions = [row.action.value for row in window.carriers]
    assert actions == ["deposit", "retrieve"]
    assert all(
        row.carrier_kind is PracticeCarrierKind.REPOSITORY_MEMBER
        for row in window.carriers
    )
    assert any(
        row.carrier_kind is PracticeCarrierKind.REPOSITORY_MEMBER
        for row in window.surviving_carriers
    )


def test_receipt_event_count_mismatch_is_rejected() -> None:
    config = _config()
    with pytest.raises(ScientificInstitutionsError):
        build_scientific_institution_windows(
            _result(32, {5: 2}),
            config,
            (
                _boundary(config, tick=0),
                _boundary(config, tick=32, events=(_event(_experiment(), tick=5),)),
            ),
        )
