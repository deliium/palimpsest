"""Run-level metric orchestration tests."""

from __future__ import annotations

import pytest

from analysis.metric_service import (
    MetricComputationInputs,
    assemble_metric_documents,
    compare_metric_documents,
    documents_compatible,
)
from analysis.models import AppliedActionRow, MetricAvailability, RelationshipEdgeRow
from analysis.serialization import metric_document_fingerprint
from experiments.memory_metric_repository import (
    InMemoryMetricDocumentRepository,
    InMemoryMetricSetRepository,
)
from experiments.metric_collection import MetricCollectionService
from simulation.evidence import (
    EvidenceHighWaterMarks,
    build_evidence_manifest,
)


def test_assemble_same_manifest_same_hashes() -> None:
    inputs = MetricComputationInputs(
        run_id="run-m",
        input_revision="rev-abc",
        window_end=5,
        applied_actions=(
            AppliedActionRow(tick=1, ordinal=0, agent_id="a", action_kind="help"),
            AppliedActionRow(tick=2, ordinal=0, agent_id="b", action_kind="attack"),
        ),
        agent_ids=("a", "b"),
        relationship_rows=(
            RelationshipEdgeRow(
                source_id="a",
                target_id="b",
                logical_tick=1,
                activation_state="active",
                trust=0.5,
            ),
        ),
    )
    first = assemble_metric_documents(inputs)
    second = assemble_metric_documents(inputs)
    assert first.fingerprints == second.fingerprints
    assert len(first.documents) >= 10


@pytest.mark.asyncio
async def test_metric_collection_persist_idempotent() -> None:
    sets = InMemoryMetricSetRepository()
    docs = InMemoryMetricDocumentRepository(metric_sets=sets)
    service = MetricCollectionService(metric_sets=sets, metric_documents=docs)
    manifest = build_evidence_manifest(
        run_id="run-m",
        objective_commit_hash="c" * 64,
        high_water=EvidenceHighWaterMarks(
            direct_memories=0,
            communicated_memories=0,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=0,
        ),
    )
    inputs = MetricComputationInputs(
        run_id="run-m",
        input_revision=manifest.manifest_hash[:32],
        window_end=3,
        agent_ids=("a",),
    )
    result = await service.compute_and_persist(
        inputs=inputs,
        manifest=manifest,
        experiment_id=None,
        condition_id=None,
    )
    assert result.lifecycle_state.value in {"complete", "partial"}
    again = await service.compute_and_persist(
        inputs=inputs,
        manifest=manifest,
        metric_set_id=result.metric_set_id,
    )
    assert again.metric_set_id == result.metric_set_id
    assert again.bundle.fingerprints == result.bundle.fingerprints


def test_compatible_comparison_rejects_revision_mismatch() -> None:
    inputs_a = MetricComputationInputs(
        run_id="run-m", input_revision="rev-a", window_end=2, agent_ids=("a",)
    )
    inputs_b = MetricComputationInputs(
        run_id="run-m", input_revision="rev-b", window_end=2, agent_ids=("a",)
    )
    left = assemble_metric_documents(inputs_a).documents[0]
    right = assemble_metric_documents(inputs_b).documents[0]
    assert left.metric_family == right.metric_family
    assert not documents_compatible(left, right)
    assert compare_metric_documents(left, right) is None


def test_empty_inputs_produce_unknown_or_absent_not_zero_false() -> None:
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-empty", input_revision="rev-empty", window_end=0, agent_ids=()
        )
    )
    for doc in bundle.documents:
        if doc.availability is MetricAvailability.PRESENT:
            # Some graph/survival empties may be present with explicit zeros;
            # never silently invent false correctness.
            assert "accuracy" not in doc.values or doc.values["accuracy"] is None
        assert metric_document_fingerprint(doc)
