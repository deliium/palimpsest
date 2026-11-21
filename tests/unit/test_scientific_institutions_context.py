# mypy: ignore-errors
"""V4-32 organization context and optional practice-signal composition."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition.models import InternalAgentState
from agents.cognition.organization_concepts import (
    OrganizationConcept,
    OrganizationConceptLedger,
    OrganizationEvidenceChannel,
    OrganizationGoalBelief,
    OrganizationGoalKind,
    OrganizationMemberBelief,
    OrganizationMembershipBasis,
    OrganizationMembershipStatus,
    OrganizationProcedureBelief,
    OrganizationProcedureKind,
    OrganizationRecordBelief,
    OrganizationRecordKind,
    OrganizationRoleBelief,
    OrganizationStatus,
    OrganizationTemporalScope,
)
from agents.models import AgentId
from analysis.organization_detection import (
    detect_organization_candidates,
    detect_organization_candidates_with_contributors,
)
from analysis.organization_evidence import OrganizationWindowEvidence
from analysis.organizations import harvest_organization_rows
from analysis.scientific_institutions_contract import (
    PracticeCoverageStatus,
    PracticeLane,
    PracticeSignalKind,
)
from experiments.scientific_institutions_completed_run import (
    ScientificInstitutionBoundaryInput,
    build_scientific_institution_windows,
)
from experiments.scientific_institutions_context import (
    build_scientific_institution_context,
)
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.clock import Tick
from simulation.fork_checkpoint import (
    FinalizedResearchBoundary,
    FinalizedResearchOwnerSnapshot,
)
from simulation.models import RunId, StochasticIdentity
from simulation.observer_facts import ObjectiveFacts
from simulation.run_control import AgentRuntimeCheckpoint
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    FinalizedTickReceipt,
    RunnerStopPolicy,
    RunnerStopReasonCode,
    SimulationRunnerConfig,
    SimulationRunnerResult,
    V3CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
)
from simulation.runner_serialization import runner_config_fingerprint
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.artifacts import ArtifactKind
from world.effects import ActionCause
from world.events import (
    ArtifactAnnotated,
    ArtifactCreated,
    ExperimentResolved,
    MeasurementTaken,
    OccurrenceContext,
    ProjectContributed,
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
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReading,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

RUN = "run-sci-context"
WORLD = WorldId("world-sci-context")
ENTITY_A = "body-a"
ENTITY_B = "body-b"
AGENT_A = "agent-a"
AGENT_B = "agent-b"
ARTIFACT = "artifact-record-1"
PROJECT = "project-1"
LOCAL = "orgc-0123456789abcdef"
OFFICE = "office-1"
PROCEDURE = "procedure-1"
_INSTRUMENT = EntityId("item-thermometer")


def _config(*, organizations: bool = True):
    body_a = alive_body(ENTITY_A)
    body_b = alive_body(ENTITY_B)
    return SimulationRunnerConfig(
        seed=9,
        stochastic_identity=StochasticIdentity("sci-inst-context"),
        scenario=WorldScenarioSpec(
            world_id=WORLD,
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId(AGENT_A),
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId(AGENT_A)),
            ),
            AgentRunnerSpec(
                agent_id=AgentId(AGENT_B),
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId(AGENT_B)),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=64),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        v4_capability_flags=V4CapabilityFlags(organizations=organizations),
    )


def _concept(
    *,
    last_tick: int,
    member_status: OrganizationMembershipStatus = (
        OrganizationMembershipStatus.PERCEIVED
    ),
    member_scope: OrganizationTemporalScope = OrganizationTemporalScope.ONGOING,
    expires_tick: int | None = None,
    record_anchor: str = ARTIFACT,
) -> OrganizationConcept:
    members = (
        OrganizationMemberBelief(
            member_id=ENTITY_A,
            status=member_status,
            basis=OrganizationMembershipBasis.PARTICIPATION,
            temporal_scope=member_scope,
            first_tick=0,
            last_tick=last_tick,
            strength=0.5,
            channels=(OrganizationEvidenceChannel.OBSERVED,),
            independently_evidenced=True,
            expires_tick=expires_tick,
        ),
        OrganizationMemberBelief(
            member_id=ENTITY_B,
            status=OrganizationMembershipStatus.PERCEIVED,
            basis=OrganizationMembershipBasis.PARTICIPATION,
            temporal_scope=OrganizationTemporalScope.ONGOING,
            first_tick=0,
            last_tick=last_tick,
            strength=0.5,
            channels=(OrganizationEvidenceChannel.OBSERVED,),
            independently_evidenced=True,
        ),
    )
    return OrganizationConcept(
        organization_id=LOCAL,
        owner_id=AgentId(AGENT_A),
        creation_tick=0,
        inception_digest="a" * 64,
        status=(
            OrganizationStatus.DISPUTED
            if member_status is OrganizationMembershipStatus.DISPUTED
            else OrganizationStatus.RECOGNIZED
        ),
        temporal_scope=OrganizationTemporalScope.ONGOING,
        strength=1.0,
        member_evidence_count=2,
        structural_channel_count=3,
        first_tick=0,
        last_tick=last_tick,
        members=members,
        goals=(
            OrganizationGoalBelief(
                anchor_kind=OrganizationGoalKind.COLLECTIVE_PROJECT,
                anchor_id=PROJECT,
                status=OrganizationStatus.RECOGNIZED,
                first_tick=0,
                last_tick=last_tick,
            ),
        ),
        records=(
            OrganizationRecordBelief(
                record_kind=OrganizationRecordKind.ARTIFACT,
                anchor_id=record_anchor,
                integrity=1.0,
                custody_belief="observed",
                first_tick=0,
                last_tick=last_tick,
            ),
        ),
        procedures=(
            OrganizationProcedureBelief(
                procedure_kind=OrganizationProcedureKind.INSTITUTION_CONCEPT,
                anchor_id=PROCEDURE,
                recurrence=2,
                status=OrganizationStatus.RECOGNIZED,
                first_tick=0,
                last_tick=last_tick,
            ),
        ),
        roles=(
            OrganizationRoleBelief(
                office_id=OFFICE,
                function="experimenter",
                context_key="site-1",
                occupant_ids=(ENTITY_A,),
                status=OrganizationStatus.RECOGNIZED,
                first_tick=0,
                last_tick=last_tick,
            ),
        ),
    )


def _checkpoint(
    agent_id: str,
    *,
    concept: OrganizationConcept | None = None,
    replication_ledger: object | None = None,
) -> AgentRuntimeCheckpoint:
    ledger = (
        OrganizationConceptLedger(
            owner_id=AgentId(agent_id),
            concepts=(concept,) if concept is not None else (),
        )
        if concept is not None
        else OrganizationConceptLedger(owner_id=AgentId(agent_id))
    )
    return AgentRuntimeCheckpoint(
        agent_id=AgentId(agent_id),
        status=AgentRuntimeStatus.ACTIVE,
        internal_state=InternalAgentState(owner_id=AgentId(agent_id)),
        last_observation_key=None,
        processed_invocation_count=0,
        finalized_hash_count=0,
        goals=(),
        organization_concepts=ledger,
        replication_ledger=replication_ledger,
    )


def _owner(agent_id: str, entity_id: str, checkpoint: AgentRuntimeCheckpoint):
    return FinalizedResearchOwnerSnapshot(
        owner_id=AgentId(agent_id),
        entity_id=EntityId(entity_id),
        generation_index=0,
        living=True,
        memories=(),
        memory_reconstructions=(),
        memory_access_operations=(),
        beliefs=(),
        belief_histories=(),
        relationship_profiles=(),
        relationship_histories=(),
        runtime_checkpoint=checkpoint,
    )


def _event(
    details: object,
    *,
    tick: int,
    sequence: int = 0,
    actor: str = ENTITY_A,
    schema: int = 22,
) -> WorldEvent:
    request = RequestId(f"req-{tick}-{sequence}")
    return WorldEvent(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id=RUN,
        world_id=WORLD,
        tick=tick,
        sequence=sequence,
        request_id=request,
        resulting_revision=WorldRevision(tick * 10 + sequence + 1),
        schema_version=schema,
        details=details,
        actor_id=EntityId(actor),
        target_id=target_id_for_details(details),
        cause=ActionCause(request, EntityId(actor)),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _receipts(ticks: int, counts: dict[int, int] | None = None):
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
        finalized_tick_receipts=_receipts(ticks, counts),
    )


def _boundary(
    config: SimulationRunnerConfig,
    *,
    tick: int,
    events: tuple[WorldEvent, ...] = (),
    concept: OrganizationConcept | None = None,
    replication_ledger: object | None = None,
) -> ScientificInstitutionBoundaryInput:
    return ScientificInstitutionBoundaryInput(
        boundary=FinalizedResearchBoundary(
            run_id=RunId(RUN),
            boundary_tick=Tick(tick),
            boundary_revision=WorldRevision(tick),
            config_fingerprint=runner_config_fingerprint(config),
            owners=(
                _owner(
                    AGENT_A,
                    ENTITY_A,
                    _checkpoint(
                        AGENT_A,
                        concept=concept,
                        replication_ledger=replication_ledger,
                    ),
                ),
                _owner(AGENT_B, ENTITY_B, _checkpoint(AGENT_B)),
            ),
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
        ),
    )


def _science_events() -> tuple[WorldEvent, ...]:
    return (
        _event(
            ArtifactCreated(
                artifact_id=EntityId(ARTIFACT),
                artifact_kind=ArtifactKind.RECORD,
                author_id=EntityId(ENTITY_A),
                content_revision=0,
                resulting_location_id=EntityId("loc-1"),
            ),
            tick=5,
        ),
        _event(
            ProjectContributed(
                project_id=EntityId(PROJECT),
                actor_id=EntityId(ENTITY_A),
                accepted=True,
                labor_done=1,
                materials_done=0,
            ),
            tick=10,
            sequence=1,
        ),
        _event(
            ExperimentResolved(
                operator="vary_process",
                operand_a_id=EntityId("item-tool-1"),
                process_token="harvest",
                outcome_class="failure",
                delta="none",
                discovery_mode="deliberate",
            ),
            tick=12,
            sequence=2,
        ),
        _event(
            ArtifactAnnotated(
                artifact_id=EntityId(ARTIFACT),
                annotation_revisions=1,
                content_revision=1,
                integrity="intact",
            ),
            tick=14,
            sequence=3,
        ),
    )


def test_positive_context_links_exact_contribution_and_carrier() -> None:
    config = _config()
    events = _science_events()
    boundaries = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=events, concept=_concept(last_tick=31)),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 10: 1, 12: 1, 14: 1}), config, boundaries
    )
    context = build_scientific_institution_context(evidence, boundaries, config)
    window = context.windows[0]
    assert len(window.organizations) == 1
    fact = window.organizations[0]
    assert len(fact.participant_tokens) == 2
    assert fact.links
    execution = [link for link in fact.links if link.execution_token is not None]
    service = [link for link in fact.links if link.service_token is not None]
    assert len(execution) == 1 and len(service) == 1
    assert execution[0].contribution_tick == 10
    assert service[0].carrier_kind is not None
    signals = {row.signal for row in window.supplements}
    assert PracticeSignalKind.EXPERIMENTER in signals
    assert PracticeSignalKind.RECORD_KEEPER in signals
    assert PracticeSignalKind.PROCEDURE in signals
    assert PracticeSignalKind.OFFICE in signals
    assert window.window.lane_status(PracticeLane.ORGANIZATION) is (
        PracticeCoverageStatus.COMPLETE
    )
    assert window.window.lane_status(PracticeLane.RECORD) is (
        PracticeCoverageStatus.COMPLETE
    )


def test_stale_contribution_and_reobservation_do_not_date_a_witness() -> None:
    config = _config()
    events = _science_events()
    late = _event(
        ProjectContributed(
            project_id=EntityId(PROJECT),
            actor_id=EntityId(ENTITY_A),
            accepted=True,
            labor_done=1,
            materials_done=0,
        ),
        tick=40,
        sequence=4,
    )
    boundaries = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=events, concept=_concept(last_tick=31)),
        _boundary(
            config,
            tick=64,
            events=(*events, late),
            concept=_concept(last_tick=63),
        ),
    )
    evidence = build_scientific_institution_windows(
        _result(64, {5: 1, 10: 1, 12: 1, 14: 1, 40: 1}), config, boundaries
    )
    context = build_scientific_institution_context(evidence, boundaries, config)
    first = context.windows[0]
    assert len(first.organizations) == 1
    assert first.organizations[0].links
    second = context.windows[1]
    assert second.organizations[0].links == ()


def test_later_than_action_contribution_does_not_justify_execution() -> None:
    config = _config()
    events = (
        _event(
            ArtifactCreated(
                artifact_id=EntityId(ARTIFACT),
                artifact_kind=ArtifactKind.RECORD,
                author_id=EntityId(ENTITY_A),
                content_revision=0,
                resulting_location_id=EntityId("loc-1"),
            ),
            tick=5,
        ),
        _event(
            ExperimentResolved(
                operator="vary_process",
                operand_a_id=EntityId("item-tool-1"),
                process_token="harvest",
                outcome_class="failure",
                delta="none",
                discovery_mode="deliberate",
            ),
            tick=12,
            sequence=1,
        ),
        _event(
            ProjectContributed(
                project_id=EntityId(PROJECT),
                actor_id=EntityId(ENTITY_A),
                accepted=True,
                labor_done=1,
                materials_done=0,
            ),
            tick=13,
            sequence=2,
        ),
        _event(
            ArtifactAnnotated(
                artifact_id=EntityId(ARTIFACT),
                annotation_revisions=1,
                content_revision=1,
                integrity="intact",
            ),
            tick=14,
            sequence=3,
        ),
    )
    boundaries = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=events, concept=_concept(last_tick=31)),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 12: 1, 13: 1, 14: 1}), config, boundaries
    )
    context = build_scientific_institution_context(evidence, boundaries, config)
    links = context.windows[0].organizations[0].links
    assert all(link.execution_token is None for link in links)
    assert any(link.service_token is not None for link in links)


def test_expired_temporary_membership_is_removed() -> None:
    config = _config()
    events = _science_events()
    temporary = _concept(
        last_tick=31,
        member_scope=OrganizationTemporalScope.TEMPORARY,
        expires_tick=20,
    )
    boundaries = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=events, concept=temporary),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 10: 1, 12: 1, 14: 1}), config, boundaries
    )
    context = build_scientific_institution_context(evidence, boundaries, config)
    fact = context.windows[0].organizations[0]
    assert len(fact.participant_tokens) == 1
    assert fact.links == ()


def test_disputed_and_expired_membership_are_not_participants() -> None:
    config = _config()
    events = _science_events()
    disputed = _concept(
        last_tick=31,
        member_status=OrganizationMembershipStatus.DISPUTED,
    )
    boundaries = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=events, concept=disputed),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 10: 1, 12: 1, 14: 1}), config, boundaries
    )
    context = build_scientific_institution_context(evidence, boundaries, config)
    fact = context.windows[0].organizations[0]
    assert len(fact.participant_tokens) == 1
    assert fact.links == ()


def test_unrelated_record_anchor_breaks_carrier_service_link() -> None:
    config = _config()
    events = _science_events()
    boundaries = (
        _boundary(config, tick=0),
        _boundary(
            config,
            tick=32,
            events=events,
            concept=_concept(last_tick=31, record_anchor="artifact-other"),
        ),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 10: 1, 12: 1, 14: 1}), config, boundaries
    )
    context = build_scientific_institution_context(evidence, boundaries, config)
    fact = context.windows[0].organizations[0]
    assert any(link.execution_token is not None for link in fact.links)
    assert all(link.service_token is None for link in fact.links)


def test_teacher_supplement_requires_both_linked_participants() -> None:
    config = _config()
    events = _science_events()
    boundaries = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=events, concept=_concept(last_tick=31)),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 10: 1, 12: 1, 14: 1}), config, boundaries
    )
    audit = SimpleNamespace(
        store=SimpleNamespace(value="advice"),
        agent_id=AgentId(AGENT_B),
        source_agent_id=AgentId(AGENT_A),
        tick=20,
    )
    context = build_scientific_institution_context(
        evidence, boundaries, config, teaching_audits=(audit,)
    )
    signals = {
        row.signal for row in context.windows[0].supplements
    }
    assert PracticeSignalKind.TEACHER in signals
    foreign = SimpleNamespace(
        store=SimpleNamespace(value="advice"),
        agent_id=AgentId("agent-foreign"),
        source_agent_id=AgentId(AGENT_A),
        tick=21,
    )
    context = build_scientific_institution_context(
        evidence, boundaries, config, teaching_audits=(foreign,)
    )
    assert PracticeSignalKind.TEACHER not in {
        row.signal for row in context.windows[0].supplements
    }


def test_disabled_optional_channels_are_unavailable() -> None:
    config = _config()
    events = _science_events()
    boundaries = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=events, concept=_concept(last_tick=31)),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 10: 1, 12: 1, 14: 1}), config, boundaries
    )
    context = build_scientific_institution_context(
        evidence, boundaries, config, teaching_audits=None
    )
    window = context.windows[0]
    assert window.window.lane_status(PracticeLane.TEACHING) is (
        PracticeCoverageStatus.UNAVAILABLE
    )
    assert window.window.lane_status(PracticeLane.REPLICATION) is (
        PracticeCoverageStatus.UNAVAILABLE
    )
    configured_empty = build_scientific_institution_context(
        evidence, boundaries, config, teaching_audits=()
    )
    assert configured_empty.windows[0].window.lane_status(
        PracticeLane.TEACHING
    ) is PracticeCoverageStatus.COMPLETE


def test_shared_instrument_requires_two_linked_actors() -> None:
    config = _config()
    before = _instrument_state()
    first = _event(
        MeasurementTaken(
            reading=_reading("reading-1"),
            instrument_before=before,
            instrument_after=replace(before, damage_milli=10),
        ),
        tick=20,
        sequence=1,
        actor=ENTITY_A,
        schema=28,
    )
    second = _event(
        MeasurementTaken(
            reading=_reading("reading-2"),
            instrument_before=replace(before, damage_milli=10),
            instrument_after=replace(before, damage_milli=20),
        ),
        tick=21,
        sequence=2,
        actor=ENTITY_B,
        schema=28,
    )
    events = (*_science_events(), first, second)
    boundaries = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=events, concept=_concept(last_tick=31)),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 10: 1, 12: 1, 14: 1, 20: 1, 21: 1}),
        config,
        boundaries,
    )
    context = build_scientific_institution_context(evidence, boundaries, config)
    shared = [
        row
        for row in context.windows[0].supplements
        if row.signal is PracticeSignalKind.SHARED_INSTRUMENT
    ]
    assert len(shared) == 1
    assert len(shared[0].actor_tokens) == 2


def test_organizations_disabled_marks_organization_unavailable() -> None:
    config = _config(organizations=False)
    events = _science_events()
    boundaries = (
        _boundary(config, tick=0),
        _boundary(config, tick=32, events=events, concept=_concept(last_tick=31)),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 10: 1, 12: 1, 14: 1}), config, boundaries
    )
    context = build_scientific_institution_context(evidence, boundaries, config)
    window = context.windows[0]
    assert window.organizations == ()
    assert window.window.lane_status(PracticeLane.ORGANIZATION) is (
        PracticeCoverageStatus.UNAVAILABLE
    )


def _instrument_state() -> InstrumentState:
    return InstrumentState(
        item_id=_INSTRUMENT,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=MeasurementUnit(MeasurementUnitKind.CELSIUS),
        nominal_step_milli=1000,
        intrinsic_bias_milli=0,
        base_error_bound_milli=0,
        damage_milli=0,
        correction_milli=0,
        calibration_state=CalibrationState.NEVER_ADJUSTED,
        calibration_revision=0,
    )


def _reading(reading_id: str) -> MeasurementReading:
    return MeasurementReading(
        reading_id=reading_id,
        instrument_id=_INSTRUMENT,
        target_id=EntityId("loc-1"),
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=MeasurementUnit(MeasurementUnitKind.CELSIUS),
        sample_tick=20,
        nominal_division_milli=1000,
        displayed_scalar_milli=15000,
    )


def test_legacy_detector_output_is_unchanged_by_attribution() -> None:
    ledger = OrganizationConceptLedger(
        owner_id=AgentId(AGENT_A),
        concepts=(_concept(last_tick=31),),
    )
    rows = harvest_organization_rows((ledger,))
    window = OrganizationWindowEvidence(
        window_index=0,
        start_tick=0,
        end_tick=31,
        owner_rows=rows,
        known_person_ids=(ENTITY_A, ENTITY_B),
        lane_presence=(),
    )
    legacy = detect_organization_candidates((window,))
    attributed = detect_organization_candidates_with_contributors((window,))
    assert attributed.result == legacy
    assert attributed.contributors == (
        (0, legacy.candidates[0].candidate_key, AGENT_A, LOCAL),
    )


def test_replication_child_execution_counted_separately(monkeypatch) -> None:
    from analysis.replication_rows import (
        ReplicationAttemptFact,
        ReplicationDesignFact,
        ReplicationExecutionFact,
        ReplicationFacts,
        ReplicationSelectorFact,
    )

    config = _config()
    events = _science_events()
    collaboration = SimpleNamespace(
        status=SimpleNamespace(value="accepted"),
        delivery_event_id="evt-18-4",
        inviter_entity_id=ENTITY_B,
        participants=(
            SimpleNamespace(
                act=SimpleNamespace(value="participate"),
                tick=18,
            ),
        ),
    )
    delivery = _event(
        ExperimentResolved(
            operator="vary_process",
            operand_a_id=EntityId("item-tool-1"),
            process_token="harvest",
            outcome_class="success",
            delta="none",
            discovery_mode="deliberate",
        ),
        tick=18,
        sequence=4,
    )
    child = _event(
        ExperimentResolved(
            operator="vary_process",
            operand_a_id=EntityId("item-tool-1"),
            process_token="harvest",
            outcome_class="success",
            delta="none",
            discovery_mode="deliberate",
        ),
        tick=20,
        sequence=5,
        actor=ENTITY_A,
    )
    all_events = (*events, delivery, child)
    ledger = SimpleNamespace(
        collaborations=(collaboration,),
        attempts=(),
        designs=(),
    )
    boundaries = (
        _boundary(config, tick=0),
        _boundary(
            config,
            tick=32,
            events=all_events,
            concept=_concept(last_tick=31),
            replication_ledger=ledger,
        ),
    )
    evidence = build_scientific_institution_windows(
        _result(32, {5: 1, 10: 1, 12: 1, 14: 1, 18: 1, 20: 1}),
        config,
        boundaries,
    )
    design = ReplicationDesignFact(
        design_token="rpd-" + "a" * 32,
        source_design_digest="d" * 64,
        origin_token="rpo-" + "a" * 32,
        parent_design_token=None,
        source_hypothesis_token="rph-" + "a" * 32,
        source_trial_token="rpt-" + "a" * 32,
        created_tick=1,
        operator="vary_process",
        process_token="harvest",
        operand_a_selector=ReplicationSelectorFact(
            family="item", kind="tool", binding_mode="same_kind"
        ),
        operand_b_selector=None,
        predicted_outcome="success",
    )
    attempt = ReplicationAttemptFact(
        attempt_token="rpa-" + "a" * 32,
        participant_token="rpp-" + "a" * 32,
        design_token=design.design_token,
        source_trial_token=design.source_trial_token,
        collaboration_token="rpc-" + "a" * 32,
        hypothesis_token="rph-" + "b" * 32,
        request_tick=16,
        submission_tick=20,
        observation_tick=20,
        operand_a_token=None,
        operand_b_token=None,
        condition_snapshot=(),
        condition_comparison="same",
        state="observed",
        result_root_token=None,
    )
    execution = ReplicationExecutionFact(
        execution_token="rpe-" + "a" * 32,
        result_root_token="rpt-" + "b" * 32,
        participant_token="rpp-" + "b" * 32,
        execution_tick=20,
        operator="vary_process",
        process_token="harvest",
        operand_a_token=None,
        operand_b_token=None,
        outcome="success",
    )

    def _fake_replication_facts(**_kwargs):
        return ReplicationFacts(
            designs=(design,),
            attempts=(attempt,),
            executions=(execution,),
        )

    monkeypatch.setattr(
        "experiments.scientific_institutions_context.replication_facts",
        _fake_replication_facts,
    )
    matched = build_scientific_institution_context(
        evidence, boundaries, config
    )
    signals = [
        row
        for row in matched.windows[0].supplements
        if row.signal is PracticeSignalKind.REPLICATION_EXPECTATION
    ]
    assert len(signals) >= 2
    assert any(row.tick == 20 for row in signals)

    unmatched_attempt = ReplicationAttemptFact(
        attempt_token=attempt.attempt_token,
        participant_token=attempt.participant_token,
        design_token=attempt.design_token,
        source_trial_token=attempt.source_trial_token,
        collaboration_token=attempt.collaboration_token,
        hypothesis_token=attempt.hypothesis_token,
        request_tick=16,
        submission_tick=None,
        observation_tick=16,
        operand_a_token=None,
        operand_b_token=None,
        condition_snapshot=(),
        condition_comparison="same",
        state="proposed",
        result_root_token=None,
    )

    def _unmatched(**_kwargs):
        return ReplicationFacts(
            designs=(design,),
            attempts=(unmatched_attempt,),
            executions=(),
        )

    monkeypatch.setattr(
        "experiments.scientific_institutions_context.replication_facts",
        _unmatched,
    )
    missing_child = build_scientific_institution_context(
        evidence, boundaries, config
    )
    unmatched_signals = [
        row
        for row in missing_child.windows[0].supplements
        if row.signal is PracticeSignalKind.REPLICATION_EXPECTATION
    ]
    assert unmatched_signals
    assert all(row.tick != 20 for row in unmatched_signals)
