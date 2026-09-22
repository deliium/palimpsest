"""Unit tests for opaque evidence codecs and in-memory stream/metric repos."""

from __future__ import annotations

import pytest

from agents.models import AgentId, GoalId, GoalOutcomeKind, GoalStatus
from experiments.memory_metric_repository import (
    InMemoryMetricDocumentRepository,
    InMemoryMetricSetRepository,
    InMemoryTruthSpecRepository,
)
from experiments.persistence import (
    EvidenceAvailability,
    MetricDocumentRecord,
    MetricSetLifecycle,
    MetricSetRecord,
    TruthSpecRecord,
)
from simulation.evidence import (
    ACTION_RESOLUTION_SCHEMA_VERSION,
    ActionResolutionRecord,
    EvidenceHighWaterMarks,
    GoalRevisionRecord,
    OpaqueCanonicalEnvelope,
    build_evidence_manifest,
    encode_action_resolution_evidence,
    encode_goal_transition_receipt,
    opaque_envelope_from_payload,
)
from simulation.lifecycle import ActionResolutionReason, ActionResolutionStatus
from simulation.memory_scientific_evidence import (
    InMemoryScientificEvidenceRepository,
    InMemoryStreamRepository,
)
from simulation.models import RunId
from simulation.persistence import FinalizedBoundaryBatch
from simulation.run_control import (
    StreamRecordDraft,
    StreamRecordKind,
    make_stream_envelope,
)
from simulation.runner_models import (
    ActionResolutionEvidence,
    GoalTransitionReasonCode,
    GoalTransitionReceipt,
)

pytestmark = pytest.mark.unit

_HASH = "a" * 64


def _high_water(**overrides: int) -> EvidenceHighWaterMarks:
    base = {
        "direct_memories": 0,
        "communicated_memories": 0,
        "reconstructions": 0,
        "beliefs": 0,
        "relationships": 0,
        "goals": 0,
        "resolutions": 0,
        "truth_specs": 0,
    }
    base.update(overrides)
    return EvidenceHighWaterMarks(**base)


def test_encode_goal_and_resolution_are_stable() -> None:
    receipt = GoalTransitionReceipt(
        goal_id=GoalId("goal-1"),
        owner_id=AgentId("agent-1"),
        outcome_kind=GoalOutcomeKind.REACH_PLACE,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.COMPLETED,
        tick=3,
        reason_code=GoalTransitionReasonCode.COMPLETED,
    )
    first = encode_goal_transition_receipt(receipt)
    second = encode_goal_transition_receipt(receipt)
    assert first.content_hash == second.content_hash
    evidence = ActionResolutionEvidence(
        ordinal=0,
        agent_id=AgentId("agent-1"),
        command_kind="move",
        status=ActionResolutionStatus.APPLIED,
        reason=ActionResolutionReason.OCCURRENCE,
        tick=3,
        base_revision=0,
        resulting_revision=1,
        request_id="req-1",
    )
    encoded = encode_action_resolution_evidence(evidence)
    assert encoded.schema_version == ACTION_RESOLUTION_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_in_memory_stream_monotonic_and_resume() -> None:
    evidence = InMemoryScientificEvidenceRepository()
    stream = InMemoryStreamRepository(evidence)
    run_id = RunId("run-1")
    drafts = (
        StreamRecordDraft(
            kind=StreamRecordKind.STATUS,
            envelope=make_stream_envelope(b'{"k":"status"}'),
        ),
        StreamRecordDraft(
            kind=StreamRecordKind.EVENTLESS_TICK,
            envelope=make_stream_envelope(b'{"k":"tick"}'),
            related_tick=1,
        ),
    )
    published = await stream.publish(run_id=run_id, drafts=drafts)
    assert [item.cursor for item in published] == [1, 2]
    assert await stream.high_water(run_id=run_id) == 2
    resumed = await stream.read_after(run_id=run_id, after_cursor=1, limit=10)
    assert [item.cursor for item in resumed] == [2]
    assert resumed[0].kind is StreamRecordKind.EVENTLESS_TICK


@pytest.mark.asyncio
async def test_identical_retry_and_divergent_conflict() -> None:
    repo = InMemoryScientificEvidenceRepository()
    envelope = opaque_envelope_from_payload(
        schema_version=ACTION_RESOLUTION_SCHEMA_VERSION,
        payload=b'{"tick":1,"ordinal":0}',
    )
    record = ActionResolutionRecord(
        run_id="run-1", tick=1, ordinal=0, envelope=envelope
    )
    await repo.append_action_resolution(record)
    await repo.append_action_resolution(record)
    divergent = ActionResolutionRecord(
        run_id="run-1",
        tick=1,
        ordinal=0,
        envelope=opaque_envelope_from_payload(
            schema_version=ACTION_RESOLUTION_SCHEMA_VERSION,
            payload=b'{"tick":1,"ordinal":0,"x":1}',
        ),
    )
    with pytest.raises(ValueError, match="action_resolution_conflict"):
        await repo.append_action_resolution(divergent)


