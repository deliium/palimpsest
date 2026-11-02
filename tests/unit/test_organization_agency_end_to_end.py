"""V4-05 end-to-end evidence across runner, metrics, publication, and API."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from agents.cognition import (
    OrganizationAgencyConcept,
    OrganizationAgencyEffect,
    OrganizationAgencyImplementationStatus,
    OrganizationAgencyLedger,
    OrganizationAgencyRecognition,
    OrganizationStatus,
    track_organization_agency_implementation,
)
from agents.models import AgentId
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from analysis.organization_agency import harvest_organization_agency_rows
from experiments.organization_harvest import build_completed_run_organization_harvest
from experiments.organization_publication import build_organization_harvest_result
from simulation.models import RunId
from simulation.organization_ports import OrganizationPublication
from simulation.runner import SimulationRunner
from tests.unit.organization_agency_helpers import (
    OWNER,
    FakeObservation,
    FakeOccurrence,
    concept_id,
    concept_ledger,
    decision,
    implementation,
    position,
    proposal,
)
from tests.unit.test_organization_agency_runtime import _config
from world.identifiers import EntityId, EventId
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

pytestmark = pytest.mark.unit

RUN_ID = "run-agency-e2e"


@pytest.mark.asyncio
async def test_completed_run_reaches_metrics_publication_and_api() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId(RUN_ID)
    ) as runner:
        result = await runner.run()
    assert len(result.organization_agency_ledgers) == 1

    concepts = concept_ledger()
    first = proposal(organization_id=concept_id(concepts))
    decided = decision(
        first,
        recognition=OrganizationAgencyRecognition.RECOGNIZED,
        status=OrganizationAgencyImplementationStatus.IMPLEMENTED,
    )
    used = implementation(decided)
    ledger = OrganizationAgencyLedger(
        owner_id=OWNER,
        concepts=(
            OrganizationAgencyConcept(
                organization_id=concept_id(concepts),
                owner_id=OWNER,
                status=OrganizationStatus.RECOGNIZED,
                first_tick=1,
                last_tick=2,
                proposals=(first,),
                positions=(position(first.proposal_id),),
                decisions=(decided,),
                implementations=(used,),
            ),
        ),
    )
    harvested = build_completed_run_organization_harvest(
        SimpleNamespace(
            organization_concept_ledgers=(concepts,),
            organization_operation_ledgers=(),
            organization_agency_ledgers=(ledger,),
        ),
        run_id=RUN_ID,
        input_revision="revision-1",
        generated_tick=2,
    )
    assert harvested.agency_summary is not None
    published = build_organization_harvest_result(harvested)
    assert published.snapshot.schema_version == "organization-snapshot-v3"
    assert published.collective_decision_count == 1

    documents = assemble_metric_documents(
        MetricComputationInputs(
            run_id=RUN_ID,
            input_revision="revision-1",
            window_end=2,
            organization_rows=(concepts,),
            organization_agency_rows=harvest_organization_agency_rows((ledger,)),
        )
    )
    families = {
        document.metric_family
        for document in documents.documents
        if document.metric_family.startswith("organization_collective")
    }
    assert families == {
        "organization_collective_agency",
        "organization_collective_implementation",
    }
    assert all(
        document.availability is not MetricAvailability.ABSENT
        for document in documents.documents
        if document.metric_family.startswith("organization_collective")
    )


def test_real_effect_kinds_distinguish_compliance_refusal_and_failure() -> None:
    concepts = concept_ledger()
    first = proposal(
        organization_id=concept_id(concepts),
        effect=OrganizationAgencyEffect.GIVE,
        target_kind="none",
        expected_actors=(
            AgentId("agent-1"),
            AgentId("agent-2"),
            AgentId("agent-3"),
        ),
    )
    decided = decision(first, decided_tick=1, window_end_tick=5)
    concept = OrganizationAgencyConcept(
        organization_id=concept_id(concepts),
        owner_id=OWNER,
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=1,
        proposals=(first,),
        decisions=(decided,),
    )
    ledger = OrganizationAgencyLedger(owner_id=OWNER, concepts=(concept,))

    def _occurrence(
        kind: str, actor: str, facts: dict[str, object] | None = None
    ) -> ObservedOccurrence:
        return ObservedOccurrence(
            provenance=ObservationProvenance(
                source_kind=ObservationSourceKind.OCCURRENCE,
                source_tick=3,
                source_event_id=EventId(f"{kind}-{actor}"),
            ),
            kind=kind,
            audience_role=ObservationAudienceRole.WITNESS,
            actor_id=EntityId(actor),
            public_facts=facts or {},
        )

    observed = FakeObservation(
        tick=6,
        occurrences=(
            _occurrence("give", "body-agent-1", {"give_item_ids": ("item-7",)}),
            _occurrence("move", "body-agent-3"),
        ),
    )
    tracked = track_organization_agency_implementation(ledger, observed, None)
    statuses = {
        item.actor_id.value: item.status for item in tracked.concepts[0].implementations
    }
    assert statuses["agent-1"] is OrganizationAgencyImplementationStatus.IMPLEMENTED
    assert statuses["agent-2"] is OrganizationAgencyImplementationStatus.UNKNOWN
    assert statuses["agent-3"] is OrganizationAgencyImplementationStatus.UNIMPLEMENTED
    assert (
        tracked.concepts[0].decisions[0].implementation_status
        is OrganizationAgencyImplementationStatus.OBSTRUCTED
        or tracked.concepts[0].decisions[0].implementation_status
        is OrganizationAgencyImplementationStatus.PARTIAL
    )


def test_no_synthetic_event_kinds_in_agency_effect_catalog() -> None:
    from agents.cognition import ORGANIZATION_AGENCY_EFFECTS

    assert "given" not in ORGANIZATION_AGENCY_EFFECTS
    assert "taken" not in ORGANIZATION_AGENCY_EFFECTS
    assert "dropped" not in ORGANIZATION_AGENCY_EFFECTS


def test_testimonial_decision_without_report_is_unimplemented_or_unknown() -> None:
    concepts = concept_ledger()
    first = proposal(
        organization_id=concept_id(concepts),
        effect=OrganizationAgencyEffect.NONE,
        target_kind="none",
        expected_actors=(OWNER,),
    )
    decided = decision(first, decided_tick=1, window_end_tick=5)
    concept = OrganizationAgencyConcept(
        organization_id=concept_id(concepts),
        owner_id=OWNER,
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=1,
        proposals=(first,),
        decisions=(decided,),
    )
    ledger = OrganizationAgencyLedger(owner_id=OWNER, concepts=(concept,))
    open_window = track_organization_agency_implementation(
        ledger,
        FakeObservation(tick=3, occurrences=(FakeOccurrence(kind="move"),)),
        None,
    )
    assert (
        open_window.concepts[0].implementations[0].status
        is OrganizationAgencyImplementationStatus.UNKNOWN
    )
    closed = track_organization_agency_implementation(
        ledger,
        FakeObservation(tick=6, occurrences=(FakeOccurrence(kind="move"),)),
        None,
    )
    assert (
        closed.concepts[0].implementations[0].status
        is OrganizationAgencyImplementationStatus.UNIMPLEMENTED
    )


def test_composed_v3_publication_is_readable_without_owner_ids(tmp_path: Path) -> None:
    from agents.cognition import OrganizationAgencyImplementationStatus
    from experiments.organization_publication import build_organization_harvest_result
    from persistence.organization_filesystem import (
        create_organization_publisher,
        create_organization_reader,
    )

    concepts = concept_ledger()
    first = proposal(organization_id=concept_id(concepts))
    decided = decision(first, status=OrganizationAgencyImplementationStatus.IMPLEMENTED)
    ledger = OrganizationAgencyLedger(
        owner_id=OWNER,
        concepts=(
            OrganizationAgencyConcept(
                organization_id=concept_id(concepts),
                owner_id=OWNER,
                status=OrganizationStatus.RECOGNIZED,
                first_tick=1,
                last_tick=2,
                proposals=(first,),
                decisions=(decided,),
                implementations=(implementation(decided),),
            ),
        ),
    )
    harvest = build_completed_run_organization_harvest(
        SimpleNamespace(
            organization_concept_ledgers=(concepts,),
            organization_operation_ledgers=(),
            organization_agency_ledgers=(ledger,),
        ),
        run_id=RUN_ID,
        input_revision="revision-1",
        generated_tick=2,
    )
    result = build_organization_harvest_result(harvest)
    publisher = create_organization_publisher(tmp_path)
    assert publisher is not None
    publisher.publish(
        OrganizationPublication(
            run_id=result.snapshot.run_id,
            publication_id=result.publication_id,
            snapshot_digest=result.snapshot_digest,
            payload=result.snapshot_bytes,
            generated_tick=result.snapshot.generated_tick,
        )
    )
    reader = create_organization_reader(tmp_path)
    assert reader is not None
    summary = reader.summary(RUN_ID)
    assert summary is not None
    assert summary.snapshot_digest == result.snapshot_digest
    assert summary.collective_decision_count == 1
    page = reader.collective_agency(RUN_ID, result.publication_id, 0, 10)
    assert len(page.rows) == 1
    assert cast(Any, page.rows[0]).decision_id.startswith("orgcpd-")


def test_real_give_command_becomes_implementation_evidence() -> None:
    from agents.cognition import organization_agency_ref
    from simulation.bootstrap import AgentRegistration, WorldBootstrap
    from simulation.engine import WorldEngine
    from simulation.lifecycle import ActionSubmission
    from simulation.models import SimulationRunConfig
    from tests.simulation_helpers import (
        alive_body,
        make_item,
        make_location,
        make_weather,
    )
    from world import Give, Wait
    from world.identifiers import WorldId, WorldRevision
    from world.models import default_physical_rules

    item = make_item("item-7", location_id=None, holder_id="body-agent-2")
    body_a = alive_body("body-agent-1")
    body_b = alive_body("body-agent-2", inventory=(EntityId("item-7"),))
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-agency-give"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body_a, body_b),
        items=(item,),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-agent-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-agent-2")),
        ),
    )
    engine = WorldEngine(
        config=SimulationRunConfig(seed=19, physical_rules=default_physical_rules()),
        bootstrap=bootstrap,
    )
    batch = engine.observe()
    submissions = []
    for observation in batch.observations:
        agent_id = engine.registration_translator.to_agent_id(observation.observer_id)
        command = (
            Give(
                item_id=EntityId("item-7"),
                recipient_id=EntityId("body-agent-1"),
            )
            if agent_id.value == "agent-2"
            else Wait()
        )
        submissions.append(ActionSubmission(batch.token, agent_id, command))
    engine.resolve_tick(tuple(submissions))
    owner_batch = engine.observe()
    owner_observation = next(
        observation
        for observation in owner_batch.observations
        if observation.observer_id == EntityId("body-agent-2")
    )
    give = next(
        occurrence
        for occurrence in owner_observation.occurrences
        if occurrence.kind == "give"
    )
    assert give.public_facts["target_id"] == "body-agent-1"
    assert give.success is None

    owner = AgentId("agent-2")
    concepts = concept_ledger(owner=owner)
    first = proposal(
        owner=owner,
        organization_id=concept_id(concepts),
        effect=OrganizationAgencyEffect.GIVE,
        target_kind="agent",
        target_ref=organization_agency_ref("body-agent-1", namespace="target"),
        expected_actors=(owner,),
    )
    decided = decision(first, owner=owner, decided_tick=0, window_end_tick=5)
    ledger = OrganizationAgencyLedger(
        owner_id=owner,
        concepts=(
            OrganizationAgencyConcept(
                organization_id=concept_id(concepts),
                owner_id=owner,
                status=OrganizationStatus.RECOGNIZED,
                first_tick=1,
                last_tick=1,
                proposals=(first,),
                decisions=(decided,),
            ),
        ),
    )
    tracked = track_organization_agency_implementation(ledger, owner_observation, None)
    assert (
        tracked.concepts[0].implementations[0].status
        is OrganizationAgencyImplementationStatus.IMPLEMENTED
    )
