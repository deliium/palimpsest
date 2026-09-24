"""Deterministic interference / source-confusion fixtures for V2 dynamics."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from analysis.memory_dynamics_metrics import compute_memory_dynamics
from analysis.models import (
    MEMORY_DYNAMICS_METRIC_VERSION,
    MetricAvailability,
)
from experiments.composition import map_recall_audits_to_dynamics_report
from memory.models import (
    ConceptMention,
    MemoryDistortionCode,
    MemoryDynamicsPolicy,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryQueryContext,
    MemoryQueryFilters,
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
    ReconstructionId,
)
from memory.service import InMemoryMemoryService
from world.identifiers import EntityId, WorldRevision

pytestmark = pytest.mark.unit


def _trace(
    memory_id: str,
    *,
    concept: str,
    tick: int,
    tags: tuple[str, ...] = (),
    salience: float = 0.5,
    access_count: int = 0,
    extra_concepts: tuple[str, ...] = (),
) -> MemoryTrace:
    concepts = (concept, *extra_concepts)
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=tuple(
            ConceptMention(
                mention_id=MentionId(f"{memory_id}-c{index}"),
                concept=item,
            )
            for index, item in enumerate(concepts)
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(tags=tags, location_id=EntityId("loc-1")),
        emotional_salience=salience,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=tick,
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=access_count,
    )


def _recall_request(
    *,
    tick: int,
    reconstruction_id: str,
    dynamics: MemoryDynamicsPolicy | None,
    tags: tuple[str, ...] = (),
) -> MemoryRecallRequest:
    return MemoryRecallRequest(
        retrieve=MemoryRetrieveRequest(
            current_tick=tick,
            limit=8,
            scoring_policy=MemoryScoringPolicy(
                policy_id="score",
                version="1",
                weights=MemoryScoreWeights(recency=1.0, emotional_salience=0.5),
            ),
            filters=MemoryQueryFilters(
                location_id=EntityId("loc-1"),
                require_active=True,
            ),
            context=MemoryQueryContext(
                location_id=EntityId("loc-1"),
                tags=tags,
            ),
            operation_id=f"fixture-{reconstruction_id}",
        ),
        reconstruction_id=ReconstructionId(reconstruction_id),
        reconstruction_policy=MemoryReconstructionPolicy(
            policy_id="fixture",
            version="1",
            allow_provider=False,
            max_source_traces=16,
        ),
        recall_context=MemoryRecallContext(
            location_id=EntityId("loc-1"),
            tags=tags,
        ),
        dynamics_policy=dynamics,
    )


@pytest.mark.asyncio
async def test_interference_fixture_cue_flips_and_v1_skips_dynamics() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-fix"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    await service.apply(
        MemoryMutationBatch(
            writes=(
                _trace(
                    "m-camp-a",
                    concept="gate",
                    extra_concepts=("shared",),
                    tick=4,
                    tags=("camp",),
                    salience=0.7,
                ),
                _trace(
                    "m-camp-b",
                    concept="door",
                    extra_concepts=("shared",),
                    tick=3,
                    tags=("camp",),
                    salience=0.65,
                ),
                _trace(
                    "m-river",
                    concept="river",
                    tick=5,
                    tags=("river",),
                    salience=0.9,
                ),
                _trace(
                    "m-ridge",
                    concept="ridge",
                    tick=1,
                    tags=("ridge",),
                    salience=0.3,
                ),
            )
        )
    )
    policy = MemoryDynamicsPolicy(
        interference_strength=0.85,
        competition_blend=0.2,
        source_confusion_mass=0.0,
    )

    camp = await service.recall(
        _recall_request(
            tick=10,
            reconstruction_id="recon-camp",
            dynamics=policy,
            tags=("camp",),
        )
    )
    river = await service.recall(
        _recall_request(
            tick=10,
            reconstruction_id="recon-river",
            dynamics=policy,
            tags=("river",),
        )
    )
    assert camp.audits and river.audits
    camp_winner = camp.audits[0].source_memory_ids[0].value
    river_winner = river.audits[0].source_memory_ids[0].value
    assert camp_winner != river_winner
    assert camp_winner.startswith("m-camp")
    assert river_winner == "m-river"
    assert camp.audits[0].competitor_ids
    assert (
        MemoryDistortionCode.INTERFERENCE in camp.audits[0].distortion_codes
        or MemoryDistortionCode.COMPETITION in camp.audits[0].distortion_codes
    )

    v1 = await service.recall(
        _recall_request(
            tick=10,
            reconstruction_id="recon-v1",
            dynamics=None,
            tags=("camp",),
        )
    )
    assert v1.audits == ()
    assert v1.reconstructions


@pytest.mark.asyncio
async def test_source_confusion_and_metrics_assembly() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-conf"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    await service.apply(
        MemoryMutationBatch(
            writes=(
                _trace("m-1", concept="gate", tick=5, tags=("camp",), salience=0.8),
                _trace("m-2", concept="gate", tick=4, tags=("camp",), salience=0.75),
                _trace("m-3", concept="wall", tick=3, tags=("camp",), salience=0.5),
                _trace("m-4", concept="stone", tick=2, tags=("camp",), salience=0.4),
            )
        )
    )
    policy = MemoryDynamicsPolicy(source_confusion_mass=1.0)

    first = await service.recall(
        _recall_request(
            tick=10,
            reconstruction_id="recon-1",
            dynamics=policy,
            tags=("camp",),
        )
    )
    assert first.audits
    audit = first.audits[0]
    assert audit.competitor_ids
    assert MemoryDistortionCode.SOURCE_CONFUSION in audit.distortion_codes
    assert audit.confidence_after <= audit.confidence_before + 1e-12
    assert audit.source_memory_ids
    assert set(audit.selected_ids) != set(audit.source_memory_ids)

    second = await service.recall(
        _recall_request(
            tick=11,
            reconstruction_id="recon-2",
            dynamics=policy,
            tags=("camp",),
        )
    )
    assert second.audits
    assert first.audits[0].strength_deltas or second.audits[0].strength_deltas

    report = map_recall_audits_to_dynamics_report(
        experiment_id="experiment-a-memory",
        run_id="run-conf",
        condition_id="a-reconstructive-v2",
        memory_mode="reconstructive_v2",
        audits=first.audits + second.audits,
    )
    assert report.metric_version == MEMORY_DYNAMICS_METRIC_VERSION
    doc = compute_memory_dynamics(report, input_revision="rev-fixture-1")
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["source_confusion"] > 0.0
    for key in (
        "recall_accuracy",
        "source_confusion",
        "memory_survival",
        "interference",
        "confidence_calibration",
    ):
        assert key in doc.values


def test_empty_dynamics_report_is_absent() -> None:
    report = map_recall_audits_to_dynamics_report(
        experiment_id="experiment-a-memory",
        run_id="run-empty",
        condition_id="a-reference",
        memory_mode="reference",
        audits=(),
    )
    doc = compute_memory_dynamics(report, input_revision="rev-empty")
    assert doc.availability is MetricAvailability.ABSENT
    assert doc.values == {}
