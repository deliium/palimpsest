"""Detached translation rows and the three translation metric families."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from agents.models import AgentId
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    metric_specification,
)
from analysis.translation_metrics import (
    CROSS_GROUP_TRANSLATION_METRIC_VERSION,
    TRANSLATION_INFLUENCE_METRIC_VERSION,
    TRANSLATION_LEARNING_METRIC_VERSION,
    TranslationAnalysisInputs,
    TranslationInfluenceRow,
    TranslationInterpretationSource,
    TranslationMappingRow,
    TranslationMessageRow,
    TranslationOutcome,
    compute_cross_group_translation,
    compute_cross_group_translation_metric,
    compute_translation_influence,
    compute_translation_influence_metric,
    compute_translation_learning,
    compute_translation_learning_metric,
    translation_label_digest,
    translation_message_rows_from_events,
    translation_referent_digest,
    translation_source_digest,
)
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId


def _mapping(
    *,
    owner: str = "alice",
    source: str = "foreign_a",
    targets: tuple[str, ...] = ("own_a",),
    status: str = "active",
    fit: str = "resolved",
    strength: str = "high",
    evidence: int = 3,
    usage: int = 1,
    channels: tuple[str, ...] = ("shared_observation",),
) -> TranslationMappingRow:
    return TranslationMappingRow(
        owner_id=owner,
        mapping_id=hashlib.sha256(f"{owner}|{source}".encode()).hexdigest(),
        source_digest=translation_source_digest(source),
        source_kind="label",
        target_label_digests=tuple(
            translation_label_digest(token) for token in targets
        ),
        target_referent_kinds=tuple("location" for _ in targets),
        target_referent_digests=tuple(
            translation_referent_digest("location", f"loc-{index}")
            for index, _ in enumerate(targets)
        ),
        status=status,
        fit=fit,
        strength_band=strength,
        evidence_count=evidence,
        usage_count=usage,
        channels=channels,
        first_tick=1,
        last_tick=3,
    )


def _message(
    *,
    speaker: str = "alice",
    listener: str = "bob",
    outcome: TranslationOutcome = TranslationOutcome.EXACT,
    source: str = "foreign_a",
    source_kind: TranslationInterpretationSource = (
        TranslationInterpretationSource.MAPPING
    ),
    cross: bool = True,
) -> TranslationMessageRow:
    return TranslationMessageRow(
        message_id=f"msg-{speaker}-{listener}-{outcome.value}",
        speaker_id=speaker,
        listener_id=listener,
        tick=2,
        source_digest=translation_source_digest(source),
        source_kind="label",
        declared_confidence_band="high",
        speaker_referent_kind="location",
        speaker_referent_digest=translation_referent_digest("location", "loc-1"),
        listener_referent_kind="location",
        listener_referent_digest=translation_referent_digest("location", "loc-1"),
        outcome=outcome,
        mapping_id=None,
        interpretation_source=source_kind,
        confidence_band="high",
        dominant_channel="shared_observation",
        cross_community=cross,
    )


def _influence(
    *,
    owner: str = "bob",
    effect: str = "outbound_term",
    outcome: str = "applied",
    command_kind: str | None = None,
) -> TranslationInfluenceRow:
    return TranslationInfluenceRow(
        owner_id=owner,
        mapping_id="m" * 64,
        message_id="msg-1",
        source_digest=translation_source_digest("foreign_a"),
        target_label_digest=translation_label_digest("own_a"),
        effect_kind=effect,
        outcome=outcome,
        tick=2,
        actor_digest=None,
        confidence_band="high",
        command_kind=command_kind,
    )


def test_metric_families_are_registered_at_115() -> None:
    assert METRIC_FAMILY_COUNT == 119
    for family, version in (
        (MetricFamilyId.TRANSLATION_LEARNING, TRANSLATION_LEARNING_METRIC_VERSION),
        (
            MetricFamilyId.CROSS_GROUP_TRANSLATION,
            CROSS_GROUP_TRANSLATION_METRIC_VERSION,
        ),
        (
            MetricFamilyId.TRANSLATION_INFLUENCE,
            TRANSLATION_INFLUENCE_METRIC_VERSION,
        ),
    ):
        spec = metric_specification(family)
        assert spec.version_identifier == version


def test_mapping_rows_are_digest_only_and_round_trip() -> None:
    row = _mapping()
    assert (
        row.source_digest == hashlib.sha256(b"translation|foreign_a").hexdigest()[:16]
    )
    assert "foreign_a" not in repr(row)
    assert "own_a" not in repr(row)


def test_learning_counts_candidates_without_fabricating_active() -> None:
    inputs = TranslationAnalysisInputs(
        mappings=(
            _mapping(status="candidate", strength="candidate"),
            _mapping(owner="bob", source="foreign_b", status="candidate"),
        ),
        expected_owner_count=2,
    )
    result = compute_translation_learning(inputs)
    assert result.mapping_count == 2
    assert result.active_count == 0
    assert result.candidate_count == 2
    document = compute_translation_learning_metric(
        result, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["active_count"] == 0


def test_learning_absent_with_zero_mappings() -> None:
    result = compute_translation_learning(TranslationAnalysisInputs())
    document = compute_translation_learning_metric(
        result, run_id="run-1", input_revision="rev-1"
    )
    assert document.availability.value == "absent"


def test_cross_group_accuracy_denominator_excludes_coverage_gaps() -> None:
    inputs = TranslationAnalysisInputs(
        messages=(
            _message(outcome=TranslationOutcome.EXACT),
            _message(outcome=TranslationOutcome.WRONG, speaker="carol"),
            _message(
                outcome=TranslationOutcome.UNRESOLVED,
                source_kind=TranslationInterpretationSource.NONE,
                speaker="dave",
            ),
            _message(
                outcome=TranslationOutcome.UNRESOLVED_INTENT,
                source_kind=TranslationInterpretationSource.NONE,
                speaker="erin",
            ),
        ),
        expected_owner_count=5,
    )
    result = compute_cross_group_translation(inputs)
    assert result.exact_count == 1
    assert result.wrong_count == 1
    assert result.unresolved_count == 1
    assert result.unresolved_intent_count == 1
    document = compute_cross_group_translation_metric(
        result, run_id="run-1", input_revision="rev-1"
    )
    ratios = dict(item.split(":") for item in document.values["ratios"].split(";"))
    assert float(ratios["exact_rate"]) == 0.5
    assert float(ratios["wrong_rate"]) == 0.5


def test_cross_group_absent_without_delivered_terms() -> None:
    result = compute_cross_group_translation(TranslationAnalysisInputs())
    document = compute_cross_group_translation_metric(
        result, run_id="run-1", input_revision="rev-1"
    )
    assert document.availability.value == "absent"
    assert result.mean_confidence_exact is None
    assert result.mean_confidence_wrong is None


def test_influence_is_descriptive_and_counted_by_effect() -> None:
    inputs = TranslationAnalysisInputs(
        messages=(_message(outcome=TranslationOutcome.WRONG),),
        influences=(
            _influence(effect="outbound_term", command_kind="talk"),
            _influence(effect="symbolic_interpretation"),
            _influence(effect="communicated_memory_overlay"),
            _influence(
                effect="outbound_term",
                outcome="ambiguous",
                command_kind="ask",
            ),
        ),
        expected_owner_count=2,
    )
    result = compute_translation_influence(inputs)
    assert result.outbound_rewrite_count == 2
    assert result.symbolic_interpretation_count == 1
    assert result.overlay_count == 1
    assert result.ambiguous_skip_count == 1
    assert result.talk_rewrite_count == 1
    assert result.ask_rewrite_count == 1
    assert result.tell_rewrite_count == 0
    document = compute_translation_influence_metric(
        result, run_id="run-1", input_revision="rev-1"
    )
    assert document.provenance.notes_code == "descriptive_association_not_causal"


def test_identical_inputs_produce_identical_documents() -> None:
    inputs = TranslationAnalysisInputs(
        mappings=(_mapping(),),
        messages=(_message(),),
        influences=(_influence(),),
        expected_owner_count=2,
    )
    first = compute_translation_learning_metric(
        compute_translation_learning(inputs),
        run_id="run-1",
        input_revision="rev-1",
    )
    second = compute_translation_learning_metric(
        compute_translation_learning(inputs),
        run_id="run-1",
        input_revision="rev-1",
    )
    assert first == second


def test_row_validation_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError, match="length_mismatch"):
        TranslationMappingRow(
            owner_id="alice",
            mapping_id="a" * 64,
            source_digest=translation_source_digest("foreign_a"),
            source_kind="label",
            target_label_digests=(translation_label_digest("own_a"),),
            target_referent_kinds=(),
            target_referent_digests=(),
            status="active",
            fit="resolved",
            strength_band="high",
            evidence_count=1,
            usage_count=0,
            channels=(),
            first_tick=1,
            last_tick=1,
        )


def test_message_harvest_reads_world_event_details() -> None:
    speaker_binding = SimpleNamespace(
        label_token="foreign_a",
        referent_kind=SimpleNamespace(value="location"),
        candidates=(SimpleNamespace(confidence=0.8, entity_id="loc-1"),),
    )
    speaker_ledger = SimpleNamespace(
        owner_id=AgentId("alice"), bindings=(speaker_binding,)
    )
    listener_ledger = SimpleNamespace(owner_id=AgentId("bob"), mappings=())
    utterance = origin_utterance(
        text="call",
        speaker_id=EntityId("body-alice"),
        communication_id="comm-1",
        relations=(
            CommunicationRelation(
                subject="foreign_a", predicate="call", object="location"
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    event = SimpleNamespace(
        event_id=SimpleNamespace(value="evt-1"),
        actor_id=EntityId("body-alice"),
        tick=2,
        details=SimpleNamespace(utterance=utterance, recipient_id=EntityId("body-bob")),
    )
    rows = translation_message_rows_from_events(
        (event,),
        (listener_ledger,),
        (speaker_ledger,),
        (),
        {"alice": "body-alice", "bob": "body-bob"},
    )
    assert len(rows) == 1
    assert rows[0].speaker_referent_digest == translation_referent_digest(
        "location", "loc-1"
    )
    assert rows[0].outcome is TranslationOutcome.UNRESOLVED
