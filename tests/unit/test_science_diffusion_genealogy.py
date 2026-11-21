# mypy: ignore-errors
"""V4-33 context joins: V3 genealogy, organization, migration, society, translation."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.practical_knowledge import (
    KnowledgeTransmissionOrigin,
    PracticalKnowledgeKind,
    PracticalKnowledgeLedger,
    SubjectivePracticalKnowledge,
)
from agents.models import AgentId
from analysis.science_diffusion_contract import (
    DiffusionContextFlag,
    DiffusionLane,
    DiffusionOccurrence,
    DiffusionReason,
    DiffusionResolution,
    DiffusionStage,
    EvidenceKind,
    EvidenceRef,
    ScienceKind,
    ScienceVersionKey,
)
from experiments.catalog import (
    base_runner_config_from_scenario,
    experiment_scientific_institutions,
)
from experiments.science_diffusion_genealogy import (
    MigrationQualification,
    OrganizationalService,
    OrganizationContextWindow,
    SocietyAssignment,
    SocietyContextWindow,
    TranslationApplication,
    join_science_diffusion_context,
)
from simulation.models import RunId, StochasticIdentity
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

RUN = "run-sdf-context"


def _config():
    body_1 = alive_body("body-1")
    body_2 = alive_body("body-2", location_id="loc-2")
    base = base_runner_config_from_scenario(
        seed=73,
        stochastic_identity=StochasticIdentity("sdf-context"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-sdf-context"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-1", adjacent=("loc-2",)),
                make_location("loc-2", adjacent=("loc-1",)),
            ),
            bodies=(body_1, body_2),
            weather=(make_weather("loc-1"), make_weather("loc-2")),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=body_1.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-2"),
                entity_id=body_2.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-2")),
            ),
        ),
        max_ticks=96,
    )
    definition = experiment_scientific_institutions(base, max_ticks=96)
    return {row.condition_id: row.runner_config for row in definition.conditions}[
        "institutions-combined-v56"
    ]


class _Boundary:
    def __init__(self, boundary, inventory):
        self.boundary = boundary
        self.inventory = inventory

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


async def _fixture(tick: int = 2):
    runner = await SimulationRunner.from_config(
        _config(),
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.initialize_finalized_boundary()
        boundary = await runner.export_finalized_research_boundary()
        inventory = runner.engine.detached_objective_facts()
    boundary = dataclasses.replace(
        boundary,
        boundary_tick=type(boundary.boundary_tick)(tick),
        boundary_revision=WorldRevision(tick),
    )
    inventory = dataclasses.replace(inventory, tick=tick, revision=tick)
    return boundary, inventory


def _occurrence(
    *,
    tick: int = 1,
    lane: DiffusionLane = DiffusionLane.SPEECH,
    event_id: str = "evt-1",
    carrier_id: str | None = None,
    content_revision: int | None = None,
    source: ScienceVersionKey | None = None,
) -> DiffusionOccurrence:
    return DiffusionOccurrence(
        run_id=RUN,
        lane=lane,
        occurrence_kind="test",
        tick=tick,
        first_observed_boundary=tick,
        evidence=EvidenceRef(
            kind=EvidenceKind.EVENT,
            run_id=RUN,
            tick=tick,
            event_id=event_id,
            sequence=0,
        ),
        stage=(
            DiffusionStage.INTERPRETED
            if lane is DiffusionLane.RECORDS
            else DiffusionStage.DELIVERED
        ),
        actor_id="agent-1",
        counterparty_id="agent-2",
        source_version=source,
        carrier_id=carrier_id,
        content_revision=content_revision,
    )


def _key() -> ScienceVersionKey:
    return ScienceVersionKey(
        run_id=RUN,
        owner_id="agent-1",
        kind=ScienceKind.HYPOTHESIS,
        local_id="h1",
        revision_index=0,
    )


@pytest.mark.asyncio
async def test_exact_teaching_entry_links_v3_node() -> None:
    boundary, inventory = await _fixture()
    entry = SubjectivePracticalKnowledge(
        entry_id="entry-1",
        owner_id=AgentId("agent-2"),
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key="tech:foraging",
        content_fingerprint=("cue:teach:foraging",),
        origin=KnowledgeTransmissionOrigin.TEACHING,
        parent_entry_ids=(),
        lineage_root_id="root-1",
        hop_index=1,
        mutated=False,
        evidence_refs=("teach:evt-1",),
        acquired_tick=1,
        active=True,
        source_agent_id=AgentId("agent-1"),
        teacher_agent_id=AgentId("agent-1"),
    )
    ledger = PracticalKnowledgeLedger(
        owner_id=AgentId("agent-2"), entries=(entry,)
    )
    owners = []
    for owner in boundary.owners:
        checkpoint = owner.runtime_checkpoint
        if owner.owner_id == AgentId("agent-2"):
            checkpoint = dataclasses.replace(
                checkpoint, practical_knowledge=ledger
            )
        owners.append(dataclasses.replace(owner, runtime_checkpoint=checkpoint))
    boundary = dataclasses.replace(boundary, owners=tuple(owners))
    occurrence = _occurrence(
        tick=1, lane=DiffusionLane.TEACHING, event_id="evt-1"
    )
    result = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        observed_boundary=1,
    )
    assert len(result.genealogy) == 1
    link = result.genealogy[0]
    assert link.v3_node_key == "knowledge:agent-2:entry-1"
    assert link.relation == "teaching_uptake"
    assert link.ambiguous is False


@pytest.mark.asyncio
async def test_missing_or_guessed_genealogy_anchor_does_not_link() -> None:
    boundary, inventory = await _fixture()
    occurrence = _occurrence(
        tick=1, lane=DiffusionLane.TEACHING, event_id="evt-unknown"
    )
    result = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        observed_boundary=1,
    )
    assert result.genealogy == ()
    assert DiffusionReason.GENEALOGY_ANCHOR_MISSING.value in result.diagnostics


@pytest.mark.asyncio
async def test_organization_requires_exact_carrier_service() -> None:
    boundary, inventory = await _fixture(tick=40)
    occurrence = _occurrence(
        tick=40, carrier_id="artifact-1", content_revision=0
    )
    window = OrganizationContextWindow(
        start_tick=0,
        end_tick_exclusive=32,
        candidates=(
            (
                "org-analytical-1",
                (
                    OrganizationalService(
                        owner_id="agent-1",
                        contributor=True,
                        candidate_id="org-analytical-1",
                    ),
                ),
            ),
        ),
    )
    shared = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        organization_windows=(window,),
        observed_boundary=40,
    )
    assert (
        DiffusionContextFlag.SHARED_ORG_CONTEXT
        in shared.occurrences[0].context_flags
    )

    exact = OrganizationContextWindow(
        start_tick=0,
        end_tick_exclusive=32,
        candidates=(
            (
                "org-analytical-1",
                (
                    OrganizationalService(
                        owner_id="agent-1",
                        contributor=True,
                        candidate_id="org-analytical-1",
                        service_carrier_id="artifact-1",
                        service_content_revision=0,
                    ),
                ),
            ),
        ),
    )
    mediated = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        organization_windows=(exact,),
        observed_boundary=40,
    )
    assert (
        DiffusionContextFlag.ORGANIZATION_MEDIATED
        in mediated.occurrences[0].context_flags
    )


@pytest.mark.asyncio
async def test_cross_society_requires_unique_disjoint_assignments() -> None:
    boundary, inventory = await _fixture(tick=40)
    occurrence = _occurrence(tick=40)
    window = SocietyContextWindow(
        start_tick=0,
        end_tick_exclusive=32,
        assignments=(
            SocietyAssignment(owner_id="agent-1", candidate_id="msoc-a"),
            SocietyAssignment(owner_id="agent-2", candidate_id="msoc-b"),
        ),
    )
    result = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        society_windows=(window,),
        observed_boundary=40,
    )
    assert DiffusionContextFlag.CROSS_SOCIETY in result.occurrences[0].context_flags

    ambiguous = SocietyContextWindow(
        start_tick=0,
        end_tick_exclusive=32,
        assignments=(
            SocietyAssignment(owner_id="agent-1", candidate_id="msoc-a"),
            SocietyAssignment(owner_id="agent-1", candidate_id="msoc-b"),
            SocietyAssignment(owner_id="agent-2", candidate_id="msoc-b"),
        ),
    )
    rejected = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        society_windows=(ambiguous,),
        observed_boundary=40,
    )
    assert (
        DiffusionContextFlag.CROSS_SOCIETY
        not in rejected.occurrences[0].context_flags
    )
    assert DiffusionReason.MEMBERSHIP_UNKNOWN.value in rejected.diagnostics


@pytest.mark.asyncio
async def test_migration_confirms_only_after_qualified_arrival() -> None:
    boundary, inventory = await _fixture(tick=40)
    key = _key()
    occurrence = _occurrence(tick=5, source=key)
    qualification = MigrationQualification(
        owner_id="agent-1",
        version_key=key,
        departure_tick=5,
        arrival_tick=8,
        qualified_boundary=12,
        journey_id="journey-1",
    )
    result = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        migration_qualifications=(qualification,),
        observed_boundary=40,
    )
    carried = [
        row for row in result.occurrences if row.lane is DiffusionLane.MIGRATION
    ]
    assert carried and carried[0].tick == 12
    assert (
        DiffusionContextFlag.CARRIED_ACROSS_REGION
        in carried[0].context_flags
    )

    unqualified = dataclasses.replace(qualification, completed=False)
    rejected = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        migration_qualifications=(unqualified,),
        observed_boundary=40,
    )
    assert not [
        row for row in rejected.occurrences if row.lane is DiffusionLane.MIGRATION
    ]
    assert DiffusionReason.UNQUALIFIED_ARRIVAL.value in rejected.diagnostics


@pytest.mark.asyncio
async def test_translation_binding_and_ambiguity() -> None:
    boundary, inventory = await _fixture(tick=10)
    occurrence = _occurrence(tick=10, event_id="msg-1")
    application = TranslationApplication(
        message_id="msg-1",
        mapping_id="map-1",
        source_digest="digest-1",
        owner_id="agent-2",
        applied=True,
        target_binding_witnessed=True,
    )
    bound = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        translation_applications=(application,),
        observed_boundary=10,
    )
    assert (
        DiffusionContextFlag.TRANSLATION_APPLIED
        in bound.occurrences[0].context_flags
    )

    ambiguous = dataclasses.replace(application, ambiguous=True)
    rejected = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=(occurrence,),
        versions=(),
        translation_applications=(ambiguous,),
        observed_boundary=10,
    )
    assert rejected.occurrences[0].resolution is DiffusionResolution.AMBIGUOUS
    assert rejected.occurrences[0].reason is DiffusionReason.TRANSLATION_UNBOUND
