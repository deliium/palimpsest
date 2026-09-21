"""Controlled repeated-drift, auditability, and immutability proofs."""

from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from dataclasses import replace

import pytest

from agents.models import AgentId
from analysis.memory_drift import (
    compare_fact_sets,
    evidence_from_reconstructed_memory,
    project_memory_trace,
    project_reconstructed_memory,
)
from analysis.models import (
    MemoryDriftReport,
    ReconstructionEvidence,
    SubjectiveDerivationEdge,
)
from analysis.service import MemoryDriftAnalysisService
from analysis.sources import InMemoryMemoryEvidenceSource, InMemoryObjectiveEventSource
from memory.errors import MemoryServiceError, MemoryServiceErrorCode
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryLineage,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryRecallContext,
    MemoryRecallRequest,
    MemoryReconstructionPolicy,
    MemoryRetrieveRequest,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    ReconstructedMemory,
    ReconstructionId,
    ReconstructionRecord,
)
from memory.mutation import prepare_memory_mutation
from memory.reconstruction import MemoryRecallOrchestrator, plan_reconsolidation
from memory.service import InMemoryMemoryService
from simulation.journal import hash_world_event
from tests.fakes.scripted_reconstructor import (
    SCRIPTED_DRIFT_SCHEDULE_VERSION,
    DriftEdit,
    ScriptedDriftReconstructor,
)
from world.events import Moved, Waited, WorldEvent, make_replayable_event
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

_FORBIDDEN_LOG_SNIPPETS = (
    "I remember",
    "scripted:gate",
    "secret-narrative",
    "belief-text",
    "api_key",
    "password",
    "SELECT ",
    "dsn=",
)


def _scoring() -> MemoryScoringPolicy:
    return MemoryScoringPolicy(
        policy_id="score",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )


def _root_trace(
    *,
    observed_source_id: str | None = "evt-1",
    concepts: tuple[str, ...] = ("gate", "yard", "latch"),
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId("m-root"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(1),
        concepts=tuple(
            ConceptMention(mention_id=MentionId(f"c-{index}"), concept=item)
            for index, item in enumerate(concepts, start=1)
        ),
        entities=(
            EntityMention(
                mention_id=MentionId("e-1"),
                label="door",
                entity_id=EntityId("ent-door"),
            ),
        ),
        relations=(),
        context=MemorySituationContext(tags=("evening", "calm")),
        emotional_salience=0.5,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
            observed_source_id=(
                None if observed_source_id is None else EventId(observed_source_id)
            ),
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=0,
        lineage=MemoryLineage(),
    )


def _event() -> WorldEvent:
    return make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(2),
        details=Moved(
            destination_id=EntityId("loc-2"),
            resulting_location_id=EntityId("loc-2"),
        ),
        actor_id=EntityId("body-1"),
    )


def _default_schedule() -> tuple[DriftEdit, ...]:
    return (
        DriftEdit(
            remove_concepts=frozenset({"latch"}),
            mutate_concepts={"yard": "garden"},
            add_concepts=("rust",),
            remove_context_tags=frozenset({"calm"}),
            add_context_tags=("fog",),
            narrative_suffix="first-recall",
            confidence_delta=-0.1,
            salience_delta=-0.05,
        ),
        DriftEdit(
            remove_concepts=frozenset({"gate"}),
            add_concepts=("hinge",),
            add_entity_labels=("bolt",),
            add_relations=(("near", "door", "bolt"),),
            narrative_suffix=";second-recall",
            confidence_delta=-0.15,
            salience_delta=0.0,
        ),
        DriftEdit(
            mutate_concepts={"garden": "courtyard"},
            add_concepts=("whisper",),
            remove_context_tags=frozenset({"evening"}),
            add_context_tags=("night",),
            narrative_suffix=";third-recall",
            confidence_delta=-0.05,
            salience_delta=-0.1,
        ),
    )


