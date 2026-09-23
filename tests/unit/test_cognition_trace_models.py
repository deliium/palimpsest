"""Unit tests for cognition-owned trace stage summary models."""

from __future__ import annotations

import pytest

from agents.cognition import (
    COGNITION_TRACE_SUMMARY_SCHEMA,
    FORBIDDEN_TRACE_ATTRIBUTES,
    SCIENTIFIC_TRACE_STAGE_SEQUENCE,
    CognitionTraceCountKey,
    CognitionTraceIdRef,
    CognitionTraceLlmMeta,
    CognitionTraceRefKind,
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
    CognitionTraceValidationError,
    ComponentKind,
    component_kinds_for_stage,
    stage_summaries_content_hash,
    unavailable_stage_summary,
)


def test_scientific_stage_sequence_order() -> None:
    assert SCIENTIFIC_TRACE_STAGE_SEQUENCE == (
        CognitionTraceStageKind.OBSERVATION,
        CognitionTraceStageKind.RETRIEVED_MEMORIES,
        CognitionTraceStageKind.RECONSTRUCTED_MEMORIES,
        CognitionTraceStageKind.SITUATION_MODEL,
        CognitionTraceStageKind.BELIEFS,
        CognitionTraceStageKind.EMOTIONAL_STATE,
        CognitionTraceStageKind.GOALS,
        CognitionTraceStageKind.IMAGINED_FUTURES,
        CognitionTraceStageKind.THEORY_OF_MIND,
        CognitionTraceStageKind.SELECTED_INTENTION,
        CognitionTraceStageKind.PLANNED_ACTION,
    )


def test_component_kind_mapping() -> None:
    assert component_kinds_for_stage(CognitionTraceStageKind.OBSERVATION) == frozenset(
        {ComponentKind.PERCEPTION}
    )
    assert component_kinds_for_stage(
        CognitionTraceStageKind.RETRIEVED_MEMORIES
    ) == frozenset({ComponentKind.MEMORY_RETRIEVAL})
    assert component_kinds_for_stage(
        CognitionTraceStageKind.RECONSTRUCTED_MEMORIES
    ) == frozenset({ComponentKind.MEMORY_RETRIEVAL})
    assert component_kinds_for_stage(CognitionTraceStageKind.BELIEFS) == frozenset()
    assert component_kinds_for_stage(
        CognitionTraceStageKind.THEORY_OF_MIND
    ) == frozenset()
    assert component_kinds_for_stage(
        CognitionTraceStageKind.EMOTIONAL_STATE
    ) == frozenset()


def test_stage_summary_rejects_forbidden_attributes() -> None:
    summary = CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.OBSERVATION,
        status=CognitionTraceStageStatus.COMPLETED,
        ordinal=0,
        confidence=0.5,
    )
    for name in FORBIDDEN_TRACE_ATTRIBUTES:
        assert not hasattr(summary, name)
    assert "rationale" in FORBIDDEN_TRACE_ATTRIBUTES
    assert "chain_of_thought" in FORBIDDEN_TRACE_ATTRIBUTES
    assert "prompt" in FORBIDDEN_TRACE_ATTRIBUTES
    assert "raw_response" in FORBIDDEN_TRACE_ATTRIBUTES
    assert "credentials" in FORBIDDEN_TRACE_ATTRIBUTES
    assert "endpoint" in FORBIDDEN_TRACE_ATTRIBUTES


def test_stage_summary_repr_is_metadata_only() -> None:
    summary = CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.PLANNED_ACTION,
        status=CognitionTraceStageStatus.COMPLETED,
        ordinal=10,
        confidence=0.9,
        command_kind="wait",
        id_refs=(
            CognitionTraceIdRef(kind=CognitionTraceRefKind.COMMAND, value="wait"),
        ),
        counts={CognitionTraceCountKey.CANDIDATE_COUNT.value: 1},
    )
    text = repr(summary)
    assert "wait" not in text
    assert "Observation(" not in text
    assert "chain_of_thought" not in text
    assert "prompt" not in text
    assert summary.command_kind == "wait"
    assert summary.schema_version == COGNITION_TRACE_SUMMARY_SCHEMA


def test_unavailable_requires_reason_code() -> None:
    with pytest.raises(CognitionTraceValidationError) as exc:
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.THEORY_OF_MIND,
            status=CognitionTraceStageStatus.UNAVAILABLE,
            ordinal=8,
        )
    assert exc.value.code == "unavailable_requires_reason"

    summary = unavailable_stage_summary(
        CognitionTraceStageKind.THEORY_OF_MIND,
        ordinal=8,
        reason_code="tom_not_implemented",
    )
    assert summary.status is CognitionTraceStageStatus.UNAVAILABLE
    assert summary.reason_code == "tom_not_implemented"


def test_invalid_count_key_rejected() -> None:
    with pytest.raises(CognitionTraceValidationError) as exc:
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.BELIEFS,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=4,
            counts={"free_text_narrative": 1},
        )
    assert exc.value.code == "invalid_count_key"


def test_llm_meta_allowlisted_fields_only() -> None:
    meta = CognitionTraceLlmMeta(
        provider_name="stub",
        model_name="fake-1",
        finish_reason="stop",
        input_tokens=10,
        output_tokens=4,
        total_tokens=14,
        attempts=1,
    )
    for name in FORBIDDEN_TRACE_ATTRIBUTES:
        assert not hasattr(meta, name)
    text = repr(meta)
    assert "credentials" not in text
    assert "endpoint" not in text


def test_stage_summaries_content_hash_stable() -> None:
    stages_a = (
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.OBSERVATION,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=0,
            confidence=1.0,
            counts={CognitionTraceCountKey.CLAIM_COUNT.value: 2},
        ),
        unavailable_stage_summary(
            CognitionTraceStageKind.THEORY_OF_MIND,
            ordinal=8,
            reason_code="tom_not_implemented",
        ),
    )
    stages_b = (
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.OBSERVATION,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=0,
            confidence=1.0,
            counts={CognitionTraceCountKey.CLAIM_COUNT.value: 2},
        ),
        unavailable_stage_summary(
            CognitionTraceStageKind.THEORY_OF_MIND,
            ordinal=8,
            reason_code="tom_not_implemented",
        ),
    )
    assert stage_summaries_content_hash(stages_a) == stage_summaries_content_hash(
        stages_b
    )
    different = (
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.OBSERVATION,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=0,
            confidence=0.5,
        ),
    )
    assert stage_summaries_content_hash(stages_a) != stage_summaries_content_hash(
        different
    )


def test_no_run_id_on_public_types() -> None:
    summary = unavailable_stage_summary(
        CognitionTraceStageKind.THEORY_OF_MIND,
        ordinal=8,
        reason_code="tom_not_implemented",
    )
    assert not hasattr(summary, "run_id")
    assert not hasattr(CognitionTraceIdRef, "run_id")
    assert not hasattr(CognitionTraceLlmMeta, "run_id")
