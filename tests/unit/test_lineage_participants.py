"""Pure native mentorship participant cards without capture rewriting."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
)
from simulation.lineage_models import (
    LineageError,
    LineageNode,
    LineageNodeState,
    MentorshipLineageRecord,
)
from simulation.lineage_participants import (
    LineageParticipantCard,
    order_participant_cards,
    project_participant_card,
)
from simulation.models import RunId

pytestmark = pytest.mark.unit

RUN = RunId("run-participants")


def _record(
    *,
    owner_id: str = "owner-1",
    teacher_id: str = "owner-1",
    learner_id: str = "learner-1",
    lineage_id: str = "lineage-1",
    content_key: str = "content-1",
    attempts: int = 1,
    evidence: int = 0,
    acquired: int = 2,
    updated: int = 3,
) -> MentorshipLineageRecord:
    return MentorshipLineageRecord(
        owner_id=owner_id,
        teacher_id=teacher_id,
        learner_id=learner_id,
        lineage_id=lineage_id,
        root_id="root-1",
        parent_ids=(),
        content_kind="skill",
        content_key=content_key,
        hop=1,
        acquisition_tick=acquired,
        update_tick=updated,
        attempt_count=attempts,
        learning_evidence_count=evidence,
        confidence_band="medium",
        mutated=False,
        evidence_refs=(
            LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
                native_id=lineage_id,
                owner_id=owner_id,
                observed_tick=updated,
            ),
        ),
        policy_version="mentorship-reciprocity.v1",
        observed_boundary=updated,
        source_observed_boundary=updated,
        native_status="learned" if evidence else "attempt_only",
        source_revision=f"{lineage_id}:{updated}",
    )


def _node(
    record: MentorshipLineageRecord | None,
    *,
    evidence_class: str = "subjective",
    owner_id: str | None = "owner-1",
    lineage_id: str | None = None,
    state: LineageNodeState = LineageNodeState.OBSERVED,
    unresolved_reason: str | None = None,
) -> LineageNode:
    return LineageNode(
        ref=LineageNodeRef(
            run_id=RUN,
            family=LineageFamily.MENTORSHIP,
            evidence_class=LineageEvidenceClass(evidence_class),
            native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
            native_id=lineage_id or (record.lineage_id if record else "lineage-x"),
            identity_owner=owner_id,
        ),
        state=state,
        observed_tick=record.update_tick if record else None,
        unresolved_reason=unresolved_reason,
        mentorship_record=record,
    )


def test_teacher_and_learner_roles_match_explicit_fields() -> None:
    node = _node(_record(teacher_id="owner-1", learner_id="learner-1"))
    teacher = project_participant_card(node, agent_id="owner-1", role="teacher")
    assert teacher is not None
    learner = project_participant_card(node, agent_id="learner-1", role="learner")
    assert learner is not None
    both = project_participant_card(node, agent_id="owner-1", role="both")
    assert both is not None
    assert project_participant_card(node, agent_id="owner-1", role="learner") is None
    assert project_participant_card(node, agent_id="nobody", role="both") is None


def test_same_agent_can_be_teacher_and_learner() -> None:
    node = _node(_record(teacher_id="owner-1", learner_id="owner-1"))
    card = project_participant_card(node, agent_id="owner-1", role="both")
    assert card is not None
    assert card.teacher_id == card.learner_id == "owner-1"


def test_attempt_only_and_evidence_positive_are_distinguished() -> None:
    attempt = _node(_record(evidence=0))
    evidence = _node(_record(lineage_id="lineage-2", evidence=2))
    attempt_card = project_participant_card(
        attempt, agent_id="learner-1", role="learner"
    )
    evidence_card = project_participant_card(
        evidence, agent_id="learner-1", role="learner"
    )
    assert attempt_card is not None
    assert evidence_card is not None
    assert attempt_card.learning_state == "attempt_only"
    assert evidence_card.learning_state == "learning_evidence"
    assert attempt_card.learning_evidence_count == 0
    assert evidence_card.learning_evidence_count == 2


def test_owner_local_ids_do_not_merge_across_owners() -> None:
    left = _node(
        _record(owner_id="owner-a", teacher_id="owner-a"),
        owner_id="owner-a",
    )
    right = _node(
        _record(owner_id="owner-b", teacher_id="owner-b"),
        owner_id="owner-b",
    )
    left_card = project_participant_card(left, agent_id="owner-a", role="teacher")
    right_card = project_participant_card(right, agent_id="owner-b", role="teacher")
    assert left_card is not None and right_card is not None
    assert left_card.ref.key != right_card.ref.key
    assert left_card.owner_id == "owner-a"
    assert right_card.owner_id == "owner-b"
    assert left_card.lineage_id == right_card.lineage_id


def test_analytical_scope_retains_native_owner_provenance() -> None:
    node = _node(
        _record(owner_id="owner-1"),
        evidence_class="analytical",
        owner_id="owner-1",
    )
    card = project_participant_card(node, agent_id="learner-1", role="learner")
    assert card is not None
    assert card.ref.evidence_class is LineageEvidenceClass.ANALYTICAL
    assert card.ref.identity_owner == "owner-1"
    assert card.owner_id == "owner-1"


def test_subjective_scope_requires_matching_owner() -> None:
    node = _node(_record(owner_id="owner-1"), owner_id="owner-2")
    with pytest.raises(LineageError) as mismatch:
        project_participant_card(node, agent_id="learner-1", role="learner")
    assert mismatch.value.code == "invalid_participant_scope"


def test_absent_metadata_and_archived_states_are_explicit() -> None:
    assert (
        project_participant_card(_node(None), agent_id="learner-1", role="both") is None
    )
    archived = _node(_record(), state=LineageNodeState.ARCHIVED)
    card = project_participant_card(archived, agent_id="learner-1", role="learner")
    assert card is not None
    unresolved = _node(
        _record(),
        state=LineageNodeState.UNRESOLVED,
        unresolved_reason="source_gap",
    )
    unresolved_card = project_participant_card(
        unresolved, agent_id="learner-1", role="learner"
    )
    assert unresolved_card is not None


def test_unknown_role_and_non_mentorship_family_fail_closed() -> None:
    node = _node(_record())
    with pytest.raises(LineageError) as role:
        project_participant_card(node, agent_id="learner-1", role="observer")
    assert role.value.code == "invalid_participant_role"
    genealogy = LineageNode(
        ref=LineageNodeRef(
            run_id=RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
            native_id="lineage-1",
        ),
        state=LineageNodeState.OBSERVED,
        mentorship_record=_record(),
    )
    with pytest.raises(LineageError) as family:
        project_participant_card(genealogy, agent_id="learner-1", role="both")
    assert family.value.code == "invalid_participant_family"


def test_ordering_is_deterministic_and_evidence_prioritized() -> None:
    high = _node(_record(lineage_id="lineage-3", attempts=4, evidence=3, acquired=9))
    tie_a = _node(_record(lineage_id="lineage-1", attempts=2, evidence=1, acquired=5))
    tie_b = _node(_record(lineage_id="lineage-2", attempts=2, evidence=1, acquired=5))
    attempt = _node(_record(lineage_id="lineage-0", attempts=9, evidence=0, acquired=1))
    cards = [
        project_participant_card(node, agent_id="learner-1", role="learner")
        for node in (attempt, tie_b, high, tie_a)
    ]
    assert all(card is not None for card in cards)
    ordered = order_participant_cards(cards)  # type: ignore[arg-type]
    assert [card.lineage_id for card in ordered[:1]] == ["lineage-3"]
    assert {card.lineage_id for card in ordered[1:3]} == {"lineage-1", "lineage-2"}
    first_key = next(card.ref.key for card in ordered if card.lineage_id == "lineage-1")
    second_key = next(
        card.ref.key for card in ordered if card.lineage_id == "lineage-2"
    )
    assert ordered[1].ref.key == min(first_key, second_key)
    assert ordered[-1].lineage_id == "lineage-0"
    assert ordered[-1].learning_state == "attempt_only"


def test_card_is_frozen_and_excludes_content_text_or_fingerprints() -> None:
    card = project_participant_card(_node(_record()), agent_id="learner-1")
    assert isinstance(card, LineageParticipantCard)
    names = {field.name for field in fields(LineageParticipantCard)}
    assert "content_kind" in names
    assert "content_key" in names
    assert not names & {"content", "text", "fingerprint", "content_fingerprint"}
    with pytest.raises(FrozenInstanceError):
        card.content_key = "mutated"  # type: ignore[misc]