@pytest.mark.asyncio
async def test_repeated_recall_measurably_drifts_with_scripted_schedule(
    caplog: pytest.LogCaptureFixture,
) -> None:
    schedule = _default_schedule()
    reconstructor = ScriptedDriftReconstructor(schedule)
    assert reconstructor.schedule_version == SCRIPTED_DRIFT_SCHEDULE_VERSION

    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    root = _root_trace()
    root_before = deepcopy(root)
    await service.apply(MemoryMutationBatch(writes=(root,)))

    objective = _event()
    event_hash_before = hash_world_event(objective)

    orchestrator = MemoryRecallOrchestrator(reconstructor)
    reconstructions: list[ReconstructionEvidence] = []
    derived_traces: list[MemoryTrace] = []
    edges: list[SubjectiveDerivationEdge] = []

    with caplog.at_level(logging.DEBUG, logger="memory.reconstruction"):
        for step in range(len(schedule)):
            parent_id = (
                MemoryId("m-root") if step == 0 else MemoryId(f"m-derived-{step}")
            )
            derived_id = MemoryId(f"m-derived-{step + 1}")
            request = MemoryRecallRequest(
                reconstruction_id=ReconstructionId(f"recon-{step + 1}"),
                retrieve=MemoryRetrieveRequest(
                    current_tick=10 + step,
                    limit=3,
                    scoring_policy=_scoring(),
                ),
                reconstruction_policy=MemoryReconstructionPolicy(
                    policy_id="recall",
                    version="1",
                    reconsolidate=True,
                ),
                recall_context=MemoryRecallContext(),
                derived_memory_id=derived_id,
            )
            result = await orchestrator.recall(service, request)
            assert len(result.reconstructions) == 1
            reconstructed = result.reconstructions[0]
            assert result.reconsolidation is not None
            intent = result.reconsolidation
            assert intent.record.policy_version == "1"
            assert intent.record.schema_version == SCRIPTED_DRIFT_SCHEDULE_VERSION
            assert intent.derived_trace.lineage.source_memory_ids
            assert (
                intent.derived_trace.lineage.reconstruction_id
                == reconstructed.reconstruction_id
            )
            assert intent.derived_trace.lineage.generation == reconstructed.generation
            assert intent.derived_trace.owner_id == AgentId("agent-1")
            assert intent.record.run_id == MemoryRunId("run-1")
            assert intent.derived_trace.provenance.observed_source_id == EventId(
                "evt-1"
            )

            apply_result = await service.apply(
                MemoryMutationBatch(
                    writes=(intent.derived_trace,),
                    reconstructions=(intent.record,),
                )
            )
            assert apply_result.reconstruction_written_count == 1
            reconstructions.append(
                evidence_from_reconstructed_memory(
                    run_id="run-1", reconstructed=reconstructed
                )
            )
            derived_traces.append(intent.derived_trace)
            edges.append(
                SubjectiveDerivationEdge(
                    derived_memory_id=derived_id.value,
                    source_memory_id=parent_id.value
                    if step == 0
                    else derived_traces[step - 1].memory_id.value,
                    ordinal=0,
                    reconstruction_id=reconstructed.reconstruction_id.value,
                )
            )

            expected = reconstructor.expected_episode_after(
                result.evidence, steps=step + 1
            )
            assert {item.concept for item in reconstructed.concepts} == set(
                expected.concepts
            )
            assert reconstructed.confidence == pytest.approx(expected.confidence)
            step_delta = compare_fact_sets(
                project_memory_trace(root if step == 0 else derived_traces[step - 1]),
                project_reconstructed_memory(reconstructed),
            )
            assert step_delta.canonical_equal is False

    stored_root = await service.get(MemoryId("m-root"))
    assert stored_root is not None
    assert stored_root == root_before
    assert stored_root.concepts == root_before.concepts
    assert stored_root.forgotten_at_tick is None
    assert hash_world_event(objective) == event_hash_before

    analysis = MemoryDriftAnalysisService(
        memory=InMemoryMemoryEvidenceSource(
            traces=(root, *derived_traces),
            reconstructions=tuple(reconstructions),
            derivation_edges=tuple(edges),
        ),
        events=InMemoryObjectiveEventSource([objective]),
    )
    report = analysis.analyze_memory_drift(
        experiment_id="exp-drift",
        run_id="run-1",
        owner_id="agent-1",
    )
    assert report.linked_count == 1
    assert len(report.chains) == 1
    assert len(report.steps) >= 3
    assert any(not step.delta.canonical_equal for step in report.steps)
    assert report.cumulative[0].canonical_equal is False
    assert "rust" in report.cumulative[0].added_concepts or any(
        "rust" in step.delta.added_concepts for step in report.steps
    )

    report_again = analysis.analyze_memory_drift(
        experiment_id="exp-drift",
        run_id="run-1",
        owner_id="agent-1",
    )
    assert report.linked_count == report_again.linked_count
    assert report.unlinked_count == report_again.unlinked_count
    assert len(report.steps) == len(report_again.steps)
    assert [
        (step.from_id, step.to_id, sorted(step.delta.added_concepts))
        for step in report.steps
    ] == [
        (step.from_id, step.to_id, sorted(step.delta.added_concepts))
        for step in report_again.steps
    ]

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    for snippet in _FORBIDDEN_LOG_SNIPPETS:
        assert snippet not in log_text
    assert "secret-narrative" not in log_text
    assert "I remember" not in log_text