@pytest.mark.asyncio
async def test_finalized_boundary_publishes_atomically() -> None:
    repo = InMemoryScientificEvidenceRepository()
    stream = InMemoryStreamRepository(repo)
    manifest = build_evidence_manifest(
        run_id="run-1",
        objective_commit_hash=_HASH,
        high_water=_high_water(resolutions=1),
    )
    resolution = ActionResolutionRecord(
        run_id="run-1",
        tick=2,
        ordinal=0,
        envelope=opaque_envelope_from_payload(
            schema_version=ACTION_RESOLUTION_SCHEMA_VERSION,
            payload=b'{"tick":2}',
        ),
    )
    published = await repo.publish_finalized_boundary(
        FinalizedBoundaryBatch(
            run_id=RunId("run-1"),
            tick=2,
            resolutions=(resolution,),
            stream_drafts=(
                StreamRecordDraft(
                    kind=StreamRecordKind.EVENT,
                    envelope=make_stream_envelope(b'{"event":1}'),
                    related_tick=2,
                ),
            ),
            manifest=manifest,
        )
    )
    assert len(published) == 1
    assert await repo.get_manifest(run_id="run-1") == manifest
    assert await stream.high_water(run_id=RunId("run-1")) == 1


@pytest.mark.asyncio
async def test_metric_set_lifecycle_and_document_link() -> None:
    sets = InMemoryMetricSetRepository()
    docs = InMemoryMetricDocumentRepository(sets)
    truths = InMemoryTruthSpecRepository()
    await truths.append_truth_spec(
        TruthSpecRecord(
            run_id="run-1",
            claim_id="claim-1",
            availability=EvidenceAvailability.AVAILABLE,
            envelope=OpaqueCanonicalEnvelope(
                schema_version="claim-truth-v1",
                content_hash=opaque_envelope_from_payload(
                    schema_version="claim-truth-v1", payload=b'{"claim":1}'
                ).content_hash,
                payload=b'{"claim":1}',
            ),
        )
    )
    metric_set = await sets.upsert_metric_set(
        MetricSetRecord(
            run_id="run-1",
            metric_set_id="set-1",
            lifecycle_state=MetricSetLifecycle.PENDING,
            evidence_manifest_hash=_HASH,
        )
    )
    running = await sets.transition_metric_set(
        run_id="run-1",
        metric_set_id="set-1",
        expected_version=metric_set.lifecycle_version,
        to_state=MetricSetLifecycle.RUNNING,
    )
    envelope = opaque_envelope_from_payload(
        schema_version="metric-document-v1", payload=b'{"family":"survival"}'
    )
    await docs.append_metric_document(
        MetricDocumentRecord(
            run_id="run-1",
            metric_set_id="set-1",
            metric_family="survival",
            evidence_manifest_hash=_HASH,
            envelope=envelope,
        )
    )
    await docs.append_metric_document(
        MetricDocumentRecord(
            run_id="run-1",
            metric_set_id="set-1",
            metric_family="survival",
            evidence_manifest_hash=_HASH,
            envelope=envelope,
        )
    )
    partial = await sets.transition_metric_set(
        run_id="run-1",
        metric_set_id="set-1",
        expected_version=running.lifecycle_version,
        to_state=MetricSetLifecycle.PARTIAL,
    )
    assert partial.lifecycle_state is MetricSetLifecycle.PARTIAL
    listed = await docs.list_metric_documents(run_id="run-1")
    assert len(listed) == 1
    assert (await truths.get_truth_spec(run_id="run-1", claim_id="claim-1")) is not None


@pytest.mark.asyncio
async def test_goal_revision_record_round_trip_codec() -> None:
    receipt = GoalTransitionReceipt(
        goal_id=GoalId("goal-2"),
        owner_id=AgentId("agent-2"),
        outcome_kind=GoalOutcomeKind.OBTAIN_ENTITY,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.ABANDONED,
        tick=5,
        reason_code=GoalTransitionReasonCode.DEATH,
    )
    envelope = encode_goal_transition_receipt(receipt)
    record = GoalRevisionRecord(
        run_id="run-1",
        goal_id=receipt.goal_id.value,
        revision=0,
        owner_id=receipt.owner_id.value,
        tick=receipt.tick,
        envelope=envelope,
    )
    repo = InMemoryScientificEvidenceRepository()
    await repo.append_goal_revision(record)
    listed = await repo.list_goal_revisions(run_id="run-1")
    assert listed == (record,)
