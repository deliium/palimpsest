"""Record cues mint owner-scoped record references and transitions."""

from __future__ import annotations

from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    NarrativeContent,
    NarrativeCueSummary,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeRecordCue,
    NarrativeRecordRef,
    NarrativeRecordRole,
    NarrativeSourceLossState,
    NarrativeStatus,
    NarrativeTransitionKind,
    NarrativeVariant,
    apply_narrative_update,
    default_generational_narrative_policy,
    narrative_content_fingerprint,
    narrative_variant_id,
)
from agents.models import AgentId
from tests.unit.test_cultural_narratives import _identity, _observation

_OWNER = AgentId("alice")


def _ledger(*variants: NarrativeVariant) -> NarrativeLedger:
    return NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=variants,
    )


def _variant(**overrides: object) -> NarrativeVariant:
    content = NarrativeContent(concepts=("water", "gone"), text="tell_story")
    values: dict[str, object] = {
        "variant_id": narrative_variant_id(
            _OWNER, narrative_content_fingerprint(content), 0, ""
        ),
        "owner_id": _OWNER,
        "content": content,
        "content_fingerprint": narrative_content_fingerprint(content),
        "origin": NarrativeOrigin.DURABLE_RECORD,
        "status": NarrativeStatus.ACTIVE,
        "strength": 0.5,
        "first_tick": 1,
        "last_tick": 1,
    }
    values.update(overrides)
    return NarrativeVariant(**values)  # type: ignore[arg-type]


def _cue(**overrides: object) -> NarrativeRecordCue:
    values: dict[str, object] = {
        "record_id": "record-1",
        "observed_revision": 1,
        "source_tick": 1,
        "integrity": "intact",
        "concepts": ("water", "gone"),
    }
    values.update(overrides)
    return NarrativeRecordCue(**values)  # type: ignore[arg-type]


def _update(previous: NarrativeLedger, cue: NarrativeRecordCue) -> NarrativeLedger:
    return apply_narrative_update(
        observation=_observation(tick=2),
        identity=_identity(),
        previous=previous,
        cues=NarrativeCueSummary(records=(cue,)),
        policy=default_generational_narrative_policy(),
    )


def test_record_reading_mints_durable_record_variant() -> None:
    ledger = _update(_ledger(), _cue())
    variant = ledger.variants[0]
    assert variant.origin is NarrativeOrigin.DURABLE_RECORD
    assert variant.record_refs[0].record_id == "record-1"
    assert variant.record_refs[0].role is NarrativeRecordRole.READ
    assert NarrativeTransitionKind.RECORD_READ in {
        transition.kind for transition in variant.transitions
    }
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.INTACT
    assert variant.source_loss.record_backed is True


def test_higher_revision_marks_amend_and_edit() -> None:
    previous = _ledger(
        _variant(
            record_refs=(
                NarrativeRecordRef(
                    record_id="record-1",
                    role=NarrativeRecordRole.READ,
                    observed_revision=1,
                    tick=1,
                    integrity="intact",
                ),
            )
        )
    )
    ledger = _update(previous, _cue(observed_revision=2))
    variant = ledger.variants[0]
    assert any(
        ref.observed_revision == 2 and ref.role is NarrativeRecordRole.AMENDED
        for ref in variant.record_refs
    )
    kinds = {transition.kind for transition in variant.transitions}
    assert NarrativeTransitionKind.RECORD_AMENDED in kinds
    assert NarrativeTransitionKind.EDITED in kinds


def test_copied_and_annotated_records_track_generations() -> None:
    previous = _ledger(
        _variant(
            record_refs=(
                NarrativeRecordRef(
                    record_id="record-1",
                    role=NarrativeRecordRole.READ,
                    observed_revision=1,
                    tick=1,
                    copy_generation=0,
                    annotation_revisions=0,
                ),
            )
        )
    )
    copied = _update(
        previous,
        _cue(copy_generation=1, annotation_revisions=0),
    )
    assert any(
        ref.role is NarrativeRecordRole.COPIED for ref in copied.variants[0].record_refs
    )
    annotated = _update(
        previous,
        _cue(copy_generation=0, annotation_revisions=1),
    )
    assert any(
        ref.role is NarrativeRecordRole.ANNOTATED
        for ref in annotated.variants[0].record_refs
    )
    kinds = {transition.kind for transition in annotated.variants[0].transitions}
    assert NarrativeTransitionKind.RECORD_ANNOTATED in kinds


def test_damaged_record_updates_source_loss() -> None:
    ledger = _update(
        _ledger(_variant(record_refs=())),
        _cue(integrity="damaged"),
    )
    variant = next(
        item for item in ledger.variants if item.record_refs
    )
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.PARTIAL
    assert NarrativeTransitionKind.RECORD_DAMAGED in {
        transition.kind for transition in variant.transitions
    }


def test_destroyed_record_updates_source_loss_to_lost() -> None:
    ledger = _update(
        _ledger(_variant(record_refs=())),
        _cue(integrity="destroyed"),
    )
    variant = ledger.variants[0]
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.LOST


def test_observed_damage_occurrence_becomes_record_cue() -> None:
    from agents.cognition.loop import _build_narrative_cue_summary
    from tests.unit.test_cultural_narratives import _observation
    from world.identifiers import EventId
    from world.observations import (
        ObservationAudienceRole,
        ObservationProvenance,
        ObservationSourceKind,
        ObservedOccurrence,
    )

    occurrence = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId("event-damage"),
        ),
        kind="artifact_damaged",
        audience_role=ObservationAudienceRole.WITNESS,
        public_facts={
            "artifact_id": "record-1",
            "content_revision": 2,
            "integrity": "damaged",
        },
    )
    cues = _build_narrative_cue_summary(
        artifact_interpretations=None,
        retrieve_context=None,
        observation=_observation(tick=2, occurrences=(occurrence,)),
        durable_records_active=True,
    )
    assert len(cues.records) == 1
    assert cues.records[0].record_id == "record-1"
    assert cues.records[0].integrity == "damaged"
    ledger = apply_narrative_update(
        observation=_observation(tick=2),
        identity=_identity(),
        previous=_ledger(_variant(record_refs=())),
        cues=cues,
        policy=default_generational_narrative_policy(),
    )
    variant = next(item for item in ledger.variants if item.record_refs)
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.PARTIAL
    assert NarrativeTransitionKind.RECORD_DAMAGED in {
        transition.kind for transition in variant.transitions
    }