@pytest.mark.asyncio
async def test_identical_inputs_yield_identical_drift_reports() -> None:
    schedule = _default_schedule()[:2]

    async def _run() -> MemoryDriftReport:
        reconstructor = ScriptedDriftReconstructor(schedule)
        scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
        service = InMemoryMemoryService(scope)
        root = _root_trace()
        await service.apply(MemoryMutationBatch(writes=(root,)))
        orchestrator = MemoryRecallOrchestrator(reconstructor)
        reconstructions: list[ReconstructionEvidence] = []
        derived: list[MemoryTrace] = []
        edges: list[SubjectiveDerivationEdge] = []
        for step in range(len(schedule)):
            derived_id = MemoryId(f"m-derived-{step + 1}")
            result = await orchestrator.recall(
                service,
                MemoryRecallRequest(
                    reconstruction_id=ReconstructionId(f"recon-{step + 1}"),
                    retrieve=MemoryRetrieveRequest(
                        current_tick=10 + step,
                        limit=3,
                        scoring_policy=_scoring(),
                    ),
                    reconstruction_policy=MemoryReconstructionPolicy(
                        policy_id="recall",
                        version="1",
                        reconsolidate=True,
                    ),
                    recall_context=MemoryRecallContext(),
                    derived_memory_id=derived_id,
                ),
            )
            intent = result.reconsolidation
            assert intent is not None
            await service.apply(
                MemoryMutationBatch(
                    writes=(intent.derived_trace,),
                    reconstructions=(intent.record,),
                )
            )
            reconstructions.append(
                evidence_from_reconstructed_memory(
                    run_id="run-1", reconstructed=result.reconstructions[0]
                )
            )
            derived.append(intent.derived_trace)
            parent = "m-root" if step == 0 else derived[step - 1].memory_id.value
            edges.append(
                SubjectiveDerivationEdge(
                    derived_memory_id=derived_id.value,
                    source_memory_id=parent,
                    ordinal=0,
                    reconstruction_id=result.reconstructions[0].reconstruction_id.value,
                )
            )
        service_analysis = MemoryDriftAnalysisService(
            memory=InMemoryMemoryEvidenceSource(
                traces=(root, *derived),
                reconstructions=tuple(reconstructions),
                derivation_edges=tuple(edges),
            ),
            events=InMemoryObjectiveEventSource([_event()]),
        )
        return service_analysis.analyze_memory_drift(
            experiment_id="exp-1",
            run_id="run-1",
            owner_id="agent-1",
        )

    first = await _run()
    second = await _run()
    assert first.metric_version == second.metric_version
    assert first.linked_count == second.linked_count
    assert len(first.cumulative) == len(second.cumulative)
    assert first.cumulative[0].added_concepts == second.cumulative[0].added_concepts
    assert first.cumulative[0].lost_concepts == second.cumulative[0].lost_concepts


