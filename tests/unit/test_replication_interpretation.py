# mypy: ignore-errors
"""V4-28 owner-relative replication interpretation and collaboration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    ReplicationCategoricalAppraisal,
    ReplicationCollaboration,
    ReplicationCollaborationAct,
    ReplicationConditionComparison,
    ReplicationInvitationStatus,
    ReplicationMeasurement,
    ReplicationMeasurementBasis,
    ReplicationMeasurementResolution,
    ReplicationOwnerContext,
    ReplicationSourceAppraisal,
    ReplicationUncertaintyKind,
    adopt_replication_design,
    build_replication_result_report,
    compare_replication_condition_sets,
    empty_replication_ledger,
    freeze_experiment_design,
    ingest_replication_report,
    interpret_replication_evidence,
    open_replication_collaboration,
    replication_ref,
    source_appraisal_for_trust,
    stage_replication_interpretation_reply,
    stage_replication_participation,
    stage_replication_result_reply,
)
from agents.cognition.experimentation import (
    ExperimentHypothesis,
    ExperimentTrial,
    HypothesisCondition,
    HypothesisConditionSlot,
    experiment_hypothesis_id,
)
from agents.models import AgentId
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId
from world.values import ItemKind

pytestmark = pytest.mark.unit

OWNER = AgentId("owner-1")
OTHER = AgentId("owner-2")
SOURCE = "body-source"


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        observer_id=EntityId("body-owner"),
        tick=3,
        items=(
            SimpleNamespace(entity_id=EntityId("item-a"), kind=ItemKind.TOOL),
            SimpleNamespace(entity_id=EntityId("item-b"), kind=ItemKind.MATERIAL),
        ),
        resources=(),
        structures=(),
        artifacts=(),
    )


def _design(conditions: tuple[HypothesisCondition, ...] = ()) -> object:
    operator = ExperimentOperator.COMBINE
    process = ExperimentProcessToken.NONE
    hypothesis = ExperimentHypothesis(
        owner_id=OWNER,
        hypothesis_id=experiment_hypothesis_id(
            OWNER, operator, "item-a", "item-b", process
        ),
        operator=operator,
        operand_a_id="item-a",
        operand_b_id="item-b",
        process_token=process,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        conditions=conditions,
        created_tick=2,
    )
    trial = ExperimentTrial(
        tick=3,
        event_id="event-9",
        outcome_class=ExperimentOutcomeClass.SUCCESS.value,
        discovery_mode="deliberate",
    )
    result = freeze_experiment_design(OWNER, hypothesis, trial, _observation())
    assert result.design is not None
    return result.design


def _measurement(
    outcome: ExperimentOutcomeClass | None,
    *,
    basis: ReplicationMeasurementBasis = ReplicationMeasurementBasis.COMMUNICATED,
    uncertainty: ReplicationUncertaintyKind = ReplicationUncertaintyKind.UNREPORTED,
) -> ReplicationMeasurement:
    possible = (
        (ExperimentOutcomeClass.SUCCESS, ExperimentOutcomeClass.FAILURE)
        if uncertainty is ReplicationUncertaintyKind.DECLARED_SET
        else ()
    )
    return ReplicationMeasurement(
        resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
        uncertainty_kind=uncertainty,
        basis=basis,
        outcome=outcome,
        possible_outcomes=possible,
    )


def _report(
    owner: AgentId,
    design: object,
    *,
    outcome: ExperimentOutcomeClass | None,
    conditions: tuple[HypothesisCondition, ...] = (),
    origin: str,
    basis: ReplicationMeasurementBasis = ReplicationMeasurementBasis.COMMUNICATED,
    source: str | None = SOURCE,
) -> object:
    return build_replication_result_report(
        owner,
        origin_report_token=replication_ref("rrep", origin),
        design_token=design.design_token,  # type: ignore[attr-defined]
        attempt_token=replication_ref("ratt", owner.value, origin),
        source_trial_token=design.source_trial_token,  # type: ignore[attr-defined]
        source_root_token=replication_ref("rrep", origin),
        measurement=_measurement(outcome, basis=basis),
        declared_measurement_basis=basis,
        performer_claim_token=replication_ref("rpart", source or "unknown", "body"),
        observed_conditions=conditions,
        reported_conditions=conditions,
        delivery_event_id=(
            "delivery-1"
            if basis is ReplicationMeasurementBasis.COMMUNICATED
            else None
        ),
        source_entity_id=source,
    )


def _ledger_with_reports(
    reports: tuple[object, ...], design: object
) -> object:
    ledger = empty_replication_ledger(OWNER)
    from agents.cognition import append_replication_design

    ledger, _ = append_replication_design(ledger, design)  # type: ignore[arg-type]
    for report in reports:
        ledger, reason = ingest_replication_report(ledger, report)  # type: ignore[arg-type]
        assert reason == "report_ingested"
    return ledger


def _interpretation(ledger: object, report_token: str) -> object:
    rows = [
        row
        for row in ledger.interpretations  # type: ignore[attr-defined]
        if report_token in row.report_tokens
    ]
    assert len(rows) == 1
    return rows[0]


def test_trust_bands_are_subjective_and_missing_trust_is_unknown() -> None:
    assert source_appraisal_for_trust(None) is ReplicationSourceAppraisal.UNKNOWN
    assert (
        source_appraisal_for_trust(0.9)
        is ReplicationSourceAppraisal.TRUSTED_TESTIMONY
    )
    assert (
        source_appraisal_for_trust(0.1)
        is ReplicationSourceAppraisal.CONTESTED_TESTIMONY
    )
    assert source_appraisal_for_trust(0.5) is ReplicationSourceAppraisal.UNKNOWN
    with pytest.raises(ValueError):
        ReplicationOwnerContext(trust_by_entity=(("body", float("nan")),))


def test_condition_comparison_never_claims_incomplete_control() -> None:
    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    weather = HypothesisCondition(HypothesisConditionSlot.WEATHER, "rain")
    assert (
        compare_replication_condition_sets((location,), (location,))
        is ReplicationConditionComparison.MATCHED
    )
    assert (
        compare_replication_condition_sets((location,), (weather,))
        is ReplicationConditionComparison.DIFFERENT
    )
    assert (
        compare_replication_condition_sets((location,), ())
        is ReplicationConditionComparison.UNKNOWN
    )


def test_conflicting_categories_survive_under_matched_conditions() -> None:
    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    design = _design((location,))
    baseline = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(location,),
        origin="origin-a",
    )
    replication = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.FAILURE,
        conditions=(location,),
        origin="origin-b",
    )
    ledger = _ledger_with_reports((baseline, replication), design)
    ledger, reason = interpret_replication_evidence(
        OWNER, ledger, ReplicationOwnerContext(), tick=5
    )
    assert reason == "interpretations_updated"
    first = _interpretation(ledger, baseline.report_token)  # type: ignore[attr-defined]
    second = _interpretation(ledger, replication.report_token)  # type: ignore[attr-defined]
    assert first.appraisal is ReplicationCategoricalAppraisal.CONFLICTING
    assert second.appraisal is ReplicationCategoricalAppraisal.CONFLICTING
    assert first.condition_comparison is ReplicationConditionComparison.MATCHED
    assert first.uncertainty_notice is True


def test_matching_categories_are_compatible_only_at_categorical_resolution() -> None:
    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    design = _design((location,))
    baseline = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(location,),
        origin="origin-a",
    )
    replication = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(location,),
        origin="origin-b",
    )
    ledger = _ledger_with_reports((baseline, replication), design)
    ledger, _ = interpret_replication_evidence(
        OWNER, ledger, ReplicationOwnerContext(), tick=5
    )
    row = _interpretation(ledger, replication.report_token)  # type: ignore[attr-defined]
    assert row.appraisal is ReplicationCategoricalAppraisal.COMPATIBLE
    assert not hasattr(row, "true")
    assert not hasattr(row, "proven")
    assert not hasattr(row, "confidence_milli")


def test_changed_and_missing_conditions_are_not_matched() -> None:
    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    weather = HypothesisCondition(HypothesisConditionSlot.WEATHER, "rain")
    design = _design((location,))
    baseline = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(location,),
        origin="origin-a",
    )
    changed = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.FAILURE,
        conditions=(weather,),
        origin="origin-b",
    )
    missing = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.FAILURE,
        origin="origin-c",
    )
    ledger = _ledger_with_reports((baseline, changed, missing), design)
    ledger, _ = interpret_replication_evidence(
        OWNER, ledger, ReplicationOwnerContext(), tick=5
    )
    changed_row = _interpretation(ledger, changed.report_token)  # type: ignore[attr-defined]
    missing_row = _interpretation(ledger, missing.report_token)  # type: ignore[attr-defined]
    assert changed_row.appraisal is ReplicationCategoricalAppraisal.NOT_COMPARABLE
    assert changed_row.condition_comparison is ReplicationConditionComparison.DIFFERENT
    assert missing_row.appraisal is ReplicationCategoricalAppraisal.INCONCLUSIVE
    assert missing_row.condition_comparison is ReplicationConditionComparison.UNKNOWN


def test_two_owners_keep_different_social_appraisals_of_the_same_report() -> None:
    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    design = _design((location,))
    baseline = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(location,),
        origin="origin-a",
    )
    replication = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.FAILURE,
        conditions=(location,),
        origin="origin-b",
    )
    trusted_ledger = _ledger_with_reports((baseline, replication), design)
    trusted_ledger, _ = interpret_replication_evidence(
        OWNER,
        trusted_ledger,
        ReplicationOwnerContext(trust_by_entity=((SOURCE, 0.95),)),
        tick=5,
    )
    contested_ledger = _ledger_with_reports((baseline, replication), design)
    contested_ledger, _ = interpret_replication_evidence(
        OWNER,
        contested_ledger,
        ReplicationOwnerContext(trust_by_entity=((SOURCE, 0.05),)),
        tick=5,
    )
    trusted = _interpretation(trusted_ledger, replication.report_token)  # type: ignore[attr-defined]
    contested = _interpretation(contested_ledger, replication.report_token)  # type: ignore[attr-defined]
    assert trusted.source_appraisal is ReplicationSourceAppraisal.TRUSTED_TESTIMONY
    assert contested.source_appraisal is ReplicationSourceAppraisal.CONTESTED_TESTIMONY
    assert trusted.appraisal is contested.appraisal


def test_own_observation_survives_contested_social_appraisal() -> None:
    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    design = _design((location,))
    baseline = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(location,),
        origin="origin-a",
    )
    own = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.FAILURE,
        conditions=(location,),
        origin="origin-b",
        basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
        source=None,
    )
    ledger = _ledger_with_reports((baseline, own), design)
    ledger, _ = interpret_replication_evidence(
        OWNER,
        ledger,
        ReplicationOwnerContext(trust_by_entity=((SOURCE, 0.0),)),
        tick=5,
    )
    row = _interpretation(ledger, own.report_token)  # type: ignore[attr-defined]
    assert row.source_appraisal is ReplicationSourceAppraisal.OWN_OBSERVATION
    assert row.appraisal is ReplicationCategoricalAppraisal.CONFLICTING


def test_duplicate_source_reports_do_not_multiply_interpretations() -> None:
    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    design = _design((location,))
    baseline = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(location,),
        origin="origin-a",
    )
    replication = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(location,),
        origin="origin-b",
    )
    ledger = _ledger_with_reports((baseline, replication), design)
    ledger, _ = interpret_replication_evidence(
        OWNER, ledger, ReplicationOwnerContext(), tick=5
    )
    before = len(ledger.interpretations)
    again, reason = interpret_replication_evidence(
        OWNER, ledger, ReplicationOwnerContext(), tick=6
    )
    assert reason == "interpretations_unchanged"
    assert len(again.interpretations) == before


def _receiver_ledger_with_invitation() -> tuple[object, object]:
    design = _design()
    ledger = empty_replication_ledger(OTHER)
    ledger, _ = adopt_replication_design(
        OTHER,
        ledger,
        design,
        delivery_event_id="design-delivery",
        received_tick=4,
        inviter_entity_id=SOURCE,
    )
    collaboration = ReplicationCollaboration(
        owner_id=OTHER,
        invitation_token=replication_ref("rinv", OTHER.value, design.design_token),
        design_token=design.design_token,
        source_trial_token=design.source_trial_token,
        inviter_entity_id=SOURCE,
        created_tick=4,
        delivery_event_id="invitation-delivery",
    )
    ledger, reason = open_replication_collaboration(ledger, collaboration)
    assert reason == "collaboration_opened"
    return ledger, design


def test_participation_reply_targets_the_verified_inviter_and_is_idempotent() -> None:
    ledger, _design_row = _receiver_ledger_with_invitation()
    invitation = ledger.collaborations[0].invitation_token
    ledger, reason = stage_replication_participation(
        ledger,
        invitation,
        actor_entity_id="body-receiver",
        act=ReplicationCollaborationAct.PARTICIPATE,
        tick=5,
    )
    assert reason == "reply_staged"
    assert ledger.collaborations[0].status is ReplicationInvitationStatus.ACCEPTED
    assert ledger.outbox[0].recipient_entity_id == SOURCE
    assert ledger.outbox[0].message_kind == "participate"
    again, reason = stage_replication_participation(
        ledger,
        invitation,
        actor_entity_id="body-other",
        act=ReplicationCollaborationAct.PARTICIPATE,
        tick=5,
    )
    assert reason == "invitation_not_pending"
    assert len(again.outbox) == 1

    decline_ledger, _decline_design = _receiver_ledger_with_invitation()
    decline_invitation = decline_ledger.collaborations[0].invitation_token
    decline_ledger, reason = stage_replication_participation(
        decline_ledger,
        decline_invitation,
        actor_entity_id="body-receiver",
        act=ReplicationCollaborationAct.DECLINE,
        tick=6,
    )
    assert reason == "reply_staged"
    assert (
        decline_ledger.collaborations[0].status
        is ReplicationInvitationStatus.DECLINED
    )
    assert decline_ledger.outbox[0].recipient_entity_id == SOURCE


def test_completed_result_and_changed_interpretation_stage_one_reply_each() -> None:
    ledger, design = _receiver_ledger_with_invitation()
    invitation = ledger.collaborations[0].invitation_token
    ledger, _ = stage_replication_participation(
        ledger,
        invitation,
        actor_entity_id="body-receiver",
        act=ReplicationCollaborationAct.PARTICIPATE,
        tick=5,
    )
    report = _report(
        OTHER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        origin="origin-r",
        basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
        source=None,
    )
    ledger, _ = ingest_replication_report(ledger, report)
    ledger, reason = stage_replication_result_reply(
        ledger, invitation, report.report_token, tick=7
    )
    assert reason == "reply_staged"
    result_entry = next(
        entry for entry in ledger.outbox if entry.message_kind == "result"
    )
    assert result_entry.recipient_entity_id == SOURCE
    assert result_entry.invitation_token == invitation
    duplicate, reason = stage_replication_result_reply(
        ledger, invitation, report.report_token, tick=7
    )
    assert reason == "reply_already_staged"
    assert len(duplicate.outbox) == len(ledger.outbox)

    ledger, _ = interpret_replication_evidence(
        OTHER, ledger, ReplicationOwnerContext(), tick=8
    )
    interpretation = ledger.interpretations[0]
    ledger, reason = stage_replication_interpretation_reply(
        ledger, invitation, interpretation.interpretation_token, tick=8
    )
    assert reason == "reply_staged"
    entries = [
        entry for entry in ledger.outbox if entry.message_kind == "interpret"
    ]
    assert len(entries) == 1
    assert entries[0].recipient_entity_id == SOURCE


def test_interpretation_is_permutation_invariant_over_retained_reports() -> None:
    from itertools import permutations

    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    design = _design((location,))
    success = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(location,),
        origin="origin-a",
    )
    failure = _report(
        OWNER,
        design,
        outcome=ExperimentOutcomeClass.FAILURE,
        conditions=(location,),
        origin="origin-b",
    )
    assessed: set[tuple[str, str]] = set()
    for order in permutations((success, failure)):
        ledger = _ledger_with_reports(order, design)
        ledger, _ = interpret_replication_evidence(
            OWNER, ledger, ReplicationOwnerContext(), tick=5
        )
        assessed.add(
            (
                _interpretation(
                    ledger, failure.report_token  # type: ignore[attr-defined]
                ).appraisal.value,
                _interpretation(
                    ledger, success.report_token  # type: ignore[attr-defined]
                ).appraisal.value,
            )
        )
    assert assessed == {("conflicting", "conflicting")}