@pytest.mark.asyncio
async def test_concurrent_reconsolidation_idempotent_and_conflict_rollback() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    root = _root_trace()
    await service.apply(MemoryMutationBatch(writes=(root,)))

    reconstructed = await MemoryRecallOrchestrator(
        ScriptedDriftReconstructor(_default_schedule()[:1])
    ).recall(
        service,
        MemoryRecallRequest(
            reconstruction_id=ReconstructionId("recon-conc"),
            retrieve=MemoryRetrieveRequest(
                current_tick=5,
                limit=1,
                scoring_policy=_scoring(),
            ),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall",
                version="1",
                reconsolidate=True,
            ),
            recall_context=MemoryRecallContext(),
            derived_memory_id=MemoryId("m-derived-conc"),
        ),
    )
    intent = reconstructed.reconsolidation
    assert intent is not None
    batch = MemoryMutationBatch(
        writes=(intent.derived_trace,),
        reconstructions=(intent.record,),
    )

    async def _apply_once() -> tuple[int, int]:
        result = await service.apply(batch)
        return (
            result.reconstruction_written_count,
            result.reconstruction_idempotent_count,
        )

    outcomes = await asyncio.gather(*(_apply_once() for _ in range(6)))
    written = sum(item[0] for item in outcomes)
    idempotent = sum(item[1] for item in outcomes)
    assert written == 1
    assert idempotent == 5
    assert await service.get(MemoryId("m-root")) == root
    derived = await service.get(MemoryId("m-derived-conc"))
    assert derived is not None

    conflicting = ReconstructionRecord(
        reconstruction_id=ReconstructionId("recon-conc"),
        run_id=MemoryRunId("run-1"),
        owner_id=AgentId("agent-1"),
        source_memory_ids=(MemoryId("m-root"),),
        reconstructed=replace(
            intent.record.reconstructed,
            narrative="conflicting-subjective-payload",
        ),
        created_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    with pytest.raises(MemoryServiceError) as exc:
        await service.apply(MemoryMutationBatch(reconstructions=(conflicting,)))
    assert exc.value.code is MemoryServiceErrorCode.CONFLICT
    assert await service.get(MemoryId("m-root")) == root
    assert (await service.get(MemoryId("m-derived-conc"))) == derived


def test_mutation_validation_parity_rejects_dangling_and_cross_owner() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    root = _root_trace()
    foreign = replace(
        root, owner_id=AgentId("agent-2"), memory_id=MemoryId("m-foreign")
    )
    dangling = ReconstructionRecord(
        reconstruction_id=ReconstructionId("recon-x"),
        run_id=MemoryRunId("run-1"),
        owner_id=AgentId("agent-1"),
        source_memory_ids=(MemoryId("m-missing"),),
        reconstructed=_reconstructed_for(
            root, ReconstructionId("recon-x"), sources=("m-missing",)
        ),
        created_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    with pytest.raises(MemoryServiceError) as missing:
        prepare_memory_mutation(
            MemoryMutationBatch(reconstructions=(dangling,)),
            scope=scope,
            existing_traces={root.memory_id: root},
            existing_reconstruction_hashes={},
        )
    assert missing.value.code is MemoryServiceErrorCode.NOT_FOUND

    cross = ReconstructionRecord(
        reconstruction_id=ReconstructionId("recon-y"),
        run_id=MemoryRunId("run-1"),
        owner_id=AgentId("agent-1"),
        source_memory_ids=(MemoryId("m-foreign"),),
        reconstructed=_reconstructed_for(
            foreign, ReconstructionId("recon-y"), sources=("m-foreign",)
        ),
        created_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    with pytest.raises(MemoryServiceError) as owned:
        prepare_memory_mutation(
            MemoryMutationBatch(reconstructions=(cross,)),
            scope=scope,
            existing_traces={
                root.memory_id: root,
                foreign.memory_id: foreign,
            },
            existing_reconstruction_hashes={},
        )
    assert owned.value.code in {
        MemoryServiceErrorCode.OWNERSHIP,
        MemoryServiceErrorCode.NOT_FOUND,
        MemoryServiceErrorCode.INVALID_BATCH,
    }


def _reconstructed_for(
    source: MemoryTrace,
    reconstruction_id: ReconstructionId,
    *,
    sources: tuple[str, ...],
) -> ReconstructedMemory:
    return ReconstructedMemory(
        reconstruction_id=reconstruction_id,
        owner_id=AgentId("agent-1"),
        narrative="subjective",
        concepts=source.concepts[:1]
        or (ConceptMention(mention_id=MentionId("c-x"), concept="x"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=0.5,
        emotional_salience=0.4,
        source_memory_ids=tuple(MemoryId(item) for item in sources),
        generation=1,
        reconstructed_at_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )


@pytest.mark.asyncio
async def test_subjective_reconsolidation_does_not_change_objective_event_hash() -> (
    None
):
    objective = _event()
    before = hash_world_event(objective)
    revision_before = objective.resulting_revision

    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    root = _root_trace()
    await service.apply(MemoryMutationBatch(writes=(root,)))
    result = await MemoryRecallOrchestrator(
        ScriptedDriftReconstructor(_default_schedule()[:1])
    ).recall(
        service,
        MemoryRecallRequest(
            reconstruction_id=ReconstructionId("recon-replay"),
            retrieve=MemoryRetrieveRequest(
                current_tick=5,
                limit=1,
                scoring_policy=_scoring(),
            ),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall",
                version="1",
                reconsolidate=True,
            ),
            recall_context=MemoryRecallContext(),
            derived_memory_id=MemoryId("m-derived-replay"),
        ),
    )
    intent = result.reconsolidation
    assert intent is not None
    await service.apply(
        MemoryMutationBatch(
            writes=(intent.derived_trace,),
            reconstructions=(intent.record,),
        )
    )
    assert hash_world_event(objective) == before
    assert objective.resulting_revision == revision_before
    assert objective.event_type == "move"
    waited = make_replayable_event(
        event_id=EventId("evt-wait"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=2,
        sequence=0,
        request_id=RequestId("r-2"),
        resulting_revision=WorldRevision(3),
        details=Waited(),
        actor_id=None,
    )
    # Unrelated subjective activity must not alias into other event digests.
    assert hash_world_event(waited) != before


def test_plan_reconsolidation_preserves_root_correlation() -> None:
    root = _root_trace()
    from memory.models import (
        RecallEvidence,
        RecallSourceEvidence,
        ReconstructedMemory,
    )

    reconstructed = ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        narrative="subjective gate",
        concepts=root.concepts,
        entities=root.entities,
        relations=(),
        context=root.context,
        confidence=0.7,
        emotional_salience=0.4,
        source_memory_ids=(root.memory_id,),
        generation=1,
        reconstructed_at_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    evidence = RecallEvidence(
        owner_id=AgentId("agent-1"),
        current_tick=5,
        reconstruction_id=ReconstructionId("recon-1"),
        policy=MemoryReconstructionPolicy(policy_id="recall", version="1"),
        sources=(
            RecallSourceEvidence(
                memory_id=root.memory_id,
                owner_id=root.owner_id,
                rank=1,
                score=1.0,
                concepts=root.concepts,
                entities=root.entities,
                relations=(),
                context=root.context,
                emotional_salience=root.emotional_salience,
                confidence=root.confidence,
                source_confidence=root.confidence,
                episode_age_ticks=0,
                storage_age_ticks=0,
                generation=0,
                provenance_kind=root.provenance.kind,
                observed_source_id=root.provenance.observed_source_id,
            ),
        ),
        beliefs=(),
        recall_context=MemoryRecallContext(),
        derived_memory_id=MemoryId("m-derived"),
    )
    intent = plan_reconsolidation(
        reconstructed=reconstructed,
        evidence=evidence,
        run_id=MemoryRunId("run-1"),
        source_traces={root.memory_id: root},
    )
    assert intent.derived_trace.provenance.observed_source_id == EventId("evt-1")
    assert intent.derived_trace.lineage.generation == 1
    assert intent.record.source_memory_ids == (root.memory_id,)
